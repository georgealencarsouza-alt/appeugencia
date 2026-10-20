"""Orquestra as etapas: transcrever → checar → alinhar → montar → renderizar."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from . import midia
from .alinhamento import FraseAlinhada, Take, alinhar, trechos
from .checagem import Relatorio, checar_cobertura, checar_take
from .ficha import Ficha
from .montagem import Plano, montar
from .render import renderizar
from .roteiro import Roteiro
from .transcricao import Palavra, Transcritor, transcritor_padrao

PASTA_CACHE = Path.home() / ".cache" / "primeiro-corte" / "transcricoes"
# Mude quando a lógica de transcrição mudar, para invalidar o cache antigo.
VERSAO_TRANSCRICAO = 2


def _chave(caminho: Path) -> str:
    st = caminho.stat()
    return hashlib.sha1(f"v{VERSAO_TRANSCRICAO}|{caminho.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()


def transcrever_com_cache(caminho: Path, transcritor: Transcritor | None = None) -> list[Palavra]:
    PASTA_CACHE.mkdir(parents=True, exist_ok=True)
    arq = PASTA_CACHE / f"{_chave(caminho)}.json"
    if arq.exists():
        return [Palavra(**p) for p in json.loads(arq.read_text(encoding="utf-8"))]
    palavras = (transcritor or transcritor_padrao()).transcrever_arquivo(caminho)
    arq.write_text(json.dumps([p.para_dict() for p in palavras], ensure_ascii=False), encoding="utf-8")
    return palavras


@dataclass
class Analise:
    roteiro: Roteiro
    takes: list[Take]
    alinhadas: list[FraseAlinhada]
    relatorio: Relatorio


def analisar(roteiro: Roteiro, caminhos: list[str | Path], ficha: Ficha | None = None,
             transcritor: Transcritor | None = None, log=print) -> Analise:
    """Etapa que roda logo após o upload do cliente: transcreve, checa e diz se precisa regravar."""
    ficha = ficha or Ficha()
    caminhos = [Path(c) for c in caminhos]
    takes, checagens = [], []
    for i, c in enumerate(caminhos):
        t0 = time.time()
        palavras = transcrever_com_cache(c, transcritor)
        checagens.append(checar_take(c))
        takes.append(Take(caminho=c, palavras=palavras, ordem=i))
        log(f"  take {i + 1}/{len(caminhos)} {c.name}: {len(palavras)} palavras, {time.time() - t0:.1f}s")
    alinhadas = alinhar(roteiro, takes, ficha.ritmo)
    frases, problemas = checar_cobertura(alinhadas, [str(c) for c in caminhos])
    return Analise(roteiro, takes, alinhadas, Relatorio(takes=checagens, frases=frases, problemas=problemas))


def primeiro_corte(roteiro: Roteiro, caminhos: list[str | Path], ficha: Ficha, pasta_saida: str | Path,
                   *, rapido: bool = False, transcritor: Transcritor | None = None, log=print) -> dict:
    pasta = Path(pasta_saida)
    pasta.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log("1/3 Transcrevendo e checando os takes...")
    an = analisar(roteiro, caminhos, ficha, transcritor, log)
    (pasta / "checagem.json").write_text(json.dumps(an.relatorio.para_dict(), ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    log("2/3 Montando o plano de edição...")
    pedacos = trechos(an.alinhadas, an.takes, ficha.ritmo)
    ancoras = {i: chk.ancora() for i, chk in enumerate(an.relatorio.takes)}
    plano = montar(pedacos, roteiro, ficha, ancoras)
    plano.salvar(pasta / "plano.json")
    log(f"3/3 Renderizando {len(plano.segmentos)} trechos ({plano.duracao:.1f}s de vídeo)...")
    video = renderizar(plano, ficha, pasta / "primeiro_corte.mp4", rapido=rapido)
    duracao_bruta = sum(midia.info(c).duracao for c in caminhos)
    resumo = {
        "video": str(video),
        "status_checagem": an.relatorio.status,
        "mensagens": an.relatorio.mensagens(),
        "duracao_bruta_s": round(duracao_bruta, 1),
        "duracao_final_s": plano.duracao,
        "trechos": len(plano.segmentos),
        "frases_encontradas": sum(f.encontrada for f in an.relatorio.frases),
        "frases_total": len(an.relatorio.frases),
        "removidas": _removidas(an.alinhadas),
        "tempo_processamento_s": round(time.time() - t0, 1),
        "ficha": ficha.resumo(),
    }
    (pasta / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumo


def _removidas(alinhadas: list[FraseAlinhada]) -> dict[str, int]:
    cont: dict[str, int] = {}
    for fa in alinhadas:
        for p in fa.palavras:
            if p.removida:
                cont[p.removida] = cont.get(p.removida, 0) + 1
    return cont


def plano_de_arquivo(caminho: str | Path) -> Plano:
    """Recarrega um plano salvo (para renderizar de novo após ajuste manual)."""
    from .montagem import PalavraSaida, Segmento, Sobreposicao

    d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    segs = [Segmento(**{**s, "ancora": tuple(s["ancora"]),
                        "palavras": [PalavraSaida(**p) for p in s["palavras"]]}) for s in d["segmentos"]]
    sobre = [Sobreposicao(**s) for s in d["sobreposicoes"]]
    return Plano(segmentos=segs, sobreposicoes=sobre, duracao=d["duracao"], ficha=d["ficha"])
