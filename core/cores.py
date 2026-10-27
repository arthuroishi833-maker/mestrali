"""Cor do orçamento: a cor de destaque do PDF, escolhida pelo técnico no Perfil.

O PDF usa uma cor principal (nome da empresa, linhas, cabeçalho da tabela, total)
e três tons claros tirados dela (faixa da data, linhas da tabela, bordas).
O técnico escolhe só a principal; os tons claros saem daqui.

Regra de legibilidade: o total e o cabeçalho da tabela têm texto BRANCO em cima
da cor. Por isso a cor precisa de contraste de pelo menos 4,5 com o branco
(o mínimo recomendado para texto, pelas normas de acessibilidade WCAG AA).
Cor clara demais é recusada, com a explicação.
"""

import re

COR_PADRAO = "#0A58CA"
CONTRASTE_MINIMO = 4.5

# Cores prontas. Todas passam na regra de contraste (há um teste que confere).
CORES_PRONTAS = {
    "Azul": "#0A58CA",
    "Verde": "#0E7A4B",
    "Vermelho": "#B42318",
    "Laranja": "#B54708",
    "Roxo": "#6941C6",
    "Vinho": "#8B1E3F",
    "Petróleo": "#0E6A82",
    "Grafite": "#344054",
}

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def hex_para_rgb(cor):
    cor = cor.lstrip("#")
    return tuple(int(cor[i: i + 2], 16) for i in (0, 2, 4))


def contraste_com_branco(cor):
    """Razão de contraste entre a cor e o branco (1 = nenhum, 21 = máximo)."""
    def canal(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(v) for v in hex_para_rgb(cor))
    luminancia = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return 1.05 / (luminancia + 0.05)


def validar_cor(cor):
    """Devolve (cor em maiúsculas, "") se servir, ou (None, mensagem de erro)."""
    cor = str(cor or "").strip()
    if not _HEX.match(cor):
        return None, "Escolha uma cor válida."
    if contraste_com_branco(cor) < CONTRASTE_MINIMO:
        return None, ("Essa cor é clara demais: o texto branco do total e da tabela ficaria difícil "
                      "de ler no PDF. Escolha um tom mais escuro.")
    return cor.upper(), ""


def _misturar_com_branco(rgb, quanto_branco):
    return tuple(round(v + (255 - v) * quanto_branco) for v in rgb)


def paleta(cor):
    """As cores do PDF a partir da cor escolhida. Cor vazia ou inválida = azul padrão."""
    cor_ok, erro = validar_cor(cor) if cor else (None, "vazia")
    principal = hex_para_rgb(cor_ok or COR_PADRAO)
    return {
        "principal": principal,
        "gelo": _misturar_com_branco(principal, 0.93),      # faixa da data e linhas do total
        "listra": _misturar_com_branco(principal, 0.97),    # linhas alternadas da tabela
        "borda": _misturar_com_branco(principal, 0.8),      # bordas da tabela
    }
