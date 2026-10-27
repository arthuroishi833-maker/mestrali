"""Identidade visual e componentes reaproveitados por todas as telas.

O que fica onde
---------------
  - .streamlit/config.toml  -> cores, FONTES, tamanhos dos títulos e cantos
                               arredondados (o tema oficial do Streamlit)
  - este arquivo            -> só o que o tema não alcança: o menu, a página
                               inicial, a trilha de passos e as animações

Funções:
  - aplicar_estilo(): injeta o CSS abaixo. Chamada uma vez, no app.py
  - menu_principal(): barra de navegação (embaixo no celular, em cima no computador)
  - rodape(): links para Ajuda e Privacidade no fim de toda tela
  - cartao(): caixa com borda fina, para agrupar um objeto (um item, um orçamento)
  - grade(): lista que vira duas colunas quando a tela é larga

Celular x computador: o app não "descobre" o aparelho. O CSS pergunta ao
navegador a LARGURA da janela (@media) e escolhe o desenho:
  - até 640px         -> celular: menu fixo embaixo, tudo em uma coluna
  - de 641 a 999px    -> tablet: abas no topo, uma coluna
  - 1000px ou mais    -> computador: menu na lateral, listas em duas colunas,
                         e tudo maior (letras, campos e botões)
É o jeito padrão da web: funciona também se a pessoa só estreitar a janela.
  - indicador_de_passos(): a trilha "1. Cliente  2. Itens ..."
  - selo_de_sucesso(): o "visto" animado depois de salvar
  - destaque_inicial(): a abertura da página inicial

Fontes: Source Sans (textos) e Source Serif (títulos). As duas já vêm dentro
do Streamlit, então nada é baixado de servidores externos.

SEGURANÇA: o HTML deste arquivo é sempre texto fixo, escrito aqui.
Nunca coloque texto digitado pelo usuário dentro de st.html().
"""

import streamlit as st

# Paleta (a mesma do .streamlit/config.toml e do PDF).
TINTA = "#0F1B2D"          # texto. Sobre branco: contraste 17:1
TINTA_SUAVE = "#42526A"    # texto secundário. Sobre branco: 8:1
AZUL = "#0A58CA"           # ação principal. Branco sobre ele: 6,5:1
AZUL_PROFUNDO = "#083A7A"  # item ativo do menu, toque em botões
NEVOA = "#F3F6FA"          # superfícies de apoio
LINHA = "#D5DEE8"          # divisórias e bordas de cartões
VERDE = "#0E7A4B"          # lucro e confirmações
LARGURA_DO_MENU = "13rem"  # menu lateral, só no computador

