"""Tela Financeiro: períodos, contas e o que aparece na tela."""

from datetime import date
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core.financeiro import limites_utc, periodo, totais

HOJE = date(2026, 10, 14)


def orc(total_itens, custo_itens, mao_de_obra=0, desconto=0):
    return {"desconto_tipo": "valor", "desconto_valor": desconto, "mao_de_obra": mao_de_obra,
            "itens": [{"nome": "x", "tipo": "peca", "quantidade": 1, "custo_unitario": custo_itens, "preco_unitario": total_itens}]}


def test_periodos_e_navegacao():
    assert periodo("Dia", 0, HOJE)[:2] == (date(2026, 10, 14), date(2026, 10, 15))
    assert periodo("Dia", -1, HOJE)[2].startswith("Ontem")
    assert periodo("Mês", 0, HOJE)[:2] == (date(2026, 10, 1), date(2026, 11, 1))
    assert periodo("Mês", 0, HOJE)[2] == "Outubro de 2026"
    # Voltar meses atravessa o ano sem erro.
    assert periodo("Mês", -10, HOJE)[:2] == (date(2025, 12, 1), date(2026, 1, 1))
    assert periodo("Ano", -1, HOJE)[:2] == (date(2025, 1, 1), date(2026, 1, 1))


def test_limites_em_utc_respeitam_o_horario_de_brasilia():
    inicio, fim = limites_utc(date(2026, 10, 14), date(2026, 10, 15))
    assert inicio.startswith("2026-10-14T03:00:00") and fim.startswith("2026-10-15T03:00:00")


def test_totais_lucro_e_prejuizo():
    pago = dict(orc(710, 230), situacao="pago")
    a_receber = dict(orc(100, 20, mao_de_obra=50, desconto=10), situacao="fechado")
    conta = totais([pago, a_receber])
    assert conta == {"custo": 250.0, "ganho": 850.0, "lucro": 600.0, "quantidade": 2,
                     "a_receber": 140.0, "ganho_pago": 710.0, "lucro_a_receber": 120.0, "lucro_pago": 480.0}
    prejuizo = totais([orc(100, 180)])
    assert prejuizo["lucro"] == -80.0
    assert totais([]) == {"custo": 0.0, "ganho": 0.0, "lucro": 0.0, "quantidade": 0,
                          "a_receber": 0.0, "ganho_pago": 0.0, "lucro_a_receber": 0.0, "lucro_pago": 0.0}


def test_data_de_fechamento_segue_a_situacao():
    from core.situacao import data_de_fechamento
    assert data_de_fechamento("aberto", "2026-10-01T10:00:00+00:00") is None
    assert data_de_fechamento("pago", "2026-10-01T10:00:00+00:00") == "2026-10-01T10:00:00+00:00"   # mantém a 1ª data
    assert data_de_fechamento("fechado", None).startswith("20")


def _tela():
    from telas import financeiro
    financeiro.mostrar()


def _abrir(fechados):
    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.formato.hoje_brasil", return_value=HOJE), \
         patch("telas.financeiro.hoje_brasil", return_value=HOJE), \
         patch("core.db.listar_fechados", return_value=fechados) as listar:
        at = AppTest.from_function(_tela, default_timeout=30)
        at.run()
        return at, listar


def textos(at):
    return " ".join(m.value for m in at.markdown)


def test_mes_e_o_padrao_e_mostra_o_lucro():
    at, listar = _abrir([orc(710, 230)])
    assert not at.exception
    assert "Lucro do mês: R\\$ 480,00" in textos(at)
    assert "Outubro de 2026" in textos(at)
    inicio, fim = listar.call_args.args[1:]
    assert inicio.startswith("2026-10-01") and fim.startswith("2026-11-01")


def test_prejuizo_aparece_em_vermelho():
    at, _ = _abrir([orc(100, 180)])
    assert ":red[Prejuízo do mês: R\\$ 80,00]" in textos(at)


def test_periodo_vazio_mostra_aviso_e_zeros():
    at, _ = _abrir([])
    assert any("Nenhum orçamento fechado neste mês" in i.value for i in at.info)
    assert "Lucro do mês: R\\$ 0,00" in textos(at)


def test_trocar_para_dia_e_ano_muda_o_texto_e_o_periodo():
    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("telas.financeiro.hoje_brasil", return_value=HOJE), \
         patch("core.db.listar_fechados", return_value=[orc(710, 230)]) as listar:
        at = AppTest.from_function(_tela, default_timeout=30)
        at.run()
        at.get("button_group")[0].set_value("Dia").run()
        assert "Lucro do dia" in textos(at)
        assert listar.call_args.args[1].startswith("2026-10-14")
        at.get("button_group")[0].set_value("Ano").run()
        assert "Lucro do ano" in textos(at)
        # Voltar um ano.
        at.button(key="fin_anterior").click().run()
        assert listar.call_args.args[1].startswith("2025-01-01")
