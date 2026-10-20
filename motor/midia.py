"""Leitura de arquivos de vídeo com ffprobe/ffmpeg."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

TAXA_AUDIO = 16000


def _exigir(binario: str) -> str:
    caminho = shutil.which(binario)
    if not caminho:
        raise RuntimeError(f"'{binario}' não encontrado. Instale o FFmpeg (https://ffmpeg.org).")
    return caminho


def rodar(cmd: list[str], *, capturar: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=capturar, text=True)
    if proc.returncode != 0:
        cauda = (proc.stderr or "")[-2000:]
        raise RuntimeError(f"Falha ao rodar {cmd[0]}:\n{cauda}")
    return proc


@dataclass
class InfoVideo:
    caminho: Path
    duracao: float
    largura: int          # já considerando rotação (o que a pessoa vê)
    altura: int
    fps: float
    tem_audio: bool
    tem_video: bool

    @property
    def vertical(self) -> bool:
        return self.altura > self.largura


def info(caminho: str | Path) -> InfoVideo:
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(caminho)
    saida = rodar([_exigir("ffprobe"), "-v", "error", "-print_format", "json", "-show_streams",
                   "-show_format", str(caminho)]).stdout
    dados = json.loads(saida)
    video = next((s for s in dados.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in dados.get("streams", []) if s.get("codec_type") == "audio"), None)
    largura = altura = 0
    fps = 0.0
    if video:
        largura, altura = int(video.get("width", 0)), int(video.get("height", 0))
        rotacao = 0
        for lado in video.get("side_data_list", []) or []:
            if "rotation" in lado:
                rotacao = int(lado["rotation"])
        rotacao = int(video.get("tags", {}).get("rotate", rotacao))
        if abs(rotacao) % 180 == 90:
            largura, altura = altura, largura
        num, _, den = (video.get("avg_frame_rate") or "0/1").partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    duracao = float(dados.get("format", {}).get("duration") or 0)
    return InfoVideo(caminho=caminho, duracao=duracao, largura=largura, altura=altura, fps=fps,
                     tem_audio=audio is not None, tem_video=video is not None)


def ler_audio(caminho: str | Path, taxa: int = TAXA_AUDIO) -> np.ndarray:
    """Áudio mono float32 em `taxa` Hz."""
    proc = subprocess.run([_exigir("ffmpeg"), "-v", "error", "-i", str(caminho), "-vn", "-ac", "1",
                           "-ar", str(taxa), "-f", "f32le", "-"], capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Não consegui ler o áudio de {caminho}:\n{proc.stderr.decode()[-1000:]}")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def energia_db(audio: np.ndarray, taxa: int = TAXA_AUDIO, janela_s: float = 0.02) -> np.ndarray:
    """RMS em dBFS por janela de 20 ms."""
    n = max(1, int(taxa * janela_s))
    cortado = audio[: len(audio) // n * n].reshape(-1, n)
    rms = np.sqrt(np.mean(cortado ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms + 1e-12)


def quadros(caminho: str | Path, tempos: list[float], largura: int = 360) -> list[np.ndarray]:
    """Extrai quadros RGB (altura proporcional) nos tempos pedidos."""
    _exigir("ffmpeg")
    imagens = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(tempos):
            destino = Path(tmp) / f"q{i}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(caminho),
                            "-frames:v", "1", "-vf", f"scale={largura}:-2", str(destino)], capture_output=True)
            if destino.exists():
                import cv2
                bgr = cv2.imread(str(destino))
                if bgr is not None:
                    imagens.append(bgr[:, :, ::-1].copy())
    return imagens
