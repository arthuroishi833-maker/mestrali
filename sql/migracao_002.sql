-- =====================================================================
-- Migração 002: acrescenta colunas novas na tabela de orçamentos.
-- Para quem JÁ rodou o schema.sql antes. (Instalação nova: rode só o
-- schema.sql, que já inclui tudo isto.)
--
-- Como usar: painel do Supabase > SQL Editor > New query > cole tudo > Run.
-- Pode rodar mais de uma vez sem problema.
-- =====================================================================

-- Mão de obra informada no fim do orçamento, somada ao total.
alter table orcamentos
  add column if not exists mao_de_obra numeric(10,2) not null default 0
  check (mao_de_obra >= 0);

-- Condições de pagamento (texto livre que aparece no PDF).
alter table orcamentos
  add column if not exists condicoes_pagamento text not null default ''
  check (char_length(condicoes_pagamento) <= 200);

-- Número do orçamento: 1, 2, 3... separado para cada técnico.
alter table orcamentos add column if not exists numero int;

-- Gatilho: ao inserir um orçamento, o próprio banco escolhe o próximo
-- número daquele técnico. O valor enviado pelo aplicativo é ignorado.
create or replace function definir_numero_orcamento() returns trigger
language plpgsql security invoker set search_path = public as $$
begin
  select coalesce(max(numero), 0) + 1 into new.numero
    from orcamentos where user_id = new.user_id;
  return new;
end $$;

drop trigger if exists numerar_orcamento on orcamentos;
create trigger numerar_orcamento before insert on orcamentos
  for each row execute function definir_numero_orcamento();

-- Numera os orçamentos que já existiam, do mais antigo para o mais novo.
with ordem as (
  select id, row_number() over (partition by user_id order by criado_em) as posicao
    from orcamentos where numero is null
)
update orcamentos o set numero = ordem.posicao from ordem where o.id = ordem.id;
