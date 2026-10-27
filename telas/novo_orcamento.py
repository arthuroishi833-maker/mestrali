"""Tela de novo orçamento, guiada em passos:

    Cliente  ->  Itens  ->  Valores  ->  Revisão  ->  (salvar)

Como o estado é guardado
------------------------
O Streamlit esquece o valor de um campo quando ele sai da tela. Como cada
passo mostra campos diferentes, os valores ficam guardados por nossa conta:

    st.session_state["orc_dados"]  -> dict com os campos do orçamento
    st.session_state["orc_itens"]  -> lista de itens
    st.session_state["orc_passo"]  -> número do passo atual (0 a 3)

Todas as chaves começam com "orc_", então limpar a tela é apagar essas chaves.

Botões e "callbacks"
--------------------
Os botões usam on_click=funcao. O Streamlit chama essa função ANTES de
redesenhar a tela (parecido com um handler de interrupção que só ajusta
variáveis); em seguida a tela é desenhada já no estado novo.
"""

import streamlit as st

from core import auth, db
from core.calculos import arredondar_centavos, calcular_resumo
from core.catalogo_inicial import TIPOS
from core.formato import escapar_md, formatar_reais, hoje_brasil
from core.privacidade import FINALIDADE_CLIENTE
from core.supabase_client import SEM_CONEXAO, sem_conexao
from telas import componentes, compartilhar
from telas.catalogo import garantir_catalogo_inicial
from core.validacao import (
    MAX_CONDICOES,
    MAX_DINHEIRO,
    MAX_ITENS_ORCAMENTO,
    MAX_NOME,
    MAX_OBSERVACOES,
    MAX_QUANTIDADE,
    MAX_TELEFONE,
    MAX_VALIDADE,
    MIN_VALIDADE,
    formatar_telefone,
    validar_desconto,
    validar_dinheiro,
    validar_quantidade,
    validar_telefone,
    validar_texto,
    validar_total,
    validar_validade,
)

PASSOS = ["Cliente", "Itens", "Valores", "Revisão"]
_CAMPOS_DE_DINHEIRO = ("mao_de_obra", "desconto_valor")


# ------------------------------------------------------------------ estado
def _limpar_tela():
    """Apaga tudo que foi digitado no orçamento atual."""
    for chave in list(st.session_state.keys()):
        if chave.startswith("orc_"):
            del st.session_state[chave]


def _dados(perfil):
    """Devolve o dict com os campos do orçamento (cria na primeira vez)."""
    return st.session_state.setdefault("orc_dados", {
        "cliente_nome": "",
        "cliente_telefone": "",
        "equipamento": "",
        "mao_de_obra": 0.0,
        "desconto_tipo": "valor",
        "desconto_valor": 0.0,
        "condicoes_pagamento": "",
        "observacoes": "",
        "validade_dias": int(perfil["validade_dias"]),
    })


def _chave(dados, campo):
    """Prepara a chave de um campo da tela ligado a dados[campo].

    Se o campo acabou de voltar para a tela (mudou de passo), recebe de
    volta o valor que estava guardado em dados.
    """
    chave = f"orc_w_{campo}"
    if chave not in st.session_state:
        st.session_state[chave] = dados[campo]
    return chave


def _sincronizar():
    """Copia o que está nos campos da tela para orc_dados e orc_itens.

    Chamada no início dos callbacks: quando um botão é clicado, o valor
    recém-digitado ainda está só no campo, não nos nossos dados.
    """
    estado = st.session_state
    dados = estado.get("orc_dados", {})
    for campo in dados:
        if f"orc_w_{campo}" in estado:
            valor = estado[f"orc_w_{campo}"]
            # Valores em reais (e o desconto em %) entram sempre com duas casas.
            dados[campo] = arredondar_centavos(valor) if campo in _CAMPOS_DE_DINHEIRO else valor
    for item in estado.get("orc_itens", []):
        if f"orc_qtd_{item['linha']}" in estado:
            item["quantidade"] = int(estado[f"orc_qtd_{item['linha']}"])
            item["preco_unitario"] = arredondar_centavos(estado[f"orc_preco_{item['linha']}"])


