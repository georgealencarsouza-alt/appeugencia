import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Atualizador, Enviador } from "@/components/cliente";
import { Gravador } from "@/components/gravador";
import { clientes, conteudos, roteiroDe, takes } from "@/lib/db";
import type { RelatorioChecagem } from "@/lib/fluxo";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Seu roteiro para gravar", robots: { index: false } };

const ROTULO_BLOCO = { gancho: "Comece com", desenvolvimento: "Depois fale", cta: "Termine com" } as const;

const DICAS = [
  "Fique de frente para uma janela ou luz. Luz atrás de você escurece o rosto.",
  "Celular em pé, na altura dos olhos, apoiado em algo firme.",
  "Escolha um lugar silencioso. Desligue ventilador e TV.",
  "Errou uma frase? Respire e fale ela de novo. A edição escolhe a melhor tentativa.",
];

export default async function KitDeGravacao({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const c = conteudos.porTokenKit(token);
  if (!c || c.status === "rascunho") notFound();
  const cliente = clientes.obter(c.cliente_id)!;
  const roteiro = roteiroDe(c);
  const blocos = roteiro.blocos.filter((b) => b.texto.trim());
  const enviados = takes.listar(c.id);
  const checagem = c.checagem_json ? (JSON.parse(c.checagem_json) as RelatorioChecagem) : null;
  const aberto = ["gravacao", "regravar", "takes_recebidos", "checando"].includes(c.status);
  const rota = `/api/kit/${token}/takes`;

  const pedidos = checagem
    ? [
        ...checagem.problemas.filter((p) => p.gravidade === "regravar").map((p) => p.mensagem),
        ...checagem.takes.flatMap((t) => t.problemas.filter((p) => p.gravidade === "regravar").map((p) => p.mensagem)),
      ]
    : [];
  const sugestoes = checagem
    ? [...new Set([...checagem.problemas, ...checagem.takes.flatMap((t) => t.problemas)].filter((p) => p.gravidade === "atencao").map((p) => p.mensagem))]
    : [];

  return (
    <main className="mx-auto max-w-xl px-4 pb-16 pt-6">
      <Atualizador ativo={c.status === "checando"} intervalo={2500} />
      <p className="mb-1 text-tinta-2">Gravação para {cliente.nome}</p>
      <h1 className="mb-6 text-4xl font-extrabold">{roteiro.titulo}</h1>

      {/* resultado da última checagem: o que o cliente mais precisa saber, logo no topo */}
      {c.status === "checando" && (
        <div className="mb-6 rounded-2xl bg-marca-claro p-5" role="status">
          <p className="text-lg font-bold">Conferindo o que você enviou…</p>
          <p className="text-tinta-2">Leva alguns segundos. Pode deixar esta página aberta.</p>
        </div>
      )}
      {c.status === "regravar" && pedidos.length > 0 && (
        <div className="mb-6 rounded-2xl bg-rec-claro p-5" role="alert">
          <p className="mb-2 text-lg font-bold text-rec">Falta pouco. Precisamos que você grave de novo:</p>
          <ul className="list-disc space-y-1 pl-5">{pedidos.map((m, i) => <li key={i}>{m}</li>)}</ul>
          <p className="mt-2 text-tinta-2">Não precisa apagar nada. É só gravar e enviar mais um take.</p>
        </div>
      )}
      {c.status === "takes_recebidos" && checagem && (
        <div className="mb-6 rounded-2xl bg-ok-claro p-5" role="status">
          <p className="text-lg font-bold text-ok">Recebemos tudo. Obrigado!</p>
          <p className="text-tinta-2">A agência vai editar e te mandar o vídeo para aprovar.</p>
          {sugestoes.length > 0 && (
            <p className="mt-2 text-sm text-tinta-2">Para as próximas: {sugestoes.slice(0, 2).join(" ")}</p>
          )}
        </div>
      )}
      {!aberto && (
        <div className="mb-6 rounded-2xl bg-cartao p-5">
          <p className="text-lg font-bold">Gravação encerrada</p>
          <p className="text-tinta-2">A agência já está com os seus vídeos. Se precisar de mais alguma coisa, ela te avisa.</p>
        </div>
      )}

      <ol className="space-y-8">
        <li>
          <h2 className="mb-3 flex items-center gap-3 text-2xl font-bold">
            <span className="grid size-9 place-items-center rounded-full bg-tinta font-titulo text-lg text-white">1</span>Leia o roteiro
          </h2>
          <div className="space-y-4 rounded-2xl bg-cartao p-5">
            {blocos.map((b, i) => (
              <div key={i}>
                <p className="mb-1 text-sm font-bold text-tinta-2">{ROTULO_BLOCO[b.tipo]}</p>
                <p className="text-xl leading-relaxed">{b.texto}</p>
              </div>
            ))}
          </div>
          <p className="mt-2 text-tinta-2">Não precisa decorar: na hora de gravar, o texto passa na tela.</p>
        </li>

        <li>
          <h2 className="mb-3 flex items-center gap-3 text-2xl font-bold">
            <span className="grid size-9 place-items-center rounded-full bg-tinta font-titulo text-lg text-white">2</span>Prepare o lugar
          </h2>
          <ul className="space-y-2">
            {DICAS.map((d) => (
              <li key={d} className="flex gap-3 text-lg"><span aria-hidden className="mt-2.5 size-2 shrink-0 rounded-full bg-marca" />{d}</li>
            ))}
          </ul>
        </li>

        <li>
          <h2 className="mb-3 flex items-center gap-3 text-2xl font-bold">
            <span className="grid size-9 place-items-center rounded-full bg-tinta font-titulo text-lg text-white">3</span>Grave e envie
          </h2>
          {aberto ? (
            <div className="space-y-5">
              <Gravador rota={rota} blocos={blocos} />
              <div className="rounded-2xl border border-dashed border-tinta/25 p-4">
                <p className="mb-3 font-bold">Prefere gravar com a câmera do celular?</p>
                <Enviador rota={rota} rotulo="Escolher vídeos da galeria" ajuda="Pode enviar vários de uma vez. Vale gravar uma parte em cada vídeo." />
              </div>
            </div>
          ) : (
            <p className="text-tinta-2">Esta gravação já foi encerrada.</p>
          )}
          {enviados.length > 0 && (
            <p className="mt-4 text-tinta-2">
              {enviados.length === 1 ? "1 vídeo enviado" : `${enviados.length} vídeos enviados`}. Pode enviar mais se quiser.
            </p>
          )}
        </li>
      </ol>
    </main>
  );
}
