"""Validação das entradas do usuário.

Funções puras (não dependem do Streamlit nem do banco), fáceis de testar.
Padrão usado: cada função devolve (valor_limpo, erro).
  - erro == ""  -> entrada válida, use valor_limpo
  - erro != ""  -> mostre o erro para o usuário
"""

import re
import unicodedata

from core.calculos import arredondar_centavos

# Limites de tamanho. São os mesmos do banco (sql/schema.sql).
MAX_NOME = 80
MAX_OBSERVACOES = 500
MAX_CONDICOES = 200
MAX_MENSAGEM = 700               # mensagem do WhatsApp escrita pelo técnico (modelo do Perfil)
MAX_MENSAGEM_ENVIO = 1000        # a mesma mensagem já com nome, equipamento e total no lugar dos marcadores
MIN_SENHA = 8
MAX_SENHA = 72
ESPECIAIS_DA_SENHA = "@#$%&"     # caracteres especiais aceitos como requisito
TAMANHO_DA_SEQUENCIA = 4         # "1234", "abcd", "4321"... a partir deste tamanho são recusadas
MIN_TELEFONE = 10                # DDD + 8 dígitos (fixo)
MAX_TELEFONE = 11                # DDD + 9 dígitos (celular)
MIN_VALIDADE = 1
MAX_VALIDADE = 90
MAX_DINHEIRO = 999999.99        # teto de cada valor digitado (custo, preço, mão de obra)
MAX_TOTAL = 99_999_999.99       # teto do total de um orçamento: o que cabe na coluna do banco
TIPOS_VALIDOS = ("mao_de_obra", "peca")
MAX_QUANTIDADE = 999
MAX_ITENS_ORCAMENTO = 50

# E-mail: antes do "@", os caracteres que o padrão permite sem aspas; depois,
# só o que cabe num nome de domínio (letras, números, hífen e pontos). Um
# "domínio" com colchetes, espaços ou símbolos nem chega a ser consultado.
_EMAIL_RE = re.compile(
    r"^[a-z0-9!#$%&'*+/=?^_`{|}~.\-]+"
    r"@[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)+$"
)


def _sem_controles(texto, multilinha):
    """Tira caracteres invisíveis de controle (inclusive o "nulo", que o banco recusa).

    Em campo de uma linha, quebra de linha e tabulação viram espaço.
    Em campo de várias linhas (observações, mensagem), a quebra de linha fica.
    """
    texto = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    if not multilinha:
        texto = texto.replace("\n", " ")
    return "".join(
        c for c in texto
        if c == "\n" or unicodedata.category(c) not in ("Cc", "Zl", "Zp")
    )


def validar_texto(texto, campo, maximo=MAX_NOME, obrigatorio=False, multilinha=False):
    """Tira espaços das pontas e caracteres de controle, e confere o tamanho."""
    limpo = _sem_controles(str(texto or ""), multilinha).strip()
    if obrigatorio and not limpo:
        return "", f"{campo}: preenchimento obrigatório."
    if len(limpo) > maximo:
        return "", f"{campo}: máximo de {maximo} caracteres."
    return limpo, ""


def validar_email(email):
    limpo = (email or "").strip().lower()
    if len(limpo) > 254 or not _EMAIL_RE.match(limpo):
        return "", "E-mail inválido."
    return limpo, ""


def tem_sequencia(texto, tamanho=TAMANHO_DA_SEQUENCIA):
    """True se há `tamanho` ou mais caracteres seguidos em ordem (1234, dcba...).

    Vale para números e para letras, crescente ou decrescente, sem
    diferenciar maiúsculas de minúsculas ("aBcD" conta como "abcd").
    """
    texto = (texto or "").lower()
    subindo = descendo = 1
    for anterior, atual in zip(texto, texto[1:]):
        ambos_numeros = anterior.isdigit() and atual.isdigit() and anterior.isascii() and atual.isascii()
        ambos_letras = "a" <= anterior <= "z" and "a" <= atual <= "z"
        passo = ord(atual) - ord(anterior) if (ambos_numeros or ambos_letras) else 0
        subindo = subindo + 1 if passo == 1 else 1
        descendo = descendo + 1 if passo == -1 else 1
        if subindo >= tamanho or descendo >= tamanho:
            return True
    return False


def requisitos_da_senha(senha):
    """Lista de (descrição, cumprido) com cada requisito de uma senha forte.

    É a ÚNICA definição das regras de senha no sistema. A barra de força da
    tela (telas/campo_senha.py) recebe estes mesmos parâmetros.
    """
    senha = senha or ""
    return [
        (f"{MIN_SENHA} caracteres", len(senha) >= MIN_SENHA),
        ("uma letra minúscula", any("a" <= c <= "z" for c in senha)),
        ("uma letra maiúscula", any("A" <= c <= "Z" for c in senha)),
        ("um número", any("0" <= c <= "9" for c in senha)),
        (f"um caractere especial ({' '.join(ESPECIAIS_DA_SENHA)})",
         any(c in ESPECIAIS_DA_SENHA for c in senha)),
    ]


