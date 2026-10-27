"""Testes de ponta a ponta contra o Supabase DE VERDADE.

Os outros testes usam banco simulado. Estes aqui fazem login com dois
usuários de teste reais e exercitam as mesmas funções que o app usa.

Como habilitar (veja também o .env.example):
  1. No painel do Supabase, crie dois usuários só de teste
     (Authentication > Users > Add user, com "Auto Confirm User").
  2. No arquivo .env, preencha TESTE_EMAIL_1, TESTE_SENHA_1,
     TESTE_EMAIL_2 e TESTE_SENHA_2, e acrescente TESTE_CONTAS_DESCARTAVEIS=sim.
     NUNCA use aqui uma conta de uso real: os testes gravam e apagam dados,
     trocam a senha da conta 1 e encerram as sessões das duas contas.
  3. Rode:  pytest tests/test_supabase_real.py -v

Sem essas variáveis, todos os testes deste arquivo são pulados.
As credenciais nunca ficam no código: são lidas do .env.

Tudo que os testes gravam leva o nome MARCA no cliente e é apagado no fim.
"""

import os
import secrets
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from supabase import create_client  # noqa: E402

from core import db  # noqa: E402
from core.supabase_client import ler_config, url_supabase  # noqa: E402

VARIAVEIS = ["TESTE_EMAIL_1", "TESTE_SENHA_1", "TESTE_EMAIL_2", "TESTE_SENHA_2"]
FALTANDO = [v for v in VARIAVEIS if not os.getenv(v, "").strip()]

# TRAVA DE SEGURANÇA. Estes testes entram nas contas, gravam e apagam dados,
# trocam a senha da conta 1 e encerram sessões. Em uma conta de uso real isso
# derruba o login da pessoa e mexe nos dados dela. Por isso só rodam quando o
# .env declara, com todas as letras, que as duas contas são descartáveis:
#     TESTE_CONTAS_DESCARTAVEIS=sim
CONTAS_DESCARTAVEIS = os.getenv("TESTE_CONTAS_DESCARTAVEIS", "").strip().lower() == "sim"

if FALTANDO or not url_supabase():
    MOTIVO = "Testes reais pulados: preencha no .env " + ", ".join(FALTANDO or ["SUPABASE_URL"])
elif not CONTAS_DESCARTAVEIS:
    MOTIVO = (
        "Testes reais pulados por segurança: eles gravam, apagam e encerram sessões. "
        "Use duas contas criadas SÓ para teste (nunca a sua) e acrescente no .env a "
        "linha TESTE_CONTAS_DESCARTAVEIS=sim (veja o CONFIG_SUPABASE.md, seção 6)."
    )
else:
    MOTIVO = ""

pytestmark = pytest.mark.skipif(bool(MOTIVO), reason=MOTIVO)

MARCA = "TESTE-AUTOMATICO"

DADOS = {
    "cliente_nome": f"{MARCA} Maria",
    "cliente_telefone": "27988887777",
    "equipamento": "Split 12.000 BTUs",
    "mao_de_obra": 100.0,
    "desconto_tipo": "percentual",
    "desconto_valor": 10.0,
    "condicoes_pagamento": "Pix",
    "observacoes": "",
    "validade_dias": 7,
}
ITENS = [
    {"nome": "Capacitor", "tipo": "peca", "quantidade": 2,
     "custo_unitario": 30.0, "preco_unitario": 90.0},
    {"nome": "Limpeza", "tipo": "mao_de_obra", "quantidade": 1,
     "custo_unitario": 20.0, "preco_unitario": 180.0},
]
TOTAL = 414.0   # (2x90 + 180 + 100) - 10%


def novo_cliente():
    """Uma conexão nova com o Supabase, ainda sem login (visitante)."""
    return create_client(url_supabase(), ler_config("SUPABASE_KEY"))


