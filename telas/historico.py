"""Tela "Meus orçamentos": lista com busca e os detalhes de cada orçamento.

Duas visões na mesma tela:
  - lista: todos os orçamentos do técnico, do mais recente para o mais antigo
  - detalhes: aberta ao tocar em "Abrir"; permite baixar o PDF de novo
    e reenviar pelo WhatsApp

O orçamento aberto fica em st.session_state["hist_aberto"] (o id dele).
"""

import streamlit as st

from core import auth, db
from core.busca import filtrar_orcamentos
from core.calculos import calcular_resumo
from core.formato import data_do_banco, escapar_md, formatar_reais
from core.pdf import formatar_numero
from core.situacao import AJUDA, SITUACOES
from core.validacao import (
    MAX_CONDICOES,
    MAX_NOME,
    MAX_OBSERVACOES,
    MAX_TELEFONE,
    formatar_telefone,
    validar_telefone,
    validar_texto,
)
from telas import componentes, compartilhar

POR_PAGINA = 20


def _abrir(orcamento_id):
    st.session_state["hist_aberto"] = orcamento_id


def _fechar():
    st.session_state.pop("hist_aberto", None)


def _excluir(user_id, orcamento_id):
    """Callback do botão de excluir: só apaga se a caixa de confirmação estiver marcada."""
    if not st.session_state.get("hist_confirmar_exclusao"):
        st.session_state["hist_erro"] = "Marque a caixa de confirmação para excluir."
        return
    try:
        apagados = db.excluir_orcamento(user_id, orcamento_id)
    except Exception:
        st.session_state["hist_erro"] = "Não foi possível excluir. Tente novamente."
        return
    db.registrar_auditoria(user_id, "excluir_orcamento", apagados)
    st.session_state.pop("hist_confirmar_exclusao", None)
    st.session_state["aviso_hist"] = "Orçamento excluído."
    _fechar()


def _mostrar_mais():
    st.session_state["hist_quantos"] = st.session_state.get("hist_quantos", POR_PAGINA) + POR_PAGINA


def mostrar():
    user_id = auth.usuario_id()
    if "hist_aberto" in st.session_state:
        _mostrar_detalhes(user_id, st.session_state["hist_aberto"])
    else:
        _mostrar_lista(user_id)


# -------------------------------------------------------------------- lista
def _mostrar_lista(user_id):
    st.header("Meus orçamentos")
    if "aviso_hist" in st.session_state:
        st.success(st.session_state.pop("aviso_hist"))
    try:
        with st.spinner("Carregando..."):
            orcamentos = db.listar_orcamentos(user_id)
    except Exception as erro:
        if db.falta_coluna(erro):
            st.info("A lista aparece aqui assim que o banco de dados for atualizado (veja o aviso acima).")
        else:
            st.error("Não foi possível carregar os orçamentos. Tente recarregar a página.")
        return

    if not orcamentos:
        st.info("Você ainda não salvou nenhum orçamento. Comece em **Novo**.")
        return

    for orcamento in orcamentos:
        orcamento["data"] = data_do_banco(orcamento["criado_em"])

    # ---------- Busca
    termo = st.text_input(
        "Buscar pelo nome do cliente", max_chars=MAX_NOME,
        placeholder="Ex.: Maria", icon=":material/search:",
    )
    # O período fica recolhido: a busca por nome resolve quase sempre, e assim
    # a lista aparece mais perto do topo no celular.
    with st.expander("Filtrar por data ou situação", icon=":material/filter_list:"):
        coluna1, coluna2 = st.columns(2)
        data_inicial = coluna1.date_input("De", value=None, format="DD/MM/YYYY")
        data_final = coluna2.date_input("Até", value=None, format="DD/MM/YYYY")
        so_situacao = st.pills("Situação", list(SITUACOES), format_func=SITUACOES.get,
                               selection_mode="multi", key="hist_filtro_situacao")
    if data_inicial and data_final and data_inicial > data_final:
        st.error("A data inicial está depois da data final.")
        return

    encontrados = filtrar_orcamentos(orcamentos, termo, data_inicial, data_final)
    if so_situacao:
        encontrados = [o for o in encontrados if (o.get("situacao") or "aberto") in so_situacao]
    total_geral = sum(float(o["total"]) for o in encontrados)
    palavra = "orçamento" if len(encontrados) == 1 else "orçamentos"
    st.caption(f"{len(encontrados)} {palavra} · soma: {formatar_reais(total_geral)}")
    if "hist_erro_situacao" in st.session_state:
        st.error(st.session_state.pop("hist_erro_situacao"))
    if not encontrados:
        st.info("Nenhum orçamento combina com a busca.")
        return

    # ---------- Resultados (em blocos, para a tela não ficar pesada no celular)
    quantos = st.session_state.get("hist_quantos", POR_PAGINA)
    # componentes.grade: uma coluna no celular, duas no computador.
    with componentes.grade("orcamentos"):
        for orcamento in encontrados[:quantos]:
            with componentes.cartao(f"orc_{orcamento['id']}"):
                st.markdown(f"**{escapar_md(orcamento['cliente_nome'])}**")
                detalhe = orcamento["data"].strftime("%d/%m/%Y")
                if formatar_numero(orcamento.get("numero")):
                    detalhe = f"Nº {formatar_numero(orcamento['numero'])} · {detalhe}"
                coluna1, coluna2 = st.columns(2)
                coluna1.caption(detalhe)
                coluna1.markdown(f"**{formatar_reais(orcamento['total'])}**")
                coluna2.button(
                    "Abrir", key=f"hist_abrir_{orcamento['id']}", width="stretch",
                    icon=":material/open_in_new:", on_click=_abrir, args=(orcamento["id"],),
                )
                # A situação muda aqui mesmo, sem abrir o orçamento.
                controle_de_situacao(user_id, orcamento, f"sit_{orcamento['id']}")
    if len(encontrados) > quantos:
        st.button(f"Mostrar mais ({len(encontrados) - quantos} restantes)",
                  width="stretch", on_click=_mostrar_mais)
    if len(orcamentos) >= db.MAX_ORCAMENTOS_NA_LISTA:
        st.caption(f"A lista mostra os {db.MAX_ORCAMENTOS_NA_LISTA} orçamentos mais recentes.")


