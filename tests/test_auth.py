"""Testes de core/auth.py com um Supabase falso (mock). Rodar com: pytest"""

from unittest.mock import MagicMock, patch

import pytest
import streamlit as st

from core import auth
from core.tentativas import MAX_FALHAS

SENHA = "Segredo@Teste9"   # forte: passa pelas regras de senha nova


@pytest.fixture(autouse=True)
def estado_limpo():
    st.session_state.clear()
    yield
    st.session_state.clear()


@pytest.fixture(autouse=True)
def dns_falso():
    """Os testes não consultam a internet: todo domínio "existe", salvo indicação."""
    with patch("core.verificar_email.dominio_recebe_email", return_value=True) as falso:
        yield falso


def cliente_falso(login_ok=True):
    cliente = MagicMock()
    if not login_ok:
        cliente.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")
    return cliente


def test_login_correto():
    with patch("core.auth.obter_cliente", return_value=cliente_falso()):
        assert auth.entrar("a@b.com", SENHA) == ""


def test_login_errado_tem_mensagem_generica_e_sem_a_senha():
    with patch("core.auth.obter_cliente", return_value=cliente_falso(login_ok=False)):
        erro = auth.entrar("a@b.com", SENHA)
    assert erro == "E-mail ou senha incorretos."
    assert SENHA not in erro


def test_bloqueia_depois_de_varias_falhas_sem_chamar_o_servidor():
    cliente = cliente_falso(login_ok=False)
    with patch("core.auth.obter_cliente", return_value=cliente):
        for _ in range(MAX_FALHAS):
            auth.entrar("a@b.com", "errada")
        chamadas = cliente.auth.sign_in_with_password.call_count
        erro = auth.entrar("a@b.com", "errada")
    assert "Muitas tentativas" in erro
    assert cliente.auth.sign_in_with_password.call_count == chamadas  # nem tentou


def test_trocar_senha_exige_a_senha_atual_correta():
    cliente = cliente_falso(login_ok=False)
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.auth.usuario_email", return_value="a@b.com"):
        assert auth.trocar_senha("errada", SENHA) == "Senha atual incorreta."
    cliente.auth.update_user.assert_not_called()


def test_trocar_senha_com_a_atual_correta():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.auth.usuario_email", return_value="a@b.com"):
        assert auth.trocar_senha("atual-correta", SENHA) == ""
    cliente.auth.update_user.assert_called_once_with({"password": SENHA})


def test_pedir_codigo_nao_revela_se_a_conta_existe():
    cliente = cliente_falso()
    cliente.auth.reset_password_for_email.side_effect = Exception("User not found")
    with patch("core.auth.obter_cliente", return_value=cliente):
        assert auth.pedir_codigo_de_senha("naoexiste@b.com") is None  # sem erro


def test_redefinir_senha_com_codigo_errado_nao_grava_nada():
    cliente = cliente_falso()
    cliente.auth.verify_otp.side_effect = Exception("Token has expired or is invalid")
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro = auth.redefinir_senha("a@b.com", "000000", SENHA)
    assert "Código incorreto" in erro and SENHA not in erro
    cliente.auth.update_user.assert_not_called()


def test_redefinir_senha_com_codigo_certo():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente):
        assert auth.redefinir_senha("a@b.com", "123456", SENHA) == ""
    cliente.auth.verify_otp.assert_called_once_with(
        {"email": "a@b.com", "token": "123456", "type": "recovery"})
    cliente.auth.update_user.assert_called_once_with({"password": SENHA})


# ------------------------------------------- login que sobrevive à recarga
TOKEN = "abcDEF123456"


def test_restaura_a_sessao_a_partir_do_cookie():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.cookie_sessao.ler", return_value=TOKEN):
        auth.restaurar_sessao()
        auth.restaurar_sessao()   # segunda chamada na mesma conexão não repete
    cliente.auth.refresh_session.assert_called_once_with(TOKEN)