class Usuario:
    """Um usuário de teste logado: a conexão e o id dele."""

    def __init__(self, numero):
        self.email = os.environ[f"TESTE_EMAIL_{numero}"].strip()
        self.senha = os.environ[f"TESTE_SENHA_{numero}"]
        self.cliente = novo_cliente()
        resposta = self.cliente.auth.sign_in_with_password(
            {"email": self.email, "password": self.senha})
        self.id = resposta.user.id


def entrar_ou_pular(numero):
    """Faz login com a conta de teste; se ela não existe mais, PULA em vez de dar erro.

    Acontece quando as contas de teste são apagadas do Supabase ou têm a senha
    trocada sem atualizar o .env. Pular com um aviso claro é melhor que uma
    pilha de erros que parece defeito do sistema.
    """
    try:
        return Usuario(numero)
    except Exception as erro:
        texto = f"{getattr(erro, 'code', '')} {erro}".lower()
        if "invalid" in texto and "credentials" in texto:
            pytest.skip(
                f"Testes reais pulados: a conta TESTE_EMAIL_{numero} não entra "
                "(foi apagada ou a senha mudou). Recrie-a no painel do Supabase, com "
                "Auto Confirm User, e atualize o .env (veja o CONFIG_SUPABASE.md)."
            )
        raise


@contextmanager
def como(usuario):
    """Faz as funções de core/db.py usarem a conexão deste usuário."""
    with patch("core.db.obter_cliente", return_value=usuario.cliente):
        yield


def apagar_dados_de_teste(usuario):
    usuario.cliente.table("orcamentos").delete().like("cliente_nome", f"{MARCA}%").execute()
    usuario.cliente.table("itens_catalogo").delete().like("nome", f"{MARCA}%").execute()


@pytest.fixture(scope="module")
def usuarios():
    u1, u2 = entrar_ou_pular(1), entrar_ou_pular(2)
    assert u1.id != u2.id, "Os dois usuários de teste precisam ser contas diferentes."
    for u in (u1, u2):
        apagar_dados_de_teste(u)   # sobras de uma execução interrompida
    yield u1, u2
    for u in (u1, u2):
        try:
            apagar_dados_de_teste(u)
            u.cliente.auth.sign_out({"scope": "local"})   # só a sessão do teste
        except Exception:
            pass


# ------------------------------------------------------------------- login
def test_login_devolve_sessao_valida(usuarios):
    u1, _ = usuarios
    sessao = u1.cliente.auth.get_session()
    assert sessao is not None and sessao.access_token and sessao.refresh_token
    assert sessao.user.email.lower() == u1.email.lower()


def test_login_com_senha_errada_e_recusado(usuarios):
    u1, _ = usuarios
    with pytest.raises(Exception):
        novo_cliente().auth.sign_in_with_password(
            {"email": u1.email, "password": "senha-errada-" + secrets.token_hex(4)})


def test_refresh_token_renova_a_sessao(usuarios):
    """O mecanismo que mantém o login ao recarregar a página."""
    _, u2 = usuarios
    token = u2.cliente.auth.get_session().refresh_token
    outra_conexao = novo_cliente()
    outra_conexao.auth.refresh_session(token)
    assert outra_conexao.auth.get_session().user.id == u2.id
    # A conexão do teste precisa do token novo para continuar valendo.
    u2.cliente.auth.set_session(
        outra_conexao.auth.get_session().access_token,
        outra_conexao.auth.get_session().refresh_token,
    )


# ------------------------------------------------------------------ perfil
def test_perfil_salvar_e_ler(usuarios):
    u1, _ = usuarios
    with como(u1):
        antes = db.buscar_perfil(u1.id)
        try:
            db.salvar_perfil(u1.id, f"{MARCA} Empresa", "27999990000", 15, None)
            lido = db.buscar_perfil(u1.id)
            assert lido["nome_empresa"] == f"{MARCA} Empresa"
            assert lido["telefone"] == "27999990000"
            assert lido["validade_dias"] == 15
        finally:
            db.salvar_perfil(u1.id, antes["nome_empresa"], antes["telefone"],
                             antes["validade_dias"], antes["logo_base64"])


