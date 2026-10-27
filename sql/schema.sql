-- =====================================================================
-- Banco de dados do sistema de orçamentos.
-- Como usar: painel do Supabase > SQL Editor > New query > cole tudo > Run.
-- Rode uma única vez, em um projeto novo.
-- =====================================================================

-- PERFIL DA EMPRESA (1 linha por técnico)
create table perfis (
  user_id       uuid primary key references auth.users(id) on delete cascade,
  nome_empresa  text not null default '' check (char_length(nome_empresa) <= 80),
  telefone      text not null default '' check (char_length(telefone) <= 20),
  logo_base64   text check (char_length(logo_base64) <= 400000),  -- ~300 KB de imagem
  validade_dias int  not null default 7 check (validade_dias between 1 and 90),
  -- Texto do WhatsApp escrito pelo técnico. Vazio = mensagem padrão do sistema.
  mensagem_whatsapp text not null default '' check (char_length(mensagem_whatsapp) <= 700),
  -- Cor de destaque do PDF (#RRGGBB). Vazio = azul padrão.
  cor_orcamento text not null default ''
    constraint perfis_cor_orcamento_formato check (cor_orcamento = '' or cor_orcamento ~ '^#[0-9A-Fa-f]{6}$'),
  criado_em     timestamptz not null default now()
);

-- CATÁLOGO DE ITENS (mão de obra e peças)
create table itens_catalogo (
  id        uuid primary key default gen_random_uuid(),
  user_id   uuid not null default auth.uid() references auth.users(id) on delete cascade,
  nome      text not null check (char_length(nome) between 1 and 80),
  tipo      text not null check (tipo in ('mao_de_obra', 'peca')),
  custo     numeric(10,2) not null default 0 check (custo >= 0),
  preco     numeric(10,2) not null default 0 check (preco >= 0),
  criado_em timestamptz not null default now()
);

-- ORÇAMENTOS
create table orcamentos (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null default auth.uid() references auth.users(id) on delete cascade,
  numero           int,  -- 1, 2, 3... por técnico; preenchido pelo gatilho abaixo
  cliente_nome     text not null check (char_length(cliente_nome) between 1 and 80),
  cliente_telefone text not null default '' check (char_length(cliente_telefone) <= 20),
  equipamento      text not null default '' check (char_length(equipamento) <= 80),
  mao_de_obra      numeric(10,2) not null default 0 check (mao_de_obra >= 0),  -- somada ao total
  desconto_tipo    text not null default 'valor' check (desconto_tipo in ('valor', 'percentual')),
  desconto_valor   numeric(10,2) not null default 0 check (desconto_valor >= 0),
  condicoes_pagamento text not null default '' check (char_length(condicoes_pagamento) <= 200),
  observacoes      text not null default '' check (char_length(observacoes) <= 500),
  validade_dias    int  not null default 7 check (validade_dias between 1 and 90),
  total            numeric(10,2) not null default 0 check (total >= 0),  -- usado na lista
  criado_em        timestamptz not null default now(),
  fechado_em       timestamptz,  -- quando saiu de "não fechado" (a tela Financeiro usa esta data)
  -- 'aberto' = não fechado; 'fechado' = aceito, ainda não pago; 'pago' = feito e pago.
  situacao         text not null default 'aberto'
    constraint orcamentos_situacao_valida check (situacao in ('aberto', 'fechado', 'pago'))
);

-- Gatilho: ao inserir um orçamento, o próprio banco escolhe o próximo
-- número daquele técnico. O valor enviado pelo aplicativo é ignorado.
create or replace function definir_numero_orcamento() returns trigger
language plpgsql security invoker set search_path = public as $$
begin
  select coalesce(max(numero), 0) + 1 into new.numero
    from orcamentos where user_id = new.user_id;
  return new;
end $$;

create trigger numerar_orcamento before insert on orcamentos
  for each row execute function definir_numero_orcamento();

-- ITENS DE CADA ORÇAMENTO
-- Guardam uma CÓPIA de nome, custo e preço: editar o catálogo depois
-- não altera orçamentos já feitos.
create table itens_orcamento (
  id             uuid primary key default gen_random_uuid(),
  orcamento_id   uuid not null references orcamentos(id) on delete cascade,
  user_id        uuid not null default auth.uid() references auth.users(id) on delete cascade,
  nome           text not null check (char_length(nome) between 1 and 80),
  tipo           text not null check (tipo in ('mao_de_obra', 'peca')),
  quantidade     int  not null check (quantidade between 1 and 999),
  custo_unitario numeric(10,2) not null check (custo_unitario >= 0),
  preco_unitario numeric(10,2) not null check (preco_unitario >= 0)
);

-- ---------------------------------------------------------------------
-- ROW LEVEL SECURITY
-- Com o RLS ligado, o banco recusa tudo que não tiver uma regra (policy).
-- A regra abaixo diz: só mexe na linha quem é o dono dela (user_id).
-- ---------------------------------------------------------------------
alter table perfis          enable row level security;
alter table itens_catalogo  enable row level security;
alter table orcamentos      enable row level security;
alter table itens_orcamento enable row level security;

create policy "dono" on perfis          for all to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "dono" on itens_catalogo  for all to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "dono" on orcamentos      for all to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
-- Um item precisa ser de quem o grava E apontar para um orçamento que
-- também é de quem o grava (senão daria para pendurar itens em orçamento alheio).
create policy "dono" on itens_orcamento for all to authenticated
  using (auth.uid() = user_id)
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from orcamentos o
       where o.id = itens_orcamento.orcamento_id and o.user_id = auth.uid()
    )
  );

-- Índices: deixam as consultas mais rápidas
create index if not exists orcamentos_fechado_em on orcamentos (user_id, fechado_em);
create index on itens_catalogo (user_id);
create index on orcamentos (user_id, criado_em desc);
create index on itens_orcamento (orcamento_id);

-- ---------------------------------------------------------------------
-- PRIVACIDADE (LGPD): aceites, auditoria e exclusão da própria conta
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- SEGUNDA TRANCA: tirar permissões que o aplicativo não usa
-- O Supabase dá permissão total nas tabelas ao visitante ("anon") e ao
-- usuário logado ("authenticated"); quem barra o acesso é o RLS, acima.
-- Aqui ficam só as permissões realmente usadas (veja sql/migracao_006.sql).
-- ---------------------------------------------------------------------
revoke all on table perfis, itens_catalogo, orcamentos, itens_orcamento,
  aceites, auditoria from anon;
revoke truncate, references, trigger on table perfis, itens_catalogo,
  orcamentos, itens_orcamento, aceites, auditoria from authenticated;
revoke update, delete on table aceites, auditoria from authenticated;
