# Guia de publicação: Rubrica no ar em ~1 hora (custo zero)

Ordem: **Supabase → Groq → Recall.ai → GitHub → Render (API) → Render (site estático) → ajustes finais → usuário de teste → teste pós-soneca.**
Anote cada chave num bloco de notas **local** (nunca no repositório).

---

## 1. Supabase: banco e login (10 min)

1. Crie uma conta em https://supabase.com e clique em **New project**.
   - Nome: `rubrica` · **Region: South America (São Paulo)** · crie e **guarde a senha do banco**.
2. **Project Settings → API**: copie a **Project URL** (`SUPABASE_URL`) e a **anon public key** (`SUPABASE_ANON_KEY`).
   Se aparecer "Publishable key" em vez de "anon", use a publishable. As duas funcionam.
3. No **SQL Editor**, rode os scripts de `backend/sql/` na ordem (troque a senha no `001`):
   - `001_papel_e_schema.sql`: cria o papel `rubrica_api` e o schema `rubrica` (fora da API pública).
   - `002_cadastro_sem_confirmacao.sql`: cadastro aberto, sem e-mail de confirmação.
   - `003_manter_api_acordada.sql`: rode depois do passo 5, com a URL real da API.
4. O `DATABASE_URL` usa o **Session pooler** com o papel próprio:
   `postgresql://rubrica_api.SEU_REF:SENHA@aws-0-sa-east-1.pooler.supabase.com:5432/postgres`
   ⚠️ Use o **pooler**, não a "Direct connection": o Render não acessa IPv6 e a conexão direta falha.

## 2. Groq: IA grátis (3 min)

1. Entre em https://console.groq.com, vá em **API Keys → Create API Key** e copie (`LLM_API_KEY`).

## 3. Recall.ai: bot da reunião (5 min)

1. Crie uma conta em https://www.recall.ai (plano Pay As You Go; **as 5 primeiras horas de gravação são grátis**).
2. Veja a URL do dashboard, por exemplo `us-west-2.recall.ai`. A primeira parte é a sua região (`RECALL_REGION=us-west-2`).
3. Em **API Keys**, crie uma chave (`RECALL_API_KEY`).
4. O webhook fica para o passo 7, quando já existir a URL do Render.

## 4. GitHub (5 min)

```bash
cd rubrica
git init
git add .
git commit -m "..."        # veja a seção "Commits distribuídos" no fim deste guia
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/rubrica.git
git push -u origin main
```

Antes do push, confira que **nenhum `.env` aparece** em `git status`.

## 5. Render: backend (10 min)

1. Em https://render.com, faça login com o GitHub e vá em **New → Blueprint**. Escolha o repositório: o `render.yaml` já configura tudo.
2. Preencha as variáveis que ele pedir:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | URI do Session pooler com o papel `rubrica_api` (passo 1.4) |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | passo 1.2 |
| `CORS_ORIGINS` | por enquanto `http://localhost:3000`; no passo 7 você troca pela URL do site |
| `RECALL_API_KEY` / `RECALL_REGION` | passo 3 |
| `LLM_API_KEY` | passo 2 |

3. Espere o deploy e abra `https://rubrica-api.onrender.com/health` (o nome pode variar). Deve aparecer `{"status":"ok"}`.
4. Em **Environment**, copie o valor gerado de `WEBHOOK_TOKEN`.

Se o blueprint der problema: **New → Web Service**, Root Directory `backend`, Build `pip install -r requirements.txt`, Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, plano Free. Depois adicione as variáveis do `backend/.env.example`.

## 6. Render: site estático (5 min)

O frontend é exportado como arquivos estáticos (`output: "export"` no `next.config.ts`), então roda como **Static Site**, que é servido por CDN e **não dorme**.

1. No Render, **New → Static Site** e escolha o repositório.
2. Build Command: `cd frontend && npm ci && npm run build` · Publish Directory: `frontend/out`.
3. Variáveis de ambiente:
   - `NODE_VERSION=22`
   - `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_ANON_KEY`: passo 1.2
   - `NEXT_PUBLIC_API_URL`: URL da API no Render, sem barra no final
