import "server-only";
import fs from "node:fs";
import path from "node:path";
import { absoluto, gerarCapa, pasta, relativo } from "./arquivos";
import { clientes, conteudos, cortes, referencias, roteiroDe, takes } from "./db";
import { fichaFinal } from "./estilo";
import { jsonDaSaida, resumoErro, rodarMotor } from "./motor";

/* Etapas longas rodam em segundo plano; o status fica no banco e as telas consultam. */

export type ProblemaChecagem = { gravidade: "regravar" | "atencao"; codigo: string; mensagem: string };
export type RelatorioChecagem = {
  status: "ok" | "atencao" | "regravar";
  takes: { caminho: string; status: string; problemas: ProblemaChecagem[]; duracao: number; resolucao: string }[];
  frases: { bloco_id: string; texto: string; encontrada: boolean; similaridade: number; tentativas: number; take: string | null; faltando: string[] }[];
  problemas: ProblemaChecagem[];
};
export type ResumoCorte = {
  duracao_bruta_s: number; duracao_final_s: number; trechos: number; frases_encontradas: number;
  frases_total: number; removidas: Record<string, number>; tempo_processamento_s: number; ficha: string;
};

export function extrairFicha(clienteId: string) {
  const refs = referencias.listar(clienteId);
  if (!refs.length) {
    clientes.atualizarFicha(clienteId, { ficha_status: "sem_referencias", ficha_json: null, ficha_resumo: null, ficha_erro: null });
    return;
  }
  clientes.atualizarFicha(clienteId, { ficha_status: "processando", ficha_erro: null });
  const destino = path.join(pasta("clientes", clienteId), "ficha.json");
  void rodarMotor(["extrair", "--json", "-o", destino, ...refs.map((r) => absoluto(r.arquivo))]).then((r) => {
    const info = jsonDaSaida<{ resumo: string }>(r.saida);
    if (r.codigo !== 0 || !info || !fs.existsSync(destino)) {
      clientes.atualizarFicha(clienteId, { ficha_status: "erro", ficha_erro: resumoErro(r) });
      return;
    }
    clientes.atualizarFicha(clienteId, {
      ficha_status: "pronta", ficha_json: fs.readFileSync(destino, "utf-8"), ficha_resumo: info.resumo, ficha_erro: null,
    });
  });
}

function escreverRoteiro(conteudoId: string, dir: string): string {
  const c = conteudos.obter(conteudoId)!;
  const arq = path.join(dir, "roteiro.json");
  fs.writeFileSync(arq, JSON.stringify(roteiroDe(c), null, 2));
  return arq;
}

export function checarTakes(conteudoId: string) {
  const lista = takes.listar(conteudoId);
  if (!lista.length) {
    conteudos.atualizar(conteudoId, { status: "gravacao", checagem_json: null, checagem_erro: null });
    return;
  }
  conteudos.atualizar(conteudoId, { status: "checando", checagem_erro: null });
  const dir = pasta("conteudos", conteudoId);
  const roteiro = escreverRoteiro(conteudoId, dir);
  void rodarMotor(["checar", "--json", "--roteiro", roteiro, ...lista.map((t) => absoluto(t.arquivo))]).then((r) => {
    const rel = jsonDaSaida<RelatorioChecagem>(r.saida);
    // código 2 = checagem rodou e pediu regravação; não é falha do motor
    if (!rel || (r.codigo !== 0 && r.codigo !== 2)) {
      conteudos.atualizar(conteudoId, { status: "takes_recebidos", checagem_erro: resumoErro(r) });
      return;
    }
    // troca o caminho absoluto pelo id do take, para a tela saber de qual take se trata
    const porCaminho = new Map(lista.map((t) => [absoluto(t.arquivo), t.id]));
    rel.takes = rel.takes.map((t) => ({ ...t, caminho: porCaminho.get(t.caminho) ?? t.caminho }));
    rel.frases = rel.frases.map((f) => ({ ...f, take: f.take ? (porCaminho.get(f.take) ?? f.take) : null }));
    conteudos.atualizar(conteudoId, {
      status: rel.status === "regravar" ? "regravar" : "takes_recebidos",
      checagem_json: JSON.stringify(rel),
      checagem_erro: null,
    });
  });
}

export async function gerarCorte(conteudoId: string): Promise<string> {
  const c = conteudos.obter(conteudoId)!;
  const cliente = clientes.obter(c.cliente_id)!;
  const lista = takes.listar(conteudoId);
  const corteId = cortes.criar(conteudoId);
  const dir = pasta("conteudos", conteudoId, "cortes", corteId);
  const roteiro = escreverRoteiro(conteudoId, dir);
  const ficha = path.join(dir, "ficha.json");
  fs.writeFileSync(ficha, JSON.stringify(await fichaFinal(cliente), null, 2));
  const statusAnterior = c.status;
  conteudos.atualizar(conteudoId, { status: "editando" });
  const args = ["cortar", "--roteiro", roteiro, "--ficha", ficha, "-o", dir];
  if (c.trilha !== "nenhuma") args.push("--trilha", c.trilha);
  void rodarMotor([...args, ...lista.map((t) => absoluto(t.arquivo))]).then(async (r) => {
    const video = path.join(dir, "primeiro_corte.mp4");
    const resumo = jsonDaSaida<ResumoCorte>(r.saida);
    if (r.codigo !== 0 || !fs.existsSync(video)) {
      cortes.atualizar(corteId, { status: "erro", erro: resumoErro(r) });
      conteudos.atualizar(conteudoId, { status: statusAnterior === "editando" ? "takes_recebidos" : statusAnterior });
      return;
    }
    await gerarCapa(video);
    cortes.atualizar(corteId, { status: "pronto", video: relativo(video), resumo_json: JSON.stringify(resumo) });
    conteudos.atualizar(conteudoId, { status: "corte_pronto" });
  });
  return corteId;
}
