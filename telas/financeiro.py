"""Tela Financeiro: custo, ganho e lucro do dia, do mês ou do ano.

Entram os orçamentos fechados e os pagos (situação escolhida no histórico), pela
data em que foram fechados. As contas ficam em core/financeiro.py.
"""

import altair as alt
import pandas as pd
import streamlit as st

from core import auth, db
from core.financeiro import NOME, TIPOS, limites_utc, periodo, totais
from core.formato import formatar_reais, hoje_brasil

# Cores: custo em cinza-azulado, ganho no azul da marca, lucro em verde, prejuízo em vermelho.
COR_CUSTO, COR_GANHO, COR_LUCRO, COR_PREJUIZO = "#6B7C93", "#0A58CA", "#0E7A4B", "#B42318"
# Eixo em reais no padrão brasileiro (o formato do gráfico é americano; troca vírgula por ponto).
EIXO_REAIS = "'R$ ' + replace(format(datum.value, ',.0f'), ',', '.')"


def _deslocamento(tipo):
    return st.session_state.setdefault("fin_deslocamento", {}).get(tipo, 0)


def _andar(tipo, passo):
    deslocamentos = st.session_state.setdefault("fin_deslocamento", {})
    deslocamentos[tipo] = min(0, deslocamentos.get(tipo, 0) + passo)


def mostrar():
    st.header("Financeiro")
    st.caption(
        "Entram os orçamentos **fechados** e **pagos**, pela data em que foram fechados. "
        "Só você vê esta tela."
    )
    # required=True: sempre há um período escolhido (um toque não "desmarca").
    tipo = st.segmented_control("Período", TIPOS, default="Mês", required=True, key="fin_tipo",
                                label_visibility="collapsed", width="stretch") or "Mês"
    deslocamento = _deslocamento(tipo)
    inicio, fim, titulo = periodo(tipo, deslocamento, hoje_brasil())

    # Navegar para o período anterior / seguinte (não passa do atual).
    with st.container(horizontal=True, vertical_alignment="center", wrap=False, key="fin_navegacao"):
        st.button("Anterior", icon=":material/chevron_left:", key="fin_anterior", type="tertiary",
                  on_click=_andar, args=(tipo, -1))
        st.markdown(f"**{titulo}**", width="stretch", text_alignment="center")
        st.button("Próximo", icon=":material/chevron_right:", icon_position="right", key="fin_seguinte",
                  type="tertiary", on_click=_andar, args=(tipo, 1), disabled=deslocamento >= 0)

    user_id = auth.usuario_id()
    try:
        with st.spinner("Calculando..."):
            orcamentos = db.listar_fechados(user_id, *limites_utc(inicio, fim))
    except Exception as erro:
        if db.falta_coluna(erro):
            st.info("O Financeiro aparece aqui assim que o banco de dados for atualizado (veja o aviso acima).")
        else:
            st.error("Não foi possível carregar o Financeiro. Tente recarregar a página.")
        return

    conta = totais(orcamentos)
    nome = NOME[tipo]
    if not orcamentos:
        st.info(
            f"Nenhum orçamento fechado neste {nome}. Quando o cliente aceitar, mude a situação do "
            "orçamento em **Orçamentos** para **Fechado** ou **Pago**: ele passa a contar aqui."
        )

    _grafico(conta)
    _resumo(conta, nome)


def _clarear(cor, quanto=0.62):
    """O mesmo tom, mais claro (como se estivesse com transparência sobre o branco)."""
    r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % tuple(round(v + (255 - v) * quanto) for v in (r, g, b))