def test_sem_cookie_nao_chama_o_servidor():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.auth._desenhar_de_novo"), \
         patch("core.cookie_sessao.ler", return_value=""), \
         patch("core.cookie_sessao.ler_pelo_navegador", return_value=""):
        auth.restaurar_sessao()                       # recebe a resposta e pede novo desenho
        assert auth.restaurar_sessao() is None
    cliente.auth.refresh_session.assert_not_called()


def test_hospedagem_que_nao_repassa_o_cookie_espera_o_navegador_e_depois_entra():
    # No Streamlit Community Cloud o cookie não chega pelo servidor: quem responde é o navegador.
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.auth._desenhar_de_novo") as de_novo, \
         patch("core.cookie_sessao.ler", return_value=""), \
         patch("core.cookie_sessao.ler_pelo_navegador", side_effect=[None, TOKEN]) as navegador:
        assert auth.restaurar_sessao() == auth.ESPERANDO_O_NAVEGADOR   # ainda sem resposta
        assert auth.restaurar_sessao() == auth.ESPERANDO_O_NAVEGADOR   # chegou: guarda e redesenha
        de_novo.assert_called_once()
        cliente.auth.refresh_session.assert_not_called()
        assert auth.restaurar_sessao() is None                         # desenho sem o leitor na página
        assert navegador.call_count == 2                               # o leitor não é montado de novo
    cliente.auth.refresh_session.assert_called_once_with(TOKEN)


def test_quem_desiste_de_esperar_vai_para_o_login():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.cookie_sessao.ler", return_value=""), \
         patch("core.cookie_sessao.ler_pelo_navegador", return_value=None) as navegador:
        assert auth.restaurar_sessao() == auth.ESPERANDO_O_NAVEGADOR
        auth.desistir_de_esperar()
        assert auth.restaurar_sessao() is None
    assert navegador.call_count == 1
    cliente.auth.refresh_session.assert_not_called()


def test_resposta_do_navegador_so_vale_no_formato_de_token():
    from types import SimpleNamespace
    from core import cookie_sessao

    for lido, esperado in ((None, None), ("-", ""), ("<script>", ""), (123, ""), (TOKEN, TOKEN)):
        componente = lambda **_: SimpleNamespace(lido=lido)
        with patch("core.cookie_sessao.st") as st_falso:
            st_falso.components.v2.component.return_value = componente
            assert cookie_sessao.ler_pelo_navegador() == esperado, repr(lido)


def test_cookie_vencido_e_apagado():
    cliente = cliente_falso()
    cliente.auth.refresh_session.side_effect = Exception("Invalid Refresh Token")
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.cookie_sessao.ler", return_value=TOKEN), \
         patch("core.cookie_sessao.apagar") as apagar:
        auth.restaurar_sessao()
        auth.manter_cookie_em_dia()
    apagar.assert_called_once()


def test_grava_o_cookie_so_quando_o_token_muda():
    cliente = cliente_falso()
    cliente.auth.get_session.return_value.refresh_token = TOKEN
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.cookie_sessao.gravar") as gravar:
        auth.manter_cookie_em_dia()
        auth.manter_cookie_em_dia()                       # mesmo token: não regrava
        assert gravar.call_count == 1
        cliente.auth.get_session.return_value.refresh_token = "novoTOKEN98765"
        auth.manter_cookie_em_dia()                       # token trocado: regrava
    assert [c.args[0] for c in gravar.call_args_list] == [TOKEN, "novoTOKEN98765"]
    assert TOKEN not in str(dict(st.session_state))       # o token não fica na memória do app


def test_sair_apaga_o_cookie_e_nao_entra_de_novo_sozinho():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.cookie_sessao.ler", return_value=TOKEN), \
         patch("core.cookie_sessao.apagar") as apagar:
        auth.sair()
        auth.restaurar_sessao()       # a página ainda enxerga o cookie antigo
        auth.manter_cookie_em_dia()
    cliente.auth.sign_out.assert_called_once()
    cliente.auth.refresh_session.assert_not_called()
    apagar.assert_called_once()


