"""Cálculos do orçamento: subtotal, desconto, total, custo, lucro e margem.

Função pura: recebe os dados, devolve os números. Não acessa tela nem banco.

Por que Decimal? O tipo float guarda dinheiro com pequenos erros
(0.1 + 0.2 = 0.30000000000000004). Decimal faz a conta em base 10, como
uma calculadora. É o mesmo cuidado de não usar float para dinheiro em C.
"""

from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal("0.01")


def _dec(valor):
    """Converte para Decimal passando por texto, para não herdar o erro do float."""
    return Decimal(str(valor))


def _arredondar(valor):
    """Arredonda para 2 casas (meio centavo sobe) e devolve float."""
    return float(valor.quantize(CENTAVO, rounding=ROUND_HALF_UP))


def arredondar_centavos(valor):
    """10.994 -> 10.99; 2.675 -> 2.68. O ÚNICO arredondamento de dinheiro do sistema.

    Tudo que é valor em reais passa por aqui ao entrar (telas e validação) e
    de novo nos cálculos. Assim o total que aparece na revisão é sempre o
    mesmo que é gravado e que vai para o PDF. (O round() do Python faria
    2.675 virar 2.67, por causa do erro do float.)
    """
    return _arredondar(_dec(valor))


def _centavos(valor):
    """Como arredondar_centavos, mas devolve Decimal, para seguir nas contas."""
    return _dec(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def calcular_resumo(itens, desconto_tipo, desconto_valor, mao_de_obra=0):
    """Calcula os totais de um orçamento.

    itens: lista de dicts com quantidade, custo_unitario e preco_unitario.
    desconto_tipo: "valor" (em R$) ou "percentual" (em %).
    mao_de_obra: valor em R$ somado ao total, além dos itens. Entra inteiro
                 no lucro, pois é o trabalho do técnico (não tem custo de peça).

    Devolve um dict com:
      itens       soma dos preços dos itens
      mao_de_obra o valor de mão de obra informado
      subtotal    itens + mão de obra, antes do desconto
      desconto    desconto em R$ (nunca maior que o subtotal)
      total       o que o cliente paga
      custo_total o que o técnico gasta
      lucro       total - custo_total
      margem      lucro / total, em %  (0 quando o total é zero)
    """
    # Cada valor é levado a centavos ANTES da conta: um preço digitado como
    # 10,994 conta como 10,99 aqui, na tela e no banco.
    soma_itens = sum(
        (_centavos(i["preco_unitario"]) * i["quantidade"] for i in itens), Decimal("0")
    )
    mao_de_obra = max(_centavos(mao_de_obra), Decimal("0"))
    subtotal = soma_itens + mao_de_obra
    custo_total = sum(
        (_centavos(i["custo_unitario"]) * i["quantidade"] for i in itens), Decimal("0")
    )

    desconto_valor = max(_centavos(desconto_valor), Decimal("0"))
    if desconto_tipo == "percentual":
        desconto = subtotal * min(desconto_valor, Decimal("100")) / 100
    else:
        desconto = desconto_valor
    # Arredonda o desconto antes de subtrair, para o PDF fechar centavo a centavo.
    desconto = min(desconto, subtotal).quantize(CENTAVO, rounding=ROUND_HALF_UP)

    total = subtotal - desconto
    lucro = total - custo_total
    margem = lucro / total * 100 if total > 0 else Decimal("0")

    return {
        "itens": _arredondar(soma_itens),
        "mao_de_obra": _arredondar(mao_de_obra),
        "subtotal": _arredondar(subtotal),
        "desconto": _arredondar(desconto),
        "total": _arredondar(total),
        "custo_total": _arredondar(custo_total),
        "lucro": _arredondar(lucro),
        "margem": _arredondar(margem),
    }
