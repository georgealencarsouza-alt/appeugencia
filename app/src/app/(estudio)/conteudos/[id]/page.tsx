import { notFound } from "next/navigation";
import {
  comentarComoEugencia, definirTrilha, enviarParaAprovacao, gerarPrimeiroCorte, liberarGravacao,
  reabrirGravacao, rechecar, removerTake,
} from "@/app/acoes";
import { Atualizador, CopiarLink, Enviador } from "@/components/cliente";
import { EditorRoteiro } from "@/components/editor-roteiro";
import { Cabecalho, Status, botao, campo, duracao, tamanho } from "@/components/ui";
import { clientes, comentarios, conteudos, cortes, roteiroDe, takes } from "@/lib/db";
import type { RelatorioChecagem, ResumoCorte } from "@/lib/fluxo";
import { urlBase } from "@/lib/url";

export const dynamic = "force-dynamic";

const ROTULO_REMOVIDA: Record<string, [string, string]> = {
  vicio: ["vício (ahn, é, né)", "vícios (ahn, é, né)"], repeticao: ["palavra repetida", "palavras repetidas"],
  hesitacao: ["tropeço", "tropeços"], borda: ["fala fora do roteiro", "falas fora do roteiro"],
};

function Etapa({ n, titulo, ativa, children }: { n: number; titulo: string; ativa: boolean; children: React.ReactNode }) {
  return (
    <section className={`rounded-cartao border bg-cartao p-5 ${ativa ? "border-petroleo/50 shadow-[0_0_0_3px_var(--color-petroleo-claro)]" : "border-linha"}`}>
      <h2 className="mb-3 flex items-center gap-3 text-xl font-bold">
        <span className={`grid size-8 shrink-0 place-items-center rounded-full font-titulo text-base ${ativa ? "bg-petroleo text-white" : "bg-papel text-tinta-2"}`}>{n}</span>
        {titulo}
      </h2>
      {children}
    </section>
  );
}