# ---------------------------------------------------------------- catálogo
def test_catalogo_criar_editar_e_excluir(usuarios):
    u1, _ = usuarios
    nome = f"{MARCA} Dreno"
    with como(u1):
        db.inserir_itens_catalogo(u1.id, [
            {"nome": nome, "tipo": "peca", "custo": 10.0, "preco": 40.0}])
        item = next(i for i in db.listar_catalogo(u1.id) if i["nome"] == nome)
        assert float(item["preco"]) == 40.0

        db.atualizar_item_catalogo(u1.id, item["id"], nome, "peca", 12.5, 55.0)
        item = next(i for i in db.listar_catalogo(u1.id) if i["nome"] == nome)
        assert float(item["custo"]) == 12.5 and float(item["preco"]) == 55.0

        db.excluir_item_catalogo(u1.id, item["id"])
        assert not [i for i in db.listar_catalogo(u1.id) if i["nome"] == nome]


# -------------------------------------------------------------- orçamentos
def test_orcamento_salvar_ler_listar_e_excluir(usuarios):
    u1, _ = usuarios
    with como(u1):
        gravado = db.salvar_orcamento(u1.id, dict(DADOS), ITENS, TOTAL)
        assert isinstance(gravado["numero"], int) and gravado["numero"] >= 1

        lido = db.buscar_orcamento(u1.id, gravado["id"])
        assert lido["cliente_nome"] == DADOS["cliente_nome"]
        assert lido["numero"] == gravado["numero"]
        assert float(lido["total"]) == TOTAL
        assert float(lido["mao_de_obra"]) == 100.0
        assert lido["condicoes_pagamento"] == "Pix"
        assert sorted(i["nome"] for i in lido["itens"]) == ["Capacitor", "Limpeza"]

        lista = db.listar_orcamentos(u1.id)
        assert lista[0]["id"] == gravado["id"]      # o mais recente vem primeiro
        assert "criado_em" in lista[0]

        assert db.excluir_orcamento(u1.id, gravado["id"]) == 1
        assert db.buscar_orcamento(u1.id, gravado["id"]) is None
        sobras = (u1.cliente.table("itens_orcamento").select("id")
                  .eq("orcamento_id", gravado["id"]).execute())
        assert sobras.data == []                    # os itens foram junto


def test_numero_do_orcamento_e_sequencial(usuarios):
    u1, _ = usuarios
    with como(u1):
        primeiro = db.salvar_orcamento(u1.id, dict(DADOS), ITENS, TOTAL)
        segundo = db.salvar_orcamento(u1.id, dict(DADOS), ITENS, TOTAL)
        assert segundo["numero"] == primeiro["numero"] + 1


def test_banco_recusa_valores_invalidos(usuarios):
    u1, _ = usuarios
    with como(u1):
        with pytest.raises(Exception):
            db.salvar_orcamento(u1.id, dict(DADOS, mao_de_obra=-1), ITENS, TOTAL)
        with pytest.raises(Exception):
            db.salvar_orcamento(u1.id, dict(DADOS, cliente_nome=""), ITENS, TOTAL)
        with pytest.raises(Exception):
            db.salvar_orcamento(u1.id, dict(DADOS), ITENS, -5)


