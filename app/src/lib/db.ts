import "server-only";
import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";
import { customAlphabet } from "nanoid";

export const DADOS_DIR = path.resolve(process.env.DADOS_DIR ?? "./dados");
fs.mkdirSync(DADOS_DIR, { recursive: true });

const id = customAlphabet("0123456789abcdefghijkmnopqrstuvwxyz", 12);
/** Token de link público: longo o bastante para não ser adivinhado. */
export const token = customAlphabet("23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz", 22);

declare global {
  // eslint-disable-next-line no-var
  var __db: Database.Database | undefined;
}

function abrir(): Database.Database {
  const db = new Database(path.join(DADOS_DIR, "app.db"));
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  db.exec(`
    CREATE TABLE IF NOT EXISTS clientes (
      id TEXT PRIMARY KEY,
      nome TEXT NOT NULL,
      nicho TEXT NOT NULL DEFAULT '',
      ficha_json TEXT,
      ficha_resumo TEXT,
      ficha_status TEXT NOT NULL DEFAULT 'sem_referencias',
      ficha_erro TEXT,
      criado_em TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS referencias (
      id TEXT PRIMARY KEY,
      cliente_id TEXT NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
      arquivo TEXT NOT NULL,
      nome_original TEXT NOT NULL,
      criado_em TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS conteudos (
      id TEXT PRIMARY KEY,
      cliente_id TEXT NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
      titulo TEXT NOT NULL,
      roteiro_json TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'rascunho',
      token_kit TEXT NOT NULL UNIQUE,
      token_aprovacao TEXT NOT NULL UNIQUE,
      trilha TEXT NOT NULL DEFAULT 'nenhuma',
      checagem_json TEXT,
      checagem_erro TEXT,
      criado_em TEXT NOT NULL DEFAULT (datetime('now')),
      atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS takes (
      id TEXT PRIMARY KEY,
      conteudo_id TEXT NOT NULL REFERENCES conteudos(id) ON DELETE CASCADE,
      arquivo TEXT NOT NULL,
      nome_original TEXT NOT NULL,
      tamanho INTEGER NOT NULL,
      criado_em TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS cortes (
      id TEXT PRIMARY KEY,
      conteudo_id TEXT NOT NULL REFERENCES conteudos(id) ON DELETE CASCADE,
      status TEXT NOT NULL DEFAULT 'processando',
      video TEXT,
      resumo_json TEXT,
      erro TEXT,
      criado_em TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS comentarios (
      id TEXT PRIMARY KEY,
      conteudo_id TEXT NOT NULL REFERENCES conteudos(id) ON DELETE CASCADE,
      autor TEXT NOT NULL,
      texto TEXT NOT NULL,
      tipo TEXT NOT NULL DEFAULT 'comentario',
      criado_em TEXT NOT NULL DEFAULT (datetime('now'))
    );
  `);
  // Trabalhos que estavam rodando quando o servidor caiu não vão terminar sozinhos.
  db.exec(`
    UPDATE cortes SET status='erro', erro='Interrompido (o servidor reiniciou). Gere de novo.' WHERE status='processando';
    UPDATE conteudos SET status='takes_recebidos' WHERE status IN ('checando','editando');
    UPDATE clientes SET ficha_status='erro', ficha_erro='Interrompido (o servidor reiniciou).' WHERE ficha_status='processando';
  `);
  return db;
}

export const db: Database.Database = globalThis.__db ?? (globalThis.__db = abrir());

// ---------- tipos ----------
export type BlocoRoteiro = { id: string; tipo: "gancho" | "desenvolvimento" | "cta"; texto: string; texto_tela?: string };
export type Roteiro = { titulo: string; palavras_chave: string[]; blocos: BlocoRoteiro[] };

export type StatusConteudo =
  | "rascunho" | "gravacao" | "checando" | "regravar" | "takes_recebidos"
  | "editando" | "corte_pronto" | "em_aprovacao" | "ajustes" | "aprovado";

export type Cliente = {
  id: string; nome: string; nicho: string; ficha_json: string | null; ficha_resumo: string | null;
  ficha_status: "sem_referencias" | "processando" | "pronta" | "erro"; ficha_erro: string | null; criado_em: string;
};
export type Referencia = { id: string; cliente_id: string; arquivo: string; nome_original: string; criado_em: string };
export type Conteudo = {
  id: string; cliente_id: string; titulo: string; roteiro_json: string; status: StatusConteudo;
  token_kit: string; token_aprovacao: string; trilha: "nenhuma" | "calmo" | "animado";
  checagem_json: string | null; checagem_erro: string | null; criado_em: string; atualizado_em: string;
};
export type Take = { id: string; conteudo_id: string; arquivo: string; nome_original: string; tamanho: number; criado_em: string };
export type Corte = {
  id: string; conteudo_id: string; status: "processando" | "pronto" | "erro"; video: string | null;
  resumo_json: string | null; erro: string | null; criado_em: string;
};
export type Comentario = {
  id: string; conteudo_id: string; autor: "eugencia" | "cliente"; texto: string;
  tipo: "comentario" | "aprovacao" | "ajuste"; criado_em: string;
};

// ---------- clientes ----------
export const clientes = {
  listar: () =>
    db.prepare(`SELECT c.*, (SELECT count(*) FROM conteudos WHERE cliente_id=c.id) AS total_conteudos
                FROM clientes c ORDER BY c.criado_em DESC`).all() as (Cliente & { total_conteudos: number })[],
  obter: (cid: string) => db.prepare("SELECT * FROM clientes WHERE id=?").get(cid) as Cliente | undefined,
  criar: (nome: string, nicho: string) => {
    const novo = id();
    db.prepare("INSERT INTO clientes (id, nome, nicho) VALUES (?,?,?)").run(novo, nome, nicho);
    return novo;
  },
  atualizarFicha: (cid: string, campos: Partial<Pick<Cliente, "ficha_json" | "ficha_resumo" | "ficha_status" | "ficha_erro">>) => {
    const chaves = Object.keys(campos);
    if (!chaves.length) return;
    db.prepare(`UPDATE clientes SET ${chaves.map((k) => `${k}=@${k}`).join(", ")} WHERE id=@id`).run({ ...campos, id: cid });
  },
};

