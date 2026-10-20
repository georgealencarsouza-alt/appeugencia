import Link from "next/link";

export default function LayoutEstudio({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <header className="border-b border-linha bg-papel/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2 font-titulo text-xl font-extrabold tracking-tight">
            <span className="ponto-rec !animate-none" aria-hidden />
            appeugência
          </Link>
          <nav className="text-tinta-2">
            <Link href="/" className="hover:text-tinta">Clientes</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>
    </div>
  );
}
