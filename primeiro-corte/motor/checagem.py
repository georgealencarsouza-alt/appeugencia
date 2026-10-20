"""Checagem dos takes antes da edição.

Objetivo: o cliente descobrir que precisa regravar enquanto ainda está com o
celular na mão, e não a eugência descobrir isso na hora de editar.

Cada problema vem com uma mensagem pensada para o cliente final (leigo).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from . import midia
from .alinhamento import FraseAlinhada

PASTA_MODELOS = Path(__file__).resolve().parent.parent / "modelos"


@dataclass
class Problema:
    gravidade: str      # "regravar" ou "atencao"
    codigo: str
    mensagem: str       # para o cliente final


@dataclass
class ChecagemTake:
    caminho: str
    duracao: float
    resolucao: str
    vertical: bool
    voz_db: float | None = None
    ruido_db: float | None = None
    estouro_pct: float | None = None
    brilho: float | None = None
    rosto_visivel_pct: float | None = None
    rosto_centro: tuple[float, float] | None = None
    rosto_altura: float | None = None   # altura do rosto / altura do quadro
    problemas: list[Problema] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(p.gravidade == "regravar" for p in self.problemas):
            return "regravar"
        return "atencao" if self.problemas else "ok"

    def ancora(self) -> tuple[float, float]:
        """Ponto que a reenquadração deve preservar: o rosto, se encontrado."""
        if self.rosto_centro and (self.rosto_visivel_pct or 0) >= 50:
            return self.rosto_centro
        return (0.5, 0.4)


@dataclass
class ChecagemFrase:
    bloco_id: str
    texto: str
    encontrada: bool
    similaridade: float
    tentativas: int
    take: str | None
    faltando: list[str]


@dataclass
class Relatorio:
    takes: list[ChecagemTake]
    frases: list[ChecagemFrase]
    problemas: list[Problema]

    @property
    def status(self) -> str:
        todos = self.problemas + [p for t in self.takes for p in t.problemas]
        if any(p.gravidade == "regravar" for p in todos):
            return "regravar"
        return "atencao" if todos else "ok"

    def para_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status
        for t, td in zip(self.takes, d["takes"]):
            td["status"] = t.status
        return d

    def mensagens(self) -> list[str]:
        """Lista curta, sem jargão, do que o cliente precisa fazer."""
        msgs = [p.mensagem for p in self.problemas if p.gravidade == "regravar"]
        for t in self.takes:
            msgs += [f"{Path(t.caminho).name}: {p.mensagem}" for p in t.problemas if p.gravidade == "regravar"]
        msgs += [p.mensagem for p in self.problemas if p.gravidade == "atencao"]
        for t in self.takes:
            msgs += [f"{Path(t.caminho).name}: {p.mensagem}" for p in t.problemas if p.gravidade == "atencao"]
        return msgs


def _detector_rosto():
    import cv2

    arq = PASTA_MODELOS / "haarcascade_frontalface_default.xml"
    if not arq.exists():
        return None
    det = cv2.CascadeClassifier(str(arq))
    return None if det.empty() else det


def checar_take(caminho: str | Path, audio: np.ndarray | None = None) -> ChecagemTake:
    inf = midia.info(caminho)
    c = ChecagemTake(caminho=str(caminho), duracao=round(inf.duracao, 2),
                     resolucao=f"{inf.largura}x{inf.altura}", vertical=inf.vertical)
    P = c.problemas
    if not inf.tem_video:
        P.append(Problema("regravar", "sem_video", "O arquivo não tem imagem. Grave um vídeo, não só áudio."))
        return c
    if not inf.tem_audio:
        P.append(Problema("regravar", "sem_audio", "O vídeo veio sem som. Confira se o microfone está liberado."))
    if not inf.vertical:
        P.append(Problema("atencao", "horizontal",
                          "Vídeo gravado na horizontal. Da próxima vez, segure o celular em pé."))
    if min(inf.largura, inf.altura) < 720:
        P.append(Problema("atencao", "resolucao_baixa",
                          "Imagem em baixa resolução. Grave em 1080p ou mais e envie o arquivo original (o WhatsApp reduz a qualidade)."))

    # ---- áudio ----
    if inf.tem_audio:
        audio = midia.ler_audio(caminho) if audio is None else audio
        if len(audio):
            db = midia.energia_db(audio)
            c.voz_db = round(float(np.percentile(db, 90)), 1)
            c.ruido_db = round(float(np.percentile(db, 10)), 1)
            c.estouro_pct = round(float(np.mean(np.abs(audio) > 0.98) * 100), 3)
            if c.voz_db < -38:
                P.append(Problema("regravar", "audio_baixo",
                                  "Sua voz está muito baixa. Grave mais perto do celular ou use um microfone."))
            elif c.voz_db < -30:
                P.append(Problema("atencao", "audio_fraco", "Voz um pouco baixa. Chegue mais perto do celular."))
            if c.estouro_pct > 0.5:
                P.append(Problema("regravar", "audio_estourado",
                                  "O som estourou (ficou distorcido). Afaste um pouco o microfone ou fale mais baixo."))
            elif c.estouro_pct > 0.05:
                P.append(Problema("atencao", "audio_no_limite", "O som chegou no limite em alguns momentos."))
            if c.voz_db - c.ruido_db < 15:
                P.append(Problema("atencao", "ruido", "Tem barulho de fundo. Procure um lugar mais silencioso."))

    # ---- imagem ----
    n = 6
    tempos = [inf.duracao * (i + 0.5) / n for i in range(n)]
    imagens = midia.quadros(caminho, tempos, largura=480)
    if imagens:
        import cv2

        cinzas = [cv2.cvtColor(im[:, :, ::-1].copy(), cv2.COLOR_BGR2GRAY) for im in imagens]
        c.brilho = round(float(np.mean([g.mean() for g in cinzas])), 1)
        if c.brilho < 55:
            P.append(Problema("regravar", "escuro", "A imagem ficou escura. Grave de frente para uma janela ou luz."))
        elif c.brilho < 75:
            P.append(Problema("atencao", "pouca_luz", "Pouca luz. Se puder, chegue mais perto de uma janela."))
        elif c.brilho > 215:
            P.append(Problema("atencao", "estourado", "Imagem muito clara. Saia da luz direta."))

        det = _detector_rosto()
        if det is not None:
            achados = []
            for g in cinzas:
                h, w = g.shape
                rostos = det.detectMultiScale(g, scaleFactor=1.1, minNeighbors=5, minSize=(int(h * 0.06),) * 2)
                if len(rostos):
                    x, y, rw, rh = max(rostos, key=lambda r: r[2] * r[3])
                    achados.append(((x + rw / 2) / w, (y + rh / 2) / h, rh / h))
            c.rosto_visivel_pct = round(100 * len(achados) / len(cinzas), 0)
            if achados:
                cx = float(np.median([a[0] for a in achados]))
                cy = float(np.median([a[1] for a in achados]))
                alt = float(np.median([a[2] for a in achados]))
                c.rosto_centro, c.rosto_altura = (round(cx, 3), round(cy, 3)), round(alt, 3)
                if inf.vertical and abs(cx - 0.5) > 0.2:
                    P.append(Problema("atencao", "fora_do_centro", "Você ficou no canto do quadro. Centralize-se."))
                if alt < 0.08:
                    P.append(Problema("atencao", "longe", "Você está longe da câmera. Chegue mais perto."))
                elif alt > 0.45:
                    P.append(Problema("atencao", "perto", "Muito perto da câmera. Afaste um pouco."))
                if cy > 0.6:
                    P.append(Problema("atencao", "baixo_no_quadro", "Seu rosto ficou baixo. Deixe os olhos no terço de cima."))
            elif c.rosto_visivel_pct == 0:
                P.append(Problema("atencao", "sem_rosto",
                                  "Não encontramos seu rosto no vídeo. Grave olhando para a câmera."))
    return c


def checar_cobertura(alinhadas: list[FraseAlinhada], caminhos: list[str]) -> tuple[list[ChecagemFrase], list[Problema]]:
    frases, problemas = [], []
    for fa in alinhadas:
        sim = round(fa.ocorrencia.similaridade, 3) if fa.ocorrencia else 0.0
        frases.append(ChecagemFrase(
            bloco_id=fa.frase.bloco_id, texto=fa.frase.texto, encontrada=fa.encontrada, similaridade=sim,
            tentativas=fa.tentativas, take=caminhos[fa.ocorrencia.take] if fa.ocorrencia else None,
            faltando=fa.faltando))
        if not fa.encontrada:
            problemas.append(Problema("regravar", "frase_faltando", f'Faltou gravar a frase: "{fa.frase.texto}"'))
        elif sim < 0.8 and len(fa.faltando) >= 2:
            problemas.append(Problema("atencao", "frase_incompleta",
                                      f'A frase "{fa.frase.texto}" saiu diferente do roteiro '
                                      f'(faltou: {", ".join(fa.faltando[:5])}).'))
    return frases, problemas
