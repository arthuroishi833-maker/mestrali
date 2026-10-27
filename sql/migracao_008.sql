-- =====================================================================
-- Migração 008: cor do orçamento (a cor de destaque do PDF, escolhida no Perfil).
-- Como usar: painel do Supabase > SQL Editor > New query > cole tudo > Run.
-- Pode rodar de novo sem problema.
-- =====================================================================

-- Vazio = a cor padrão (azul). Senão, uma cor no formato #RRGGBB.
alter table perfis add column if not exists cor_orcamento text not null default '';

-- O banco também confere o formato (o aplicativo já confere antes de gravar).
alter table perfis drop constraint if exists perfis_cor_orcamento_formato;
alter table perfis add constraint perfis_cor_orcamento_formato
  check (cor_orcamento = '' or cor_orcamento ~ '^#[0-9A-Fa-f]{6}$');

-- Não precisa de regra nova de acesso: a regra "dono" dos perfis já cobre.
