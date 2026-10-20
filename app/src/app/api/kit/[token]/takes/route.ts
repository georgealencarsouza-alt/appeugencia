import { receberTake } from "@/lib/receber-take";
import { conteudos } from "@/lib/db";

const ABERTOS = new Set(["gravacao", "regravar", "takes_recebidos", "checando"]);

export async function POST(req: Request, { params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const c = conteudos.porTokenKit(token);
  if (!c) return Response.json({ erro: "Link inválido" }, { status: 404 });
  if (!ABERTOS.has(c.status)) return Response.json({ erro: "Esta gravação já foi encerrada pela agência." }, { status: 409 });
  return receberTake(req, c.id);
}
