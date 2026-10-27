"""Formatação de valores e datas para mostrar na tela e no PDF."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def hoje_brasil():
    """Data de hoje no horário de Brasília (o servidor pode estar em outro fuso)."""
    return datetime.now(FUSO_BRASIL).date()


def formatar_reais(valor):
    """1234.5 -> "R$ 1.234,56" (padrão brasileiro: ponto no milhar, vírgula nos centavos)."""
    texto = f"{float(valor):,.2f}"  # padrão americano: "1,234.50"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def escapar_md(texto):
    """Neutraliza os símbolos de formatação (Markdown) em textos digitados.

    As telas interpretam * _ [ ] ( ) etc. como formatação. Sem isto, um nome
    de cliente como "[clique](http://site)" viraria um link de verdade.
    """
    return re.sub(r"([\\`*_{}\[\]()<>#+\-.!|~$:&])", r"\\\1", str(texto or ""))


def data_do_banco(texto):
    """Converte a data/hora que vem do banco (texto, em UTC) para a data no Brasil.

    Ex.: "2026-10-10T01:30:00.123+00:00" -> date(2026, 10, 9)
    """
    texto = re.sub(r"\.\d+", "", str(texto))   # tira os milissegundos
    texto = texto.replace("Z", "+00:00")         # "Z" é outro jeito de escrever UTC
    return datetime.fromisoformat(texto).astimezone(FUSO_BRASIL).date()