def _juntar(partes):
    """["a", "b", "c"] -> "a, b e c" """
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " e " + partes[-1]


def validar_senha(senha):
    """Senha NOVA (cadastro, troca, redefinição): precisa ser forte.

    Não use para conferir a senha de quem está entrando: contas antigas
    podem ter senhas criadas antes destas regras.
    """
    senha = senha or ""
    if len(senha) > MAX_SENHA:
        return "", f"A senha pode ter no máximo {MAX_SENHA} caracteres."
    faltando = [descricao for descricao, cumprido in requisitos_da_senha(senha) if not cumprido]
    frases = []
    if faltando:
        frases.append(f"Sua senha deve ter pelo menos: {_juntar(faltando)}.")
    if tem_sequencia(senha):
        frases.append("Sua senha não pode conter sequências como 1234 ou abcd.")
    if frases:
        return "", " ".join(frases)
    return senha, ""


def validar_telefone(telefone, obrigatorio=False):
    """Telefone: só números, com DDD, de 10 a 11 dígitos.

    Não aceita máscara: parênteses, traço, espaço, ponto, "+" ou letras são
    recusados (em vez de removidos), para o que está na tela ser exatamente
    o que vai para o banco.
    """
    telefone = telefone or ""
    if not telefone:
        if obrigatorio:
            return "", "Telefone: preenchimento obrigatório."
        return "", ""
    if not all("0" <= c <= "9" for c in telefone):
        return "", "O telefone deve conter apenas números."
    if len(telefone) > MAX_TELEFONE:
        return "", f"O telefone deve ter no máximo {MAX_TELEFONE} números, incluindo o DDD."
    if len(telefone) < MIN_TELEFONE:
        return "", "O telefone deve ter o DDD e o número (10 ou 11 números)."
    return telefone, ""


def formatar_telefone(digitos):
    """27999990000 -> (27) 99999-0000. Usado para mostrar na tela e no PDF."""
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return digitos


def validar_validade(dias):
    """Validade do orçamento em dias (número inteiro)."""
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        return 0, "Validade: informe um número de dias."
    if not MIN_VALIDADE <= dias <= MAX_VALIDADE:
        return 0, f"Validade: entre {MIN_VALIDADE} e {MAX_VALIDADE} dias."
    return dias, ""


def validar_dinheiro(valor, campo):
    """Valor em reais: número, não negativo, com 2 casas decimais."""
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return 0.0, f"{campo}: informe um valor em reais."
    if valor != valor or valor < 0:  # "valor != valor" detecta NaN
        return 0.0, f"{campo}: o valor não pode ser negativo."
    if valor > MAX_DINHEIRO:         # também barra "infinito"
        return 0.0, f"{campo}: valor acima do limite permitido."
    return arredondar_centavos(valor), ""


def validar_tipo(tipo):
    if tipo not in TIPOS_VALIDOS:
        return "", "Tipo inválido."
    return tipo, ""


def validar_quantidade(quantidade):
    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError):
        return 0, "Quantidade: informe um número inteiro."
    if not 1 <= quantidade <= MAX_QUANTIDADE:
        return 0, f"Quantidade: entre 1 e {MAX_QUANTIDADE}."
    return quantidade, ""


def validar_desconto(tipo, valor, subtotal):
    """Desconto em R$ (até o subtotal) ou em % (até 100)."""
    if tipo not in ("valor", "percentual"):
        return 0.0, "Tipo de desconto inválido."
    valor, erro = validar_dinheiro(valor, "Desconto")
    if erro:
        return 0.0, erro
    if tipo == "percentual" and valor > 100:
        return 0.0, "Desconto: o máximo é 100%."
    if tipo == "valor" and valor > subtotal:
        return 0.0, "Desconto: não pode ser maior que o subtotal."
    return valor, ""


def validar_codigo(codigo):
    """Código numérico enviado por e-mail para redefinir a senha."""
    limpo = re.sub(r"\s", "", codigo or "")
    if not re.fullmatch(r"\d{6,10}", limpo):
        return "", "Código inválido: digite os números que chegaram no e-mail."
    return limpo, ""


def validar_total(total):
    """O total do orçamento precisa caber na coluna do banco (numeric(10,2)).

    Só é atingido com quantidades e valores absurdos, mas sem esta conferência
    o banco recusava a gravação e a tela mostrava apenas "não foi possível salvar".
    """
    if total > MAX_TOTAL:
        return ("O total passou do limite do sistema (R$ 99.999.999,99). "
                "Confira as quantidades e os valores.")
    return ""
