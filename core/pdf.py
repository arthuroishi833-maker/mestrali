"""Gera o PDF do orçamento que vai para o cliente.

REGRA DE OURO: este arquivo nunca lê custo, lucro nem margem.
Dos itens ele usa só nome, quantidade e preço; do resumo, só itens,
mão de obra, subtotal, desconto e total. O teste tests/test_pdf.py confere.

O fpdf2 funciona como desenhar numa folha: um "cursor" anda pela página
e cada comando escreve algo onde o cursor está. Medidas em milímetros.

Ordem do documento:
    cabeçalho (logo + empresa)  ->  título e datas  ->  cliente
    ->  tabela de itens  ->  totais  ->  pagamento  ->  observações
    e, em toda página, um rodapé com o contato e o número da página.
"""

import io
import re
import unicodedata
from datetime import timedelta

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from PIL import Image

from core.cores import paleta
from core.formato import formatar_reais
from core.imagem import logo_para_bytes
from core.validacao import formatar_telefone

MARGEM_PAGINA = 15       # mm
LOGO_LARGURA_MAX = 60    # mm
LOGO_ALTURA_MAX = 32     # mm

# Cores (R, G, B) fixas. A cor de destaque (azul, por padrão) e os tons claros tirados
# dela vêm do perfil do técnico (core/cores.py) e ficam guardados em pdf.cores.
TEXTO = (15, 23, 42)
CINZA = (71, 85, 105)

# Caracteres comuns que a fonte padrão do PDF não tem, e seus substitutos.
_TROCAS = {"–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "•": "-"}


def _limpar(texto):
    """Deixa o texto só com caracteres que a fonte do PDF conhece.

    A fonte padrão (Helvetica) cobre o português inteiro, mas não emojis
    nem outros alfabetos. O que não existe vira "?" em vez de quebrar o PDF.
    """
    texto = str(texto or "")
    for original, novo in _TROCAS.items():
        texto = texto.replace(original, novo)
    return texto.encode("latin-1", errors="replace").decode("latin-1")


def nome_arquivo(cliente_nome, data):
    """ "Maria Conceição" -> "orcamento-maria-conceicao-2026-10-09.pdf" """
    sem_acento = unicodedata.normalize("NFKD", cliente_nome or "")
    sem_acento = sem_acento.encode("ascii", "ignore").decode("ascii")
    nome = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-") or "cliente"
    return f"orcamento-{nome[:40]}-{data.isoformat()}.pdf"


def formatar_numero(numero):
    """12 -> "0012". Devolve "" quando o orçamento não tem número."""
    return f"{int(numero):04d}" if numero else ""


class _Documento(FPDF):
    """Página A4 com rodapé automático (o fpdf2 chama footer() em cada página)."""

    texto_rodape = ""

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*CINZA)
        # Reserva o canto direito para "Página X de Y": o contato não pode invadi-lo.
        largura_do_contato = self.w - 2 * MARGEM_PAGINA - 30
        self.cell(0, 5, _cortar(self, self.texto_rodape, largura_do_contato), align="L")
        self.set_x(MARGEM_PAGINA)
        # {nb} é trocado pelo total de páginas quando o PDF é finalizado.
        self.cell(0, 5, _limpar(f"Página {self.page_no()} de {{nb}}"), align="R")


def gerar_pdf(perfil, dados, itens, resumo, data):
    """Monta o PDF e devolve os bytes do arquivo.

    perfil: dict do técnico (nome_empresa, telefone, logo_base64)
    dados:  dict do orçamento (cliente_nome, cliente_telefone, equipamento,
            desconto_tipo, desconto_valor, observacoes, validade_dias e,
            opcionais, numero e condicoes_pagamento)
    itens:  lista de dicts (nome, quantidade, preco_unitario)
    resumo: dict de core.calculos (itens, mao_de_obra, subtotal, desconto, total)
    data:   data de emissão (datetime.date)
    """
    pdf = _Documento(format="A4")
    pdf.cores = paleta(perfil.get("cor_orcamento"))
    pdf.set_margins(MARGEM_PAGINA, MARGEM_PAGINA, MARGEM_PAGINA)
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_title(_limpar(f"Orçamento - {dados['cliente_nome']}"))
    contato = [perfil.get("nome_empresa") or "", formatar_telefone(perfil.get("telefone") or "")]
    pdf.texto_rodape = _limpar("  |  ".join(parte for parte in contato if parte))
    pdf.add_page()

    _cabecalho(pdf, perfil)
    _titulo(pdf, dados, data)
    _cliente(pdf, dados)
    _tabela_itens(pdf, itens)
    _totais(pdf, dados, resumo)
    _secao_de_texto(pdf, "Condições de pagamento", dados.get("condicoes_pagamento"))
    _secao_de_texto(pdf, "Observações", dados.get("observacoes"))
    return bytes(pdf.output())