export const referencias = {
  listar: (cid: string) => db.prepare("SELECT * FROM referencias WHERE cliente_id=? ORDER BY criado_em").all(cid) as Referencia[],
  criar: (cid: string, arquivo: string, nome: string) => {
    const novo = id();
    db.prepare("INSERT INTO referencias (id, cliente_id, arquivo, nome_original) VALUES (?,?,?,?)").run(novo, cid, arquivo, nome);
    return novo;
  },
  obter: (rid: string) => db.prepare("SELECT * FROM referencias WHERE id=?").get(rid) as Referencia | undefined,
  remover: (rid: string) => db.prepare("DELETE FROM referencias WHERE id=?").run(rid),
};

// ---------- conteúdos ----------
export const conteudos = {
  doCliente: (cid: string) =>
    db.prepare("SELECT * FROM conteudos WHERE cliente_id=? ORDER BY criado_em DESC").all(cid) as Conteudo[],
  recentes: (limite = 20) =>
    db.prepare(`SELECT co.*, cl.nome AS cliente_nome FROM conteudos co JOIN clientes cl ON cl.id=co.cliente_id
                ORDER BY co.atualizado_em DESC LIMIT ?`).all(limite) as (Conteudo & { cliente_nome: string })[],
  obter: (cid: string) => db.prepare("SELECT * FROM conteudos WHERE id=?").get(cid) as Conteudo | undefined,
  porTokenKit: (t: string) => db.prepare("SELECT * FROM conteudos WHERE token_kit=?").get(t) as Conteudo | undefined,
  porTokenAprovacao: (t: string) => db.prepare("SELECT * FROM conteudos WHERE token_aprovacao=?").get(t) as Conteudo | undefined,
  criar: (clienteId: string, roteiro: Roteiro) => {
    const novo = id();
    db.prepare(`INSERT INTO conteudos (id, cliente_id, titulo, roteiro_json, token_kit, token_aprovacao)
                VALUES (?,?,?,?,?,?)`).run(novo, clienteId, roteiro.titulo, JSON.stringify(roteiro), token(), token());
    return novo;
  },
  atualizar: (cid: string, campos: Partial<Omit<Conteudo, "id" | "cliente_id" | "criado_em">>) => {
    const chaves = Object.keys(campos);
    if (!chaves.length) return;
    db.prepare(`UPDATE conteudos SET ${chaves.map((k) => `${k}=@${k}`).join(", ")}, atualizado_em=datetime('now') WHERE id=@id`)
      .run({ ...campos, id: cid });
  },
};

export const takes = {
  listar: (cid: string) => db.prepare("SELECT * FROM takes WHERE conteudo_id=? ORDER BY criado_em").all(cid) as Take[],
  criar: (cid: string, arquivo: string, nome: string, tamanho: number) => {
    const novo = id();
    db.prepare("INSERT INTO takes (id, conteudo_id, arquivo, nome_original, tamanho) VALUES (?,?,?,?,?)").run(novo, cid, arquivo, nome, tamanho);
    return novo;
  },
  obter: (tid: string) => db.prepare("SELECT * FROM takes WHERE id=?").get(tid) as Take | undefined,
  remover: (tid: string) => db.prepare("DELETE FROM takes WHERE id=?").run(tid),
};

export const cortes = {
  listar: (cid: string) => db.prepare("SELECT * FROM cortes WHERE conteudo_id=? ORDER BY criado_em DESC").all(cid) as Corte[],
  ultimo: (cid: string) =>
    db.prepare("SELECT * FROM cortes WHERE conteudo_id=? ORDER BY criado_em DESC LIMIT 1").get(cid) as Corte | undefined,
  ultimoPronto: (cid: string) =>
    db.prepare("SELECT * FROM cortes WHERE conteudo_id=? AND status='pronto' ORDER BY criado_em DESC LIMIT 1").get(cid) as Corte | undefined,
  obter: (id_: string) => db.prepare("SELECT * FROM cortes WHERE id=?").get(id_) as Corte | undefined,
  criar: (cid: string) => {
    const novo = id();
    db.prepare("INSERT INTO cortes (id, conteudo_id) VALUES (?,?)").run(novo, cid);
    return novo;
  },
  atualizar: (id_: string, campos: Partial<Pick<Corte, "status" | "video" | "resumo_json" | "erro">>) => {
    const chaves = Object.keys(campos);
    db.prepare(`UPDATE cortes SET ${chaves.map((k) => `${k}=@${k}`).join(", ")} WHERE id=@id`).run({ ...campos, id: id_ });
  },
};

export const comentarios = {
  listar: (cid: string) => db.prepare("SELECT * FROM comentarios WHERE conteudo_id=? ORDER BY criado_em").all(cid) as Comentario[],
  criar: (cid: string, autor: Comentario["autor"], texto: string, tipo: Comentario["tipo"] = "comentario") =>
    db.prepare("INSERT INTO comentarios (id, conteudo_id, autor, texto, tipo) VALUES (?,?,?,?,?)").run(id(), cid, autor, texto, tipo),
};

export function roteiroDe(c: Conteudo): Roteiro {
  return JSON.parse(c.roteiro_json) as Roteiro;
}
