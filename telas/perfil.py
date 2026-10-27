"""Tela do perfil da empresa: dados do cabeçalho do PDF, a cor do orçamento e a mensagem do WhatsApp."""

import streamlit as st

from core import auth, db
from core.cores import COR_PADRAO, CORES_PRONTAS, paleta, validar_cor
from core.formato import escapar_md, hoje_brasil
from core.privacidade import FINALIDADE_PERFIL
from core.imagem import logo_para_bytes, preparar_logo
from core.whatsapp import MARCADORES, MODELO_SUGERIDO, montar_mensagem
from telas.campo_senha import campo_senha, campo_senha_nova
from core.validacao import (
    MAX_MENSAGEM,
    MAX_NOME,
    MAX_TELEFONE,
    MAX_VALIDADE,
    MIN_VALIDADE,
    validar_senha,
    validar_telefone,
    validar_texto,
    validar_validade,
)


def mostrar():
    st.header("Perfil da empresa")
    st.caption(FINALIDADE_PERFIL)

    user_id = auth.usuario_id()
    try:
        perfil = db.buscar_perfil(user_id)
    except Exception:
        st.error(
            "Não foi possível ler o perfil. Confira se o sql/schema.sql foi "
            "executado no SQL Editor do Supabase."
        )
        return

    logo_atual = perfil.get("logo_base64")

    with st.form("form_perfil"):
        nome = st.text_input(
            "Nome da empresa ou do técnico",
            value=perfil["nome_empresa"],
            max_chars=MAX_NOME,
        )
        telefone = st.text_input(
            "Seu telefone / WhatsApp, com DDD",
            value=perfil["telefone"],
            max_chars=MAX_TELEFONE,
            placeholder="27999990000",
            help="Só números, com DDD. Ex.: 27999990000",
        )
        validade = st.number_input(
            "Validade padrão do orçamento (dias)",
            min_value=MIN_VALIDADE,
            max_value=MAX_VALIDADE,
            value=int(perfil["validade_dias"]),
            step=1,
        )

        st.markdown("**Logo (opcional)**")
        st.caption("Aparece no topo do PDF. Envie em PNG ou JPG, de preferência com fundo branco.")
        if logo_atual:
            try:
                st.image(logo_para_bytes(logo_atual), width=280)
            except Exception:
                st.caption("Não foi possível mostrar o logo salvo. Envie outro.")
        arquivo = st.file_uploader("Enviar novo logo (PNG ou JPG)", type=["png", "jpg", "jpeg"])
        remover = st.checkbox("Remover o logo atual") if logo_atual else False

        salvar = st.form_submit_button("Salvar perfil", type="primary", width="stretch", icon=":material/check:")

    if salvar:
        _salvar(user_id, nome, telefone, validade, arquivo, remover, logo_atual)

    # ---------- Cor do orçamento
    st.divider()
    _cor_do_orcamento(user_id, perfil)

    # ---------- Mensagem do WhatsApp
    st.divider()
    _mensagem_do_whatsapp(user_id, perfil)

    # ---------- Conta
    st.divider()
    st.subheader("Sua conta")
    st.caption(f"Você entrou como {escapar_md(auth.usuario_email())}")
    with st.expander("Trocar senha", icon=":material/key:"):
        _trocar_senha()
    if "pagina_ajuda" in st.session_state:
        st.page_link(
            st.session_state["pagina_ajuda"],
            label="Ajuda: dúvidas frequentes e contato do suporte",
            icon=":material/help:",
        )
    if "pagina_privacidade" in st.session_state:
        st.page_link(
            st.session_state["pagina_privacidade"],
            label="Privacidade: política, baixar ou apagar meus dados",
            icon=":material/policy:",
        )
    if st.button("Sair da conta", width="stretch", icon=":material/logout:"):
        auth.sair()
        st.rerun()


