"""Onde ficam os arquivos que mudam (fichas e aparências).

Sem configuração, ficam ao lado do código. No Railway, crie um Volume (por exemplo em /dados)
e defina a variável DATA_DIR=/dados: assim as fichas e imagens sobrevivem aos reinícios.
"""
import os
import shutil
from pathlib import Path

CODIGO = Path(__file__).parent
DADOS = Path(os.environ.get("DATA_DIR", CODIGO))


def preparar():
    DADOS.mkdir(parents=True, exist_ok=True)
    (DADOS / "aparencias").mkdir(exist_ok=True)
    fichas = DADOS / "fichas.json"
    if not fichas.exists():
        modelo = CODIGO / "fichas.json"
        if modelo.exists():
            shutil.copy(modelo, fichas)
        else:
            fichas.write_text("{}", encoding="utf-8")