_CSS = f"""
<style>
:root {{ color-scheme: light; }}

/* ---------- Base ---------- */
.stApp {{ background: #FFFFFF; color: {TINTA}; }}
/* A barra do topo do Streamlit fica vazia neste app: some, e o conteúdo sobe. */
[data-testid="stHeader"] {{ display: none; }}
[data-testid="stMainBlockContainer"] {{
    max-width: 680px;
    padding-top: 1.75rem;
    padding-bottom: 3rem;
}}

/* Títulos: a fonte e os tamanhos vêm do tema; aqui só o ajuste fino. */
.stApp h1, .stApp h2 {{ letter-spacing: -0.012em; line-height: 1.15; text-wrap: balance; }}
.stApp h3 {{ line-height: 1.25; text-wrap: balance; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
    color: {TINTA_SUAVE} !important; opacity: 1; font-size: 0.95rem; line-height: 1.45;
}}

/* ---------- Menu principal ----------
   No computador: abas de texto no topo. No celular: barra fixa embaixo,
   ao alcance do polegar, como nos aplicativos. */
.st-key-menu_principal {{
    flex-wrap: nowrap; gap: 0.15rem;
    border-bottom: 1px solid {LINHA}; margin-bottom: 0.4rem;
}}
.st-key-menu_principal > [data-testid="stLayoutWrapper"] {{ flex: 0 0 auto; width: auto; }}
.st-key-menu_principal [data-testid="stPageLink"] a {{
    min-height: 2.75rem; padding: 0.4rem 0.85rem;
    border-radius: 8px 8px 0 0; border-bottom: 2px solid transparent; margin-bottom: -1px;
    background: transparent; transition: background-color 0.15s ease;
}}
.st-key-menu_principal [data-testid="stPageLink"] a:hover {{ background: {NEVOA}; }}
.st-key-menu_principal [data-testid="stPageLink"] a p {{
    font-weight: 600; color: {TINTA_SUAVE}; white-space: nowrap; overflow: visible;
}}
.st-key-menu_principal [data-testid="stPageLink"] a span {{ color: {TINTA_SUAVE}; }}
.st-key-menu_atual [data-testid="stPageLink"] a {{ border-bottom-color: {AZUL}; }}
.st-key-menu_atual [data-testid="stPageLink"] a p,
.st-key-menu_atual [data-testid="stPageLink"] a span {{ color: {AZUL_PROFUNDO}; }}

@media (max-width: 640px) {{
    .st-key-menu_principal {{
        position: fixed; left: 0; right: 0; bottom: 0; z-index: 999;
        width: 100vw; margin: 0; gap: 0;
        /* "--folga-da-hospedagem": altura dos selos do Streamlit Cloud (core/cookie_sessao.py). */
        padding: 5px 6px calc(5px + env(safe-area-inset-bottom) + var(--folga-da-hospedagem, 0px));
        background: rgba(255, 255, 255, 0.97); backdrop-filter: blur(10px);
        border-bottom: 0; border-top: 1px solid {LINHA};
    }}
    .st-key-menu_principal > [data-testid="stLayoutWrapper"] {{ flex: 1 1 0; min-width: 0; }}
    .st-key-menu_principal [data-testid="stElementContainer"],
    .st-key-menu_principal [data-testid="stPageLink"],
    .st-key-menu_principal [data-testid="stPageLink"] > div {{ width: 100% !important; }}
    .st-key-menu_principal [data-testid="stPageLink"] a {{
        flex-direction: column; justify-content: center; gap: 1px; width: 100%;
        min-height: 3.3rem; padding: 5px 2px; margin: 0;
        border: 0; border-radius: 10px;
    }}
    .st-key-menu_principal [data-testid="stPageLink"] a p {{ font-size: 0.74rem; line-height: 1.1; }}
    .st-key-menu_atual [data-testid="stPageLink"] a {{ background: #E8F0FB; }}
    /* Espaço para o conteúdo não ficar escondido atrás da barra. */
    [data-testid="stMainBlockContainer"] {{
        padding-top: 1.25rem; padding-bottom: calc(6.5rem + var(--folga-da-hospedagem, 0px));
    }}
}}

/* ---------- Botões e campos ---------- */
[data-testid^="stBaseButton"], [data-testid^="stBaseLinkButton"] {{
    min-height: 3rem;
    transition: transform 0.08s ease, background-color 0.15s ease, border-color 0.15s ease;
}}
[data-testid^="stBaseButton"] p, [data-testid^="stBaseLinkButton"] p {{ font-weight: 600; font-size: 1.02rem; }}
[data-testid^="stBaseButton"]:active, [data-testid^="stBaseLinkButton"]:active {{ transform: scale(0.985); }}
[data-testid^="stBaseButton"]:focus-visible, [data-testid^="stBaseLinkButton"]:focus-visible {{
    outline: 3px solid #8DB8F5; outline-offset: 2px;
}}
[data-testid^="stBaseButton"]:disabled {{ opacity: 0.5; transform: none; }}

.stApp input, .stApp textarea {{ font-size: 1.05rem; }}
.stApp input {{ min-height: 2.9rem; }}
[data-testid="stNumberInput"] input {{ font-variant-numeric: tabular-nums; }}
[data-testid="stWidgetLabel"] p {{ font-weight: 600; font-size: 0.98rem; color: {TINTA}; }}

/* ---------- Superfícies ---------- */
/* Cartões só para objetos (um item, um orçamento). Borda fina, sem sombra. */
[class*="st-key-cartao_"], [data-testid="stForm"], [data-testid="stExpander"] details {{
    background: #FFFFFF;
    border: 1px solid {LINHA} !important;
    border-radius: 14px !important;
    box-shadow: none;
}}
[data-testid="stExpander"] summary {{ min-height: 3.1rem; font-weight: 600; }}

/* Totais: números alinhados coluna a coluna. */
[data-testid="stMetric"] {{ background: {NEVOA}; border-radius: 12px; padding: 0.65rem 0.85rem; }}
[data-testid="stMetricLabel"] p {{ color: {TINTA_SUAVE}; font-weight: 600; font-size: 0.9rem; }}
[data-testid="stMetricValue"] {{
    color: {TINTA}; font-weight: 700; font-size: 1.4rem; font-variant-numeric: tabular-nums;
}}

/* No celular o Streamlit empilha as colunas. Para os totais isso vira uma
   pilha de blocos grandes; aqui eles continuam lado a lado, em grade 2x2. */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {{
    flex-wrap: nowrap !important; gap: 0.6rem;
}}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"])
    > [data-testid="stColumn"] {{ flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }}
@media (max-width: 640px) {{
    [data-testid="stMetricValue"] {{ font-size: 1.2rem; }}
    [data-testid="stMetric"] {{ padding: 0.55rem 0.7rem; }}
}}
/* O tamanho do número acompanha a largura da caixa (16% do espaço interno),
   para valores até "R$ 125.450,00" caberem numa linha só em qualquer celular,
   no maior tamanho possível. Navegador antigo, que não conhece essa unidade,
   fica com os tamanhos fixos acima. */
[data-testid="stMetric"] {{ container-type: inline-size; }}
@supports (font-size: 1cqi) {{
    [data-testid="stMetricValue"] {{ font-size: clamp(0.82rem, 16cqi, 1.4rem); }}
}}
/* Um valor em dinheiro nunca pode aparecer cortado com "...": o técnico leria
   um total errado. Se ainda assim não couber (valor muito alto), o valor
   quebra de linha e continua inteiro. */
[data-testid="stMetricValue"] [data-testid="stMarkdownContainer"],
[data-testid="stMetricValue"] p {{
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
    overflow-wrap: anywhere; line-height: 1.2;
}}

/* Lista de orçamentos: dentro de cada cartão, dados à esquerda e "Abrir" à
   direita, na mesma linha também no celular. */
[class*="st-key-cartao_orc_"] [data-testid="stHorizontalBlock"] {{
    flex-wrap: nowrap !important; align-items: center; gap: 0.75rem;
}}
[class*="st-key-cartao_orc_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    min-width: 0 !important; width: auto !important;
}}
[class*="st-key-cartao_orc_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {{ flex: 1 1 auto !important; }}
[class*="st-key-cartao_orc_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{ flex: 0 0 7.2rem !important; }}

.st-key-rodape [data-testid="stPageLink"] a p {{ color: {TINTA_SUAVE}; font-size: 0.92rem; }}
.st-key-rodape [data-testid="stPageLink"] a span {{ color: {TINTA_SUAVE}; }}

/* ---------- Trilha de passos ---------- */
.passos {{ display: flex; gap: 5px; margin: 0.1rem 0 0.4rem; }}
.passo {{ flex: 1; }}
.passo .barra {{ height: 4px; border-radius: 4px; background: {LINHA}; overflow: hidden; }}
.passo .barra::after {{ content: ""; display: block; height: 100%; width: 0; background: {AZUL}; }}
.passo.feito .barra::after {{ width: 100%; opacity: 0.45; }}
.passo.atual .barra::after {{ width: 100%; animation: encher 0.4s ease-out; }}
.passo .rotulo {{
    display: block; margin-top: 7px; font-size: 0.82rem; font-weight: 600; color: {TINTA_SUAVE};
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.passo.atual .rotulo {{ color: {AZUL_PROFUNDO}; font-weight: 700; }}
@keyframes encher {{ from {{ width: 0; }} to {{ width: 100%; }} }}

/* O conteúdo de cada passo entra suavemente quando o passo muda. */
[class*="st-key-passo_"] {{ animation: surgir 0.22s ease-out; }}
@keyframes surgir {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

/* ---------- Confirmação de "salvo" ---------- */
.sucesso {{
    width: 56px; height: 56px; border-radius: 50%; background: {VERDE};
    display: flex; align-items: center; justify-content: center;
    animation: pousar 0.32s cubic-bezier(0.2, 0.9, 0.3, 1.25) both;
}}
.sucesso .visto {{
    width: 13px; height: 25px; margin-top: -5px;
    border: solid #FFFFFF; border-width: 0 4px 4px 0; transform: rotate(45deg);
    animation: riscar 0.3s 0.22s ease-out both;
}}
@keyframes pousar {{ from {{ opacity: 0; transform: scale(0.6); }} to {{ opacity: 1; transform: scale(1); }} }}
@keyframes riscar {{
    from {{ clip-path: inset(0 0 100% 0); }}
    to   {{ clip-path: inset(0 0 0 0); }}
}}

/* ---------- Página inicial ---------- */
.abertura {{ display: grid; grid-template-columns: 1fr; gap: 1.6rem; align-items: center; margin-bottom: 0.4rem; }}
.abertura h1 {{
    font-family: "Source Serif", Georgia, serif; font-weight: 650; color: {TINTA};
    font-size: 2.05rem; line-height: 1.1; letter-spacing: -0.02em; text-wrap: balance;
    margin: 0 0 0.7rem; padding: 0;
}}
.abertura p {{ font-size: 1.08rem; line-height: 1.5; color: {TINTA_SUAVE}; margin: 0; max-width: 34ch; }}

/* A "cena": uma folha de orçamento como a que o técnico envia, com o lucro
   aparecendo ao lado. É o produto mostrado, em vez de uma ilustração genérica. */
.cena {{
    position: relative; padding: 1.1rem 1.1rem 4.3rem; border-radius: 18px; background: {NEVOA};
    font-variant-numeric: tabular-nums;
}}
.folha {{
    background: #FFFFFF; border: 1px solid {LINHA}; border-top: 4px solid {AZUL}; border-radius: 4px;
    padding: 0.9rem 0.95rem 0.8rem; transform: rotate(-1.1deg);
    box-shadow: 0 1px 2px rgba(15, 27, 45, 0.06), 0 14px 30px -12px rgba(15, 27, 45, 0.28);
    animation: pousar-folha 0.45s ease-out both;
}}
.folha-topo {{
    display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline;
    gap: 0.1rem 0.6rem; margin-bottom: 0.55rem;
}}
.folha-titulo {{
    font-family: "Source Serif", Georgia, serif; font-weight: 650; font-size: 1.02rem; color: {TINTA};
    white-space: nowrap;
}}
.folha-equip {{ font-size: 0.78rem; color: {TINTA_SUAVE}; white-space: nowrap; }}
.linha-item {{
    display: flex; justify-content: space-between; gap: 0.8rem;
    padding: 0.36rem 0; border-top: 1px solid #E6ECF3; font-size: 0.88rem; color: {TINTA};
    animation: surgir 0.3s ease-out both;
}}
.linha-item span:last-child, .linha-total span:last-child {{ white-space: nowrap; }}
.linha-item.i1 {{ animation-delay: 0.30s; }}
.linha-item.i2 {{ animation-delay: 0.44s; }}
.linha-item.i3 {{ animation-delay: 0.58s; }}
.linha-total {{
    display: flex; justify-content: space-between; margin-top: 0.5rem; padding: 0.5rem 0.65rem;
    background: {AZUL}; color: #FFFFFF; border-radius: 3px; font-weight: 700; font-size: 0.98rem;
    animation: surgir 0.3s 0.78s ease-out both;
}}
.lucro {{
    position: absolute; right: 0.55rem; bottom: 0.6rem;
    display: flex; flex-direction: column; gap: 1px; padding: 0.5rem 0.75rem;
    background: #FFFFFF; border: 1.5px solid {VERDE}; border-radius: 12px;
    box-shadow: 0 10px 22px -10px rgba(14, 122, 75, 0.45);
    animation: revelar 0.42s 1.15s cubic-bezier(0.2, 0.9, 0.3, 1.15) both;
}}
.lucro-rotulo {{ font-size: 0.72rem; font-weight: 600; color: {TINTA_SUAVE}; }}
.lucro-valor {{ font-size: 1.2rem; font-weight: 700; color: {VERDE}; line-height: 1.15; }}
.lucro-margem {{ font-size: 0.74rem; color: {TINTA_SUAVE}; }}
@keyframes pousar-folha {{
    from {{ opacity: 0; transform: translateY(14px) rotate(0deg); }}
    to   {{ opacity: 1; transform: translateY(0) rotate(-1.1deg); }}
}}
@keyframes revelar {{
    from {{ opacity: 0; transform: translate(-14px, -10px) scale(0.92); }}
    to   {{ opacity: 1; transform: translate(0, 0) scale(1); }}
}}
@media (min-width: 641px) {{
    .abertura {{ grid-template-columns: 1.05fr 1fr; gap: 2rem; margin: 0.6rem 0 1rem; }}
    .abertura h1 {{ font-size: 2.45rem; }}
}}

/* ---------- Computador (janela com 1000px ou mais) ----------
   Tudo o que muda no computador fica neste bloco. */
@media (min-width: 1000px) {{
    /* Tudo maior: no computador a tela fica mais longe dos olhos que o celular.
       Os tamanhos do app são em "rem" (múltiplos deste valor), então textos,
       campos e botões crescem juntos. No celular o tamanho base é 17px. */
    html {{ font-size: 20px !important; }}
    [data-testid="stMainBlockContainer"] {{ max-width: 54rem; padding-top: 2.5rem; }}

    /* Menu na lateral esquerda, fixo, como em um programa de computador. */
    .st-key-menu_principal {{
        position: fixed; left: 0; top: 0; bottom: 0; z-index: 999;
        width: {LARGURA_DO_MENU}; margin: 0; padding: 1.4rem 0.9rem;
        flex-direction: column; flex-wrap: nowrap; align-items: stretch; gap: 0.2rem;
        background: {NEVOA}; border-bottom: 0; border-right: 1px solid {LINHA};
    }}
    .st-key-menu_principal::before {{
        content: "Orçamentos"; display: block; padding: 0 0.7rem 1.1rem;
        font-family: "Source Serif", Georgia, serif; font-weight: 650; font-size: 1.3rem;
        letter-spacing: -0.012em; color: {TINTA};
    }}
    .st-key-menu_principal > [data-testid="stLayoutWrapper"] {{ flex: 0 0 auto; width: 100%; }}
    .st-key-menu_principal [data-testid="stElementContainer"],
    .st-key-menu_principal [data-testid="stPageLink"],
    .st-key-menu_principal [data-testid="stPageLink"] > div {{ width: 100% !important; }}
    .st-key-menu_principal [data-testid="stPageLink"] a {{
        width: 100%; justify-content: flex-start; gap: 0.6rem;
        min-height: 2.9rem; padding: 0.5rem 0.7rem; margin: 0;
        border: 0; border-radius: 10px;
    }}
    .st-key-menu_principal [data-testid="stPageLink"] a:hover {{ background: #E6ECF3; }}
    .st-key-menu_atual [data-testid="stPageLink"] a,
    .st-key-menu_atual [data-testid="stPageLink"] a:hover {{ background: #DCE8F8; }}
    /* O conteúdo abre espaço para o menu (só nas telas que têm menu). */
    .stApp:has(.st-key-menu_principal) [data-testid="stMain"] {{ padding-left: {LARGURA_DO_MENU}; }}

    /* Listas em duas colunas. */
    [class*="st-key-grade_"] {{
        display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem 1rem; align-items: start;
    }}
    [class*="st-key-grade_"] > * {{ width: 100% !important; min-width: 0; }}

    /* Página inicial: apresentação à esquerda, acesso à direita. */
    [data-testid="stMainBlockContainer"]:has(.st-key-inicio) {{ max-width: 66rem; }}
    .st-key-inicio {{
        display: grid; grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
        column-gap: 3.5rem; row-gap: 1.5rem; align-items: start;
    }}
    .st-key-inicio > * {{ width: 100% !important; min-width: 0; }}
    .st-key-inicio > :has(.st-key-inicio_abertura) {{ grid-column: 1; grid-row: 1; }}
    .st-key-inicio > :has(.st-key-inicio_mais) {{ grid-column: 1; grid-row: 2; }}
    .st-key-inicio > :has(.st-key-inicio_acesso) {{ grid-column: 2; grid-row: 1 / span 2; }}
    .st-key-inicio_acesso {{
        padding: 1.5rem 1.6rem 1.2rem; border: 1px solid {LINHA}; border-radius: 16px;
        background: #FFFFFF;
    }}
    /* Na coluna da esquerda, o texto fica em cima e a folha de exemplo embaixo. */
    .st-key-inicio .abertura {{ grid-template-columns: 1fr; gap: 1.8rem; margin: 0.4rem 0 0; }}
    .st-key-inicio .abertura h1 {{ font-size: 2.9rem; }}
    .st-key-inicio .abertura p {{ font-size: 1.15rem; max-width: 40ch; }}
    .st-key-inicio .cena {{ max-width: 24rem; }}
}}

/* Monitores largos: mais um degrau de tamanho. */
@media (min-width: 1400px) {{
    html {{ font-size: 22px !important; }}
}}

/* Quem pede menos movimento no aparelho não recebe animações. */
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation: none !important; transition: none !important; }}
}}
</style>
"""


