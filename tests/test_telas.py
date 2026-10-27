"""Testes das telas, simulando cliques com o AppTest do Streamlit.

O banco e o login são substituídos por versões falsas (mock), então estes
testes não acessam o Supabase.
"""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core.catalogo_inicial import ITENS_INICIAIS

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CATALOGO = [dict(item, id=f"id{n}") for n, item in enumerate(ITENS_INICIAIS)]
PERFIL = {"nome_empresa": "Clima Frio", "telefone": "27999990000",
          "logo_base64": None, "validade_dias": 7}


ORCAMENTOS = [
    {"id": "o2", "numero": 2, "cliente_nome": "Maria Conceição", "total": 342.0,
     "criado_em": "2026-10-09T15:00:00+00:00"},
    {"id": "o1", "numero": 1, "cliente_nome": "João Pedro", "total": 150.0,
     "criado_em": "2026-10-01T12:00:00+00:00"},
]
DETALHES = {
    "id": "o2", "numero": 2, "cliente_nome": "Maria Conceição", "cliente_telefone": "27988887777",
    "equipamento": "Split 12.000 BTUs", "mao_de_obra": 0, "desconto_tipo": "percentual",
    "desconto_valor": 10, "condicoes_pagamento": "Pix", "observacoes": "", "validade_dias": 7,
    "total": 342.0, "criado_em": "2026-10-09T15:00:00+00:00",
    "itens": [
        {"nome": "Capacitor", "tipo": "peca", "quantidade": 2,
         "custo_unitario": 30, "preco_unitario": 100},
        {"nome": "Limpeza", "tipo": "mao_de_obra", "quantidade": 1,
         "custo_unitario": 20, "preco_unitario": 180},
    ],
}


def buscar_orcamento(user_id, orcamento_id):
    """Só devolve o orçamento se for do usuário "u1" (como o banco faz)."""
    if user_id == "u1" and orcamento_id == "o2":
        return dict(DETALHES)
    return None


@contextmanager
def app_logado(salvos):
    """Abre o app como se um técnico estivesse logado."""

    def salvar_orcamento(user_id, dados, itens, total):
        salvos.append({"dados": dados, "itens": itens, "total": total})
        return {"id": "orc-1", "numero": 12}

    # config_ok é simulado: os testes não podem depender de existir um .env
    # com as chaves do Supabase no computador de quem roda.
    with patch("core.supabase_client.config_ok", return_value=True), \
         patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.auth.usuario_email", return_value="tecnico@exemplo.com"), \
         patch("core.db.buscar_perfil", return_value=dict(PERFIL)), \
         patch("core.db.listar_catalogo", return_value=CATALOGO), \
         patch("core.auth.ler_marcador", return_value=True), \
         patch("core.db.migracao_pendente", return_value=False), \
         patch("core.auth.restaurar_sessao"), patch("core.auth.manter_cookie_em_dia"), \
         patch("core.db.aceitou_politica", return_value=True), \
         patch("core.db.salvar_orcamento", side_effect=salvar_orcamento), \
         patch("core.db.listar_orcamentos", return_value=[dict(o) for o in ORCAMENTOS]), \
         patch("core.db.buscar_orcamento", side_effect=buscar_orcamento):
        yield AppTest.from_file(APP, default_timeout=30)


def botao(at, rotulo):
    return next(b for b in at.button if rotulo in b.label)


def dados_da_mensagem(at):
    """O que a tela entregou à caixa de mensagem do WhatsApp (texto e endereço)."""
    import json

    componente = next(
        e for e in at.get("bidi_component") if e.proto.component_name == "mensagem_whatsapp"
    )
    return json.loads(componente.proto.json)


def erros(at):
    return [e.value for e in at.error]


def test_passo_a_passo_completo():
    salvos = []
    with app_logado(salvos) as at:
        at.run()
        assert not at.exception

        # Passo 1: não avança sem o nome do cliente
        botao(at, "Continuar").click().run()
        assert "Nome do cliente: preenchimento obrigatório." in erros(at)
        at.text_input(key="orc_w_cliente_nome").set_value(" Maria ")
        at.text_input(key="orc_w_cliente_telefone").set_value("27988887777")
        botao(at, "Continuar").click().run()

        # Passo 2: adiciona dois itens do catálogo e um avulso
        at.selectbox(key="orc_escolhido").set_value(4)          # Capacitor
        at.number_input(key="orc_nova_quantidade").set_value(2)
        botao(at, "Adicionar ao orçamento").click().run()
        at.selectbox(key="orc_escolhido").set_value(1)          # Limpeza
        at.number_input(key="orc_nova_quantidade").set_value(1)
        botao(at, "Adicionar ao orçamento").click().run()
        botao(at, "Adicionar item avulso").click().run()
        assert "Descrição: preenchimento obrigatório." in erros(at)
        at.text_input(key="orc_av_nome").set_value("Suporte")
        at.number_input(key="orc_av_preco").set_value(40.0)
        at.number_input(key="orc_av_custo").set_value(15.0)
        botao(at, "Adicionar item avulso").click().run()
        assert [i["nome"] for i in at.session_state["orc_itens"]] == [
            "Capacitor", "Limpeza / higienização", "Suporte"]
        botao(at, "Continuar").click().run()

        # Passo 3: desconto maior que 100% é recusado
        at.radio(key="orc_w_desconto_tipo").set_value("percentual")
        at.number_input(key="orc_w_desconto_valor").set_value(150.0)
        botao(at, "Continuar").click().run()
        assert "Desconto: o máximo é 100%." in erros(at)
        at.number_input(key="orc_w_desconto_valor").set_value(10.0)
        at.number_input(key="orc_w_mao_de_obra").set_value(100.0)
        botao(at, "Continuar").click().run()

        # Passo 4: revisão e salvar
        valores = {m.label: m.value for m in at.metric}
        assert valores["Total"] == "R$ 450,00"      # (2x90 + 180 + 40 + 100) - 10%
        assert valores["Lucro"] == "R$ 355,00"      # 450 - (60 + 20 + 15)
        botao(at, "Salvar orçamento").click().run()
        assert not at.exception

    assert len(salvos) == 1
    assert salvos[0]["dados"]["cliente_nome"] == "Maria"
    assert salvos[0]["dados"]["cliente_telefone"] == "27988887777"
    assert salvos[0]["total"] == 450.00
    assert salvos[0]["dados"]["mao_de_obra"] == 100.00
    assert [i["quantidade"] for i in salvos[0]["itens"]] == [2, 1, 1]
    assert at.header[0].value == "Orçamento salvo"
    assert at.session_state["orc_salvo"]["dados"]["numero"] == 12
    assert [b.label for b in at.get("download_button")] == ["1. Baixar o PDF"]
    mensagem = dados_da_mensagem(at)
    assert mensagem["inicio"] == "https://wa.me/5527988887777?text="
    assert "Olá, Maria!" in mensagem["texto"] and "R$ 450,00" in mensagem["texto"]


