import "server-only";
import fs from "node:fs";
import path from "node:path";
import { pasta } from "./arquivos";
import { db, type Cliente } from "./db";
import { rodarMotor } from "./motor";

/*
 * Estilo final de um cliente = ficha extraída das referências + ajustes manuais da eugência.
 * Os ajustes ficam separados para sobreviver a uma nova análise de referências.
 */

try {
  db.exec("ALTER TABLE clientes ADD COLUMN estilo_ajustes TEXT");
} catch {
  /* coluna já existe */
}

export type Ajustes = Partial<{
  ritmo: "acelerado" | "medio" | "calmo";
  legenda_modo: "palavra" | "frase" | "nenhuma";
  legenda_caixa_alta: boolean;
  zoom: "nenhum" | "baixo" | "medio" | "alto";
  cor: "neutro" | "quente" | "frio";
}>;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type FichaJson = Record<string, any> & { origem: Record<string, string> };

const PAUSA: Record<string, number> = { acelerado: 0.15, medio: 0.3, calmo: 0.5 };

let fichaPadrao: FichaJson | null = null;
async function padrao(): Promise<FichaJson> {
  if (fichaPadrao) return fichaPadrao;
  const arq = path.join(pasta("sistema"), "ficha_padrao.json");
  if (!fs.existsSync(arq)) await rodarMotor(["ficha", "--preset", "equilibrado", "-o", arq]);
  fichaPadrao = JSON.parse(fs.readFileSync(arq, "utf-8")) as FichaJson;
  return fichaPadrao;
}

export function lerAjustes(c: Cliente): Ajustes {
  const bruto = (c as Cliente & { estilo_ajustes?: string | null }).estilo_ajustes;
  return bruto ? (JSON.parse(bruto) as Ajustes) : {};
}

/** Guarda só o que difere da ficha extraída: o resto continua acompanhando as referências. */
export async function salvarAjustes(c: Cliente, pedidos: Ajustes) {
  const base = descrever(await fichaFinal({ ...c, estilo_ajustes: null } as Cliente));
  const atuais: Record<keyof Ajustes, string | boolean> = {
    ritmo: base.ritmo.valor, legenda_modo: base.legenda.valor, legenda_caixa_alta: base.legenda.caixa_alta,
    zoom: base.zoom.valor, cor: base.cor.valor,
  };
  const diferentes = Object.fromEntries(
    Object.entries(pedidos).filter(([k, v]) => v !== undefined && v !== atuais[k as keyof Ajustes]),
  ) as Ajustes;
  db.prepare("UPDATE clientes SET estilo_ajustes=? WHERE id=?").run(JSON.stringify(diferentes), c.id);
}

export async function fichaFinal(c: Cliente): Promise<FichaJson> {
  const base: FichaJson = structuredClone(c.ficha_status === "pronta" && c.ficha_json ? JSON.parse(c.ficha_json) : await padrao());
  const a = lerAjustes(c);
  base.origem ??= {};
  const marcar = (chave: string) => (base.origem[chave] = "manual");
  if (a.ritmo) {
    base.ritmo.pausa_max_s = PAUSA[a.ritmo];
    base.ritmo.respiro_fim_s = Math.min(0.2, Math.max(0.04, PAUSA[a.ritmo] * 0.45));
    marcar("ritmo.pausa_max_s");
  }
  if (a.legenda_modo) {
    base.legenda.modo = a.legenda_modo;
    if (a.legenda_modo === "frase") {
      base.legenda.tamanho = Math.min(base.legenda.tamanho, 60);
      base.legenda.destacar_palavra_atual = false;
    }
    marcar("legenda.modo");
  }
  if (a.legenda_caixa_alta !== undefined) {
    base.legenda.caixa_alta = a.legenda_caixa_alta;
    marcar("legenda.caixa_alta");
  }
  if (a.zoom) {
    base.movimento.zoom_frequencia = a.zoom;
    marcar("movimento.zoom_frequencia");
  }
  if (a.cor) {
    base.cor.tom = a.cor;
    marcar("cor.tom");
  }
  return base;
}

/** Valores atuais em linguagem de eugência, com a origem de cada um. */
export function descrever(f: FichaJson) {
  const p = f.ritmo.pausa_max_s as number;
  const ritmo = p <= 0.18 ? "acelerado" : p <= 0.4 ? "medio" : "calmo";
  const o = (k: string) => f.origem?.[k] ?? "padrao";
  return {
    ritmo: { valor: ritmo, texto: { acelerado: "Acelerado, quase sem respiro", medio: "Médio, com pausas curtas", calmo: "Calmo, com respiro" }[ritmo], origem: o("ritmo.pausa_max_s") },
    legenda: {
      valor: f.legenda.modo as string,
      caixa_alta: f.legenda.caixa_alta as boolean,
      texto: f.legenda.modo === "nenhuma" ? "Sem legenda"
        : (f.legenda.modo === "frase" ? "Frase inteira" : `${f.legenda.palavras_por_bloco} palavras por vez`) + (f.legenda.caixa_alta ? ", em caixa alta" : ""),
      origem: [o("legenda.modo"), o("legenda.caixa_alta")].includes("padrao") ? "padrao" : o("legenda.modo"),
    },
    zoom: {
      valor: f.movimento.zoom_frequencia as string,
      texto: f.movimento.zoom_frequencia === "nenhum" ? "Sem zoom"
        : `${({ baixo: "Pouco", medio: "Moderado", alto: "Frequente" } as Record<string, string>)[f.movimento.zoom_frequencia]}, ${f.movimento.zoom_tipo === "corte" ? "em corte seco" : "suave"}`,
      origem: o("movimento.zoom_frequencia"),
    },
    cor: { valor: f.cor.tom as string, texto: ({ neutro: "Neutra", quente: "Quente", frio: "Fria" } as Record<string, string>)[f.cor.tom], origem: o("cor.tom") },
  };
}
