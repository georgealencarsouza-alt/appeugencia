"""Ficha de estilo: o contrato entre "entender a referência" e "editar o vídeo".

Regra: só entra aqui o que (1) dá para medir ou julgar numa referência e
(2) o editor sabe aplicar. Se um parâmetro não está na ficha, a IA pode até
perceber na referência, mas a montagem não consegue usar.

Cada campo extraído de uma referência carrega a origem do valor:
  - "medido": calculado por código (cortes, pausas, cor)
  - "ia":     julgado por modelo multimodal (estilo de legenda, texto na tela)
  - "padrao": não deu para extrair; veio do preset e precisa de confirmação
"""
from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from statistics import median
from typing import Any

FREQUENCIAS_ZOOM = ("nenhum", "baixo", "medio", "alto")
# Intervalo médio (s) entre mudanças de zoom para cada frequência.
INTERVALO_ZOOM_S = {"nenhum": None, "baixo": 6.0, "medio": 3.5, "alto": 2.0}


@dataclass
class Formato:
    largura: int = 1080
    altura: int = 1920
    fps: int = 30
    duracao_alvo_s: float | None = None  # só informativo no MVP; não cortamos conteúdo para caber


@dataclass
class Ritmo:
    pausa_max_s: float = 0.25        # pausa maior que isso entre palavras vira corte
    respiro_inicio_s: float = 0.06   # folga antes da primeira palavra de um trecho
    respiro_fim_s: float = 0.10      # folga depois da última palavra de um trecho
    remover_vicios: bool = True      # "é", "ahn", "tipo", "né" que não estão no roteiro
    remover_repeticoes: bool = True  # gagueira: "o o valor"


@dataclass
class Gancho:
    texto_na_tela: bool = True   # mostra o texto_tela do bloco de gancho
    zoom_inicial: bool = True    # push-in suave no primeiro trecho
    duracao_s: float = 3.0


@dataclass
class Legenda:
    modo: str = "palavra"            # "palavra" (poucas palavras por vez), "frase" ou "nenhuma"
    palavras_por_bloco: int = 3
    caixa_alta: bool = True
    fonte: str = "Poppins"
    negrito: bool = True
    tamanho: int = 84
    cor: str = "#FFFFFF"
    cor_destaque: str = "#FFD400"
    contorno: int = 6
    posicao: str = "centro_baixo"    # "centro", "centro_baixo", "baixo"
    destacar_palavras_chave: bool = True
    destacar_palavra_atual: bool = True


@dataclass
class Movimento:
    zoom_frequencia: str = "medio"   # um de FREQUENCIAS_ZOOM
    zoom_intensidade: float = 1.12   # 1.12 = 12% mais perto
    zoom_tipo: str = "corte"         # "corte" (punch-in seco) ou "suave"


@dataclass
class TextoNaTela:
    titulos: bool = True             # texto_tela dos blocos que não são gancho
    fundo: str = "caixa"             # "caixa" ou "nenhum"
    cor_fundo: str = "#111111"
    cor_texto: str = "#FFFFFF"


@dataclass
class Audio:
    normalizar: bool = True
    alvo_lufs: float = -14.0
    musica: str | None = None        # caminho do arquivo de música
    musica_volume: float = 0.10


@dataclass
class Cor:
    tom: str = "neutro"              # "neutro", "quente" ou "frio"
    contraste: float = 1.0
    saturacao: float = 1.0


@dataclass
class Fechamento:
    cta_na_tela: bool = True
    fade_final_s: float = 0.3


