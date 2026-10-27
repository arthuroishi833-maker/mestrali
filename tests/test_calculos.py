"""Testes de core/calculos.py. Rodar com: pytest"""

from core.calculos import arredondar_centavos, calcular_resumo

# 2 capacitores (custo 30, preço 90) + 1 limpeza (custo 20, preço 180)
# subtotal = 2*90 + 180 = 360     custo = 2*30 + 20 = 80
ITENS = [
    {"quantidade": 2, "custo_unitario": 30.0, "preco_unitario": 90.0},
    {"quantidade": 1, "custo_unitario": 20.0, "preco_unitario": 180.0},
]


def test_sem_desconto():
    r = calcular_resumo(ITENS, "valor", 0)
    assert r["subtotal"] == 360.00
    assert r["desconto"] == 0.00
    assert r["total"] == 360.00
    assert r["custo_total"] == 80.00
    assert r["lucro"] == 280.00
    assert r["margem"] == 77.78  # 280 / 360


def test_desconto_em_reais():
    r = calcular_resumo(ITENS, "valor", 60)
    assert r["desconto"] == 60.00
    assert r["total"] == 300.00
    assert r["lucro"] == 220.00
    assert r["margem"] == 73.33  # 220 / 300


def test_desconto_em_percentual():
    r = calcular_resumo(ITENS, "percentual", 10)
    assert r["desconto"] == 36.00
    assert r["total"] == 324.00
    assert r["lucro"] == 244.00


def test_desconto_nunca_deixa_total_negativo():
    r = calcular_resumo(ITENS, "valor", 9999)
    assert r["desconto"] == 360.00
    assert r["total"] == 0.00
    assert r["lucro"] == -80.00
    assert r["margem"] == 0.00  # sem venda, não há margem para calcular

    r = calcular_resumo(ITENS, "percentual", 150)
    assert r["total"] == 0.00


def test_desconto_negativo_e_ignorado():
    assert calcular_resumo(ITENS, "valor", -50)["total"] == 360.00


def test_prejuizo_da_margem_negativa():
    itens = [{"quantidade": 1, "custo_unitario": 100.0, "preco_unitario": 80.0}]
    r = calcular_resumo(itens, "valor", 0)
    assert r["lucro"] == -20.00
    assert r["margem"] == -25.00


def test_sem_itens():
    r = calcular_resumo([], "valor", 0)
    assert r == {
        "itens": 0.0, "mao_de_obra": 0.0,
        "subtotal": 0.0, "desconto": 0.0, "total": 0.0,
        "custo_total": 0.0, "lucro": 0.0, "margem": 0.0,
    }


def test_centavos_sem_erro_de_arredondamento():
    # 3 x 33,33 = 99,99 ; 15% de 99,99 = 14,9985 -> 15,00
    itens = [{"quantidade": 3, "custo_unitario": 0.10, "preco_unitario": 33.33}]
    r = calcular_resumo(itens, "percentual", 15)
    assert r["subtotal"] == 99.99
    assert r["desconto"] == 15.00
    assert r["total"] == 84.99
    assert r["custo_total"] == 0.30


def test_mao_de_obra_soma_no_total_e_no_lucro():
    r = calcular_resumo(ITENS, "valor", 0, mao_de_obra=150)
    assert r["itens"] == 360.00
    assert r["mao_de_obra"] == 150.00
    assert r["subtotal"] == 510.00
    assert r["total"] == 510.00
    assert r["custo_total"] == 80.00
    assert r["lucro"] == 430.00


def test_desconto_percentual_incide_sobre_itens_mais_mao_de_obra():
    r = calcular_resumo(ITENS, "percentual", 10, mao_de_obra=140)
    assert r["desconto"] == 50.00   # 10% de (360 + 140)
    assert r["total"] == 450.00


def test_so_mao_de_obra_sem_itens():
    r = calcular_resumo([], "valor", 0, mao_de_obra=200)
    assert r["total"] == 200.00 and r["lucro"] == 200.00 and r["margem"] == 100.00


def test_mao_de_obra_negativa_e_ignorada():
    assert calcular_resumo(ITENS, "valor", 0, mao_de_obra=-10)["total"] == 360.00


def test_arredondamento_unico_de_dinheiro():
    # Meio centavo sobe, sem o erro do float (round(2.675, 2) daria 2.67).
    assert arredondar_centavos(2.675) == 2.68
    assert arredondar_centavos(10.994) == 10.99
    assert arredondar_centavos(10.995) == 11.0
    assert arredondar_centavos(0.004) == 0.0
    assert arredondar_centavos("19.999") == 20.0
    assert arredondar_centavos(0) == 0.0


def test_valores_com_mais_de_duas_casas_contam_como_centavos():
    # A conta com 10,994 tem de ser a mesma conta com 10,99: é o que vai para o banco.
    cru = calcular_resumo([{"quantidade": 3, "preco_unitario": 10.994, "custo_unitario": 1.006}], "valor", 0.004, 0.004)
    limpo = calcular_resumo([{"quantidade": 3, "preco_unitario": 10.99, "custo_unitario": 1.01}], "valor", 0.0, 0.0)
    assert cru == limpo
    assert cru["total"] == 32.97 and cru["custo_total"] == 3.03


def test_desconto_percentual_com_tres_casas_usa_duas():
    assert calcular_resumo(ITENS, "percentual", 12.345) == calcular_resumo(ITENS, "percentual", 12.35)
