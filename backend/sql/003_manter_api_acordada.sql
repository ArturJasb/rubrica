-- Mantém a API do Render Free acordada: o próprio Supabase visita /health a cada 10 minutos.
-- (O Render Free dorme após 15 min sem requisições; 24 h/dia consomem ~744 das 750 h grátis do mês.)
create extension if not exists pg_cron;
create extension if not exists pg_net;
select cron.schedule(
  'manter-api-rubrica-acordada',
  '*/10 * * * *',
  $$select net.http_get('https://rubrica-api-yjb4.onrender.com/health', timeout_milliseconds := 60000)$$
);
