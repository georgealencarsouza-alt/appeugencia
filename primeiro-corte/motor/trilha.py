"""Trilha de fundo original gerada por código (livre de direitos).

Não substitui uma biblioteca de músicas, mas garante que todo primeiro corte
possa sair com fundo musical sem risco de direitos autorais. Estilos:
  - "calmo":    piano suave + pad, progressão I–V–vi–IV, ~76 BPM
  - "animado":  mesma harmonia, arpejo mais rápido e pulso de bumbo, ~104 BPM
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

TAXA = 44100
# progressão I–V–vi–IV em Dó maior (notas MIDI)
ACORDES = [[48, 55, 60, 64, 67], [43, 50, 55, 59, 62], [45, 52, 57, 60, 64], [41, 48, 53, 57, 60]]


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _piano(freq: float, dur: float, vel: float = 0.5) -> np.ndarray:
    t = np.arange(int(dur * TAXA)) / TAXA
    env = np.exp(-t * 2.8) * (1 - np.exp(-t * 300))
    som = sum(a * np.sin(2 * np.pi * freq * h * t) for h, a in ((1, 1.0), (2, 0.45), (3, 0.2), (4, 0.08)))
    return (som * env * vel).astype(np.float32)


def _pad(freqs: list[float], dur: float) -> np.ndarray:
    t = np.arange(int(dur * TAXA)) / TAXA
    ataque = np.minimum(1, t / 0.8) * np.minimum(1, (dur - t) / 0.8)
    som = sum(np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.003 * t) for f in freqs)
    return (som * ataque * 0.04).astype(np.float32)


def _bumbo(dur: float = 0.25) -> np.ndarray:
    t = np.arange(int(dur * TAXA)) / TAXA
    freq = 110 * np.exp(-t * 30) + 45
    return (np.sin(2 * np.pi * np.cumsum(freq) / TAXA) * np.exp(-t * 18) * 0.5).astype(np.float32)


def _eco(x: np.ndarray, atraso: float = 0.32, ganho: float = 0.35, repeticoes: int = 4) -> np.ndarray:
    saida = x.copy()
    d = int(atraso * TAXA)
    for k in range(1, repeticoes + 1):
        saida[d * k:] += x[: len(x) - d * k] * ganho ** k
    return saida


def gerar(destino: str | Path, duracao: float, estilo: str = "calmo", semente: int = 3) -> Path:
    bpm = {"calmo": 76, "animado": 104}[estilo]
    batida = 60 / bpm
    compasso = batida * 4
    rng = np.random.default_rng(semente)
    total = int((duracao + 2) * TAXA)
    mix = np.zeros(total, dtype=np.float32)
    t = 0.0
    i = 0
    while t < duracao + 1:
        acorde = ACORDES[i % len(ACORDES)]
        ini = int(t * TAXA)
        pad = _pad([_hz(n) for n in acorde[:3]], compasso + 0.6)
        mix[ini: ini + len(pad)] += pad[: total - ini]
        # baixo na cabeça do compasso
        b = _piano(_hz(acorde[0] - 12), compasso, 0.35)
        mix[ini: ini + len(b)] += b[: total - ini]
        # arpejo
        passos = 4 if estilo == "calmo" else 8
        for p in range(passos):
            nota = acorde[1 + (p % 4)] + (12 if estilo == "animado" and p >= 4 else 0)
            pos = int((t + p * compasso / passos) * TAXA)
            if pos >= total:
                break
            n = _piano(_hz(nota), 1.6, 0.18 + 0.05 * rng.random())
            mix[pos: pos + len(n)] += n[: total - pos]
        if estilo == "animado":
            for p in range(4):
                pos = int((t + p * batida) * TAXA)
                k = _bumbo()
                mix[pos: pos + len(k)] += k[: max(0, total - pos)]
        t += compasso
        i += 1
    mix = _eco(mix)[: int(duracao * TAXA)]
    fade = int(1.5 * TAXA)
    mix[:int(0.5 * TAXA)] *= np.linspace(0, 1, int(0.5 * TAXA))
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1e-6, np.abs(mix).max()) / 0.8
    destino = Path(destino)
    sf.write(destino, np.stack([mix, mix], axis=1), TAXA)
    return destino