def aplicar_estilo():
    """Aplica a identidade visual. Chamada uma vez, no início do app.py."""
    st.html(_CSS)


def menu_principal(paginas, atual):
    """Navegação sempre visível: barra embaixo no celular, abas no topo no computador.

    paginas: lista de st.Page.  atual: a página aberta agora (fica destacada).
    """
    with st.container(horizontal=True, key="menu_principal", gap="small"):
        for pagina in paginas:
            # A chave vira uma classe CSS; "menu_atual" recebe o destaque.
            e_atual = pagina.url_path == atual.url_path
            chave = "menu_atual" if e_atual else f"menu_link_{pagina.url_path}"
            with st.container(key=chave):
                st.page_link(pagina, label=pagina.title, icon=pagina.icon, width="content")


def rodape(paginas, atual):
    """Links discretos no fim de toda tela (Ajuda, Privacidade).

    paginas: lista de st.Page.  atual: a página aberta agora (não aparece no rodapé).
    """
    outras = [p for p in paginas if p.url_path != atual.url_path]
    if not outras:
        return
    st.divider()
    with st.container(horizontal=True, key="rodape", gap="small"):
        for pagina in outras:
            st.page_link(pagina, label=pagina.title, icon=pagina.icon, width="content")


def cartao(nome):
    """Caixa com borda fina. Use com `with componentes.cartao("x"):`.

    `nome` precisa ser único na tela (vira a chave do componente) e é
    sempre definido no código, nunca vem de texto digitado.
    """
    return st.container(border=True, key=f"cartao_{nome}")


