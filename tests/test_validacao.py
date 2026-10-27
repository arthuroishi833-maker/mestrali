"""Testes de core/validacao.py. Rodar com: pytest"""

from core import validacao as v


def test_texto_tira_espacos():
    assert v.validar_texto("  Clima Frio  ", "Nome") == ("Clima Frio", "")


def test_texto_obrigatorio_vazio():
    valor, erro = v.validar_texto("   ", "Nome", obrigatorio=True)
    assert valor == "" and "obrigatório" in erro


def test_texto_opcional_vazio_e_valido():
    assert v.validar_texto("", "Nome") == ("", "")


def test_texto_longo_demais():
    _, erro = v.validar_texto("a" * 81, "Nome", maximo=80)
    assert "máximo de 80" in erro


def test_texto_no_limite():
    valor, erro = v.validar_texto("a" * 80, "Nome", maximo=80)
    assert erro == "" and len(valor) == 80


def test_email_valido_fica_minusculo():
    assert v.validar_email(" Joao@Exemplo.com ") == ("joao@exemplo.com", "")


def test_email_invalido():
    for ruim in ["", "joao", "joao@", "@x.com", "a b@x.com", "joao@x"]:
        assert v.validar_email(ruim)[1] != "", ruim


# ------------------------------------------------------------- senha forte
FALTA = "Sua senha deve ter pelo menos: "
SEQUENCIA = "Sua senha não pode conter sequências como 1234 ou abcd."


def test_senha_forte_e_aceita():
    assert v.validar_senha("Casa@2024") == ("Casa@2024", "")
    for especial in "@#$%&":
        assert v.validar_senha(f"Casa{especial}Verde7") == (f"Casa{especial}Verde7", "")


def test_senha_sem_numero():
    assert v.validar_senha("Casa@Verde") == ("", FALTA + "um número.")


def test_senha_sem_maiuscula():
    assert v.validar_senha("casa@2024") == ("", FALTA + "uma letra maiúscula.")


def test_senha_sem_minuscula():
    assert v.validar_senha("CASA@2024") == ("", FALTA + "uma letra minúscula.")


def test_senha_sem_caractere_especial():
    assert v.validar_senha("Casa2024") == ("", FALTA + "um caractere especial (@ # $ % &).")
    # outros símbolos não contam como o especial exigido
    assert v.validar_senha("Casa-2024!")[1] == FALTA + "um caractere especial (@ # $ % &)."


def test_senha_lista_tudo_que_falta_numa_frase_so():
    assert v.validar_senha("casa2024")[1] == (
        FALTA + "uma letra maiúscula e um caractere especial (@ # $ % &).")
    assert v.validar_senha("abc")[1] == (
        FALTA + "8 caracteres, uma letra maiúscula, um número e "
        "um caractere especial (@ # $ % &).")
    assert v.validar_senha("")[1] == (
        FALTA + "8 caracteres, uma letra minúscula, uma letra maiúscula, um número e "
        "um caractere especial (@ # $ % &).")


def test_senha_com_sequencia_e_recusada():
    for senha in ["Abcd@xyz", "Xy@1234z", "Xy@4321z", "Xy@dcbaZ", "Xy@ABCDz", "Xy@aBcDz", "Zy@9876k"]:
        valor, erro = v.validar_senha(senha)
        assert valor == "" and SEQUENCIA in erro, senha
    # com todos os outros requisitos cumpridos, a frase da sequência vem sozinha
    for senha in ["Xy@1234z", "Xy@4321z", "Zy@9876k", "Xy@7dcbaZ", "Abcd@xy7"]:
        assert v.validar_senha(senha) == ("", SEQUENCIA), senha


def test_senha_com_falta_e_sequencia_mostra_as_duas_frases():
    assert v.validar_senha("abcd1234")[1] == (
        FALTA + "uma letra maiúscula e um caractere especial (@ # $ % &). " + SEQUENCIA)


def test_sequencia_de_tres_ou_quebrada_nao_conta():
    for senha in ["Casa@123x", "Casa@abcX7", "Casa@12a34", "Casa@1357", "Casa@aaaa7", "Casa@89ab"]:
        assert v.validar_senha(senha)[1] == "", senha
    assert v.tem_sequencia("12349") and v.tem_sequencia("x9876") and v.tem_sequencia("wxyz")
    assert not v.tem_sequencia("9012")       # não "dá a volta" de 9 para 0
    assert not v.tem_sequencia("yzab")       # nem de z para a


def test_senha_longa_demais():
    assert v.validar_senha("Aa@" + "x" * 70)[1] == "A senha pode ter no máximo 72 caracteres."


def test_requisitos_da_senha_para_a_barra_de_forca():
    cumpridos = [ok for _, ok in v.requisitos_da_senha("casa")]
    assert cumpridos == [False, True, False, False, False]
    assert all(ok for _, ok in v.requisitos_da_senha("Casa@2024"))


# ---------------------------------------------------------------- telefone
SO_NUMEROS = "O telefone deve conter apenas números."
NO_MAXIMO = "O telefone deve ter no máximo 11 números, incluindo o DDD."


def test_telefone_so_com_numeros_e_aceito():
    assert v.validar_telefone("27999998888") == ("27999998888", "")
    assert v.validar_telefone("2733330000") == ("2733330000", "")     # fixo, 10 dígitos


