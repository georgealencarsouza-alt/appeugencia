from pathlib import Path

import pytest

from motor.alinhamento import PalavraAlinhada, Trecho
from motor.ficha import Ficha, consolidar, preset
from motor.legendas import gerar_ass
from motor.montagem import montar
from motor.roteiro import Roteiro

ROTEIRO = Roteiro.de_dict({
    "titulo": "t", "palavras_chave": ["preço"],
    "blocos": [{"id": "g", "tipo": "gancho", "texto": "Qual o preço?", "texto_tela": "PREÇO?"},
               {"id": "c", "tipo": "cta", "texto": "Comente agora.", "texto_tela": "Comente"}],
})


def _trecho(frase, bloco, tipo, palavras, ini):
    pas = [PalavraAlinhada(0, i, ini + i * 0.4, ini + i * 0.4 + 0.3, w, w, True) for i, w in enumerate(palavras)]
    return Trecho(0, Path("a.mp4"), ini - 0.05, ini + len(palavras) * 0.4, frase, bloco, tipo, pas)


def test_ficha_ida_e_volta_e_validacao(tmp_path):
    f = preset("dinamico").com(**{"legenda.caixa_alta": False})
    f.salvar(tmp_path / "f.json")
    g = Ficha.carregar(tmp_path / "f.json")
    assert g.legenda.caixa_alta is False and g.origem["legenda.caixa_alta"] == "manual"
    with pytest.raises(ValueError):
        f.com(**{"movimento.zoom_frequencia": "turbo"})


def test_consolidar_usa_mediana_e_ignora_padrao():
    a, b, c = preset("equilibrado"), preset("equilibrado"), preset("equilibrado")
    for f, p in zip((a, b, c), (0.1, 0.2, 0.9)):
        f.ritmo.pausa_max_s = p
        f.origem["ritmo.pausa_max_s"] = "medido"
    c.cor.tom = "frio"
    a.cor.tom = b.cor.tom = "quente"
    for f in (a, b, c):
        f.origem["cor.tom"] = "medido"
    r = consolidar([a, b, c])
    assert r.ritmo.pausa_max_s == 0.2 and r.cor.tom == "quente"


def test_montagem_encadeia_tempos_e_cria_sobreposicoes(tmp_path):
    trs = [_trecho(0, "g", "gancho", ["Qual", "o", "preço?"], 1.0),
           _trecho(1, "c", "cta", ["Comente", "agora."], 5.0)]
    plano = montar(trs, ROTEIRO, preset("equilibrado"))
    assert plano.segmentos[1].saida_inicio == pytest.approx(plano.segmentos[0].saida_fim)
    assert any(p.chave for p in plano.palavras())          # "preço" é palavra-chave
    assert {s.tipo for s in plano.sobreposicoes} == {"gancho", "cta"}
    ass = gerar_ass(plano, preset("equilibrado"), tmp_path / "x.ass").read_text(encoding="utf-8")
    assert "PREÇO" in ass and "Dialogue:" in ass


def test_trecho_longo_ganha_punch_in_sem_cortar_fala():
    palavras = "Você sabia que você precisa de pelo menos cinquenta reais para poder me fazer um Pix?".split()
    trs = [_trecho(0, "g", "gancho", palavras, 1.0)]
    plano = montar(trs, ROTEIRO, preset("equilibrado"))   # 16 palavras * 0.4 s = 6.4 s
    assert len(plano.segmentos) >= 2
    assert all(s.continua for s in plano.segmentos[1:])
    for a, b in zip(plano.segmentos, plano.segmentos[1:]):
        assert a.origem_fim == b.origem_inicio                  # áudio contínuo, nada repetido nem perdido
    zooms = [s.zoom_fim for s in plano.segmentos]
    assert max(zooms) - min(zooms) >= 0.06                      # a troca de enquadramento é visível
