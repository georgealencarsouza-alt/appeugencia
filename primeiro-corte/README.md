# Motor do primeiro corte

Recebe o **roteiro aprovado**, os **takes gravados pelo cliente** e uma **ficha de estilo**
(extraída das referências do cliente) e devolve um **primeiro corte** em 9:16, pronto para a
eugência revisar.

É a parte mais arriscada do produto, por isso veio antes do app: se o primeiro corte não
economizar tempo de edição de verdade, o resto não importa.

## O que ele faz

1. **Transcreve** cada take com tempo por palavra (modelo local, sem custo por minuto e sem
   mandar o vídeo do cliente para terceiros).
2. **Checa** os takes: som baixo ou estourado, imagem escura, vídeo na horizontal, rosto fora do
   quadro e, principalmente, **se todas as frases do roteiro foram ditas**. As mensagens são
   escritas para o cliente final ("Faltou gravar a frase: ...").
3. **Alinha** a fala com o roteiro: para cada frase, acha todas as tentativas, escolhe a melhor (em
   empate, a mais recente), corta falsos começos, "ahn", "é", palavra repetida, tropeços e
   pausas longas.
4. **Monta** o plano de edição (`plano.json`): trechos, zooms, legendas e textos na tela.
5. **Renderiza** com FFmpeg: reenquadra para 9:16 centrado no rosto, punch-in ou zoom suave,
   legenda com a **grafia do roteiro** (não a da transcrição), destaque de palavras-chave,
   texto do gancho e do CTA, cor, normalização de volume e música com ducking.

E, separadamente, **extrai a ficha de estilo** de vídeos de referência: cortes por minuto,
punch-ins (e de quanto), ritmo de fala e pausas, tom de cor. Com `ANTHROPIC_API_KEY` definida,
um modelo de visão completa o que é julgamento (estilo da legenda, texto na tela). Cada campo
da ficha diz de onde veio: `medido`, `ia`, `padrao` ou `manual`.

## Instalação

Requer Python 3.11+ e FFmpeg com libass (o padrão das distribuições Linux e do Homebrew).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/baixar_modelos.py           # ~560 MB, uma vez só
```

## Uso

```bash
# 1. Ficha de estilo a partir das referências do cliente (várias são consolidadas)
python -m motor extrair -o ficha.json ref1.mp4 ref2.mp4 ref3.mp4

# 2. O que o cliente vê logo depois de enviar os takes
python -m motor checar --roteiro roteiro.json take1.mp4 take2.mp4

# 3. Primeiro corte
python -m motor cortar --roteiro roteiro.json --ficha ficha.json -o saida/ take1.mp4 take2.mp4

# Ajustou algo no saida/plano.json (trocou um zoom, por exemplo)? Renderize de novo:
python -m motor renderizar --plano saida/plano.json -o saida/v2.mp4
```

`--ficha` também aceita os presets `equilibrado`, `dinamico` e `calmo`. `--rapido` gera uma
prévia mais leve. `--musica arquivo.mp3` coloca música de fundo (a voz abaixa a música
automaticamente); `--trilha calmo|animado` gera uma trilha original, livre de direitos.

O formato do roteiro está documentado em `motor/roteiro.py`. A ficha, campo a campo, em
`motor/ficha.py`.

## Testar sem gravar nada

```bash
python scripts/baixar_modelos.py --voz
python exemplos/gerar.py
python -m motor cortar --roteiro exemplos/saida/roteiro.json --ficha equilibrado \
  -o exemplos/saida/corte exemplos/saida/take1_vertical.mp4 exemplos/saida/take2_horizontal.mp4
python -m pytest testes
```

Os exemplos usam voz sintética e um cenário desenhado com o tempo do arquivo original impresso
na tela, para dar para ver de onde veio cada trecho.

## Estrutura

| Arquivo | Papel |
|---|---|
| `motor/ficha.py` | Ficha de estilo, presets e consolidação de várias referências |
| `motor/roteiro.py` | Roteiro aprovado e divisão em frases |
| `motor/transcricao.py` | Transcrição com tempo por palavra (provedor trocável) |
| `motor/checagem.py` | Checagem técnica dos takes e cobertura do roteiro |
| `motor/alinhamento.py` | Escolha da melhor tentativa e limpeza de vícios e pausas |
| `motor/montagem.py` | Plano de edição (EDL) |
| `motor/legendas.py` | Legendas e textos na tela (ASS) |
| `motor/render.py` | Renderização com FFmpeg |
| `motor/extracao.py` | Referência → ficha de estilo |
| `motor/pipeline.py` | Orquestração e cache de transcrição |

## Limites conhecidos (próximos passos)

- Ainda não testado com takes reais: voz sintética é limpa demais. Sotaque, ruído e fala
  embolada vão mostrar onde o alinhamento erra.
- Detecção de rosto simples (Haar): falha com rosto de lado ou pouca luz.
- Tom de cor medido é influenciado pelo cenário (parede azul "parece" estilo frio).
- Sem B-roll, transições elaboradas nem animações: ficaram fora do MVP de propósito.
- Trilhas geradas são simples (piano e pad); para música de verdade, use um arquivo com direitos
  de uso ou adicione o áudio dentro do próprio Instagram/TikTok.