def test_voltar_nao_perde_o_que_foi_digitado():
    with app_logado([]) as at:
        at.run()
        at.text_input(key="orc_w_cliente_nome").set_value("João")
        botao(at, "Continuar").click().run()
        botao(at, "Voltar").click().run()
        assert at.text_input(key="orc_w_cliente_nome").value == "João"


def test_nome_com_simbolos_nao_vira_formatacao():
    with app_logado([]) as at:
        at.session_state["orc_dados"] = {
            "cliente_nome": "[clique](http://x)", "cliente_telefone": "", "equipamento": "",
            "desconto_tipo": "valor", "desconto_valor": 0.0, "observacoes": "",
            "validade_dias": 7, "mao_de_obra": 0.0, "condicoes_pagamento": "",
        }
        at.session_state["orc_itens"] = [{
            "linha": 1, "nome": "**x**", "tipo": "peca", "quantidade": 1,
            "custo_unitario": 1.0, "preco_unitario": 2.0,
        }]
        at.session_state["orc_passo"] = 3
        at.run()
        assert not at.exception
        textos = " ".join(m.value for m in at.markdown)
        assert "[clique](http://x)" not in textos
        assert "\\[clique\\]\\(http\\://x\\)" in textos


def test_orcamento_zerado_nao_avanca():
    with app_logado([]) as at:
        at.run()
        at.text_input(key="orc_w_cliente_nome").set_value("João")
        botao(at, "Continuar").click().run()   # para Itens
        botao(at, "Continuar").click().run()   # para Valores (sem itens)
        botao(at, "Continuar").click().run()   # tenta ir para Revisão
        assert any("zerado" in e for e in erros(at))


def test_remover_item():
    with app_logado([]) as at:
        at.session_state["orc_passo"] = 1
        at.run()
        botao(at, "Adicionar ao orçamento").click().run()
        at.selectbox(key="orc_escolhido").set_value(4)
        botao(at, "Adicionar ao orçamento").click().run()
        assert len(at.session_state["orc_itens"]) == 2
        botao(at, "Remover").click().run()
        assert [i["nome"] for i in at.session_state["orc_itens"]] == ["Capacitor"]
        assert not at.exception


# ------------------------------------------------------- Meus orçamentos
def _tela_historico():
    """Roda só a tela "Meus orçamentos" (o AppTest executa o corpo desta função)."""
    from telas import historico

    historico.mostrar()


@contextmanager
def historico_logado(user_id="u1"):
    with patch("core.auth.usuario_id", return_value=user_id), \
         patch("core.db.buscar_perfil", return_value=dict(PERFIL)), \
         patch("core.db.listar_orcamentos", return_value=[dict(o) for o in ORCAMENTOS]), \
         patch("core.db.buscar_orcamento", side_effect=buscar_orcamento):
        yield AppTest.from_function(_tela_historico, default_timeout=30)


def textos(at):
    return " ".join(m.value for m in at.markdown)


def test_lista_vem_do_mais_recente_para_o_mais_antigo():
    with historico_logado() as at:
        at.run()
        assert not at.exception
        assert textos(at).index("Maria") < textos(at).index("João")
        assert "2 orçamentos" in at.caption[0].value


def test_busca_por_nome_e_por_data():
    from datetime import date

    with historico_logado() as at:
        at.run()
        at.text_input[0].set_value("joao").run()
        assert "João Pedro" in textos(at) and "Maria" not in textos(at)

        at.text_input[0].set_value("").run()
        at.date_input[0].set_value(date(2026, 10, 5)).run()   # "De"
        assert "Maria" in textos(at) and "João" not in textos(at)

        at.text_input[0].set_value("ninguem").run()
        assert any("Nenhum orçamento" in i.value for i in at.info)


def test_abrir_detalhes_e_reenviar():
    with historico_logado() as at:
        at.run()
        botao(at, "Abrir").click().run()
        assert not at.exception
        assert at.header[0].value == "Orçamento nº 0002"
        assert "Total: R$ 342,00" in textos(at)           # (2x100 + 180) - 10%
        valores = {m.label: m.value for m in at.metric}
        assert valores["Lucro"] == "R$ 262,00"
        assert [b.label for b in at.get("download_button")] == ["1. Baixar o PDF"]
        assert dados_da_mensagem(at)["inicio"] == "https://wa.me/5527988887777?text="
        botao(at, "Voltar para a lista").click().run()
        assert at.header[0].value == "Meus orçamentos"


def test_nao_abre_orcamento_de_outro_usuario():
    """Mesmo sabendo o id, outro usuário recebe "não encontrado"."""
    with historico_logado(user_id="outro") as at:
        at.session_state["hist_aberto"] = "o2"
        at.run()
        assert [e.value for e in at.error] == ["Orçamento não encontrado."]
        assert "Maria" not in textos(at)
        assert not at.get("download_button")