def test_cookie_com_formato_estranho_e_ignorado():
    from core import cookie_sessao

    for ruim in ["", "curto", "tem espaco aqui", "<script>alert(1)</script>", "a';x=1;//", "x" * 600]:
        with patch.object(cookie_sessao.st, "context") as contexto:
            contexto.cookies = {cookie_sessao.NOME_COOKIE: ruim}
            assert cookie_sessao.ler() == "", ruim
    with patch.object(cookie_sessao.st, "context") as contexto:
        contexto.cookies = {cookie_sessao.NOME_COOKIE: TOKEN}
        assert cookie_sessao.ler() == TOKEN


# ------------------------------------- senha fraca não chega ao Supabase
FRACAS = ["casa@2024", "CASA@2024", "Casa2024", "Casa@Verde", "Abcd@xyz", "Xy@1234z", "Ab@1"]


def test_cadastro_com_senha_fraca_nao_chama_o_servidor():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente):
        for fraca in FRACAS:
            erro, _ = auth.cadastrar("a@b.com", fraca)
            assert erro.startswith("Sua senha"), fraca
    cliente.auth.sign_up.assert_not_called()


def test_troca_e_redefinicao_com_senha_fraca_nao_chamam_o_servidor():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.auth.usuario_email", return_value="a@b.com"):
        for fraca in FRACAS:
            assert auth.trocar_senha("atual", fraca).startswith("Sua senha"), fraca
            assert auth.redefinir_senha("a@b.com", "123456", fraca).startswith("Sua senha"), fraca
    cliente.auth.update_user.assert_not_called()
    cliente.auth.verify_otp.assert_not_called()          # nem gasta o código do e-mail
    cliente.auth.sign_in_with_password.assert_not_called()


def test_cadastro_com_senha_forte_chega_ao_servidor():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro, _ = auth.cadastrar("a@b.com", "Casa@2024")
    assert erro == ""
    cliente.auth.sign_up.assert_called_once_with({"email": "a@b.com", "password": "Casa@2024"})


def test_recusa_do_servidor_por_senha_fraca_tem_mensagem_clara():
    cliente = cliente_falso()
    cliente.auth.sign_up.side_effect = Exception("weak_password: Password should contain a digit")
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro, _ = auth.cadastrar("a@b.com", "Casa@Forte7")
    assert "recusada pelo servidor" in erro and "Casa@Forte7" not in erro


# ------------------------------------------ e-mail inexistente ou repetido
def test_dominio_sem_servidor_de_email_bloqueia_o_cadastro(dns_falso):
    dns_falso.return_value = False
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro, _ = auth.cadastrar("maria@gmail.con", "Casa@2024")
    assert "@gmail.con" in erro and "Confira se digitou certo" in erro
    cliente.auth.sign_up.assert_not_called()


def test_dns_fora_do_ar_nao_impede_o_cadastro(dns_falso):
    dns_falso.return_value = None      # não deu para saber
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro, _ = auth.cadastrar("maria@gmail.com", "Casa@2024")
    assert erro == ""
    cliente.auth.sign_up.assert_called_once()


def test_email_ja_cadastrado_com_confirmacao_ligada():
    cliente = cliente_falso()
    cliente.auth.sign_up.return_value.user.identities = []     # usuário "de mentira"
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro, precisa_confirmar = auth.cadastrar("maria@gmail.com", "Casa@2024")
    assert erro == auth.EMAIL_JA_CADASTRADO and precisa_confirmar is False


def test_email_ja_cadastrado_com_confirmacao_desligada():
    cliente = cliente_falso()
    cliente.auth.sign_up.side_effect = Exception("user_already_exists: User already registered")
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro, _ = auth.cadastrar("maria@gmail.com", "Casa@2024")
    assert erro == auth.EMAIL_JA_CADASTRADO


