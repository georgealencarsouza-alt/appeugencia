import Link from "next/link";
import { criarCliente } from "@/app/acoes";
import { Status, botao, campo } from "@/components/ui";
import { clientes, conteudos } from "@/lib/db";

export const dynamic = "force-dynamic";

const PEDEM_ACAO = new Set(["takes_recebidos", "corte_pronto", "ajustes", "regravar"]);

export default function Painel() {
  const lista = clientes.listar();
  const recentes = conteudos.recentes(30);
  const pendentes = recentes.filter((c) => PEDEM_ACAO.has(c.status));

  return (
    <div className="grid gap-10 lg:grid-cols-[1fr_22rem]">
      <div>
        <h1 className="mb-2 text-4xl font-extrabold sm:text-5xl">Clientes</h1>
        <p className="mb-8 text-tinta-2">Cada cliente tem as próprias referências, estilo de edição e conteúdos.</p>

        {lista.length === 0 ? (
          <div className="rounded-cartao border border-dashed border-tinta/25 p-8 text-tinta-2">
            Nenhum cliente ainda. Cadastre o primeiro ao lado para começar.
          </div>
        ) : (
          <ul className="divide-y divide-linha overflow-hidden rounded-cartao border border-linha bg-cartao">
            {lista.map((c) => (
              <li key={c.id}>
                <Link href={`/clientes/${c.id}`} className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-papel">
                  <div className="min-w-0">
                    <p className="truncate text-lg font-bold">{c.nome}</p>
                    <p className="truncate text-tinta-2">
                      {[c.nicho, `${c.total_conteudos} ${c.total_conteudos === 1 ? "conteúdo" : "conteúdos"}`].filter(Boolean).join(", ")}
                    </p>
                  </div>
                  <span className="shrink-0 text-sm text-tinta-2">
                    {c.ficha_status === "pronta" ? "Estilo definido" : c.ficha_status === "processando" ? "Analisando referências…" : "Sem estilo ainda"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}

        {pendentes.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-3 text-2xl font-bold">Esperando você</h2>
            <ul className="space-y-2">
              {pendentes.map((c) => (
                <li key={c.id}>
                  <Link href={`/conteudos/${c.id}`} className="flex items-center justify-between gap-3 rounded-xl border border-linha bg-cartao px-4 py-3 hover:border-tinta/40">
                    <span className="min-w-0 truncate"><b>{c.titulo}</b> <span className="text-tinta-2">· {c.cliente_nome}</span></span>
                    <Status status={c.status} />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <aside>
        <form action={criarCliente} className="sticky top-6 rounded-cartao border border-linha bg-cartao p-5">
          <h2 className="mb-4 text-xl font-bold">Novo cliente</h2>
          <label className="mb-1 block font-bold" htmlFor="nome">Nome</label>
          <input id="nome" name="nome" required maxLength={120} className={campo + " mb-4"} placeholder="Ex.: Clínica Sorriso" />
          <label className="mb-1 block font-bold" htmlFor="nicho">Nicho</label>
          <input id="nicho" name="nicho" maxLength={120} className={campo + " mb-5"} placeholder="Ex.: odontologia" />
          <button className={botao.primario + " w-full"}>Cadastrar cliente</button>
        </form>
      </aside>
    </div>
  );
}