def _orcamento_em_andamento():
    """False se o orçamento já foi salvo ou limpo (os dados não estão mais na memória).

    Protege os callbacks contra o toque duplo: o primeiro toque em "Salvar"
    grava e limpa a tela; o segundo chegaria aqui sem dados e quebraria.
    """
    return "orc_dados" in st.session_state and "orc_itens" in st.session_state


def _erros_do_passo(passo):
    estado = st.session_state
    dados, itens = estado["orc_dados"], estado["orc_itens"]
    if passo == 0:
        return _erros_cliente(dados)
    if passo == 1:
        return _erros_itens(itens)
    return _erros_valores(dados, _resumo(dados, itens))


def _avancar(passo):
    """Callback do botão Continuar: só avança se o passo não tiver erros."""
    if not _orcamento_em_andamento():
        return
    _sincronizar()
    erros = _erros_do_passo(passo)
    if erros:
        st.session_state["orc_erros"] = erros
    else:
        st.session_state["orc_passo"] = passo + 1


def _voltar(passo):
    """Callback do botão Voltar: guarda o que foi digitado e volta um passo."""
    _sincronizar()
    st.session_state["orc_passo"] = passo - 1


def _mostrar_erros():
    """Mostra (uma vez) os erros deixados por um callback."""
    for erro in st.session_state.pop("orc_erros", []):
        st.error(erro)


# --------------------------------------------------------------- validação
def _erros_cliente(dados):
    erros = [
        validar_texto(dados["cliente_nome"], "Nome do cliente", MAX_NOME, obrigatorio=True)[1],
        validar_telefone(dados["cliente_telefone"])[1],
        validar_texto(dados["equipamento"], "Equipamento", MAX_NOME)[1],
    ]
    return [e for e in erros if e]


def _erros_itens(itens):
    erros = []
    if len(itens) > MAX_ITENS_ORCAMENTO:
        erros.append(f"Máximo de {MAX_ITENS_ORCAMENTO} itens por orçamento.")
    for item in itens:
        erros.append(validar_texto(item["nome"], "Descrição do item", MAX_NOME, obrigatorio=True)[1])
        erros.append(validar_quantidade(item["quantidade"])[1])
        nome = escapar_md(item["nome"])  # o nome vai aparecer numa mensagem de erro
        erros.append(validar_dinheiro(item["preco_unitario"], f"Preço de {nome}")[1])
        erros.append(validar_dinheiro(item["custo_unitario"], f"Custo de {nome}")[1])
    return [e for e in erros if e]


def _erros_valores(dados, resumo):
    erros = [
        validar_dinheiro(dados["mao_de_obra"], "Mão de obra")[1],
        validar_desconto(dados["desconto_tipo"], dados["desconto_valor"], resumo["subtotal"])[1],
        validar_texto(dados["condicoes_pagamento"], "Condições de pagamento", MAX_CONDICOES)[1],
        validar_texto(dados["observacoes"], "Observações", MAX_OBSERVACOES, multilinha=True)[1],
        validar_validade(dados["validade_dias"])[1],
    ]
    if resumo["subtotal"] <= 0:
        erros.append("O orçamento está zerado: adicione itens ou informe a mão de obra.")
    erros.append(validar_total(resumo["total"]))
    return [e for e in erros if e]


def _resumo(dados, itens):
    return calcular_resumo(
        itens, dados["desconto_tipo"], dados["desconto_valor"], dados["mao_de_obra"]
    )


# -------------------------------------------------------------------- tela
def mostrar():
    # Depois de salvar, mostra a confirmação em vez dos passos.
    if "orc_salvo" in st.session_state:
        _mostrar_confirmacao(st.session_state["orc_salvo"])
        return

    st.header("Novo orçamento")

    user_id = auth.usuario_id()
    # Conta nova: antes do primeiro orçamento, escolhe a área e recebe os exemplos.
    try:
        if not garantir_catalogo_inicial(user_id):
            return
    except Exception:
        pass   # sem a lista de exemplo dá para seguir: o item avulso continua disponível
    try:
        with st.spinner("Carregando..."):
            perfil = db.buscar_perfil(user_id)
            catalogo = db.listar_catalogo(user_id)
    except Exception:
        st.error("Não foi possível carregar seus dados. Tente recarregar a página.")
        return

    dados = _dados(perfil)
    itens = st.session_state.setdefault("orc_itens", [])
    passo = st.session_state.setdefault("orc_passo", 0)

    _indicador_de_passos(passo)

    # Cada passo fica num bloco com chave própria: ao mudar de passo o bloco
    # é trocado, e o CSS faz o conteúdo novo entrar suavemente.
    with st.container(key=f"passo_{passo}"):
        if passo == 0:
            _passo_cliente(dados, perfil)
        elif passo == 1:
            _passo_itens(dados, itens, catalogo)
        elif passo == 2:
            _passo_valores(dados, itens)
        else:
            _passo_revisao(user_id, dados, itens)


