"""Leitura e gravação no banco (tabelas do sql/schema.sql).

Todas as funções usam o cliente da sessão, que carrega o token do usuário
logado. O Row Level Security do Supabase garante que cada consulta só
enxerga as linhas desse usuário, mesmo que o código esqueça um filtro.
"""

from core.situacao import CONTAM_NO_FINANCEIRO, data_de_fechamento
from core.supabase_client import obter_cliente
from core.validacao import validar_telefone


def _conferir_telefone(telefone):
    """Última barreira antes do banco: telefone fora do padrão não é gravado.

    As telas já validam e mostram a mensagem; isto protege contra qualquer
    caminho que esqueça de validar. Levanta ValueError com a mesma mensagem.
    """
    _, erro = validar_telefone(telefone)
    if erro:
        raise ValueError(erro)

PERFIL_PADRAO = {
    "nome_empresa": "",
    "telefone": "",
    "logo_base64": None,
    "validade_dias": 7,
}


# ---------------------------------------------------------------- PERFIL
def buscar_perfil(user_id):
    """Devolve o perfil do técnico (dict). Se ainda não existe, o padrão."""
    resposta = (
        obter_cliente().table("perfis").select("*").eq("user_id", user_id).execute()
    )
    if resposta.data:
        return resposta.data[0]
    return dict(PERFIL_PADRAO)


def salvar_perfil(user_id, nome_empresa, telefone, validade_dias, logo_base64):
    """Cria ou atualiza o perfil (upsert = insert, ou update se já existe)."""
    _conferir_telefone(telefone)
    obter_cliente().table("perfis").upsert(
        {
            "user_id": user_id,
            "nome_empresa": nome_empresa,
            "telefone": telefone,
            "validade_dias": validade_dias,
            "logo_base64": logo_base64,
        }
    ).execute()


def salvar_mensagem_whatsapp(user_id, mensagem):
    """Grava o texto do WhatsApp escolhido pelo técnico ("" = usar o padrão).

    Fica separado do salvar_perfil de propósito: se a coluna ainda não existe
    no banco (falta rodar sql/migracao_005.sql), só esta gravação falha e o
    resto do perfil continua funcionando.
    """
    obter_cliente().table("perfis").upsert(
        {"user_id": user_id, "mensagem_whatsapp": mensagem}
    ).execute()


def salvar_cor_orcamento(user_id, cor):
    """Grava a cor do orçamento ("" = azul padrão). Separada do perfil pelo mesmo motivo
    da mensagem: sem a migração 008, só esta gravação falha."""
    obter_cliente().table("perfis").upsert({"user_id": user_id, "cor_orcamento": cor}).execute()


# -------------------------------------------------------------- CATÁLOGO
def listar_catalogo(user_id):
    """Devolve os itens do catálogo (lista de dicts), por tipo e nome."""
    resposta = (
        obter_cliente()
        .table("itens_catalogo")
        .select("id, nome, tipo, custo, preco")
        .eq("user_id", user_id)
        .order("tipo")
        .order("nome")
        .execute()
    )
    return resposta.data


def inserir_itens_catalogo(user_id, itens):
    """Insere um ou mais itens. Cada item: dict com nome, tipo, custo, preco."""
    linhas = [dict(item, user_id=user_id) for item in itens]
    if not linhas:
        return   # o servidor recusa uma lista vazia; não há o que gravar
    obter_cliente().table("itens_catalogo").insert(linhas).execute()


def atualizar_item_catalogo(user_id, item_id, nome, tipo, custo, preco):
    (
        obter_cliente()
        .table("itens_catalogo")
        .update({"nome": nome, "tipo": tipo, "custo": custo, "preco": preco})
        .eq("id", item_id)
        .eq("user_id", user_id)
        .execute()
    )


def excluir_item_catalogo(user_id, item_id):
    (
        obter_cliente()
        .table("itens_catalogo")
        .delete()
        .eq("id", item_id)
        .eq("user_id", user_id)
        .execute()
    )


def excluir_todo_o_catalogo(user_id):
    """Apaga todos os itens do catálogo do usuário. Os orçamentos já salvos não mudam:
    cada orçamento guarda a sua própria cópia dos itens."""
    obter_cliente().table("itens_catalogo").delete().eq("user_id", user_id).execute()


