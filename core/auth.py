"""Login, cadastro, logout e troca de senha usando o Supabase Auth.

SENHAS: este sistema nunca guarda nem registra senhas. Elas são enviadas
por HTTPS ao Supabase Auth, que armazena apenas o hash bcrypt (com salt
individual). Nenhuma função daqui escreve a senha em log, em mensagem de
erro ou no banco de dados do aplicativo.

O Supabase devolve um "token" de sessão depois do login.
Esse token fica dentro do cliente (core/supabase_client.py) e é enviado
automaticamente em cada consulta ao banco: é por ele que o Row Level
Security sabe quem é o usuário.
"""

import re
import time

import streamlit as st

from core import cookie_sessao, tentativas, verificar_email
from core.supabase_client import SEM_CONEXAO, obter_cliente, sem_conexao
from core.validacao import validar_senha


def usuario_id():
    """Devolve o id do usuário logado, ou None se ninguém está logado."""
    try:
        sessao = obter_cliente().auth.get_session()  # renova o token se venceu
    except Exception:
        return None
    if sessao is None or sessao.user is None:
        return None
    return sessao.user.id


def usuario_email():
    try:
        sessao = obter_cliente().auth.get_session()
        return sessao.user.email if sessao else ""
    except Exception:
        return ""


def ler_marcador(nome):
    """Lê uma anotação guardada junto da conta do usuário (ou None).

    O Supabase permite guardar pequenos dados na própria conta
    ("user_metadata"). Usamos isso para lembrar, por exemplo, que o
    catálogo inicial já foi criado.
    """
    try:
        sessao = obter_cliente().auth.get_session()
        return (sessao.user.user_metadata or {}).get(nome)
    except Exception:
        return None


def gravar_marcador(nome, valor):
    obter_cliente().auth.update_user({"data": {nome: valor}})


def entrar(email, senha):
    """Tenta fazer login. Devolve "" se deu certo, ou a mensagem de erro."""
    # Freio contra força bruta (veja core/tentativas.py).
    estado = st.session_state.setdefault("login_tentativas", {})
    espera = tentativas.segundos_bloqueado(estado, time.time())
    if espera:
        return f"Muitas tentativas. Aguarde {espera} segundos e tente de novo."
    try:
        obter_cliente().auth.sign_in_with_password({"email": email, "password": senha})
    except Exception as erro:
        if sem_conexao(erro):
            # A internet caiu: não é senha errada e não conta como tentativa.
            return SEM_CONEXAO
        if "not confirmed" in str(erro).lower():
            return "Confirme seu e-mail pelo link que enviamos antes de entrar."
        tentativas.registrar_falha(estado, time.time())
        # Mensagem genérica de propósito: não revela se o e-mail existe.
        return "E-mail ou senha incorretos."
    tentativas.registrar_sucesso(estado)
    return ""


def _reafirmar_login(cliente):
    """Refaz o "crachá" do usuário nas consultas ao banco depois de update_user.

    A biblioteca do Supabase, ao receber o evento USER_UPDATED (que update_user
    dispara), troca o cabeçalho de autorização pela chave PÚBLICA. Se o cliente
    de banco for criado depois disso, as consultas seguem como "anônimas" e o
    Row Level Security as recusa: o usuário está logado, mas o banco não o
    reconhece. Aqui o token da sessão atual volta ao cabeçalho.
    """
    try:
        sessao = cliente.auth.get_session()
    except Exception:
        return
    if sessao is None or not sessao.access_token:
        return
    cliente.options.headers["Authorization"] = f"Bearer {sessao.access_token}"
    cliente.postgrest.auth(sessao.access_token)


def trocar_senha(senha_atual, senha_nova):
    """Troca a senha do usuário logado. Devolve "" ou a mensagem de erro.

    Confere a senha atual antes: se alguém pegar o celular desbloqueado,
    não consegue trocar a senha sem saber a antiga.
    """
    _, erro = validar_senha(senha_nova)   # última conferência antes de enviar
    if erro:
        return erro
    email = usuario_email()
    if not email:
        return "Sua sessão expirou. Entre de novo."
    erro = entrar(email, senha_atual)
    if erro:
        return "Senha atual incorreta." if "incorretos" in erro else erro
    try:
        cliente = obter_cliente()
        cliente.auth.update_user({"password": senha_nova})
    except Exception as erro:
        return (_erro_de_senha_fraca(erro)
                or "Não foi possível trocar a senha. Escolha uma senha diferente da atual.")
    _reafirmar_login(cliente)
    return ""


def pedir_codigo_de_senha(email):
    """Pede ao Supabase que envie o e-mail de redefinição de senha.

    Não devolve erro de propósito: a resposta é sempre a mesma, exista ou
    não uma conta com esse e-mail (para não revelar quem é cliente).
    """
    try:
        obter_cliente().auth.reset_password_for_email(email)
    except Exception:
        pass


