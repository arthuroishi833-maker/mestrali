"""Cor do orçamento: validação, contraste e o PDF saindo com a cor escolhida."""

import re
import zlib

from core.cores import CONTRASTE_MINIMO, CORES_PRONTAS, contraste_com_branco, paleta, validar_cor
from core.pdf import gerar_pdf
from tests.test_pdf import DADOS, DATA, ITENS, PERFIL, RESUMO


def test_cores_prontas_sao_legiveis_com_texto_branco():
    for nome, cor in CORES_PRONTAS.items():
        assert contraste_com_branco(cor) >= CONTRASTE_MINIMO, nome
        assert validar_cor(cor) == (cor.upper(), "")


def test_cor_clara_ou_invalida_e_recusada():
    assert validar_cor("#FFE08A")[0] is None          # amarelo claro: texto branco ilegível
    assert "clara demais" in validar_cor("#9ED8FF")[1]
    for ruim in ("", "azul", "#12345", "#GGGGGG", "javascript:alert(1)", None):
        assert validar_cor(ruim)[0] is None, ruim
    assert validar_cor("#b42318") == ("#B42318", "")


def test_paleta_padrao_e_tons_claros():
    assert paleta("")["principal"] == (10, 88, 202)
    assert paleta("#FFFFFF")["principal"] == (10, 88, 202)   # inválida: volta ao azul
    tons = paleta("#B42318")
    assert tons["principal"] == (180, 35, 24)
    assert all(v > 230 for v in tons["gelo"]) and all(v > 240 for v in tons["listra"])


def _conteudo_do_pdf(pdf_bytes):
    """Junta o conteúdo descomprimido das páginas, onde ficam os comandos de cor."""
    partes = []
    for bloco in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        try:
            partes.append(zlib.decompress(bloco).decode("latin-1"))
        except zlib.error:
            pass
    return "\n".join(partes)


def test_pdf_sai_com_a_cor_escolhida():
    vermelho = _conteudo_do_pdf(gerar_pdf({**PERFIL, "cor_orcamento": "#B42318"}, DADOS, ITENS, RESUMO, DATA))
    assert "0.7059 0.1373 0.0941" in vermelho          # 180, 35, 24 em escala de 0 a 1
    assert "0.0392 0.3451 0.7922" not in vermelho      # o azul padrão não aparece
    padrao = _conteudo_do_pdf(gerar_pdf(PERFIL, DADOS, ITENS, RESUMO, DATA))
    assert "0.0392 0.3451 0.7922" in padrao