# ------------------------------------------------- banco desatualizado
class ErroDoBanco(Exception):
    """Imita o erro que o Supabase devolve (tem um atributo .code)."""

    def __init__(self, code, mensagem):
        super().__init__(mensagem)
        self.code = code


def test_falta_coluna_reconhece_os_dois_codigos():
    from core import db

    assert db.falta_coluna(ErroDoBanco("42703", "column orcamentos.numero does not exist"))
    assert db.falta_coluna(ErroDoBanco("PGRST204", "Could not find the 'mao_de_obra' column"))
    assert not db.falta_coluna(ErroDoBanco("23514", "violates check constraint"))
    assert not db.falta_coluna(Exception("timeout"))


def test_banco_desatualizado_mostra_como_resolver():
    with app_logado([]) as at, patch("core.db.migracao_pendente", return_value=True):
        at.run()
        assert not at.exception
        assert any("precisa ser atualizado" in e.value for e in at.error)
        assert any("migracao_*.sql" in m.value for m in at.markdown)
        assert "banco_conferido" not in at.session_state


def test_banco_em_dia_confere_uma_vez_so():
    with app_logado([]) as at, patch("core.db.migracao_pendente", return_value=False) as conferir:
        at.run()
        at.run()
        assert conferir.call_count == 1
        assert not any("precisa ser atualizado" in e.value for e in at.error)


def test_lista_com_banco_desatualizado_nao_mostra_erro_generico():
    erro = ErroDoBanco("42703", "column orcamentos.numero does not exist")
    with historico_logado() as at, patch("core.db.listar_orcamentos", side_effect=erro):
        at.run()
        assert not at.error
        assert any("banco de dados for atualizado" in i.value for i in at.info)


def test_salvar_com_banco_desatualizado_explica_o_motivo():
    erro = ErroDoBanco("PGRST204", "Could not find the 'mao_de_obra' column of 'orcamentos'")
    with app_logado([]) as at, patch("core.db.salvar_orcamento", side_effect=erro):
        at.session_state["orc_dados"] = {
            "cliente_nome": "Maria", "cliente_telefone": "", "equipamento": "", "mao_de_obra": 50.0,
            "desconto_tipo": "valor", "desconto_valor": 0.0, "condicoes_pagamento": "",
            "observacoes": "", "validade_dias": 7,
        }
        at.session_state["orc_itens"] = []
        at.session_state["orc_passo"] = 3
        at.run()
        botao(at, "Salvar orçamento").click().run()
        assert any("migracao_" in e for e in erros(at))
        assert "orc_salvo" not in at.session_state


# -------------------------------------------- corrigir dados do cliente
def test_corrigir_dados_do_cliente_valida_e_grava_so_os_campos_do_cliente():
    gravados = []

    def corrigir(user_id, orcamento_id, dados):
        gravados.append((user_id, orcamento_id, dados))
        return 1

    with historico_logado() as at, patch("core.db.corrigir_dados_do_cliente", side_effect=corrigir):
        at.session_state["hist_aberto"] = "o2"
        at.run()
        campos = {c.label: c for c in at.text_input}
        assert campos["Nome do cliente"].value == "Maria Conceição"

        campos["Nome do cliente"].set_value("   ")
        botao(at, "Salvar correção").click().run()
        assert "Nome do cliente: preenchimento obrigatório." in [e.value for e in at.error]
        assert gravados == []

        campos = {c.label: c for c in at.text_input}
        campos["Nome do cliente"].set_value(" Maria C. Souza ")
        campos["WhatsApp do cliente, com DDD (opcional)"].set_value("27977776666")
        botao(at, "Salvar correção").click().run()

    assert len(gravados) == 1
    user_id, orcamento_id, dados = gravados[0]
    assert (user_id, orcamento_id) == ("u1", "o2")
    assert dados["cliente_nome"] == "Maria C. Souza"
    assert dados["cliente_telefone"] == "27977776666"
    assert set(dados) == {"cliente_nome", "cliente_telefone", "equipamento",
                          "condicoes_pagamento", "observacoes"}


def test_correcao_nunca_altera_valores_mesmo_que_o_dict_traga():
    from unittest.mock import MagicMock

    from core import db

    cliente = MagicMock()
    with patch("core.db.obter_cliente", return_value=cliente):
        db.corrigir_dados_do_cliente(
            "u1", "o2", {"cliente_nome": "Novo", "total": 0, "user_id": "outro", "numero": 99})
    cliente.table.return_value.update.assert_called_once_with({"cliente_nome": "Novo"})


# ------------------------------------------------ telefone só com números
def test_telefone_com_mascara_nao_avanca_no_orcamento():
    with app_logado([]) as at:
        at.run()
        at.text_input(key="orc_w_cliente_nome").set_value("Maria")
        campo = at.text_input(key="orc_w_cliente_telefone")
        assert campo.max_chars == 11
        campo.set_value("27 99999-8")
        botao(at, "Continuar").click().run()
        assert "O telefone deve conter apenas números." in erros(at)
        assert at.session_state["orc_passo"] == 0


def test_telefone_invalido_nao_e_gravado_nem_que_a_tela_falhe():
    """A última barreira fica em core/db.py, logo antes do envio ao Supabase."""
    from unittest.mock import MagicMock

    import pytest

    from core import db

    cliente = MagicMock()
    with patch("core.db.obter_cliente", return_value=cliente):
        for ruim in ["(27) 99999-8888", "279999988881", "27abc998888", "+5527999998888"]:
            with pytest.raises(ValueError):
                db.salvar_perfil("u1", "Empresa", ruim, 7, None)
            with pytest.raises(ValueError):
                db.salvar_orcamento("u1", {"cliente_nome": "A", "cliente_telefone": ruim}, [], 0)
            with pytest.raises(ValueError):
                db.corrigir_dados_do_cliente("u1", "o1", {"cliente_telefone": ruim})
    cliente.table.assert_not_called()      # nada chegou perto do banco