def _indicador_de_passos(passo):
    """Mostra em que passo o técnico está."""
    componentes.indicador_de_passos(PASSOS, passo)


def _botoes_de_navegacao(passo, rotulo_avancar="Continuar"):
    """Botões Voltar / Continuar, e os erros que impediram de avançar."""
    _mostrar_erros()
    coluna1, coluna2 = st.columns(2)
    if passo > 0:
        coluna1.button("Voltar", width="stretch", icon=":material/arrow_back:",
                       on_click=_voltar, args=(passo,))
    coluna2.button(rotulo_avancar, type="primary", width="stretch",
                   on_click=_avancar, args=(passo,))


# --------------------------------------------------------- passo 1: cliente
def _passo_cliente(dados, perfil):
    st.subheader("Para quem é o orçamento?")
    st.caption(FINALIDADE_CLIENTE)
    if not perfil["nome_empresa"]:
        st.warning("Preencha o **Perfil** da empresa: ele aparece no cabeçalho do PDF.")

    dados["cliente_nome"] = st.text_input(
        "Nome do cliente", max_chars=MAX_NOME, key=_chave(dados, "cliente_nome"),
    )
    dados["cliente_telefone"] = st.text_input(
        "WhatsApp do cliente, com DDD (opcional)",
        max_chars=MAX_TELEFONE, placeholder="27999990000",
        help="Só números, com DDD. Usado para abrir a conversa no WhatsApp.",
        key=_chave(dados, "cliente_telefone"),
    )
    dados["equipamento"] = st.text_input(
        "Equipamento ou local do serviço (opcional)", max_chars=MAX_NOME,
        placeholder="Ex.: Split 12.000 BTUs, quadro de luz, banheiro", key=_chave(dados, "equipamento"),
    )
    _botoes_de_navegacao(0, "Continuar para os itens")


# ----------------------------------------------------------- passo 2: itens
def _passo_itens(dados, itens, catalogo):
    st.subheader("O que entra no orçamento?")
    st.caption("Adicione quantos itens precisar: peças, serviços ou equipamentos.")

    aba_catalogo, aba_avulso = st.tabs(["Do catálogo", "Item avulso"])
    with aba_catalogo:
        _adicionar_do_catalogo(catalogo)
    with aba_avulso:
        _adicionar_avulso()
    _mostrar_erros()
    _editar_itens(itens)

    resumo = _resumo(dados, itens)
    st.metric("Soma dos itens", formatar_reais(resumo["itens"]))
    _botoes_de_navegacao(1, "Continuar para os valores")


def _novo_item(nome, tipo, quantidade, custo, preco):
    """Coloca um item na lista do orçamento."""
    itens = st.session_state["orc_itens"]
    if len(itens) >= MAX_ITENS_ORCAMENTO:
        st.session_state["orc_erros"] = [f"Máximo de {MAX_ITENS_ORCAMENTO} itens por orçamento."]
        return
    # Cada linha recebe um número único, usado nas chaves dos campos.
    # (O contador não começa com "orc_" de propósito: ele não é zerado ao
    # limpar a tela, então uma chave de campo nunca é reaproveitada.)
    numero = st.session_state.get("contador_linhas", 0) + 1
    st.session_state["contador_linhas"] = numero
    itens.append({
        "linha": numero,
        "nome": nome,
        "tipo": tipo,
        "quantidade": int(quantidade),
        "custo_unitario": arredondar_centavos(custo),
        "preco_unitario": arredondar_centavos(preco),
    })
    st.toast(f"Item adicionado: {escapar_md(nome)}")