def _salvar(user_id, nome, telefone, validade, arquivo, remover, logo_atual):
    """Valida os campos do perfil e grava no banco."""

    # Valida tudo antes de gravar; junta os erros para mostrar de uma vez.
    erros = []
    nome, erro = validar_texto(nome, "Nome", MAX_NOME, obrigatorio=True)
    erros.append(erro)
    telefone, erro = validar_telefone(telefone, obrigatorio=True)
    erros.append(erro)
    validade, erro = validar_validade(validade)
    erros.append(erro)

    logo = None if remover else logo_atual
    if arquivo is not None:
        logo, erro = preparar_logo(arquivo.getvalue())
        erros.append(erro)

    erros = [e for e in erros if e]
    if erros:
        for e in erros:
            st.error(e)
        return

    try:
        db.salvar_perfil(user_id, nome, telefone, validade, logo)
    except Exception:
        st.error("Não foi possível salvar o perfil. Tente novamente.")
        return
    # Guarda o aviso para mostrar depois do recarregamento da página.
    st.session_state["aviso"] = "Perfil salvo."
    st.rerun()


def _cor_do_orcamento(user_id, perfil):
    """A cor de destaque do PDF: uma das prontas ou outra, com prévia na hora."""
    st.subheader("Cor do orçamento")
    st.caption("A cor do PDF que o cliente recebe: o nome da sua empresa, as linhas, a tabela e o total.")
    gravada = (perfil.get("cor_orcamento") or "").upper() or COR_PADRAO
    opcoes = list(CORES_PRONTAS) + ["Outra cor"]
    inicial = next((nome for nome, cor in CORES_PRONTAS.items() if cor == gravada), "Outra cor")
    escolha = st.pills("Cor", opcoes, default=inicial, required=True, key="cor_escolha",
                       label_visibility="collapsed")
    if escolha == "Outra cor":
        cor = st.color_picker("Escolha a cor", value=gravada, key="cor_livre")
    else:
        cor = CORES_PRONTAS.get(escolha, COR_PADRAO)
    cor_ok, erro = validar_cor(cor)
    _previa_da_cor(cor)
    if erro:
        st.warning(erro)
    mudou = cor_ok is not None and cor_ok != gravada
    if st.button("Salvar cor", type="primary", width="stretch", icon=":material/palette:", key="salvar_cor",
                 disabled=not mudou):
        try:
            db.salvar_cor_orcamento(user_id, "" if cor_ok == COR_PADRAO else cor_ok)
        except Exception as falha:
            if db.falta_coluna(falha):
                st.error("O banco de dados ainda não tem onde guardar a cor. Rode o arquivo "
                         "`sql/migracao_008.sql` no SQL Editor do Supabase e tente de novo.")
            else:
                st.error("Não foi possível salvar a cor. Tente novamente.")
            return
        st.session_state["aviso"] = "Cor do orçamento salva. Os próximos PDFs já saem com ela."
        st.rerun()


def _previa_da_cor(cor):
    """Um pedacinho do PDF desenhado com a cor escolhida (cor já no formato #RRGGBB)."""
    p = paleta(cor) if validar_cor(cor)[0] else {**paleta(""), "principal": tuple(int(cor[i:i + 2], 16) for i in (1, 3, 5))}
    rgb = lambda c: f"rgb{tuple(c)}"
    st.html(f"""
    <div style="border:1px solid #D5DEE8;border-radius:12px;padding:14px 16px;background:#fff;
                font-family:sans-serif;color:#0F172A;max-width:420px">
      <div style="text-align:right;font-weight:800;font-size:17px;color:{rgb(p['principal'])}">Sua empresa</div>
      <div style="height:3px;background:{rgb(p['principal'])};margin:8px 0 10px"></div>
      <div style="background:{rgb(p['gelo'])};text-align:center;font-weight:700;font-size:12px;padding:6px">
        Nº 0013 &nbsp; Válido até 21/10</div>
      <div style="display:flex;justify-content:space-between;background:{rgb(p['principal'])};color:#fff;
                  font-weight:700;font-size:12px;padding:6px 8px;margin-top:10px">
        <span>Descrição</span><span>Subtotal</span></div>
      <div style="display:flex;justify-content:space-between;background:{rgb(p['listra'])};font-size:12px;padding:6px 8px">
        <span>Higienização</span><span>R$ 180,00</span></div>
      <div style="display:flex;justify-content:flex-end;margin-top:10px">
        <div style="background:{rgb(p['principal'])};color:#fff;font-weight:800;padding:7px 12px;font-size:14px">
          TOTAL &nbsp; R$ 710,00</div></div>
    </div>""")