def redefinir_senha(email, codigo, senha_nova):
    """Confere o código recebido por e-mail e grava a senha nova.

    Devolve "" se deu certo (o usuário já fica logado), ou a mensagem de erro.
    """
    _, erro = validar_senha(senha_nova)   # confere ANTES de gastar o código do e-mail
    if erro:
        return erro
    estado = st.session_state.setdefault("login_tentativas", {})
    espera = tentativas.segundos_bloqueado(estado, time.time())
    if espera:
        return f"Muitas tentativas. Aguarde {espera} segundos e tente de novo."
    cliente = obter_cliente()
    try:
        cliente.auth.verify_otp({"email": email, "token": codigo, "type": "recovery"})
    except Exception as erro:
        if sem_conexao(erro):
            return SEM_CONEXAO   # o código não foi conferido: continua valendo
        tentativas.registrar_falha(estado, time.time())
        return "Código incorreto ou vencido. Peça um novo código."
    try:
        cliente.auth.update_user({"password": senha_nova})
    except Exception as erro:
        # O código já foi aceito e abriu uma sessão, mas a senha NÃO mudou.
        # Sem encerrar essa sessão, a tela diria "não foi possível" e, no clique
        # seguinte, a pessoa apareceria dentro do sistema com a senha antiga.
        try:
            cliente.auth.sign_out({"scope": "local"})   # só esta sessão
        except Exception:
            pass
        if sem_conexao(erro):
            return SEM_CONEXAO.replace("tente de novo", "peça um novo código")
        return (_erro_de_senha_fraca(erro)
                or "Não foi possível gravar a senha nova. Peça um novo código e "
                   "escolha uma senha diferente da anterior.")
    _reafirmar_login(cliente)   # sem isto, o banco recusaria a próxima consulta
    tentativas.registrar_sucesso(estado)
    return ""


def _erro_de_senha_fraca(erro):
    """Mensagem para quando o SERVIDOR recusa a senha (regras do painel do Supabase)."""
    texto = f"{getattr(erro, 'code', '')} {erro}".lower()
    if "weak_password" in texto or "password should" in texto:
        return ("A senha foi recusada pelo servidor por ser fraca ou muito conhecida. "
                "Escolha outra, com letras maiúsculas e minúsculas, um número e um "
                "caractere especial (@ # $ % &).")
    return ""


# Devolvido por cadastrar() quando o e-mail já tem conta. A tela reconhece
# este valor e leva a pessoa para a aba Entrar.
EMAIL_JA_CADASTRADO = "Já existe uma conta com este e-mail."


def _ja_cadastrado(resposta=None, erro=None):
    """O Supabase avisa de dois jeitos que o e-mail já tem conta.

    - Com "Confirm email" ligado (o padrão): não dá erro, mas devolve um
      usuário "de mentira", sem nenhuma identidade ligada a ele.
    - Com "Confirm email" desligado: devolve o erro user_already_exists.
    """
    if erro is not None:
        texto = f"{getattr(erro, 'code', '')} {erro}".lower()
        return "user_already_exists" in texto or "already registered" in texto
    usuario = getattr(resposta, "user", None)
    return usuario is not None and getattr(usuario, "identities", None) == []


LIMITE_DE_EMAILS = (
    "O limite de e-mails de confirmação por hora foi atingido. "
    "Aguarde cerca de uma hora e tente de novo."
)


def _limite_de_envio(erro):
    """True se o Supabase recusou por excesso de e-mails ou de tentativas."""
    texto = f"{getattr(erro, 'code', '')} {erro}".lower()
    return ("rate_limit" in texto or "rate limit" in texto or "too many" in texto
            or _segundos_de_espera(erro) is not None)


def _segundos_de_espera(erro):
    """Segundos que o Supabase pediu para esperar ("after 47 seconds"), ou None.

    Acontece ao pedir outro e-mail para o MESMO endereço em menos de um minuto.
    """
    achado = re.search(r"after (\d{1,4}) seconds?", str(erro).lower())
    return int(achado.group(1)) if achado else None


def _erro_de_cadastro(erro):
    """Mensagem para um cadastro recusado por motivo que o app não previu.

    Explica os casos conhecidos e, nos demais, mostra o CÓDIGO técnico do erro
    (ex.: "unexpected_failure"). O código não tem dado pessoal e é o que
    permite achar a causa nos registros do Supabase.
    """
    codigo = str(getattr(erro, "code", "") or "").strip()
    texto = f"{codigo} {erro}".lower()
    if "sending" in texto or "smtp" in texto or "unexpected_failure" in texto:
        return ("Sua conta não pôde ser criada porque o e-mail de confirmação não saiu. "
                "Tente de novo em alguns minutos."
                + (f" (código: {codigo})" if codigo else ""))
    if "email_address_invalid" in texto or "email address" in texto and "invalid" in texto:
        return "Esse endereço de e-mail não foi aceito. Confira se está certo ou use outro."
    if "signup_disabled" in texto or "signups not allowed" in texto:
        return "Novos cadastros estão desativados no momento."
    detalhe = f" (código: {codigo})" if codigo and len(codigo) <= 40 else ""
    return "Não foi possível criar a conta. Tente novamente em instantes." + detalhe