# ------------------------------------- cadastro com e-mail já cadastrado
def _tela_login():
    from telas import login

    login.mostrar()


def test_email_ja_cadastrado_leva_para_a_aba_entrar_com_o_email_preenchido():
    from core import auth

    with patch("telas.login.campo_senha_nova", return_value="Casa@2024"), \
         patch("telas.login.campo_senha", return_value="Casa@2024"), \
         patch("core.auth.cadastrar", return_value=(auth.EMAIL_JA_CADASTRADO, False)) as cadastrar:
        at = AppTest.from_function(_tela_login, default_timeout=30).run()
        assert not at.exception
        at.text_input(key="cad_email_0").set_value("Maria@Gmail.com")
        at.button(key="cad_enviar").click().run()

        cadastrar.assert_called_once_with("maria@gmail.com", "Casa@2024")
        assert any("Já existe uma conta com o e-mail" in i.value for i in at.info)
        assert not at.error
        emails = [c for c in at.text_input if c.label == "E-mail"]
        assert emails[0].value == "maria@gmail.com"                   # preenchido na aba Entrar
        assert at.text_input(key="cad_email_1").value == ""           # cadastro esvaziado
        assert at.session_state["rodada_abas"] == 1                   # abas voltam para "Entrar"


def test_email_de_dominio_inexistente_mostra_erro_e_fica_no_cadastro():
    erro = "Não encontramos o servidor de e-mail de “@gmail.con”. Confira se digitou certo."
    with patch("telas.login.campo_senha_nova", return_value="Casa@2024"), \
         patch("telas.login.campo_senha", return_value="Casa@2024"), \
         patch("core.auth.cadastrar", return_value=(erro, False)):
        at = AppTest.from_function(_tela_login, default_timeout=30).run()
        at.text_input(key="cad_email_0").set_value("maria@gmail.con")
        at.button(key="cad_enviar").click().run()
        assert erro in [e.value for e in at.error]
        assert "entrar_com_email" not in at.session_state


def test_senhas_diferentes_no_cadastro_nao_chamam_o_servidor():
    with patch("telas.login.campo_senha_nova", return_value="Casa@2024"), \
         patch("telas.login.campo_senha", return_value="Casa@2025"), \
         patch("core.auth.cadastrar") as cadastrar:
        at = AppTest.from_function(_tela_login, default_timeout=30).run()
        at.text_input(key="cad_email_0").set_value("maria@gmail.com")
        at.button(key="cad_enviar").click().run()
        assert "As senhas não são iguais." in [e.value for e in at.error]
        cadastrar.assert_not_called()


def test_sem_as_chaves_do_supabase_o_app_explica_e_para():
    with patch("core.supabase_client.config_ok", return_value=False):
        at = AppTest.from_file(APP, default_timeout=30).run()
        assert not at.exception
        assert any("Configuração incompleta" in e.value for e in at.error)
        assert not at.button          # nenhuma tela é mostrada


# ------------------------------------- servidor fora do ar ao abrir o app
def test_sem_internet_ao_abrir_o_app_explica_em_vez_de_quebrar():
    import httpx

    with app_logado([]) as at, \
         patch("core.db.migracao_pendente", side_effect=httpx.ConnectError("sem rede")):
        at.run()
        assert not at.exception
        assert any("Não foi possível falar com o servidor" in e.value for e in at.error)
        assert not at.button                                   # nenhuma tela pela metade
        assert "banco_conferido" not in at.session_state       # confere de novo na próxima


def test_sem_internet_ao_conferir_o_aceite_tambem_explica():
    import httpx

    with app_logado([]) as at, \
         patch("core.db.aceitou_politica", side_effect=httpx.ReadTimeout("demorou")):
        at.run()
        assert not at.exception
        assert any("Não foi possível falar com o servidor" in e.value for e in at.error)


def test_migracao_pendente_distingue_estrutura_de_falha_de_rede():
    from unittest.mock import MagicMock

    import httpx
    import pytest

    from core import db

    cliente = MagicMock()
    consulta = cliente.table.return_value.select.return_value.limit.return_value.execute
    with patch("core.db.obter_cliente", return_value=cliente):
        consulta.side_effect = None
        assert db.migracao_pendente() is False
        consulta.side_effect = ErroDoBanco("42703", "column orcamentos.numero does not exist")
        assert db.migracao_pendente() is True
        consulta.side_effect = httpx.ConnectError("sem rede")
        with pytest.raises(httpx.ConnectError):
            db.migracao_pendente()


# --------------------------------------------- toque duplo e catálogo alterado
DADOS_PRONTOS = {
    "cliente_nome": "Maria", "cliente_telefone": "", "equipamento": "", "mao_de_obra": 50.0,
    "desconto_tipo": "valor", "desconto_valor": 0.0, "condicoes_pagamento": "",
    "observacoes": "", "validade_dias": 7,
}


def test_toque_duplo_em_salvar_grava_uma_vez_so_e_nao_quebra():
    from telas import novo_orcamento

    salvos = []
    with app_logado(salvos) as at:
        at.session_state["orc_dados"] = dict(DADOS_PRONTOS)
        at.session_state["orc_itens"] = []
        at.session_state["orc_passo"] = 3
        at.run()
        botao(at, "Salvar orçamento").click().run()
        assert len(salvos) == 1 and "orc_salvo" in at.session_state

    # O segundo toque chega quando os dados já foram limpos da memória.
    estado = {"orc_salvo": {"id": "x"}}
    with patch.object(novo_orcamento.st, "session_state", estado), \
         patch("core.db.salvar_orcamento") as salvar_de_novo:
        novo_orcamento._salvar("u1")            # antes: KeyError
        novo_orcamento._avancar(3)
        novo_orcamento._remover_item(1)
        novo_orcamento._adicionar_avulso_cb()
        novo_orcamento._adicionar_do_catalogo_cb(CATALOGO)
    salvar_de_novo.assert_not_called()
    assert estado == {"orc_salvo": {"id": "x"}}       # nada foi mexido


