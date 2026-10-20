"""Gera takes e uma referência SINTÉTICOS para testar o motor sem gravar nada.

A voz é sintetizada (Piper pt-BR) e a imagem é um cenário desenhado, com o
tempo do arquivo original impresso na tela: no vídeo final dá para ver de qual
segundo do take cada trecho veio.

Os takes imitam um cliente real gravando: começo em silêncio, falso começo,
"ahn", palavra repetida, pausa no meio da frase, frase refeita e um take
gravado na horizontal.

    python exemplos/gerar.py            # cria exemplos/saida/
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from motor.transcricao import PASTA_MODELOS  # noqa: E402

SAIDA = Path(__file__).resolve().parent / "saida"
VOZ = PASTA_MODELOS / "vits-piper-pt_BR-faber-medium"
TAXA = 22050
FONTE = RAIZ / "fontes" / "Poppins-Bold.ttf"

ROTEIRO = {
    "titulo": "Preço x valor",
    "palavras_chave": ["preço", "valor"],
    "blocos": [
        {"id": "gancho", "tipo": "gancho", "texto": "Seu cliente só pergunta o preço?",
         "texto_tela": "Só perguntam o preço?"},
        {"id": "corpo", "tipo": "desenvolvimento",
         "texto": "Então o problema não é o preço. É que ninguém entendeu o valor do seu serviço. "
                  "Antes de mandar o orçamento, mostre o que está incluído e como funciona o atendimento.",
         "texto_tela": "O problema não é o preço"},
        {"id": "cta", "tipo": "cta", "texto": "Comente valor que eu te mando o roteiro completo.",
         "texto_tela": "Comente VALOR"},
    ],
}

# (texto, pausa_depois_s). Texto vazio = silêncio.
TAKE1 = [
    ("", 1.4),
    ("Seu cliente só pergunta o", 0.25),
    ("ahn, desculpa.", 0.9),
    ("Seu cliente só pergunta o preço?", 1.1),
    ("Então o problema não é", 0.15), ("é", 0.15), ("o preço.", 0.8),
    ("É que ninguém entendeu o o valor do seu serviço.", 1.2),
    ("Antes de mandar o orçamento,", 0.9),
    ("mostre o que está incluído e como funciona o", 0.3),
    ("Antes de mandar o orçamento, mostre o que está incluído e como funciona o atendimento.", 1.5),
]
TAKE2 = [
    ("", 1.0),
    ("Comente valor que eu te mando o roteiro.", 1.2),
    ("Comente valor que eu te mando o roteiro completo.", 1.3),
]
REFERENCIA = [
    ("Você não precisa de uma ideia nova todo dia.", 0.08),
    ("Pegue uma pergunta do seu público.", 0.06),
    ("Grave uma resposta, mostre um exemplo.", 0.07),
    ("E use a próxima dúvida para outro vídeo.", 0.06),
    ("Salve para planejar seus próximos três vídeos.", 0.3),
]


def _tts():
    import sherpa_onnx

    cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=str(VOZ / "pt_BR-faber-medium.onnx"),
                                                   tokens=str(VOZ / "tokens.txt"),
                                                   data_dir=str(VOZ / "espeak-ng-data")), num_threads=2))
    return sherpa_onnx.OfflineTts(cfg)


def _aparar(x: np.ndarray) -> np.ndarray:
    """Remove o silêncio que o sintetizador coloca no começo e no fim."""
    voz = np.where(np.abs(x) > 0.01)[0]
    return x[max(0, voz[0] - 200): voz[-1] + 400] if len(voz) else x


def _falas(tts, roteiro: list[tuple[str, float]], velocidade: float = 1.0) -> np.ndarray:
    rng = np.random.default_rng(7)
    partes = []
    for texto, pausa in roteiro:
        if texto:
            a = tts.generate(texto, sid=0, speed=velocidade)
            partes.append(_aparar(np.asarray(a.samples, dtype=np.float32)) * 0.6)
        partes.append(np.zeros(int(TAXA * pausa), dtype=np.float32))
    audio = np.concatenate(partes)
    return audio + rng.normal(0, 0.0012, len(audio)).astype(np.float32)  # chiado leve, como num quarto real


def _cenario(destino: Path, largura: int, altura: int, cor_fundo: tuple[int, int, int], rotulo: str) -> None:
    """Desenha um 'apresentador' simples: fundo, silhueta de cabeça e ombros, grade de referência."""
    img = np.zeros((altura, largura, 3), dtype=np.uint8)
    yy, xx = np.mgrid[0:altura, 0:largura]
    grad = (yy / altura)[..., None]
    img[:] = (np.array(cor_fundo) * (1 - 0.4 * grad)).astype(np.uint8)
    cx, cy = largura // 2, int(altura * 0.38)
    r = int(min(largura, altura) * 0.16)
    cabeca = (xx - cx) ** 2 + ((yy - cy) / 1.2) ** 2 < r ** 2
    ombros = ((xx - cx) / (r * 2.6)) ** 2 + ((yy - (cy + r * 3.2)) / (r * 1.9)) ** 2 < 1
    img[ombros] = (40, 60, 90)
    img[cabeca] = (225, 185, 150)
    olhos = (((xx - (cx - r * 0.35)) ** 2 + (yy - (cy - r * 0.15)) ** 2) < (r * 0.09) ** 2) | \
            (((xx - (cx + r * 0.35)) ** 2 + (yy - (cy - r * 0.15)) ** 2) < (r * 0.09) ** 2)
    img[olhos] = (30, 30, 30)
    for g in range(0, largura, max(1, largura // 9)):
        img[:, g:g + 2] = img[:, g:g + 2] // 2 + 60
    import cv2

    cv2.putText(img, rotulo, (int(largura * 0.06), int(altura * 0.08)), cv2.FONT_HERSHEY_SIMPLEX,
                largura / 900, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.imwrite(str(destino), img[:, :, ::-1])


def _video(audio: np.ndarray, imagem: Path, destino: Path, filtro_extra: str = "") -> None:
    wav = destino.with_suffix(".wav")
    sf.write(wav, audio, TAXA)
    fonte = str(FONTE).replace(":", "\\:")
    texto = f"drawtext=fontfile='{fonte}':text='origem %{{pts\\:hms}}':x=(w-tw)/2:y=h*0.9:fontsize=h/28:" \
            f"fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=12"
    vf = ",".join(f for f in [filtro_extra, texto] if f)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-i", str(imagem),
                    "-i", str(wav), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", str(destino)], check=True)
    wav.unlink()


def _referencia(tts, destino: Path) -> None:
    """Referência 'editada': fala rápida, cortes com punch-in a cada ~1,3 s e cor quente."""
    audio = _falas(tts, REFERENCIA, velocidade=1.12)
    img = destino.with_name("ref.png")
    _cenario(img, 1080, 1920, (60, 70, 85), "REFERENCIA")
    dur = len(audio) / TAXA
    # zoom alterna 1.0 / 1.18 em blocos de 1.3 s (simula jump cuts com punch-in)
    zoom = "if(lt(mod(t,2.6),1.3),1,1.18)"
    filtro = (f"scale=w='trunc(1080*{zoom}/2)*2':h='trunc(1920*{zoom}/2)*2':eval=frame,"
              f"crop=1080:1920,colorbalance=rs=0.12:gs=0.03:bs=-0.12:rm=0.08:bm=-0.08")
    sf.write(destino.with_suffix(".wav"), audio, TAXA)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", f"{dur:.2f}",
                    "-i", str(img), "-i", str(destino.with_suffix(".wav")), "-vf", filtro, "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(destino)], check=True)
    destino.with_suffix(".wav").unlink()
    img.unlink()


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    tts = _tts()
    (SAIDA / "roteiro.json").write_text(json.dumps(ROTEIRO, ensure_ascii=False, indent=2), encoding="utf-8")

    img1 = SAIDA / "cenario_vertical.png"
    _cenario(img1, 1080, 1920, (70, 90, 110), "TAKE 1")
    _video(_falas(tts, TAKE1), img1, SAIDA / "take1_vertical.mp4")

    img2 = SAIDA / "cenario_horizontal.png"
    _cenario(img2, 1920, 1080, (90, 80, 110), "TAKE 2 (horizontal)")
    _video(_falas(tts, TAKE2), img2, SAIDA / "take2_horizontal.mp4")
    img1.unlink()
    img2.unlink()

    _referencia(tts, SAIDA / "referencia.mp4")
    print(f"Exemplos gerados em {SAIDA}")
    for p in sorted(SAIDA.iterdir()):
        print(" ", p.name)


if __name__ == "__main__":
    main()
