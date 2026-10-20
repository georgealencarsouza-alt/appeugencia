"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { botao } from "./ui";

/** Atualiza a página a cada poucos segundos enquanto algo estiver processando. */
export function Atualizador({ ativo, intervalo = 3000 }: { ativo: boolean; intervalo?: number }) {
  const router = useRouter();
  useEffect(() => {
    if (!ativo) return;
    const t = setInterval(() => router.refresh(), intervalo);
    return () => clearInterval(t);
  }, [ativo, intervalo, router]);
  return null;
}

export function CopiarLink({ url, rotulo = "Copiar link" }: { url: string; rotulo?: string }) {
  const [copiado, setCopiado] = useState(false);
  return (
    <div className="flex min-w-0 flex-1 items-center gap-2 rounded-full border border-linha bg-papel py-1 pl-4 pr-1">
      <span className="min-w-0 flex-1 truncate text-sm text-tinta-2">{url}</span>
      <button
        type="button"
        className={botao.primario + " !px-4 !py-1.5 text-sm"}
        onClick={async () => {
          await navigator.clipboard.writeText(url);
          setCopiado(true);
          setTimeout(() => setCopiado(false), 2000);
        }}
      >
        {copiado ? "Copiado" : rotulo}
      </button>
    </div>
  );
}

type EstadoEnvio = { nome: string; progresso: number; erro?: string; pronto?: boolean };

/**
 * Envia vídeos direto (sem multipart) para a rota informada, um por vez, com barra de progresso.
 * Usa XMLHttpRequest porque fetch ainda não informa progresso de envio.
 */
export function Enviador({
  rota, rotulo, ajuda, grande = false, aoTerminar,
}: { rota: string; rotulo: string; ajuda?: string; grande?: boolean; aoTerminar?: () => void }) {
  const router = useRouter();
  const entrada = useRef<HTMLInputElement>(null);
  const [envios, setEnvios] = useState<EstadoEnvio[]>([]);
  const enviando = envios.some((e) => !e.pronto && !e.erro);

  function enviarUm(arquivo: File, i: number): Promise<void> {
    return new Promise((resolve) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", rota);
      xhr.setRequestHeader("x-nome", encodeURIComponent(arquivo.name));
      xhr.setRequestHeader("content-type", arquivo.type || "application/octet-stream");
      xhr.upload.onprogress = (ev) => {
        if (ev.lengthComputable) setEnvios((l) => l.map((e, j) => (j === i ? { ...e, progresso: ev.loaded / ev.total } : e)));
      };
      xhr.onload = () => {
        let erro: string | undefined;
        if (xhr.status >= 300) {
          try { erro = JSON.parse(xhr.responseText).erro; } catch { erro = "Não foi possível enviar"; }
        }
        setEnvios((l) => l.map((e, j) => (j === i ? { ...e, progresso: 1, pronto: !erro, erro } : e)));
        resolve();
      };
      xhr.onerror = () => {
        setEnvios((l) => l.map((e, j) => (j === i ? { ...e, erro: "A conexão caiu. Tente enviar de novo." } : e)));
        resolve();
      };
      xhr.send(arquivo);
    });
  }

  async function escolher(lista: FileList | null) {
    if (!lista?.length) return;
    const arquivos = Array.from(lista);
    const base = envios.length;
    setEnvios((l) => [...l, ...arquivos.map((a) => ({ nome: a.name, progresso: 0 }))]);
    for (let k = 0; k < arquivos.length; k++) await enviarUm(arquivos[k], base + k);
    if (entrada.current) entrada.current.value = "";
    aoTerminar?.();
    router.refresh();
  }

  return (
    <div>
      <input ref={entrada} type="file" accept="video/*" multiple className="sr-only" id={`enviar-${rota}`}
        onChange={(e) => escolher(e.target.files)} disabled={enviando} />
      <label htmlFor={`enviar-${rota}`}
        className={`${grande ? botao.rec + " w-full !py-4 text-lg" : botao.secundario} cursor-pointer ${enviando ? "pointer-events-none opacity-60" : ""}`}>
        {enviando ? "Enviando…" : rotulo}
      </label>
      {ajuda && <p className="mt-2 text-sm text-tinta-2">{ajuda}</p>}
      {envios.length > 0 && (
        <ul className="mt-3 space-y-2" aria-live="polite">
          {envios.map((e, i) => (
            <li key={i} className="rounded-xl bg-papel px-3 py-2 text-sm">
              <div className="flex justify-between gap-3">
                <span className="truncate">{e.nome}</span>
                <span className={e.erro ? "text-rec" : "text-tinta-2"}>
                  {e.erro ? "falhou" : e.pronto ? "enviado" : `${Math.round(e.progresso * 100)}%`}
                </span>
              </div>
              {!e.pronto && !e.erro && (
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-linha">
                  <div className="h-full bg-petroleo transition-[width]" style={{ width: `${e.progresso * 100}%` }} />
                </div>
              )}
              {e.erro && <p className="mt-1 text-rec">{e.erro}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