def _adicionar_do_catalogo_cb(catalogo):
    """Callback do botão "Adicionar ao orçamento"."""
    if not _orcamento_em_andamento():
        return
    _sincronizar()
    posicao = st.session_state.get("orc_escolhido")
    # O catálogo pode ter mudado em outra aba desde que a lista foi desenhada.
    if not isinstance(posicao, int) or not 0 <= posicao < len(catalogo):
        st.session_state["orc_erros"] = ["Escolha o item de novo: o catálogo mudou."]
        return
    escolhido = catalogo[posicao]
    # Copia os valores do catálogo: o preço pode ser alterado só no orçamento.
    _novo_item(escolhido["nome"], escolhido["tipo"], st.session_state["orc_nova_quantidade"],
               escolhido["custo"], escolhido["preco"])


def _adicionar_avulso():
    """Campos para um item que não está no catálogo (só neste orçamento)."""
    with componentes.cartao("avulso"):
        st.text_input("Descrição", max_chars=MAX_NOME, key="orc_av_nome",
                      placeholder="Ex.: Suporte para condensadora")
        st.selectbox("Tipo", options=list(TIPOS), format_func=lambda t: TIPOS[t], key="orc_av_tipo")
        coluna1, coluna2 = st.columns(2)
        coluna1.number_input("Quantidade", min_value=1, max_value=MAX_QUANTIDADE, value=1,
                             step=1, key="orc_av_quantidade")
        coluna2.number_input("Valor unitário (R$)", min_value=0.0, max_value=MAX_DINHEIRO,
                             step=10.0, format="%.2f", key="orc_av_preco")
        st.number_input("Seu custo unitário (R$, opcional)", min_value=0.0, max_value=MAX_DINHEIRO,
                        step=10.0, format="%.2f", key="orc_av_custo",
                        help="Usado só no seu resumo de lucro. O cliente não vê.")
        st.button("Adicionar item avulso", width="stretch", key="orc_av_adicionar",
                  icon=":material/add:", on_click=_adicionar_avulso_cb)


def _adicionar_avulso_cb():
    """Callback do botão "Adicionar item avulso"."""
    if not _orcamento_em_andamento():
        return
    _sincronizar()
    estado = st.session_state
    nome, erro = validar_texto(estado["orc_av_nome"], "Descrição", MAX_NOME, obrigatorio=True)
    if erro:
        estado["orc_erros"] = [erro]
        return
    _novo_item(nome, estado["orc_av_tipo"], estado["orc_av_quantidade"],
               estado["orc_av_custo"], estado["orc_av_preco"])
    # Limpa os campos para o próximo item avulso.
    estado["orc_av_nome"] = ""
    estado["orc_av_quantidade"] = 1
    estado["orc_av_preco"] = 0.0
    estado["orc_av_custo"] = 0.0


def _remover_item(linha):
    """Callback do botão Remover."""
    if not _orcamento_em_andamento():
        return
    _sincronizar()
    itens = st.session_state["orc_itens"]
    itens[:] = [item for item in itens if item["linha"] != linha]


def _adicionar_do_catalogo(catalogo):
    """Caixa para escolher um item do catálogo e colocar no orçamento."""
    if not catalogo:
        st.info("Seu catálogo está vazio. Cadastre itens em **Catálogo** ou use **Item avulso**.")
        return
    with componentes.cartao("catalogo"):
        # As opções são as posições (0, 1, 2...) na lista do catálogo;
        # format_func define o texto que aparece para cada posição.
        st.selectbox(
            "Item do catálogo",
            options=range(len(catalogo)),
            format_func=lambda p: f"{catalogo[p]['nome']} · {formatar_reais(catalogo[p]['preco'])}",
            key="orc_escolhido",
        )
        # Em celular estreito a caixa acima corta o fim do texto, que é justo o
        # preço. Aqui o item escolhido aparece inteiro, com quebra de linha.
        posicao = st.session_state.get("orc_escolhido")
        if isinstance(posicao, int) and 0 <= posicao < len(catalogo):
            escolhido = catalogo[posicao]
            st.caption(f"{escapar_md(escolhido['nome'])}: **{formatar_reais(escolhido['preco'])}** cada")
        st.number_input(
            "Quantidade", min_value=1, max_value=MAX_QUANTIDADE, value=1, step=1,
            key="orc_nova_quantidade",
        )
        st.button("Adicionar ao orçamento", width="stretch", key="orc_adicionar",
                  icon=":material/add:",
                  on_click=_adicionar_do_catalogo_cb, args=(catalogo,))