# ------------------------------------------------------------ ORÇAMENTOS
def salvar_orcamento(user_id, dados, itens, total):
    """Grava o orçamento e seus itens. Devolve {"id": ..., "numero": ...}.

    O número (1, 2, 3... por técnico) é definido pelo próprio banco na hora
    de gravar; veja o gatilho "numerar_orcamento" no sql/schema.sql.

    dados: dict com cliente_nome, cliente_telefone, equipamento, mao_de_obra,
           desconto_tipo, desconto_valor, condicoes_pagamento, observacoes,
           validade_dias.
    itens: lista de dicts com nome, tipo, quantidade, custo_unitario,
           preco_unitario.

    São duas gravações (orçamento, depois itens). Se a segunda falhar,
    o orçamento é apagado para não ficar um orçamento pela metade.

    Um orçamento pode não ter itens (só mão de obra). Nesse caso a segunda
    gravação é pulada: o servidor recusa uma lista vazia (erro PGRST100), e
    era isso que fazia todo orçamento sem itens falhar ao salvar.
    """
    _conferir_telefone(dados.get("cliente_telefone"))
    cliente = obter_cliente()
    linha = dict(dados, user_id=user_id, total=total)
    resposta = cliente.table("orcamentos").insert(linha).execute()
    orcamento_id = resposta.data[0]["id"]

    linhas_itens = [
        dict(item, orcamento_id=orcamento_id, user_id=user_id) for item in itens
    ]
    if not linhas_itens:
        return {"id": orcamento_id, "numero": resposta.data[0].get("numero")}
    try:
        cliente.table("itens_orcamento").insert(linhas_itens).execute()
    except Exception:
        (
            cliente.table("orcamentos").delete()
            .eq("id", orcamento_id).eq("user_id", user_id).execute()
        )
        raise
    return {"id": orcamento_id, "numero": resposta.data[0].get("numero")}


MAX_ORCAMENTOS_NA_LISTA = 500


def listar_orcamentos(user_id):
    """Orçamentos do técnico, do mais recente para o mais antigo."""
    resposta = (
        obter_cliente()
        .table("orcamentos")
        .select("id, numero, cliente_nome, total, criado_em, fechado_em, situacao")
        .eq("user_id", user_id)   # além do RLS: nunca lista dados de outro usuário
        .order("criado_em", desc=True)
        .limit(MAX_ORCAMENTOS_NA_LISTA)
        .execute()
    )
    return resposta.data


def definir_situacao(user_id, orcamento_id, situacao, fechado_em_atual=None):
    """Muda a situação do orçamento (não fechado, fechado ou pago; veja core/situacao.py).

    A data de fechamento fica a da primeira vez que ele foi fechado; volta a vazia
    se o orçamento voltar para "não fechado".
    """
    (
        obter_cliente()
        .table("orcamentos")
        .update({"situacao": situacao, "fechado_em": data_de_fechamento(situacao, fechado_em_atual)})
        .eq("id", orcamento_id)
        .eq("user_id", user_id)
        .execute()
    )


def listar_fechados(user_id, inicio_utc, fim_utc):
    """Orçamentos fechados ou pagos no período [inicio, fim), com os itens (para somar o custo)."""
    resposta = (
        obter_cliente()
        .table("orcamentos")
        .select("id, total, desconto_tipo, desconto_valor, mao_de_obra, fechado_em, situacao, "
                "itens:itens_orcamento(nome, tipo, quantidade, custo_unitario, preco_unitario)")
        .eq("user_id", user_id)
        .in_("situacao", list(CONTAM_NO_FINANCEIRO))
        .gte("fechado_em", inicio_utc)
        .lt("fechado_em", fim_utc)
        .execute()
    )
    return resposta.data


def buscar_orcamento(user_id, orcamento_id):
    """Um orçamento completo, com a lista "itens". None se não for do usuário.

    O filtro por user_id (e o RLS no banco) impede abrir o orçamento de
    outra pessoa mesmo que alguém descubra o id dele.
    """
    cliente = obter_cliente()
    resposta = (
        cliente.table("orcamentos").select("*")
        .eq("id", orcamento_id).eq("user_id", user_id).execute()
    )
    if not resposta.data:
        return None
    orcamento = resposta.data[0]
    itens = (
        cliente.table("itens_orcamento")
        .select("nome, tipo, quantidade, custo_unitario, preco_unitario")
        .eq("orcamento_id", orcamento_id).eq("user_id", user_id)
        .order("id").execute()
    )
    orcamento["itens"] = itens.data
    return orcamento


def excluir_orcamento(user_id, orcamento_id):
    """Apaga um orçamento do técnico. Devolve quantos foram apagados (0 ou 1).

    Os itens somem junto: a tabela itens_orcamento tem "on delete cascade".
    """
    resposta = (
        obter_cliente().table("orcamentos").delete()
        .eq("id", orcamento_id).eq("user_id", user_id).execute()
    )
    return len(resposta.data)


# ------------------------------------------------------- PRIVACIDADE (LGPD)
def aceitou_politica(user_id, versao):
    """True se o usuário já aceitou esta versão da política de privacidade."""
    resposta = (
        obter_cliente().table("aceites").select("id")
        .eq("user_id", user_id).eq("versao_politica", versao).limit(1).execute()
    )
    return bool(resposta.data)


def registrar_aceite(user_id, versao):
    """Grava o aceite. A data e a hora são as do servidor, não as do aplicativo."""
    obter_cliente().table("aceites").insert(
        {"user_id": user_id, "versao_politica": versao}
    ).execute()


