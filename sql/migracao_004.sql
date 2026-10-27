-- =====================================================================
-- Migração 004: um item só pode ser ligado a um orçamento do PRÓPRIO técnico.
--
-- O problema: a regra antiga conferia apenas se o item pertencia a quem o
-- gravava. Um técnico que descobrisse o identificador de um orçamento alheio
-- conseguia pendurar itens nele. O dono do orçamento nunca via esses itens
-- (a regra de leitura o protege) e nada do que é dele era alterado, mas o
-- banco ficava com registros cruzados entre contas.
--
-- A correção: além de pertencer a quem grava, o item precisa apontar para
-- um orçamento que também é de quem grava.
--
-- Para quem JÁ tem as tabelas. (Instalação nova: rode só o schema.sql.)
-- Como usar: painel do Supabase > SQL Editor > New query > cole tudo > Run.
-- Pode rodar mais de uma vez. Não apaga nem altera nenhum dado.
--
-- Para desfazer:
--   drop policy if exists "dono" on itens_orcamento;
--   create policy "dono" on itens_orcamento for all to authenticated
--     using (auth.uid() = user_id) with check (auth.uid() = user_id);
-- =====================================================================

begin;

drop policy if exists "dono" on itens_orcamento;
create policy "dono" on itens_orcamento for all to authenticated
  using (auth.uid() = user_id)
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from orcamentos o
       where o.id = itens_orcamento.orcamento_id and o.user_id = auth.uid()
    )
  );

commit;

-- Conferência opcional: quantos itens estão ligados a orçamento de outra conta.
-- O esperado é 0. Se der mais que zero, não apague nada: avise antes.
--   select count(*) from itens_orcamento i
--     join orcamentos o on o.id = i.orcamento_id
--    where o.user_id <> i.user_id;