# ----------------------------------------------------------------- detalhes
def _mudar_situacao(user_id, orcamento, chave):
    """Grava a situação escolhida no controle (chamada quando a pessoa toca numa opção)."""
    nova = st.session_state.get(chave)
    atual = orcamento.get("situacao") or "aberto"
    if not nova or nova == atual:
        return
    try:
        db.definir_situacao(user_id, orcamento["id"], nova, orcamento.get("fechado_em"))
    except Exception as erro:
        st.session_state[chave] = atual          # o controle volta para o que está gravado
        st.session_state["hist_erro_situacao"] = (
            "Para mudar a situação, o banco de dados precisa ser atualizado (veja o aviso acima)."
            if db.falta_coluna(erro) else "Não foi possível mudar a situação. Tente de novo."
        )
        return
    st.toast(f"{orcamento['cliente_nome'][:40]}: {SITUACOES[nova]}.", icon=":material/check:")


def controle_de_situacao(user_id, orcamento, chave):
    """Os três botões: Não fechado, Fechado, Pago."""
    st.segmented_control(
        "Situação", list(SITUACOES), format_func=SITUACOES.get,
        default=orcamento.get("situacao") or "aberto", required=True, key=chave,
        on_change=_mudar_situacao, args=(user_id, orcamento, chave),
        label_visibility="collapsed", width="stretch",
    )


def _situacao(user_id, orcamento):
    """Situação do orçamento, com o controle para mudar."""
    with componentes.cartao("det_situacao"):
        st.markdown("**Situação**")
        controle_de_situacao(user_id, orcamento, f"sit_det_{orcamento['id']}")
        if orcamento.get("fechado_em"):
            st.caption(f"Fechado em {data_do_banco(orcamento['fechado_em']).strftime('%d/%m/%Y')}. {AJUDA}")
        else:
            st.caption(AJUDA)
        if "hist_erro_situacao" in st.session_state:
            st.error(st.session_state.pop("hist_erro_situacao"))


def _corrigir_cliente(user_id, orcamento):
    """Formulário para corrigir os dados do cliente (direito de correção, LGPD)."""
    with st.expander("Corrigir dados do cliente", icon=":material/edit:"):
        st.caption("Corrige nome, contato e textos. Os itens e os valores não mudam.")
        with st.form("form_corrigir_cliente"):
            nome = st.text_input("Nome do cliente", value=orcamento["cliente_nome"], max_chars=MAX_NOME)
            telefone = st.text_input(
                "WhatsApp do cliente, com DDD (opcional)",
                value=orcamento["cliente_telefone"], max_chars=MAX_TELEFONE,
                placeholder="27999990000", help="Só números, com DDD. Ex.: 27999990000",
            )
            equipamento = st.text_input(
                "Equipamento (opcional)", value=orcamento["equipamento"], max_chars=MAX_NOME)
            pagamento = st.text_input(
                "Condições de pagamento (opcional)",
                value=orcamento.get("condicoes_pagamento") or "", max_chars=MAX_CONDICOES)
            observacoes = st.text_area(
                "Observações (opcional)", value=orcamento["observacoes"], max_chars=MAX_OBSERVACOES,
                help="Não escreva CPF, endereço completo nem informações de saúde do cliente.")
            salvar = st.form_submit_button(
                "Salvar correção", type="primary", width="stretch", icon=":material/check:")
        if not salvar:
            return

        erros, dados = [], {}
        dados["cliente_nome"], erro = validar_texto(nome, "Nome do cliente", MAX_NOME, obrigatorio=True)
        erros.append(erro)
        dados["cliente_telefone"], erro = validar_telefone(telefone)
        erros.append(erro)
        dados["equipamento"], erro = validar_texto(equipamento, "Equipamento", MAX_NOME)
        erros.append(erro)
        dados["condicoes_pagamento"], erro = validar_texto(
            pagamento, "Condições de pagamento", MAX_CONDICOES)
        erros.append(erro)
        dados["observacoes"], erro = validar_texto(
            observacoes, "Observações", MAX_OBSERVACOES, multilinha=True)
        erros.append(erro)
        erros = [e for e in erros if e]
        if erros:
            for e in erros:
                st.error(e)
            return
        try:
            alterados = db.corrigir_dados_do_cliente(user_id, orcamento["id"], dados)
        except Exception:
            st.error("Não foi possível salvar a correção. Tente novamente.")
            return
        if not alterados:
            st.error("Orçamento não encontrado.")
            return
        st.session_state["aviso_detalhe"] = "Dados do cliente corrigidos. O PDF já sai atualizado."
        st.rerun()


