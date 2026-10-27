"""Testes das rotinas de privacidade (LGPD). Rodar com: pytest"""

import json
from contextlib import contextmanager
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core import privacidade

ORCAMENTOS = [
    {"id": "o1", "numero": 1, "cliente_nome": "Maria Conceição", "cliente_telefone": "27988887777",
     "equipamento": "Split", "condicoes_pagamento": "Pix", "observacoes": "portão azul",
     "total": 342.0, "criado_em": "2026-10-09T15:00:00+00:00",
     "itens": [{"nome": "Capacitor", "tipo": "peca", "quantidade": 2,
                "custo_unitario": 31.47, "preco_unitario": 100.0}]},
    {"id": "o2", "numero": 2, "cliente_nome": "João Pedro", "cliente_telefone": "",
     "equipamento": "", "condicoes_pagamento": "", "observacoes": "",
     "total": 150.0, "criado_em": "2026-10-01T12:00:00+00:00", "itens": []},
    {"id": "o3", "numero": 3, "cliente_nome": "MARIA CONCEICAO", "cliente_telefone": "",
     "equipamento": "", "condicoes_pagamento": "", "observacoes": "",
     "total": 90.0, "criado_em": "2026-09-01T12:00:00+00:00", "itens": []},
]


# ------------------------------------------------------------ localizar
def achados(termo):
    return [o["id"] for o in ORCAMENTOS if privacidade.orcamento_e_do_cliente(o, termo)]


def test_localiza_cliente_por_nome_sem_acento_e_por_telefone():
    assert achados("maria conceicao") == ["o1", "o3"]
    assert achados("(27) 98888-7777") == ["o1"]
    assert achados("98888-7777") == ["o1"]
    assert achados("joão") == ["o2"]


def test_busca_vazia_ou_curta_nao_traz_todo_mundo():
    assert achados("") == []
    assert achados("   ") == []
    assert achados("7777") == []        # poucos dígitos não valem como telefone


# ------------------------------------------------------------- exportar
def test_exportacao_do_cliente_nao_leva_custo_nem_margem():
    arquivo = privacidade.montar_exportacao_do_cliente("maria", [ORCAMENTOS[0]])
    texto = json.dumps(arquivo, ensure_ascii=False)
    assert "Maria Conceição" in texto and "27988887777" in texto and "portão azul" in texto
    assert "custo" not in texto.lower() and "31.47" not in texto
    assert arquivo["orcamentos"][0]["itens"] == [
        {"descricao": "Capacitor", "quantidade": 2, "valor_unitario": 100.0}]


def test_exportacao_da_conta_traz_tudo_do_tecnico():
    arquivo = privacidade.montar_exportacao_da_conta(
        "tecnico@exemplo.com", {"nome_empresa": "Clima Frio"}, [{"nome": "Capacitor"}],
        ORCAMENTOS, [{"versao_politica": "1.0", "aceito_em": "2026-10-09T15:00:00+00:00"}])
    assert arquivo["conta"]["email"] == "tecnico@exemplo.com"
    assert arquivo["perfil"]["nome_empresa"] == "Clima Frio"
    assert len(arquivo["orcamentos"]) == 3
    assert arquivo["aceites_da_politica"][0]["versao_politica"] == "1.0"
    json.dumps(arquivo)   # precisa ser gravável como JSON


def test_dados_anonimos_cobrem_todos_os_campos_pessoais_do_orcamento():
    assert set(privacidade.DADOS_ANONIMOS) == {
        "cliente_nome", "cliente_telefone", "equipamento", "condicoes_pagamento", "observacoes"}
    assert privacidade.DADOS_ANONIMOS["cliente_nome"]          # o banco exige nome não vazio


# --------------------------------------------------------------- política
def test_politica_cita_o_que_o_sistema_realmente_usa():
    texto = privacidade.texto_da_politica()
    for trecho in ["Supabase", "Streamlit", "WhatsApp", "cookie", "CPF",
                   "transferência", privacidade.VERSAO_POLITICA]:
        assert trecho in texto, trecho


def test_app_nao_carrega_fontes_de_servidores_externos():
    from telas import componentes

    assert "googleapis" not in componentes._CSS
    assert "@import" not in componentes._CSS
    assert "Google Fonts" not in privacidade.texto_da_politica()


def test_campos_juridicos_nao_foram_inventados():
    # Enquanto o dono do sistema não preencher, os campos seguem marcados.
    assert "ENCARREGADO_EMAIL" in privacidade.pendencias() or privacidade.ENCARREGADO_EMAIL != "PREENCHER"
    if privacidade.pendencias():
        assert "PREENCHER" in privacidade.texto_da_politica()


# ------------------------------------------------------------------ telas
def _tela_aceite():
    from telas import privacidade as tela

    if tela.precisa_aceitar("u1"):
        tela.mostrar_aceite("u1")
    else:
        import streamlit as st

        st.write("DENTRO DO SISTEMA")