@dataclass
class Ficha:
    versao: int = 1
    nome: str = "equilibrado"
    formato: Formato = field(default_factory=Formato)
    ritmo: Ritmo = field(default_factory=Ritmo)
    gancho: Gancho = field(default_factory=Gancho)
    legenda: Legenda = field(default_factory=Legenda)
    movimento: Movimento = field(default_factory=Movimento)
    texto_na_tela: TextoNaTela = field(default_factory=TextoNaTela)
    audio: Audio = field(default_factory=Audio)
    cor: Cor = field(default_factory=Cor)
    fechamento: Fechamento = field(default_factory=Fechamento)
    # caminho "secao.campo" -> "medido" | "ia" | "padrao" | "manual"
    origem: dict[str, str] = field(default_factory=dict)

    # ---------- serialização ----------
    def para_dict(self) -> dict[str, Any]:
        return asdict(self)

    def salvar(self, caminho: str | Path) -> None:
        Path(caminho).write_text(json.dumps(self.para_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "Ficha":
        ficha = cls()
        for f in fields(cls):
            if f.name not in dados:
                continue
            atual = getattr(ficha, f.name)
            if is_dataclass(atual):
                for k, v in dados[f.name].items():
                    if hasattr(atual, k):
                        setattr(atual, k, v)
            else:
                setattr(ficha, f.name, dados[f.name])
        ficha.validar()
        return ficha

    @classmethod
    def carregar(cls, caminho: str | Path) -> "Ficha":
        return cls.de_dict(json.loads(Path(caminho).read_text(encoding="utf-8")))

    def com(self, **ajustes: Any) -> "Ficha":
        """Cópia com ajustes no formato {"legenda.caixa_alta": False}."""
        nova = copy.deepcopy(self)
        for caminho, valor in ajustes.items():
            secao, campo = caminho.replace("__", ".").split(".")
            setattr(getattr(nova, secao), campo, valor)
            nova.origem[f"{secao}.{campo}"] = "manual"
        nova.validar()
        return nova

    def validar(self) -> None:
        erros = []
        if self.movimento.zoom_frequencia not in FREQUENCIAS_ZOOM:
            erros.append(f"movimento.zoom_frequencia inválida: {self.movimento.zoom_frequencia}")
        if not 1.0 <= self.movimento.zoom_intensidade <= 1.5:
            erros.append("movimento.zoom_intensidade deve ficar entre 1.0 e 1.5")
        if self.movimento.zoom_tipo not in ("corte", "suave"):
            erros.append("movimento.zoom_tipo deve ser 'corte' ou 'suave'")
        if self.legenda.modo not in ("palavra", "frase", "nenhuma"):
            erros.append("legenda.modo deve ser 'palavra', 'frase' ou 'nenhuma'")
        if self.legenda.posicao not in ("centro", "centro_baixo", "baixo"):
            erros.append("legenda.posicao inválida")
        if self.cor.tom not in ("neutro", "quente", "frio"):
            erros.append("cor.tom deve ser 'neutro', 'quente' ou 'frio'")
        if not 0.05 <= self.ritmo.pausa_max_s <= 2.0:
            erros.append("ritmo.pausa_max_s deve ficar entre 0.05 e 2.0")
        if self.legenda.palavras_por_bloco < 1:
            erros.append("legenda.palavras_por_bloco deve ser >= 1")
        if erros:
            raise ValueError("Ficha inválida:\n- " + "\n- ".join(erros))

    def resumo(self) -> str:
        """Tradução da ficha em linguagem de eugência (o que aparece na tela do app)."""
        p = self.ritmo.pausa_max_s
        ritmo = "acelerado" if p <= 0.18 else "médio" if p <= 0.4 else "calmo"
        leg = {"palavra": f"{self.legenda.palavras_por_bloco} palavras por vez", "frase": "frase inteira",
               "nenhuma": "sem legenda"}[self.legenda.modo]
        if self.legenda.modo != "nenhuma" and self.legenda.caixa_alta:
            leg += ", caixa alta"
        zoom = "sem zoom" if self.movimento.zoom_frequencia == "nenhum" else (
            f"zoom {self.movimento.zoom_frequencia} ({self.movimento.zoom_tipo})")
        return f"Ritmo {ritmo} · Legenda: {leg} · {zoom} · Cor {self.cor.tom}"


PRESETS: dict[str, Ficha] = {
    "equilibrado": Ficha(),
    "dinamico": Ficha(
        nome="dinamico",
        ritmo=Ritmo(pausa_max_s=0.15, respiro_inicio_s=0.04, respiro_fim_s=0.07),
        legenda=Legenda(palavras_por_bloco=2, tamanho=92),
        movimento=Movimento(zoom_frequencia="alto", zoom_intensidade=1.15),
    ),
    "calmo": Ficha(
        nome="calmo",
        ritmo=Ritmo(pausa_max_s=0.5, respiro_inicio_s=0.1, respiro_fim_s=0.2),
        legenda=Legenda(modo="frase", caixa_alta=False, tamanho=64, destacar_palavra_atual=False),
        movimento=Movimento(zoom_frequencia="baixo", zoom_tipo="suave", zoom_intensidade=1.06),
    ),
}


def preset(nome: str) -> Ficha:
    if nome not in PRESETS:
        raise KeyError(f"Preset desconhecido: {nome}. Opções: {', '.join(PRESETS)}")
    return copy.deepcopy(PRESETS[nome])


def consolidar(fichas: list[Ficha]) -> Ficha:
    """Junta as fichas de várias referências do mesmo cliente numa só.

    Números: mediana. Categorias e booleanos: maioria (empate fica com a primeira).
    Campos "padrao" (não extraídos) não votam se alguma ficha mediu o valor.
    """
    if not fichas:
        raise ValueError("Nenhuma ficha para consolidar")
    if len(fichas) == 1:
        return copy.deepcopy(fichas[0])
    base = copy.deepcopy(fichas[0])
    base.nome = "consolidada"
    base.origem = {}
    for secao_f in fields(Ficha):
        secao = getattr(base, secao_f.name)
        if not is_dataclass(secao):
            continue
        for campo_f in fields(secao):
            chave = f"{secao_f.name}.{campo_f.name}"
            votantes = [f for f in fichas if f.origem.get(chave, "padrao") != "padrao"] or fichas
            valores = [getattr(getattr(f, secao_f.name), campo_f.name) for f in votantes]
            if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valores):
                valor = median(valores)
                if all(isinstance(v, int) for v in valores):
                    valor = int(round(valor))
            else:
                contagem: dict[Any, int] = {}
                for v in valores:
                    contagem[json.dumps(v)] = contagem.get(json.dumps(v), 0) + 1
                valor = json.loads(max(contagem, key=lambda k: contagem[k]))
            setattr(secao, campo_f.name, valor)
            origens = {f.origem.get(chave, "padrao") for f in votantes}
            base.origem[chave] = "padrao" if origens == {"padrao"} else ("ia" if "ia" in origens else "medido")
    base.validar()
    return base
