"""Testes do alinhamento com transcrições sintéticas (não precisam de modelo nem de vídeo)."""
from pathlib import Path

from motor.alinhamento import Take, alinhar, trechos
from motor.ficha import Ritmo
from motor.roteiro import Roteiro
from motor.transcricao import Palavra


def falar(texto: str, inicio: float = 0.0, passo: float = 0.3, pausas: dict[int, float] | None = None) -> list[Palavra]:
    """Gera palavras com tempos artificiais; `pausas` = {índice: segundos extras antes da palavra}."""
    saida, t = [], inicio
    for i, w in enumerate(texto.split()):
        t += (pausas or {}).get(i, 0.0)
        saida.append(Palavra(texto=w, inicio=t, fim=t + passo * 0.8, confianca=0.95))
        t += passo
    return saida


ROTEIRO = Roteiro.de_dict({
    "titulo": "teste",
    "blocos": [
        {"id": "g", "tipo": "gancho", "texto": "Seu cliente só pergunta o preço?"},
        {"id": "d", "tipo": "desenvolvimento", "texto": "Então você está explicando errado o valor do seu serviço."},
        {"id": "c", "tipo": "cta", "texto": "Comente valor que eu te mando o roteiro."},
    ],
})


def test_escolhe_a_ultima_tentativa_quando_empata():
    falado = ("seu cliente só pergunta desculpa seu cliente só pergunta o preço "
              "então você está explicando errado o valor do seu serviço "
              "comente valor que eu te mando o roteiro")
    take = Take(Path("a.mp4"), falar(falado), 0)
    res = alinhar(ROTEIRO, [take])
    assert all(fa.encontrada for fa in res)
    gancho = res[0]
    # a tentativa completa começa na palavra 5 ("seu" depois de "desculpa")
    assert gancho.ocorrencia.i_ini == 5
    assert [p.texto_legenda for p in gancho.palavras][-1] == "preço?"


def test_prefere_take_mais_recente():
    t1 = Take(Path("1.mp4"), falar("seu cliente só pergunta o preço"), 0)
    t2 = Take(Path("2.mp4"), falar("seu cliente só pergunta o preço"), 1)
    res = alinhar(ROTEIRO, [t1, t2])
    assert res[0].ocorrencia.take == 1
    assert not res[1].encontrada and not res[2].encontrada


def test_remove_vicio_e_repeticao_e_corta_pausa_longa():
    falado = "então você ahn está explicando errado o o valor do seu serviço"
    palavras = falar(falado, pausas={8: 1.2})  # pausa longa antes de "valor"
    take = Take(Path("a.mp4"), palavras, 0)
    res = alinhar(ROTEIRO, [take], Ritmo(pausa_max_s=0.25))
    desenvolvimento = res[1]
    removidas = {p.texto_falado: p.removida for p in desenvolvimento.palavras if p.removida}
    assert removidas.get("ahn") == "vicio"
    assert "repeticao" in removidas.values()
    pedacos = trechos(res, [take], Ritmo(pausa_max_s=0.25))
    # ahn, repetição e pausa longa => o trecho é quebrado em vários pedaços
    assert len(pedacos) >= 3
    texto_final = " ".join(p.texto_legenda for t in pedacos for p in t.palavras)
    assert "ahn" not in texto_final
    assert texto_final.count(" o ") == 1


def test_corrige_erro_de_transcricao_na_legenda():
    take = Take(Path("a.mp4"), falar("seu clientes só pergunta o preso"), 0)
    res = alinhar(ROTEIRO, [take])
    legenda = [p.texto_legenda for p in res[0].palavras]
    assert legenda == ["Seu", "cliente", "só", "pergunta", "o", "preço?"]


def test_frase_nao_dita_aparece_como_faltando():
    take = Take(Path("a.mp4"), falar("seu cliente só pergunta o preço"), 0)
    res = alinhar(ROTEIRO, [take])
    assert res[2].faltando[0] == "Comente"


def test_hesitacao_sai_mas_improviso_colado_fica():
    # "Ludo" isolado por pausa = tropeço; "gente" colado nas vizinhas = improviso natural
    roteiro = Roteiro.de_dict({"titulo": "t", "blocos": [
        {"id": "d", "tipo": "desenvolvimento", "texto": "Então o problema não é o preço."}]})
    tropeco = falar("então o problema não é Ludo o preço", pausas={5: 0.4})
    res = alinhar(roteiro, [Take(Path("a.mp4"), tropeco, 0)])
    assert {p.texto_falado: p.removida for p in res[0].palavras}["Ludo"] == "hesitacao"
    improviso = falar("então o problema não é gente o preço")
    res = alinhar(roteiro, [Take(Path("b.mp4"), improviso, 0)])
    assert {p.texto_falado: p.removida for p in res[0].palavras}["gente"] is None
