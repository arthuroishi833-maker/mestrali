-- =====================================================================
-- Migração 005: mensagem do WhatsApp escrita pelo técnico.
--
-- Cria a coluna onde fica o texto padrão que o técnico escolheu para
-- enviar aos clientes (Perfil > Mensagem do WhatsApp). Vazia = o sistema
-- usa a mensagem padrão dele.
--
-- Para quem JÁ tem as tabelas. (Instalação nova: rode só o schema.sql.)
-- Como usar: painel do Supabase > SQL Editor > New query > cole tudo > Run.
-- Pode rodar mais de uma vez. Não apaga nem altera nenhum dado.
--
-- Para desfazer (apaga as mensagens gravadas):
--   alter table perfis drop column if exists mensagem_whatsapp;
-- =====================================================================

alter table perfis
  add column if not exists mensagem_whatsapp text not null default ''
  check (char_length(mensagem_whatsapp) <= 700);