def test_item_escolhido_que_saiu_do_catalogo_nao_quebra():
    from telas import novo_orcamento

    # A lista foi desenhada com 9 itens; o catálogo agora tem 2 e a posição 8 não existe mais.
    estado = {"orc_dados": dict(DADOS_PRONTOS), "orc_itens": [], "orc_escolhido": 8,
              "orc_nova_quantidade": 1}
    with patch.object(novo_orcamento.st, "session_state", estado):
        novo_orcamento._adicionar_do_catalogo_cb(CATALOGO[:2])    # antes: IndexError
    assert estado["orc_itens"] == []
    assert "catálogo mudou" in estado["orc_erros"][0]


def test_total_acima_do_que_o_banco_guarda_e_avisado_antes_de_salvar():
    from core.calculos import calcular_resumo
    from telas import novo_orcamento

    itens = [{"nome": "Compressor", "tipo": "peca", "quantidade": 999,
              "custo_unitario": 0.0, "preco_unitario": 999_999.99}]       # ~ R$ 999 milhões
    resumo = calcular_resumo(itens, "valor", 0, 0)
    erros_do_passo = novo_orcamento._erros_valores(dict(DADOS_PRONTOS), resumo)
    assert any("limite do sistema" in e for e in erros_do_passo)

    normal = calcular_resumo([dict(itens[0], quantidade=1, preco_unitario=500.0)], "valor", 0, 0)
    assert novo_orcamento._erros_valores(dict(DADOS_PRONTOS), normal) == []


# ---------------------------------------------------------------- catálogo
def _tela_catalogo():
    from telas import catalogo

    catalogo.mostrar()


def test_catalogo_mostra_os_itens_sem_erro():
    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("telas.catalogo.garantir_catalogo_inicial"), \
         patch("core.db.listar_catalogo", return_value=CATALOGO):
        at = AppTest.from_function(_tela_catalogo, default_timeout=30)
        at.run()
        assert not at.exception
        assert not erros(at)
        # Os itens aparecem separados por tipo, e cada um tem o seu formulário.
        assert "Serviços" in [s.value for s in at.subheader]
        assert len(at.button) > len(CATALOGO)


# ------------------------------------------------- mensagem do WhatsApp
def _tela_perfil():
    from telas import perfil

    perfil.mostrar()


def test_perfil_grava_a_mensagem_do_tecnico_e_volta_ao_padrao():
    gravadas = []
    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.auth.usuario_email", return_value="tecnico@exemplo.com"), \
         patch("core.db.buscar_perfil", return_value=dict(PERFIL)), \
         patch("core.db.salvar_mensagem_whatsapp", side_effect=lambda u, m: gravadas.append((u, m))):
        at = AppTest.from_function(_tela_perfil, default_timeout=30)
        at.run()
        assert not at.exception
        caixa = next(c for c in at.text_area if c.label == "Sua mensagem")
        assert "{cliente}" in caixa.value           # começa com a sugestão

        caixa.set_value("  Oi {cliente}, deu {total}.  ")
        botao(at, "Salvar mensagem").click().run()
        assert gravadas == [("u1", "Oi {cliente}, deu {total}.")]

        botao(at, "Voltar à mensagem do sistema").click().run()
        assert gravadas[-1] == ("u1", "")


def test_perfil_nao_grava_mensagem_vazia_e_avisa_se_falta_a_migracao():
    def sem_coluna(user_id, mensagem):
        raise Exception("PGRST204 Could not find the 'mensagem_whatsapp' column")

    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.auth.usuario_email", return_value="tecnico@exemplo.com"), \
         patch("core.db.buscar_perfil", return_value=dict(PERFIL)), \
         patch("core.db.salvar_mensagem_whatsapp", side_effect=sem_coluna) as gravar:
        at = AppTest.from_function(_tela_perfil, default_timeout=30)
        at.run()
        caixa = next(c for c in at.text_area if c.label == "Sua mensagem")
        caixa.set_value("   ")
        botao(at, "Salvar mensagem").click().run()
        assert "Mensagem: preenchimento obrigatório." in erros(at)
        assert not gravar.called

        caixa = next(c for c in at.text_area if c.label == "Sua mensagem")
        caixa.set_value("Oi {cliente}")
        botao(at, "Salvar mensagem").click().run()
        assert any("migracao_005.sql" in e for e in erros(at))


# ------------------------------------------- esqueci minha senha (a partir do login)
def _tela_entrar():
    from telas import login

    login._formulario_entrar()


def test_esqueci_minha_senha_usa_o_email_digitado_no_login():
    with patch("core.auth.pedir_codigo_de_senha") as pedir:
        at = AppTest.from_function(_tela_entrar, default_timeout=30)
        at.run()
        assert not at.exception
        assert [t.label for t in at.text_input] == ["E-mail", "Senha"]

        # Sem e-mail: orienta e não envia nada.
        botao(at, "Esqueci minha senha").click().run()
        assert any("Digite o seu e-mail" in e for e in erros(at))
        pedir.assert_not_called()

        at.text_input[0].set_value("não é um e-mail")
        botao(at, "Esqueci minha senha").click().run()
        assert "E-mail inválido." in erros(at)
        pedir.assert_not_called()

        # Com e-mail: o código vai para ele, sem pedir o endereço de novo.
        at.text_input[0].set_value("  Ana@Exemplo.com ")
        botao(at, "Esqueci minha senha").click().run()
        pedir.assert_called_once_with("ana@exemplo.com")
        assert [t.label for t in at.text_input] == ["Código recebido por e-mail"]
        assert "ana@exemplo\\.com" in " ".join(i.value for i in at.info)

        # "Voltar ao login" desfaz tudo e esquece o endereço.
        botao(at, "Voltar ao login").click().run()
        assert [t.label for t in at.text_input] == ["E-mail", "Senha"]
        assert "redefinir_email_do_codigo" not in at.session_state


