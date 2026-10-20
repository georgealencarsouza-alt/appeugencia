import "server-only";
import { spawn } from "node:child_process";
import path from "node:path";

export const MOTOR_DIR = path.resolve(process.env.MOTOR_DIR ?? "../primeiro-corte");
const PYTHON = process.env.PYTHON ?? "python3";

export type ResultadoMotor = { codigo: number; saida: string; erro: string };

declare global {
  // eslint-disable-next-line no-var
  var __filaMotor: Promise<unknown> | undefined;
}

/**
 * Roda o motor em Python. As execuções entram numa fila e rodam uma de cada vez:
 * transcrição e renderização usam toda a CPU, e rodar duas juntas deixa as duas lentas.
 */
export function rodarMotor(args: string[], limiteMs = 20 * 60 * 1000): Promise<ResultadoMotor> {
  const tarefa = () =>
    new Promise<ResultadoMotor>((resolve) => {
      const proc = spawn(PYTHON, ["-m", "motor", ...args], { cwd: MOTOR_DIR, env: process.env });
      let saida = "";
      let erro = "";
      const timer = setTimeout(() => proc.kill("SIGKILL"), limiteMs);
      proc.stdout.on("data", (d) => (saida += d));
      proc.stderr.on("data", (d) => (erro += d));
      proc.on("error", (e) => {
        clearTimeout(timer);
        resolve({ codigo: -1, saida, erro: `Não consegui iniciar o motor (${PYTHON}): ${e.message}` });
      });
      proc.on("close", (codigo) => {
        clearTimeout(timer);
        resolve({ codigo: codigo ?? -1, saida, erro });
      });
    });
  const anterior = globalThis.__filaMotor ?? Promise.resolve();
  const atual = anterior.then(tarefa, tarefa);
  globalThis.__filaMotor = atual.catch(() => undefined);
  return atual;
}

/** Última linha que é um objeto JSON (o motor imprime logs antes). */
export function jsonDaSaida<T>(saida: string): T | null {
  const inicio = saida.indexOf("{");
  if (inicio < 0) return null;
  for (let i = inicio; i >= 0 && i < saida.length; i = saida.indexOf("{", i + 1)) {
    try {
      return JSON.parse(saida.slice(i)) as T;
    } catch {
      /* tenta a próxima chave */
    }
  }
  return null;
}

/** Mensagem curta para mostrar na tela quando o motor falha. */
export function resumoErro(r: ResultadoMotor): string {
  const linhas = (r.erro || r.saida).trim().split("\n").filter(Boolean);
  const util = linhas.reverse().find((l) => /error|erro|falha|not found|não/i.test(l)) ?? linhas[0] ?? "erro desconhecido";
  return util.slice(0, 400);
}