def _mostrar_detalhes(user_id, orcamento_id):
    st.button("Voltar para a lista", icon=":material/arrow_back:", on_click=_fechar)
    if "aviso_detalhe" in st.session_state:
        st.success(st.session_state.pop("aviso_detalhe"))
    try:
        with st.spinner("Abrindo..."):
            orcamento = db.buscar_orcamento(user_id, orcamento_id)
            perfil = db.buscar_perfil(user_id)
    except Exception:
        st.error("Não foi possível abrir o orçamento. Tente novamente.")
        return
    if orcamento is None:
        # Não existe, foi apagado ou pertence a outra conta: a mensagem é a mesma.
        st.error("Orçamento não encontrado.")
        return

    itens = orcamento["itens"]
    data = data_do_banco(orcamento["criado_em"])
    resumo = calcular_resumo(
        itens, orcamento["desconto_tipo"], orcamento["desconto_valor"],
        orcamento.get("mao_de_obra") or 0,
    )

    numero = formatar_numero(orcamento.get("numero"))
    st.header(f"Orçamento nº {numero}" if numero else "Orçamento")
    st.caption(f"Emitido em {data.strftime('%d/%m/%Y')}")

    _situacao(user_id, orcamento)

    with componentes.cartao("det_cliente"):
        st.markdown(f"**Cliente:** {escapar_md(orcamento['cliente_nome'])}")
        if orcamento["cliente_telefone"]:
            st.markdown(f"**WhatsApp:** {formatar_telefone(orcamento['cliente_telefone'])}")
        if orcamento["equipamento"]:
            st.markdown(f"**Equipamento:** {escapar_md(orcamento['equipamento'])}")

    with componentes.cartao("det_itens"):
        for item in itens:
            subtotal = item["quantidade"] * float(item["preco_unitario"])
            st.markdown(
                f"{item['quantidade']} × {escapar_md(item['nome'])} — **{formatar_reais(subtotal)}**"
            )
        if resumo["mao_de_obra"] > 0:
            st.markdown(f"Mão de obra — **{formatar_reais(resumo['mao_de_obra'])}**")
        if resumo["desconto"] > 0:
            st.markdown(f"Desconto — **{formatar_reais(resumo['desconto'])}**")
        st.markdown(f"### Total: {formatar_reais(resumo['total'])}")

    if orcamento.get("condicoes_pagamento"):
        st.markdown(f"**Pagamento:** {escapar_md(orcamento['condicoes_pagamento'])}")
    if orcamento["observacoes"]:
        st.markdown(f"**Observações:** {escapar_md(orcamento['observacoes'])}")

    with componentes.cartao("det_interno"):
        st.markdown(":material/lock: **Resumo interno** — só você vê; não vai para o PDF")
        coluna1, coluna2 = st.columns(2)
        coluna1.metric("Custo total", formatar_reais(resumo["custo_total"]))
        coluna2.metric("Lucro", formatar_reais(resumo["lucro"]))
        st.caption(f"Margem: {resumo['margem']:.1f}%".replace(".", ","))

    st.subheader("Enviar de novo para o cliente")
    compartilhar.mostrar_botoes(perfil, orcamento, itens, resumo, data)

    _corrigir_cliente(user_id, orcamento)

    with st.expander("Excluir este orçamento", icon=":material/delete:"):
        st.caption("Apaga o orçamento e os dados do cliente que estão nele. Não dá para desfazer.")
        st.checkbox("Quero excluir este orçamento", key="hist_confirmar_exclusao")
        if "hist_erro" in st.session_state:
            st.error(st.session_state.pop("hist_erro"))
        st.button("Excluir para sempre", width="stretch", icon=":material/delete_forever:",
                  on_click=_excluir, args=(user_id, orcamento_id))
