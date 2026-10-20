import "server-only";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { DADOS_DIR } from "./db";

export const ARQUIVOS_DIR = path.join(DADOS_DIR, "arquivos");
const LIMITE_BYTES = 3 * 1024 ** 3; // 3 GB: um take 4K de alguns minutos cabe
const EXTENSOES_VIDEO = new Set([".mp4", ".mov", ".m4v", ".webm", ".3gp", ".mkv"]);

export function pasta(...partes: string[]): string {
  const p = path.join(ARQUIVOS_DIR, ...partes);
  fs.mkdirSync(p, { recursive: true });
  return p;
}

/** Caminho relativo (o que vai para o banco) -> absoluto, sem permitir sair da pasta de arquivos. */
export function absoluto(relativo: string): string {
  const p = path.resolve(ARQUIVOS_DIR, relativo);
  if (!p.startsWith(ARQUIVOS_DIR + path.sep)) throw new Error("Caminho inválido");
  return p;
}

export function relativo(abs: string): string {
  return path.relative(ARQUIVOS_DIR, abs);
}

export function extensaoVideo(nome: string): string {
  const ext = path.extname(nome).toLowerCase();
  return EXTENSOES_VIDEO.has(ext) ? ext : ".mp4";
}

export function ehVideo(nome: string, tipo: string | null): boolean {
  return (tipo ?? "").startsWith("video/") || EXTENSOES_VIDEO.has(path.extname(nome).toLowerCase());
}

/**
 * Grava o corpo da requisição direto no disco, sem carregar o vídeo na memória.
 * O cliente envia o arquivo cru (não multipart), o que permite barra de progresso e arquivos grandes.
 */
export async function salvarCorpo(req: Request, destino: string): Promise<number> {
  if (!req.body) throw new Error("Arquivo vazio");
  const declarado = Number(req.headers.get("content-length") ?? 0);
  if (declarado > LIMITE_BYTES) throw new Error("Arquivo grande demais (limite de 3 GB)");
  let total = 0;
  const contador = new Transform({
    transform(chunk, _enc, cb) {
      total += chunk.length;
      if (total > LIMITE_BYTES) cb(new Error("Arquivo grande demais (limite de 3 GB)"));
      else cb(null, chunk);
    },
  });
  const temporario = `${destino}.parcial`;
  try {
    await pipeline(Readable.fromWeb(req.body as never), contador, fs.createWriteStream(temporario));
    if (total === 0) throw new Error("Arquivo vazio");
    fs.renameSync(temporario, destino);
    return total;
  } catch (e) {
    fs.rmSync(temporario, { force: true });
    throw e;
  }
}

const TIPOS: Record<string, string> = {
  ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
  ".3gp": "video/3gpp", ".mkv": "video/x-matroska", ".jpg": "image/jpeg", ".png": "image/png", ".wav": "audio/wav",
};

/** Serve um arquivo com suporte a Range (necessário para o player de vídeo do Safari/iPhone). */
export function servir(abs: string, req: Request, nomeDownload?: string): Response {
  if (!fs.existsSync(abs)) return new Response("Arquivo não encontrado", { status: 404 });
  const tamanho = fs.statSync(abs).size;
  const tipo = TIPOS[path.extname(abs).toLowerCase()] ?? "application/octet-stream";
  const base: Record<string, string> = { "Content-Type": tipo, "Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600" };
  if (nomeDownload) base["Content-Disposition"] = `attachment; filename="${nomeDownload.replace(/"/g, "")}"`;
  const range = req.headers.get("range");
  const m = range?.match(/bytes=(\d*)-(\d*)/);
  if (m) {
    let ini = m[1] ? Number(m[1]) : NaN;
    let fim = m[2] ? Number(m[2]) : tamanho - 1;
    if (Number.isNaN(ini)) { ini = Math.max(0, tamanho - fim); fim = tamanho - 1; } // "bytes=-500"
    fim = Math.min(fim, tamanho - 1);
    if (ini > fim || ini >= tamanho) {
      return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${tamanho}` } });
    }
    const corpo = Readable.toWeb(fs.createReadStream(abs, { start: ini, end: fim })) as ReadableStream;
    return new Response(corpo, {
      status: 206,
      headers: { ...base, "Content-Range": `bytes ${ini}-${fim}/${tamanho}`, "Content-Length": String(fim - ini + 1) },
    });
  }
  const corpo = Readable.toWeb(fs.createReadStream(abs)) as ReadableStream;
  return new Response(corpo, { headers: { ...base, "Content-Length": String(tamanho) } });
}

export function removerArquivo(rel: string) {
  try {
    fs.rmSync(absoluto(rel), { force: true });
    fs.rmSync(caminhoCapa(absoluto(rel)), { force: true });
  } catch {
    /* já não existe */
  }
}

export function caminhoCapa(abs: string): string {
  return abs.replace(/\.[^.]+$/, "") + ".capa.jpg";
}

/**
 * Gera a imagem de capa (o iPhone não mostra o primeiro quadro de um vídeo sem `poster`).
 * Rápida: um quadro só, reduzido.
 */
export function gerarCapa(abs: string): Promise<void> {
  return new Promise((resolve) => {
    const proc = spawn("ffmpeg", ["-v", "error", "-y", "-ss", "0.8", "-i", abs, "-frames:v", "1",
      "-vf", "scale=360:-2", "-q:v", "4", caminhoCapa(abs)]);
    proc.on("close", () => resolve());
    proc.on("error", () => resolve());
  });
}
