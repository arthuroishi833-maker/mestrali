"""Botões de compartilhar um orçamento: baixar o PDF e abrir o WhatsApp.

Usado na tela "Orçamento salvo" e nos detalhes de "Meus orçamentos".
"""

import streamlit as st

from core.pdf import gerar_pdf, nome_arquivo
from core.whatsapp import montar_mensagem
from telas import mensagem_whatsapp


def mostrar_botoes(perfil, dados, itens, resumo, data):
    """Mostra "Baixar PDF", a mensagem (editável) e "Abrir WhatsApp"."""
    try:
        pdf = gerar_pdf(perfil, dados, itens, resumo, data)
    except Exception:
        st.error("Não foi possível gerar o PDF. O orçamento continua salvo.")
        return

    st.download_button(
        "1. Baixar o PDF",
        data=pdf,
        file_name=nome_arquivo(dados["cliente_nome"], data),
        mime="application/pdf",
        type="primary",
        width="stretch",
        icon=":material/download:",
    )
    # A mensagem já vem pronta (a do Perfil, se o técnico gravou uma; senão a
    # padrão) e pode ser ajustada aqui só para este envio.
    mensagem_whatsapp.mostrar(
        dados["cliente_telefone"],
        montar_mensagem(perfil, dados, resumo, data),
        chave=f"mensagem_{dados.get('id') or dados.get('numero') or 'novo'}",
    )
    st.caption(
        "O WhatsApp abre com o texto preenchido, mas não anexa arquivos: "
        "depois de abrir a conversa, anexe o PDF que você baixou. "
        "Para mudar a mensagem de todos os orçamentos, vá em Perfil."
    )
    if not dados["cliente_telefone"]:
        st.caption("Este orçamento não tem telefone: escolha o contato dentro do WhatsApp.")
