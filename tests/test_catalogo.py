"""Testes do catálogo inicial, dos valores em reais e da formatação."""

from core import validacao as v
from core.catalogo_inicial import AREAS, ITENS_INICIAIS, TIPOS
from core.formato import formatar_reais


def test_dinheiro_arredonda_para_centavos():
    assert v.validar_dinheiro(10.556, "Preço") == (10.56, "")


def test_dinheiro_zero_e_valido():
    assert v.validar_dinheiro(0, "Custo") == (0.0, "")


def test_dinheiro_negativo():
    assert "negativo" in v.validar_dinheiro(-0.01, "Custo")[1]


def test_dinheiro_acima_do_limite():
    assert v.validar_dinheiro(1_000_000, "Preço")[1] != ""


def test_dinheiro_nao_numerico():
    assert v.validar_dinheiro("abc", "Preço")[1] != ""
    assert v.validar_dinheiro(None, "Preço")[1] != ""
    assert v.validar_dinheiro(float("nan"), "Preço")[1] != ""


def test_tipo():
    assert v.validar_tipo("peca") == ("peca", "")
    assert v.validar_tipo("outro")[1] != ""


def test_formatar_reais():
    assert formatar_reais(0) == "R$ 0,00"
    assert formatar_reais(90) == "R$ 90,00"
    assert formatar_reais(1450.5) == "R$ 1.450,50"
    assert formatar_reais(1234567.891) == "R$ 1.234.567,89"


def test_cada_area_tem_exemplos_validos_e_que_dao_lucro():
    assert AREAS["outra"]["itens"] == []                 # quem escolhe "outra" começa vazio
    for chave, area in AREAS.items():
        assert v.validar_texto(area["nome"], "Área", obrigatorio=True)[1] == ""
        nomes = [item["nome"] for item in area["itens"]]
        assert len(nomes) == len(set(nomes)), chave      # sem item repetido na mesma área
        for item in area["itens"]:
            assert v.validar_texto(item["nome"], "Nome", obrigatorio=True)[1] == "", item
            assert item["tipo"] in TIPOS
            assert v.validar_dinheiro(item["custo"], "Custo")[1] == ""
            assert v.validar_dinheiro(item["preco"], "Preço")[1] == ""
            assert item["preco"] > item["custo"], item


def test_lista_inicial_tem_os_nove_itens_validos():
    assert len(ITENS_INICIAIS) == 9
    for item in ITENS_INICIAIS:
        assert v.validar_texto(item["nome"], "Nome", obrigatorio=True)[1] == ""
        assert item["tipo"] in TIPOS
        assert v.validar_dinheiro(item["custo"], "Custo")[1] == ""
        assert v.validar_dinheiro(item["preco"], "Preço")[1] == ""
        assert item["preco"] > item["custo"]  # exemplo precisa dar lucro