def _linha(pdf, texto, tamanho=10, estilo="", cor=TEXTO, alinhamento="L", altura=6):
    """Escreve uma linha de texto e desce o cursor para a linha seguinte."""
    pdf.set_font("Helvetica", estilo, tamanho)
    pdf.set_text_color(*cor)
    pdf.cell(0, altura, _limpar(texto), align=alinhamento,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _paragrafo(pdf, texto, tamanho=10, estilo="", cor=TEXTO, alinhamento="L", altura=6,
               x=None, largura=0):
    """Como _linha, mas QUEBRA o texto em várias linhas quando ele não cabe.

    Use para tudo que o usuário digita (nome do cliente, da empresa, equipamento):
    um nome comprido não pode sair da folha nem passar por cima do logo.
    x e largura delimitam a faixa onde o texto pode ficar (padrão: a largura toda).
    """
    pdf.set_font("Helvetica", estilo, tamanho)
    pdf.set_text_color(*cor)
    if x is not None:
        pdf.set_x(x)
    pdf.multi_cell(largura, altura, _limpar(texto), align=alinhamento,
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _cortar(pdf, texto, largura):
    """Encurta o texto com "..." até caber em `largura` (para o rodapé, de uma linha só)."""
    texto = _limpar(texto)
    if pdf.get_string_width(texto) <= largura:
        return texto
    while texto and pdf.get_string_width(texto + "...") > largura:
        texto = texto[:-1]
    return texto.rstrip() + "..."


def _titulo_de_secao(pdf, texto):
    _linha(pdf, texto.upper(), 9, "B", pdf.cores["principal"], altura=6)


def _cabecalho(pdf, perfil):
    """Logo à esquerda (se houver) e contato do técnico à direita."""
    topo = pdf.get_y()
    altura_logo = largura_logo = 0
    if perfil.get("logo_base64"):
        try:
            dados_logo = logo_para_bytes(perfil["logo_base64"])
            largura_px, altura_px = Image.open(io.BytesIO(dados_logo)).size
            # Escala para caber na caixa máxima sem deformar.
            escala = min(LOGO_LARGURA_MAX / largura_px, LOGO_ALTURA_MAX / altura_px)
            pdf.image(io.BytesIO(dados_logo), x=MARGEM_PAGINA, y=topo,
                      w=largura_px * escala, h=altura_px * escala)
            altura_logo = altura_px * escala
            largura_logo = largura_px * escala
        except Exception:
            altura_logo = largura_logo = 0  # logo ilegível: o PDF sai sem ele, em vez de falhar

    # O texto ocupa só a faixa à direita do logo. Um nome de empresa comprido
    # quebra em mais linhas ali dentro, em vez de passar por cima do logo.
    x_texto = MARGEM_PAGINA + largura_logo + (5 if largura_logo else 0)
    largura_texto = pdf.w - MARGEM_PAGINA - x_texto
    pdf.set_y(topo)
    _paragrafo(pdf, perfil.get("nome_empresa") or "", 16, "B", pdf.cores["principal"], "R", 8,
               x=x_texto, largura=largura_texto)
    if perfil.get("telefone"):
        _paragrafo(pdf, f"Tel./WhatsApp: {formatar_telefone(perfil['telefone'])}", 10, "",
                   CINZA, "R", x=x_texto, largura=largura_texto)

    # Continua abaixo do que for mais alto: o logo ou o texto.
    pdf.set_y(max(pdf.get_y(), topo + altura_logo) + 4)
    pdf.set_draw_color(*pdf.cores["principal"])
    pdf.set_line_width(0.8)
    pdf.line(MARGEM_PAGINA, pdf.get_y(), pdf.w - MARGEM_PAGINA, pdf.get_y())
    pdf.ln(7)


def _titulo(pdf, dados, data):
    """Título com o nome do cliente e a faixa com número, emissão e validade."""
    _paragrafo(pdf, f"Orçamento para {dados['cliente_nome']}", 17, "B", altura=9)
    pdf.ln(1)

    dias = dados["validade_dias"]
    vence = data + timedelta(days=dias)
    texto_dias = "1 dia" if dias == 1 else f"{dias} dias"
    partes = []
    if formatar_numero(dados.get("numero")):
        partes.append(f"Nº {formatar_numero(dados['numero'])}")
    partes.append(f"Emissão: {data.strftime('%d/%m/%Y')}")
    partes.append(f"Válido até {vence.strftime('%d/%m/%Y')} ({texto_dias})")

    # Faixa clara (um tom da cor do orçamento) ocupando a largura toda.
    pdf.set_fill_color(*pdf.cores["gelo"])
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*TEXTO)
    pdf.cell(0, 9, _limpar("     ".join(partes)), align="C", fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)


def _cliente(pdf, dados):
    _titulo_de_secao(pdf, "Cliente")
    _paragrafo(pdf, dados["cliente_nome"], 11, "B")
    if dados.get("cliente_telefone"):
        _linha(pdf, f"Telefone: {formatar_telefone(dados['cliente_telefone'])}")
    if dados.get("equipamento"):
        _paragrafo(pdf, f"Equipamento: {dados['equipamento']}")
    pdf.ln(5)


def _tabela_itens(pdf, itens):
    if not itens:
        return
    _titulo_de_secao(pdf, "Itens")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXTO)
    pdf.set_draw_color(*pdf.cores["borda"])
    pdf.set_line_width(0.2)
    # A tabela quebra de página sozinha e repete o título das colunas.
    with pdf.table(
        col_widths=(50, 10, 20, 20),  # proporções das colunas
        text_align=("LEFT", "CENTER", "RIGHT", "RIGHT"),
        line_height=7.5,
        headings_style=FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=pdf.cores["principal"]),
        cell_fill_color=pdf.cores["listra"],
        cell_fill_mode="ROWS",  # linhas alternadas com um tom bem leve da cor
    ) as tabela:
        linha = tabela.row()
        for titulo in ("Descrição", "Qtd.", "Valor unit.", "Subtotal"):
            linha.cell(_limpar(titulo))
        for item in itens:
            subtotal = item["quantidade"] * item["preco_unitario"]
            linha = tabela.row()
            linha.cell(_limpar(item["nome"]))
            linha.cell(str(item["quantidade"]))
            linha.cell(_limpar(formatar_reais(item["preco_unitario"])))
            linha.cell(_limpar(formatar_reais(subtotal)))
    pdf.ln(5)