def _grafico(conta):
    """Um gráfico só: custo, ganho e lucro.

    Nas colunas de ganho e de lucro, a parte já paga vem na cor forte e a parte
    ainda não paga (orçamentos fechados) vem empilhada por cima, na mesma cor, mais clara.
    Prejuízo fica vermelho, abaixo da linha do zero.
    """
    lucro = conta["lucro"]
    coluna_lucro = "Lucro" if lucro >= 0 else "Prejuízo"
    cor_lucro = COR_LUCRO if lucro >= 0 else COR_PREJUIZO
    def reais(v):
        return formatar_reais(v) if v >= 0 else "-" + formatar_reais(abs(v))
    partes = [  # coluna, parte (legenda), valor, cor
        ("Custo", "Custo", conta["custo"], COR_CUSTO),
        ("Ganho", "Ganho pago", conta["ganho_pago"], COR_GANHO),
        ("Ganho", "Ganho a receber", conta["a_receber"], _clarear(COR_GANHO)),
        (coluna_lucro, f"{coluna_lucro} pago", conta["lucro_pago"], cor_lucro),
        (coluna_lucro, f"{coluna_lucro} a receber", conta["lucro_a_receber"], _clarear(cor_lucro)),
    ]
    # Só entram na legenda as partes que existem (sem "a receber" quando tudo já foi pago).
    partes = [p for p in partes if p[2] != 0 or p[1] in ("Custo", "Ganho pago", f"{coluna_lucro} pago")]
    dados = pd.DataFrame([{"Coluna": c, "Parte": p, "Valor": v, "Texto": reais(v), "Ordem": i}
                          for i, (c, p, v, _) in enumerate(partes)])
    totais = pd.DataFrame([
        {"Coluna": "Custo", "Valor": conta["custo"], "Texto": reais(conta["custo"])},
        {"Coluna": "Ganho", "Valor": conta["ganho"], "Texto": reais(conta["ganho"])},
        {"Coluna": coluna_lucro, "Valor": lucro, "Texto": reais(lucro)},
    ])
    ordem = ["Custo", "Ganho", coluna_lucro]
    maior = max(conta["custo"], conta["ganho"], conta["lucro_pago"] + max(conta["lucro_a_receber"], 0), lucro, 1)
    menor = min(lucro, conta["lucro_pago"], conta["lucro_a_receber"], 0)
    eixo_x = alt.X("Coluna:N", sort=ordem, axis=alt.Axis(title=None, labelAngle=0, labelFontSize=14))
    eixo_y = alt.Y("Valor:Q", stack="zero", axis=alt.Axis(title=None, labelExpr=EIXO_REAIS, tickCount=5),
                   scale=alt.Scale(domain=[menor * 1.25, maior * 1.2]))
    barras = alt.Chart(dados).mark_bar(size=52).encode(
        x=eixo_x, y=eixo_y,
        color=alt.Color("Parte:N", scale=alt.Scale(domain=[p[1] for p in partes], range=[p[3] for p in partes]),
                        legend=alt.Legend(title=None, orient="top", columns=2, labelFontSize=12, labelLimit=220, symbolType="square")),
        order=alt.Order("Ordem:Q"),
        tooltip=[alt.Tooltip("Parte:N", title=" "), alt.Tooltip("Texto:N", title="Valor")],
    )
    # O total de cada coluna aparece em cima dela (no prejuízo, embaixo).
    base_total = alt.Chart(totais).encode(x=alt.X("Coluna:N", sort=ordem), y=alt.Y("Valor:Q"))
    acima = base_total.transform_filter("datum.Valor >= 0").mark_text(dy=-10, fontSize=14, fontWeight="bold", color="#0F1B2D").encode(text="Texto:N")
    abaixo = base_total.transform_filter("datum.Valor < 0").mark_text(dy=14, fontSize=14, fontWeight="bold", color=COR_PREJUIZO).encode(text="Texto:N")
    zero = alt.Chart(pd.DataFrame([{"y": 0}])).mark_rule(color="#42526A", strokeWidth=1.5).encode(y="y:Q")
    st.subheader("Custo, ganho e lucro")
    st.altair_chart((barras + acima + abaixo + zero).properties(height=320), width="stretch",
                    alt=f"Custo {formatar_reais(conta['custo'])}; ganho {formatar_reais(conta['ganho'])}, "
                        f"dos quais {formatar_reais(conta['a_receber'])} a receber; "
                        f"{coluna_lucro.lower()} {formatar_reais(abs(lucro))}")
    if conta["a_receber"] > 0:
        st.caption("Cor forte: já pago. Cor clara: fechado, ainda não pago.")


def _reais_md(valor):
    # Dois "$" no mesmo texto viram fórmula matemática no Markdown; a barra evita isso.
    return formatar_reais(valor).replace("$", "\\$")


def _resumo(conta, nome):
    lucro = conta["lucro"]
    if lucro >= 0:
        st.markdown(f"### :green[Lucro do {nome}: {_reais_md(lucro)}]")
    else:
        st.markdown(f"### :red[Prejuízo do {nome}: {_reais_md(abs(lucro))}]")
    quantidade = conta["quantidade"]
    palavra = "orçamento fechado" if quantidade == 1 else "orçamentos fechados"
    st.caption(f"{quantidade} {palavra} · ganho {_reais_md(conta['ganho'])} · custo {_reais_md(conta['custo'])}")
    if conta["a_receber"] > 0:
        st.markdown(f":orange[:material/schedule:] Ainda falta receber **{_reais_md(conta['a_receber'])}**, "
                    f"com **{_reais_md(conta['lucro_a_receber'])}** de lucro.")
