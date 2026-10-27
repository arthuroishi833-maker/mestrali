"""Monta o link do WhatsApp (wa.me) com a mensagem pronta para o cliente.

O link só abre a conversa com o texto preenchido. Ele NÃO anexa arquivos:
o técnico baixa o PDF e anexa na conversa.

De onde vem o texto, em ordem:
  1. se o técnico gravou uma mensagem própria no Perfil, ela é usada, com os
     marcadores ({cliente}, {total}...) trocados pelos dados do orçamento;
  2. senão, a mensagem padrão do sistema;
  3. na hora de enviar, o técnico ainda pode mexer no texto daquele envio.
"""

from datetime import timedelta
from urllib.parse import quote

from core.formato import formatar_reais

CODIGO_BRASIL = "55"

# Marcadores que o técnico pode escrever na mensagem dele, e o que cada um vira.
# De propósito NÃO existe marcador de custo, lucro ou margem.
MARCADORES = {
    "{cliente}": "primeiro nome do cliente",
    "{empresa}": "nome da sua empresa (o do Perfil)",
    "{equipamento}": "equipamento do orçamento",
    "{total}": "valor total",
    "{validade}": "data até quando o orçamento vale",
}

# Ponto de partida oferecido no Perfil para quem quer escrever a própria mensagem.
MODELO_SUGERIDO = (
    "Olá, {cliente}!\n"
    "Aqui é da {empresa}.\n"
    "Segue o orçamento para {equipamento}.\n"
    "\n"
    "Total: {total}\n"
    "Válido até {validade}\n"
    "\n"
    "O PDF com todos os detalhes vai em anexo. Qualquer dúvida, é só chamar!"
)


def _primeiro_nome(dados):
    return (dados["cliente_nome"].split() or ["tudo bem"])[0]


def aplicar_modelo(modelo, perfil, dados, resumo, data):
    """Troca os marcadores do texto do técnico pelos dados do orçamento.

    É uma troca simples de texto (replace), não str.format: chaves que não
    são marcadores ficam como foram escritas e nada digitado vira código.
    """
    vence = data + timedelta(days=dados["validade_dias"])
    valores = {
        "{cliente}": _primeiro_nome(dados),
        "{empresa}": perfil.get("nome_empresa") or "",
        "{equipamento}": dados.get("equipamento") or "o serviço solicitado",
        "{total}": formatar_reais(resumo["total"]),
        "{validade}": vence.strftime("%d/%m/%Y"),
    }
    texto = modelo
    for marcador, valor in valores.items():
        texto = texto.replace(marcador, valor)
    return texto.strip()


def montar_mensagem(perfil, dados, resumo, data):
    """Texto enviado ao cliente. Nunca inclui custo, lucro nem margem."""
    modelo = (perfil.get("mensagem_whatsapp") or "").strip()
    if modelo:
        return aplicar_modelo(modelo, perfil, dados, resumo, data)

    primeiro_nome = _primeiro_nome(dados)
    vence = data + timedelta(days=dados["validade_dias"])

    linhas = [f"Olá, {primeiro_nome}!"]
    if perfil.get("nome_empresa"):
        linhas.append(f"Aqui é da {perfil['nome_empresa']}.")
    assunto = "Segue o orçamento"
    if dados.get("equipamento"):
        assunto += f" para {dados['equipamento']}"
    linhas.append(assunto + ".")
    linhas.append("")
    linhas.append(f"Total: {formatar_reais(resumo['total'])}")
    linhas.append(f"Válido até {vence.strftime('%d/%m/%Y')}")
    linhas.append("")
    linhas.append("O PDF com todos os detalhes vai em anexo. Qualquer dúvida, é só chamar!")
    return "\n".join(linhas)


def inicio_do_link(telefone):
    """Devolve o endereço wa.me até "?text=", sem a mensagem.

    telefone: só dígitos, com DDD (ex.: "27999990000"), ou "" para o técnico
              escolher o contato dentro do WhatsApp.
    """
    digitos = "".join(c for c in (telefone or "") if c.isdigit())
    if digitos:
        return f"https://wa.me/{CODIGO_BRASIL}{digitos}?text="
    return "https://wa.me/?text="


def montar_link(telefone, mensagem):
    """Devolve o endereço wa.me completo.

    A mensagem é codificada para URL (quote), então nenhum caractere
    digitado consegue alterar o endereço.
    """
    return inicio_do_link(telefone) + quote(mensagem, safe="")