def test_email_novo_nao_e_confundido_com_ja_cadastrado():
    cliente = cliente_falso()
    cliente.auth.sign_up.return_value.user.identities = [object()]   # conta nova de verdade
    cliente.auth.sign_up.return_value.session = None
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro, precisa_confirmar = auth.cadastrar("nova@gmail.com", "Casa@2024")
    assert erro == "" and precisa_confirmar is True


def test_limite_de_emails_do_supabase_tem_mensagem_clara():
    cliente = cliente_falso()
    cliente.auth.sign_up.side_effect = Exception("over_email_send_rate_limit: email rate limit exceeded")
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro, _ = auth.cadastrar("maria@gmail.com", "Casa@2024")
    assert erro == auth.LIMITE_DE_EMAILS


def test_cookie_com_valor_que_nao_e_texto_e_ignorado():
    from core import cookie_sessao

    for estranho in [None, 123, b"abcdefgh12", ["abcdefgh12"], object()]:
        with patch.object(cookie_sessao.st, "context") as contexto:
            contexto.cookies = {cookie_sessao.NOME_COOKIE: estranho}
            assert cookie_sessao.ler() == "", repr(estranho)


# -------------------------------------- queda de internet não é senha errada
def test_sem_internet_no_login_nao_diz_senha_errada_nem_bloqueia():
    import httpx

    from core.supabase_client import SEM_CONEXAO

    cliente = cliente_falso()
    cliente.auth.sign_in_with_password.side_effect = httpx.ConnectError("sem rede")
    with patch("core.auth.obter_cliente", return_value=cliente):
        for _ in range(MAX_FALHAS + 3):                 # mais vezes que o limite do bloqueio
            assert auth.entrar("a@b.com", SENHA) == SEM_CONEXAO
        # a rede voltou e a senha está certa: entra normalmente, sem bloqueio
        cliente.auth.sign_in_with_password.side_effect = None
        assert auth.entrar("a@b.com", SENHA) == ""


def test_tempo_esgotado_tambem_conta_como_falha_de_rede():
    import httpx

    from core.supabase_client import SEM_CONEXAO, sem_conexao
    from supabase_auth.errors import AuthApiError, AuthRetryableError

    assert sem_conexao(httpx.ReadTimeout("demorou"))
    assert sem_conexao(AuthRetryableError("servidor fora do ar", 503))
    assert not sem_conexao(AuthApiError("Invalid login credentials", 400, "invalid_credentials"))
    assert not sem_conexao(ValueError("outro erro"))
    assert "internet" in SEM_CONEXAO


def test_sem_internet_ao_conferir_o_codigo_nao_queima_tentativa():
    import httpx

    from core.supabase_client import SEM_CONEXAO

    cliente = cliente_falso()
    cliente.auth.verify_otp.side_effect = httpx.ConnectError("sem rede")
    with patch("core.auth.obter_cliente", return_value=cliente):
        for _ in range(MAX_FALHAS + 2):
            assert auth.redefinir_senha("a@b.com", "123456", SENHA) == SEM_CONEXAO
    cliente.auth.update_user.assert_not_called()


def test_senha_atual_errada_continua_sendo_recusa():
    cliente = cliente_falso(login_ok=False)
    with patch("core.auth.obter_cliente", return_value=cliente):
        assert auth.entrar("a@b.com", "errada") == "E-mail ou senha incorretos."


def test_sem_internet_ao_abrir_o_app_nao_apaga_o_cookie_de_login():
    import httpx

    cliente = cliente_falso()
    cliente.auth.refresh_session.side_effect = httpx.ConnectError("sem rede")
    cliente.auth.get_session.return_value = None        # ninguém logado nesta abertura
    with patch("core.auth.obter_cliente", return_value=cliente), \
         patch("core.cookie_sessao.ler", return_value=TOKEN), \
         patch("core.cookie_sessao.apagar") as apagar:
        auth.restaurar_sessao()
        auth.manter_cookie_em_dia()
    apagar.assert_not_called()                           # o cookie sobrevive à queda de rede
    assert "cookie_apagar" not in st.session_state


