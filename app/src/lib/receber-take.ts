import "server-only";
import path from "node:path";
import { customAlphabet } from "nanoid";
import { ehVideo, extensaoVideo, gerarCapa, pasta, relativo, salvarCorpo } from "./arquivos";
import { takes } from "./db";
import { checarTakes } from "./fluxo";

const nomeArquivo = customAlphabet("abcdefghijkmnopqrstuvwxyz23456789", 10);

export async function receberTake(req: Request, conteudoId: string): Promise<Response> {
  const nome = decodeURIComponent(req.headers.get("x-nome") ?? "take.mp4");
  if (!ehVideo(nome, req.headers.get("content-type"))) {
    return Response.json({ erro: "Esse arquivo não é um vídeo." }, { status: 400 });
  }
  const destino = path.join(pasta("conteudos", conteudoId, "takes"), nomeArquivo() + extensaoVideo(nome));
  let bytes: number;
  try {
    bytes = await salvarCorpo(req, destino);
  } catch (e) {
    return Response.json({ erro: (e as Error).message }, { status: 400 });
  }
  await gerarCapa(destino);
  takes.criar(conteudoId, relativo(destino), nome, bytes);
  checarTakes(conteudoId);
  return Response.json({ ok: true });
}
