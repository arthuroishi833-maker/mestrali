"""Tela de Ajuda: perguntas frequentes e os contatos do suporte.

Duas entradas:
  - mostrar(): a página Ajuda, para quem está logado
  - mostrar_antes_do_login(): versão curta, na página inicial, com as
    dúvidas de acesso (é quando a pessoa mais precisa e ainda não entrou)

Os textos e os contatos ficam em core/suporte.py.
"""

import streamlit as st

from core import suporte
from telas import componentes


def _contatos(prefixo):
    """Mostra como falar com o suporte. `prefixo` diferencia as chaves dos cartões."""
    if not suporte.contato_configurado():
        st.info("O canal de atendimento ainda está sendo configurado. Volte em breve.")
        return
    with componentes.cartao(f"{prefixo}_contato"):
        st.markdown("**Fale com o suporte**")
        if suporte.horario_do_suporte():
            st.caption(f"Atendimento: {suporte.horario_do_suporte()}")
        if suporte.link_do_whatsapp():
            st.link_button(
                f"Chamar no WhatsApp {suporte.whatsapp_formatado()}",
                suporte.link_do_whatsapp(),
                type="primary", width="stretch", icon=":material/chat:",
            )
        if suporte.email_do_suporte():
            # Os contatos vêm do código (core/suporte.py), não de quem usa o sistema.
            st.markdown(f"E-mail: **{suporte.email_do_suporte()}**")


def _perguntas(antes_do_login, recolhidas=True):
    """Lista as perguntas. recolhidas=False escreve tudo aberto (para usar dentro
    de outro bloco que já abre e fecha, pois eles não podem ficar um dentro do outro)."""
    for pergunta, resposta in suporte.perguntas(antes_do_login):
        if recolhidas:
            with st.expander(pergunta):
                st.markdown(resposta)
        else:
            st.markdown(f"**{pergunta}**")
            st.markdown(resposta)


def mostrar():
    """Página Ajuda (usuário logado)."""
    st.header("Ajuda")
    st.caption("Respostas rápidas para as dúvidas mais comuns. Não achou? Fale com a gente.")
    _contatos("ajuda")
    st.subheader("Perguntas frequentes")
    _perguntas(antes_do_login=False)


def mostrar_antes_do_login():
    """Bloco de ajuda da página inicial: só as dúvidas de quem não conseguiu entrar."""
    with st.expander("Precisa de ajuda para entrar?", icon=":material/help:"):
        _perguntas(antes_do_login=True, recolhidas=False)
        _contatos("inicio")
