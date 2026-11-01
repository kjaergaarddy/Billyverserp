"""Repositório de aparências: cada personagem (de qualquer obra) só pode ser usado por um jogador.

Tolera erro de digitação, acento, maiúscula e nome incompleto:
  "sasuk uchiha" / "Naruto"  ≈  "Sasuke" / "naruto"
Três respostas possíveis em `checar`:
  - "livre":    ninguém usa
  - "igual":    é praticamente o mesmo (recusa direto)
  - "parecido": talvez seja o mesmo (o bot pergunta "é o mesmo?" com botões)
"""
from __future__ import annotations
import difflib
import io
import json
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

import caminhos

RAIZ = caminhos.DADOS / "aparencias"
INDICE = RAIZ / "indice.json"
LADO = 512                      # as imagens são guardadas em quadrado de 512px

LIMITE_IGUAL = 0.93
LIMITE_PARECIDO = 0.80


def normalizar(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    txt = re.sub(r"[^a-z0-9]+", " ", txt.lower())
    return " ".join(txt.split())


def similaridade(a: str, b: str) -> float:
    """0 a 1. Considera erro de letra, ordem das palavras e nome incompleto."""
    a, b = normalizar(a), normalizar(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    direta = difflib.SequenceMatcher(None, a, b).ratio()
    ordenada = difflib.SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split()))).ratio()
    melhor = max(direta, ordenada)
    ta, tb = set(a.split()), set(b.split())
    curto, longo = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if curto and curto <= longo:
        melhor = max(melhor, 0.9)                 # "Sasuke" dentro de "Sasuke Uchiha"
    else:                                         # palavra com erro dentro do nome maior
        casadas = sum(1 for p in curto if difflib.get_close_matches(p, longo, n=1, cutoff=0.8))
        if curto and casadas == len(curto):
            melhor = max(melhor, 0.88)
    return melhor


def carregar() -> list[dict]:
    return json.loads(INDICE.read_text(encoding="utf-8")) if INDICE.exists() else []


def _salvar(registros: list[dict]):
    RAIZ.mkdir(parents=True, exist_ok=True)
    INDICE.write_text(json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8")


def checar(personagem: str, obra: str, ignorar_dono: int | None = None) -> tuple[str, list[dict]]:
    """Devolve (veredito, registros parecidos)."""
    achados = []
    for r in carregar():
        if ignorar_dono is not None and r["dono_id"] == ignorar_dono:
            continue
        sp = similaridade(personagem, r["personagem"])
        so = similaridade(obra, r["obra"])
        if so >= LIMITE_PARECIDO and sp >= LIMITE_PARECIDO:
            achados.append({**r, "pontos": round(min(sp, so), 2), "_sp": sp, "_so": so})
    achados.sort(key=lambda r: r["pontos"], reverse=True)
    if not achados:
        return "livre", []
    topo = achados[0]
    if topo["_sp"] >= LIMITE_IGUAL and topo["_so"] >= LIMITE_IGUAL:
        return "igual", achados
    return "parecido", achados


def registrar(personagem: str, obra: str, imagem: bytes, dono_id: int) -> dict:
    """Guarda a imagem (recortada em quadrado) e cria o registro. Já deve ter passado por `checar`."""
    registros = carregar()
    novo_id = max([r["id"] for r in registros], default=0) + 1
    RAIZ.mkdir(parents=True, exist_ok=True)
    img = ImageOps.fit(Image.open(io.BytesIO(imagem)).convert("RGB"), (LADO, LADO), Image.LANCZOS)
    arq = f"{novo_id}.png"
    img.save(RAIZ / arq)
    reg = {"id": novo_id, "personagem": personagem.strip(), "obra": obra.strip(),
           "arquivo": arq, "dono_id": dono_id}
    registros.append(reg)
    _salvar(registros)
    return reg


def liberar(aparencia_id: int):
    """Narrador libera uma aparência (o dono deixa de usar)."""
    _salvar([r for r in carregar() if r["id"] != aparencia_id])


def imagem_de(aparencia_id: int | None) -> Image.Image | None:
    if not aparencia_id:
        return None
    for r in carregar():
        if r["id"] == aparencia_id:
            caminho = RAIZ / r["arquivo"]
            return Image.open(caminho).convert("RGB") if caminho.exists() else None
    return None
