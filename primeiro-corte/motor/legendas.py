"""Gera as legendas e os textos na tela em ASS (renderizados pelo libass do FFmpeg).

A legenda usa o texto do roteiro, não o da transcrição: a grafia sai certa
mesmo quando o modelo de fala erra uma palavra.
"""
from __future__ import annotations

from pathlib import Path

from .ficha import Ficha
from .montagem import PalavraSaida, Plano

PAUSA_QUEBRA_S = 0.35   # pausa que força novo bloco de legenda
CARACTERES_LINHA = 18   # quebra de linha aproximada para o modo palavra
CARACTERES_FRASE = 26


def _cor_ass(hexa: str, alfa: int = 0) -> str:
    h = hexa.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


def _tempo(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _quebrar(palavras: list[str], limite: int) -> str:
    linhas, atual = [], ""
    for w in palavras:
        if atual and len(atual) + 1 + len(w) > limite:
            linhas.append(atual)
            atual = w
        else:
            atual = f"{atual} {w}".strip()
    if atual:
        linhas.append(atual)
    return "\\N".join(linhas)


def _blocos(palavras: list[PalavraSaida], tamanho: int) -> list[list[PalavraSaida]]:
    blocos, atual = [], []
    for i, p in enumerate(palavras):
        if atual and (len(atual) >= tamanho or p.inicio - atual[-1].fim > PAUSA_QUEBRA_S):
            blocos.append(atual)
            atual = []
        atual.append(p)
        if p.fim_de_frase:
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    return blocos


def _equilibrar(blocos: list[list[PalavraSaida]], maximo: int) -> list[list[PalavraSaida]]:
    """Divide frases longas em partes de tamanho parecido (evita sobrar 'das outras.' sozinho)."""
    saida = []
    for b in blocos:
        partes = -(-len(b) // maximo)   # teto
        tam = -(-len(b) // partes)
        saida.extend(b[i:i + tam] for i in range(0, len(b), tam))
    return saida


def gerar_ass(plano: Plano, ficha: Ficha, destino: str | Path) -> Path:
    leg = ficha.legenda
    fmt = ficha.formato
    W, H = fmt.largura, fmt.altura
    escala = H / 1920
    alinhamento = 5 if leg.posicao == "centro" else 2
    margem = {"centro": 0, "centro_baixo": int(560 * escala), "baixo": int(260 * escala)}[leg.posicao]
    tn = ficha.texto_na_tela
    estilos = [
        # Name, Fontname, Fontsize, Primary, Secondary, Outline, Back, Bold, Italic, Underline, StrikeOut,
        # ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        f"Style: Legenda,{leg.fonte},{int(leg.tamanho * escala)},{_cor_ass(leg.cor)},{_cor_ass(leg.cor_destaque)},"
        f"&H00000000,&H64000000,{-1 if leg.negrito else 0},0,0,0,100,100,0,0,1,{leg.contorno},2,{alinhamento},"
        f"80,80,{margem},1",
        f"Style: Gancho,{leg.fonte},{int(76 * escala)},{_cor_ass(tn.cor_texto)},&H000000FF,"
        f"{_cor_ass(tn.cor_fundo)},{_cor_ass(tn.cor_fundo)},-1,0,0,0,100,100,0,0,"
        f"{3 if tn.fundo == 'caixa' else 1},{18 if tn.fundo == 'caixa' else 5},0,8,90,90,{int(250 * escala)},1",
        f"Style: Titulo,{leg.fonte},{int(68 * escala)},{_cor_ass(tn.cor_texto)},&H000000FF,"
        f"{_cor_ass(tn.cor_fundo)},{_cor_ass(tn.cor_fundo)},-1,0,0,0,100,100,0,0,"
        f"{3 if tn.fundo == 'caixa' else 1},{14 if tn.fundo == 'caixa' else 4},0,8,90,90,{int(250 * escala)},1",
        f"Style: CTA,{leg.fonte},{int(66 * escala)},{_cor_ass('#111111')},&H000000FF,"
        f"{_cor_ass(leg.cor_destaque)},{_cor_ass(leg.cor_destaque)},-1,0,0,0,100,100,0,0,3,16,0,8,"
        f"90,90,{int(250 * escala)},1",
    ]
    eventos: list[str] = []

    def dialogo(inicio: float, fim: float, estilo: str, texto: str, camada: int = 0) -> None:
        if fim - inicio < 0.04:
            return
        eventos.append(f"Dialogue: {camada},{_tempo(inicio)},{_tempo(fim)},{estilo},,0,0,0,,{texto}")

    destaque = _cor_ass(leg.cor_destaque)
    normal = _cor_ass(leg.cor)

    def formatar(w: PalavraSaida, atual: bool) -> str:
        t = _escapar(w.texto.upper() if leg.caixa_alta else w.texto)
        cor = destaque if (atual and leg.destacar_palavra_atual) or (w.chave and leg.destacar_palavras_chave) else normal
        if cor == normal:
            return t
        pulo = "\\fscx108\\fscy108" if atual and leg.destacar_palavra_atual else ""
        return f"{{\\1c{cor}{pulo}}}{t}{{\\1c{normal}\\fscx100\\fscy100}}"

    palavras = plano.palavras()
    if leg.modo == "palavra":
        blocos = _blocos(palavras, leg.palavras_por_bloco)
        for b_i, bloco in enumerate(blocos):
            fim_bloco = blocos[b_i + 1][0].inicio if b_i + 1 < len(blocos) else bloco[-1].fim + 0.25
            fim_bloco = min(fim_bloco, bloco[-1].fim + 0.6)
            for i, w in enumerate(bloco):
                ini = w.inicio if i else bloco[0].inicio
                fim = bloco[i + 1].inicio if i + 1 < len(bloco) else fim_bloco
                textos = [formatar(x, x is w) for x in bloco]
                dialogo(ini, fim, "Legenda", _quebrar_formatado(bloco, textos, leg.caixa_alta))
    elif leg.modo == "frase":
        blocos = _equilibrar(_blocos(palavras, 10_000), 12)
        for b_i, bloco in enumerate(blocos):
            fim_bloco = blocos[b_i + 1][0].inicio if b_i + 1 < len(blocos) else bloco[-1].fim + 0.3
            textos = [formatar(x, False) for x in bloco]
            dialogo(bloco[0].inicio, min(fim_bloco, bloco[-1].fim + 0.8), "Legenda",
                    _quebrar_formatado(bloco, textos, leg.caixa_alta, CARACTERES_FRASE))

    for s in plano.sobreposicoes:
        estilo = {"gancho": "Gancho", "titulo": "Titulo", "cta": "CTA"}[s.tipo]
        # segue o estilo da legenda: referência sem caixa alta gera título sem caixa alta
        texto = _escapar(s.texto.upper() if (leg.caixa_alta and s.tipo != "titulo") else s.texto)
        entrada = "{\\fad(120,120)}"
        dialogo(s.inicio, s.fim, estilo, entrada + _quebrar(texto.split(), 20), camada=1)

    conteudo = "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        *estilos, "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *eventos, "",
    ])
    destino = Path(destino)
    destino.write_text(conteudo, encoding="utf-8")
    return destino


def _quebrar_formatado(bloco: list[PalavraSaida], textos: list[str], caixa_alta: bool,
                       limite: int = CARACTERES_LINHA) -> str:
    """Quebra linhas pelo tamanho do texto visível, preservando as tags de cor."""
    linhas, atual, tamanho = [], [], 0
    for w, t in zip(bloco, textos):
        visivel = len(w.texto)
        if atual and tamanho + 1 + visivel > limite:
            linhas.append(" ".join(atual))
            atual, tamanho = [], 0
        atual.append(t)
        tamanho += visivel + (1 if tamanho else 0)
    if atual:
        linhas.append(" ".join(atual))
    return "\\N".join(linhas)
