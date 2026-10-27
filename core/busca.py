"""Filtro da lista de orçamentos (por nome do cliente e por data).

O filtro roda aqui no Python, sobre a lista que o banco já devolveu só
com os orçamentos do técnico. O texto digitado na busca nunca é enviado
ao banco, então não há como usá-lo para alterar a consulta.
"""

import unicodedata


def normalizar(texto):
    """ "João  Conceição" -> "joao conceicao" (sem acentos, minúsculas)."""
    sem_acento = unicodedata.normalize("NFKD", str(texto or ""))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def filtrar_orcamentos(orcamentos, termo="", data_inicial=None, data_final=None):
    """Devolve os orçamentos que combinam com a busca.

    orcamentos: lista de dicts com "cliente_nome" e "data" (datetime.date).
    termo: parte do nome do cliente (ignora acentos e maiúsculas).
    data_inicial / data_final: limites do período, inclusive; None = sem limite.
    """
    termo = normalizar(termo)
    resultado = []
    for orcamento in orcamentos:
        if termo and termo not in normalizar(orcamento["cliente_nome"]):
            continue
        if data_inicial and orcamento["data"] < data_inicial:
            continue
        if data_final and orcamento["data"] > data_final:
            continue
        resultado.append(orcamento)
    return resultado
