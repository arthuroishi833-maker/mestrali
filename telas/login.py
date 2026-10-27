"""Página inicial: apresentação do sistema, login e cadastro.

Aparece quando ninguém está logado.
"""

import time

import streamlit as st

from core import auth
from core.validacao import validar_codigo, validar_email, validar_senha
from core.formato import escapar_md
from core.privacidade import FINALIDADE_CADASTRO
from telas import ajuda, componentes, privacidade
from telas.campo_senha import campo_senha, campo_senha_nova

BENEFICIOS = [
    (":material/bolt:", "Rápido no celular",
     "Passo a passo simples, com botões grandes, feito para usar no local do serviço."),
    (":material/savings:", "Seu lucro na hora",
     "Veja custo, lucro e margem antes de fechar. O cliente nunca vê esses números."),
    (":material/picture_as_pdf:", "PDF com a sua marca",
     "Orçamento com logo e contato, pronto para enviar pelo WhatsApp."),
]


def mostrar():
    # Três blocos com nome (key). No celular ficam um embaixo do outro, nesta
    # ordem. No computador o CSS de telas/componentes.py os arruma em duas
    # colunas: apresentação à esquerda e o acesso à direita, sempre à vista.
    with st.container(key="inicio"):
        with st.container(key="inicio_abertura"):
            componentes.destaque_inicial()
        with st.container(key="inicio_acesso"):
            _acesso()
        with st.container(key="inicio_mais"):
            st.subheader("Por que usar")
            # Lista simples, sem caixas: três frases curtas não precisam de três cartões.
            for icone, titulo, texto in BENEFICIOS:
                st.markdown(f"{icone} **{titulo}**  \n{texto}")
            st.caption(
                "Seus dados ficam separados por conta: cada técnico vê apenas os próprios orçamentos."
            )
            privacidade.mostrar_politica_resumida()


def _acesso():
    """Entrar, criar conta e recuperar a senha."""
    st.subheader("Acesse sua conta", anchor="acesso")
    # Trocar a chave das abas faz o Streamlit redesenhá-las na aba padrão
    # ("Entrar"). É assim que levamos para lá quem tentou criar uma conta
    # com um e-mail que já tem cadastro.
    aba_entrar, aba_cadastrar = st.tabs(
        ["Entrar", "Criar conta"], default="Entrar", key=f"abas_acesso_{_rodada('abas')}"
    )
    with aba_entrar:
        _formulario_entrar()
    with aba_cadastrar:
        if "aviso_cadastro" in st.session_state:
            st.success(st.session_state.pop("aviso_cadastro"))
        _formulario_cadastrar()
    ajuda.mostrar_antes_do_login()


def _formulario_entrar():
    # Pediu o código? A tela de login dá lugar à do código, para o mesmo e-mail.
    email_do_codigo = st.session_state.get(_EMAIL_DO_CODIGO)
    if email_do_codigo:
        _passo_do_codigo(email_do_codigo)
        return

    # Veio da aba "Criar conta" com um e-mail que já tem cadastro?
    email_conhecido = st.session_state.get("entrar_com_email", "")
    if email_conhecido:
        st.info(
            f"Já existe uma conta com o e-mail **{escapar_md(email_conhecido)}**. "
            "Entre com a sua senha. Se não lembra dela, toque em **Esqueci minha senha**, logo abaixo."
        )
    # st.form agrupa os campos: o app só processa quando o botão é clicado.
    with st.form("form_entrar"):
        email = st.text_input("E-mail", max_chars=254, value=email_conhecido)
        senha = st.text_input("Senha", type="password", max_chars=72)
        enviar = st.form_submit_button(
            "Entrar", type="primary", width="stretch", icon=":material/login:"
        )
        # Fica no mesmo formulário de propósito: ao tocar, o e-mail digitado
        # acima segue junto e não é preciso escrevê-lo de novo.
        esqueci = st.form_submit_button(
            "Esqueci minha senha", type="tertiary", width="stretch",
            icon=":material/lock_reset:",
        )
    if esqueci:
        _pedir_codigo(email)
        return
    if not enviar:
        return
    email, erro = validar_email(email)
    if not erro and not senha:
        erro = "Informe a senha."
    if not erro:
        with st.spinner("Entrando..."):
            erro = auth.entrar(email, senha)
    if erro:
        st.error(erro)
    else:
        st.session_state.pop("entrar_com_email", None)
        st.rerun()  # recarrega a página, agora logado


def _rodada(nome):
    """Número que entra nas chaves dos campos; aumentar esvazia os campos."""
    return st.session_state.get(f"rodada_{nome}", 0)


# Prefixo das chaves dos campos de cada grupo (para apagar as senhas da memória).
_PREFIXOS = {"cadastro": "cad_", "redefinir": "red_"}


def _limpar_campos(nome):
    """Esvazia os campos do grupo e apaga da memória o que foi digitado neles."""
    n = _rodada(nome)
    prefixo = _PREFIXOS.get(nome)
    if prefixo:
        for chave in list(st.session_state.keys()):
            if chave.startswith(prefixo) and chave.endswith(f"_{n}"):
                del st.session_state[chave]
    st.session_state[f"rodada_{nome}"] = n + 1


