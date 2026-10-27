"""Tratamento do logo enviado pelo técnico.

O logo é guardado como texto (base64) na tabela perfis. Antes de guardar,
a imagem é reduzida e regravada como WebP (formato moderno, bem mais leve
que PNG com a mesma qualidade): isso limita o tamanho e descarta qualquer
coisa que não seja realmente uma imagem.
"""

import base64
import io

from PIL import Image, ImageOps  # Pillow: já vem instalado junto com o fpdf2

LADO_MAXIMO = 800  # pixels: nítido na tela e no PDF impresso
MAX_PIXELS_ENTRADA = 25_000_000  # recusa imagens gigantes antes de abrir
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # arquivo enviado: até 5 MB
MAX_BASE64 = 400_000  # mesmo limite da coluna logo_base64 no banco
# Únicos formatos que o leitor de imagens pode tentar abrir. "MPO" é como
# alguns celulares gravam um JPG comum. Sem esta lista, o arquivo enviado
# seria entregue a dezenas de leitores de formatos antigos (GIF, TIFF, ICO...),
# cada um deles uma porta a mais para um arquivo malicioso.
FORMATOS_ACEITOS = ("PNG", "JPEG", "MPO")
# Ao LER o logo do banco: só os formatos em que o sistema grava (WebP hoje;
# PNG e JPEG em versões antigas) e um tamanho pequeno. O banco aceita o que a
# conta gravar, inclusive por fora do aplicativo; sem esta conferência, um
# arquivo montado de propósito seria aberto no servidor ao gerar o PDF.
FORMATOS_GUARDADOS = ("WEBP", "PNG", "JPEG")
LADO_MAXIMO_GUARDADO = 2000  # pixels; o aplicativo grava no máximo LADO_MAXIMO


def preparar_logo(dados):
    """Recebe os bytes do arquivo enviado. Devolve (logo_base64, erro)."""
    if len(dados) > MAX_UPLOAD_BYTES:
        return None, "Logo: arquivo muito grande (máximo 5 MB)."
    try:
        imagem = Image.open(io.BytesIO(dados), formats=FORMATOS_ACEITOS)
        largura, altura = imagem.size  # lido do cabeçalho, sem abrir a imagem toda
        if largura * altura > MAX_PIXELS_ENTRADA:
            return None, "Logo: imagem grande demais. Use uma de até 5000 x 5000 pixels."
        imagem.load()
    except Exception:
        return None, "Logo: o arquivo não é uma imagem PNG ou JPG válida."

    # Foto de celular costuma vir "deitada", com uma anotação dizendo como girar.
    # Aplica o giro aqui, porque essa anotação se perde ao regravar a imagem.
    imagem = ImageOps.exif_transpose(imagem)
    imagem = imagem.convert("RGBA")
    imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO))  # reduz mantendo a proporção

    saida = io.BytesIO()
    imagem.save(saida, format="WEBP", quality=90, method=6)
    texto = base64.b64encode(saida.getvalue()).decode("ascii")
    if len(texto) > MAX_BASE64:
        return None, "Logo: imagem muito detalhada. Tente uma mais simples."
    return texto, ""


def logo_para_bytes(logo_base64):
    """Converte o texto guardado no banco de volta para os bytes da imagem.

    Levanta ValueError se o conteúdo não for uma imagem pequena em um dos
    formatos esperados. Quem chama trata isso como "sem logo".
    """
    if not isinstance(logo_base64, str) or not 0 < len(logo_base64) <= MAX_BASE64:
        raise ValueError("logo ausente ou grande demais")
    try:
        dados = base64.b64decode(logo_base64, validate=True)
        # Só o cabeçalho é lido aqui (formato e medidas); a imagem não é aberta inteira.
        largura, altura = Image.open(io.BytesIO(dados), formats=FORMATOS_GUARDADOS).size
    except Exception as erro:
        raise ValueError("logo ilegível") from erro
    if not (0 < largura <= LADO_MAXIMO_GUARDADO and 0 < altura <= LADO_MAXIMO_GUARDADO):
        raise ValueError("logo com medidas fora do esperado")
    return dados
