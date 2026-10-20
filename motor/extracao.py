"""Extração: olha uma referência e preenche a ficha de estilo.

Regra: medir com código o que dá para medir; pedir ao modelo de visão só o
que é julgamento (estilo de legenda, texto na tela). Cada campo da ficha
registra de onde veio o valor, para a eugência saber o que confirmar.

Medições por código:
  - cortes por minuto e duração média dos planos (detecção de troca de cena)
  - punch-in: em cada corte, compara os quadros antes/depois e estima a escala
  - ritmo da fala: palavras por segundo e distribuição das pausas
  - tom de cor: média do canal amarelo-azul (Lab) em quadros amostrados
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from pathlib import Path

import numpy as np

from . import midia
from .ficha import Ficha, consolidar, preset
from .pipeline import transcrever_com_cache

LIMIAR_CENA = 0.12
MODELO_IA = os.environ.get("MOTOR_MODELO_IA", "claude-sonnet-5-5")


# ---------------- medições ----------------
def detectar_cortes(caminho: str | Path, minimo: float = 0.04, fator: float = 4.0) -> list[float]:
    """Cortes = picos na diferença entre quadros consecutivos.

    Um limiar fixo de "troca de cena" perde os jump cuts e punch-ins de vídeo
    de cabeça falante (mesmo cenário, mesma pessoa). Aqui um quadro conta como
    corte quando a diferença dele é bem maior que a dos quadros ao redor.
    """
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(caminho), "-vf",
         "scale=320:-2,select='gte(scene,0)',metadata=print:key=lavfi.scene_score", "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    tempos = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]
    notas = [float(s) for s in re.findall(r"lavfi\.scene_score=([0-9.]+)", proc.stderr)]
    n = min(len(tempos), len(notas))
    tempos, notas = tempos[:n], np.array(notas[:n])
    cortes: list[float] = []
    for i in range(1, n):
        vizinhos = np.concatenate([notas[max(0, i - 15): i], notas[i + 1: i + 16]])
        base = float(np.median(vizinhos)) if len(vizinhos) else 0.0
        if notas[i] >= max(minimo, base * fator, LIMIAR_CENA if base > 0.03 else 0):
            if not cortes or tempos[i] - cortes[-1] > 0.25:  # picos colados são o mesmo corte
                cortes.append(tempos[i])
    return cortes


def escala_entre(a: np.ndarray, b: np.ndarray) -> float | None:
    """Escala aproximada de b em relação a a (1.15 = b está 15% mais perto)."""
    import cv2

    ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(1500)
    ka, da = orb.detectAndCompute(ga, None)
    kb, db = orb.detectAndCompute(gb, None)
    if da is None or db is None or len(ka) < 12 or len(kb) < 12:
        return None
    pares = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(pares) < 12:
        return None
    pa = np.float32([ka[m.queryIdx].pt for m in pares])
    pb = np.float32([kb[m.trainIdx].pt for m in pares])
    matriz, inliers = cv2.estimateAffinePartial2D(pa, pb, ransacReprojThreshold=3.0)
    if matriz is None or inliers is None or inliers.sum() < 10:
        return None
    return float(np.hypot(matriz[0, 0], matriz[1, 0]))


def medir(caminho: str | Path) -> dict:
    inf = midia.info(caminho)
    dur = max(inf.duracao, 0.1)
    cortes = detectar_cortes(caminho)

    escalas = []
    for t in cortes:
        par = midia.quadros(caminho, [max(0.0, t - 0.12), min(dur - 0.05, t + 0.12)], largura=540)
        if len(par) == 2:
            s = escala_entre(par[0], par[1])
            if s:
                escalas.append(s)
    punch = [s for s in escalas if abs(np.log(s)) > np.log(1.04)]

    palavras = transcrever_com_cache(Path(caminho)) if inf.tem_audio else []
    pausas = [b.inicio - a.fim for a, b in zip(palavras, palavras[1:])]
    pausas = [p for p in pausas if p >= 0]
    fala_s = (palavras[-1].fim - palavras[0].inicio) if len(palavras) > 1 else 0.0

    amostras = midia.quadros(caminho, [dur * (i + 0.5) / 6 for i in range(6)], largura=360)
    b_lab = None
    if amostras:
        import cv2

        b_lab = float(np.mean([cv2.cvtColor(im, cv2.COLOR_RGB2LAB)[:, :, 2].mean() - 128 for im in amostras]))

    return {
        "arquivo": str(caminho),
        "duracao_s": round(dur, 2),
        "vertical": inf.vertical,
        "cortes": len(cortes),
        "cortes_por_minuto": round(len(cortes) / dur * 60, 1),
        "plano_medio_s": round(dur / (len(cortes) + 1), 2),
        "cortes_com_escala_medida": len(escalas),
        "punch_ins": len(punch),
        "escala_mediana_punch": round(float(np.median([max(s, 1 / s) for s in punch])), 3) if punch else None,
        "palavras": len(palavras),
        "palavras_por_segundo": round(len(palavras) / fala_s, 2) if fala_s else None,
        "pausa_p50_s": round(float(np.percentile(pausas, 50)), 3) if pausas else None,
        "pausa_p90_s": round(float(np.percentile(pausas, 90)), 3) if pausas else None,
        "pausa_max_s": round(max(pausas), 3) if pausas else None,
        "cor_b_lab": round(b_lab, 2) if b_lab is not None else None,
        "transcricao": " ".join(p.texto for p in palavras),
    }


def _ficha_por_medidas(m: dict) -> Ficha:
    f = preset("equilibrado")
    f.nome = Path(m["arquivo"]).stem
    o = f.origem
    for chave in ("ritmo.pausa_max_s", "movimento.zoom_frequencia", "movimento.zoom_intensidade",
                  "movimento.zoom_tipo", "cor.tom", "legenda.modo", "legenda.palavras_por_bloco",
                  "legenda.caixa_alta", "legenda.posicao", "legenda.cor", "legenda.cor_destaque",
                  "gancho.texto_na_tela", "texto_na_tela.titulos", "texto_na_tela.fundo"):
        o[chave] = "padrao"

    # Ritmo: as pausas de uma referência já editada mostram quanto silêncio o editor deixa.
    if m["pausa_p90_s"] is not None:
        f.ritmo.pausa_max_s = float(np.clip(m["pausa_p90_s"] * 1.2, 0.08, 0.6))
        f.ritmo.respiro_fim_s = float(np.clip(f.ritmo.pausa_max_s * 0.45, 0.04, 0.2))
        f.ritmo.respiro_inicio_s = float(np.clip(f.ritmo.pausa_max_s * 0.25, 0.03, 0.1))
        o["ritmo.pausa_max_s"] = "medido"

    # Zoom: quantas trocas de escala por segundo e de quanto.
    if m["cortes_com_escala_medida"]:
        if m["punch_ins"] == 0:
            f.movimento.zoom_frequencia = "nenhum"
        else:
            intervalo = m["duracao_s"] / m["punch_ins"]
            f.movimento.zoom_frequencia = ("alto" if intervalo <= 2.5 else "medio" if intervalo <= 4.5
                                           else "baixo" if intervalo <= 8 else "nenhum")
            f.movimento.zoom_intensidade = float(np.clip(m["escala_mediana_punch"], 1.04, 1.3))
            f.movimento.zoom_tipo = "corte"
            o["movimento.zoom_intensidade"] = o["movimento.zoom_tipo"] = "medido"
        o["movimento.zoom_frequencia"] = "medido"

    # Cor: canal b do Lab (positivo = amarelado/quente, negativo = azulado/frio).
    if m["cor_b_lab"] is not None:
        f.cor.tom = "quente" if m["cor_b_lab"] > 8 else "frio" if m["cor_b_lab"] < -4 else "neutro"
        o["cor.tom"] = "medido"
    f.validar()
    return f


# ---------------- julgamento por IA (opcional) ----------------
PROMPT_IA = """Você é editor de vídeos curtos (Reels/TikTok). Analise estes quadros de um vídeo de referência,
na ordem do tempo, e descreva o estilo de EDIÇÃO (não o conteúdo). Medições já feitas por código:
{medidas}

