-- =====================================================================
-- Migração 007: orçamento fechado (o cliente aceitou o serviço).
-- A tela Financeiro soma só os orçamentos fechados, pela data do fechamento.
-- Como usar: painel do Supabase > SQL Editor > New query > cole tudo > Run.
-- Pode rodar de novo sem problema.
-- =====================================================================

-- Vazio = ainda não fechado. Preenchido = data e hora em que foi marcado como fechado.
alter table orcamentos add column if not exists fechado_em timestamptz;

-- Deixa rápida a busca "fechados deste técnico neste período".
create index if not exists orcamentos_fechado_em on orcamentos (user_id, fechado_em);

-- Não precisa de regra nova de acesso: a regra "dono" dos orçamentos já cobre
-- ler e alterar só os próprios.
