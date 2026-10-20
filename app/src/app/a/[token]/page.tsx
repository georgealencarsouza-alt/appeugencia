import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { aprovarPeloLink, pedirAjustePeloLink } from "@/app/acoes";
import { botao, campo } from "@/components/ui";
import { clientes, comentarios, conteudos, cortes } from "@/lib/db";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Seu vídeo para aprovar", robots: { index: false } };

export default async function Aprovacao({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const c = conteudos.porTokenAprovacao(token);
  if (!c) notFound();
  const corte = cortes.ultimoPronto(c.id);
  if (!corte || !["em_aprovacao", "ajustes", "aprovado"].includes(c.status)) notFound();
  const cliente = clientes.obter(c.cliente_id)!;
  const conversa = comentarios.listar(c.id);

  return (
    <main className="mx-auto max-w-md px-4 pb-16 pt-6">
      <p className="mb-1 text-tinta-2">Para {cliente.nome}</p>
      <h1 className="mb-5 text-4xl font-extrabold">{c.titulo}</h1>

      <video src={`/api/aprovacao/${token}/video`} poster={`/api/aprovacao/${token}/video?capa`} controls playsInline preload="metadata" className="moldura mb-6 w-full" />

      {c.status === "em_aprovacao" && (
        <div className="space-y-4">
          <form action={aprovarPeloLink.bind(null, token)}>
            <input type="hidden" name="texto" value="" />
            <button className={botao.primario + " w-full !py-4 text-lg"}>Aprovar este vídeo</button>
          </form>
          <details className="rounded-2xl bg-cartao p-4">
            <summary className="cursor-pointer text-lg font-bold">Quero mudar alguma coisa</summary>
            <form action={pedirAjustePeloLink.bind(null, token)} className="mt-3 space-y-3">
              <label htmlFor="texto" className="block text-tinta-2">Diga o que mudar. Se for num momento específico, cite o segundo (ex.: &quot;no 0:12&quot;).</label>
              <textarea id="texto" name="texto" required rows={4} maxLength={2000} className={campo} />
              <button className={botao.secundario + " w-full"}>Enviar pedido de ajuste</button>
            </form>
          </details>
        </div>
      )}
      {c.status === "aprovado" && (
        <div className="rounded-2xl bg-ok-claro p-5" role="status">
          <p className="text-lg font-bold text-ok">Vídeo aprovado</p>
          <p className="text-tinta-2">Obrigado! A agência já foi avisada.</p>
        </div>
      )}
      {c.status === "ajustes" && (
        <div className="rounded-2xl bg-marca-claro p-5" role="status">
          <p className="text-lg font-bold">Pedido de ajuste enviado</p>
          <p className="text-tinta-2">A agência vai fazer as mudanças e te mandar uma nova versão.</p>
        </div>
      )}

      {conversa.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-xl font-bold">Conversa</h2>
          <ol className="space-y-2">
            {conversa.map((m) => (
              <li key={m.id} className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${m.autor === "cliente" ? "ml-auto bg-petroleo-claro" : "bg-cartao"}`}>
                <p className="text-xs font-bold text-tinta-2">{m.autor === "cliente" ? "Você" : "Agência"}</p>
                <p className="whitespace-pre-wrap">{m.texto}</p>
              </li>
            ))}
          </ol>
        </section>
      )}
    </main>
  );
}
