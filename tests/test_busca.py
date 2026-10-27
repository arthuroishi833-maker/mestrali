"""Testes de core/busca.py e da conversão de datas. Rodar com: pytest"""

from datetime import date

from core.busca import filtrar_orcamentos, normalizar
from core.formato import data_do_banco

LISTA = [
    {"cliente_nome": "Maria Conceição", "data": date(2026, 10, 9)},
    {"cliente_nome": "João Pedro", "data": date(2026, 10, 1)},
    {"cliente_nome": "MARIANA Souza", "data": date(2026, 9, 20)},
]


def nomes(lista):
    return [o["cliente_nome"] for o in lista]


def test_normalizar():
    assert normalizar("  João  CONCEIÇÃO ") == "joao conceicao"


def test_sem_filtro_devolve_tudo_na_mesma_ordem():
    assert filtrar_orcamentos(LISTA) == LISTA


def test_busca_por_nome_ignora_acento_e_maiuscula():
    assert nomes(filtrar_orcamentos(LISTA, "maria")) == ["Maria Conceição", "MARIANA Souza"]
    assert nomes(filtrar_orcamentos(LISTA, "conceicao")) == ["Maria Conceição"]
    assert nomes(filtrar_orcamentos(LISTA, "JOAO")) == ["João Pedro"]
    assert filtrar_orcamentos(LISTA, "zzz") == []


def test_busca_com_simbolos_e_tratada_como_texto_comum():
    assert filtrar_orcamentos(LISTA, "%' or 1=1 --") == []


def test_filtro_por_periodo_inclui_as_pontas():
    assert nomes(filtrar_orcamentos(LISTA, data_inicial=date(2026, 10, 1))) == [
        "Maria Conceição", "João Pedro"]
    assert nomes(filtrar_orcamentos(LISTA, data_final=date(2026, 10, 1))) == [
        "João Pedro", "MARIANA Souza"]
    assert nomes(filtrar_orcamentos(
        LISTA, data_inicial=date(2026, 9, 21), data_final=date(2026, 10, 8))) == ["João Pedro"]


def test_nome_e_periodo_juntos():
    assert nomes(filtrar_orcamentos(LISTA, "maria", data_inicial=date(2026, 10, 1))) == [
        "Maria Conceição"]


def test_data_do_banco_converte_para_o_horario_de_brasilia():
    # 01:30 em UTC do dia 10 ainda é dia 9 em Brasília (UTC-3)
    assert data_do_banco("2026-10-10T01:30:00+00:00") == date(2026, 10, 9)
    assert data_do_banco("2026-10-09T15:00:00.12345+00:00") == date(2026, 10, 9)
    assert data_do_banco("2026-10-09T15:00:00Z") == date(2026, 10, 9)