def grade(nome):
    """Lista de cartões: uma coluna no celular, duas no computador.

    Use com `with componentes.grade("x"):` em volta do laço que desenha os
    cartões. `nome` é sempre definido no código (vira a chave do componente).
    """
    return st.container(key=f"grade_{nome}")


def indicador_de_passos(passos, atual):
    """Trilha de progresso. `passos` é uma lista FIXA de rótulos do código."""
    partes = []
    for numero, rotulo in enumerate(passos):
        classe = "atual" if numero == atual else "feito" if numero < atual else ""
        partes.append(
            f'<div class="passo {classe}"><div class="barra"></div>'
            f'<span class="rotulo">{numero + 1}. {rotulo}</span></div>'
        )
    st.html(f'<div class="passos" aria-label="Passo {atual + 1} de {len(passos)}">{"".join(partes)}</div>')


def selo_de_sucesso():
    """O "visto" verde que aparece quando algo foi salvo."""
    st.html('<div class="sucesso" role="img" aria-label="Salvo"><span class="visto"></span></div>')


def destaque_inicial():
    """Abertura da página inicial (antes do login).

    Os valores da folha de exemplo são os do catálogo inicial do sistema:
    limpeza (R$ 180), 2 capacitores (R$ 90 cada) e carga de gás (R$ 350)
    somam R$ 710; os custos somam R$ 230, logo o lucro é R$ 480 (67,6%).
    """
    st.html("""
    <div class="abertura">
      <div>
        <h1>Orçamento profissional em minutos, direto do celular</h1>
        <p>Para quem presta serviço na casa do cliente: ar-condicionado, elétrica,
        hidráulica, câmeras, bikes elétricas e assistência técnica. Monte o orçamento no local,
        veja o seu lucro na hora e envie o PDF pelo WhatsApp.</p>
      </div>
      <div class="cena" role="img"
           aria-label="Exemplo de orçamento com três itens e total de R$ 710,00. Ao lado, o lucro de R$ 480,00, que só o técnico vê.">
        <div class="folha" aria-hidden="true">
          <div class="folha-topo">
            <span class="folha-titulo">Orçamento nº 0012</span>
            <span class="folha-equip">Split 12.000 BTUs</span>
          </div>
          <div class="linha-item i1"><span>Limpeza / higienização</span><span>R$ 180,00</span></div>
          <div class="linha-item i2"><span>Capacitor, 2 un.</span><span>R$ 180,00</span></div>
          <div class="linha-item i3"><span>Carga de gás</span><span>R$ 350,00</span></div>
          <div class="linha-total"><span>Total</span><span>R$ 710,00</span></div>
        </div>
        <div class="lucro" aria-hidden="true">
          <span class="lucro-rotulo">Seu lucro, só você vê</span>
          <span class="lucro-valor">R$ 480,00</span>
          <span class="lucro-margem">margem de 67,6%</span>
        </div>
      </div>
    </div>
    """)


