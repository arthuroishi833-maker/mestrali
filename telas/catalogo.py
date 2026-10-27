"""Tela do catálogo: serviços e peças, com custo e preço."""

import streamlit as st

from core import auth, db
from core.catalogo_inicial import AREAS, TIPOS, TIPOS_PLURAL
from core.formato import escapar_md, formatar_reais
from telas import componentes
from core.validacao import (
    MAX_DINHEIRO,
    MAX_NOME,
    validar_dinheiro,
    validar_texto,
    validar_tipo,
)

MARCADOR = "catalogo_inicial_criado"


def garantir_catalogo_inicial(user_id):
    """No primeiro acesso, pergunta a área de trabalho e cria o catálogo de exemplo.

    Devolve True quando o catálogo já está pronto. Devolve False quando acabou
    de desenhar a pergunta: quem chamou deve parar ali e não desenhar o resto.

    Chamada pela tela Catálogo e pela tela Novo orçamento: quem cria a conta
    e vai direto fazer um orçamento também passa pela escolha.
    O marcador na conta evita perguntar de novo se o técnico apagar tudo depois.
    """
    if auth.ler_marcador(MARCADOR) or st.session_state.get(MARCADOR):
        return True
    if db.listar_catalogo(user_id):
        # Conta antiga, que já tem itens: só anota que não precisa perguntar.
        _marcar_como_criado()
        return True

    st.subheader("Qual é a sua área de trabalho?")
    st.caption(
        "Colocamos no seu catálogo alguns serviços e peças de exemplo dessa área, "
        "para você começar. Os preços são só exemplos: depois é só trocar pelos seus."
    )
    area = st.radio(
        "Área de trabalho", list(AREAS), format_func=lambda chave: AREAS[chave]["nome"],
        label_visibility="collapsed", key="area_escolhida",
    )
    if st.button("Começar", type="primary", width="stretch"):
        try:
            db.inserir_itens_catalogo(user_id, AREAS[area]["itens"])
            _marcar_como_criado()
        except Exception:
            st.error("Não foi possível criar o catálogo. Verifique a internet e tente de novo.")
            return False
        st.rerun()
    return False


def _marcar_como_criado():
    st.session_state[MARCADOR] = True
    auth.gravar_marcador(MARCADOR, True)


def _campos_item(chave, nome="", tipo="mao_de_obra", custo=0.0, preco=0.0):
    """Desenha os 4 campos de um item. Devolve os valores digitados."""
    nome = st.text_input("Nome", value=nome, max_chars=MAX_NOME, key=f"nome_{chave}")
    tipo = st.selectbox(
        "Tipo",
        options=list(TIPOS),
        index=list(TIPOS).index(tipo),
        format_func=lambda t: TIPOS[t],  # mostra "Serviço" em vez de "mao_de_obra"
        key=f"tipo_{chave}",
    )
    coluna1, coluna2 = st.columns(2)
    custo = coluna1.number_input(
        "Custo (R$)", min_value=0.0, max_value=MAX_DINHEIRO, value=float(custo),
        step=10.0, format="%.2f", key=f"custo_{chave}",
    )
    preco = coluna2.number_input(
        "Preço de venda (R$)", min_value=0.0, max_value=MAX_DINHEIRO, value=float(preco),
        step=10.0, format="%.2f", key=f"preco_{chave}",
    )
    return nome, tipo, custo, preco


def _validar_item(nome, tipo, custo, preco):
    """Devolve (item_limpo, lista_de_erros)."""
    erros = []
    nome, erro = validar_texto(nome, "Nome", MAX_NOME, obrigatorio=True)
    erros.append(erro)
    tipo, erro = validar_tipo(tipo)
    erros.append(erro)
    custo, erro = validar_dinheiro(custo, "Custo")
    erros.append(erro)
    preco, erro = validar_dinheiro(preco, "Preço de venda")
    erros.append(erro)
    item = {"nome": nome, "tipo": tipo, "custo": custo, "preco": preco}
    return item, [e for e in erros if e]


def _voltar_com_aviso(texto):
    st.session_state["aviso"] = texto
    st.rerun()


def mostrar():
    st.header("Catálogo")
    st.caption("Seus serviços e peças. Toque em um item para editar. O custo nunca aparece para o cliente.")

    user_id = auth.usuario_id()
    try:
        if not garantir_catalogo_inicial(user_id):
            return                      # está na pergunta da área de trabalho
        itens = db.listar_catalogo(user_id)
    except Exception:
        st.error("Não foi possível carregar o catálogo. Tente recarregar a página.")
        return

    # ---------- Novo item
    with st.expander("Adicionar item ao catálogo", icon=":material/add:"):
        # clear_on_submit limpa os campos depois de adicionar.
        with st.form("form_novo_item", clear_on_submit=True):
            valores = _campos_item("novo")
            adicionar = st.form_submit_button("Adicionar ao catálogo", type="primary", width="stretch")
        if adicionar:
            item, erros = _validar_item(*valores)
            if erros:
                for e in erros:
                    st.error(e)
            else:
                try:
                    db.inserir_itens_catalogo(user_id, [item])
                except Exception:
                    st.error("Não foi possível adicionar o item.")
                else:
                    _voltar_com_aviso(f"Item adicionado: {escapar_md(item['nome'])}")

    _trazer_outra_area(user_id, itens)

    if not itens:
        st.info("Seu catálogo está vazio. Adicione o primeiro item acima.")
        return

    # ---------- Itens existentes, separados por tipo
    for tipo, titulo in TIPOS_PLURAL.items():
        do_tipo = [i for i in itens if i["tipo"] == tipo]
        if not do_tipo:
            continue
        st.subheader(titulo)
        # Uma coluna no celular, duas no computador.
        with componentes.grade(f"catalogo_{tipo}"):
            for item in do_tipo:
                _mostrar_item(user_id, item)

    _reiniciar_catalogo(user_id, len(itens))


