"""Testes de core/pdf.py. O mais importante: custo e margem NUNCA aparecem.

O pypdf lê o texto de dentro do PDF gerado, para conferirmos o conteúdo.
"""

import io
from datetime import date

from PIL import Image
from pypdf import PdfReader

from core.calculos import calcular_resumo
from core.imagem import preparar_logo
from core.pdf import gerar_pdf, nome_arquivo

PERFIL = {
    "nome_empresa": "Clima Frio Refrigeração",
    "telefone": "27999990000",
    "logo_base64": None,
    "validade_dias": 7,
}
DADOS = {
    "cliente_nome": "Maria Conceição",
    "cliente_telefone": "27988887777",
    "equipamento": "Split 12.000 BTUs",
    "desconto_tipo": "percentual",
    "desconto_valor": 10.0,
    "observacoes": "Garantia de 90 dias para o serviço.",
    "condicoes_pagamento": "Pix ou cartão em até 3x.",
    "numero": 12,
    "validade_dias": 7,
}
# Custos com valores "estranhos" de propósito: fáceis de procurar no PDF.
ITENS = [
    {"nome": "Capacitor", "tipo": "peca", "quantidade": 2,
     "custo_unitario": 31.47, "preco_unitario": 100.0},
    {"nome": "Limpeza / higienização", "tipo": "mao_de_obra", "quantidade": 1,
     "custo_unitario": 23.59, "preco_unitario": 180.0},
]
RESUMO = calcular_resumo(ITENS, "percentual", 10.0)
DATA = date(2026, 10, 9)


def _texto(pdf_bytes):
    leitor = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(pagina.extract_text() for pagina in leitor.pages)


def test_pdf_tem_os_dados_do_cliente_e_os_valores():
    texto = _texto(gerar_pdf(PERFIL, DADOS, ITENS, RESUMO, DATA))
    assert "Clima Frio Refrigeração" in texto
    assert "(27) 99999-0000" in texto
    assert "Maria Conceição" in texto
    assert "(27) 98888-7777" in texto
    assert "Split 12.000 BTUs" in texto
    assert "09/10/2026" in texto          # data do orçamento
    assert "16/10/2026" in texto          # validade: 7 dias depois
    assert "Capacitor" in texto
    assert "Limpeza / higienização" in texto
    assert "R$ 100,00" in texto           # preço unitário
    assert "R$ 200,00" in texto           # 2 x 100
    assert "R$ 380,00" in texto           # subtotal
    assert "R$ 38,00" in texto            # desconto de 10%
    assert "R$ 342,00" in texto           # total
    assert "Garantia de 90 dias" in texto
    assert "Nº 0012" in texto             # número do orçamento
    assert "Pix ou cartão em até 3x." in texto
    assert "Página 1 de 1" in texto


def test_pdf_nunca_mostra_custo_lucro_nem_margem():
    texto = _texto(gerar_pdf(PERFIL, DADOS, ITENS, RESUMO, DATA)).lower()
    for proibido in ["custo", "lucro", "margem"]:
        assert proibido not in texto
    # valores de custo unitário, custo total (86,53), lucro (255,47) e margem (74,7)
    for valor in ["31,47", "23,59", "62,94", "86,53", "255,47", "74,7"]:
        assert valor not in texto


def test_pdf_sem_desconto_nao_mostra_linha_de_desconto():
    dados = dict(DADOS, desconto_valor=0.0)
    resumo = calcular_resumo(ITENS, "percentual", 0.0)
    texto = _texto(gerar_pdf(PERFIL, dados, ITENS, resumo, DATA))
    assert "Desconto" not in texto and "Subtotal" not in texto.replace("Subtotal\n", "")
    assert "R$ 380,00" in texto


def test_pdf_com_campos_opcionais_vazios():
    dados = dict(DADOS, cliente_telefone="", equipamento="", observacoes="",
                 condicoes_pagamento="", numero=None)
    perfil = dict(PERFIL, nome_empresa="", telefone="")
    pdf = gerar_pdf(perfil, dados, ITENS, RESUMO, DATA)
    assert pdf[:5] == b"%PDF-"
    texto = _texto(pdf).upper()
    assert "OBSERVAÇÕES" not in texto
    assert "CONDIÇÕES DE PAGAMENTO" not in texto
    assert "Nº" not in texto


def test_pdf_com_caracteres_fora_do_padrao_nao_quebra():
    dados = dict(DADOS, cliente_nome="João 😀 “Zé”", observacoes="Preço – válido… ✔ 日本")
    pdf = gerar_pdf(PERFIL, dados, ITENS, RESUMO, DATA)
    assert "João" in _texto(pdf)


def test_pdf_com_logo():
    saida = io.BytesIO()
    Image.new("RGB", (300, 100), "navy").save(saida, format="PNG")
    logo, erro = preparar_logo(saida.getvalue())
    assert erro == ""
    pdf = gerar_pdf(dict(PERFIL, logo_base64=logo), DADOS, ITENS, RESUMO, DATA)
    assert len(PdfReader(io.BytesIO(pdf)).pages[0].images) == 1


def test_pdf_com_muitos_itens_passa_para_outra_pagina():
    itens = [dict(ITENS[0], nome=f"Item {n}") for n in range(50)]
    resumo = calcular_resumo(itens, "valor", 0)
    pdf = gerar_pdf(PERFIL, DADOS, itens, resumo, DATA)
    assert len(PdfReader(io.BytesIO(pdf)).pages) >= 2


