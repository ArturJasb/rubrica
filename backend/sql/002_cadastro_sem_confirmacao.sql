-- Cadastro aberto: cria o usuário no Supabase Auth já confirmado (sem e-mail de confirmação).
-- Usado pelo endpoint POST /api/auth/signup. Só o papel do backend pode executar.
create or replace function rubrica.create_confirmed_user(p_email text, p_password text, p_name text)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_email text := lower(trim(p_email));
  v_name text := coalesce(nullif(trim(p_name), ''), split_part(lower(trim(p_email)), '@', 1));
  v_id uuid := gen_random_uuid();
begin
  if v_email is null or v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' then
    raise exception 'invalid_email' using errcode = '22023';
  end if;
  if p_password is null or length(p_password) < 6 then
    raise exception 'weak_password' using errcode = '22023';
  end if;
  if exists (select 1 from auth.users where lower(email) = v_email) then
    raise exception 'email_exists' using errcode = '23505';
  end if;

  insert into auth.users (
    instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
    confirmation_token, recovery_token, email_change_token_new, email_change
  ) values (
    '00000000-0000-0000-0000-000000000000', v_id, 'authenticated', 'authenticated', v_email,
    extensions.crypt(p_password, extensions.gen_salt('bf')), now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    jsonb_build_object('full_name', v_name, 'email_verified', true),
    now(), now(), '', '', '', ''
  );

  insert into auth.identities (user_id, provider_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
  values (
    v_id, v_id::text,
    jsonb_build_object('sub', v_id::text, 'email', v_email, 'email_verified', true, 'phone_verified', false),
    'email', now(), now(), now()
  );

  return v_id;
end;
$$;

revoke all on function rubrica.create_confirmed_user(text, text, text) from public, anon, authenticated;
grant execute on function rubrica.create_confirmed_user(text, text, text) to rubrica_api;
