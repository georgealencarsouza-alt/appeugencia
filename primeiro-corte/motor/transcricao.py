"""Transcrição com tempo por palavra.

Provedor padrão: modelo local Parakeet TDT v3 (multilíngue, inclui português)
rodando via sherpa-onnx, sem custo por minuto e sem mandar o vídeo do cliente
para terceiros. A interface `Transcritor` permite trocar por uma API depois.
"""
from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import midia
from .roteiro import normalizar

PASTA_MODELOS = Path(os.environ.get("MOTOR_MODELOS", Path(__file__).resolve().parent.parent / "modelos"))
MODELO_PADRAO = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
# Trechos longos são transcritos em pedaços para não estourar memória.
JANELA_S = 30.0
SOBREPOSICAO_S = 1.0


@dataclass
class Palavra:
    texto: str            # como o modelo transcreveu
    inicio: float         # segundos, no arquivo de origem
    fim: float
    confianca: float      # 0..1

    @property
    def norm(self) -> str:
        return normalizar(self.texto)

    def para_dict(self) -> dict:
        return asdict(self)


class Transcritor:
    def transcrever(self, audio: np.ndarray, taxa: int = midia.TAXA_AUDIO) -> list[Palavra]:
        raise NotImplementedError

    def transcrever_arquivo(self, caminho: str | Path) -> list[Palavra]:
        return self.transcrever(midia.ler_audio(caminho))


class TranscritorLocal(Transcritor):
    def __init__(self, modelo: str = MODELO_PADRAO, threads: int | None = None):
        import sherpa_onnx

        pasta = PASTA_MODELOS / modelo
        if not (pasta / "encoder.int8.onnx").exists():
            raise FileNotFoundError(
                f"Modelo de transcrição não encontrado em {pasta}.\nRode: python scripts/baixar_modelos.py")
        self._rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(pasta / "encoder.int8.onnx"), decoder=str(pasta / "decoder.int8.onnx"),
            joiner=str(pasta / "joiner.int8.onnx"), tokens=str(pasta / "tokens.txt"),
            model_type="nemo_transducer", num_threads=threads or max(1, (os.cpu_count() or 2)))

    def _pedaco(self, audio: np.ndarray, taxa: int, deslocamento: float) -> list[Palavra]:
        fluxo = self._rec.create_stream()
        fluxo.accept_waveform(taxa, audio)
        self._rec.decode_stream(fluxo)
        r = fluxo.result
        duracoes = list(getattr(r, "durations", []) or [])
        logprobs = list(getattr(r, "ys_log_probs", []) or [])
        palavras: list[Palavra] = []
        atual: dict | None = None
        for i, (tok, t) in enumerate(zip(r.tokens, r.timestamps)):
            dur = duracoes[i] if i < len(duracoes) else 0.08
            prob = math.exp(logprobs[i]) if i < len(logprobs) else 1.0
            limpo = tok.replace("▁", " ")
            # o modelo cola números na palavra anterior ("menos50"): troca letra<->dígito também separa
            troca_tipo = (atual is not None and limpo[:1].isalnum() and atual["texto"][-1:].isalnum()
                          and limpo[:1].isdigit() != atual["texto"][-1:].isdigit())
            inicia_palavra = tok.startswith(" ") or tok.startswith("▁") or atual is None or troca_tipo
            if not normalizar(limpo):  # pontuação: cola na palavra anterior
                if atual is not None:
                    atual["texto"] += limpo.strip()
                continue
            if inicia_palavra:
                if atual is not None:
                    palavras.append(_fechar(atual))
                atual = {"texto": limpo.strip(), "inicio": t, "fim": t + dur, "probs": [prob]}
            else:
                atual["texto"] += limpo
                atual["fim"] = t + dur
                atual["probs"].append(prob)
        if atual is not None:
            palavras.append(_fechar(atual))
        for p in palavras:
            p.inicio += deslocamento
            p.fim += deslocamento
        return palavras

    def transcrever(self, audio: np.ndarray, taxa: int = midia.TAXA_AUDIO) -> list[Palavra]:
        total = len(audio) / taxa
        if total <= JANELA_S + SOBREPOSICAO_S:
            return _refinar_fins(self._pedaco(audio, taxa, 0.0), audio, taxa)
        palavras: list[Palavra] = []
        inicio = 0.0
        while inicio < total:
            fim = min(total, inicio + JANELA_S + SOBREPOSICAO_S)
            pedaco = self._pedaco(audio[int(inicio * taxa): int(fim * taxa)], taxa, inicio)
            corte = inicio + JANELA_S if fim < total else math.inf
            ultimo_fim = palavras[-1].fim if palavras else -1.0
            # fica com cada palavra uma única vez: as que começam antes do corte e depois da última aceita
            palavras.extend(p for p in pedaco if p.inicio < corte and p.inicio >= ultimo_fim - 0.02)
            inicio += JANELA_S
        return _refinar_fins(palavras, audio, taxa)


def _fechar(atual: dict) -> Palavra:
    return Palavra(texto=atual["texto"], inicio=float(atual["inicio"]), fim=float(atual["fim"]),
                   confianca=float(np.mean(atual["probs"])))


def _refinar_fins(palavras: list[Palavra], audio: np.ndarray, taxa: int) -> list[Palavra]:
    """O modelo marca bem o começo das palavras, mas o fim é aproximado.

    Estende o fim de cada palavra enquanto ainda houver voz (energia acima do
    piso de ruído), sem invadir a próxima palavra. Isso evita cortar o final
    das sílabas quando removemos silêncio.
    """
    if not palavras:
        return palavras
    janela = 0.02
    db = midia.energia_db(audio, taxa, janela)
    piso = float(np.percentile(db, 10))
    voz = float(np.percentile(db, 90))
    limiar = piso + max(6.0, (voz - piso) * 0.25)
    for i, p in enumerate(palavras):
        limite = palavras[i + 1].inicio if i + 1 < len(palavras) else len(audio) / taxa
        idx = int(p.fim / janela)
        maximo = min(int(limite / janela), idx + int(0.35 / janela), len(db) - 1)
        while idx < maximo and db[idx] > limiar:
            idx += 1
        p.fim = max(p.fim, min(limite, idx * janela))
    return palavras


@lru_cache(maxsize=1)
def transcritor_padrao() -> Transcritor:
    return TranscritorLocal()


def texto(palavras: list[Palavra]) -> str:
    return " ".join(p.texto for p in palavras)