def _editar_itens(itens):
    """Lista os itens já adicionados, com quantidade e preço editáveis."""
    if not itens:
        st.caption("Nenhum item adicionado ainda.")
        return

    st.markdown(f"**Itens no orçamento ({len(itens)})**")
    for item in list(itens):
        linha = item["linha"]
        chave_qtd, chave_preco = f"orc_qtd_{linha}", f"orc_preco_{linha}"
        if chave_qtd not in st.session_state:
            st.session_state[chave_qtd] = item["quantidade"]
            st.session_state[chave_preco] = item["preco_unitario"]

        with componentes.cartao(f"item_{linha}"):
            st.markdown(f"**{escapar_md(item['nome'])}** · {TIPOS[item['tipo']]}")
            coluna1, coluna2 = st.columns(2)
            item["quantidade"] = int(coluna1.number_input(
                "Quantidade", min_value=1, max_value=MAX_QUANTIDADE, step=1, key=chave_qtd,
            ))
            # O campo aceita mais de duas casas; o valor já entra em centavos,
            # para o subtotal desta linha ser o mesmo da revisão e do PDF.
            item["preco_unitario"] = arredondar_centavos(coluna2.number_input(
                "Valor unitário (R$)", min_value=0.0, max_value=MAX_DINHEIRO,
                step=10.0, format="%.2f", key=chave_preco,
            ))
            coluna1, coluna2 = st.columns(2)
            subtotal = item["quantidade"] * item["preco_unitario"]
            coluna1.markdown(f"Subtotal: **{formatar_reais(subtotal)}**")
            coluna2.button("Remover", key=f"orc_remover_{linha}", width="stretch",
                           icon=":material/delete:",
                           on_click=_remover_item, args=(linha,))


# --------------------------------------------------------- passo 3: valores
def _passo_valores(dados, itens):
    st.subheader("Mão de obra, desconto e condições")

    dados["mao_de_obra"] = arredondar_centavos(st.number_input(
        "Mão de obra (R$)", min_value=0.0, max_value=MAX_DINHEIRO, step=10.0, format="%.2f",
        help="Somada ao total. Se a mão de obra já está nos itens, deixe em zero.",
        key=_chave(dados, "mao_de_obra"),
    ))
    coluna1, coluna2 = st.columns(2)
    dados["desconto_tipo"] = coluna1.radio(
        "Tipo de desconto",
        options=["valor", "percentual"],
        format_func=lambda t: "Em R$" if t == "valor" else "Em %",
        horizontal=True, key=_chave(dados, "desconto_tipo"),
    )
    dados["desconto_valor"] = arredondar_centavos(coluna2.number_input(
        "Desconto (R$)" if dados["desconto_tipo"] == "valor" else "Desconto (%)",
        min_value=0.0, max_value=MAX_DINHEIRO, step=5.0, format="%.2f",
        help="Deixe em zero se não houver desconto.",
        key=_chave(dados, "desconto_valor"),
    ))
    dados["condicoes_pagamento"] = st.text_input(
        "Condições de pagamento (opcional, aparecem no PDF)", max_chars=MAX_CONDICOES,
        placeholder="Ex.: Pix ou cartão em até 3x; 50% na aprovação.",
        key=_chave(dados, "condicoes_pagamento"),
    )
    dados["observacoes"] = st.text_area(
        "Observações (opcional, aparecem no PDF)", max_chars=MAX_OBSERVACOES,
        placeholder="Ex.: garantia de 90 dias para o serviço.",
        help="Não escreva CPF, endereço completo nem informações de saúde do cliente.",
        key=_chave(dados, "observacoes"),
    )
    dados["validade_dias"] = st.number_input(
        "Validade do orçamento (dias)",
        min_value=MIN_VALIDADE, max_value=MAX_VALIDADE, step=1,
        key=_chave(dados, "validade_dias"),
    )

    resumo = _resumo(dados, itens)
    _mostrar_totais(resumo)
    _botoes_de_navegacao(2, "Continuar para a revisão")


