"""Testes dos arquivos SQL num PostgreSQL de verdade (local e descartável).

Confere o que os outros testes não alcançam: se o schema.sql e a migração
rodam sem erro, se o RLS separa os usuários e se o gatilho numera certo.

Precisam do pacote "pgserver" (um PostgreSQL embutido). Sem ele, estes
testes são pulados:   pip install pgserver

O Supabase fornece o esquema "auth" (usuários, auth.uid()) e os papéis
"authenticated" e "anon". Aqui eles são imitados pelo PREPARO abaixo.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

pgserver = pytest.importorskip("pgserver")
from pgserver._commands import POSTGRES_BIN_PATH  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SCHEMA = (RAIZ / "sql" / "schema.sql").read_text(encoding="utf-8")
MIGRACAO = (RAIZ / "sql" / "migracao_002.sql").read_text(encoding="utf-8")
MIGRACAO_3 = (RAIZ / "sql" / "migracao_003.sql").read_text(encoding="utf-8")
MIGRACAO_4 = (RAIZ / "sql" / "migracao_004.sql").read_text(encoding="utf-8")
MIGRACAO_5 = (RAIZ / "sql" / "migracao_005.sql").read_text(encoding="utf-8")
MIGRACAO_6 = (RAIZ / "sql" / "migracao_006.sql").read_text(encoding="utf-8")
MIGRACAO_7 = (RAIZ / "sql" / "migracao_007.sql").read_text(encoding="utf-8")
MIGRACAO_8 = (RAIZ / "sql" / "migracao_008.sql").read_text(encoding="utf-8")
MIGRACAO_9 = (RAIZ / "sql" / "migracao_009.sql").read_text(encoding="utf-8")

U1 = "11111111-1111-1111-1111-111111111111"
U2 = "22222222-2222-2222-2222-222222222222"

PREPARO = f"""
do $$ begin
  if not exists (select from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin; create role anon nologin;
  end if;
end $$;
create schema auth;
create table auth.users (id uuid primary key);
create function auth.uid() returns uuid language sql stable as
  $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema auth to authenticated, anon;
grant usage on schema public to authenticated, anon;
-- O Supabase dá acesso às tabelas para estes papéis; quem protege é o RLS.
alter default privileges in schema public grant all on tables to authenticated, anon;
insert into auth.users values ('{U1}'), ('{U2}');
"""

# O schema.sql da primeira versão, antes das colunas novas (para testar a migração).
SCHEMA_ANTIGO_ORCAMENTOS = """
create table orcamentos (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null default auth.uid() references auth.users(id) on delete cascade,
  cliente_nome     text not null check (char_length(cliente_nome) between 1 and 80),
  cliente_telefone text not null default '' check (char_length(cliente_telefone) <= 20),
  equipamento      text not null default '' check (char_length(equipamento) <= 80),
  desconto_tipo    text not null default 'valor' check (desconto_tipo in ('valor', 'percentual')),
  desconto_valor   numeric(10,2) not null default 0 check (desconto_valor >= 0),
  observacoes      text not null default '' check (char_length(observacoes) <= 500),
  validade_dias    int  not null default 7 check (validade_dias between 1 and 90),
  total            numeric(10,2) not null default 0 check (total >= 0),
  criado_em        timestamptz not null default now()
);
alter table orcamentos enable row level security;
create policy "dono" on orcamentos for all to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
"""


@pytest.fixture(scope="module")
def servidor():
    pasta = tempfile.mkdtemp(prefix="pgteste", dir="/tmp")
    pg = pgserver.get_server(pasta, cleanup_mode="stop")
    yield pg
    pg.cleanup()
    shutil.rmtree(pasta, ignore_errors=True)


class Banco:
    """Um banco de dados vazio dentro do servidor de teste."""

    def __init__(self, servidor, nome):
        self.uri_base = servidor.get_uri()
        self._psql(self.uri_base, f"create database {nome};")
        self.uri = self.uri_base.replace("/postgres?", f"/{nome}?")

    @staticmethod
    def _psql(uri, sql):
        r = subprocess.run(
            [str(POSTGRES_BIN_PATH / "psql"), uri, "-X", "-At", "-q", "-v", "ON_ERROR_STOP=1", "-c", sql],
            capture_output=True, text=True,
        )
        return r.stdout.strip(), r.stderr.strip()

    def rodar(self, sql):
        """Roda como administrador. Falha o teste se o SQL der erro."""
        saida, erro = self._psql(self.uri, sql)
        assert "ERROR" not in erro, erro
        return saida

    def como(self, usuario, sql, papel="authenticated"):
        """Roda como um usuário logado (ou anônimo). Devolve (saída, erro)."""
        return self._psql(
            self.uri,
            f"set role {papel}; set request.jwt.claim.sub = '{usuario}'; {sql}",
        )


@pytest.fixture
def banco_novo(servidor, request):
    banco = Banco(servidor, f"novo_{abs(hash(request.node.name)) % 10**8}")
    banco.rodar(PREPARO)
    banco.rodar(SCHEMA)
    return banco


INSERIR = "insert into orcamentos (cliente_nome, total) values ('{nome}', {total}) returning numero;"


def test_schema_novo_roda_sem_erro_e_tem_as_colunas(banco_novo):
    colunas = banco_novo.rodar(
        "select string_agg(column_name, ',' order by column_name) from information_schema.columns "
        "where table_name = 'orcamentos';"
    )
    for coluna in ["numero", "mao_de_obra", "condicoes_pagamento", "total", "user_id"]:
        assert coluna in colunas.split(",")


def test_rls_ligado_em_todas_as_tabelas(banco_novo):
    sem_rls = banco_novo.rodar(
        "select count(*) from pg_tables where schemaname = 'public' and not rowsecurity;"
    )
    assert sem_rls == "0"


def test_numero_e_sequencial_por_tecnico(banco_novo):
    assert banco_novo.como(U1, INSERIR.format(nome="A", total=10))[0].endswith("1")
    assert banco_novo.como(U1, INSERIR.format(nome="B", total=10))[0].endswith("2")
    assert banco_novo.como(U2, INSERIR.format(nome="C", total=10))[0].endswith("1")
    assert banco_novo.como(U1, INSERIR.format(nome="D", total=10))[0].endswith("3")


def test_numero_enviado_pelo_aplicativo_e_ignorado(banco_novo):
    saida, _ = banco_novo.como(
        U1, "insert into orcamentos (cliente_nome, numero) values ('A', 999) returning numero;")
    assert saida.endswith("1")


def test_um_tecnico_nao_ve_nem_altera_dados_do_outro(banco_novo):
    banco_novo.como(U1, INSERIR.format(nome="Cliente do U1", total=100))
    banco_novo.como(U2, INSERIR.format(nome="Cliente do U2", total=200))

    saida, _ = banco_novo.como(U1, "select string_agg(cliente_nome, ',') from orcamentos;")
    assert saida.endswith("Cliente do U1")

    # Alterar e apagar "passam" sem erro, mas não atingem nenhuma linha do outro.
    banco_novo.como(U1, "update orcamentos set total = 0; delete from orcamentos where total > 0;")
    assert banco_novo.rodar("select total from orcamentos where cliente_nome = 'Cliente do U2';") == "200.00"


def test_nao_da_para_gravar_em_nome_de_outro_tecnico(banco_novo):
    _, erro = banco_novo.como(
        U1, f"insert into orcamentos (cliente_nome, user_id) values ('Falso', '{U2}');")
    assert "row-level security" in erro
    _, erro = banco_novo.como(
        U1, f"insert into itens_catalogo (nome, tipo, user_id) values ('x', 'peca', '{U2}');")
    assert "row-level security" in erro
    _, erro = banco_novo.como(
        U1, f"insert into perfis (user_id, nome_empresa) values ('{U2}', 'x');")
    assert "row-level security" in erro


def test_visitante_sem_login_nao_ve_nada(banco_novo):
    banco_novo.como(U1, INSERIR.format(nome="A", total=10))
    saida, erro = banco_novo.como("", "select count(*) from orcamentos;", papel="anon")
    # Com a segunda tranca (migração 006) o visitante nem tem permissão de ler.
    assert "permission denied" in erro and not saida.endswith("1")
    _, erro = banco_novo.como("", "insert into orcamentos (cliente_nome) values ('x');", papel="anon")
    assert "ERROR" in erro


def test_o_banco_recusa_valores_invalidos(banco_novo):
    invalidos = [
        "insert into orcamentos (cliente_nome, total) values ('A', -1);",
        "insert into orcamentos (cliente_nome, mao_de_obra) values ('A', -1);",
        "insert into orcamentos (cliente_nome, desconto_valor) values ('A', -1);",
        "insert into orcamentos (cliente_nome) values ('');",
        f"insert into orcamentos (cliente_nome) values ('{'x' * 81}');",
        "insert into orcamentos (cliente_nome, validade_dias) values ('A', 0);",
        f"insert into orcamentos (cliente_nome, condicoes_pagamento) values ('A', '{'x' * 201}');",
        "insert into itens_catalogo (nome, tipo, custo) values ('A', 'peca', -1);",
        "insert into itens_catalogo (nome, tipo) values ('A', 'outro');",
    ]
    for sql in invalidos:
        _, erro = banco_novo.como(U1, sql)
        assert "violates check constraint" in erro, sql


def test_fluxo_do_aplicativo_orcamento_com_itens(banco_novo):
    """As mesmas gravações e leituras que core/db.py faz."""
    saida, erro = banco_novo.como(U1, """
        insert into orcamentos (user_id, cliente_nome, cliente_telefone, equipamento, mao_de_obra,
            desconto_tipo, desconto_valor, condicoes_pagamento, observacoes, validade_dias, total)
        values (auth.uid(), 'Maria', '27988887777', 'Split', 100, 'percentual', 10, 'Pix', '', 7, 450)
        returning id;""")
    assert erro == "", erro
    orcamento_id = saida.splitlines()[-1]
    _, erro = banco_novo.como(U1, f"""
        insert into itens_orcamento (orcamento_id, user_id, nome, tipo, quantidade,
            custo_unitario, preco_unitario)
        values ('{orcamento_id}', auth.uid(), 'Capacitor', 'peca', 2, 30, 90);""")
    assert erro == "", erro
    saida, _ = banco_novo.como(U1, "select numero, total, mao_de_obra from orcamentos;")
    assert saida.endswith("1|450.00|100.00")
    # O outro técnico não enxerga os itens nem consegue pendurar itens neste orçamento.
    saida, _ = banco_novo.como(U2, "select count(*) from itens_orcamento;")
    assert saida.endswith("0")
    # Apagar o orçamento apaga os itens junto.
    banco_novo.como(U1, "delete from orcamentos;")
    assert banco_novo.rodar("select count(*) from itens_orcamento;") == "0"


def test_migracao_atualiza_um_banco_antigo_sem_perder_dados(servidor):
    banco = Banco(servidor, "antigo")
    banco.rodar(PREPARO)
    banco.rodar(SCHEMA_ANTIGO_ORCAMENTOS)
    # Três orçamentos feitos antes da migração (dois de um técnico, um de outro).
    banco.como(U1, "insert into orcamentos (cliente_nome, total, criado_em) values "
                   "('Primeiro', 10, '2026-10-01'), ('Segundo', 20, '2026-10-02');")
    banco.como(U2, "insert into orcamentos (cliente_nome, total) values ('Do outro', 30);")

    banco.rodar(MIGRACAO)
    banco.rodar(MIGRACAO)   # rodar duas vezes não pode dar erro nem bagunçar

    numerados = banco.rodar(
        "select string_agg(cliente_nome || '=' || numero, ',' order by cliente_nome) from orcamentos;")
    assert numerados == "Do outro=1,Primeiro=1,Segundo=2"
    assert banco.rodar("select sum(total) from orcamentos;") == "60.00"
    assert banco.rodar("select count(*) from orcamentos where mao_de_obra = 0 "
                       "and condicoes_pagamento = '';") == "3"
    # Depois da migração, a numeração continua de onde parou.
    assert banco.como(U1, INSERIR.format(nome="Terceiro", total=5))[0].endswith("3")
    assert banco.como(U2, INSERIR.format(nome="Outro 2", total=5))[0].endswith("2")


# ------------------------------------------------ migração 003 (privacidade)
def test_aceite_e_gravado_com_a_hora_do_servidor(banco_novo):
    _, erro = banco_novo.como(U1, "insert into aceites (versao_politica) values ('1.0');")
    assert erro == "", erro
    saida, _ = banco_novo.como(
        U1, "select count(*) from aceites where aceito_em > now() - interval '1 minute';")
    assert saida.endswith("1")
    # Informar outra data, repetir o aceite, alterar ou apagar: tudo recusado.
    _, erro = banco_novo.como(
        U1, "insert into aceites (versao_politica, aceito_em) values ('2.0', '2020-01-01');")
    assert "row-level security" in erro
    _, erro = banco_novo.como(U1, "insert into aceites (versao_politica) values ('1.0');")
    assert "duplicate key" in erro
    banco_novo.como(U1, "update aceites set versao_politica = '9'; delete from aceites;")
    assert banco_novo.rodar("select versao_politica from aceites;") == "1.0"


def test_aceite_e_auditoria_sao_separados_por_usuario(banco_novo):
    banco_novo.como(U1, "insert into aceites (versao_politica) values ('1.0');")
    banco_novo.como(U1, "insert into auditoria (acao, quantidade) values ('exportar_conta', 3);")
    assert banco_novo.como(U2, "select count(*) from aceites;")[0].endswith("0")
    assert banco_novo.como(U2, "select count(*) from auditoria;")[0].endswith("0")
    _, erro = banco_novo.como(
        U2, f"insert into aceites (user_id, versao_politica) values ('{U1}', '1.0');")
    assert "row-level security" in erro
    _, erro = banco_novo.como(
        U2, f"insert into auditoria (user_id, acao) values ('{U1}', 'excluir_conta');")
    assert "row-level security" in erro


def test_auditoria_so_aceita_acoes_conhecidas_e_nao_pode_ser_apagada(banco_novo):
    _, erro = banco_novo.como(U1, "insert into auditoria (acao) values ('qualquer coisa');")
    assert "violates check constraint" in erro
    banco_novo.como(U1, "insert into auditoria (acao) values ('exportar_cliente');")
    banco_novo.como(U1, "delete from auditoria;")
    banco_novo.como(U1, "update auditoria set quantidade = 99;")
    assert banco_novo.rodar("select acao || '=' || quantidade from auditoria;") == "exportar_cliente=0"
    colunas = banco_novo.rodar(
        "select string_agg(column_name, ',' order by column_name) from information_schema.columns "
        "where table_name = 'auditoria';")
    assert colunas == "acao,criado_em,id,quantidade,user_id"   # nenhum campo de dado pessoal


def test_excluir_minha_conta_apaga_tudo_de_quem_chama_e_so_dele(banco_novo):
    for usuario in (U1, U2):
        banco_novo.como(usuario, INSERIR.format(nome="Cliente", total=10))
        banco_novo.como(usuario, "insert into perfis (user_id, nome_empresa) values (auth.uid(), 'E');")
        banco_novo.como(usuario, "insert into itens_catalogo (nome, tipo) values ('x', 'peca');")
        banco_novo.como(usuario, "insert into aceites (versao_politica) values ('1.0');")

    _, erro = banco_novo.como(U1, "select excluir_minha_conta();")
    assert erro == "", erro

    def contar(tabela, usuario):
        return banco_novo.rodar(f"select count(*) from {tabela} where user_id = '{usuario}';")

    for tabela in ["orcamentos", "perfis", "itens_catalogo", "aceites"]:
        assert contar(tabela, U1) == "0", tabela
        assert contar(tabela, U2) == "1", tabela
    assert banco_novo.rodar(f"select count(*) from auth.users where id = '{U1}';") == "0"
    assert banco_novo.rodar(f"select count(*) from auth.users where id = '{U2}';") == "1"
    # A auditoria da exclusão sobrevive à conta.
    assert banco_novo.rodar(f"select acao from auditoria where user_id = '{U1}';") == "excluir_conta"


def test_visitante_nao_consegue_excluir_conta(banco_novo):
    _, erro = banco_novo.como("", "select excluir_minha_conta();", papel="anon")
    assert "permission denied" in erro
    assert banco_novo.rodar("select count(*) from auth.users;") == "2"


def test_migracao_003_em_banco_que_parou_na_002(servidor):
    banco = Banco(servidor, "ate_002")
    banco.rodar(PREPARO)
    banco.rodar(SCHEMA_ANTIGO_ORCAMENTOS)
    banco.rodar(MIGRACAO)
    banco.como(U1, INSERIR.format(nome="Antes", total=10))
    banco.rodar(MIGRACAO_3)
    banco.rodar(MIGRACAO_3)   # repetir não pode dar erro
    assert banco.rodar("select count(*) from orcamentos;") == "1"   # nada se perdeu
    _, erro = banco.como(U1, "insert into aceites (versao_politica) values ('1.0');")
    assert erro == "", erro
    _, erro = banco.como(U1, "select excluir_minha_conta();")
    assert erro == "", erro
    assert banco.rodar("select count(*) from orcamentos;") == "0"


# ------------------------- migração 004: item só em orçamento do próprio dono
INSERIR_ITEM = (
    "insert into itens_orcamento (orcamento_id, nome, tipo, quantidade, custo_unitario, "
    "preco_unitario) values ('{orcamento}', '{nome}', 'peca', 1, 0, 10);"
)
# A regra ANTIGA dos itens, como estava no schema.sql até a migração 003.
REGRA_ANTIGA_DOS_ITENS = """
drop policy if exists "dono" on itens_orcamento;
create policy "dono" on itens_orcamento for all to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
"""


def _novo_orcamento(banco, usuario, nome):
    saida, erro = banco.como(
        usuario, f"insert into orcamentos (cliente_nome, total) values ('{nome}', 100) returning id;")
    assert erro == "", erro
    return saida.splitlines()[-1]


def test_tecnico_nao_liga_item_ao_orcamento_de_outro(banco_novo):
    do_u1 = _novo_orcamento(banco_novo, U1, "Do U1")
    do_u2 = _novo_orcamento(banco_novo, U2, "Do U2")

    # No próprio orçamento, continua funcionando.
    _, erro = banco_novo.como(U1, INSERIR_ITEM.format(orcamento=do_u1, nome="meu"))
    assert erro == "", erro

    # No orçamento do outro, é recusado.
    _, erro = banco_novo.como(U1, INSERIR_ITEM.format(orcamento=do_u2, nome="intruso"))
    assert "row-level security" in erro
    assert banco_novo.rodar(f"select count(*) from itens_orcamento where orcamento_id = '{do_u2}';") == "0"

    # Nem mudando depois um item próprio para apontar para o orçamento do outro.
    banco_novo.como(U1, f"update itens_orcamento set orcamento_id = '{do_u2}' where nome = 'meu';")
    assert banco_novo.rodar(f"select count(*) from itens_orcamento where orcamento_id = '{do_u1}';") == "1"
    assert banco_novo.rodar(f"select count(*) from itens_orcamento where orcamento_id = '{do_u2}';") == "0"


def test_item_continua_editavel_e_apagavel_pelo_dono(banco_novo):
    orcamento = _novo_orcamento(banco_novo, U1, "Do U1")
    banco_novo.como(U1, INSERIR_ITEM.format(orcamento=orcamento, nome="meu"))
    _, erro = banco_novo.como(U1, "update itens_orcamento set quantidade = 3 where nome = 'meu';")
    assert erro == "", erro
    assert banco_novo.rodar("select quantidade from itens_orcamento;") == "3"
    banco_novo.como(U1, "delete from itens_orcamento where nome = 'meu';")
    assert banco_novo.rodar("select count(*) from itens_orcamento;") == "0"


def test_migracao_004_fecha_a_falha_em_banco_com_a_regra_antiga(banco_novo):
    banco_novo.rodar(REGRA_ANTIGA_DOS_ITENS)
    do_u1 = _novo_orcamento(banco_novo, U1, "Do U1")
    do_u2 = _novo_orcamento(banco_novo, U2, "Do U2")
    banco_novo.como(U1, INSERIR_ITEM.format(orcamento=do_u1, nome="legitimo"))

    # Com a regra antiga, a falha existe:
    _, erro = banco_novo.como(U1, INSERIR_ITEM.format(orcamento=do_u2, nome="antes"))
    assert erro == "", "a regra antiga deveria aceitar (é a falha que a migração corrige)"

    banco_novo.rodar(MIGRACAO_4)
    banco_novo.rodar(MIGRACAO_4)      # repetir não pode dar erro

    # Depois da migração, é recusado; e nada do que existia foi apagado.
    _, erro = banco_novo.como(U1, INSERIR_ITEM.format(orcamento=do_u2, nome="depois"))
    assert "row-level security" in erro
    assert banco_novo.rodar("select count(*) from itens_orcamento;") == "2"
    assert banco_novo.rodar("select count(*) from orcamentos;") == "2"
    # O fluxo normal do aplicativo segue funcionando.
    _, erro = banco_novo.como(U1, INSERIR_ITEM.format(orcamento=do_u1, nome="normal"))
    assert erro == "", erro


# ------------------------------------------------ mensagem do WhatsApp (005)
def test_migracao_005_cria_a_coluna_sem_mexer_no_que_existe(banco_novo):
    # Banco como estava antes: sem a coluna, e com um perfil já gravado.
    banco_novo.rodar("alter table perfis drop column mensagem_whatsapp;")
    banco_novo.como(U1, "insert into perfis (user_id, nome_empresa) values (auth.uid(), 'Clima Frio');")

    banco_novo.rodar(MIGRACAO_5)
    banco_novo.rodar(MIGRACAO_5)      # repetir não pode dar erro

    assert banco_novo.rodar("select nome_empresa || '|' || mensagem_whatsapp from perfis;") == "Clima Frio|"
    # O dono grava a mensagem dele; outro técnico não a enxerga nem altera.
    _, erro = banco_novo.como(U1, "update perfis set mensagem_whatsapp = 'Oi {cliente}';")
    assert erro == "", erro
    saida, _ = banco_novo.como(U2, "select count(*) from perfis;")
    assert saida == "0"
    banco_novo.como(U2, "update perfis set mensagem_whatsapp = 'invadido';")
    assert banco_novo.rodar("select mensagem_whatsapp from perfis;") == "Oi {cliente}"


def test_mensagem_maior_que_o_limite_e_recusada_pelo_banco(banco_novo):
    banco_novo.como(U1, "insert into perfis (user_id) values (auth.uid());")
    _, erro = banco_novo.como(U1, "update perfis set mensagem_whatsapp = repeat('a', 701);")
    assert "check constraint" in erro
    _, erro = banco_novo.como(U1, "update perfis set mensagem_whatsapp = repeat('a', 700);")
    assert erro == "", erro


# ------------------------------------------------ segunda tranca (006)
TABELAS = ("perfis", "itens_catalogo", "orcamentos", "itens_orcamento", "aceites", "auditoria")
TODAS_AS_PERMISSOES = f"grant all on table {', '.join(TABELAS)} to anon, authenticated;"


def _permissoes(banco, papel, tabela):
    return set(banco.rodar(
        f"select string_agg(privilege_type, ',' order by privilege_type) from information_schema.role_table_grants "
        f"where grantee = '{papel}' and table_name = '{tabela}';").split(",")) - {""}


def test_schema_novo_ja_vem_com_a_segunda_tranca(banco_novo):
    for tabela in TABELAS:
        assert _permissoes(banco_novo, "anon", tabela) == set(), tabela
    for tabela in ("perfis", "itens_catalogo", "orcamentos", "itens_orcamento"):
        assert _permissoes(banco_novo, "authenticated", tabela) == {"SELECT", "INSERT", "UPDATE", "DELETE"}
    for tabela in ("aceites", "auditoria"):
        assert _permissoes(banco_novo, "authenticated", tabela) == {"SELECT", "INSERT"}


def test_migracao_006_tira_as_permissoes_sem_mexer_nos_dados_nem_no_uso_normal(banco_novo):
    banco_novo.rodar(TODAS_AS_PERMISSOES)          # banco como o Supabase entrega: tudo liberado
    banco_novo.como(U1, INSERIR.format(nome="Maria", total=10))
    banco_novo.como(U1, "insert into aceites (versao_politica) values ('1.0');")
    # Antes: o visitante "lê" (o RLS devolve zero linhas) e o logado poderia esvaziar a tabela inteira.
    assert banco_novo.como("", "select count(*) from orcamentos;", papel="anon")[0].endswith("0")
    assert "TRUNCATE" in _permissoes(banco_novo, "authenticated", "orcamentos")

    banco_novo.rodar(MIGRACAO_6)
    banco_novo.rodar(MIGRACAO_6)                   # repetir não pode dar erro

    for tabela in TABELAS:
        _, erro = banco_novo.como("", f"select count(*) from {tabela};", papel="anon")
        assert "permission denied" in erro, tabela
    _, erro = banco_novo.como(U2, "truncate orcamentos cascade;")
    assert "permission denied" in erro
    _, erro = banco_novo.como(U1, "delete from aceites;")
    assert "permission denied" in erro
    _, erro = banco_novo.como(U1, "update auditoria set quantidade = 1;")
    assert "permission denied" in erro
    # Nada foi apagado, e o dono continua trabalhando normalmente.
    assert banco_novo.rodar("select count(*) from orcamentos;") == "1"
    assert banco_novo.rodar("select count(*) from aceites;") == "1"
    orcamento = _novo_orcamento(banco_novo, U1, "Depois da 006")
    _, erro = banco_novo.como(U1, INSERIR_ITEM.format(orcamento=orcamento, nome="item"))
    assert erro == "", erro
    _, erro = banco_novo.como(U1, "update orcamentos set cliente_nome = 'Ana' where cliente_nome = 'Maria';")
    assert erro == "", erro
    _, erro = banco_novo.como(U1, "insert into auditoria (acao) values ('exportar_conta');")
    assert erro == "", erro
    _, erro = banco_novo.como(U1, "select excluir_minha_conta();")
    assert erro == "", erro
    assert banco_novo.rodar(f"select count(*) from auth.users where id = '{U1}';") == "0"


# ------------------------------------------------ mais tentativas de invasão entre contas
def test_ninguem_passa_um_orcamento_ou_item_para_a_conta_de_outro(banco_novo):
    do_u1 = _novo_orcamento(banco_novo, U1, "Do U1")
    do_u2 = _novo_orcamento(banco_novo, U2, "Do U2")
    banco_novo.como(U1, INSERIR_ITEM.format(orcamento=do_u1, nome="meu"))
    # "Dar" o próprio orçamento ou item a outra conta (para sujar os dados dela) é recusado...
    for sql in (f"update orcamentos set user_id = '{U2}';",
                f"update itens_orcamento set user_id = '{U2}';",
                f"update itens_catalogo set user_id = '{U2}';",
                f"update perfis set user_id = '{U2}';"):
        banco_novo.como(U1, sql)
    assert banco_novo.rodar(f"select count(*) from orcamentos where user_id = '{U2}';") == "1"
    assert banco_novo.rodar(f"select count(*) from itens_orcamento where user_id = '{U2}';") == "0"
    # ...e mover o próprio item para dentro do orçamento de outra conta também.
    _, erro = banco_novo.como(U1, f"update itens_orcamento set orcamento_id = '{do_u2}';")
    assert "row-level security" in erro
    assert banco_novo.rodar(f"select count(*) from itens_orcamento where orcamento_id = '{do_u2}';") == "0"


def test_aceite_nao_pode_ser_alterado_apagado_nem_antedatado(banco_novo):
    banco_novo.como(U1, "insert into aceites (versao_politica) values ('1.0');")
    antes = banco_novo.rodar("select aceito_em from aceites;")
    for sql in ("update aceites set aceito_em = '2000-01-01';", "delete from aceites;",
                "update aceites set versao_politica = '9.9';"):
        banco_novo.como(U1, sql)
    assert banco_novo.rodar("select versao_politica || '|' || aceito_em from aceites;") == f"1.0|{antes}"
    _, erro = banco_novo.como(
        U1, "insert into aceites (versao_politica, aceito_em) values ('2.0', '2000-01-01');")
    assert "row-level security" in erro


def test_migracao_007_fechado_so_pelo_dono(banco_novo):
    # Banco como estava antes: sem a coluna, com um orçamento já gravado.
    banco_novo.rodar("alter table orcamentos drop column fechado_em;")
    banco_novo.como(U1, "insert into orcamentos (cliente_nome, total) values ('Maria', 710);")
    banco_novo.rodar(MIGRACAO_7)
    banco_novo.rodar(MIGRACAO_7)      # repetir não pode dar erro
    assert banco_novo.rodar("select cliente_nome || '|' || coalesce(fechado_em::text, 'aberto') from orcamentos;") == "Maria|aberto"
    # O dono fecha o próprio orçamento; outro técnico não enxerga nem consegue fechar.
    _, erro = banco_novo.como(U1, "update orcamentos set fechado_em = now();")
    assert erro == "", erro
    banco_novo.como(U2, "update orcamentos set fechado_em = null;")
    assert banco_novo.rodar("select fechado_em is not null from orcamentos;") == "t"
    saida, _ = banco_novo.como(U2, "select count(*) from orcamentos where fechado_em is not null;")
    assert saida == "0"


def test_migracao_008_cor_valida_e_so_do_dono(banco_novo):
    banco_novo.rodar("alter table perfis drop column cor_orcamento;")
    banco_novo.como(U1, "insert into perfis (user_id, nome_empresa) values (auth.uid(), 'Clima Frio');")
    banco_novo.rodar(MIGRACAO_8)
    banco_novo.rodar(MIGRACAO_8)      # repetir não pode dar erro
    assert banco_novo.rodar("select nome_empresa || '|' || cor_orcamento from perfis;") == "Clima Frio|"
    _, erro = banco_novo.como(U1, "update perfis set cor_orcamento = '#B42318';")
    assert erro == "", erro
    # Formato errado é recusado pelo próprio banco.
    _, erro = banco_novo.como(U1, "update perfis set cor_orcamento = 'red; drop table perfis';")
    assert "check constraint" in erro
    # Outro técnico não muda a cor de ninguém.
    banco_novo.como(U2, "update perfis set cor_orcamento = '#000000';")
    assert banco_novo.rodar("select cor_orcamento from perfis;") == "#B42318"


def test_migracao_009_situacao_e_mantem_os_ja_fechados(banco_novo):
    banco_novo.rodar("alter table orcamentos drop column situacao;")
    banco_novo.como(U1, "insert into orcamentos (cliente_nome, total) values ('Maria', 710);")
    banco_novo.como(U1, "insert into orcamentos (cliente_nome, total, fechado_em) values ('José', 180, now());")
    banco_novo.rodar(MIGRACAO_9)
    banco_novo.rodar(MIGRACAO_9)      # repetir não pode dar erro
    assert banco_novo.rodar("select string_agg(cliente_nome || '=' || situacao, ',' order by cliente_nome) from orcamentos;") \
        == "José=fechado,Maria=aberto"
    _, erro = banco_novo.como(U1, "update orcamentos set situacao = 'pago' where cliente_nome = 'Maria';")
    assert erro == "", erro
    _, erro = banco_novo.como(U1, "update orcamentos set situacao = 'talvez';")
    assert "check constraint" in erro
    banco_novo.como(U2, "update orcamentos set situacao = 'aberto';")
    assert banco_novo.rodar("select situacao from orcamentos where cliente_nome = 'Maria';") == "pago"
