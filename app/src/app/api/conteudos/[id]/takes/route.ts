import { receberTake } from "@/lib/receber-take";
import { conteudos } from "@/lib/db";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const c = conteudos.obter(id);
  if (!c) return Response.json({ erro: "Conteúdo não encontrado" }, { status: 404 });
  return receberTake(req, c.id);
}