def aviso_banco_desatualizado():
    """Explica como atualizar o banco quando faltam as colunas novas."""
    st.error(
        "**O banco de dados precisa ser atualizado.** Enquanto isso, partes do "
        "sistema (orçamentos e privacidade) podem não funcionar."
    )
    with st.expander("Como atualizar (leva 1 minuto)", expanded=True, icon=":material/build:"):
        st.markdown(
            "1. Abra o painel do Supabase e entre no seu projeto.\n"
            "2. No menu da esquerda, clique em **SQL Editor** e depois em **New query**.\n"
            "3. Abra a pasta `sql` do projeto. Para cada arquivo `migracao_*.sql` que você "
            "ainda não rodou, em ordem numérica: copie tudo, cole lá e clique em **Run**.\n"
            "4. Deve aparecer *Success* em cada um. Rodar um arquivo repetido não estraga nada.\n"
            "5. Volte aqui e recarregue a página."
        )


def faixa_de_teste():
    """Faixa fixa no alto da tela, só no app de teste."""
    st.html(
        "<div style='position:fixed;top:0;left:0;right:0;z-index:1000000;"
        "background:#ffd34d;color:#0f1b2d;text-align:center;font-weight:800;"
        "font-size:0.85rem;padding:4px 8px;letter-spacing:0.02em;'>"
        "Ambiente de teste: os dados daqui não são dos técnicos</div>"
    )
