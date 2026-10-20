/** Rótulos e cores dos status, compartilhados entre as telas. */
export const STATUS: Record<string, { rotulo: string; tom: "neutro" | "info" | "alerta" | "ok" | "progresso" }> = {
  rascunho: { rotulo: "Rascunho", tom: "neutro" },
  gravacao: { rotulo: "Aguardando gravação", tom: "info" },
  checando: { rotulo: "Checando takes", tom: "progresso" },
  regravar: { rotulo: "Precisa regravar", tom: "alerta" },
  takes_recebidos: { rotulo: "Takes recebidos", tom: "info" },
  editando: { rotulo: "Editando", tom: "progresso" },
  corte_pronto: { rotulo: "Corte pronto", tom: "info" },
  em_aprovacao: { rotulo: "Com o cliente", tom: "info" },
  ajustes: { rotulo: "Pediu ajustes", tom: "alerta" },
  aprovado: { rotulo: "Aprovado", tom: "ok" },
};