def test_reenviar_codigo_usa_o_mesmo_email_do_login_e_respeita_o_intervalo():
    with patch("core.auth.pedir_codigo_de_senha") as pedir:
        at = AppTest.from_function(_tela_entrar, default_timeout=30)
        at.run()
        at.text_input[0].set_value("ana@exemplo.com")
        botao(at, "Esqueci minha senha").click().run()
        assert pedir.call_count == 1

        # Logo em seguida: o servidor ignoraria o pedido, então a tela não finge que reenviou.
        botao(at, "Reenviar código").click().run()
        assert pedir.call_count == 1
        assert any("Aguarde" in w.value for w in at.warning)

        # Voltar ao login e pedir de novo para o MESMO e-mail não burla a espera...
        botao(at, "Voltar ao login").click().run()
        at.text_input[0].set_value("ana@exemplo.com")
        botao(at, "Esqueci minha senha").click().run()
        assert pedir.call_count == 1
        assert [t.label for t in at.text_input] == ["Código recebido por e-mail"]   # ...mas segue para o código

        # Passado um minuto, o reenvio sai, para o mesmo e-mail.
        at.session_state["redefinir_hora_do_pedido"] -= 61
        botao(at, "Reenviar código").click().run()
        assert [c.args for c in pedir.call_args_list] == [("ana@exemplo.com",), ("ana@exemplo.com",)]


# ------------------------------------------- falha ao salvar: diz o motivo
def test_falha_ao_salvar_explica_o_motivo_e_guarda_o_que_foi_preenchido():
    import httpx

    casos = [
        (httpx.ConnectError("sem rede"), "Não foi possível falar com o servidor"),
        (ErroDoBanco("42501", "new row violates row-level security policy"), "não reconheceu o seu login"),
        (ErroDoBanco("23514", "violates check constraint"), "(código: 23514)"),
    ]
    for erro, trecho in casos:
        with app_logado([]) as at, patch("core.db.salvar_orcamento", side_effect=erro):
            at.session_state["orc_dados"] = {
                "cliente_nome": "Maria", "cliente_telefone": "", "equipamento": "", "mao_de_obra": 50.0,
                "desconto_tipo": "valor", "desconto_valor": 0.0, "condicoes_pagamento": "",
                "observacoes": "", "validade_dias": 7,
            }
            at.session_state["orc_itens"] = []
            at.session_state["orc_passo"] = 3
            at.run()
            botao(at, "Salvar orçamento").click().run()
            assert any(trecho in e for e in erros(at)), (trecho, erros(at))
            assert "orc_salvo" not in at.session_state
            assert at.session_state["orc_dados"]["cliente_nome"] == "Maria"   # nada se perdeu


def test_conta_nova_de_eletricista_recebe_os_exemplos_de_eletrica():
    from core.catalogo_inicial import AREAS

    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.auth.ler_marcador", return_value=None), \
         patch("core.auth.gravar_marcador") as marcar, \
         patch("core.db.listar_catalogo", return_value=[]), \
         patch("core.db.inserir_itens_catalogo") as inserir:
        at = AppTest.from_function(_tela_catalogo, default_timeout=30)
        at.run()
        assert not at.exception
        at.radio[0].set_value("eletrica")
        botao(at, "Começar").click().run()
        inserir.assert_called_once_with("u1", AREAS["eletrica"]["itens"])
        marcar.assert_called_once()


def test_trazer_outra_area_acrescenta_so_o_que_falta():
    from core.catalogo_inicial import AREAS
    from telas.catalogo import itens_que_faltam

    # Quem tem o catálogo de ar-condicionado e traz "bikes": entram os 9, nada é repetido.
    assert itens_que_faltam("bikes_eletricas", CATALOGO) == AREAS["bikes_eletricas"]["itens"]
    # Trazer a mesma área de novo não repete nada (nem com o nome em maiúsculas).
    assert itens_que_faltam("ar_condicionado", [dict(i, nome=i["nome"].upper()) for i in CATALOGO]) == []

    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.auth.ler_marcador", return_value=True), \
         patch("core.db.listar_catalogo", return_value=CATALOGO), \
         patch("core.db.inserir_itens_catalogo") as inserir:
        at = AppTest.from_function(_tela_catalogo, default_timeout=30)
        at.run()
        at.selectbox(key="outra_area").set_value("bikes_eletricas")
        at.button(key="trazer_area").click().run()
        assert not at.exception
        inserir.assert_called_once_with("u1", AREAS["bikes_eletricas"]["itens"])


def test_reiniciar_o_catalogo_so_apaga_depois_da_confirmacao():
    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.auth.ler_marcador", return_value=True), \
         patch("core.auth.gravar_marcador") as marcar, \
         patch("core.db.listar_catalogo", return_value=CATALOGO), \
         patch("core.db.excluir_todo_o_catalogo") as apagar:
        at = AppTest.from_function(_tela_catalogo, default_timeout=30)
        at.run()
        # 1º toque: só aparece o aviso, nada é apagado.
        at.button(key="pedir_reinicio").click().run()
        assert not at.exception
        assert any("Quer mesmo reiniciar" in a.value for a in at.warning)
        apagar.assert_not_called()
        # Cancelar fecha o aviso e continua sem apagar.
        at.button(key="cancelar_reinicio").click().run()
        assert not at.warning
        apagar.assert_not_called()
        # Pedir de novo e confirmar: agora apaga e libera a pergunta da área.
        at.button(key="pedir_reinicio").click().run()
        at.button(key="confirmar_reinicio").click().run()
        assert not at.exception
        apagar.assert_called_once_with("u1")
        marcar.assert_called_once_with("catalogo_inicial_criado", False)


