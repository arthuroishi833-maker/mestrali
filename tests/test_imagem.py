"""Testes de core/imagem.py. Rodar com: pytest"""

import io

from PIL import Image

from core.imagem import LADO_MAXIMO, logo_para_bytes, preparar_logo


def _png(largura, altura):
    saida = io.BytesIO()
    Image.new("RGB", (largura, altura), "blue").save(saida, format="PNG")
    return saida.getvalue()


def test_imagem_grande_e_reduzida():
    texto, erro = preparar_logo(_png(2400, 1200))
    assert erro == ""
    imagem = Image.open(io.BytesIO(logo_para_bytes(texto)))
    assert imagem.size == (LADO_MAXIMO, LADO_MAXIMO // 2)
    assert imagem.format == "WEBP"


def test_logo_fica_leve():
    texto, _ = preparar_logo(_png(2400, 1200))
    assert len(texto) < 50_000  # bem abaixo do limite do banco (400 mil)


def test_imagem_gigante_e_recusada_sem_abrir():
    texto, erro = preparar_logo(_png(6000, 5000))
    assert texto is None and "grande demais" in erro


def test_arquivo_que_nao_e_imagem():
    texto, erro = preparar_logo(b"isto nao e uma imagem")
    assert texto is None and "não é uma imagem" in erro


def test_arquivo_grande_demais():
    texto, erro = preparar_logo(b"0" * (5 * 1024 * 1024 + 1))
    assert texto is None and "muito grande" in erro


def _imagem(formato, tamanho=(60, 40)):
    saida = io.BytesIO()
    Image.new("RGB", tamanho, "red").save(saida, format=formato)
    return saida.getvalue()


def test_so_png_e_jpg_sao_abertos():
    for formato in ["PNG", "JPEG"]:
        texto, erro = preparar_logo(_imagem(formato))
        assert texto and erro == "", formato
    for formato in ["GIF", "BMP", "TIFF", "ICO", "PPM", "WEBP"]:
        texto, erro = preparar_logo(_imagem(formato))
        assert texto is None and "não é uma imagem PNG ou JPG" in erro, formato


def test_arquivo_de_outro_formato_renomeado_para_png_e_recusado():
    """A extensão do arquivo não importa: vale o conteúdo."""
    assert preparar_logo(_imagem("GIF"))[0] is None


def _jpg_com_orientacao(orientacao, tamanho=(400, 200)):
    imagem = Image.new("RGB", tamanho, "blue")
    exif = imagem.getexif()
    exif[0x0112] = orientacao          # campo "Orientation" da foto
    saida = io.BytesIO()
    imagem.save(saida, format="JPEG", exif=exif)
    return saida.getvalue()


def test_foto_de_celular_marcada_como_em_pe_nao_fica_deitada():
    # Orientação 6 = "gire 90 graus": a foto 400x200 deve virar 200x400.
    texto, erro = preparar_logo(_jpg_com_orientacao(6))
    assert erro == ""
    assert Image.open(io.BytesIO(logo_para_bytes(texto))).size == (200, 400)


def test_foto_sem_giro_fica_como_estava():
    texto, _ = preparar_logo(_jpg_com_orientacao(1))
    assert Image.open(io.BytesIO(logo_para_bytes(texto))).size == (400, 200)
    texto, _ = preparar_logo(_png(400, 200))     # PNG não tem essa anotação
    assert Image.open(io.BytesIO(logo_para_bytes(texto))).size == (400, 200)


# ------------------------------------------- o logo é conferido também ao LER
import base64

import pytest


def _b64(dados):
    return base64.b64encode(dados).decode("ascii")


def _imagem(formato, largura=40, altura=20):
    saida = io.BytesIO()
    Image.new("RGB", (largura, altura), "blue").save(saida, format=formato)
    return saida.getvalue()


def test_logo_gravado_pelo_app_e_aceito_na_leitura():
    texto, _ = preparar_logo(_png(300, 100))
    assert logo_para_bytes(texto)[:4] == b"RIFF"            # WebP
    assert logo_para_bytes(_b64(_imagem("PNG")))             # formatos de versões antigas
    assert logo_para_bytes(_b64(_imagem("JPEG")))


def test_conteudo_que_nao_e_logo_e_recusado_na_leitura():
    # O banco aceita o que a conta gravar (inclusive por fora do aplicativo).
    # Nada disto pode chegar ao gerador de PDF nem à tela.
    ruins = {
        "formato fora da lista (GIF)": _b64(_imagem("GIF")),
        "formato fora da lista (BMP)": _b64(_imagem("BMP")),
        "imagem com medidas enormes": _b64(_imagem("PNG", 2001, 4)),
        "SVG (texto que vira desenho)": _b64(b"<svg xmlns='http://www.w3.org/2000/svg'><script>1</script></svg>"),
        "texto qualquer": _b64(b"isto nao e uma imagem"),
        "base64 inválido": "@@@nao-e-base64@@@",
        "vazio": "",
        "tipo errado": None,
        "grande demais": "A" * 400_001,
    }
    for motivo, conteudo in ruins.items():
        with pytest.raises(ValueError):
            logo_para_bytes(conteudo)
            raise AssertionError(motivo)