def _tela_privacidade():
    from telas import privacidade as tela

    tela.mostrar()


def botao(at, rotulo):
    return next(b for b in at.button if rotulo in b.label)


def test_sem_aceite_o_sistema_nao_abre_e_o_aceite_e_registrado():
    registrados = []
    with patch("core.db.aceitou_politica", return_value=False), \
         patch("core.db.registrar_aceite", side_effect=lambda u, v: registrados.append((u, v))):
        at = AppTest.from_function(_tela_aceite, default_timeout=30).run()
        assert at.header[0].value == "Antes de continuar"
        assert not any("DENTRO" in str(m.value) for m in at.markdown)

        botao(at, "Aceitar e continuar").click().run()        # sem marcar a caixa
        assert registrados == [] and at.error

        at.checkbox[0].check()
        botao(at, "Aceitar e continuar").click().run()
        assert registrados == [("u1", privacidade.VERSAO_POLITICA)]
        assert any("DENTRO" in str(m.value) for m in at.markdown)


def test_quem_ja_aceitou_entra_direto():
    with patch("core.db.aceitou_politica", return_value=True):
        at = AppTest.from_function(_tela_aceite, default_timeout=30).run()
        assert any("DENTRO" in str(m.value) for m in at.markdown)


@contextmanager
def pagina_privacidade(acoes):
    def auditoria(user_id, acao, quantidade=0):
        acoes.append(("auditoria", acao, quantidade))

    def anonimizar(user_id, ids, dados):
        acoes.append(("anonimizar", sorted(ids)))
        return len(ids)

    def excluir(user_id, ids):
        acoes.append(("excluir", sorted(ids)))
        return len(ids)

    with patch("core.auth.usuario_id", return_value="u1"), \
         patch("core.auth.usuario_email", return_value="tecnico@exemplo.com"), \
         patch("core.db.buscar_perfil", return_value={"nome_empresa": "Clima Frio"}), \
         patch("core.db.listar_catalogo", return_value=[]), \
         patch("core.db.listar_aceites", return_value=[]), \
         patch("core.db.listar_orcamentos_completos", return_value=[dict(o) for o in ORCAMENTOS]), \
         patch("core.db.registrar_auditoria", side_effect=auditoria), \
         patch("core.db.anonimizar_orcamentos", side_effect=anonimizar), \
         patch("core.db.excluir_orcamentos", side_effect=excluir):
        yield AppTest.from_function(_tela_privacidade, default_timeout=30)


def test_exportar_a_propria_conta_gera_arquivo_e_auditoria():
    acoes = []
    with pagina_privacidade(acoes) as at:
        at.run()
        assert not at.exception
        botao(at, "Preparar meu arquivo").click().run()
        arquivo = json.loads(at.session_state["priv_arquivo_conta"].decode("utf-8"))
        assert arquivo["conta"]["email"] == "tecnico@exemplo.com"
        assert len(arquivo["orcamentos"]) == 3
    assert acoes == [("auditoria", "exportar_conta", 3)]


def test_pedido_de_cliente_exige_confirmacao_e_age_so_nos_orcamentos_dele():
    acoes = []
    with pagina_privacidade(acoes) as at:
        at.run()
        at.text_input(key="priv_termo").set_value("maria").run()
        assert any("2 orçamentos" in m.value for m in at.markdown)

        botao(at, "Aplicar").click().run()                  # sem confirmar
        assert acoes == [] and at.error

        at.checkbox[0].check()
        botao(at, "Aplicar").click().run()
    assert acoes == [("anonimizar", ["o1", "o3"]), ("auditoria", "anonimizar_cliente", 2)]


def test_pedido_de_cliente_pode_apagar_por_completo():
    acoes = []
    with pagina_privacidade(acoes) as at:
        at.run()
        at.text_input(key="priv_termo").set_value("joao").run()
        at.radio[0].set_value("excluir")
        at.checkbox[0].check()
        botao(at, "Aplicar").click().run()
    assert acoes == [("excluir", ["o2"]), ("auditoria", "excluir_cliente", 1)]


def test_excluir_conta_exige_palavra_e_senha():
    with pagina_privacidade([]) as at, \
         patch("core.auth.entrar", return_value="E-mail ou senha incorretos.") as entrar, \
         patch("core.db.excluir_minha_conta") as excluir_conta:
        at.run()
        campos = {c.label: c for c in at.text_input}
        campos["Sua senha atual"].set_value("qualquer")
        botao(at, "Excluir minha conta para sempre").click().run()   # sem a palavra
        entrar.assert_not_called()

        {c.label: c for c in at.text_input}["Digite EXCLUIR para confirmar"].set_value("excluir")
        {c.label: c for c in at.text_input}["Sua senha atual"].set_value("senha-errada")
        botao(at, "Excluir minha conta para sempre").click().run()   # senha errada
        assert any("Senha incorreta" in e.value for e in at.error)
        excluir_conta.assert_not_called()