def listar_aceites(user_id):
    resposta = (
        obter_cliente().table("aceites").select("versao_politica, aceito_em")
        .eq("user_id", user_id).order("aceito_em").execute()
    )
    return resposta.data


def listar_orcamentos_completos(user_id):
    """Todos os orçamentos do técnico, cada um com a lista "itens" (para exportar)."""
    resposta = (
        obter_cliente().table("orcamentos")
        .select("*, itens:itens_orcamento(nome, tipo, quantidade, custo_unitario, preco_unitario)")
        .eq("user_id", user_id).order("criado_em", desc=True).execute()
    )
    return resposta.data


CAMPOS_DO_CLIENTE = (
    "cliente_nome", "cliente_telefone", "equipamento", "condicoes_pagamento", "observacoes",
)


def corrigir_dados_do_cliente(user_id, orcamento_id, dados):
    """Corrige os dados do cliente num orçamento salvo. Devolve 0 ou 1.

    Só os campos de CAMPOS_DO_CLIENTE são gravados: itens, valores, número
    e data nunca mudam por aqui, mesmo que venham no dict.
    """
    permitidos = {campo: dados[campo] for campo in CAMPOS_DO_CLIENTE if campo in dados}
    if not permitidos:
        return 0
    if "cliente_telefone" in permitidos:
        _conferir_telefone(permitidos["cliente_telefone"])
    resposta = (
        obter_cliente().table("orcamentos").update(permitidos)
        .eq("id", orcamento_id).eq("user_id", user_id).execute()
    )
    return len(resposta.data)


def anonimizar_orcamentos(user_id, ids, dados_anonimos):
    """Troca os dados pessoais do cliente nos orçamentos indicados.

    Itens e valores ficam, para o histórico do técnico. Devolve quantos mudaram.
    """
    if not ids:
        return 0
    resposta = (
        obter_cliente().table("orcamentos").update(dados_anonimos)
        .in_("id", ids).eq("user_id", user_id).execute()
    )
    return len(resposta.data)


def excluir_orcamentos(user_id, ids):
    """Apaga os orçamentos indicados (e seus itens). Devolve quantos foram apagados."""
    if not ids:
        return 0
    resposta = (
        obter_cliente().table("orcamentos").delete()
        .in_("id", ids).eq("user_id", user_id).execute()
    )
    return len(resposta.data)


def registrar_auditoria(user_id, acao, quantidade=0):
    """Anota que uma exportação ou exclusão aconteceu (quem, o quê, quantos, quando).

    Nunca recebe nome, telefone nem outro dado pessoal. Se a anotação falhar,
    a operação principal não é desfeita.
    """
    try:
        obter_cliente().table("auditoria").insert(
            {"user_id": user_id, "acao": acao, "quantidade": int(quantidade)}
        ).execute()
    except Exception:
        pass


def excluir_minha_conta():
    """Apaga a conta do usuário logado e tudo que é dele. Não tem volta.

    Quem apaga é a função "excluir_minha_conta" do banco (sql/schema.sql),
    que só age sobre a conta de quem chama.
    """
    obter_cliente().rpc("excluir_minha_conta").execute()


# ------------------------------------------------- BANCO ATUALIZADO?
# Códigos de erro que significam "falta rodar uma migração":
#   42703 / PGRST204 = coluna não existe   (leitura / gravação)
#   42P01 / PGRST205 = tabela não existe
#   PGRST202         = função não existe
CODIGOS_DE_ESTRUTURA = ("42703", "PGRST204", "42P01", "PGRST205", "PGRST202")
COLUNAS_NOVAS = "numero, mao_de_obra, condicoes_pagamento, fechado_em, situacao"   # migrações 002, 007 e 009


def codigo_do_erro(erro):
    """Código técnico de um erro do banco (ex.: "42501"), ou "" se não houver.

    Serve para mostrar na tela junto da mensagem genérica: não tem dado
    pessoal e é o que permite descobrir a causa. Só letras, números e "_".
    """
    codigo = str(getattr(erro, "code", "") or "")
    limpo = "".join(c for c in codigo if c.isalnum() or c == "_")
    return limpo[:20]


def falta_coluna(erro):
    """True se o erro do banco indica coluna, tabela ou função inexistente."""
    texto = f"{getattr(erro, 'code', '')} {erro}"
    return any(codigo in texto for codigo in CODIGOS_DE_ESTRUTURA)


def migracao_pendente():
    """True se o banco ainda não recebeu todas as migrações (sql/migracao_*.sql).

    Se a consulta falhar por outro motivo (internet fora do ar, por exemplo),
    o erro é repassado: não dá para afirmar nem que falta, nem que está em dia.
    """
    cliente = obter_cliente()
    try:
        cliente.table("orcamentos").select(COLUNAS_NOVAS).limit(1).execute()   # 002
        cliente.table("aceites").select("id").limit(1).execute()               # 003
        cliente.table("auditoria").select("id").limit(1).execute()             # 003
    except Exception as erro:
        if falta_coluna(erro):
            return True
        raise
    return False
