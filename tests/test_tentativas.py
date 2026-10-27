"""Testes do freio contra força bruta no login. Rodar com: pytest"""

from core.tentativas import (
    BLOQUEIO_MAXIMO,
    MAX_FALHAS,
    registrar_falha,
    registrar_sucesso,
    segundos_bloqueado,
)


def test_libera_antes_do_limite():
    estado = {}
    for _ in range(MAX_FALHAS - 1):
        registrar_falha(estado, agora=1000)
    assert segundos_bloqueado(estado, agora=1000) == 0


def test_bloqueia_por_um_minuto_ao_atingir_o_limite():
    estado = {}
    for _ in range(MAX_FALHAS):
        registrar_falha(estado, agora=1000)
    assert segundos_bloqueado(estado, agora=1000) == 60
    assert segundos_bloqueado(estado, agora=1030) == 30
    assert segundos_bloqueado(estado, agora=1060) == 0


def test_bloqueio_dobra_e_tem_teto():
    estado, agora, duracoes = {}, 0, []
    for _ in range(8):
        for _ in range(MAX_FALHAS):
            registrar_falha(estado, agora)
        duracoes.append(segundos_bloqueado(estado, agora))
        agora += duracoes[-1]
    assert duracoes[:5] == [60, 120, 240, 480, BLOQUEIO_MAXIMO]
    assert max(duracoes) == BLOQUEIO_MAXIMO


def test_sucesso_zera_a_contagem():
    estado = {}
    for _ in range(MAX_FALHAS - 1):
        registrar_falha(estado, agora=0)
    registrar_sucesso(estado)
    registrar_falha(estado, agora=0)
    assert segundos_bloqueado(estado, agora=0) == 0