Responda SOMENTE com um JSON válido neste formato (use null quando não der para saber pelos quadros):
{{
  "legenda": {{"modo": "palavra|frase|nenhuma", "palavras_por_bloco": 1-6, "caixa_alta": true|false,
              "posicao": "centro|centro_baixo|baixo", "cor": "#RRGGBB", "cor_destaque": "#RRGGBB|null"}},
  "gancho_texto_na_tela": true|false,
  "titulos_na_tela": true|false,
  "texto_com_fundo_caixa": true|false,
  "observacoes": "1 a 2 frases sobre o que torna esse estilo reconhecível"
}}"""


def julgar_com_ia(caminho: str | Path, medidas: dict) -> dict | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    import cv2

    dur = medidas["duracao_s"]
    tempos = [0.4, 1.2, 2.2] + [dur * (i + 1) / 7 for i in range(1, 6)]
    imagens = midia.quadros(caminho, [min(t, dur - 0.1) for t in tempos], largura=540)
    conteudo: list[dict] = []
    for im in imagens:
        ok, buf = cv2.imencode(".jpg", im[:, :, ::-1].copy(), [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            conteudo.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                         "data": base64.b64encode(buf.tobytes()).decode()}})
    resumo = {k: v for k, v in medidas.items() if k != "transcricao"}
    conteudo.append({"type": "text", "text": PROMPT_IA.format(medidas=json.dumps(resumo, ensure_ascii=False))})
    cliente = anthropic.Anthropic()
    resp = cliente.messages.create(model=MODELO_IA, max_tokens=800, messages=[{"role": "user", "content": conteudo}])
    texto = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    achado = re.search(r"\{.*\}", texto, re.S)
    return json.loads(achado.group(0)) if achado else None


def _aplicar_ia(f: Ficha, ia: dict) -> None:
    leg = ia.get("legenda") or {}
    mapa = {"modo": ("palavra", "frase", "nenhuma"), "posicao": ("centro", "centro_baixo", "baixo")}
    for campo in ("modo", "palavras_por_bloco", "caixa_alta", "posicao", "cor", "cor_destaque"):
        v = leg.get(campo)
        if v is None or (campo in mapa and v not in mapa[campo]):
            continue
        if campo in ("cor", "cor_destaque") and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)):
            continue
        if campo == "palavras_por_bloco":
            v = int(np.clip(int(v), 1, 6))
        setattr(f.legenda, campo, v)
        f.origem[f"legenda.{campo}"] = "ia"
    for chave_ia, (secao, campo) in {"gancho_texto_na_tela": ("gancho", "texto_na_tela"),
                                     "titulos_na_tela": ("texto_na_tela", "titulos")}.items():
        if isinstance(ia.get(chave_ia), bool):
            setattr(getattr(f, secao), campo, ia[chave_ia])
            f.origem[f"{secao}.{campo}"] = "ia"
    if isinstance(ia.get("texto_com_fundo_caixa"), bool):
        f.texto_na_tela.fundo = "caixa" if ia["texto_com_fundo_caixa"] else "nenhum"
        f.origem["texto_na_tela.fundo"] = "ia"
    f.validar()


# ---------------- entrada principal ----------------
def extrair(caminho: str | Path, usar_ia: bool = True) -> tuple[Ficha, dict]:
    medidas = medir(caminho)
    ficha = _ficha_por_medidas(medidas)
    ia = None
    if usar_ia:
        try:
            ia = julgar_com_ia(caminho, medidas)
        except Exception as erro:  # a extração continua só com medições
            medidas["erro_ia"] = str(erro)[:300]
        if ia:
            _aplicar_ia(ficha, ia)
    return ficha, {"medidas": medidas, "ia": ia}


def extrair_varias(caminhos: list[str | Path], usar_ia: bool = True) -> tuple[Ficha, list[dict]]:
    fichas, evidencias = [], []
    for c in caminhos:
        f, e = extrair(c, usar_ia)
        fichas.append(f)
        evidencias.append(e)
    return consolidar(fichas), evidencias