export default async function PaginaConteudo({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const c = conteudos.obter(id);
  if (!c) notFound();
  const cliente = clientes.obter(c.cliente_id)!;
  const roteiro = roteiroDe(c);
  const listaTakes = takes.listar(id);
  const listaCortes = cortes.listar(id);
  const corte = listaCortes[0];
  const corteProntoAtual = listaCortes.find((k) => k.status === "pronto");
  const resumo = corteProntoAtual?.resumo_json ? (JSON.parse(corteProntoAtual.resumo_json) as ResumoCorte) : null;
  const checagem = c.checagem_json ? (JSON.parse(c.checagem_json) as RelatorioChecagem) : null;
  const conversa = comentarios.listar(id);
  const base = await urlBase();
  const processando = ["checando", "editando"].includes(c.status);
  const temRoteiro = roteiro.blocos.some((b) => b.texto.trim());
  const porTake = new Map(checagem?.takes.map((t) => [t.caminho, t]) ?? []);
  const usados = new Set(checagem?.frases.map((f) => f.take).filter(Boolean));

  const etapaAtiva =
    c.status === "rascunho" ? 0
      : ["gravacao", "regravar", "checando"].includes(c.status) ? 1
      : ["takes_recebidos", "editando", "corte_pronto", "ajustes"].includes(c.status) ? 2
      : 3;

  return (
    <>
      <Atualizador ativo={processando || c.status === "gravacao" || c.status === "em_aprovacao"} intervalo={processando ? 2500 : 8000} />
      <Cabecalho voltar={{ href: `/clientes/${cliente.id}`, rotulo: cliente.nome }} titulo={c.titulo}>
        <Status status={c.status} />
      </Cabecalho>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="rounded-cartao border border-linha bg-cartao p-5 sm:p-6 lg:sticky lg:top-6">
          <h2 className="mb-1 text-xl font-bold">Roteiro</h2>
          <p className="mb-4 text-tinta-2">É o que o cliente vê no teleprompter e o que a edição usa para escolher as melhores tentativas.</p>
          <EditorRoteiro key={c.atualizado_em} conteudoId={id} inicial={roteiro} bloqueado={c.status === "editando" || c.status === "aprovado"} />
        </section>

        <div className="space-y-5">
          <Etapa n={1} titulo="Gravação pelo cliente" ativa={etapaAtiva <= 1}>
            {c.status === "rascunho" ? (
              <>
                <p className="mb-4 text-tinta-2">Quando o roteiro estiver pronto, libere a gravação e envie o link. O cliente grava pelo celular, sem precisar de conta.</p>
                <form action={liberarGravacao.bind(null, id)}>
                  <button className={botao.primario} disabled={!temRoteiro}>Liberar gravação</button>
                </form>
                {!temRoteiro && <p className="mt-2 text-sm text-tinta-2">Escreva e salve o roteiro primeiro.</p>}
              </>
            ) : (
              <>
                <p className="mb-3 text-tinta-2">Envie este link ao cliente pelo WhatsApp. Ele vê o roteiro, usa o teleprompter e manda os takes por ali.</p>
                <div className="flex flex-wrap gap-2">
                  <CopiarLink url={`${base}/k/${c.token_kit}`} />
                  <a href={`/k/${c.token_kit}`} target="_blank" className={botao.secundario + " !py-1.5 text-sm"}>Abrir como cliente</a>
                </div>
              </>
            )}
          </Etapa>

          <Etapa n={2} titulo="Takes e checagem" ativa={etapaAtiva === 1 || etapaAtiva === 2}>
            {c.status === "checando" && <p className="mb-3 rounded-xl bg-marca-claro px-4 py-3">Transcrevendo e conferindo os takes contra o roteiro…</p>}
            {c.checagem_erro && <p className="mb-3 rounded-xl bg-rec-claro px-4 py-3 text-rec">A checagem falhou: {c.checagem_erro}</p>}

            {checagem && c.status !== "checando" && (
              <div className="mb-4">
                <ul className="space-y-1.5">
                  {checagem.frases.map((f, i) => (
                    <li key={i} className="flex gap-2.5">
                      <span aria-hidden className={`mt-1.5 size-2.5 shrink-0 rounded-full ${!f.encontrada ? "bg-rec" : f.similaridade < 0.8 ? "bg-marca" : "bg-ok"}`} />
                      <span className={!f.encontrada ? "text-rec" : ""}>
                        {f.texto}
                        {!f.encontrada && <b> (não gravada)</b>}
                        {f.encontrada && f.tentativas > 1 && <span className="text-tinta-2"> · {f.tentativas} tentativas, usando a melhor</span>}
                        {f.encontrada && f.faltando.length > 0 && f.similaridade < 0.8 && <span className="text-tinta-2"> · faltou: {f.faltando.slice(0, 4).join(", ")}</span>}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {listaTakes.length > 0 ? (
              <ul className="mb-4 space-y-2">
                {listaTakes.map((t) => {
                  const chk = porTake.get(t.id);
                  return (
                    <li key={t.id} className="flex gap-3 rounded-xl bg-papel p-2 pr-3">
                      <a href={`/api/midia/take/${t.id}`} target="_blank" className="shrink-0" aria-label={`Assistir ${t.nome_original}`}><img src={`/api/midia/take/${t.id}?capa`} alt="" className="moldura w-12 object-cover" /></a>
                      <div className="min-w-0 flex-1 text-sm">
                        <p className="truncate font-bold">{t.nome_original}</p>
                        <p className="text-tinta-2">
                          {[chk && duracao(chk.duracao), tamanho(t.tamanho), chk?.resolucao, checagem && !usados.has(t.id) ? "não usado no corte" : null].filter(Boolean).join(" · ")}
                        </p>
                        {chk?.problemas.map((p, i) => (
                          <p key={i} className={p.gravidade === "regravar" ? "text-rec" : "text-tinta-2"}>{p.mensagem}</p>
                        ))}
                      </div>
                      <form action={removerTake.bind(null, t.id)} className="self-start">
                        <button className="text-sm text-tinta-2 hover:text-rec" disabled={processando}>Remover</button>
                      </form>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mb-4 text-tinta-2">{c.status === "rascunho" ? "Os takes aparecem aqui quando o cliente enviar." : "Aguardando o cliente enviar os takes."}</p>
            )}

            <div className="flex flex-wrap items-start gap-3">
              <Enviador rota={`/api/conteudos/${id}/takes`} rotulo="Enviar takes você mesmo" />
              {listaTakes.length > 0 && !processando && (
                <form action={rechecar.bind(null, id)}><button className={botao.texto + " py-2.5"}>Checar de novo</button></form>
              )}
            </div>
          </Etapa>

          <Etapa n={3} titulo="Primeiro corte" ativa={etapaAtiva === 2}>
            <form className="mb-4 flex flex-wrap items-center gap-2" action={async (fd: FormData) => {
              "use server";
              await definirTrilha(id, String(fd.get("trilha")) as "nenhuma" | "calmo" | "animado");
            }}>
              <span className="font-bold">Música:</span>
              {(["nenhuma", "calmo", "animado"] as const).map((t) => (
                <button key={t} name="trilha" value={t} disabled={processando}
                  className={`rounded-full border px-3 py-1 text-sm font-bold ${c.trilha === t ? "border-petroleo bg-petroleo text-white" : "border-linha hover:border-tinta/40"}`}>
                  {{ nenhuma: "Sem música", calmo: "Trilha calma", animado: "Trilha animada" }[t]}
                </button>
              ))}
            </form>

            {c.status === "editando" && (
              <p className="mb-4 rounded-xl bg-marca-claro px-4 py-3">Editando. Costuma levar de 30 segundos a 2 minutos.</p>
            )}
            {corte?.status === "erro" && <p className="mb-4 rounded-xl bg-rec-claro px-4 py-3 text-rec">A edição falhou: {corte.erro}</p>}

            {corteProntoAtual && (
              <div className="mb-4 flex flex-col gap-4 sm:flex-row">
                <video key={corteProntoAtual.id} src={`/api/midia/corte/${corteProntoAtual.id}`} poster={`/api/midia/corte/${corteProntoAtual.id}?capa`} controls playsInline preload="metadata"
                  className="moldura w-full max-w-[15rem] self-center sm:self-start" />
                {resumo && (
                  <div className="text-tinta-2">
                    <p className="font-titulo text-3xl font-extrabold text-tinta">
                      {duracao(resumo.duracao_bruta_s)} <span className="text-tinta-3">→</span> {duracao(resumo.duracao_final_s)}
                    </p>
                    <p className="mb-3">de gravação bruta para vídeo final, em {duracao(resumo.tempo_processamento_s)}</p>
                    <ul className="space-y-1">
                      <li>{resumo.trechos} trechos montados</li>
                      <li>{resumo.frases_encontradas} de {resumo.frases_total} frases do roteiro</li>
                      {Object.entries(resumo.removidas ?? {}).map(([k, n]) => <li key={k}>{n} {(ROTULO_REMOVIDA[k] ?? [k, k])[n === 1 ? 0 : 1]} {n === 1 ? "removido" : "removidos"}</li>)}
                    </ul>
                    <a href={`/api/midia/corte/${corteProntoAtual.id}?baixar`} className={botao.texto + " mt-3 inline-block"}>Baixar vídeo</a>
                  </div>
                )}
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <form action={gerarPrimeiroCorte.bind(null, id)}>
                <button className={corteProntoAtual ? botao.secundario : botao.primario} disabled={processando || !listaTakes.length || c.status === "aprovado"}>
                  {corteProntoAtual ? "Gerar de novo" : "Gerar primeiro corte"}
                </button>
              </form>
              {corteProntoAtual && ["corte_pronto", "ajustes", "takes_recebidos"].includes(c.status) && (
                <form action={enviarParaAprovacao.bind(null, id)}>
                  <button className={botao.primario}>Enviar para aprovação</button>
                </form>
              )}
            </div>
            {!listaTakes.length && <p className="mt-2 text-sm text-tinta-2">Precisa de pelo menos um take.</p>}
            {checagem?.status === "regravar" && listaTakes.length > 0 && (
              <p className="mt-2 text-sm text-tinta-2">A checagem pediu regravação, mas dá para gerar um corte com o que já chegou.</p>
            )}
          </Etapa>

          <Etapa n={4} titulo="Aprovação do cliente" ativa={etapaAtiva === 3 || c.status === "ajustes"}>
            {["em_aprovacao", "ajustes", "aprovado"].includes(c.status) ? (
              <div className="mb-4 flex flex-wrap gap-2">
                <CopiarLink url={`${base}/a/${c.token_aprovacao}`} />
                <a href={`/a/${c.token_aprovacao}`} target="_blank" className={botao.secundario + " !py-1.5 text-sm"}>Abrir como cliente</a>
              </div>
            ) : (
              <p className="mb-4 text-tinta-2">Depois de revisar o corte, envie para o cliente aprovar pelo link.</p>
            )}

            {conversa.length > 0 && (
              <ol className="mb-4 space-y-2">
                {conversa.map((m) => (
                  <li key={m.id} className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${m.autor === "cliente" ? "bg-papel" : "ml-auto bg-petroleo-claro"}`}>
                    <p className="text-xs font-bold text-tinta-2">
                      {m.autor === "cliente" ? cliente.nome : "Você"}
                      {m.tipo === "aprovacao" && " aprovou"}
                      {m.tipo === "ajuste" && " pediu ajuste"}
                    </p>
                    <p className="whitespace-pre-wrap">{m.texto}</p>
                  </li>
                ))}
              </ol>
            )}

            {c.status !== "rascunho" && (
              <form action={comentarComoEugencia.bind(null, id)} className="flex gap-2">
                <input name="texto" className={campo + " !py-2"} placeholder="Escrever para o cliente" maxLength={2000} />
                <button className={botao.secundario + " !py-2"}>Enviar</button>
              </form>
            )}
            {c.status === "ajustes" && (
              <form action={reabrirGravacao.bind(null, id)} className="mt-3">
                <button className={botao.texto}>Pedir nova gravação ao cliente</button>
              </form>
            )}
          </Etapa>
        </div>
      </div>
    </>
  );
}