def _mostrar_totais(resumo):
    """Os valores que o cliente vai ver."""
    coluna1, coluna2 = st.columns(2)
    coluna1.metric("Itens", formatar_reais(resumo["itens"]))
    coluna2.metric("Mão de obra", formatar_reais(resumo["mao_de_obra"]))
    coluna1.metric("Desconto", formatar_reais(resumo["desconto"]))
    coluna2.metric("Total", formatar_reais(resumo["total"]))


def _mostrar_resumo_interno(resumo):
    """Custo, lucro e margem: só o técnico vê."""
    with componentes.cartao("interno"):
        st.markdown(":material/lock: **Resumo interno** — só você vê; não vai para o PDF")
        coluna1, coluna2 = st.columns(2)
        coluna1.metric("Custo total", formatar_reais(resumo["custo_total"]))
        coluna2.metric("Preço total", formatar_reais(resumo["total"]))
        coluna1.metric("Lucro", formatar_reais(resumo["lucro"]))
        coluna2.metric("Margem", f"{resumo['margem']:.1f}%".replace(".", ","))
        if resumo["total"] > 0 and resumo["lucro"] < 0:
            st.warning("Atenção: este orçamento dá prejuízo.")


# --------------------------------------------------------- passo 4: revisão
def _passo_revisao(user_id, dados, itens):
    st.subheader("Confira antes de salvar")
    resumo = _resumo(dados, itens)

    with componentes.cartao("rev_cliente"):
        st.markdown(f"**Cliente:** {escapar_md(dados['cliente_nome'])}")
        if dados["cliente_telefone"]:
            st.markdown(f"**WhatsApp:** {formatar_telefone(dados['cliente_telefone'])}")
        if dados["equipamento"]:
            st.markdown(f"**Equipamento:** {escapar_md(dados['equipamento'])}")

    with componentes.cartao("rev_itens"):
        _listar_itens(itens)
        if resumo["mao_de_obra"] > 0:
            st.markdown(f"Mão de obra — **{formatar_reais(resumo['mao_de_obra'])}**")

    _mostrar_totais(resumo)
    _mostrar_resumo_interno(resumo)

    # Mostra o que ainda impede de salvar (o botão fica desligado).
    erros = _erros_cliente(dados) + _erros_itens(itens) + _erros_valores(dados, resumo)
    for erro in erros:
        st.error(erro)
    _mostrar_erros()

    coluna1, coluna2 = st.columns(2)
    coluna1.button("Voltar", width="stretch", icon=":material/arrow_back:",
                   on_click=_voltar, args=(3,))
    coluna2.button("Salvar orçamento", type="primary", width="stretch",
                   icon=":material/check_circle:",
                   disabled=bool(erros), on_click=_salvar, args=(user_id,))


def _listar_itens(itens):
    for item in itens:
        subtotal = item["quantidade"] * item["preco_unitario"]
        st.markdown(
            f"{item['quantidade']} × {escapar_md(item['nome'])} — **{formatar_reais(subtotal)}**"
        )


