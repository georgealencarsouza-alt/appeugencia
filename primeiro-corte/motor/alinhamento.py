"""Alinha o que foi falado nos takes com o roteiro aprovado.

Para cada frase do roteiro:
  1. procura todas as tentativas dela em todos os takes (janelas de palavras
     comparadas com o texto do roteiro, tolerando erros de transcrição);
  2. escolhe a melhor; em empate técnico, fica com a mais recente, porque quem
     erra costuma repetir até acertar;
  3. dentro da tentativa escolhida, marca vícios ("é", "ahn", "né") e
     repetições ("o o valor") para remoção;
  4. quebra em trechos onde houver pausa maior que a da ficha.

O resultado é uma lista de trechos (arquivo, início, fim) na ordem do roteiro,
com as palavras de cada trecho já casadas com a grafia do roteiro.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from .ficha import Ritmo
from .roteiro import Frase, Roteiro, normalizar
from .transcricao import Palavra

VICIOS = {"e", "eh", "ahn", "ah", "hum", "hm", "humm", "uh", "um", "tipo", "ne", "entao", "assim", "aham"}
SIMILARIDADE_MINIMA = 0.6      # abaixo disso a frase conta como "não falada"
MARGEM_EMPATE = 0.08           # tentativas dentro dessa margem da melhor contam como empate
PALAVRA_PARECIDA = 80          # fuzz.ratio mínimo para considerar a palavra do take igual à do roteiro


@dataclass
class Take:
    caminho: Path
    palavras: list[Palavra]
    ordem: int  # ordem de gravação (índice na lista de takes)


@dataclass
class PalavraAlinhada:
    take: int
    indice: int               # índice da palavra no take
    inicio: float
    fim: float
    texto_falado: str
    texto_legenda: str        # grafia do roteiro quando casou; senão, o que foi falado
    casou: bool               # True se corresponde a uma palavra do roteiro
    removida: str | None = None   # "vicio", "repeticao" ou None


@dataclass
class Ocorrencia:
    frase: int
    take: int
    i_ini: int
    i_fim: int                # exclusivo
    similaridade: float

    def sobrepoe(self, outra: "Ocorrencia") -> bool:
        return self.take == outra.take and self.i_ini < outra.i_fim and outra.i_ini < self.i_fim


@dataclass
class FraseAlinhada:
    frase: Frase
    ocorrencia: Ocorrencia | None
    tentativas: int                           # quantas tentativas plausíveis foram achadas
    palavras: list[PalavraAlinhada] = field(default_factory=list)
    faltando: list[str] = field(default_factory=list)  # palavras do roteiro que não foram ditas

    @property
    def encontrada(self) -> bool:
        return self.ocorrencia is not None


@dataclass
class Trecho:
    take: int
    caminho: Path
    inicio: float
    fim: float
    frase: int
    bloco_id: str
    tipo_bloco: str
    palavras: list[PalavraAlinhada]

    @property
    def duracao(self) -> float:
        return self.fim - self.inicio


def _aproximar(take_norm: list[str], frase_norm: list[str]) -> list[str]:
    """Troca palavras do take pela palavra do roteiro mais parecida (corrige erro de transcrição)."""
    vocab = set(frase_norm)
    saida = []
    for w in take_norm:
        if w in vocab or len(w) <= 2:
            saida.append(w)
            continue
        melhor = max(vocab, key=lambda v: fuzz.ratio(w, v))
        saida.append(melhor if fuzz.ratio(w, melhor) >= PALAVRA_PARECIDA else w)
    return saida


def _candidatas(frase: Frase, takes: list[Take]) -> list[Ocorrencia]:
    alvo = frase.normalizadas
    n = len(alvo)
    inicio_alvo = set(alvo[: min(3, n)])
    saida: list[Ocorrencia] = []
    for t_idx, take in enumerate(takes):
        norm = _aproximar([p.norm for p in take.palavras], alvo)
        melhores_por_inicio: list[Ocorrencia] = []
        for i in range(len(norm)):
            if norm[i] not in inicio_alvo:
                continue
            melhor = None
            for tam in range(max(1, n - 3), n + 4):
                if i + tam > len(norm):
                    break
                sim = Levenshtein.normalized_similarity(alvo, norm[i: i + tam])
                if melhor is None or sim > melhor.similaridade + 1e-9:
                    melhor = Ocorrencia(frase=frase.indice, take=t_idx, i_ini=i, i_fim=i + tam, similaridade=sim)
            if melhor and melhor.similaridade >= SIMILARIDADE_MINIMA:
                melhores_por_inicio.append(melhor)
        # elimina janelas que são a mesma tentativa deslocada: fica a de maior similaridade
        melhores_por_inicio.sort(key=lambda o: -o.similaridade)
        escolhidas: list[Ocorrencia] = []
        for o in melhores_por_inicio:
            if not any(o.sobrepoe(e) for e in escolhidas):
                escolhidas.append(o)
        saida.extend(escolhidas)
    return saida


def _preferencia(o: Ocorrencia, takes: list[Take]) -> tuple:
    return (takes[o.take].ordem, o.i_ini)


def _mapear_palavras(frase: Frase, oc: Ocorrencia, take: Take, ritmo: Ritmo) -> tuple[list[PalavraAlinhada], list[str]]:
    janela = take.palavras[oc.i_ini: oc.i_fim]
    norm = _aproximar([p.norm for p in janela], frase.normalizadas)
    casamento: dict[int, int] = {}  # índice na janela -> índice no roteiro
    ops = Levenshtein.editops(frase.normalizadas, norm)
    # reconstrói o alinhamento a partir das operações de edição
    i_r = i_t = 0
    for op in list(ops) + [None]:
        alvo_r = op.src_pos if op else len(frase.normalizadas)
        alvo_t = op.dest_pos if op else len(norm)
        while i_r < alvo_r and i_t < alvo_t:
            casamento[i_t] = i_r
            i_r += 1
            i_t += 1
        if op is None:
            break
        if op.tag == "replace":
            # substituição só conta como casamento se a palavra for parecida (erro de transcrição)
            if fuzz.ratio(frase.normalizadas[op.src_pos], norm[op.dest_pos]) >= 60:
                casamento[op.dest_pos] = op.src_pos
            i_r, i_t = op.src_pos + 1, op.dest_pos + 1
        elif op.tag == "delete":   # palavra do roteiro que não foi dita
            i_r, i_t = op.src_pos + 1, op.dest_pos
        elif op.tag == "insert":   # palavra dita que não está no roteiro
            i_r, i_t = op.src_pos, op.dest_pos + 1

    palavras: list[PalavraAlinhada] = []
    for j, p in enumerate(janela):
        casou = j in casamento
        palavras.append(PalavraAlinhada(
            take=oc.take, indice=oc.i_ini + j, inicio=p.inicio, fim=p.fim, texto_falado=p.texto,
            texto_legenda=frase.palavras[casamento[j]] if casou else p.texto, casou=casou))

    # vícios e repetições que não estão no roteiro
    confiancas = [p.confianca for p in janela]
    for j, pa in enumerate(palavras):
        if pa.casou:
            continue
        n = normalizar(pa.texto_falado)
        vizinhos = {normalizar(palavras[k].texto_falado) for k in (j - 1, j + 1) if 0 <= k < len(palavras)}
        if ritmo.remover_repeticoes and n in vizinhos:
            pa.removida = "repeticao"
        elif ritmo.remover_vicios and n in VICIOS:
            pa.removida = "vicio"
        elif ritmo.remover_vicios and _hesitacao(palavras, j, confiancas[j]):
            pa.removida = "hesitacao"

    # palavras soltas nas pontas da janela (fora do roteiro) saem sempre
    while palavras and not palavras[0].casou:
        palavras[0].removida = palavras[0].removida or "borda"
        palavras = palavras[1:]
    while palavras and not palavras[-1].casou:
        palavras[-1].removida = palavras[-1].removida or "borda"
        palavras = palavras[:-1]

    ditas = set(casamento.values())
    faltando = [frase.palavras[k] for k in range(len(frase.palavras)) if k not in ditas]
    return palavras, faltando


def _hesitacao(palavras: list[PalavraAlinhada], j: int, confianca: float) -> bool:
    """Palavra fora do roteiro, isolada entre palavras do roteiro e com cara de tropeço.

    Fala improvisada de verdade ("gente", "olha só") costuma vir colada nas
    vizinhas; tropeço vem cercado de pausa ou com transcrição incerta.
    Só remove sequências de até 2 palavras fora do roteiro.
    """
    ini = j
    while ini > 0 and not palavras[ini - 1].casou:
        ini -= 1
    fim = j
    while fim + 1 < len(palavras) and not palavras[fim + 1].casou:
        fim += 1
    if fim - ini + 1 > 2 or ini == 0 or fim == len(palavras) - 1:
        return False
    pausa_antes = palavras[ini].inicio - palavras[ini - 1].fim
    pausa_depois = palavras[fim + 1].inicio - palavras[fim].fim
    return confianca < 0.5 or max(pausa_antes, pausa_depois) >= 0.2


def alinhar(roteiro: Roteiro, takes: list[Take], ritmo: Ritmo | None = None) -> list[FraseAlinhada]:
    ritmo = ritmo or Ritmo()
    frases = roteiro.frases()
    candidatas = {f.indice: _candidatas(f, takes) for f in frases}

    # Escolha global: frases com melhor tentativa decidem primeiro; tentativas não podem se sobrepor.
    ordem = sorted(frases, key=lambda f: -max((o.similaridade for o in candidatas[f.indice]), default=0))
    escolhidas: dict[int, Ocorrencia] = {}
    for f in ordem:
        livres = [o for o in candidatas[f.indice] if not any(o.sobrepoe(e) for e in escolhidas.values())]
        if not livres:
            continue
        topo = max(o.similaridade for o in livres)
        empatadas = [o for o in livres if o.similaridade >= topo - MARGEM_EMPATE]
        escolhidas[f.indice] = max(empatadas, key=lambda o: _preferencia(o, takes))

    resultado = []
    for f in frases:
        oc = escolhidas.get(f.indice)
        if oc is None:
            resultado.append(FraseAlinhada(frase=f, ocorrencia=None, tentativas=0, faltando=list(f.palavras)))
            continue
        palavras, faltando = _mapear_palavras(f, oc, takes[oc.take], ritmo)
        resultado.append(FraseAlinhada(frase=f, ocorrencia=oc, tentativas=len(candidatas[f.indice]),
                                       palavras=palavras, faltando=faltando))
    return resultado


def trechos(alinhadas: list[FraseAlinhada], takes: list[Take], ritmo: Ritmo | None = None) -> list[Trecho]:
    """Converte frases alinhadas em trechos contínuos de fala, cortando pausas longas e palavras removidas."""
    ritmo = ritmo or Ritmo()
    saida: list[Trecho] = []
    for fa in alinhadas:
        if not fa.encontrada:
            continue
        take = takes[fa.ocorrencia.take]
        todas = take.palavras
        grupo: list[PalavraAlinhada] = []

        def fechar():
            if not grupo:
                return
            primeira, ultima = grupo[0], grupo[-1]
            anterior_fim = todas[primeira.indice - 1].fim if primeira.indice > 0 else 0.0
            proxima_ini = todas[ultima.indice + 1].inicio if ultima.indice + 1 < len(todas) else ultima.fim + 1.0
            inicio = max(anterior_fim, primeira.inicio - ritmo.respiro_inicio_s, 0.0)
            fim = min(proxima_ini, ultima.fim + ritmo.respiro_fim_s)
            saida.append(Trecho(take=fa.ocorrencia.take, caminho=take.caminho, inicio=inicio, fim=fim,
                                frase=fa.frase.indice, bloco_id=fa.frase.bloco_id, tipo_bloco=fa.frase.tipo,
                                palavras=list(grupo)))
            grupo.clear()

        for pa in fa.palavras:
            if pa.removida:
                fechar()
                continue
            if grupo:
                pausa = pa.inicio - grupo[-1].fim
                pulou = pa.indice != grupo[-1].indice + 1
                if pausa > ritmo.pausa_max_s or pulou:
                    fechar()
            grupo.append(pa)
        fechar()
    return _sem_sobreposicao(saida)


def _sem_sobreposicao(saida: list[Trecho]) -> list[Trecho]:
    """Trechos vizinhos do mesmo take não podem repetir áudio: divide a folga entre eles."""
    for a, b in zip(saida, saida[1:]):
        if a.take == b.take and b.inicio < a.fim and b.inicio >= a.inicio:
            meio = (a.palavras[-1].fim + b.palavras[0].inicio) / 2
            a.fim, b.inicio = meio, meio
    return saida
