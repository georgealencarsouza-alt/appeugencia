# App para eugências

SaaS com IA para pequenas agências de conteúdo. O fluxo completo:

**briefing do cliente → pauta com referências → aprovação → kit de gravação → checagem dos takes → primeiro corte editado no estilo das referências → aprovação final**

O diferencial está na ponte entre a eugência e o cliente final: o cliente recebe links
(sem login) para responder o briefing, aprovar roteiros e gravar seguindo um kit; os takes
chegam padronizados, o que torna a edição automática viável.

## Estrutura

| Pasta | O que é | Status |
|---|---|---|
| [`primeiro-corte/`](primeiro-corte/) | Motor de edição: checa os takes, alinha com o roteiro e gera o primeiro corte no estilo da referência | Testado com takes e referências reais (celular e WhatsApp) |
| [`app/`](app/) | Aplicação web: clientes, estilo, roteiro, kit de gravação com teleprompter, checagem, primeiro corte e aprovação pelo link | Fluxo completo funcionando localmente; briefing e roteiro com IA ainda não |

Cada pasta tem seu próprio README com instalação e uso.
