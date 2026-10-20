"""Baixa os modelos usados pelo motor para a pasta modelos/ (cerca de 560 MB).

    python scripts/baixar_modelos.py            # transcrição + detector de rosto
    python scripts/baixar_modelos.py --voz      # + voz pt-BR (só para gerar exemplos sintéticos)
"""
from __future__ import annotations

import argparse
import tarfile
import urllib.request
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "modelos"
BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
MODELOS = {
    "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8": f"{BASE}/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2",
}
VOZ = {"vits-piper-pt_BR-faber-medium": f"{BASE}/tts-models/vits-piper-pt_BR-faber-medium.tar.bz2"}
ROSTO = ("haarcascade_frontalface_default.xml",
         "https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_frontalface_default.xml")


def _baixar(url: str, destino: Path) -> None:
    print(f"Baixando {url}")
    urllib.request.urlretrieve(url, destino)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voz", action="store_true")
    a = ap.parse_args()
    PASTA.mkdir(exist_ok=True)
    alvos = dict(MODELOS, **(VOZ if a.voz else {}))
    for nome, url in alvos.items():
        if (PASTA / nome).exists():
            print(f"Já existe: {nome}")
            continue
        arq = PASTA / f"{nome}.tar.bz2"
        _baixar(url, arq)
        with tarfile.open(arq) as t:
            t.extractall(PASTA, filter="data")
        arq.unlink()
    nome, url = ROSTO
    if not (PASTA / nome).exists():
        _baixar(url, PASTA / nome)
    print("Modelos prontos em", PASTA)


if __name__ == "__main__":
    main()
