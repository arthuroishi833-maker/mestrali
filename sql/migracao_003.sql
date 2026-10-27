-- =====================================================================
-- Migração 003: privacidade (LGPD).
--   - aceites: registro de quem aceitou qual versão da política, e quando
--   - auditoria: registro de exportações e exclusões (sem dado pessoal)
--   - excluir_minha_conta(): apaga a conta de quem chama, com tudo dentro
--
-- Para quem JÁ tem as tabelas. (Instalação nova: rode só o schema.sql.)
-- Como usar: painel do Supabase > SQL Editor > New query > cole tudo > Run.
-- Pode rodar mais de uma vez sem problema. Não apaga nem altera dados.
--
-- Para desfazer (apaga os registros de aceite e de auditoria!):
--   drop function if exists excluir_minha_conta();
--   drop table if exists auditoria;
--   drop table if exists aceites;
-- =====================================================================

-- ACEITES DA POLÍTICA DE PRIVACIDADE
create table if not exists aceites (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users(id) on delete cascade,
  versao_politica text not null check (char_length(versao_politica) between 1 and 20),
  aceito_em       timestamptz not null default now(),
  unique (user_id, versao_politica)
);
alter table aceites enable row level security;

-- Cada um lê e cria só os próprios aceites. Não há regra de alterar nem de
-- apagar: um aceite registrado não pode ser mexido pelo aplicativo.
-- "aceito_em = now()" impede o aplicativo de informar uma data diferente
-- da hora real do servidor.
drop policy if exists "ler os proprios" on aceites;
create policy "ler os proprios" on aceites for select to authenticated
  using (auth.uid() = user_id);
drop policy if exists "criar o proprio" on aceites;
create policy "criar o proprio" on aceites for insert to authenticated
  with check (auth.uid() = user_id and aceito_em = now());

-- AUDITORIA DE EXPORTAÇÕES E EXCLUSÕES
-- Guarda quem fez, o quê, quantos registros e quando. Não guarda nome,
-- telefone nem qualquer conteúdo. user_id não tem "references" de propósito:
-- o registro precisa continuar existindo depois que a conta é excluída.
create table if not exists auditoria (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid(),
  acao       text not null check (acao in (
               'exportar_conta', 'exportar_cliente', 'anonimizar_cliente',
               'excluir_cliente', 'excluir_orcamento', 'excluir_conta')),
  quantidade int  not null default 0 check (quantidade >= 0),
  criado_em  timestamptz not null default now()
);
alter table auditoria enable row level security;

drop policy if exists "ler os proprios" on auditoria;
create policy "ler os proprios" on auditoria for select to authenticated
  using (auth.uid() = user_id);
drop policy if exists "criar o proprio" on auditoria;
create policy "criar o proprio" on auditoria for insert to authenticated
  with check (auth.uid() = user_id and criado_em = now());

create index if not exists auditoria_user_id_idx on auditoria (user_id, criado_em desc);

-- EXCLUSÃO DA PRÓPRIA CONTA
-- O aplicativo usa só a chave pública, que não tem permissão para apagar
-- usuários. Esta função roda com a permissão de quem a criou ("security
-- definer"), mas só apaga a conta de QUEM CHAMA (auth.uid()); não recebe
-- nenhum parâmetro, então não há como apontá-la para outra pessoa.
-- Perfil, catálogo, orçamentos, itens e aceites somem junto (on delete cascade).
create or replace function excluir_minha_conta() returns void
language plpgsql security definer set search_path = '' as $$
declare
  quem uuid := auth.uid();
begin
  if quem is null then
    raise exception 'É preciso estar logado para excluir a conta.';
  end if;
  insert into public.auditoria (user_id, acao) values (quem, 'excluir_conta');
  delete from auth.users where id = quem;
end $$;

revoke all on function excluir_minha_conta() from public, anon;
grant execute on function excluir_minha_conta() to authenticated;