def _salvar(user_id):
    """Callback do botão Salvar: grava no banco e troca a tela pela confirmação."""
    if not _orcamento_em_andamento():
        return   # toque duplo: o primeiro toque já salvou
    dados, itens = st.session_state["orc_dados"], st.session_state["orc_itens"]
    # Última barreira: nada é gravado se algum passo tiver erro.
    erros = _erros_cliente(dados) + _erros_itens(itens) + _erros_valores(dados, _resumo(dados, itens))
    if erros:
        st.session_state["orc_erros"] = erros
        return
    # Os valores já passaram pela validação; aqui pegamos a versão "limpa"
    # (sem espaços sobrando, telefone só com dígitos, centavos arredondados).
    dados_limpos = {
        "cliente_nome": validar_texto(dados["cliente_nome"], "Nome", MAX_NOME)[0],
        "cliente_telefone": validar_telefone(dados["cliente_telefone"])[0],
        "equipamento": validar_texto(dados["equipamento"], "Equipamento", MAX_NOME)[0],
        "mao_de_obra": validar_dinheiro(dados["mao_de_obra"], "Mão de obra")[0],
        "desconto_tipo": dados["desconto_tipo"],
        "desconto_valor": validar_dinheiro(dados["desconto_valor"], "Desconto")[0],
        "condicoes_pagamento": validar_texto(
            dados["condicoes_pagamento"], "Condições de pagamento", MAX_CONDICOES)[0],
        "observacoes": validar_texto(
            dados["observacoes"], "Observações", MAX_OBSERVACOES, multilinha=True)[0],
        "validade_dias": validar_validade(dados["validade_dias"])[0],
    }
    itens_limpos = [
        {
            "nome": validar_texto(item["nome"], "Descrição", MAX_NOME)[0],
            "tipo": item["tipo"],
            "quantidade": validar_quantidade(item["quantidade"])[0],
            "custo_unitario": validar_dinheiro(item["custo_unitario"], "Custo")[0],
            "preco_unitario": validar_dinheiro(item["preco_unitario"], "Preço")[0],
        }
        for item in itens
    ]
    # Recalcula com os valores limpos: é este total que vai para o banco.
    resumo = _resumo(dados_limpos, itens_limpos)
    try:
        gravado = db.salvar_orcamento(user_id, dados_limpos, itens_limpos, resumo["total"])
    except Exception as erro:
        codigo = db.codigo_do_erro(erro)
        if sem_conexao(erro):
            mensagem = SEM_CONEXAO + " O que você preencheu continua aqui."
        elif db.falta_coluna(erro):
            mensagem = ("O banco de dados está desatualizado. Rode o arquivo "
                        "sql/migracao_*.sql pendentes no SQL Editor do Supabase (veja o aviso no topo).")
        elif codigo == "42501":
            # O banco não reconheceu o login (regra de acesso por usuário).
            mensagem = ("O banco não reconheceu o seu login e recusou a gravação. Saia da conta, "
                        "entre de novo e salve outra vez. (código: 42501)")
        else:
            mensagem = "Não foi possível salvar o orçamento. Tente novamente."
            if codigo:
                mensagem += f" (código: {codigo})"
        st.session_state["orc_erros"] = [mensagem]
        return

    _limpar_tela()
    dados_limpos["numero"] = gravado["numero"]  # usado no PDF
    st.session_state["orc_salvo"] = {
        "id": gravado["id"], "dados": dados_limpos, "itens": itens_limpos,
        "resumo": resumo, "data": hoje_brasil(),
    }


# ------------------------------------------------------------- confirmação
def _mostrar_confirmacao(salvo):
    """Tela mostrada logo depois de salvar, com o PDF e o WhatsApp."""
    dados, resumo = salvo["dados"], salvo["resumo"]
    componentes.selo_de_sucesso()
    st.header("Orçamento salvo")
    st.success(
        f"Orçamento de **{escapar_md(dados['cliente_nome'])}** salvo: "
        f"**{formatar_reais(resumo['total'])}**"
    )
    if dados["cliente_telefone"]:
        st.caption(f"Telefone: {formatar_telefone(dados['cliente_telefone'])}")

    with componentes.cartao("salvo_itens"):
        _listar_itens(salvo["itens"])
        if resumo["mao_de_obra"] > 0:
            st.markdown(f"Mão de obra — **{formatar_reais(resumo['mao_de_obra'])}**")
        if resumo["desconto"] > 0:
            st.markdown(f"Desconto — **{formatar_reais(resumo['desconto'])}**")

    st.subheader("Enviar para o cliente")
    try:
        perfil = db.buscar_perfil(auth.usuario_id())
    except Exception:
        st.error("Não foi possível carregar seu perfil. O orçamento continua salvo.")
    else:
        compartilhar.mostrar_botoes(perfil, dados, salvo["itens"], resumo, salvo["data"])

    st.button("Criar outro orçamento", width="stretch", icon=":material/add_circle:",
              on_click=_limpar_tela)