def test_conta_antiga_com_itens_nao_ve_a_pergunta_da_area():
    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.auth.ler_marcador", return_value=None), \
         patch("core.auth.gravar_marcador") as marcar, \
         patch("core.db.listar_catalogo", return_value=CATALOGO), \
         patch("core.db.inserir_itens_catalogo") as inserir:
        at = AppTest.from_function(_tela_catalogo, default_timeout=30)
        at.run()
        assert not at.exception
        assert not at.radio
        inserir.assert_not_called()
        marcar.assert_called_once()


# ------------------------------------- conta nova: catálogo de exemplo no 1º orçamento
def test_conta_nova_ja_encontra_o_catalogo_de_exemplo_no_novo_orcamento():
    criado = []                        # o catálogo fica vazio até a lista de exemplo ser criada

    def listar(_user_id):
        return CATALOGO if criado else []

    with app_logado([]) as at, \
         patch("core.auth.ler_marcador", return_value=None), \
         patch("core.auth.gravar_marcador") as marcar, \
         patch("core.db.listar_catalogo", side_effect=listar), \
         patch("core.db.inserir_itens_catalogo", side_effect=lambda *_: criado.append(1)) as inserir:
        at.run()
        assert not at.exception
        # Antes do primeiro orçamento, a conta nova escolhe a área de trabalho.
        assert "área de trabalho" in at.subheader[0].value
        inserir.assert_not_called()
        botao(at, "Começar").click().run()
        inserir.assert_called_once_with("u1", ITENS_INICIAIS)     # a primeira opção é ar-condicionado
        marcar.assert_called_once()
        at.text_input(key="orc_w_cliente_nome").set_value("Maria")
        botao(at, "Continuar").click().run()
        # O passo de itens mostra o catálogo, e não o aviso de catálogo vazio.
        assert not any("catálogo está vazio" in i.value for i in at.info)
        assert at.selectbox(key="orc_escolhido") is not None


def test_falha_ao_criar_o_catalogo_de_exemplo_nao_impede_o_orcamento():
    with app_logado([]) as at, \
         patch("core.auth.ler_marcador", return_value=None), \
         patch("core.auth.gravar_marcador", side_effect=Exception("sem rede")):
        at.run()
        assert not at.exception
        assert not erros(at)
        assert at.header[0].value == "Novo orçamento"


# ------------------------------------- centavos: o que se vê é o que se grava
def test_total_da_revisao_e_igual_ao_total_gravado_com_preco_de_tres_casas():
    # Antes: preço 10,994 x 3 e mão de obra 0,004 mostravam R$ 32,99 na revisão
    # e gravavam R$ 32,97 (o PDF saía com um valor diferente do que foi conferido).
    salvos = []
    with app_logado(salvos) as at:
        at.run()
        at.text_input(key="orc_w_cliente_nome").set_value("Maria")
        botao(at, "Continuar").click().run()
        at.selectbox(key="orc_escolhido").set_value(1)
        at.number_input(key="orc_nova_quantidade").set_value(3)
        botao(at, "Adicionar ao orçamento").click().run()
        linha = at.session_state["orc_itens"][0]["linha"]
        at.number_input(key=f"orc_preco_{linha}").set_value(10.994).run()
        assert "Subtotal: **R$ 32,97**" in textos(at)                # a linha do item já em centavos
        botao(at, "Continuar").click().run()
        at.number_input(key="orc_w_mao_de_obra").set_value(0.004).run()
        botao(at, "Continuar").click().run()
        na_revisao = {m.label: m.value for m in at.metric}["Total"]
        botao(at, "Salvar orçamento").click().run()
    assert na_revisao == "R$ 32,97"
    assert salvos[0]["total"] == 32.97
    assert salvos[0]["itens"][0]["preco_unitario"] == 10.99
    assert salvos[0]["dados"]["mao_de_obra"] == 0.0


def test_observacoes_guardam_as_quebras_de_linha_e_perdem_caracteres_de_controle():
    salvos = []
    with app_logado(salvos) as at:
        at.session_state["orc_dados"] = {
            "cliente_nome": "Maria\x00 da\tSilva\n", "cliente_telefone": "", "equipamento": "", "mao_de_obra": 50.0,
            "desconto_tipo": "valor", "desconto_valor": 0.0, "condicoes_pagamento": "",
            "observacoes": "Garantia de 90 dias.\r\nPagamento na entrega.\x07", "validade_dias": 7,
        }
        at.session_state["orc_itens"] = []
        at.session_state["orc_passo"] = 3
        at.run()
        botao(at, "Salvar orçamento").click().run()
    assert salvos[0]["dados"]["cliente_nome"] == "Maria da Silva"
    assert salvos[0]["dados"]["observacoes"] == "Garantia de 90 dias.\nPagamento na entrega."


# ------------------------------------- configuração: chave secreta nunca roda
def test_app_nao_roda_com_a_chave_secreta_do_supabase():
    with app_logado([]) as at, patch("core.supabase_client.ler_config", return_value="sb_secret_abc123"), \
         patch("core.supabase_client.config_ok", return_value=True):
        at.run()
        assert any("chave SECRETA" in e for e in erros(at))
        assert not at.header                                   # nenhuma tela do sistema apareceu