def test_telefone_com_mascara_e_bloqueado():
    assert v.validar_telefone("(27) 99999-8888") == ("", SO_NUMEROS)


def test_telefone_com_qualquer_outro_caractere_e_bloqueado():
    for ruim in ["27abc998888", "27 99999888", "27-99998888", "27.99998888", "+2799999888",
                 "(2799999888", " 2799999888", "2799999888 ", "２７９９９９９８８８８"]:
        assert v.validar_telefone(ruim) == ("", SO_NUMEROS), repr(ruim)


def test_telefone_com_mais_de_11_numeros_e_bloqueado():
    assert v.validar_telefone("279999988881") == ("", NO_MAXIMO)
    assert v.validar_telefone("5527999998888") == ("", NO_MAXIMO)


def test_telefone_curto_demais_e_bloqueado():
    assert v.validar_telefone("999998888")[1] != ""       # sem DDD


def test_telefone_vazio_opcional():
    assert v.validar_telefone("") == ("", "")


def test_telefone_vazio_obrigatorio():
    assert v.validar_telefone("", obrigatorio=True)[1] != ""


def test_formatar_telefone():
    assert v.formatar_telefone("27999990000") == "(27) 99999-0000"
    assert v.formatar_telefone("2733330000") == "(27) 3333-0000"
    assert v.formatar_telefone("") == ""


def test_validade():
    assert v.validar_validade(7) == (7, "")
    assert v.validar_validade(0)[1] != ""
    assert v.validar_validade(91)[1] != ""
    assert v.validar_validade("abc")[1] != ""


def test_quantidade():
    assert v.validar_quantidade(1) == (1, "")
    assert v.validar_quantidade(999) == (999, "")
    assert v.validar_quantidade(0)[1] != ""
    assert v.validar_quantidade(1000)[1] != ""
    assert v.validar_quantidade("x")[1] != ""


def test_desconto_em_reais_limitado_ao_subtotal():
    assert v.validar_desconto("valor", 50, 100) == (50.0, "")
    assert v.validar_desconto("valor", 100, 100) == (100.0, "")
    assert "subtotal" in v.validar_desconto("valor", 100.01, 100)[1]


def test_desconto_percentual_ate_100():
    assert v.validar_desconto("percentual", 100, 50) == (100.0, "")
    assert "100%" in v.validar_desconto("percentual", 101, 50)[1]


def test_desconto_negativo_ou_tipo_invalido():
    assert v.validar_desconto("valor", -1, 100)[1] != ""
    assert v.validar_desconto("outro", 1, 100)[1] != ""


def test_codigo_de_redefinicao():
    assert v.validar_codigo(" 123 456 ") == ("123456", "")
    assert v.validar_codigo("12345")[1] != ""
    assert v.validar_codigo("12a456")[1] != ""
    assert v.validar_codigo("")[1] != ""


def test_total_do_orcamento_precisa_caber_no_banco():
    assert v.validar_total(0) == ""
    assert v.validar_total(99_999_999.99) == ""
    assert "limite" in v.validar_total(100_000_000.00)


# ------------------------------------------------------- reforços da revisão 2
def test_email_so_aceita_dominio_com_cara_de_dominio():
    # O que vem depois do "@" aparece em mensagem de erro e é consultado no DNS:
    # só letras, números, hífen e pontos.
    for bom in ["ana@exemplo.com", "ana.silva+orc@sub.exemplo.com.br", "a_b-c@x-y.co", "o'neil@exemplo.com"]:
        assert v.validar_email(bom)[1] == "", bom
    for ruim in ["a@[clique](http://x.co).zz", "a@exemplo .com", "a@-exemplo.com", "a@exemplo-.com",
                 "a@exem_plo.com", "a@exemplo..com", "a@.com", "a@exemplo", "<b>@exemplo.com",
                 "a b@exemplo.com", "a@exemplo.com.", "a@ex(emplo).com", "ação@exemplo.com"]:
        assert v.validar_email(ruim)[1] != "", ruim


def test_texto_perde_caracteres_de_controle():
    assert v.validar_texto("Ma\x00ri\x07a", "Nome") == ("Maria", "")
    assert v.validar_texto("linha1\nlinha2\tfim", "Nome") == ("linha1 linha2 fim", "")
    assert v.validar_texto("a\u2028b\u2029c", "Nome") == ("abc", "")
    # Um texto só de controles é vazio, e o campo obrigatório percebe.
    assert v.validar_texto("\x00\x01", "Nome", obrigatorio=True)[1] != ""
    # Acentos, emojis e outros alfabetos continuam.
    assert v.validar_texto("José 😀 日本", "Nome") == ("José 😀 日本", "")


def test_texto_de_varias_linhas_guarda_as_quebras():
    assert v.validar_texto(" a\r\nb\rc\n ", "Obs", 500, multilinha=True) == ("a\nb\nc", "")
    assert v.validar_texto("a\x00\nb", "Obs", 500, multilinha=True) == ("a\nb", "")


def test_dinheiro_arredonda_meio_centavo_para_cima_e_barra_infinito():
    assert v.validar_dinheiro(2.675, "x") == (2.68, "")
    assert v.validar_dinheiro("10.994", "x") == (10.99, "")
    assert v.validar_dinheiro(float("inf"), "x")[1] != ""
    assert v.validar_dinheiro(float("nan"), "x")[1] != ""
    assert v.validar_dinheiro(-0.001, "x")[1] != ""
