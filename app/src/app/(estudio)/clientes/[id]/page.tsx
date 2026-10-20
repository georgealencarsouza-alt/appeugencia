import Link from "next/link";
import { notFound } from "next/navigation";
import { criarConteudo, removerReferencia, salvarEstilo } from "@/app/acoes";
import { Atualizador, Enviador } from "@/components/cliente";
import { Cabecalho, Secao, Status, botao, campo } from "@/components/ui";
import { clientes, conteudos, referencias } from "@/lib/db";
import { descrever, fichaFinal } from "@/lib/estilo";

export const dynamic = "force-dynamic";

const ORIGEM: Record<string, string> = { medido: "medido na referência", ia: "visto pela IA", manual: "ajustado por você" };

function Opcoes({ nome, atual, opcoes }: { nome: string; atual: string; opcoes: [string, string][] }) {
  return (
    <fieldset className="mb-3">
      <legend className="mb-1.5 font-bold">{({ ritmo: "Ritmo", legenda_modo: "Legenda", legenda_caixa_alta: "Caixa alta", zoom: "Zoom", cor: "Cor" } as Record<string, string>)[nome]}</legend>
      <div className="flex flex-wrap gap-1.5">
        {opcoes.map(([v, r]) => (
          <label key={v} className="cursor-pointer">
            <input type="radio" name={nome} value={v} defaultChecked={atual === v} className="peer sr-only" />
            <span className="inline-block rounded-full border border-linha px-3 py-1 text-sm font-bold peer-checked:border-petroleo peer-checked:bg-petroleo peer-checked:text-white peer-focus-visible:outline-3 peer-focus-visible:outline-marca">{r}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default async function PaginaCliente({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cliente = clientes.obter(id);
  if (!cliente) notFound();
  const refs = referencias.listar(id);
  const lista = conteudos.doCliente(id);
  const estilo = descrever(await fichaFinal(cliente));
  const processando = cliente.ficha_status === "processando" || lista.some((c) => ["checando", "editando"].includes(c.status));

  return (
    <>
      <Atualizador ativo={processando} />
      <Cabecalho voltar={{ href: "/", rotulo: "Clientes" }} titulo={cliente.nome}>
        {cliente.nicho && <span className="text-lg text-tinta-2">{cliente.nicho}</span>}
      </Cabecalho>

      <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
        <Secao
          titulo="Conteúdos"
          descricao="Um conteúdo vai do roteiro ao vídeo aprovado."
        >
          <form action={criarConteudo.bind(null, id)} className="mb-5 flex flex-wrap gap-2">
            <input name="titulo" maxLength={140} placeholder="Título do próximo conteúdo" className={campo + " min-w-0 flex-1"} required />
            <button className={botao.primario}>Criar conteúdo</button>
          </form>
          {lista.length === 0 ? (
            <p className="text-tinta-2">Nenhum conteúdo ainda.</p>
          ) : (
            <ul className="divide-y divide-linha">
              {lista.map((c) => (
                <li key={c.id}>
                  <Link href={`/conteudos/${c.id}`} className="-mx-2 flex items-center justify-between gap-3 rounded-lg px-2 py-3 hover:bg-papel">
                    <span className="min-w-0 truncate text-lg font-bold">{c.titulo}</span>
                    <Status status={c.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Secao>

        <Secao
          titulo="Estilo de edição"
          descricao="Envie vídeos que o cliente admira. O app mede ritmo, cortes, zoom e cor e edita os próximos vídeos desse jeito."
        >
          {cliente.ficha_status === "processando" && (
            <p className="mb-4 rounded-xl bg-marca-claro px-4 py-3">Analisando as referências. Leva cerca de meio minuto por vídeo.</p>
          )}
          {cliente.ficha_status === "erro" && (
            <p className="mb-4 rounded-xl bg-rec-claro px-4 py-3 text-rec">Não consegui analisar: {cliente.ficha_erro}</p>
          )}
          {cliente.ficha_status !== "processando" && (
            <dl className="mb-4 space-y-2.5">
              {([["Ritmo", estilo.ritmo], ["Legenda", estilo.legenda], ["Zoom", estilo.zoom], ["Cor", estilo.cor]] as const).map(([rotulo, l]) => (
                <div key={rotulo} className="flex gap-3">
                  <dt className="w-20 shrink-0 text-tinta-2">{rotulo}</dt>
                  <dd>
                    <span className="font-bold">{l.texto}</span>
                    <span className={`block text-sm ${l.origem === "padrao" ? "text-rec" : "text-tinta-3"}`}>
                      {l.origem === "padrao" ? (refs.length ? "padrão: a análise não mede isso, confira" : "padrão") : ORIGEM[l.origem] ?? l.origem}
                    </span>
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <details className="mb-5 rounded-xl bg-papel p-4">
            <summary className="cursor-pointer font-bold">Ajustar estilo</summary>
            <form action={salvarEstilo.bind(null, id)} className="mt-3">
              <Opcoes nome="ritmo" atual={estilo.ritmo.valor} opcoes={[["acelerado", "Acelerado"], ["medio", "Médio"], ["calmo", "Calmo"]]} />
              <Opcoes nome="legenda_modo" atual={estilo.legenda.valor} opcoes={[["palavra", "Poucas palavras"], ["frase", "Frase inteira"], ["nenhuma", "Sem legenda"]]} />
              <Opcoes nome="legenda_caixa_alta" atual={estilo.legenda.caixa_alta ? "sim" : "nao"} opcoes={[["sim", "Sim"], ["nao", "Não"]]} />
              <Opcoes nome="zoom" atual={estilo.zoom.valor} opcoes={[["nenhum", "Sem zoom"], ["baixo", "Pouco"], ["medio", "Moderado"], ["alto", "Frequente"]]} />
              <Opcoes nome="cor" atual={estilo.cor.valor} opcoes={[["neutro", "Neutra"], ["quente", "Quente"], ["frio", "Fria"]]} />
              <button className={botao.primario + " mt-1"}>Salvar estilo</button>
            </form>
          </details>
          {refs.length > 0 && (
            <ul className="mb-4 space-y-2">
              {refs.map((r) => (
                <li key={r.id} className="flex items-center gap-3 rounded-xl bg-papel p-2 pr-3">
                  <img src={`/api/midia/referencia/${r.id}?capa`} alt="" className="moldura w-10 shrink-0 object-cover" />
                  <span className="min-w-0 flex-1 truncate text-sm">{r.nome_original}</span>
                  <form action={removerReferencia.bind(null, r.id)}>
                    <button className="text-sm text-tinta-2 hover:text-rec" aria-label={`Remover ${r.nome_original}`}>Remover</button>
                  </form>
                </li>
              ))}
            </ul>
          )}
          <Enviador rota={`/api/clientes/${id}/referencias`} rotulo="Enviar referências" ajuda="Baixe o Reels ou TikTok e envie o arquivo de vídeo." />
        </Secao>
      </div>
    </>
  );
}
