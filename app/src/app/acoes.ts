"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { removerArquivo } from "@/lib/arquivos";
import { clientes, comentarios, conteudos, referencias, takes, type Roteiro, type Conteudo } from "@/lib/db";
import { checarTakes, extrairFicha, gerarCorte } from "@/lib/fluxo";
import { salvarAjustes, type Ajustes } from "@/lib/estilo";

function texto(fd: FormData, campo: string, max = 2000): string {
  return String(fd.get(campo) ?? "").trim().slice(0, max);
}

// ---------- eugência ----------
export async function criarCliente(fd: FormData) {
  const nome = texto(fd, "nome", 120);
  if (!nome) return;
  const id = clientes.criar(nome, texto(fd, "nicho", 120));
  redirect(`/clientes/${id}`);
}

export async function removerReferencia(referenciaId: string) {
  const r = referencias.obter(referenciaId);
  if (!r) return;
  referencias.remover(referenciaId);
  removerArquivo(r.arquivo);
  extrairFicha(r.cliente_id);
  revalidatePath(`/clientes/${r.cliente_id}`);
}

export async function salvarEstilo(clienteId: string, fd: FormData) {
  const pegar = <T extends string>(campo: string, validos: readonly T[]): T | undefined => {
    const v = String(fd.get(campo) ?? "");
    return (validos as readonly string[]).includes(v) ? (v as T) : undefined;
  };
  const caixa = String(fd.get("legenda_caixa_alta") ?? "");
  const ajustes: Ajustes = {
    ritmo: pegar("ritmo", ["acelerado", "medio", "calmo"] as const),
    legenda_modo: pegar("legenda_modo", ["palavra", "frase", "nenhuma"] as const),
    legenda_caixa_alta: caixa === "sim" ? true : caixa === "nao" ? false : undefined,
    zoom: pegar("zoom", ["nenhum", "baixo", "medio", "alto"] as const),
    cor: pegar("cor", ["neutro", "quente", "frio"] as const),
  };
  const cliente = clientes.obter(clienteId);
  if (!cliente) return;
  await salvarAjustes(cliente, ajustes);
  revalidatePath(`/clientes/${clienteId}`);
}

const ROTEIRO_INICIAL = (titulo: string): Roteiro => ({
  titulo,
  palavras_chave: [],
  blocos: [
    { id: "gancho", tipo: "gancho", texto: "", texto_tela: "" },
    { id: "desenvolvimento", tipo: "desenvolvimento", texto: "" },
    { id: "cta", tipo: "cta", texto: "", texto_tela: "" },
  ],
});

export async function criarConteudo(clienteId: string, fd: FormData) {
  const titulo = texto(fd, "titulo", 140) || "Novo conteúdo";
  const id = conteudos.criar(clienteId, ROTEIRO_INICIAL(titulo));
  redirect(`/conteudos/${id}`);
}

export type ResultadoRoteiro = { ok: boolean; erro?: string };

export async function salvarRoteiro(conteudoId: string, roteiro: Roteiro): Promise<ResultadoRoteiro> {
  const c = conteudos.obter(conteudoId);
  if (!c) return { ok: false, erro: "Conteúdo não encontrado" };
  const blocos = roteiro.blocos
    .map((b, i) => ({ ...b, id: b.id || `bloco${i + 1}`, texto: b.texto.trim(), texto_tela: b.texto_tela?.trim() || undefined }))
    .filter((b) => b.texto);
  if (!blocos.length) return { ok: false, erro: "Escreva o texto de pelo menos um bloco." };
  const limpo: Roteiro = {
    titulo: roteiro.titulo.trim() || "Sem título",
    palavras_chave: roteiro.palavras_chave.map((p) => p.trim()).filter(Boolean).slice(0, 12),
    blocos,
  };
  conteudos.atualizar(conteudoId, { roteiro_json: JSON.stringify(limpo), titulo: limpo.titulo });
  // roteiro mudou: a checagem antiga não vale mais
  if (takes.listar(conteudoId).length && !["editando", "checando"].includes(c.status)) checarTakes(conteudoId);
  revalidatePath(`/conteudos/${conteudoId}`);
  return { ok: true };
}

export async function liberarGravacao(conteudoId: string) {
  const c = conteudos.obter(conteudoId);
  if (!c) return;
  const roteiro = JSON.parse(c.roteiro_json) as Roteiro;
  if (!roteiro.blocos.some((b) => b.texto.trim())) return;
  conteudos.atualizar(conteudoId, { status: takes.listar(conteudoId).length ? "takes_recebidos" : "gravacao" });
  revalidatePath(`/conteudos/${conteudoId}`);
}

export async function removerTake(takeId: string) {
  const t = takes.obter(takeId);
  if (!t) return;
  takes.remover(takeId);
  removerArquivo(t.arquivo);
  checarTakes(t.conteudo_id);
  revalidatePath(`/conteudos/${t.conteudo_id}`);
}

export async function rechecar(conteudoId: string) {
  checarTakes(conteudoId);
  revalidatePath(`/conteudos/${conteudoId}`);
}

export async function definirTrilha(conteudoId: string, trilha: Conteudo["trilha"]) {
  if (!["nenhuma", "calmo", "animado"].includes(trilha)) return;
  conteudos.atualizar(conteudoId, { trilha });
  revalidatePath(`/conteudos/${conteudoId}`);
}

export async function gerarPrimeiroCorte(conteudoId: string) {
  const c = conteudos.obter(conteudoId);
  if (!c || c.status === "editando" || !takes.listar(conteudoId).length) return;
  await gerarCorte(conteudoId);
  revalidatePath(`/conteudos/${conteudoId}`);
}

export async function enviarParaAprovacao(conteudoId: string) {
  conteudos.atualizar(conteudoId, { status: "em_aprovacao" });
  revalidatePath(`/conteudos/${conteudoId}`);
}

export async function reabrirGravacao(conteudoId: string) {
  conteudos.atualizar(conteudoId, { status: "gravacao" });
  revalidatePath(`/conteudos/${conteudoId}`);
}

export async function comentarComoEugencia(conteudoId: string, fd: FormData) {
  const t = texto(fd, "texto");
  if (!t) return;
  comentarios.criar(conteudoId, "eugencia", t);
  revalidatePath(`/conteudos/${conteudoId}`);
}

// ---------- cliente final (pelo link de aprovação) ----------
export async function aprovarPeloLink(token: string, fd: FormData) {
  const c = conteudos.porTokenAprovacao(token);
  if (!c || c.status !== "em_aprovacao") return;
  const t = texto(fd, "texto");
  comentarios.criar(c.id, "cliente", t || "Aprovado.", "aprovacao");
  conteudos.atualizar(c.id, { status: "aprovado" });
  revalidatePath(`/a/${token}`);
}

export async function pedirAjustePeloLink(token: string, fd: FormData) {
  const c = conteudos.porTokenAprovacao(token);
  const t = texto(fd, "texto");
  if (!c || c.status !== "em_aprovacao" || !t) return;
  comentarios.criar(c.id, "cliente", t, "ajuste");
  conteudos.atualizar(c.id, { status: "ajustes" });
  revalidatePath(`/a/${token}`);
}
