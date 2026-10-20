"""Linha de comando do motor.

  python -m motor checar  --roteiro roteiro.json take1.mp4 take2.mp4
  python -m motor cortar  --roteiro roteiro.json --ficha ficha.json -o saida/ take1.mp4 take2.mp4
  python -m motor extrair -o ficha.json referencia1.mp4 referencia2.mp4
  python -m motor renderizar --plano saida/plano.json -o saida/v2.mp4
  python -m motor ficha --preset dinamico -o ficha.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ficha import PRESETS, Ficha, preset
from .roteiro import Roteiro


def _ficha(arg: str | None) -> Ficha:
    if not arg:
        return preset("equilibrado")
    if arg in PRESETS:
        return preset(arg)
    return Ficha.carregar(arg)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="motor", description="Motor do primeiro corte")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("checar", help="Checa os takes contra o roteiro (o que o cliente vê após o upload)")
    c.add_argument("--roteiro", required=True)
    c.add_argument("takes", nargs="+")
    c.add_argument("--json", action="store_true", help="imprime o relatório completo em JSON")

    k = sub.add_parser("cortar", help="Gera o primeiro corte")
    k.add_argument("--roteiro", required=True)
    k.add_argument("--ficha", help="arquivo JSON ou nome de preset (equilibrado, dinamico, calmo)")
    k.add_argument("-o", "--saida", required=True, help="pasta de saída")
    k.add_argument("--rapido", action="store_true", help="renderização rápida para pré-visualização")
    k.add_argument("takes", nargs="+")

    e = sub.add_parser("extrair", help="Extrai a ficha de estilo de uma ou mais referências")
    e.add_argument("-o", "--saida", required=True)
    e.add_argument("--sem-ia", action="store_true", help="só medições por código, sem modelo de visão")
    e.add_argument("--evidencias", help="salva as medições brutas neste JSON")
    e.add_argument("referencias", nargs="+")

    r = sub.add_parser("renderizar", help="Renderiza de novo um plano.json (após ajuste manual)")
    r.add_argument("--plano", required=True)
    r.add_argument("--ficha", help="sobrescreve a ficha gravada no plano")
    r.add_argument("-o", "--saida", required=True)
    r.add_argument("--rapido", action="store_true")

    f = sub.add_parser("ficha", help="Cria uma ficha a partir de um preset")
    f.add_argument("--preset", default="equilibrado", choices=list(PRESETS))
    f.add_argument("-o", "--saida", required=True)

    a = ap.parse_args(argv)

    if a.cmd == "checar":
        from .pipeline import analisar

        an = analisar(Roteiro.carregar(a.roteiro), a.takes)
        if a.json:
            print(json.dumps(an.relatorio.para_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"\nResultado: {an.relatorio.status.upper()}")
            for fr in an.relatorio.frases:
                marca = "ok " if fr.encontrada else "!! "
                print(f"  {marca}[{fr.bloco_id}] {fr.texto}  (similaridade {fr.similaridade:.2f}, "
                      f"{fr.tentativas} tentativa(s))")
            for m in an.relatorio.mensagens():
                print(f"  - {m}")
        return 0 if an.relatorio.status != "regravar" else 2

    if a.cmd == "cortar":
        from .pipeline import primeiro_corte

        ficha = _ficha(a.ficha)
        print(f"Ficha: {ficha.resumo()}")
        resumo = primeiro_corte(Roteiro.carregar(a.roteiro), a.takes, ficha, a.saida, rapido=a.rapido)
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
        return 0

    if a.cmd == "extrair":
        from .extracao import extrair_varias

        ficha, evid = extrair_varias(a.referencias, usar_ia=not a.sem_ia)
        ficha.salvar(a.saida)
        if a.evidencias:
            Path(a.evidencias).write_text(json.dumps(evid, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Ficha salva em {a.saida}: {ficha.resumo()}")
        pendentes = [k for k, v in ficha.origem.items() if v == "padrao"]
        if pendentes:
            print(f"Campos que vieram do padrão (confirme): {', '.join(pendentes)}")
        return 0

    if a.cmd == "renderizar":
        from .pipeline import plano_de_arquivo
        from .render import renderizar

        plano = plano_de_arquivo(a.plano)
        ficha = _ficha(a.ficha) if a.ficha else Ficha.de_dict(plano.ficha)
        print(renderizar(plano, ficha, a.saida, rapido=a.rapido))
        return 0

    if a.cmd == "ficha":
        preset(a.preset).salvar(a.saida)
        print(f"Ficha '{a.preset}' salva em {a.saida}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
