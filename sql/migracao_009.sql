-- =====================================================================
-- Migração 009: situação do orçamento (não fechado, fechado ou pago).
-- Precisa da 007 antes. Como usar: SQL Editor > New query > cole > Run.
-- Pode rodar de novo sem problema.
-- =====================================================================

-- 'aberto' = não fechado; 'fechado' = aceito, ainda não pago; 'pago' = feito e pago.
alter table orcamentos add column if not exists situacao text not null default 'aberto';
alter table orcamentos drop constraint if exists orcamentos_situacao_valida;
alter table orcamentos add constraint orcamentos_situacao_valida
  check (situacao in ('aberto', 'fechado', 'pago'));

-- Quem já tinha sido marcado como fechado (migração 007) continua fechado.
update orcamentos set situacao = 'fechado' where fechado_em is not null and situacao = 'aberto';
