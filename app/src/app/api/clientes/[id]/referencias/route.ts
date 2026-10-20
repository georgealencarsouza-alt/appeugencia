import path from "node:path";
import { ehVideo, extensaoVideo, gerarCapa, pasta, relativo, salvarCorpo } from "@/lib/arquivos";
import { clientes, referencias } from "@/lib/db";
import { extrairFicha } from "@/lib/fluxo";
import { customAlphabet } from "nanoid";

const nomeArquivo = customAlphabet("abcdefghijkmnopqrstuvwxyz23456789", 10);

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!clientes.obter(id)) return Response.json({ erro: "Cliente não encontrado" }, { status: 404 });
  const nome = decodeURIComponent(req.headers.get("x-nome") ?? "referencia.mp4");
  if (!ehVideo(nome, req.headers.get("content-type"))) return Response.json({ erro: "Envie um arquivo de vídeo" }, { status: 400 });
  const destino = path.join(pasta("clientes", id, "referencias"), nomeArquivo() + extensaoVideo(nome));
  try {
    await salvarCorpo(req, destino);
  } catch (e) {
    return Response.json({ erro: (e as Error).message }, { status: 400 });
  }
  await gerarCapa(destino);
  referencias.criar(id, relativo(destino), nome);
  extrairFicha(id);
  return Response.json({ ok: true });
}
