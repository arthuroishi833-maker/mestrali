"""Testes de core/verificar_email.py, com o DNS simulado (sem internet)."""

from unittest.mock import MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from core import verificar_email as ve


@pytest.fixture(autouse=True)
def sem_cache():
    ve.dominio_recebe_email.cache_clear()
    yield
    ve.dominio_recebe_email.cache_clear()


def dns_que_responde(respostas):
    """respostas: {"MX": [...], "A": [...]}; uma exceção no lugar da lista é levantada."""

    def consultar(dominio, tipo):
        resposta = respostas.get(tipo, [])
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    return patch("core.verificar_email._consultar", side_effect=consultar)


def mx(servidor):
    registro = MagicMock()
    registro.exchange = servidor
    return registro


def test_dominio_com_servidor_de_email():
    with dns_que_responde({"MX": [mx("smtp.gmail.com.")]}):
        assert ve.dominio_recebe_email("gmail.com") is True
        assert ve.erro_de_dominio("maria@gmail.com") == ""


def test_dominio_que_nao_existe():
    with dns_que_responde({"MX": dns.resolver.NXDOMAIN()}):
        assert ve.dominio_recebe_email("gmail.con") is False
        erro = ve.erro_de_dominio("Maria@Gmail.CON")
        assert "@gmail.con" in erro and "Confira se digitou certo" in erro


def test_dominio_que_declara_nao_receber_email():
    with dns_que_responde({"MX": [mx(".")]}):
        assert ve.dominio_recebe_email("example.com") is False


def test_dominio_sem_mx_mas_com_endereco_ainda_recebe():
    with dns_que_responde({"MX": [], "A": ["203.0.113.5"]}):
        assert ve.dominio_recebe_email("empresa-pequena.com.br") is True


def test_dominio_sem_mx_e_sem_endereco():
    with dns_que_responde({"MX": [], "A": [], "AAAA": []}):
        assert ve.dominio_recebe_email("so-o-nome.com.br") is False


def test_falha_de_rede_nao_bloqueia():
    with dns_que_responde({"MX": dns.exception.Timeout()}):
        assert ve.dominio_recebe_email("gmail.com") is None
        assert ve.erro_de_dominio("maria@gmail.com") == ""
