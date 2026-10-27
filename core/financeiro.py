"""Contas da tela Financeiro: períodos (dia, mês, ano) e totais de custo, ganho e lucro.

Entram os orçamentos FECHADOS e os PAGOS (veja core/situacao.py), pela data do fechamento.
  ganho = total cobrado do cliente (com mão de obra e desconto)
  custo = soma do custo das peças e serviços do orçamento
  lucro = ganho - custo  (negativo = prejuízo)

As contas são as mesmas da tela de revisão (core/calculos.py), para os números
baterem com o que o técnico viu ao fazer o orçamento.
"""

from datetime import date, datetime, time, timedelta, timezone

from core.calculos import arredondar_centavos, calcular_resumo
from core.formato import FUSO_BRASIL

TIPOS = ("Dia", "Mês", "Ano")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
# Como o período aparece nas frases: "Lucro do mês", "Nenhum orçamento fechado neste ano".
NOME = {"Dia": "dia", "Mês": "mês", "Ano": "ano"}


def periodo(tipo, deslocamento, hoje):
    """Começo (incluído) e fim (não incluído) do período, e o nome dele para a tela.

    deslocamento 0 = hoje / este mês / este ano; -1 = o anterior; e assim por diante.
    """
    if tipo == "Dia":
        inicio = hoje + timedelta(days=deslocamento)
        fim = inicio + timedelta(days=1)
        if deslocamento == 0:
            titulo = f"Hoje ({inicio.strftime('%d/%m')})"
        elif deslocamento == -1:
            titulo = f"Ontem ({inicio.strftime('%d/%m')})"
        else:
            titulo = inicio.strftime("%d/%m/%Y")
    elif tipo == "Mês":
        indice = hoje.year * 12 + (hoje.month - 1) + deslocamento
        inicio = date(indice // 12, indice % 12 + 1, 1)
        fim = date((indice + 1) // 12, (indice + 1) % 12 + 1, 1)
        titulo = f"{MESES[inicio.month - 1].capitalize()} de {inicio.year}"
    elif tipo == "Ano":
        inicio = date(hoje.year + deslocamento, 1, 1)
        fim = date(inicio.year + 1, 1, 1)
        titulo = str(inicio.year)
    else:
        raise ValueError(tipo)
    return inicio, fim, titulo


def limites_utc(inicio, fim):
    """O período em dias do Brasil vira horários em UTC, como o banco guarda."""
    def converter(dia):
        return datetime.combine(dia, time(0), FUSO_BRASIL).astimezone(timezone.utc).isoformat()
    return converter(inicio), converter(fim)


def totais(orcamentos):
    """Soma custo, ganho e lucro dos orçamentos fechados e pagos do período.

    "a_receber" e "lucro_a_receber" vêm dos orçamentos fechados ainda não pagos;
    "ganho_pago" e "lucro_pago", dos pagos.
    """
    custo = ganho = a_receber = lucro_a_receber = 0.0
    for orcamento in orcamentos:
        resumo = calcular_resumo(
            orcamento.get("itens") or [], orcamento.get("desconto_tipo") or "valor",
            orcamento.get("desconto_valor") or 0, orcamento.get("mao_de_obra") or 0,
        )
        custo += resumo["custo_total"]
        ganho += resumo["total"]
        if orcamento.get("situacao") == "fechado":          # aceito, mas ainda não pago
            a_receber += resumo["total"]
            lucro_a_receber += resumo["total"] - resumo["custo_total"]
    custo, ganho = arredondar_centavos(custo), arredondar_centavos(ganho)
    lucro = arredondar_centavos(ganho - custo)
    a_receber, lucro_a_receber = arredondar_centavos(a_receber), arredondar_centavos(lucro_a_receber)
    return {"custo": custo, "ganho": ganho, "lucro": lucro, "quantidade": len(orcamentos),
            "a_receber": a_receber, "ganho_pago": arredondar_centavos(ganho - a_receber),
            "lucro_a_receber": lucro_a_receber, "lucro_pago": arredondar_centavos(lucro - lucro_a_receber)}
