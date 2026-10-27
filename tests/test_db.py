"""Testes de core/db.py com um Supabase falso (mock). Rodar com: pytest"""

from unittest.mock import MagicMock, patch

from core import db

DADOS = {
    "cliente_nome": "Maria", "cliente_telefone": "", "equipamento": "", "mao_de_obra": 200.0,
    "desconto_tipo": "valor", "desconto_valor": 0.0, "condicoes_pagamento": "",
    "observacoes": "", "validade_dias": 7,
}
ITEM = {"nome": "Limpeza", "tipo": "mao_de_obra", "quantidade": 1, "custo_unitario": 20.0, "preco_unitario": 180.0}


def cliente_falso():
    cliente = MagicMock()
    cliente.table.return_value.insert.return_value.execute.return_value.data = [{"id": "o1", "numero": 3}]
    return cliente


def tabelas_usadas(cliente):
    return [chamada.args[0] for chamada in cliente.table.call_args_list]


def test_orcamento_so_com_mao_de_obra_nao_envia_lista_vazia_de_itens():
    # O servidor recusa uma lista vazia (erro PGRST100: "failed to parse columns parameter").
    # Antes desta proteção, todo orçamento sem itens falhava ao salvar, e o
    # orçamento recém-gravado era apagado em seguida.
    cliente = cliente_falso()
    with patch("core.db.obter_cliente", return_value=cliente):
        gravado = db.salvar_orcamento("u1", DADOS, [], 200.0)
    assert gravado == {"id": "o1", "numero": 3}
    assert tabelas_usadas(cliente) == ["orcamentos"]            # nem tocou em itens_orcamento
    cliente.table.return_value.delete.assert_not_called()       # e não apagou o orçamento


def test_orcamento_com_itens_grava_as_duas_tabelas():
    cliente = cliente_falso()
    with patch("core.db.obter_cliente", return_value=cliente):
        db.salvar_orcamento("u1", DADOS, [ITEM], 380.0)
    assert tabelas_usadas(cliente) == ["orcamentos", "itens_orcamento"]
    linhas = cliente.table.return_value.insert.call_args_list[1].args[0]
    assert linhas == [dict(ITEM, orcamento_id="o1", user_id="u1")]


def test_se_os_itens_falham_o_orcamento_e_apagado():
    cliente = cliente_falso()
    gravar_orcamento = cliente.table.return_value.insert.return_value.execute
    gravar_orcamento.side_effect = [gravar_orcamento.return_value, Exception("falhou")]
    with patch("core.db.obter_cliente", return_value=cliente):
        try:
            db.salvar_orcamento("u1", DADOS, [ITEM], 380.0)
        except Exception as erro:
            assert str(erro) == "falhou"
        else:
            raise AssertionError("deveria repassar o erro")
    cliente.table.return_value.delete.assert_called_once()


def test_catalogo_sem_itens_para_inserir_nao_chama_o_servidor():
    cliente = cliente_falso()
    with patch("core.db.obter_cliente", return_value=cliente):
        db.inserir_itens_catalogo("u1", [])
    cliente.table.assert_not_called()