# --------------------- redefinição: código aceito, mas a senha não foi gravada
def test_se_a_senha_nova_nao_for_gravada_a_sessao_do_codigo_e_encerrada():
    cliente = cliente_falso()
    cliente.auth.update_user.side_effect = Exception("same_password: New password should be different")
    with patch("core.auth.obter_cliente", return_value=cliente):
        erro = auth.redefinir_senha("a@b.com", "123456", SENHA)
    assert erro and SENHA not in erro
    cliente.auth.verify_otp.assert_called_once()
    cliente.auth.sign_out.assert_called_once_with({"scope": "local"})   # não fica logado


def test_redefinicao_bem_sucedida_nao_encerra_a_sessao():
    cliente = cliente_falso()
    with patch("core.auth.obter_cliente", return_value=cliente):
        assert auth.redefinir_senha("a@b.com", "123456", SENHA) == ""
    cliente.auth.sign_out.assert_not_called()                         # continua dentro


def test_cookie_so_e_gravado_com_token_no_formato_esperado():
    from core import cookie_sessao

    with patch("core.cookie_sessao._rodar_js") as rodar_js:
        for estranho in ["</script><script>alert(1)</script>", "a';alert(1);//", "x y z 12345",
                         "", None, 12345678, "curto"]:
            cookie_sessao.gravar(estranho)
        rodar_js.assert_not_called()                 # nada vira JavaScript
        cookie_sessao.gravar(TOKEN)
        rodar_js.assert_called_once()
        assert TOKEN in rodar_js.call_args.args[0]


# ---- o banco precisa reconhecer o usuário depois de trocar/redefinir a senha
def _cliente_de_verdade_com_sessao():
    """Cliente real da biblioteca (sem rede), já com uma sessão salva."""
    from supabase import create_client
    from supabase_auth.types import Session, User

    cliente = create_client("https://abc.supabase.co", "chave-publica-123")
    usuario = User(id="00000000-0000-0000-0000-000000000001", app_metadata={},
                   user_metadata={}, aud="authenticated", created_at="2026-01-01T00:00:00Z")
    sessao = Session(access_token="TOKEN-DO-USUARIO", refresh_token="r", expires_in=3600,
                     token_type="bearer", user=usuario)
    cliente.auth._save_session(sessao)
    return cliente, sessao


def test_reafirmar_login_devolve_o_token_do_usuario_ao_banco():
    cliente, sessao = _cliente_de_verdade_com_sessao()
    # O que update_user faz por dentro: avisa USER_UPDATED, e a biblioteca
    # troca o cabeçalho pela chave pública.
    cliente.auth._notify_all_subscribers("USER_UPDATED", sessao)
    assert cliente.postgrest.headers["Authorization"] == "Bearer chave-publica-123"

    auth._reafirmar_login(cliente)
    assert cliente.postgrest.headers["Authorization"] == "Bearer TOKEN-DO-USUARIO"


def test_trocar_e_redefinir_senha_reafirmam_o_login():
    for chamar in (
        lambda: auth.redefinir_senha("a@b.com", "123456", SENHA),
        lambda: auth.trocar_senha(SENHA, "Outra@Senha77"),
    ):
        cliente, sessao = _cliente_de_verdade_com_sessao()
        st.session_state["login_tentativas"] = {}
        # verify_otp / sign_in / update_user simulados, com o evento verdadeiro.
        cliente.auth.verify_otp = lambda *_: cliente.auth._notify_all_subscribers("SIGNED_IN", sessao)
        cliente.auth.sign_in_with_password = lambda *_: cliente.auth._notify_all_subscribers("SIGNED_IN", sessao)
        cliente.auth.update_user = lambda *_: cliente.auth._notify_all_subscribers("USER_UPDATED", sessao)
        with patch("core.auth.obter_cliente", return_value=cliente), \
             patch("core.auth.usuario_email", return_value="a@b.com"):
            assert chamar() == ""
        assert cliente.postgrest.headers["Authorization"] == "Bearer TOKEN-DO-USUARIO"


