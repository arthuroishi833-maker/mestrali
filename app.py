"""Ponto de entrada do app (equivalente ao main() em C).

Rodar com:  streamlit run app.py

O Streamlit executa este arquivo de cima para baixo a cada interação
do usuário (clique, digitação etc.). O que precisa sobreviver entre uma
execução e outra fica em st.session_state.
"""

import streamlit as st

from core import auth, db
from core.supabase_client import SEM_CONEXAO, chave_e_secreta, config_ok, ler_config
from telas import ajuda, catalogo, componentes, financeiro, historico, login, novo_orcamento, perfil, privacidade

# layout="centered" deixa a página estreita, boa para celular.
st.set_page_config(page_title="Orçamentos", page_icon=":material/ac_unit:", layout="centered")
componentes.aplicar_estilo()  # cores, fontes e tamanhos de todas as telas

# App de teste (Secrets: AMBIENTE = "teste"): uma faixa amarela em todas as telas,
# para ninguém confundir com o app dos técnicos. No app oficial, nada aparece.
if ler_config("AMBIENTE").lower() == "teste":
    componentes.faixa_de_teste()

# 1) Sem as chaves não há o que fazer: mostra a instrução e para aqui.
if not config_ok():
    st.error(
        "Configuração incompleta: defina SUPABASE_URL e SUPABASE_KEY no arquivo "
        ".env (veja o .env.example e o README)."
    )
    st.stop()
if chave_e_secreta():
    st.error(
        "Configuração insegura: SUPABASE_KEY está com a chave SECRETA do Supabase. "
        "Troque pela chave pública (\"publishable\" ou \"anon\"). O sistema não "
        "roda com a chave secreta, porque ela ignora a separação de dados entre contas."
    )
    st.stop()

# 2) Recarregou a página? Tenta entrar de novo pelo cookie de login.
if auth.restaurar_sessao() == auth.ESPERANDO_O_NAVEGADOR:
    # O navegador ainda não respondeu se há um login guardado (leva um instante).
    # O botão é a saída caso a resposta não chegue (JavaScript bloqueado, por exemplo).
    st.caption("Abrindo...")
    st.button("Ir para o login", type="tertiary", on_click=auth.desistir_de_esperar)
    st.stop()

# 3) Ninguém logado: mostra só a tela de login e para aqui.
user_id = auth.usuario_id()
if user_id is None:
    if "aviso_login" in st.session_state:
        st.warning(st.session_state.pop("aviso_login"))
    login.mostrar()
    auth.manter_cookie_em_dia()   # apaga o cookie se o usuário acabou de sair
    st.stop()

# 4) Banco de dados desatualizado: avisa como resolver, em vez de falhar depois.
#    Quando está tudo certo, a conferência é feita uma vez só por sessão.
banco_em_dia = st.session_state.get("banco_conferido", False)
try:
    if not banco_em_dia:
        if db.migracao_pendente():
            componentes.aviso_banco_desatualizado()
        else:
            banco_em_dia = st.session_state["banco_conferido"] = True

    # 5) Política de privacidade: sem o aceite da versão atual, não entra.
    #    (Com o banco desatualizado não há onde registrar o aceite; segue sem pedir.)
    falta_aceitar = banco_em_dia and privacidade.precisa_aceitar(user_id)
except Exception:
    # As duas conferências acima consultam o servidor. Se ele não responder
    # (internet fora do ar), explica e para, em vez de mostrar um erro genérico.
    st.error(SEM_CONEXAO.replace("tente de novo", "recarregue a página"))
    auth.manter_cookie_em_dia()
    st.stop()

if falta_aceitar:
    privacidade.mostrar_aceite(user_id)
    auth.manter_cookie_em_dia()
    st.stop()

# 6) Usuário logado: menu + tela escolhida.
# Títulos curtos: os cinco botões do menu precisam caber na tela do celular.
paginas_do_menu = [
    st.Page(novo_orcamento.mostrar, title="Novo", icon=":material/add_circle:", url_path="novo"),
    st.Page(historico.mostrar, title="Orçamentos", icon=":material/receipt_long:", url_path="orcamentos"),
    st.Page(financeiro.mostrar, title="Financeiro", icon=":material/payments:", url_path="financeiro"),
    st.Page(catalogo.mostrar, title="Catálogo", icon=":material/inventory_2:", url_path="catalogo"),
    st.Page(perfil.mostrar, title="Perfil", icon=":material/storefront:", url_path="perfil"),
]
# Ajuda e Privacidade existem, mas não ocupam lugar no menu: abrem pelo
# rodapé de qualquer tela e pelo Perfil.
pagina_ajuda = st.Page(ajuda.mostrar, title="Ajuda", icon=":material/help:", url_path="ajuda")
pagina_privacidade = st.Page(
    privacidade.mostrar, title="Privacidade", icon=":material/policy:", url_path="privacidade"
)
paginas_do_rodape = [pagina_ajuda, pagina_privacidade]
st.session_state["pagina_ajuda"] = pagina_ajuda
st.session_state["pagina_privacidade"] = pagina_privacidade

# position="hidden": o menu padrão some e usamos o nosso, sempre visível.
pagina = st.navigation(paginas_do_menu + paginas_do_rodape, position="hidden")
componentes.menu_principal(paginas_do_menu, pagina)

# Aviso deixado por uma tela antes de recarregar (ex.: "Perfil salvo.").
# A caixa existe sempre, com ou sem aviso: assim o aviso não empurra o resto da
# tela. Quando empurrava, o Streamlit deixava cópias apagadas (opacidade baixa)
# do item a cada salvamento no Catálogo.
caixa_do_aviso = st.container()
if "aviso" in st.session_state:
    caixa_do_aviso.success(st.session_state.pop("aviso"))

pagina.run()

componentes.rodape(paginas_do_rodape, pagina)

# Por último: mantém no navegador o cookie que preserva o login ao recarregar.
auth.manter_cookie_em_dia()