def _mensagem_do_whatsapp(user_id, perfil):
    """O texto que o técnico quer enviar aos clientes junto com o orçamento."""
    st.subheader("Mensagem do WhatsApp")
    st.caption(
        "É o texto que já vem escrito quando você envia um orçamento. "
        "Escreva do seu jeito. Na hora de enviar você ainda pode ajustar."
    )
    gravada = (perfil.get("mensagem_whatsapp") or "").strip()

    with st.form("form_mensagem"):
        texto = st.text_area(
            "Sua mensagem",
            value=gravada or MODELO_SUGERIDO,
            max_chars=MAX_MENSAGEM,
            height=260,
        )
        st.markdown(
            "**Palavras que o sistema troca sozinho** (escreva com as chaves):  \n"
            + "  \n".join(f"`{marcador}` = {significado}" for marcador, significado in MARCADORES.items())
        )
        coluna1, coluna2 = st.columns(2)
        salvar = coluna1.form_submit_button(
            "Salvar mensagem", type="primary", width="stretch", icon=":material/check:"
        )
        padrao = coluna2.form_submit_button(
            "Voltar à mensagem do sistema", width="stretch", icon=":material/restart_alt:"
        )

    # Exemplo com dados inventados, para o técnico ver como o cliente recebe.
    with st.expander("Ver como o cliente recebe", icon=":material/visibility:"):
        exemplo = montar_mensagem(
            {**perfil, "mensagem_whatsapp": gravada},
            {"cliente_nome": "Maria", "equipamento": "Split 12.000 BTUs",
             "validade_dias": int(perfil["validade_dias"])},
            {"total": 710.0},
            hoje_brasil(),
        )
        st.text(exemplo)
        if not gravada:
            st.caption("Você ainda não gravou uma mensagem: esta é a do sistema.")

    if not (salvar or padrao):
        return
    if padrao:
        texto = ""
    texto, erro = validar_texto(texto, "Mensagem", MAX_MENSAGEM, obrigatorio=salvar, multilinha=True)
    if erro:
        st.error(erro)
        return
    try:
        db.salvar_mensagem_whatsapp(user_id, texto)
    except Exception as falha:
        if db.falta_coluna(falha):
            st.error(
                "O banco de dados ainda não tem onde guardar a mensagem. Rode o arquivo "
                "`sql/migracao_005.sql` no SQL Editor do Supabase e tente de novo."
            )
        else:
            st.error("Não foi possível salvar a mensagem. Tente novamente.")
        return
    st.session_state["aviso"] = "Mensagem salva." if texto else "Voltou para a mensagem do sistema."
    st.rerun()


def _trocar_senha():
    # Sem st.form aqui: a barra de força precisa reagir enquanto a pessoa digita.
    n = st.session_state.get("rodada_troca", 0)   # aumentar esvazia os campos
    if "aviso_troca" in st.session_state:
        st.success(st.session_state.pop("aviso_troca"))
    atual = campo_senha("Senha atual", f"troca_atual_{n}", nova=False)
    nova = campo_senha_nova("Senha nova", f"troca_nova_{n}")
    nova2 = campo_senha("Repita a senha nova", f"troca_nova2_{n}")
    trocar = st.button("Trocar senha", width="stretch", icon=":material/check:", key="troca_enviar")
    if not trocar:
        return
    nova, erro = validar_senha(nova)
    if not erro and not atual:
        erro = "Informe a senha atual."
    if not erro and nova != nova2:
        erro = "As senhas novas não são iguais."
    if not erro and nova == atual:
        erro = "A senha nova precisa ser diferente da atual."
    if not erro:
        with st.spinner("Trocando..."):
            erro = auth.trocar_senha(atual, nova)
    if erro:
        st.error(erro)
    else:
        for chave in (f"troca_atual_{n}", f"troca_nova_{n}", f"troca_nova2_{n}"):
            st.session_state.pop(chave, None)      # apaga as senhas da memória
        st.session_state["rodada_troca"] = n + 1   # e esvazia os campos na tela
        st.session_state["aviso_troca"] = "Senha trocada."
        st.rerun()