def cadastrar(email, senha):
    """Cria a conta. Devolve (erro, precisa_confirmar_email).

    erro == EMAIL_JA_CADASTRADO quando o e-mail já tem conta.
    """
    # Última conferência antes de enviar: mesmo que a tela falhe, senha fraca não passa.
    _, erro = validar_senha(senha)
    if erro:
        return erro, False
    # O domínio do e-mail existe e recebe mensagens? (barra "gmail.con" e inventados)
    erro = verificar_email.erro_de_dominio(email)
    if erro:
        return erro, False
    try:
        resposta = obter_cliente().auth.sign_up({"email": email, "password": senha})
    except Exception as erro:
        if _ja_cadastrado(erro=erro):
            return EMAIL_JA_CADASTRADO, False
        espera = _segundos_de_espera(erro)
        if espera is not None:
            return (f"Um e-mail de confirmação já foi pedido para este endereço agora há pouco. "
                    f"Aguarde {espera} segundos e tente de novo, ou procure a mensagem "
                    "na caixa de entrada e no spam."), False
        if _limite_de_envio(erro):
            return LIMITE_DE_EMAILS, False
        mensagem = _erro_de_senha_fraca(erro)
        return mensagem or _erro_de_cadastro(erro), False
    if _ja_cadastrado(resposta=resposta):
        return EMAIL_JA_CADASTRADO, False
    # Se o Supabase exige confirmação por e-mail, a sessão vem vazia.
    return "", resposta.session is None


def sair():
    """Encerra a sessão no Supabase e apaga o que estava guardado no app."""
    try:
        obter_cliente().auth.sign_out()   # invalida o refresh token no servidor
    except Exception:
        pass
    st.session_state.clear()
    # O cookie é apagado no próximo desenho da tela (manter_cookie_em_dia).
    st.session_state["cookie_apagar"] = True
    # A página ainda "enxerga" o cookie antigo até recarregar: não tente usá-lo.
    st.session_state["cookie_conferido"] = True


ESPERANDO_O_NAVEGADOR = "esperando"


def _desenhar_de_novo():
    st.rerun()


def restaurar_sessao():
    """Se há um cookie de login válido, entra de novo sem pedir senha.

    Roda uma vez por conexão da página (ao abrir ou recarregar).

    Devolve ESPERANDO_O_NAVEGADOR quando o cookie ainda está sendo lido pelo
    navegador (veja core/cookie_sessao.py): nesse caso o app mostra
    "Abrindo..." e para; o Streamlit roda de novo quando a resposta chega.
    """
    estado = st.session_state
    if estado.get("cookie_conferido"):
        return None
    if "cookie_do_navegador" in estado:
        token = estado.pop("cookie_do_navegador")      # a resposta guardada no desenho anterior
    else:
        token = cookie_sessao.ler()
        if not token:
            token = cookie_sessao.ler_pelo_navegador()
            if token is None:
                return ESPERANDO_O_NAVEGADOR
            # A resposta chegou. Guarda e desenha a tela de novo, agora SEM o leitor
            # do cookie na página. Se ele ficasse ali, um login que demora mais de um
            # segundo deixava a tela de login "fantasma" por cima do sistema.
            estado["cookie_do_navegador"] = token
            _desenhar_de_novo()
            return ESPERANDO_O_NAVEGADOR
    estado["cookie_conferido"] = True
    if not token:
        return None
    try:
        # Pede uma sessão nova; o Supabase devolve também um refresh token novo.
        obter_cliente().auth.refresh_session(token)
    except Exception as erro:
        if sem_conexao(erro):
            # A internet falhou: o cookie continua bom. Mostra o login agora e
            # tenta de novo no próximo carregamento da página.
            return None
        # Token vencido, já usado ou inválido: limpa o cookie e pede login.
        st.session_state["cookie_apagar"] = True
    return None


def desistir_de_esperar():
    """A pessoa pediu para ir direto ao login, sem esperar o navegador."""
    st.session_state["cookie_conferido"] = True


def manter_cookie_em_dia():
    """Grava, regrava ou apaga o cookie conforme o estado do login.

    Chamada a cada desenho da tela; só mexe no cookie quando algo mudou.
    Como é sempre a última coisa da tela, é daqui que sai também a limpeza do
    endereço (uma vez por sessão): um script no fim da página não ocupa espaço
    no topo nem faz o conteúdo "pular".
    """
    # O link de confirmação do e-mail deixa tokens de acesso no endereço da página.
    cookie_sessao.limpar_tokens_do_endereco()
    cookie_sessao.abrir_espaco_para_selos()
    estado = st.session_state
    if estado.pop("cookie_apagar", False):
        cookie_sessao.apagar()
        estado.pop("cookie_gravado", None)
        return
    try:
        sessao = obter_cliente().auth.get_session()
    except Exception:
        return
    if sessao is None or not sessao.refresh_token:
        return
    digital = cookie_sessao.impressao_digital(sessao.refresh_token)
    if estado.get("cookie_gravado") != digital:
        cookie_sessao.gravar(sessao.refresh_token)
        estado["cookie_gravado"] = digital