def itens_que_faltam(area, itens_atuais):
    """Os exemplos de uma área que ainda não estão no catálogo (compara pelo nome, sem ligar para maiúsculas)."""
    nomes = {item["nome"].strip().lower() for item in itens_atuais}
    return [item for item in AREAS[area]["itens"] if item["nome"].strip().lower() not in nomes]


def _trazer_outra_area(user_id, itens):
    """Mudou de ramo, ou atende mais de um? Traz os exemplos de outra área para o catálogo.

    Só ACRESCENTA: nada do que a pessoa já tem é apagado nem alterado, e um
    item com o mesmo nome não é repetido. Quem quiser tirar os antigos exclui
    um por um, na lista abaixo.
    """
    with st.expander("Trazer exemplos de outra área", icon=":material/category:"):
        st.caption(
            "Para quem mudou de área ou atende mais de uma. Os exemplos entram no seu catálogo; "
            "o que você já tem continua como está."
        )
        areas = [chave for chave in AREAS if AREAS[chave]["itens"]]
        area = st.selectbox("Área", areas, format_func=lambda chave: AREAS[chave]["nome"], key="outra_area")
        if st.button("Adicionar os exemplos desta área", width="stretch", key="trazer_area"):
            novos = itens_que_faltam(area, itens)
            if not novos:
                st.info("Você já tem todos os exemplos dessa área.")
                return
            try:
                db.inserir_itens_catalogo(user_id, novos)
            except Exception:
                st.error("Não foi possível adicionar os exemplos. Verifique a internet e tente de novo.")
                return
            _voltar_com_aviso(f"{len(novos)} itens de {AREAS[area]['nome']} adicionados. Troque os preços pelos seus.")


def _pedir_confirmacao():
    st.session_state["reiniciar_catalogo"] = True


def _desistir_de_reiniciar():
    st.session_state.pop("reiniciar_catalogo", None)


def _reiniciar_catalogo(user_id, quantos):
    """Apaga o catálogo inteiro e volta à pergunta da área de trabalho.

    É uma ação sem volta, por isso tem dois passos: o botão só abre o aviso;
    apagar exige tocar em "Sim, apagar tudo".
    """
    st.divider()
    if not st.session_state.get("reiniciar_catalogo"):
        st.button("Reiniciar o catálogo", icon=":material/restart_alt:", type="tertiary",
                  on_click=_pedir_confirmacao, key="pedir_reinicio")
        return

    st.warning(
        f"**Quer mesmo reiniciar o catálogo?** Os {quantos} itens serão apagados, com os preços que você "
        "cadastrou, e não dá para desfazer. Depois você escolhe a área de novo e recebe os exemplos dela. "
        "Os orçamentos já salvos não mudam."
    )
    coluna1, coluna2 = st.columns(2)
    coluna1.button("Cancelar", width="stretch", on_click=_desistir_de_reiniciar, key="cancelar_reinicio")
    if coluna2.button("Sim, apagar tudo", width="stretch", icon=":material/delete_forever:", key="confirmar_reinicio"):
        try:
            db.excluir_todo_o_catalogo(user_id)
            auth.gravar_marcador(MARCADOR, False)       # faz a pergunta da área aparecer de novo
        except Exception:
            st.error("Não foi possível reiniciar o catálogo. Verifique a internet e tente de novo.")
            return
        st.session_state[MARCADOR] = False
        _desistir_de_reiniciar()
        _voltar_com_aviso("Catálogo reiniciado. Escolha a sua área para receber os exemplos.")


def _mostrar_item(user_id, item):
    """Um item do catálogo: linha que abre para editar ou excluir."""
    with st.expander(f"{escapar_md(item['nome'])} · {formatar_reais(item['preco'])}"):
        with st.form(f"form_{item['id']}"):
            valores = _campos_item(
                item["id"], item["nome"], item["tipo"], item["custo"], item["preco"]
            )
            excluir_marcado = st.checkbox("Quero excluir este item", key=f"excluir_{item['id']}")
            coluna1, coluna2 = st.columns(2)
            salvar = coluna1.form_submit_button("Salvar", type="primary", width="stretch", icon=":material/check:")
            excluir = coluna2.form_submit_button("Excluir", width="stretch", icon=":material/delete:")

        if excluir:
            if not excluir_marcado:
                st.warning("Para excluir, marque a caixa \"Quero excluir este item\".")
                return
            try:
                db.excluir_item_catalogo(user_id, item["id"])
            except Exception:
                st.error("Não foi possível excluir o item.")
                return
            _voltar_com_aviso(f"Item excluído: {escapar_md(item['nome'])}")

        if salvar:
            novo, erros = _validar_item(*valores)
            if erros:
                for e in erros:
                    st.error(e)
                return
            try:
                db.atualizar_item_catalogo(user_id, item["id"], **novo)
            except Exception:
                st.error("Não foi possível salvar o item.")
                return
            _voltar_com_aviso(f"Item salvo: {escapar_md(novo['nome'])}")
