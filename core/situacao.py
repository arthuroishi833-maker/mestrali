"""Situação do orçamento: não fechado, fechado (a receber) ou pago.

  aberto   "Não fechado": o cliente ainda não respondeu.
  fechado  "Fechado": o cliente aceitou; o serviço ainda não foi pago.
  pago     "Pago": serviço feito e pago.

Fechado e pago contam no Financeiro, pela data em que o orçamento foi fechado
(fechado_em). Essa data é gravada na primeira vez que ele sai de "não fechado"
e é apagada se voltar para "não fechado".
"""

from datetime import datetime, timezone

SITUACOES = {"aberto": "Não fechado", "fechado": "Fechado", "pago": "Pago"}
CONTAM_NO_FINANCEIRO = ("fechado", "pago")
AJUDA = ("Não fechado: o cliente ainda não respondeu. Fechado: aceitou, mas ainda não pagou. "
         "Pago: serviço feito e pago. Fechado e pago entram no Financeiro.")


def data_de_fechamento(nova, fechado_em_atual):
    """A data de fechamento depois da troca de situação (texto em UTC, ou None)."""
    if nova not in SITUACOES:
        raise ValueError(nova)
    if nova == "aberto":
        return None
    return fechado_em_atual or datetime.now(timezone.utc).isoformat()