def test_cadastro_recusado_mostra_o_codigo_tecnico_sem_dados_pessoais():
    class ErroDoSupabase(Exception):
        def __init__(self, code, mensagem):
            super().__init__(mensagem)
            self.code = code

    casos = [
        (ErroDoSupabase("unexpected_failure", "Error sending confirmation email"),
         "e-mail de confirmação não saiu", "unexpected_failure"),
        (ErroDoSupabase("email_address_invalid", "Email address is invalid"),
         "endereço de e-mail não foi aceito", None),
        (ErroDoSupabase("coisa_nova", "algo que o app nao previu"),
         "Não foi possível criar a conta", "coisa_nova"),
    ]
    for erro, trecho, codigo in casos:
        cliente = cliente_falso()
        cliente.auth.sign_up.side_effect = erro
        with patch("core.auth.obter_cliente", return_value=cliente):
            mensagem, _ = auth.cadastrar("ana@exemplo.com", SENHA)
        assert trecho in mensagem
        if codigo:
            assert f"(código: {codigo})" in mensagem
        assert "ana@exemplo.com" not in mensagem and SENHA not in mensagem


def test_cadastro_repetido_em_menos_de_um_minuto_diz_quantos_segundos_esperar():
    cliente = cliente_falso()
    cliente.auth.sign_up.side_effect = Exception(
        "For security purposes, you can only request this after 47 seconds.")
    with patch("core.auth.obter_cliente", return_value=cliente):
        mensagem, precisa = auth.cadastrar("ana@exemplo.com", SENHA)
    assert "47 segundos" in mensagem and "hora" not in mensagem
    assert precisa is False


def test_cliente_do_app_nao_perde_o_login_das_consultas_em_nenhum_aviso():
    """A proteção de core/supabase_client.py, com a biblioteca de verdade (sem rede)."""
    from core.supabase_client import manter_login_nas_consultas

    cliente, sessao = _cliente_de_verdade_com_sessao()
    manter_login_nas_consultas(cliente)
    avisar = cliente.auth._notify_all_subscribers

    # Pior caso: o token é renovado e, sem nenhuma consulta no meio, a conta é
    # alterada (é o que acontece dentro de update_user). Sem a proteção, a
    # consulta seguinte iria com a chave pública.
    avisar("TOKEN_REFRESHED", sessao)
    avisar("USER_UPDATED", sessao)
    assert cliente.postgrest.headers["Authorization"] == "Bearer TOKEN-DO-USUARIO"
    # ...e é esse o cabeçalho que uma consulta de verdade leva:
    consulta = cliente.table("orcamentos").select("*")
    assert consulta.request.headers.get("Authorization") == "Bearer TOKEN-DO-USUARIO"

    avisar("PASSWORD_RECOVERY", sessao)
    assert cliente.postgrest.headers["Authorization"] == "Bearer TOKEN-DO-USUARIO"

    # Ao sair, as consultas voltam a ser de visitante (chave pública).
    avisar("SIGNED_OUT", None)
    assert cliente.postgrest.headers["Authorization"] == "Bearer chave-publica-123"


def test_chave_secreta_e_reconhecida_nos_dois_formatos():
    import base64, json
    from core.supabase_client import chave_e_secreta

    def jwt(papel):
        meio = base64.urlsafe_b64encode(json.dumps({"role": papel, "iss": "supabase"}).encode()).decode().rstrip("=")
        return f"cabecalho.{meio}.assinatura"

    assert chave_e_secreta("sb_secret_abc123")
    assert chave_e_secreta(jwt("service_role"))
    assert not chave_e_secreta("sb_publishable_abc123")
    assert not chave_e_secreta(jwt("anon"))
    assert not chave_e_secreta("")
    assert not chave_e_secreta("a.b.c")                  # parece JWT, mas não dá para ler: não trava o app
