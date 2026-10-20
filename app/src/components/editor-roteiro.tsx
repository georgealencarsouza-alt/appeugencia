"use client";

import { useState, useTransition } from "react";
import { salvarRoteiro } from "@/app/acoes";
import type { BlocoRoteiro, Roteiro } from "@/lib/db";
import { botao, campo } from "./ui";

const TIPOS: { valor: BlocoRoteiro["tipo"]; rotulo: string; dica: string }[] = [
  { valor: "gancho", rotulo: "Gancho", dica: "A frase que segura o dedo nos 3 primeiros segundos." },
  { valor: "desenvolvimento", rotulo: "Desenvolvimento", dica: "O conteúdo em si. Frases curtas são mais fáceis de gravar." },
  { valor: "cta", rotulo: "Chamada para ação", dica: "O que a pessoa deve fazer depois de assistir." },
];

const PALAVRAS_POR_SEGUNDO = 2.6;

export function EditorRoteiro({ conteudoId, inicial, bloqueado }: { conteudoId: string; inicial: Roteiro; bloqueado: boolean }) {
  const [roteiro, setRoteiro] = useState<Roteiro>(inicial);
  const [chaves, setChaves] = useState(inicial.palavras_chave.join(", "));
  const [mensagem, setMensagem] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const [alterado, setAlterado] = useState(false);
  const [salvando, iniciar] = useTransition();

  const palavras = roteiro.blocos.reduce((n, b) => n + b.texto.split(/\s+/).filter(Boolean).length, 0);

  function mudarBloco(i: number, campos: Partial<BlocoRoteiro>) {
    setRoteiro((r) => ({ ...r, blocos: r.blocos.map((b, j) => (j === i ? { ...b, ...campos } : b)) }));
    setAlterado(true);
    setMensagem(null);
  }

  function mover(i: number, delta: number) {
    setRoteiro((r) => {
      const blocos = [...r.blocos];
      const [b] = blocos.splice(i, 1);
      blocos.splice(i + delta, 0, b);
      return { ...r, blocos };
    });
    setAlterado(true);
  }

  function salvar() {
    iniciar(async () => {
      const res = await salvarRoteiro(conteudoId, {
        ...roteiro,
        palavras_chave: chaves.split(",").map((p) => p.trim()).filter(Boolean),
      });
      setMensagem(res.ok ? { tipo: "ok", texto: "Roteiro salvo." } : { tipo: "erro", texto: res.erro ?? "Não foi possível salvar." });
      if (res.ok) setAlterado(false);
    });
  }

  return (
    <div>
      <fieldset disabled={bloqueado || salvando} className="space-y-4">
        <div>
          <label htmlFor="titulo" className="mb-1 block font-bold">Título interno</label>
          <input id="titulo" className={campo} value={roteiro.titulo}
            onChange={(e) => { setRoteiro({ ...roteiro, titulo: e.target.value }); setAlterado(true); }} />
        </div>

        <ol className="space-y-3">
          {roteiro.blocos.map((b, i) => {
            const tipo = TIPOS.find((t) => t.valor === b.tipo)!;
            return (
              <li key={i} className="rounded-xl border border-linha bg-papel p-4">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <select aria-label="Tipo do bloco" value={b.tipo} onChange={(e) => mudarBloco(i, { tipo: e.target.value as BlocoRoteiro["tipo"] })}
                    className="rounded-lg border border-linha bg-cartao px-2 py-1 font-bold">
                    {TIPOS.map((t) => <option key={t.valor} value={t.valor}>{t.rotulo}</option>)}
                  </select>
                  <div className="flex gap-1 text-sm text-tinta-2">
                    <button type="button" onClick={() => mover(i, -1)} disabled={i === 0} className="rounded px-2 py-1 hover:bg-cartao disabled:opacity-30" aria-label="Subir bloco">↑</button>
                    <button type="button" onClick={() => mover(i, 1)} disabled={i === roteiro.blocos.length - 1} className="rounded px-2 py-1 hover:bg-cartao disabled:opacity-30" aria-label="Descer bloco">↓</button>
                    <button type="button" onClick={() => { setRoteiro({ ...roteiro, blocos: roteiro.blocos.filter((_, j) => j !== i) }); setAlterado(true); }}
                      disabled={roteiro.blocos.length === 1} className="rounded px-2 py-1 hover:bg-cartao hover:text-rec disabled:opacity-30">Remover</button>
                  </div>
                </div>
                <textarea aria-label={`Fala do bloco ${tipo.rotulo}`} rows={Math.max(b.tipo === "desenvolvimento" ? 4 : 2, Math.ceil(b.texto.length / 48) + 1)}
                  className={campo + " resize-y text-lg leading-relaxed"} placeholder={tipo.dica}
                  value={b.texto} onChange={(e) => mudarBloco(i, { texto: e.target.value })} />
                <input aria-label="Texto na tela" className={campo + " mt-2 !py-2 text-sm"}
                  placeholder={b.tipo === "desenvolvimento" ? "Título na tela (opcional)" : "Texto que aparece na tela (opcional)"}
                  value={b.texto_tela ?? ""} onChange={(e) => mudarBloco(i, { texto_tela: e.target.value })} />
              </li>
            );
          })}
        </ol>

        <button type="button" className={botao.texto}
          onClick={() => { setRoteiro({ ...roteiro, blocos: [...roteiro.blocos, { id: `bloco${Date.now()}`, tipo: "desenvolvimento", texto: "" }] }); setAlterado(true); }}>
          Adicionar bloco
        </button>

        <div>
          <label htmlFor="chaves" className="mb-1 block font-bold">Palavras-chave</label>
          <input id="chaves" className={campo} value={chaves} placeholder="Ex.: preço, valor"
            onChange={(e) => { setChaves(e.target.value); setAlterado(true); }} />
          <p className="mt-1 text-sm text-tinta-2">Separadas por vírgula. Ganham destaque na legenda e puxam o zoom.</p>
        </div>
      </fieldset>

      <div className="mt-5 flex flex-wrap items-center gap-4">
        {!bloqueado && (
          <button type="button" onClick={salvar} disabled={salvando || !alterado} className={botao.primario}>
            {salvando ? "Salvando…" : "Salvar roteiro"}
          </button>
        )}
        <span className="text-tinta-2">≈ {Math.max(1, Math.round(palavras / PALAVRAS_POR_SEGUNDO))} s de fala, {palavras} palavras</span>
        {mensagem && <span className={mensagem.tipo === "ok" ? "text-ok" : "text-rec"} role="status">{mensagem.texto}</span>}
        {alterado && !mensagem && !bloqueado && <span className="text-tinta-2">Alterações não salvas</span>}
      </div>
    </div>
  );
}
