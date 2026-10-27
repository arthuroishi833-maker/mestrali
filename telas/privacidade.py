"""Privacidade (LGPD): aceite da política, exportação e exclusão de dados.

Três partes:
  - mostrar_aceite(): tela que pede o aceite da política antes de usar o sistema
  - mostrar_politica_resumida(): a política e o contato, para a página inicial
  - mostrar(): a página "Privacidade", com as rotinas dos direitos do titular

Cada pessoa só alcança os próprios dados: todas as consultas passam pelo
filtro de usuário e pelo Row Level Security. Por isso não existe aqui uma
"tela de administrador": ninguém, pelo aplicativo, consegue exportar ou
apagar dados de outra conta. Cada exportação ou exclusão é anotada na
tabela auditoria (quem, o quê, quantos, quando), sem dados pessoais.
"""

import json

import streamlit as st

from core import auth, db, privacidade
from core.formato import escapar_md, hoje_brasil
from core.validacao import MAX_NOME
from telas import componentes

PALAVRA_DE_CONFIRMACAO = "EXCLUIR"


def _para_json(dados):
    """Converte para o texto do arquivo .json (legível, com acentos)."""
    return json.dumps(dados, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _avisar_pendencias():
    """Lembra o dono do sistema de que faltam informações jurídicas na política."""
    faltando = privacidade.pendencias()
    if faltando:
        st.warning(
            "Política incompleta: faltam informações que só o responsável pelo "
            f"sistema pode preencher ({len(faltando)} campos marcados como PREENCHER "
            "em `core/privacidade.py`). Não ofereça o sistema a usuários reais antes disso."
        )


# ------------------------------------------------------------------ aceite
def precisa_aceitar(user_id):
    """True se o usuário ainda não aceitou a versão atual da política.

    Quando o aceite já existe, a consulta é feita uma vez só por sessão.
    """
    if st.session_state.get("aceite_ok") == privacidade.VERSAO_POLITICA:
        return False
    if db.aceitou_politica(user_id, privacidade.VERSAO_POLITICA):
        st.session_state["aceite_ok"] = privacidade.VERSAO_POLITICA
        return False
    return True


def _registrar_aceite(user_id):
    """Grava o aceite. True se ele ficou registrado.

    O banco só guarda um aceite por versão. Se a gravação "falhar" porque o
    aceite já estava lá (toque duplo, outra aba, resposta que se perdeu na
    rede), o resultado para o usuário é o mesmo: está aceito.
    """
    try:
        db.registrar_aceite(user_id, privacidade.VERSAO_POLITICA)
        return True
    except Exception:
        try:
            return db.aceitou_politica(user_id, privacidade.VERSAO_POLITICA)
        except Exception:
            return False


def mostrar_aceite(user_id):
    """Tela que bloqueia o uso até a política ser aceita."""
    st.header("Antes de continuar")
    st.markdown(
        "Para usar o sistema, leia e aceite a Política de Privacidade. "
        "Ela explica quais dados guardamos, para quê e com quem são compartilhados."
    )
    _avisar_pendencias()
    with componentes.cartao("politica_aceite"):
        st.markdown(privacidade.texto_da_politica())

    with st.form("form_aceite"):
        aceito = st.checkbox(
            f"Li e aceito a Política de Privacidade (versão {privacidade.VERSAO_POLITICA})."
        )
        continuar = st.form_submit_button(
            "Aceitar e continuar", type="primary", width="stretch", icon=":material/check:"
        )
    if continuar:
        if not aceito:
            st.error("Marque a caixa para confirmar que leu e aceita a política.")
        else:
            if _registrar_aceite(user_id):
                st.session_state["aceite_ok"] = privacidade.VERSAO_POLITICA
                st.rerun()
            else:
                st.error("Não foi possível registrar o aceite. Tente novamente.")

    st.caption("Não concorda? Você pode sair agora; nenhum dado além do seu e-mail foi guardado.")
    if st.button("Sair", icon=":material/logout:"):
        auth.sair()
        st.rerun()


def mostrar_politica_resumida():
    """Política e contato, recolhidos, para a página inicial (antes do login)."""
    with st.expander("Política de Privacidade", icon=":material/policy:"):
        st.markdown(privacidade.texto_da_politica())
    with st.expander("Contato de privacidade", icon=":material/mail:"):
        st.markdown(privacidade.texto_do_contato())


# ------------------------------------------------------------------ página
def mostrar():
    st.header("Privacidade e seus dados")
    st.caption("Veja a política, baixe uma cópia dos seus dados ou apague o que quiser.")
    _avisar_pendencias()
    user_id = auth.usuario_id()

    with st.expander("Política de Privacidade", icon=":material/policy:"):
        st.markdown(privacidade.texto_da_politica())
    with st.expander("Contato de privacidade", icon=":material/mail:"):
        st.markdown(privacidade.texto_do_contato())

    st.subheader("Seus dados")
    _exportar_conta(user_id)

    st.subheader("Pedido de um cliente")
    st.caption(
        "Um cliente pediu para ver ou apagar os dados dele? Procure pelo nome ou "
        "pelo telefone e escolha o que fazer."
    )
    _pedido_de_cliente(user_id)

    st.subheader("Excluir minha conta")
    _excluir_conta()


def _exportar_conta(user_id):
    st.markdown("Baixe um arquivo com tudo que o sistema guarda sobre você e seus orçamentos.")
    if st.button("Preparar meu arquivo", width="stretch", icon=":material/folder_zip:"):
        try:
            with st.spinner("Reunindo seus dados..."):
                dados = privacidade.montar_exportacao_da_conta(
                    auth.usuario_email(),
                    db.buscar_perfil(user_id),
                    db.listar_catalogo(user_id),
                    db.listar_orcamentos_completos(user_id),
                    db.listar_aceites(user_id),
                )
        except Exception:
            st.error("Não foi possível reunir os dados. Tente novamente.")
            return
        st.session_state["priv_arquivo_conta"] = _para_json(dados)
        db.registrar_auditoria(user_id, "exportar_conta", len(dados["orcamentos"]))

    if "priv_arquivo_conta" in st.session_state:
        st.download_button(
            "Baixar meus dados (JSON)",
            data=st.session_state["priv_arquivo_conta"],
            file_name=f"meus-dados-{hoje_brasil().isoformat()}.json",
            mime="application/json", type="primary", width="stretch",
            icon=":material/download:",
        )
        st.caption("O arquivo contém dados pessoais seus e dos seus clientes. Guarde com cuidado.")


def _pedido_de_cliente(user_id):
    termo = st.text_input(
        "Nome ou telefone do cliente", max_chars=MAX_NOME, icon=":material/search:",
        key="priv_termo",
    )
    if not termo.strip():
        return
    try:
        todos = db.listar_orcamentos_completos(user_id)
    except Exception:
        st.error("Não foi possível buscar os orçamentos. Tente novamente.")
        return
    achados = [o for o in todos if privacidade.orcamento_e_do_cliente(o, termo)]
    if not achados:
        st.info("Nenhum orçamento encontrado para essa busca.")
        return

    nomes = sorted({o["cliente_nome"] for o in achados})
    palavra = "orçamento" if len(achados) == 1 else "orçamentos"
    st.markdown(
        f"**{len(achados)} {palavra}** de: " + ", ".join(escapar_md(n) for n in nomes[:5])
        + (" e outros" if len(nomes) > 5 else "")
    )
    st.caption("Confira se todos são da mesma pessoa. Se vierem nomes de outras pessoas, refine a busca.")
    ids = [o["id"] for o in achados]

    st.download_button(
        "Baixar os dados deste cliente (JSON)",
        data=_para_json(privacidade.montar_exportacao_do_cliente(termo, achados)),
        file_name=f"dados-do-cliente-{hoje_brasil().isoformat()}.json",
        mime="application/json", width="stretch", icon=":material/download:",
        on_click=db.registrar_auditoria, args=(user_id, "exportar_cliente", len(ids)),
    )
    st.caption("Este arquivo é para entregar ao cliente: não leva seus custos nem sua margem.")

    with st.form("form_apagar_cliente"):
        acao = st.radio(
            "O que fazer com os dados deste cliente?",
            options=["anonimizar", "excluir"],
            format_func=lambda a: (
                "Remover só os dados pessoais (os valores ficam no seu histórico)"
                if a == "anonimizar" else "Apagar os orçamentos por completo"
            ),
        )
        confirmo = st.checkbox(f"Confirmo: isto vale para os {len(ids)} {palavra} acima e não tem volta.")
        aplicar = st.form_submit_button("Aplicar", width="stretch", icon=":material/delete:")
    if not aplicar:
        return
    if not confirmo:
        st.error("Marque a caixa de confirmação.")
        return
    try:
        if acao == "anonimizar":
            feitos = db.anonimizar_orcamentos(user_id, ids, privacidade.DADOS_ANONIMOS)
            db.registrar_auditoria(user_id, "anonimizar_cliente", feitos)
            aviso = f"Dados pessoais removidos de {feitos} orçamento(s)."
        else:
            feitos = db.excluir_orcamentos(user_id, ids)
            db.registrar_auditoria(user_id, "excluir_cliente", feitos)
            aviso = f"{feitos} orçamento(s) apagado(s)."
    except Exception:
        st.error("Não foi possível concluir. Nada foi alterado; tente novamente.")
        return
    st.session_state.pop("priv_termo", None)
    st.session_state["aviso"] = aviso
    st.rerun()


def _excluir_conta():
    with st.expander("Apagar minha conta e todos os meus dados", icon=":material/warning:"):
        st.markdown(
            "Isto apaga **para sempre** sua conta, seu perfil, seu catálogo e todos os "
            "seus orçamentos. Não dá para desfazer. Se quiser guardar uma cópia, "
            "baixe seus dados antes."
        )
        with st.form("form_excluir_conta"):
            senha = st.text_input("Sua senha atual", type="password", max_chars=72)
            palavra = st.text_input(
                f"Digite {PALAVRA_DE_CONFIRMACAO} para confirmar", max_chars=20
            )
            excluir = st.form_submit_button(
                "Excluir minha conta para sempre", width="stretch", icon=":material/delete_forever:"
            )
        if not excluir:
            return
        if palavra.strip().upper() != PALAVRA_DE_CONFIRMACAO:
            st.error(f"Digite {PALAVRA_DE_CONFIRMACAO} no campo de confirmação.")
            return
        if not senha:
            st.error("Informe sua senha atual.")
            return
        # Confere a senha: um celular desbloqueado na mão de outra pessoa não basta.
        erro = auth.entrar(auth.usuario_email(), senha)
        if erro:
            st.error("Senha incorreta." if "incorretos" in erro else erro)
            return
        try:
            with st.spinner("Excluindo..."):
                db.excluir_minha_conta()
        except Exception:
            st.error("Não foi possível excluir a conta. Nada foi apagado; tente novamente.")
            return
        auth.sair()
        st.session_state["aviso_login"] = "Sua conta e seus dados foram excluídos."
        st.rerun()
