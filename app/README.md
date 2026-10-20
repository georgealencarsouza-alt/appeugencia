# App (eugência + cliente final)

Aplicação web do fluxo completo:

| Quem | Tela | O que faz |
|---|---|---|
| Eugência | `/` | Clientes e o que está esperando ação |
| Eugência | `/clientes/:id` | Conteúdos do cliente, referências e estilo de edição (medido + ajustável) |
| Eugência | `/conteudos/:id` | Roteiro em blocos, link do kit, takes com checagem, primeiro corte, aprovação e conversa |
| Cliente final | `/k/:token` | Kit de gravação no celular, sem login: roteiro, dicas, **gravação com teleprompter no navegador** ou envio da galeria, resultado da checagem |
| Cliente final | `/a/:token` | Vídeo para aprovar ou pedir ajuste |

O trabalho pesado (transcrição, checagem, edição, análise de referências) é feito pelo motor em
[`../primeiro-corte`](../primeiro-corte), chamado em segundo plano. As execuções entram numa fila e
rodam uma de cada vez; as telas se atualizam sozinhas enquanto algo processa.

## Rodar

Requer Node 20+ e o motor instalado (veja o README dele: Python, FFmpeg e `baixar_modelos.py`).

```bash
npm install
cp .env.example .env      # ajuste se o motor ou o Python estiverem em outro lugar
npm run build && npm start   # http://localhost:3000
```

Para testar no celular na mesma rede, abra `http://IP-DO-COMPUTADOR:3000` e defina `APP_URL`
com esse endereço. A gravação pelo navegador exige HTTPS fora do `localhost`; sem HTTPS, o cliente
ainda pode enviar vídeos da galeria.

## Teste de ponta a ponta

Com o app rodando, simula a eugência no computador e o cliente no celular (Playwright):

```bash
python testes/e2e.py --take take.mp4 --referencia referencia.mp4 --saida prints/
```

## Decisões do MVP (e o que muda antes de ir ao ar)

- **SQLite + arquivos no disco** (`dados/`). Para produção: Supabase (Postgres) e armazenamento de
  objetos (R2/S3) com upload direto do celular por URL assinada.
- **Sem login no lado da eugência.** Os links do cliente usam tokens longos e aleatórios. Antes de ir
  ao ar: autenticação e separação por agência (multi-tenant).
- **Fila em memória.** Para produção: fila persistente e um worker separado para o motor.
- **Estilo**: sem `ANTHROPIC_API_KEY`, a análise mede ritmo, zoom e cor, e a legenda fica no padrão
  até a eugência ajustar. Os ajustes manuais ficam guardados à parte e sobrevivem a uma nova análise.
