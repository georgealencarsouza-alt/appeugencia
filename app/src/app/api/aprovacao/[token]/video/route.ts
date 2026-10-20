import { absoluto, caminhoCapa, servir } from "@/lib/arquivos";
import { conteudos, cortes } from "@/lib/db";

export async function GET(req: Request, { params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const c = conteudos.porTokenAprovacao(token);
  const corte = c ? cortes.ultimoPronto(c.id) : undefined;
  if (!corte?.video) return new Response("Não encontrado", { status: 404 });
  if (new URL(req.url).searchParams.has("capa")) return servir(caminhoCapa(absoluto(corte.video)), req);
  return servir(absoluto(corte.video), req);
}
