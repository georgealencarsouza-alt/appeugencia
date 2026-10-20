"""Teste de ponta a ponta no navegador: eugência cria tudo, cliente grava pelo link, aprova.

    python testes/e2e.py --take vídeo.mp4 --referencia ref.mp4 --saida pasta_de_prints

Precisa do app rodando em http://localhost:3000 (ou --url).
"""
import argparse
import re
import time
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost:3000")
ap.add_argument("--take", required=True)
ap.add_argument("--referencia")
ap.add_argument("--saida", default="prints")
a = ap.parse_args()
SAIDA = Path(a.saida)
SAIDA.mkdir(parents=True, exist_ok=True)

ROTEIRO = [
    ("E você, que história gostaria de contar para os seus netos? Conta aqui para mim nos comentários.",
     "Que história você contaria para os seus netos?"),
    ("E se essa mensagem fez sentido para você, compartilha com outra avó. Quem sabe as nossas histórias "
     "também podem fazer sentido na vida umas das outras.", ""),
]


def print_(p: Page, nome: str, inteira=True):
    p.screenshot(path=str(SAIDA / f"{nome}.png"), full_page=inteira)
    print("print:", nome)


def esperar_texto(p: Page, padrao: str, limite_s: int = 300):
    fim = time.time() + limite_s
    while time.time() < fim:
        if re.search(padrao, p.content()):
            return
        time.sleep(2)
        p.reload()
    raise TimeoutError(f"não apareceu: {padrao}")


with sync_playwright() as pw:
    nav = pw.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    desk = nav.new_page(viewport={"width": 1366, "height": 900})

    # 1. cliente
    desk.goto(a.url)
    print_(desk, "01_painel_vazio")
    desk.fill("#nome", "Dona Regina")
    desk.fill("#nicho", "avós e família")
    desk.click("text=Cadastrar cliente")
    desk.wait_for_url(re.compile(r"/clientes/"))
    url_cliente = desk.url

    if a.referencia:
        desk.set_input_files("input[type=file]", a.referencia)
        esperar_texto(desk, r"medido na referência", 400)
        print_(desk, "02_cliente_com_estilo")
        # a análise sem IA não mede a legenda: a eugência ajusta para ficar como a referência
        desk.click("text=Ajustar estilo")
        desk.click("text=Frase inteira")
        desk.locator("fieldset", has_text="Caixa alta").get_by_text("Não").click()
        desk.click("text=Salvar estilo")
        expect(desk.get_by_text("ajustado por você").first).to_be_visible()
        print_(desk, "02b_estilo_ajustado")

    # 2. conteúdo + roteiro
    desk.fill("input[name=titulo]", "Histórias para os netos")
    desk.click("text=Criar conteúdo")
    desk.wait_for_url(re.compile(r"/conteudos/"))
    url_conteudo = desk.url
    blocos = desk.locator("ol li textarea")
    telas = desk.locator("ol li input[aria-label='Texto na tela']")
    # o roteiro inicial tem 3 blocos (gancho, desenvolvimento, cta); este vídeo tem 2 partes
    desk.locator("ol li").nth(1).get_by_role("button", name="Remover").click()
    for i, (fala, tela) in enumerate(ROTEIRO):
        blocos.nth(i).fill(fala)
        telas.nth(i).fill(tela)
    desk.fill("#chaves", "netos, avó")
    desk.click("text=Salvar roteiro")
    expect(desk.get_by_text("Roteiro salvo.")).to_be_visible()
    desk.click("text=Liberar gravação")
    expect(desk.get_by_text("Abrir como cliente").first).to_be_visible()
    link_kit = desk.locator("a", has_text="Abrir como cliente").first.get_attribute("href")
    print_(desk, "03_conteudo_liberado")

    # 3. cliente no celular
    cel = nav.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    k = cel.new_page()
    k.goto(a.url + link_kit)
    print_(k, "04_kit_celular")
    # gravador no navegador (câmera falsa do Chromium): abre e confere o teleprompter
    k.get_by_role("button", name=re.compile("Gravar com o roteiro")).click()
    k.wait_for_selector("text=Normal")
    time.sleep(1)
    print_(k, "05_gravador", inteira=False)
    k.get_by_role("button", name="Cancelar").click()
    # envio do arquivo real pela galeria
    k.set_input_files("input[type=file]", a.take)
    esperar_texto(k, r"Recebemos tudo|grave de novo", 400)
    print_(k, "06_kit_depois_do_envio")

    # 4. primeiro corte
    desk.goto(url_conteudo)
    print_(desk, "07_takes_checados")
    desk.click("text=Trilha calma")
    desk.click("text=Gerar primeiro corte")
    esperar_texto(desk, r"Enviar para aprovação", 600)
    print_(desk, "08_corte_pronto")

    # 5. aprovação
    desk.click("text=Enviar para aprovação")
    expect(desk.locator("a", has_text="Abrir como cliente").nth(1)).to_be_visible()
    link_aprov = desk.locator("a", has_text="Abrir como cliente").nth(1).get_attribute("href")
    ap_ = cel.new_page()
    ap_.goto(a.url + link_aprov)
    print_(ap_, "09_aprovacao_celular")
    ap_.click("text=Quero mudar alguma coisa")
    ap_.fill("#texto", "Pode tirar a música no começo?")
    ap_.click("text=Enviar pedido de ajuste")
    expect(ap_.get_by_text("Pedido de ajuste enviado")).to_be_visible()
    desk.goto(url_conteudo)
    print_(desk, "10_eugencia_ve_ajuste")
    desk.click("text=Enviar para aprovação")
    ap_.reload()
    ap_.click("text=Aprovar este vídeo")
    expect(ap_.get_by_text("Vídeo aprovado")).to_be_visible()
    print_(ap_, "11_aprovado")
    desk.goto(a.url)
    print_(desk, "12_painel_final")
    nav.close()
    print("OK: fluxo completo")
