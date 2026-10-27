"""Testes de core/whatsapp.py. Rodar com: pytest"""

from datetime import date
from urllib.parse import parse_qs, urlparse

from core.calculos import calcular_resumo
from core.whatsapp import MODELO_SUGERIDO, aplicar_modelo, inicio_do_link, montar_link, montar_mensagem

PERFIL = {"nome_empresa": "Clima Frio", "telefone": "27999990000"}
DADOS = {"cliente_nome": "Maria Conceição", "equipamento": "Split 12.000 BTUs", "validade_dias": 7}
ITENS = [{"quantidade": 2, "custo_unitario": 31.47, "preco_unitario": 100.0}]
RESUMO = calcular_resumo(ITENS, "valor", 0)
DATA = date(2026, 10, 9)


def test_mensagem_tem_o_essencial():
    texto = montar_mensagem(PERFIL, DADOS, RESUMO, DATA)
    assert "Olá, Maria!" in texto
    assert "Clima Frio" in texto
    assert "Split 12.000 BTUs" in texto
    assert "R$ 200,00" in texto
    assert "16/10/2026" in texto
    assert "anexo" in texto


def test_mensagem_nunca_fala_de_custo_ou_lucro():
    texto = montar_mensagem(PERFIL, DADOS, RESUMO, DATA).lower()
    for proibido in ["custo", "lucro", "margem", "31,47", "62,94", "137,06"]:
        assert proibido not in texto


def test_link_com_telefone_usa_codigo_do_brasil():
    link = montar_link("27988887777", "Olá!")
    assert link.startswith("https://wa.me/5527988887777?text=")


def test_link_sem_telefone():
    assert montar_link("", "Olá!").startswith("https://wa.me/?text=")


def test_mensagem_volta_igual_depois_de_codificada():
    mensagem = montar_mensagem(PERFIL, DADOS, RESUMO, DATA)
    link = montar_link("27988887777", mensagem)
    assert parse_qs(urlparse(link).query)["text"] == [mensagem]


def test_texto_malicioso_nao_muda_o_endereco():
    link = montar_link("27988887777", "oi&text=outro#x?y=1 https://site.com")
    partes = urlparse(link)
    assert partes.netloc == "wa.me"
    assert partes.path == "/5527988887777"
    assert partes.fragment == ""
    assert list(parse_qs(partes.query)) == ["text"]


def test_telefone_com_lixo_fica_so_com_digitos():
    assert montar_link("(27) 98888-7777/../x", "oi").startswith("https://wa.me/5527988887777?")


# ------------------------------------------------ mensagem escrita pelo técnico
def test_mensagem_do_tecnico_substitui_a_padrao():
    perfil = {**PERFIL, "mensagem_whatsapp": "Oi {cliente}! Aqui é {empresa}. {equipamento}: {total} até {validade}."}
    texto = montar_mensagem(perfil, DADOS, RESUMO, DATA)
    assert texto == "Oi Maria! Aqui é Clima Frio. Split 12.000 BTUs: R$ 200,00 até 16/10/2026."


def test_mensagem_em_branco_no_perfil_usa_a_padrao():
    assert montar_mensagem({**PERFIL, "mensagem_whatsapp": "   "}, DADOS, RESUMO, DATA) == \
        montar_mensagem(PERFIL, DADOS, RESUMO, DATA)


def test_modelo_sugerido_diz_o_mesmo_que_a_mensagem_padrao():
    assert aplicar_modelo(MODELO_SUGERIDO, PERFIL, DADOS, RESUMO, DATA) == \
        montar_mensagem(PERFIL, DADOS, RESUMO, DATA)


def test_chaves_que_nao_sao_marcadores_ficam_como_estao():
    # Nada de str.format: "{custo}", "{0}" e "{dados[x]}" não podem dar erro nem revelar nada.
    modelo = "{custo} {lucro} {0} {dados[cliente_nome]} {total.__class__} {cliente}"
    texto = aplicar_modelo(modelo, PERFIL, DADOS, RESUMO, DATA)
    assert texto == "{custo} {lucro} {0} {dados[cliente_nome]} {total.__class__} Maria"


def test_sem_equipamento_o_marcador_nao_fica_vazio():
    dados = {**DADOS, "equipamento": ""}
    assert aplicar_modelo("Orçamento para {equipamento}.", PERFIL, dados, RESUMO, DATA) == \
        "Orçamento para o serviço solicitado."


def test_inicio_do_link_nao_carrega_o_texto():
    assert inicio_do_link("(27) 98888-7777") == "https://wa.me/5527988887777?text="
    assert inicio_do_link("") == "https://wa.me/?text="
    assert montar_link("27988887777", "a b") == "https://wa.me/5527988887777?text=a%20b"
