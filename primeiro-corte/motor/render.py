"""Renderiza o plano com FFmpeg: reenquadra 9:16, aplica zooms, cor, legendas e áudio."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import midia
from .ficha import Ficha
from .legendas import gerar_ass
from .montagem import Plano, Segmento

PASTA_FONTES = Path(__file__).resolve().parent.parent / "fontes"
FADE_AUDIO_S = 0.012   # evita estalo no corte


def _par(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def _filtro_video(seg: Segmento, src: midia.InfoVideo, ficha: Ficha, idx: int) -> str:
    W, H, fps = ficha.formato.largura, ficha.formato.altura, ficha.formato.fps
    ax, ay = seg.ancora
    # escala que cobre o quadro 9:16 (corta o excesso), já com o zoom estático
    cobre = max(W / src.largura, H / src.altura)
    partes = [f"[{idx}:v]fps={fps}"]
    if seg.zoom_inicio == seg.zoom_fim:
        s = cobre * seg.zoom_inicio
        sw, sh = _par(src.largura * s), _par(src.altura * s)
        x = min(max(ax * sw - W / 2, 0), sw - W)
        y = min(max(ay * sh - H * 0.4, 0), sh - H)
        partes.append(f"scale={sw}:{sh}:flags=lanczos,crop={W}:{H}:{int(x)}:{int(y)}")
    else:
        # aproximação suave: enquadra 9:16 e anima o zoom quadro a quadro
        sw, sh = _par(src.largura * cobre), _par(src.altura * cobre)
        x = min(max(ax * sw - W / 2, 0), sw - W)
        y = min(max(ay * sh - H * 0.4, 0), sh - H)
        # ponto de ancoragem dentro do quadro já recortado
        axc = min(max((ax * sw - x) / W, 0.0), 1.0)
        ayc = min(max((ay * sh - y) / H, 0.0), 1.0)
        n = max(1, int(round(seg.duracao * fps)) - 1)
        z0, z1 = seg.zoom_inicio, seg.zoom_fim
        zexpr = f"{z0}+({z1 - z0})*min(on/{n},1)"
        partes.append(
            f"scale={sw}:{sh}:flags=lanczos,crop={W}:{H}:{int(x)}:{int(y)},"
            f"scale={W * 2}:{H * 2},"  # supersampling reduz o tremido do zoompan
            f"zoompan=z='{zexpr}':x='max(0,min(iw-iw/zoom,{axc}*iw-iw/zoom/2))'"
            f":y='max(0,min(ih-ih/zoom,{ayc}*ih-ih/zoom*0.4))':d=1:s={W}x{H}:fps={fps}")
    partes.append("setsar=1,format=yuv420p")
    return ",".join(partes) + f"[v{idx}]"


def _filtro_cor(ficha: Ficha) -> str:
    c = ficha.cor
    filtros = []
    if c.contraste != 1.0 or c.saturacao != 1.0:
        filtros.append(f"eq=contrast={c.contraste}:saturation={c.saturacao}")
    if c.tom == "quente":
        filtros.append("colorbalance=rs=0.05:gs=0.01:bs=-0.06:rm=0.04:bm=-0.05")
    elif c.tom == "frio":
        filtros.append("colorbalance=rs=-0.05:bs=0.06:rm=-0.04:bm=0.05")
    return ",".join(filtros)


def renderizar(plano: Plano, ficha: Ficha, destino: str | Path, *, rapido: bool = False,
               mostrar_progresso: bool = False) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg não encontrado.")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    infos: dict[str, midia.InfoVideo] = {}
    for seg in plano.segmentos:
        if seg.caminho not in infos:
            infos[seg.caminho] = midia.info(seg.caminho)

    with tempfile.TemporaryDirectory() as tmp:
        ass = gerar_ass(plano, ficha, Path(tmp) / "legendas.ass")
        cmd = [ffmpeg, "-y", "-v", "error", "-stats" if mostrar_progresso else "-nostats"]
        for seg in plano.segmentos:
            cmd += ["-ss", f"{seg.origem_inicio:.3f}", "-t", f"{seg.duracao:.3f}", "-i", seg.caminho]
        musica_idx = None
        if ficha.audio.musica:
            musica_idx = len(plano.segmentos)
            cmd += ["-stream_loop", "-1", "-i", ficha.audio.musica]

        cadeias = []
        for i, seg in enumerate(plano.segmentos):
            cadeias.append(_filtro_video(seg, infos[seg.caminho], ficha, i))
            d = seg.duracao
            proximo_continua = i + 1 < len(plano.segmentos) and plano.segmentos[i + 1].continua
            fades = []
            if not seg.continua:   # emenda de áudio contínuo não leva fade (evitaria um "buraco" na voz)
                fades.append(f"afade=t=in:d={FADE_AUDIO_S}")
            if not proximo_continua:
                fades.append(f"afade=t=out:st={max(0.0, d - FADE_AUDIO_S):.3f}:d={FADE_AUDIO_S}")
            cadeias.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,"
                           + "".join(f"{f}," for f in fades)
                           + f"apad=whole_dur={d:.3f},atrim=0:{d:.3f}[a{i}]")
        n = len(plano.segmentos)
        cadeias.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")

        total = plano.duracao
        fade = ficha.fechamento.fade_final_s
        pos_video = [f for f in [_filtro_cor(ficha)] if f]
        fontsdir = str(PASTA_FONTES).replace(":", "\\:")
        caminho_ass = str(ass).replace("\\", "/").replace(":", "\\:")
        pos_video.append(f"ass='{caminho_ass}':fontsdir='{fontsdir}'")
        if fade > 0:
            pos_video.append(f"fade=t=out:st={max(0.0, total - fade):.3f}:d={fade}")
        cadeias.append("[vc]" + ",".join(pos_video) + "[vout]")

        pos_audio = []
        if ficha.audio.normalizar:
            pos_audio.append(f"loudnorm=I={ficha.audio.alvo_lufs}:TP=-1.5:LRA=11")
        pos_audio.append("aresample=48000")
        if fade > 0:
            pos_audio.append(f"afade=t=out:st={max(0.0, total - fade):.3f}:d={fade}")
        if musica_idx is not None:
            cadeias.append("[ac]" + ",".join(pos_audio) + ",asplit[voz][vozsc]")
            cadeias.append(f"[{musica_idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                           f"volume={ficha.audio.musica_volume},atrim=0:{total:.3f},"
                           f"afade=t=out:st={max(0.0, total - 1.0):.3f}:d=1[mus]")
            cadeias.append("[mus][vozsc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[musd]")
            cadeias.append("[voz][musd]amix=inputs=2:duration=first:normalize=0[aout]")
        else:
            cadeias.append("[ac]" + ",".join(pos_audio) + "[aout]")

        cmd += ["-filter_complex", ";".join(cadeias), "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "ultrafast" if rapido else "medium",
                "-crf", "28" if rapido else "20", "-pix_fmt", "yuv420p", "-r", str(ficha.formato.fps),
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(destino)]
        proc = subprocess.run(cmd, capture_output=not mostrar_progresso, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Falha na renderização:\n{(proc.stderr or '')[-3000:]}")
    return destino