4. Copie a URL (em produção: `https://rubrica-site.onrender.com`).

Também funciona na Vercel (Root Directory `frontend`), se preferir.

## 7. Ajustes finais (5 min)

1. **Render → Environment** da API: `CORS_ORIGINS=https://rubrica-site.onrender.com`. Salve (o serviço reinicia sozinho).
2. **Supabase → Authentication → URL Configuration**: em **Site URL**, coloque a URL do site.
3. **Recall.ai → Webhooks → Add Endpoint**:
   - URL: `https://rubrica-api.onrender.com/api/webhooks/recall?token=SEU_WEBHOOK_TOKEN`
   - Eventos: marque os de status do bot (`bot.*`, principalmente `bot.done` e `bot.fatal`).
   Mesmo sem webhook o fluxo funciona, porque a página consulta o status sozinha, mas com ele a rubrica sai mais rápido.

## 8. Usuário de teste (2 min)

No seu computador:

```bash
cd backend
pip install httpx
python scripts/criar_usuario_teste.py --supabase-url https://SEU_REF.supabase.co --anon-key SUA_ANON_KEY --api-url https://rubrica-api.onrender.com
```

Isso cria `avaliador@rubrica.app` / `Rubrica@2026` com uma entrevista de exemplo já processada.

## 9. Teste de ponta a ponta em produção (15 min)

1. Abra a URL do site numa **janela anônima** → Criar conta → Nova entrevista → Colar transcrição → exemplo → Gerar rubrica.
2. **Teste do bot:** crie uma reunião no Google Meet (meet.new) e cole o link em "Enviar bot para a reunião". Em 1–2 min o bot pede para entrar: **admita-o**. Confira a imagem "GRAVANDO" e a mensagem no chat. Converse 2–3 minutos em português (um faz o recrutador, outro o candidato) e encerre a chamada. Em poucos minutos a rubrica aparece.
3. Tire **prints das telas em produção** para o relatório.
4. **Teste pós-soneca:** espere 20 min sem usar, abra de novo e confirme que tudo volta depois do carregamento inicial.
5. A API fica acordada pelo `003_manter_api_acordada.sql` (Supabase chama `/health` a cada 10 min). Alternativa: um job gratuito no https://cron-job.org.

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| Tela diz "Não foi possível conectar ao servidor" | `NEXT_PUBLIC_API_URL` errado, ou `CORS_ORIGINS` sem a URL do site |
| "Sessão inválida" logo após o login | `SUPABASE_URL`/`SUPABASE_ANON_KEY` do backend diferentes dos do frontend |
| Deploy do Render falha ao conectar no banco | Usou a "Direct connection"; troque pela URI do **Session pooler** |
| Cadastro diz "confirme seu e-mail" | A função do `002_cadastro_sem_confirmacao.sql` não foi criada (o site cai no cadastro padrão do Supabase) |
| Rubrica com "Falha ao gerar a rubrica" | `LLM_API_KEY` inválida ou limite da Groq; use "Gerar de novo" ou troque para o Gemini |
| Bot não entra | Ninguém o admitiu na sala de espera, ou a reunião exige conta da organização |

## Commits distribuídos (critério de avaliação)

O professor avalia commits **ao longo da sprint e entre os dois integrantes**. Não subam tudo num commit só. Sugestão de divisão, com **cada um commitando da própria máquina e conta do GitHub** (adicione o Luigi como colaborador do repo):

- **Artur (backend):** `backend/app/models.py` e `db.py` → `auth.py` e `routers/team.py` → `services/recall.py` e `pipeline.py` → testes.
- **Luigi (frontend):** `lib/` e `components/` → páginas de login/cadastro → painel e busca → nova entrevista e detalhe → página de time.
- **Juntos:** `render.yaml`, README e relatório.

Cada um deve entender e saber explicar o próprio trecho: o enunciado prevê arguição.