# ------------------------------------------- isolamento entre usuários (RLS)
def test_um_usuario_nao_ve_os_dados_do_outro(usuarios):
    u1, u2 = usuarios
    with como(u1):
        gravado = db.salvar_orcamento(u1.id, dict(DADOS), ITENS, TOTAL)
    orcamento_id = gravado["id"]

    # Pelas funções do app, mesmo "mentindo" o id do dono:
    with como(u2):
        assert db.buscar_orcamento(u2.id, orcamento_id) is None
        assert db.buscar_orcamento(u1.id, orcamento_id) is None
        assert orcamento_id not in [o["id"] for o in db.listar_orcamentos(u2.id)]
        assert orcamento_id not in [o["id"] for o in db.listar_orcamentos(u1.id)]
        assert db.excluir_orcamento(u1.id, orcamento_id) == 0

    # Falando direto com o banco, sem passar pelo app:
    tabela = u2.cliente.table("orcamentos")
    assert tabela.select("id").eq("id", orcamento_id).execute().data == []
    assert tabela.update({"total": 0}).eq("id", orcamento_id).execute().data == []
    assert tabela.delete().eq("id", orcamento_id).execute().data == []
    itens = u2.cliente.table("itens_orcamento").select("id").eq("orcamento_id", orcamento_id)
    assert itens.execute().data == []

    # O orçamento do usuário 1 continua intacto.
    with como(u1):
        assert float(db.buscar_orcamento(u1.id, orcamento_id)["total"]) == TOTAL


def test_usuario_nao_grava_em_nome_do_outro(usuarios):
    u1, u2 = usuarios
    with pytest.raises(Exception):
        u2.cliente.table("orcamentos").insert(
            {"cliente_nome": f"{MARCA} falso", "user_id": u1.id}).execute()
    with pytest.raises(Exception):
        u2.cliente.table("itens_catalogo").insert(
            {"nome": f"{MARCA} falso", "tipo": "peca", "user_id": u1.id}).execute()
    with pytest.raises(Exception):
        u2.cliente.table("perfis").upsert({"user_id": u1.id, "nome_empresa": "x"}).execute()


def test_visitante_sem_login_nao_ve_nada(usuarios):
    u1, _ = usuarios
    with como(u1):
        db.salvar_orcamento(u1.id, dict(DADOS), ITENS, TOTAL)
    visitante = novo_cliente()
    for tabela in ["orcamentos", "itens_orcamento", "itens_catalogo", "perfis"]:
        assert visitante.table(tabela).select("*").limit(5).execute().data == [], tabela
    with pytest.raises(Exception):
        visitante.table("orcamentos").insert({"cliente_nome": f"{MARCA} visitante"}).execute()


# ------------------------------------------------------------------ senhas
def test_trocar_a_senha_e_voltar_para_a_original(usuarios):
    u1, _ = usuarios
    provisoria = "Prov-" + secrets.token_urlsafe(12)
    u1.cliente.auth.update_user({"password": provisoria})
    try:
        # A senha antiga parou de valer e a nova funciona.
        with pytest.raises(Exception):
            novo_cliente().auth.sign_in_with_password({"email": u1.email, "password": u1.senha})
        conexao = novo_cliente()
        conexao.auth.sign_in_with_password({"email": u1.email, "password": provisoria})
        assert conexao.auth.get_session().user.id == u1.id
    finally:
        # Devolve a senha original, para os testes poderem rodar de novo.
        u1.cliente.auth.update_user({"password": u1.senha})
    novo_cliente().auth.sign_in_with_password({"email": u1.email, "password": u1.senha})


# ------------------------------------------------------------------ logout
def test_logout_encerra_a_sessao(usuarios):
    """Usa uma conexão própria, para não derrubar a dos outros testes.

    Depende de `usuarios` de propósito: se a conta 1 não existir, este teste
    também é pulado, em vez de entrar sozinho na conta 2.
    scope="local" encerra só ESTA sessão, sem derrubar outros aparelhos.
    """
    usuario = entrar_ou_pular(2)
    token_antigo = usuario.cliente.auth.get_session().refresh_token
    usuario.cliente.auth.sign_out({"scope": "local"})
    assert usuario.cliente.auth.get_session() is None
    assert usuario.cliente.table("orcamentos").select("id").limit(1).execute().data == []
    with pytest.raises(Exception):               # o refresh token antigo não serve mais
        novo_cliente().auth.refresh_session(token_antigo)


