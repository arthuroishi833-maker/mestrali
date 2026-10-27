"""Freio contra tentativa de adivinhar senha (força bruta) no login.

Depois de MAX_FALHAS erros seguidos, o login fica bloqueado por um tempo
que dobra a cada novo bloqueio (1 min, 2 min, 4 min... até 15 min).

LIMITE CONHECIDO: a contagem vale para a sessão do navegador. Quem abrir
uma sessão nova recomeça do zero. A proteção de verdade é a do Supabase
Auth, que limita tentativas por endereço de rede no servidor; este freio
é uma camada a mais, que também evita cliques repetidos por engano.

Funções puras: recebem o dict de estado e o horário (segundos), para
poderem ser testadas sem esperar o relógio.
"""

MAX_FALHAS = 5
BLOQUEIO_INICIAL = 60        # segundos
BLOQUEIO_MAXIMO = 15 * 60    # segundos


def segundos_bloqueado(estado, agora):
    """Quantos segundos faltam para poder tentar de novo (0 = liberado)."""
    return max(0, int(estado.get("bloqueado_ate", 0) - agora + 0.999))


def registrar_falha(estado, agora):
    """Conta um erro de login; bloqueia ao atingir o limite."""
    estado["falhas"] = estado.get("falhas", 0) + 1
    if estado["falhas"] >= MAX_FALHAS:
        duracao = min(BLOQUEIO_INICIAL * 2 ** estado.get("bloqueios", 0), BLOQUEIO_MAXIMO)
        estado["bloqueado_ate"] = agora + duracao
        estado["bloqueios"] = estado.get("bloqueios", 0) + 1
        estado["falhas"] = 0


def registrar_sucesso(estado):
    """Login correto: zera a contagem."""
    estado.clear()
