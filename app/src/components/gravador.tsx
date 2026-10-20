"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { BlocoRoteiro } from "@/lib/db";
import { botao } from "./ui";

/**
 * Gravação no navegador com o roteiro passando perto da câmera, como um teleprompter.
 * O cliente não precisa instalar nada: grava, revê e envia na mesma tela.
 */

const VELOCIDADES = [
  { rotulo: "Devagar", pxs: 22 },
  { rotulo: "Normal", pxs: 34 },
  { rotulo: "Rápido", pxs: 48 },
];

function tipoSuportado(): string {
  const candidatos = ["video/mp4;codecs=avc1,mp4a", "video/mp4", "video/webm;codecs=vp9,opus", "video/webm"];
  return candidatos.find((t) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t)) ?? "";
}

export function Gravador({ rota, blocos }: { rota: string; blocos: BlocoRoteiro[] }) {
  const router = useRouter();
  const [aberto, setAberto] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [fase, setFase] = useState<"preparando" | "pronto" | "gravando" | "revendo" | "enviando" | "enviado">("preparando");
  const [progresso, setProgresso] = useState(0);
  const [velocidade, setVelocidade] = useState(1);
  const [segundos, setSegundos] = useState(0);
  const [gravacao, setGravacao] = useState<{ blob: Blob; url: string } | null>(null);
  const [contagem, setContagem] = useState(0);

  const video = useRef<HTMLVideoElement>(null);
  const fluxo = useRef<MediaStream | null>(null);
  const gravador = useRef<MediaRecorder | null>(null);
  const pedacos = useRef<Blob[]>([]);
  const rolagem = useRef<HTMLDivElement>(null);
  const animacao = useRef<number>(0);

  async function abrir() {
    setErro(null);
    setAberto(true);
    setFase("preparando");
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1080 }, height: { ideal: 1920 }, frameRate: { ideal: 30 } },
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      fluxo.current = s;
      if (video.current) {
        video.current.srcObject = s;
        await video.current.play().catch(() => undefined);
      }
      setFase("pronto");
    } catch {
      setErro("Não conseguimos acessar a câmera. Libere câmera e microfone para este site, ou grave com a câmera do celular e envie o arquivo.");
      setAberto(false);
    }
  }

  function fechar() {
    cancelAnimationFrame(animacao.current);
    gravador.current?.state === "recording" && gravador.current.stop();
    fluxo.current?.getTracks().forEach((t) => t.stop());
    fluxo.current = null;
    if (gravacao) URL.revokeObjectURL(gravacao.url);
    setGravacao(null);
    setAberto(false);
  }

  useEffect(() => () => fluxo.current?.getTracks().forEach((t) => t.stop()), []);

  function rolar(inicio: number, ultimo: number) {
    const el = rolagem.current;
    if (!el) return;
    const agora = performance.now();
    el.scrollTop += ((agora - ultimo) / 1000) * VELOCIDADES[velocidadeRef.current].pxs;
    setSegundos(Math.floor((agora - inicio) / 1000));
    animacao.current = requestAnimationFrame(() => rolar(inicio, agora));
  }
  const velocidadeRef = useRef(velocidade);
  velocidadeRef.current = velocidade;

  function comecar() {
    if (!fluxo.current) return;
    setContagem(3);
    let n = 3;
    const t = setInterval(() => {
      n -= 1;
      setContagem(n);
      if (n > 0) return;
      clearInterval(t);
      pedacos.current = [];
      const tipo = tipoSuportado();
      const rec = new MediaRecorder(fluxo.current!, tipo ? { mimeType: tipo, videoBitsPerSecond: 8_000_000 } : undefined);
      rec.ondataavailable = (e) => e.data.size && pedacos.current.push(e.data);
      rec.onstop = () => {
        const blob = new Blob(pedacos.current, { type: rec.mimeType || "video/webm" });
        setGravacao({ blob, url: URL.createObjectURL(blob) });
        setFase("revendo");
      };
      gravador.current = rec;
      rec.start(1000);
      setFase("gravando");
      if (rolagem.current) rolagem.current.scrollTop = 0;
      const inicio = performance.now();
      animacao.current = requestAnimationFrame(() => rolar(inicio, inicio));
    }, 1000);
  }

  function parar() {
    cancelAnimationFrame(animacao.current);
    gravador.current?.stop();
  }

  function regravar() {
    if (gravacao) URL.revokeObjectURL(gravacao.url);
    setGravacao(null);
    setSegundos(0);
    setFase("pronto");
  }

  function enviar() {
    if (!gravacao) return;
    setFase("enviando");
    setProgresso(0);
    const ext = gravacao.blob.type.includes("mp4") ? "mp4" : "webm";
    const xhr = new XMLHttpRequest();
    xhr.open("POST", rota);
    xhr.setRequestHeader("x-nome", encodeURIComponent(`gravacao-${new Date().toISOString().slice(11, 19).replace(/:/g, "")}.${ext}`));
    xhr.setRequestHeader("content-type", gravacao.blob.type || "video/webm");
    xhr.upload.onprogress = (e) => e.lengthComputable && setProgresso(e.loaded / e.total);
    xhr.onload = () => {
      if (xhr.status >= 300) {
        let msg = "Não foi possível enviar.";
        try { msg = JSON.parse(xhr.responseText).erro ?? msg; } catch { /* resposta sem JSON */ }
        setErro(msg);
        setFase("revendo");
        return;
      }
      setFase("enviado");
      fechar();
      router.refresh();
    };
    xhr.onerror = () => { setErro("A conexão caiu. Tente enviar de novo."); setFase("revendo"); };
    xhr.send(gravacao.blob);
  }

  return (
    <>
      <button type="button" onClick={abrir} className={botao.rec + " w-full !py-4 text-lg"}>
        <span className="ponto-rec !bg-white" aria-hidden /> Gravar com o roteiro na tela
      </button>
      {erro && !aberto && <p className="mt-2 text-rec">{erro}</p>}

      {aberto && (
        <div className="fixed inset-0 z-50 flex flex-col bg-black text-white" role="dialog" aria-modal="true" aria-label="Gravação">
          <video ref={video} muted playsInline className={`absolute inset-0 h-full w-full -scale-x-100 object-cover ${fase === "revendo" || fase === "enviando" ? "invisible" : ""}`} />
          {gravacao && (fase === "revendo" || fase === "enviando") && (
            <video src={gravacao.url} controls playsInline className="absolute inset-0 h-full w-full bg-black object-contain" />
          )}

          {/* roteiro no topo, perto da câmera, para o olhar não fugir da lente */}
          {(fase === "pronto" || fase === "gravando") && (
            <div ref={rolagem} className="relative z-10 max-h-[38dvh] overflow-hidden bg-gradient-to-b from-black/85 via-black/70 to-transparent px-6 pb-10 pt-[max(env(safe-area-inset-top),1rem)]">
              <div className="space-y-6 pb-[30dvh] text-center text-[1.65rem] font-bold leading-snug">
                {blocos.map((b, i) => <p key={i}>{b.texto}</p>)}
                <p className="text-white/50">Fim. Pode parar a gravação.</p>
              </div>
            </div>
          )}

          {contagem > 0 && (
            <div className="absolute inset-0 z-20 grid place-items-center font-titulo text-[9rem] font-extrabold" aria-live="assertive">{contagem}</div>
          )}

          <div className="relative z-10 mt-auto space-y-3 bg-gradient-to-t from-black/90 to-transparent px-5 pb-[max(env(safe-area-inset-bottom),1.25rem)] pt-10">
            {erro && <p className="rounded-xl bg-rec px-4 py-2 text-white">{erro}</p>}
            {fase === "preparando" && <p className="text-center">Abrindo a câmera…</p>}

            {fase === "pronto" && (
              <>
                <div className="flex justify-center gap-2" role="radiogroup" aria-label="Velocidade do texto">
                  {VELOCIDADES.map((v, i) => (
                    <button key={v.rotulo} type="button" role="radio" aria-checked={velocidade === i} onClick={() => setVelocidade(i)}
                      className={`rounded-full px-4 py-1.5 text-sm font-bold ${velocidade === i ? "bg-white text-black" : "bg-white/15"}`}>{v.rotulo}</button>
                  ))}
                </div>
                <p className="text-center text-sm text-white/80">Errou? Respire e fale a frase de novo. A edição usa a melhor tentativa.</p>
                <div className="flex items-center justify-between">
                  <button type="button" onClick={fechar} className="px-3 py-2 font-bold">Cancelar</button>
                  <button type="button" onClick={comecar} disabled={contagem > 0} aria-label="Começar a gravar"
                    className="grid size-20 place-items-center rounded-full border-4 border-white"><span className="size-14 rounded-full bg-rec" /></button>
                  <span className="w-20" />
                </div>
              </>
            )}

            {fase === "gravando" && (
              <div className="flex items-center justify-between">
                <span className="flex w-20 items-center gap-2 font-bold"><span className="ponto-rec" />{Math.floor(segundos / 60)}:{String(segundos % 60).padStart(2, "0")}</span>
                <button type="button" onClick={parar} aria-label="Parar gravação"
                  className="grid size-20 place-items-center rounded-full border-4 border-white"><span className="size-8 rounded-md bg-rec" /></button>
                <span className="w-20" />
              </div>
            )}

            {(fase === "revendo" || fase === "enviando") && (
              <div className="grid grid-cols-2 gap-3">
                <button type="button" onClick={regravar} disabled={fase === "enviando"} className="rounded-full bg-white/15 py-3.5 font-bold">Gravar de novo</button>
                <button type="button" onClick={enviar} disabled={fase === "enviando"} className="rounded-full bg-white py-3.5 font-bold text-black">
                  {fase === "enviando" ? `Enviando ${Math.round(progresso * 100)}%` : "Enviar este take"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