# ------------------------------------------------------- privacidade (LGPD)
def test_exportacao_anonimizacao_e_exclusao_em_lote(usuarios):
    from core import privacidade

    u1, u2 = usuarios
    with como(u1):
        a = db.salvar_orcamento(u1.id, dict(DADOS), ITENS, TOTAL)
        b = db.salvar_orcamento(u1.id, dict(DADOS), ITENS, TOTAL)

        completos = db.listar_orcamentos_completos(u1.id)
        do_teste = [o for o in completos if o["id"] in (a["id"], b["id"])]
        assert len(do_teste) == 2
        assert sorted(i["nome"] for i in do_teste[0]["itens"]) == ["Capacitor", "Limpeza"]

    # O outro usuário não consegue anonimizar nem apagar esses orçamentos.
    with como(u2):
        assert db.anonimizar_orcamentos(u2.id, [a["id"]], privacidade.DADOS_ANONIMOS) == 0
        assert db.anonimizar_orcamentos(u1.id, [a["id"]], privacidade.DADOS_ANONIMOS) == 0
        assert db.excluir_orcamentos(u1.id, [a["id"], b["id"]]) == 0

    with como(u1):
        assert db.anonimizar_orcamentos(u1.id, [a["id"]], privacidade.DADOS_ANONIMOS) == 1
        anonimo = db.buscar_orcamento(u1.id, a["id"])
        assert anonimo["cliente_nome"] == "Cliente removido"
        assert anonimo["cliente_telefone"] == "" and anonimo["equipamento"] == ""
        assert float(anonimo["total"]) == TOTAL          # os valores ficam
        assert len(anonimo["itens"]) == 2

        assert db.excluir_orcamentos(u1.id, [a["id"], b["id"]]) == 2
        assert db.buscar_orcamento(u1.id, b["id"]) is None


def test_aceite_da_politica_e_auditoria(usuarios):
    u1, u2 = usuarios
    versao = "teste-" + secrets.token_hex(4)      # versão única: o aceite não pode ser apagado
    with como(u1):
        assert db.aceitou_politica(u1.id, versao) is False
        db.registrar_aceite(u1.id, versao)
        assert db.aceitou_politica(u1.id, versao) is True
        assert versao in [a["versao_politica"] for a in db.listar_aceites(u1.id)]
        db.registrar_auditoria(u1.id, "exportar_conta", 3)
        minhas = u1.cliente.table("auditoria").select("acao").eq("user_id", u1.id).execute()
        assert "exportar_conta" in [linha["acao"] for linha in minhas.data]
    with como(u2):
        assert db.aceitou_politica(u1.id, versao) is False      # não enxerga o aceite do outro
    alheias = u2.cliente.table("auditoria").select("id").eq("user_id", u1.id).execute()
    assert alheias.data == []


def test_corrigir_dados_do_cliente(usuarios):
    u1, u2 = usuarios
    with como(u1):
        gravado = db.salvar_orcamento(u1.id, dict(DADOS), ITENS, TOTAL)
    correcao = {"cliente_nome": f"{MARCA} Maria Souza", "cliente_telefone": "27977776666",
                "total": 0, "numero": 9999}          # total e numero devem ser ignorados
    with como(u2):                                    # o outro usuário não corrige
        assert db.corrigir_dados_do_cliente(u2.id, gravado["id"], correcao) == 0
        assert db.corrigir_dados_do_cliente(u1.id, gravado["id"], correcao) == 0
    with como(u1):
        assert db.corrigir_dados_do_cliente(u1.id, gravado["id"], correcao) == 1
        lido = db.buscar_orcamento(u1.id, gravado["id"])
        assert lido["cliente_nome"] == f"{MARCA} Maria Souza"
        assert lido["cliente_telefone"] == "27977776666"
        assert float(lido["total"]) == TOTAL and lido["numero"] == gravado["numero"]
