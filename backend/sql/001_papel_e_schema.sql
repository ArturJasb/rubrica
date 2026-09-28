-- Papel próprio do backend e schema "rubrica" (fora da API pública do Supabase).
-- Rode no SQL Editor do Supabase trocando a senha. A DATABASE_URL do Render fica:
-- postgresql://rubrica_api.SEU_REF:SENHA@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
create role rubrica_api with login password 'TROQUE_ESTA_SENHA';
grant rubrica_api to current_user;
create schema if not exists rubrica authorization rubrica_api;
alter role rubrica_api set search_path = rubrica;
revoke all on schema rubrica from public;
-- As tabelas são criadas pelo backend na primeira inicialização (SQLAlchemy create_all).