def test_endereco_e_limpo_uma_vez_por_sessao_com_script_fixo():
    from core import cookie_sessao

    with patch("core.cookie_sessao._rodar_js") as rodar_js, patch("core.cookie_sessao.st") as st_falso:
        st_falso.session_state = {}
        cookie_sessao.limpar_tokens_do_endereco()
        cookie_sessao.limpar_tokens_do_endereco()
    rodar_js.assert_called_once()
    script = rodar_js.call_args.args[0]
    assert "replaceState" in script and "access_token" in script and "refresh_token" in script
    # Com < > ou & o Streamlit não executa o script (e não avisa): veja core/cookie_sessao.py.
    assert not set("<>&") & set(script)


def test_folga_dos_selos_e_medida_uma_vez_por_sessao_com_script_fixo():
    from core import cookie_sessao
    from telas import componentes

    with patch("core.cookie_sessao._rodar_js") as rodar_js, patch("core.cookie_sessao.st") as st_falso:
        st_falso.session_state = {}
        cookie_sessao.abrir_espaco_para_selos()
        cookie_sessao.abrir_espaco_para_selos()
    rodar_js.assert_called_once()
    script = rodar_js.call_args.args[0]
    assert "--folga-da-hospedagem" in script
    assert not set("<>&") & set(script)
    # O menu do celular usa a mesma variável que o script grava.
    import inspect
    assert "var(--folga-da-hospedagem, 0px)" in inspect.getsource(componentes)


def test_scripts_do_cookie_tambem_nao_tem_caracteres_que_o_streamlit_estraga():
    from core import cookie_sessao

    with patch("core.cookie_sessao._rodar_js") as rodar_js:
        cookie_sessao.gravar("abcDEF123456")
        cookie_sessao.apagar()
    assert rodar_js.call_count == 2
    for chamada in rodar_js.call_args_list:
        assert not set("<>&") & set(chamada.args[0])


# ------------------------------------- mensagem do WhatsApp longa não é cortada
def test_mensagem_montada_passa_de_700_sem_ser_cortada_na_caixa_de_envio():
    from core.validacao import MAX_MENSAGEM, MAX_MENSAGEM_ENVIO

    modelo = ("Olá, {cliente}! {empresa} {equipamento} " + "x" * 650)[:MAX_MENSAGEM]
    perfil = dict(PERFIL, mensagem_whatsapp=modelo, nome_empresa="E" * 80)
    with historico_logado() as at, patch("core.db.buscar_perfil", return_value=perfil):
        at.session_state["hist_aberto"] = "o2"
        at.run()
        assert not at.exception
        dados = dados_da_mensagem(at)
    assert dados["maximo"] == MAX_MENSAGEM_ENVIO
    assert MAX_MENSAGEM < len(dados["texto"]) <= MAX_MENSAGEM_ENVIO
    assert dados["texto"].endswith("x" * 20)                  # o fim do texto do técnico chegou inteiro


def test_item_escolhido_do_catalogo_mostra_o_preco_inteiro_abaixo_da_caixa():
    # A caixa de escolha corta o texto em celular estreito; o preço não pode sumir.
    with app_logado([]) as at:
        at.run()
        at.text_input(key="orc_w_cliente_nome").set_value("Maria")
        botao(at, "Continuar").click().run()
        at.selectbox(key="orc_escolhido").set_value(1).run()          # Limpeza / higienização
        legendas = " ".join(c.value for c in at.caption)
        assert "R$ 180,00" in legendas and "Limpeza" in legendas


def test_faixa_de_teste_so_aparece_no_app_de_teste():
    for valor, aparece in (("teste", True), ("", False)):
        with app_logado([]) as at, \
             patch("core.supabase_client.ler_config", side_effect=lambda nome, v=valor: v if nome == "AMBIENTE" else "x"), \
             patch("telas.componentes.faixa_de_teste") as faixa:
            at.run()
            assert not at.exception
            assert faixa.called == aparece


def test_situacao_muda_na_lista_e_no_orcamento():
    with historico_logado() as at, patch("core.db.definir_situacao") as definir:
        at.run()
        assert not at.exception
        # Na lista: cada orçamento tem o controle, que começa em "Não fechado".
        controles = at.get("button_group")
        assert len(controles) >= len(ORCAMENTOS)
        controles[-1].set_value("pago").run()
        assert not at.exception
        assert definir.call_args.args[2] == "pago"
        # Dentro do orçamento.
        at.session_state["hist_aberto"] = "o2"
        at.run()
        situacao = at.get("button_group")[0]
        situacao.set_value("fechado").run()
        assert definir.call_args.args[:3] == ("u1", "o2", "fechado")

def test_perfil_grava_a_cor_do_orcamento():
    gravadas = []
    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.auth.usuario_email", return_value="tecnico@exemplo.com"), \
         patch("core.db.buscar_perfil", return_value=dict(PERFIL)), \
         patch("core.db.salvar_cor_orcamento", side_effect=lambda u, c: gravadas.append((u, c))):
        at = AppTest.from_function(_tela_perfil, default_timeout=30)
        at.run()
        assert not at.exception
        assert at.button(key="salvar_cor").disabled            # nada mudou ainda
        pilulas = next(b for b in at.get("button_group") if "Vermelho" in str(b.proto))
        pilulas.set_value("Vermelho").run()
        at.button(key="salvar_cor").click().run()
        assert gravadas == [("u1", "#B42318")]



def test_aviso_de_salvo_nao_muda_a_posicao_do_resto_da_tela():
    """O aviso verde ("Item salvo") aparece em um desenho e some no seguinte.
    Se ele empurrasse o resto da tela, o Streamlit deixava cópias apagadas
    (opacidade baixa) dos itens a cada salvamento. Por isso ele fica numa
    caixa que existe sempre, com ou sem aviso."""
    with app_logado([]) as at:
        at.run()
        sem_aviso = len(at.main.children)
        at.session_state["aviso"] = "Item salvo: Teste"
        at.run()
        assert not at.exception
        assert at.success[0].value == "Item salvo: Teste"
        assert len(at.main.children) == sem_aviso
