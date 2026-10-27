"""Testes do atendimento: contatos de suporte e a tela Ajuda."""

from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core import suporte


def com_contatos(whatsapp=suporte.PREENCHER, email=suporte.PREENCHER, horario=suporte.PREENCHER):
    return patch.multiple(
        "core.suporte", SUPORTE_WHATSAPP=whatsapp, SUPORTE_EMAIL=email, SUPORTE_HORARIO=horario)


# ---------------------------------------------------------------- contatos
def test_sem_preencher_nao_ha_contato_nem_link():
    with com_contatos():
        assert suporte.contato_configurado() is False
        assert suporte.link_do_whatsapp() == ""
        assert suporte.email_do_suporte() == ""
        assert suporte.horario_do_suporte() == ""


def test_whatsapp_valido_gera_link_com_codigo_do_brasil():
    with com_contatos(whatsapp="27999990000"):
        assert suporte.contato_configurado() is True
        assert suporte.link_do_whatsapp().startswith("https://wa.me/5527999990000?text=")
        assert suporte.whatsapp_formatado() == "(27) 99999-0000"


def test_whatsapp_fora_do_padrao_e_ignorado_em_vez_de_gerar_link_errado():
    for ruim in ["(27) 99999-0000", "999990000", "279999900001", "abc", ""]:
        with com_contatos(whatsapp=ruim):
            assert suporte.link_do_whatsapp() == "", ruim


def test_email_valido_e_invalido():
    with com_contatos(email="Suporte@Exemplo.com.br"):
        assert suporte.email_do_suporte() == "suporte@exemplo.com.br"
        assert suporte.contato_configurado() is True
    with com_contatos(email="nao-e-email"):
        assert suporte.email_do_suporte() == ""


# -------------------------------------------------------------- perguntas
def test_antes_do_login_so_aparecem_as_duvidas_de_acesso():
    todas = suporte.perguntas()
    de_acesso = suporte.perguntas(antes_do_login=True)
    assert 0 < len(de_acesso) < len(todas)
    assert any("Esqueci minha senha" in p for p, _ in de_acesso)
    assert not any("PDF" in p for p, _ in de_acesso)


def test_respostas_nao_prometem_o_que_o_sistema_nao_faz():
    texto = " ".join(r for _, r in suporte.perguntas()).lower()
    assert "não anexa" in texto                     # o WhatsApp não anexa o PDF
    assert "itens e valores não mudam" in texto     # orçamento salvo não é editável
    for proibido in ["nota fiscal", "pagamento online", "estoque"]:   # fora do escopo
        assert proibido not in texto


def test_regras_de_senha_da_ajuda_batem_com_a_validacao():
    from core.validacao import ESPECIAIS_DA_SENHA, MIN_SENHA

    resposta = next(r for p, r in suporte.perguntas() if "senha o sistema aceita" in p)
    assert f"{MIN_SENHA} caracteres" in resposta
    for simbolo in ESPECIAIS_DA_SENHA:
        assert simbolo in resposta


# ------------------------------------------------------------------- telas
def _tela_ajuda():
    from telas import ajuda

    ajuda.mostrar()


def _tela_ajuda_inicio():
    from telas import ajuda

    ajuda.mostrar_antes_do_login()


def test_tela_ajuda_sem_contato_configurado():
    with com_contatos():
        at = AppTest.from_function(_tela_ajuda, default_timeout=30).run()
        assert not at.exception
        assert at.header[0].value == "Ajuda"
        assert any("ainda está sendo configurado" in i.value for i in at.info)
        assert len(at.expander) == len(suporte.perguntas())
        assert not at.get("link_button")


def test_tela_ajuda_com_contato_mostra_o_whatsapp():
    with com_contatos(whatsapp="27999990000", email="suporte@exemplo.com.br", horario="Seg a sex, 8h às 18h"):
        at = AppTest.from_function(_tela_ajuda, default_timeout=30).run()
        assert not at.exception and not at.info
        botao = at.get("link_button")[0]
        assert botao.proto.url.startswith("https://wa.me/5527999990000?text=")
        assert any("suporte@exemplo.com.br" in m.value for m in at.markdown)
        assert any("8h às 18h" in c.value for c in at.caption)


def test_ajuda_da_pagina_inicial_nao_quebra():
    with com_contatos():
        at = AppTest.from_function(_tela_ajuda_inicio, default_timeout=30).run()
        assert not at.exception
        assert any("Esqueci minha senha" in m.value for m in at.markdown)
