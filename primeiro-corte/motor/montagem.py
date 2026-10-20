"""Montagem: transforma trechos alinhados + ficha num plano de edição (EDL).

O plano é independente do renderizador. É ele que o app vai mostrar e deixar
ajustar (trocar take de uma frase, mudar o zoom de um trecho) antes de
renderizar de novo.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .alinhamento import Trecho
from .ficha import INTERVALO_ZOOM_S, Ficha
from .roteiro import Roteiro, normalizar


@dataclass
class PalavraSaida:
    texto: str          # grafia do roteiro
    inicio: float       # tempo no vídeo final
    fim: float
    chave: bool         # é palavra-chave do roteiro
    fim_de_frase: bool


@dataclass
class Segmento:
    caminho: str
    take: int
    origem_inicio: float
    origem_fim: float
    saida_inicio: float
    saida_fim: float
    bloco_id: str
    tipo_bloco: str
    frase: int
    zoom_inicio: float      # 1.0 = enquadramento original
    zoom_fim: float
    ancora: tuple[float, float] = (0.5, 0.4)   # ponto do quadro (0..1) que a reenquadração preserva
    palavras: list[PalavraSaida] = field(default_factory=list)
    continua: bool = False   # continuação direta do segmento anterior (só muda o zoom; áudio sem fade)

    @property
    def duracao(self) -> float:
        return self.origem_fim - self.origem_inicio


@dataclass
class Sobreposicao:
    """Texto na tela que não é legenda: gancho, títulos e CTA."""
    tipo: str          # "gancho", "titulo" ou "cta"
    texto: str
    inicio: float
    fim: float


@dataclass
class Plano:
    segmentos: list[Segmento]
    sobreposicoes: list[Sobreposicao]
    duracao: float
    ficha: dict

    def salvar(self, caminho: str | Path) -> None:
        Path(caminho).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def palavras(self) -> list[PalavraSaida]:
        return [p for s in self.segmentos for p in s.palavras]


def montar(trechos: list[Trecho], roteiro: Roteiro, ficha: Ficha,
           ancoras: dict[int, tuple[float, float]] | None = None) -> Plano:
    if not trechos:
        raise ValueError("Nenhum trecho para montar: nenhuma frase do roteiro foi encontrada nos takes.")
    ancoras = ancoras or {}
    chaves = roteiro.chaves_normalizadas()
    segmentos: list[Segmento] = []
    t = 0.0
    for tr in trechos:
        dur = tr.duracao
        palavras = []
        for i, pa in enumerate(tr.palavras):
            # palavrinha fora do roteiro ("o", "e", "aí") fica no áudio, mas não suja a legenda:
            # na maioria das vezes é erro de transcrição, não algo que a pessoa quis dizer
            if not pa.casou and len(normalizar(pa.texto_falado)) <= 2:
                continue
            ini = t + max(0.0, pa.inicio - tr.inicio)
            fim = t + min(dur, pa.fim - tr.inicio)
            palavras.append(PalavraSaida(
                texto=pa.texto_legenda, inicio=round(ini, 3), fim=round(max(fim, ini + 0.05), 3),
                chave=normalizar(pa.texto_legenda) in chaves,
                fim_de_frase=pa.texto_legenda.rstrip().endswith((".", "?", "!")) or
                (i == len(tr.palavras) - 1 and tr is trechos[-1])))
        segmentos.append(Segmento(
            caminho=str(tr.caminho), take=tr.take, origem_inicio=round(tr.inicio, 3), origem_fim=round(tr.fim, 3),
            saida_inicio=round(t, 3), saida_fim=round(t + dur, 3), bloco_id=tr.bloco_id, tipo_bloco=tr.tipo_bloco,
            frase=tr.frase, zoom_inicio=1.0, zoom_fim=1.0, ancora=ancoras.get(tr.take, (0.5, 0.4)),
            palavras=palavras))
        t += dur

    intervalo = INTERVALO_ZOOM_S[ficha.movimento.zoom_frequencia]
    if intervalo is not None and ficha.movimento.zoom_tipo == "corte":
        segmentos = _dividir_longos(segmentos, intervalo)
    _aplicar_zoom(segmentos, ficha)
    sobreposicoes = _sobreposicoes(segmentos, roteiro, ficha, t)
    return Plano(segmentos=segmentos, sobreposicoes=sobreposicoes, duracao=round(t, 3), ficha=ficha.para_dict())


def _dividir_longos(segmentos: list[Segmento], intervalo: float) -> list[Segmento]:
    """Divide trechos longos em pontos entre palavras para permitir punch-in sem cortar a fala.

    Prefere dividir logo antes de uma palavra-chave (o punch-in cai nela) ou
    depois de uma vírgula/fim de frase; senão, no espaço entre palavras mais
    perto do intervalo da ficha.
    """
    saida: list[Segmento] = []
    for seg in segmentos:
        pedacos = [seg]
        while pedacos[-1].duracao > intervalo * 1.4 and len(pedacos[-1].palavras) >= 4:
            atual = pedacos[-1]
            ps = atual.palavras
            alvo = atual.saida_inicio + intervalo
            melhor, nota_melhor = None, None
            for i in range(2, len(ps) - 1):           # pelo menos 2 palavras de cada lado
                corte = (ps[i - 1].fim + ps[i].inicio) / 2
                if corte - atual.saida_inicio < intervalo * 0.5 or atual.saida_fim - corte < intervalo * 0.4:
                    continue
                nota = abs(corte - alvo)
                if ps[i].chave:
                    nota -= intervalo * 0.4
                if ps[i - 1].texto.endswith((",", ".", "?", "!", ";", ":")):
                    nota -= intervalo * 0.3
                if nota_melhor is None or nota < nota_melhor:
                    melhor, nota_melhor = (i, corte), nota
            if melhor is None:
                break
            i, corte = melhor
            desl = corte - atual.saida_inicio
            meio_origem = atual.origem_inicio + desl
            esquerda = Segmento(**{**atual.__dict__, "origem_fim": round(meio_origem, 3), "saida_fim": round(corte, 3),
                                   "palavras": ps[:i]})
            direita = Segmento(**{**atual.__dict__, "origem_inicio": round(meio_origem, 3),
                                  "saida_inicio": round(corte, 3), "palavras": ps[i:], "continua": True})
            pedacos[-1:] = [esquerda, direita]
        saida.extend(pedacos)
    return saida


def _aplicar_zoom(segmentos: list[Segmento], ficha: Ficha) -> None:
    mov = ficha.movimento
    intervalo = INTERVALO_ZOOM_S[mov.zoom_frequencia]
    z = mov.zoom_intensidade
    if intervalo is not None:
        if mov.zoom_tipo == "corte":
            # Punch-in seco: alterna perto/longe nos cortes, respeitando o intervalo da ficha.
            # Trechos com palavra-chave puxam o "perto" para si.
            perto = False
            desde_troca = intervalo  # permite trocar já no primeiro corte
            anterior_bloco = None
            for seg in segmentos:
                tem_chave = any(p.chave for p in seg.palavras)
                novo_bloco = seg.bloco_id != anterior_bloco
                if desde_troca >= intervalo or (tem_chave and not perto) or (novo_bloco and anterior_bloco):
                    perto = (not perto) if not tem_chave else True
                    desde_troca = 0.0
                escala = z if perto else 1.0
                seg.zoom_inicio = seg.zoom_fim = escala
                desde_troca += seg.duracao
                anterior_bloco = seg.bloco_id
        else:
            # Suave: aproximação lenta ao longo de cada frase, alternando com trechos parados.
            frase_anterior = None
            ligado = False
            for seg in segmentos:
                if seg.frase != frase_anterior:
                    ligado = not ligado
                    frase_anterior = seg.frase
                if ligado:
                    seg.zoom_inicio, seg.zoom_fim = 1.0, z
    if ficha.gancho.zoom_inicial and segmentos:
        primeiro = segmentos[0]
        primeiro.zoom_inicio, primeiro.zoom_fim = 1.0, max(1.06, min(z, 1.1))
        # o punch-in seguinte precisa ser visível: se ficaria quase igual ao fim do push-in, volta para o aberto
        if len(segmentos) > 1 and mov.zoom_tipo == "corte":
            seg2 = segmentos[1]
            if seg2.palavras and seg2.palavras[0].chave:
                # palavra-chave: fecha ainda mais que o fim do push-in
                seg2.zoom_inicio = seg2.zoom_fim = round(min(1.3, primeiro.zoom_fim + 0.1), 3)
            elif abs(seg2.zoom_inicio - primeiro.zoom_fim) < 0.06:
                seg2.zoom_inicio = seg2.zoom_fim = 1.0 if seg2.continua else z


def _sobreposicoes(segmentos: list[Segmento], roteiro: Roteiro, ficha: Ficha, total: float) -> list[Sobreposicao]:
    saida: list[Sobreposicao] = []
    for bloco in roteiro.blocos:
        if not bloco.texto_tela:
            continue
        segs = [s for s in segmentos if s.bloco_id == bloco.id]
        if not segs:
            continue
        ini, fim = segs[0].saida_inicio, segs[-1].saida_fim
        if bloco.tipo == "gancho" and ficha.gancho.texto_na_tela:
            saida.append(Sobreposicao("gancho", bloco.texto_tela, ini, min(fim, ini + ficha.gancho.duracao_s)))
        elif bloco.tipo == "cta" and ficha.fechamento.cta_na_tela:
            saida.append(Sobreposicao("cta", bloco.texto_tela, ini, total))
        elif bloco.tipo == "desenvolvimento" and ficha.texto_na_tela.titulos:
            saida.append(Sobreposicao("titulo", bloco.texto_tela, ini, min(fim, ini + 2.5)))
    return saida
