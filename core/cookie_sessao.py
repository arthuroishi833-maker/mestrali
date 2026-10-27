"""Mantém o login depois de recarregar a página, usando um cookie.

Por que é preciso
-----------------
O Streamlit guarda o login na memória do servidor, ligado à conexão da
página. Recarregar (ou o celular bloquear a tela) cria uma conexão nova,
e o login se perdia.

Como funciona
-------------
  1. Depois do login, gravamos no navegador um cookie com o "refresh token"
     do Supabase: um código que serve só para pedir uma sessão nova.
  2. Ao abrir o app, lemos o cookie e pedimos essa sessão nova ao Supabase.
  3. A cada renovação o Supabase troca o refresh token (o antigo deixa de
     valer), então regravamos o cookie sempre que ele muda.
  4. Ao sair, apagamos o cookie e encerramos a sessão no Supabase.

O que NÃO vai para o cookie: senha e access token. Nada vai para a URL.

Sem biblioteca extra, de propósito
----------------------------------
Gravação: três linhas de JavaScript. Leitura, em dois degraus:

  1. st.context.cookies, do próprio Streamlit, que já vem pronto no
     primeiro carregamento (função ler).
  2. Se não veio nada, perguntamos ao navegador (função ler_pelo_navegador).
     É preciso porque o Streamlit Community Cloud NÃO repassa ao app os
     cookies que não são dele: lá o degrau 1 volta sempre vazio, e recarregar
     a página derrubava o login. A resposta do navegador chega um instante
     depois do primeiro desenho; enquanto isso o app mostra "Abrindo...".

As bibliotecas de cookie para Streamlit fazem o mesmo que o degrau 2, mas
seriam mais um código de terceiros com acesso ao token.

Limite conhecido
----------------
Um cookie gravado por JavaScript não pode ser "HttpOnly" (invisível a
scripts). Por isso ele guarda só o refresh token, leva "SameSite=Strict"
(não é enviado em visitas vindas de outros sites) e "Secure" (só trafega
por HTTPS) quando o app está publicado.
"""

import hashlib
import json
import re

import streamlit as st

NOME_COOKIE = "orc_sessao"
DIAS_LOGADO = 30
_FORMATO_TOKEN = re.compile(r"^[A-Za-z0-9_\-.]{8,512}$")


def ler():
    """Devolve o refresh token guardado no navegador, ou "" se não houver."""
    try:
        token = st.context.cookies.get(NOME_COOKIE, "")
    except Exception:
        return ""
    # Só aceita o formato esperado: o cookie é um dado que vem de fora.
    if not isinstance(token, str):
        return ""
    return token if _FORMATO_TOKEN.match(token) else ""


# O componente não desenha nada: só lê o cookie no navegador e devolve o valor.
# "-" quer dizer "não há cookie" (para diferenciar de "ainda não respondeu").
_JS_LEITOR = """
export default function (component) {
  const nome = component.data.nome + "=";
  const achado = document.cookie.split("; ").find((c) => c.startsWith(nome));
  const valor = achado ? decodeURIComponent(achado.slice(nome.length)) : "-";
  // Responde uma vez só: repetir a mesma resposta faria o app se redesenhar à toa.
  if (window.__cookieJaLido === valor) return;
  window.__cookieJaLido = valor;
  component.setStateValue("lido", valor);
}
"""


def ler_pelo_navegador():
    """Pede o cookie ao navegador. Devolve None enquanto a resposta não chegou;
    depois, o refresh token (ou "" se não houver cookie válido).

    Quem chama precisa parar o desenho da tela enquanto vier None: quando o
    navegador responde, o Streamlit roda o app de novo sozinho.
    """
    leitor = st.components.v2.component("leitor_do_cookie", html="<span></span>", js=_JS_LEITOR)
    resposta = leitor(key="leitor_do_cookie", data={"nome": NOME_COOKIE}, on_lido_change=lambda: None)
    lido = getattr(resposta, "lido", None)
    if lido is None:
        return None
    # O valor vem de fora: só aceita o formato esperado.
    if not isinstance(lido, str) or not _FORMATO_TOKEN.match(lido):
        return ""
    return lido


def _rodar_js(codigo):
    st.html(f"<script>{codigo}</script>", unsafe_allow_javascript=True)