def test_excluir_conta_com_tudo_certo_apaga_e_sai():
    with pagina_privacidade([]) as at, \
         patch("core.auth.entrar", return_value=""), patch("core.auth.sair") as sair, \
         patch("core.db.excluir_minha_conta") as excluir_conta:
        at.run()
        campos = {c.label: c for c in at.text_input}
        campos["Sua senha atual"].set_value("senha-certa")
        campos["Digite EXCLUIR para confirmar"].set_value("EXCLUIR")
        botao(at, "Excluir minha conta para sempre").click().run()
        excluir_conta.assert_called_once()
        sair.assert_called_once()


# ---------------------------------------------------- identidade visual
def test_fontes_do_tema_sao_as_embutidas_e_nao_as_de_um_servidor():
    import tomllib
    from pathlib import Path

    tema = tomllib.loads(
        (Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml").read_text("utf-8")
    )["theme"]
    # "sans-serif" e "serif" são as fontes que o Streamlit traz consigo. Um endereço
    # (http...) aqui significaria baixar a fonte de fora a cada acesso.
    assert tema["font"] == "sans-serif" and tema["headingFont"] == "serif"
    assert "http" not in str(tema) and "fontFaces" not in tema
    assert tema["base"] == "light"                 # tema sempre claro


def test_exemplo_da_pagina_inicial_usa_numeros_que_o_sistema_realmente_calcula():
    """A folha de exemplo mostra total, lucro e margem: têm de bater com o cálculo real."""
    import inspect

    from core.calculos import calcular_resumo
    from core.catalogo_inicial import ITENS_INICIAIS
    from core.formato import formatar_reais
    from telas import componentes

    catalogo = {item["nome"]: item for item in ITENS_INICIAIS}
    itens = [
        {"quantidade": q, "custo_unitario": catalogo[n]["custo"], "preco_unitario": catalogo[n]["preco"]}
        for n, q in [("Limpeza / higienização", 1), ("Capacitor", 2), ("Carga de gás", 1)]
    ]
    resumo = calcular_resumo(itens, "valor", 0)
    pagina = inspect.getsource(componentes.destaque_inicial)
    assert formatar_reais(resumo["total"]) in pagina          # R$ 710,00
    assert formatar_reais(resumo["lucro"]) in pagina          # R$ 480,00
    assert f"{resumo['margem']:.1f}%".replace(".", ",") in pagina   # 67,6%


def test_animacoes_respeitam_quem_pede_menos_movimento():
    from telas import componentes

    assert "prefers-reduced-motion: reduce" in componentes._CSS
    assert "animation: none !important" in componentes._CSS


def test_aceite_que_ja_estava_gravado_conta_como_aceito():
    # Toque duplo, outra aba ou resposta perdida na rede: a segunda gravação é
    # recusada pelo banco (um aceite por versão), mas o aceite existe.
    respostas = iter([False, True])       # 1ª consulta: ainda não aceitou; depois da "falha": já consta
    with patch("core.db.aceitou_politica", side_effect=lambda u, v: next(respostas, True)), \
         patch("core.db.registrar_aceite", side_effect=Exception("23505 duplicate key")):
        at = AppTest.from_function(_tela_aceite, default_timeout=30).run()
        at.checkbox[0].check()
        botao(at, "Aceitar e continuar").click().run()
        assert not at.error
        assert any("DENTRO" in str(m.value) for m in at.markdown)


def test_aceite_que_falhou_de_verdade_continua_avisando():
    with patch("core.db.aceitou_politica", return_value=False), \
         patch("core.db.registrar_aceite", side_effect=Exception("sem rede")):
        at = AppTest.from_function(_tela_aceite, default_timeout=30).run()
        at.checkbox[0].check()
        botao(at, "Aceitar e continuar").click().run()
        assert any("Não foi possível registrar o aceite" in e.value for e in at.error)
        assert not any("DENTRO" in str(m.value) for m in at.markdown)


def test_politica_sai_sem_documento_enquanto_ele_estiver_vazio():
    # No piloto o documento fica vazio (para não publicar CPF) e isso não conta como pendência.
    with patch.object(privacidade, "CONTROLADOR_DOCUMENTO", ""):
        assert "CONTROLADOR_DOCUMENTO" not in privacidade.pendencias()
        assert privacidade.quem_somos() == f"{privacidade.CONTROLADOR_NOME}, {privacidade.CONTROLADOR_CIDADE}"
        assert ", ," not in privacidade.texto_da_politica()
    with patch.object(privacidade, "CONTROLADOR_DOCUMENTO", "CNPJ 00.000.000/0001-00"):
        assert "CNPJ 00.000.000/0001-00" in privacidade.texto_da_politica()
