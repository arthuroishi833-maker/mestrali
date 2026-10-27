-- =====================================================================
-- Migração 006 (opcional, recomendada): tirar permissões que o
-- aplicativo não usa.
--
-- Hoje quem protege os dados é o Row Level Security (RLS): cada conta só
-- alcança as próprias linhas, e um visitante sem login não alcança nenhuma.
-- Isso continua valendo. Esta migração acrescenta uma segunda tranca, para
-- o caso de uma regra de RLS ser alterada por engano no futuro:
--
--   1. O visitante sem login ("anon") perde TODA permissão nas tabelas.
--      O aplicativo só consulta o banco depois do login.
--   2. O usuário logado fica só com ler, criar, alterar e apagar LINHAS
--      (o RLS decide quais). Perde as permissões de estrutura: esvaziar a
--      tabela inteira, criar gatilho e criar referência.
--   3. Nos aceites e na auditoria, o usuário logado perde também alterar e
--      apagar: esses registros já não podiam ser mexidos (não há regra de
--      RLS para isso); agora nem a permissão existe.
--
-- Para quem JÁ tem as tabelas. (Instalação nova: rode só o schema.sql.)
-- Como usar: painel do Supabase > SQL Editor > New query > cole tudo > Run.
-- Pode rodar mais de uma vez. Não apaga nem altera nenhum dado.
-- Nada muda para quem usa o aplicativo.
--
-- Para desfazer:
--   grant all on table perfis, itens_catalogo, orcamentos, itens_orcamento,
--     aceites, auditoria to anon, authenticated;
-- =====================================================================

begin;

revoke all on table perfis, itens_catalogo, orcamentos, itens_orcamento,
  aceites, auditoria from anon;

revoke truncate, references, trigger on table perfis, itens_catalogo,
  orcamentos, itens_orcamento, aceites, auditoria from authenticated;

revoke update, delete on table aceites, auditoria from authenticated;

commit;