def gravar(token):
    """Grava (ou regrava) o cookie no navegador.

    O token entra num trecho de JavaScript. Por garantia, só é gravado se
    tiver o formato esperado (letras, números, "_", "-" e "."): assim nenhum
    valor inesperado consegue virar código executado na página.
    """
    if not isinstance(token, str) or not _FORMATO_TOKEN.match(token):
        return
    # json.dumps coloca o token entre aspas com segurança dentro do JavaScript.
    _rodar_js(
        f"document.cookie = '{NOME_COOKIE}=' + encodeURIComponent({json.dumps(token)})"
        f" + '; path=/; max-age={DIAS_LOGADO * 24 * 60 * 60}; SameSite=Strict'"
        " + (location.protocol === 'https:' ? '; Secure' : '');"
    )


def apagar():
    """Apaga o cookie do navegador."""
    _rodar_js(
        f"document.cookie = '{NOME_COOKIE}=; path=/; max-age=0; SameSite=Strict'"
        " + (location.protocol === 'https:' ? '; Secure' : '');"
    )


def limpar_tokens_do_endereco():
    """Tira da barra de endereço os tokens que o link de confirmação de e-mail deixa.

    Ao confirmar o e-mail, o Supabase devolve a pessoa para o app com
    "#access_token=...&refresh_token=..." no fim do endereço. O app não usa
    esses tokens (a pessoa entra com e-mail e senha), mas eles ficariam à
    vista na barra de endereço e gravados no histórico do navegador, e um
    refresh token nunca usado continua valendo. Roda uma vez por sessão.

    O script é fixo: nenhum dado digitado entra nele. Em hospedagens que
    mostram o app dentro de uma moldura (Streamlit Cloud), o endereço que
    aparece é o da janela de fora; por isso as três janelas são conferidas.
    """
    if st.session_state.get("endereco_conferido"):
        return
    st.session_state["endereco_conferido"] = True
    # A limpeza é repetida algumas vezes nos primeiros segundos: ao terminar de
    # carregar, o próprio Streamlit pode regravar o endereço.
    #
    # ATENÇÃO ao mexer neste script: ele não pode ter os caracteres < > nem &.
    # O Streamlit trata o HTML antes de executar o JavaScript, e com eles o
    # script deixa de rodar sem dar nenhum erro (por isso "j.indexOf(x) < 0" e
    # "a && b" foram evitados). O teste em tests/test_telas.py confere.
    _rodar_js(
        "(function(){function limpar(){[window,window.parent,window.top].forEach(function(w){"
        "try{var l=w.location;if(/(access_token|refresh_token|error_code)=/.test(l.hash)){"
        "w.history.replaceState(null,'',l.pathname+l.search);}}catch(e){}});}"
        "limpar();[150,600,1500,3000,6000].forEach(function(t){setTimeout(limpar,t);});})();"
    )


def abrir_espaco_para_selos():
    """Sobe o menu do celular quando a hospedagem põe selos no canto da tela.

    O Streamlit Cloud mostra dois selos fixos no canto de baixo, à direita
    (a foto de quem publicou e o logotipo do Streamlit). No celular eles
    ficavam em cima das últimas abas do menu. Os selos estão na janela de
    fora, que não é nossa: em vez de mexer neles, medimos a altura que eles
    ocupam e guardamos em "--folga-da-hospedagem". O CSS do menu
    (telas/componentes.py) soma essa folga embaixo das abas.

    Fora do Streamlit Cloud não há selo e a folga fica em zero. Roda uma vez
    por sessão. O script é fixo e, como o de cima, não pode ter < > nem &.
    """
    if st.session_state.get("selos_medidos"):
        return
    st.session_state["selos_medidos"] = True
    _rodar_js(
        "(function(){function medir(){var folga=0;[window.parent,window.top].forEach(function(w){"
        "try{var selo=w.document.querySelector('[class*=viewerBadge]');"
        "if(selo){var r=selo.getBoundingClientRect();"
        "if(r.height){folga=Math.max(folga,Math.round(w.innerHeight-r.top));}}}catch(e){}});"
        "document.documentElement.style.setProperty('--folga-da-hospedagem',folga+'px');}"
        "medir();[500,1500,4000,8000].forEach(function(t){setTimeout(medir,t);});})();"
    )


def impressao_digital(token):
    """Resumo do token, para saber se ele mudou sem guardar outra cópia dele."""
    return hashlib.sha256(token.encode()).hexdigest()
