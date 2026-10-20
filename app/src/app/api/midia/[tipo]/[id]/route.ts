import { absoluto, caminhoCapa, servir } from "@/lib/arquivos";
import { cortes, referencias, takes } from "@/lib/db";

// Mídia do lado da eugência. (O MVP roda sem login; antes de ir ao ar, proteger com autenticação.)
export async function GET(req: Request, { params }: { params: Promise<{ tipo: string; id: string }> }) {
  const { tipo, id } = await params;
  const busca = new URL(req.url).searchParams;
  const baixar = busca.has("baixar");
  let rel: string | null | undefined;
  let nome = "video.mp4";
  if (tipo === "take") { const t = takes.obter(id); rel = t?.arquivo; nome = t?.nome_original ?? nome; }
  else if (tipo === "referencia") { const r = referencias.obter(id); rel = r?.arquivo; nome = r?.nome_original ?? nome; }
  else if (tipo === "corte") { rel = cortes.obter(id)?.video; nome = `primeiro-corte-${id}.mp4`; }
  if (!rel) return new Response("Não encontrado", { status: 404 });
  if (busca.has("capa")) return servir(caminhoCapa(absoluto(rel)), req);
  return servir(absoluto(rel), req, baixar ? nome : undefined);
}
