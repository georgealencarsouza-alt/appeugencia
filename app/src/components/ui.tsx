import Link from "next/link";
import { STATUS } from "@/lib/status";

export const botao = {
  primario:
    "inline-flex items-center justify-center gap-2 rounded-full bg-petroleo px-5 py-2.5 font-bold text-white transition-colors hover:bg-petroleo-escuro disabled:cursor-not-allowed disabled:opacity-50",
  secundario:
    "inline-flex items-center justify-center gap-2 rounded-full border border-tinta/20 bg-cartao px-5 py-2.5 font-bold text-tinta transition-colors hover:border-tinta/50 disabled:opacity-50",
  rec: "inline-flex items-center justify-center gap-2 rounded-full bg-rec px-5 py-2.5 font-bold text-white transition-colors hover:brightness-95 disabled:opacity-50",
  texto: "font-bold text-petroleo underline decoration-petroleo/30 underline-offset-4 hover:decoration-petroleo",
};

export const campo =
  "w-full rounded-xl border border-linha bg-cartao px-4 py-3 text-tinta placeholder:text-tinta-3 focus:border-petroleo focus:outline-none";

const TONS = {
  neutro: "bg-tinta/5 text-tinta-2",
  info: "bg-petroleo-claro text-petroleo",
  progresso: "bg-marca-claro text-tinta",
  alerta: "bg-rec-claro text-rec",
  ok: "bg-ok-claro text-ok",
};

export function Status({ status }: { status: string }) {
  const s = STATUS[status] ?? { rotulo: status, tom: "neutro" as const };
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-sm font-bold ${TONS[s.tom]}`}>
      {s.tom === "progresso" && <span className="size-2 animate-pulse rounded-full bg-tinta/60" />}
      {s.rotulo}
    </span>
  );
}

export function Cabecalho({ voltar, titulo, children }: { voltar?: { href: string; rotulo: string }; titulo: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="mb-8">
      {voltar && (
        <Link href={voltar.href} className="mb-3 inline-block text-tinta-2 hover:text-tinta">
          ‹ {voltar.rotulo}
        </Link>
      )}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-4xl font-extrabold sm:text-5xl">{titulo}</h1>
        {children}
      </div>
    </div>
  );
}

export function Secao({ titulo, descricao, acao, children }: { titulo: string; descricao?: string; acao?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-cartao border border-linha bg-cartao p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">{titulo}</h2>
          {descricao && <p className="mt-1 max-w-prose text-tinta-2">{descricao}</p>}
        </div>
        {acao}
      </div>
      {children}
    </section>
  );
}

export function duracao(s: number | undefined | null): string {
  if (s == null) return "–";
  const m = Math.floor(s / 60);
  const seg = Math.round(s % 60);
  return m ? `${m}min ${String(seg).padStart(2, "0")}s` : `${seg}s`;
}

export function tamanho(bytes: number): string {
  if (bytes > 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  return `${Math.max(1, Math.round(bytes / 1024 ** 2))} MB`;
}
