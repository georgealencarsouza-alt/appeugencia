"""Roteiro aprovado: é o que o cliente deveria ter falado.

Ter o texto de antemão é a vantagem do kit de gravação: a montagem sabe o que
procurar nos takes, escolhe a melhor tentativa de cada frase e usa o texto do
roteiro (com a grafia certa) na legenda.

Formato JSON:
{
  "titulo": "Preço x valor",
  "palavras_chave": ["preço", "valor"],
  "blocos": [
    {"id": "gancho", "tipo": "gancho", "texto": "Seu cliente só pergunta o preço?",
     "texto_tela": "SÓ PERGUNTAM O PREÇO?"},
    {"id": "corpo", "tipo": "desenvolvimento", "texto": "Então ... ."},
    {"id": "cta", "tipo": "cta", "texto": "Comente VALOR ...", "texto_tela": "Comente VALOR"}
  ]
}
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

TIPOS_BLOCO = ("gancho", "desenvolvimento", "cta")


def normalizar(palavra: str) -> str:
    """minúsculas, sem acento e sem pontuação: 'Preço?' -> 'preco'."""
    sem_acento = unicodedata.normalize("NFKD", palavra.lower())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", sem_acento)


def tokenizar(texto: str) -> list[str]:
    """Palavras como aparecem no roteiro (com acento e pontuação colada)."""
    return [p for p in texto.split() if normalizar(p)]


def dividir_frases(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.!?;])\s+", texto.strip())
    return [p.strip() for p in partes if normalizar(p)]


@dataclass
class Frase:
    """Unidade de alinhamento: a montagem procura cada frase nos takes."""
    bloco_id: str
    tipo: str
    indice: int               # posição global no roteiro
    texto: str
    palavras: list[str] = field(default_factory=list)       # como no roteiro
    normalizadas: list[str] = field(default_factory=list)   # para comparar


@dataclass
class Bloco:
    id: str
    tipo: str
    texto: str
    texto_tela: str | None = None


@dataclass
class Roteiro:
    titulo: str
    blocos: list[Bloco]
    palavras_chave: list[str] = field(default_factory=list)

    @classmethod
    def de_dict(cls, dados: dict) -> "Roteiro":
        blocos = []
        for i, b in enumerate(dados.get("blocos", [])):
            tipo = b.get("tipo", "desenvolvimento")
            if tipo not in TIPOS_BLOCO:
                raise ValueError(f"Bloco {i}: tipo '{tipo}' inválido. Use {TIPOS_BLOCO}")
            if not normalizar(b.get("texto", "")):
                raise ValueError(f"Bloco {i}: texto vazio")
            blocos.append(Bloco(id=b.get("id", f"bloco{i + 1}"), tipo=tipo, texto=b["texto"],
                                texto_tela=b.get("texto_tela")))
        if not blocos:
            raise ValueError("Roteiro sem blocos")
        return cls(titulo=dados.get("titulo", "Sem título"), blocos=blocos,
                   palavras_chave=dados.get("palavras_chave", []))

    @classmethod
    def carregar(cls, caminho: str | Path) -> "Roteiro":
        return cls.de_dict(json.loads(Path(caminho).read_text(encoding="utf-8")))

    def frases(self) -> list[Frase]:
        saida = []
        for bloco in self.blocos:
            for texto in dividir_frases(bloco.texto):
                palavras = tokenizar(texto)
                saida.append(Frase(bloco_id=bloco.id, tipo=bloco.tipo, indice=len(saida), texto=texto,
                                   palavras=palavras, normalizadas=[normalizar(p) for p in palavras]))
        return saida

    def chaves_normalizadas(self) -> set[str]:
        return {normalizar(p) for p in self.palavras_chave}

    def bloco(self, bloco_id: str) -> Bloco:
        return next(b for b in self.blocos if b.id == bloco_id)