def _linha_de_total(pdf, rotulo, valor, destaque=False):
    """Uma linha do quadro de totais: rótulo e valor alinhados à direita."""
    largura_rotulo, largura_valor = 50, 40
    pdf.set_x(pdf.w - MARGEM_PAGINA - largura_rotulo - largura_valor)
    if destaque:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(*pdf.cores["principal"])
        altura = 11
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*TEXTO)
        pdf.set_fill_color(*pdf.cores["gelo"])
        altura = 7.5
    pdf.cell(largura_rotulo, altura, _limpar("  " + rotulo), fill=True)
    pdf.cell(largura_valor, altura, _limpar(valor + "  "), align="R", fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _totais(pdf, dados, resumo):
    """Quadro à direita: itens, mão de obra, desconto (se houver) e total."""
    mao_de_obra = resumo.get("mao_de_obra", 0)
    tem_desconto = resumo["desconto"] > 0
    # Evita que o quadro fique dividido entre duas páginas.
    if pdf.will_page_break(45):
        pdf.add_page()

    if mao_de_obra > 0:
        _linha_de_total(pdf, "Itens", formatar_reais(resumo.get("itens", resumo["subtotal"])))
        _linha_de_total(pdf, "Mão de obra", formatar_reais(mao_de_obra))
    if tem_desconto:
        _linha_de_total(pdf, "Subtotal", formatar_reais(resumo["subtotal"]))
        rotulo = "Desconto"
        if dados["desconto_tipo"] == "percentual":
            percentual = f"{dados['desconto_valor']:g}".replace(".", ",")
            rotulo = f"Desconto ({percentual}%)"
        _linha_de_total(pdf, rotulo, "- " + formatar_reais(resumo["desconto"]))
    _linha_de_total(pdf, "TOTAL", formatar_reais(resumo["total"]), destaque=True)
    pdf.ln(7)


def _secao_de_texto(pdf, titulo, texto):
    """Seção opcional de texto livre (pagamento, observações)."""
    if not texto:
        return
    _titulo_de_secao(pdf, titulo)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXTO)
    # multi_cell quebra o texto em várias linhas automaticamente.
    pdf.multi_cell(0, 5.5, _limpar(texto), align="L",
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
