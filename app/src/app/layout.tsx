import type { Metadata, Viewport } from "next";
import "@fontsource-variable/bricolage-grotesque/opsz.css";
import "@fontsource/atkinson-hyperlegible/latin-400.css";
import "@fontsource/atkinson-hyperlegible/latin-700.css";
import "@fontsource/atkinson-hyperlegible/latin-ext-400.css";
import "@fontsource/atkinson-hyperlegible/latin-ext-700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "appeugência",
  description: "Do roteiro ao primeiro corte, com o cliente gravando do próprio celular.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f1f2ee" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="antialiased">{children}</body>
    </html>
  );
}