def test_nome_do_arquivo():
    assert nome_arquivo("Maria Conceição", DATA) == "orcamento-maria-conceicao-2026-10-09.pdf"
    assert nome_arquivo("  ../../x  ", DATA) == "orcamento-x-2026-10-09.pdf"
    assert nome_arquivo("😀", DATA) == "orcamento-cliente-2026-10-09.pdf"


def test_pdf_mostra_mao_de_obra_quando_informada():
    resumo = calcular_resumo(ITENS, "valor", 0, mao_de_obra=150)
    texto = _texto(gerar_pdf(PERFIL, dict(DADOS, desconto_valor=0.0, desconto_tipo="valor"),
                             ITENS, resumo, DATA))
    assert "Mão de obra" in texto
    assert "R$ 150,00" in texto
    assert "R$ 530,00" in texto   # 380 de itens + 150


# ------------------------------------------- nomes compridos não saem da folha
NOME_LONGO = "Maria Aparecida da Conceição dos Santos Oliveira Albuquerque e Silva Pereira Lima"   # 80
SEM_ESPACOS = "M" * 80
EMPRESA_LONGA = "Refrigeração e Climatização Vila Velha e Grande Vitória Serviços Técnicos Ltda"

MARGEM_PT = 15 / 25.4 * 72           # margem de 15 mm, em pontos
PAGINA_PT = 210 / 25.4 * 72          # largura da folha A4, em pontos


def _trechos(pdf_bytes, pagina=0):
    """Lista de (texto, x, y, tamanho_da_fonte) de cada trecho escrito na página."""
    achados = []

    def visitante(texto, _cm, tm, _fonte, tamanho):
        if texto.strip():
            achados.append((texto.strip(), tm[4], tm[5], tamanho))

    PdfReader(io.BytesIO(pdf_bytes)).pages[pagina].extract_text(visitor_text=visitante)
    return achados


def _logo_largo():
    saida = io.BytesIO()
    Image.new("RGB", (600, 200), "navy").save(saida, format="PNG")
    return preparar_logo(saida.getvalue())[0]


def test_nome_longo_do_cliente_quebra_em_linhas_e_fica_inteiro():
    for nome in (NOME_LONGO, SEM_ESPACOS):
        pdf = gerar_pdf(PERFIL, dict(DADOS, cliente_nome=nome), ITENS, RESUMO, DATA)
        texto = _texto(pdf)
        assert "".join(nome.split()) in "".join(texto.split()), nome     # nada foi cortado
        titulo = [t for t in _trechos(pdf) if abs(t[3] - 17) < 0.1]       # trechos em corpo 17
        assert len({round(y) for _, _, y, _ in titulo}) >= 2             # ocupou 2+ linhas
        assert all(x >= MARGEM_PT - 1 for _, x, _, _ in titulo)          # nenhuma começa fora


def test_nome_longo_da_empresa_nao_passa_por_cima_do_logo():
    perfil = dict(PERFIL, nome_empresa=EMPRESA_LONGA, logo_base64=_logo_largo())
    pdf = gerar_pdf(perfil, DADOS, ITENS, RESUMO, DATA)
    assert "".join(EMPRESA_LONGA.split()) in "".join(_texto(pdf).split())
    # O logo ocupa até 60 mm a partir da margem; o nome (corpo 16) tem de começar depois.
    fim_do_logo_pt = (15 + 60) / 25.4 * 72
    nome = [t for t in _trechos(pdf) if abs(t[3] - 16) < 0.1]
    assert nome and all(x >= fim_do_logo_pt for _, x, _, _ in nome)
    assert len({round(y) for _, _, y, _ in nome}) >= 2                   # quebrou em linhas


def test_nomes_curtos_continuam_em_uma_linha_so():
    pdf = gerar_pdf(PERFIL, DADOS, ITENS, RESUMO, DATA)
    titulo = [t for t in _trechos(pdf) if abs(t[3] - 17) < 0.1]
    assert len({round(y) for _, _, y, _ in titulo}) == 1


def test_rodape_com_nome_enorme_nao_invade_o_numero_da_pagina():
    perfil = dict(PERFIL, nome_empresa="W" * 80)
    pdf = gerar_pdf(perfil, DADOS, ITENS, RESUMO, DATA)
    assert "Página 1 de 1" in _texto(pdf)
    rodape = [t for t in _trechos(pdf) if abs(t[3] - 8) < 0.1 and t[0].startswith("W")]
    assert rodape and rodape[0][0].endswith("...")                        # foi encurtado
    assert len(rodape[0][0]) < 80


def test_tudo_no_limite_de_tamanho_ainda_gera_um_pdf():
    dados = dict(DADOS, cliente_nome=SEM_ESPACOS, equipamento="E" * 80,
                 observacoes="O" * 500, condicoes_pagamento="C" * 200)
    itens = [dict(ITENS[0], nome="I" * 80)]
    perfil = dict(PERFIL, nome_empresa="W" * 80, logo_base64=_logo_largo())
    pdf = gerar_pdf(perfil, dados, itens, calcular_resumo(itens, "valor", 0), DATA)
    assert pdf[:5] == b"%PDF-"
    assert "E" * 40 in "".join(_texto(pdf).split())


def test_logo_estranho_no_banco_nao_e_aberto_e_o_pdf_sai_sem_ele():
    import base64
    from unittest.mock import patch

    svg = base64.b64encode(b"<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/>").decode()
    perfil = dict(PERFIL, logo_base64=svg)
    with patch("fpdf.FPDF.image") as desenhar:
        pdf = gerar_pdf(perfil, DADOS, ITENS, RESUMO, DATA)
    assert pdf[:4] == b"%PDF"
    desenhar.assert_not_called()          # o conteúdo nem chegou ao leitor de imagens do PDF