def _formulario_cadastrar():
    # Sem st.form aqui: a barra de força precisa reagir enquanto a pessoa digita.
    n = _rodada("cadastro")
    email = st.text_input("E-mail", max_chars=254, key=f"cad_email_{n}")
    senha = campo_senha_nova("Crie uma senha", f"cad_senha_{n}")
    senha2 = campo_senha("Repita a senha", f"cad_senha2_{n}")
    st.caption(
        FINALIDADE_CADASTRO + " No primeiro acesso você verá a Política de "
        "Privacidade e só continua se aceitar."
    )
    enviar = st.button(
        "Criar minha conta", type="primary", width="stretch", icon=":material/person_add:",
        key="cad_enviar",
    )
    if not enviar:
        return
    email, erro = validar_email(email)
    if not erro:
        senha, erro = validar_senha(senha)
    if not erro and senha != senha2:
        erro = "As senhas não são iguais."
    if erro:
        st.error(erro)
        return
    with st.spinner("Criando sua conta..."):
        erro, precisa_confirmar = auth.cadastrar(email, senha)
    if erro == auth.EMAIL_JA_CADASTRADO:
        # Leva para a aba Entrar, com o e-mail já preenchido e sem a senha na tela.
        st.session_state["entrar_com_email"] = email
        _limpar_campos("cadastro")
        _limpar_campos("abas")
        st.rerun()
    elif erro:
        st.error(erro)
    elif precisa_confirmar:
        st.session_state["aviso_cadastro"] = (
            "Conta criada! Enviamos um link de confirmação para o seu e-mail. "
            "Se não aparecer em alguns minutos, olhe também a caixa de **spam**. "
            "Depois de confirmar, entre pela aba Entrar."
        )
        _limpar_campos("cadastro")   # tira a senha da tela
        st.rerun()
    else:
        st.rerun()


# E-mail para o qual o código de redefinição foi pedido (vale só nesta sessão).
_EMAIL_DO_CODIGO = "redefinir_email_do_codigo"
# Quando o último código foi pedido. O servidor ignora um segundo pedido para o
# mesmo e-mail em menos de um minuto; a tela espera esse tempo antes de reenviar.
_HORA_DO_PEDIDO = "redefinir_hora_do_pedido"
_ULTIMO_EMAIL = "redefinir_ultimo_email"
INTERVALO_ENTRE_CODIGOS = 60   # segundos


def _pedir_codigo(email):
    """"Esqueci minha senha": envia o código para o e-mail digitado no login."""
    if not (email or "").strip():
        st.error("Digite o seu e-mail no campo acima e toque em Esqueci minha senha.")
        return
    email, erro = validar_email(email)
    if erro:
        st.error(erro)
        return
    estado = st.session_state
    recente = time.time() - estado.get(_HORA_DO_PEDIDO, 0) < INTERVALO_ENTRE_CODIGOS
    if not (recente and estado.get(_ULTIMO_EMAIL) == email):
        # (Mesmo e-mail em menos de um minuto: o servidor ignoraria o pedido;
        # a pessoa segue para a tela do código, que continua valendo.)
        with st.spinner("Enviando o código..."):
            auth.pedir_codigo_de_senha(email)
        estado[_HORA_DO_PEDIDO] = time.time()
        estado[_ULTIMO_EMAIL] = email
    estado[_EMAIL_DO_CODIGO] = email
    st.session_state.pop("entrar_com_email", None)
    st.rerun()


def _passo_do_codigo(email):
    """Código recebido por e-mail + senha nova.

    O e-mail vem do login e não pode ser trocado aqui: o código só é conferido
    para o endereço que o recebeu.
    """
    n = _rodada("redefinir")
    # Mesma mensagem exista ou não a conta: não revela quem é cliente.
    st.info(
        f"Se existir uma conta com o e-mail **{escapar_md(email)}**, o código chega "
        "em instantes. Olhe também a caixa de spam."
    )
    codigo = st.text_input("Código recebido por e-mail", max_chars=12, key=f"red_codigo_{n}")
    senha = campo_senha_nova("Senha nova", f"red_senha_{n}")
    senha2 = campo_senha("Repita a senha nova", f"red_senha2_{n}")
    usar = st.button(
        "Gravar senha nova", type="primary", width="stretch", icon=":material/check:",
        key="red_enviar",
    )

    coluna1, coluna2 = st.columns(2)
    reenviar = coluna1.button("Reenviar código", width="stretch", icon=":material/refresh:",
                              key="red_reenviar")
    voltar = coluna2.button("Voltar ao login", width="stretch", icon=":material/arrow_back:",
                            key="red_voltar")
    if voltar:
        _limpar_campos("redefinir")
        st.session_state.pop(_EMAIL_DO_CODIGO, None)
        st.rerun()   # (a hora do pedido fica: voltar e pedir de novo não burla a espera)
    if reenviar:
        falta = int(st.session_state.get(_HORA_DO_PEDIDO, 0) + INTERVALO_ENTRE_CODIGOS - time.time() + 0.999)
        if falta > 0:
            # Sem esta espera a tela diria "pedimos outro código" enquanto o
            # servidor, na verdade, ignorava o pedido.
            st.warning(f"Aguarde {falta} segundos para pedir outro código. O que já foi enviado continua valendo.")
        else:
            auth.pedir_codigo_de_senha(email)
            st.session_state[_HORA_DO_PEDIDO] = time.time()
            st.success("Pedimos um novo código. Use o mais recente que chegar.")
    if not usar:
        return

    codigo, erro = validar_codigo(codigo)
    if not erro:
        senha, erro = validar_senha(senha)
    if not erro and senha != senha2:
        erro = "As senhas não são iguais."
    if not erro:
        with st.spinner("Gravando..."):
            erro = auth.redefinir_senha(email, codigo, senha)
    if erro:
        st.error(erro)
    else:
        _limpar_campos("redefinir")
        st.session_state.pop(_EMAIL_DO_CODIGO, None)
        st.session_state["aviso"] = "Senha alterada. Você já está dentro."
        st.rerun()
