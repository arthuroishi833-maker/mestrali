"""Lê as chaves do Supabase e cria o cliente de conexão.

As chaves vêm de um destes lugares (nunca do código):
  - st.secrets  -> quando o app está publicado
  - arquivo .env -> quando roda no seu computador
"""

import base64
import json
import os
from urllib.parse import urlparse

import httpx
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client
from supabase_auth.errors import AuthRetryableError

# Carrega o arquivo .env (se existir) para dentro das variáveis de ambiente.
load_dotenv()


def ler_config(nome: str) -> str:
    """Devolve o valor de uma configuração, ou "" se não estiver definida."""
    try:
        if nome in st.secrets:
            return str(st.secrets[nome]).strip()
    except Exception:
        # Não existe secrets.toml: normal ao rodar localmente com .env.
        pass
    return os.getenv(nome, "").strip()


def url_supabase() -> str:
    """Devolve só "https://xxxx.supabase.co".

    O painel do Supabase às vezes mostra a URL com "/rest/v1/" no final;
    se ela for colada assim no .env, a parte extra é descartada aqui.
    """
    partes = urlparse(ler_config("SUPABASE_URL"))
    if not partes.netloc:
        return ""
    return f"{partes.scheme}://{partes.netloc}"


def config_ok() -> bool:
    """True se a URL e a chave do Supabase estão preenchidas de verdade."""
    url = url_supabase()
    chave = ler_config("SUPABASE_KEY")
    # Os textos do .env.example não contam como configuração.
    if "SEU-PROJETO" in url or "sua-chave" in chave:
        return False
    return url.startswith("https://") and bool(chave)


def chave_e_secreta(chave=None) -> bool:
    """True se a chave configurada parece ser a SECRETA do Supabase.

    A chave secreta ("sb_secret_..." ou a antiga "service_role") ignora o Row
    Level Security: com ela, o banco deixaria de separar os dados de cada
    técnico. O app só pode rodar com a chave pública ("publishable"/"anon").
    Esta conferência existe para um engano de configuração não passar em branco.
    """
    chave = ler_config("SUPABASE_KEY") if chave is None else chave
    if chave.startswith("sb_secret_"):
        return True
    partes = chave.split(".")
    if len(partes) != 3:
        return False
    try:   # chave no formato antigo (JWT): o papel vem escrito no meio dela
        carga = json.loads(base64.urlsafe_b64decode(partes[1] + "=" * (-len(partes[1]) % 4)))
        return carga.get("role") == "service_role"
    except Exception:
        return False


def obter_cliente() -> Client:
    """Devolve o cliente Supabase da sessão atual.

    O cliente fica em st.session_state, que é separado para cada pessoa
    usando o app. Assim o login de um técnico nunca se mistura com o de outro.
    (Não use cache global aqui!)
    """
    if "supabase" not in st.session_state:
        cliente = create_client(url_supabase(), ler_config("SUPABASE_KEY"))
        manter_login_nas_consultas(cliente)
        st.session_state["supabase"] = cliente
    return st.session_state["supabase"]


def manter_login_nas_consultas(cliente):
    """Garante que as consultas ao banco levem sempre o token de quem está logado.

    A biblioteca do Supabase só atualiza o "crachá" das consultas em três
    avisos (entrou, renovou o token, saiu). Em qualquer outro, como
    USER_UPDATED (alterar algo na conta), ela troca o crachá pela chave
    PÚBLICA. Se o cliente de banco for recriado nesse intervalo, o usuário
    continua logado mas o banco o trata como visitante, e o Row Level
    Security recusa tudo.

    Este "ouvinte" roda depois do da biblioteca, em todo aviso que traga uma
    sessão, e devolve o token dela ao crachá.
    """
    def ao_mudar(_evento, sessao):
        token = getattr(sessao, "access_token", None)
        if token:
            cliente.options.headers["Authorization"] = f"Bearer {token}"
            cliente.postgrest.auth(token)

    cliente.auth.on_auth_state_change(ao_mudar)


SEM_CONEXAO = "Não foi possível falar com o servidor. Verifique a internet e tente de novo."


def sem_conexao(erro) -> bool:
    """True se o erro foi de REDE (sem internet, tempo esgotado, servidor fora do ar).

    Serve para não confundir "a internet caiu" com "o servidor recusou":
    senha errada e código inválido são recusas; queda de rede não é.
    """
    return isinstance(erro, (httpx.TransportError, AuthRetryableError))
