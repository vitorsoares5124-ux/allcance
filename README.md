# Lead Prospector ⚡

Sistema de prospecção de leads e geração automática de propostas comerciais personalizadas em PDF com IA e Playwright.

## Stack

| Componente    | Tecnologia                      |
|---------------|----------------------------------|
| Scraper       | Python + Playwright (headless)   |
| Propostas     | Playwright + LLMs (Gemini / Groq / OpenAI) |
| Execução      | GitHub Actions (workflow_dispatch sob demanda) |
| Banco de dados| Supabase (Postgres + Storage)    |
| Frontend      | HTML + CSS + JS (Vercel dark style) |

## Setup

### 1. Supabase

1. Crie um projeto no [Supabase](https://supabase.com)
2. Vá em **SQL Editor** e execute o conteúdo de [`database/schema.sql`](database/schema.sql)
3. Copie a **URL** e a **anon key** do projeto (Settings → API)

### 2. GitHub

1. Faça um fork ou push deste repositório para o GitHub
2. Vá em **Settings → Secrets and variables → Actions** e adicione:
   - `SUPABASE_URL` — URL do seu projeto Supabase
   - `SUPABASE_KEY` — Anon key (ou service_role key para mais permissões)
3. Crie um [Personal Access Token (PAT)](https://github.com/settings/tokens) com permissão `repo` ou `actions:write`

### 3. Frontend

1. Abra `frontend/index.html` no navegador (ou hospede no GitHub Pages / Vercel / Netlify)
2. Clique no ⚙ no canto superior direito e configure:
   - **Supabase URL** e **Anon Key**
   - **GitHub Repo** (formato: `owner/repo`)
   - **GitHub Token** (seu PAT)

## Uso

### Buscar Leads

1. Na aba **🔍 Buscar Leads**, informe:
   - **Nicho**: ex: "cabeleireiro", "advogado", "pet shop"
   - **Região**: selecione ou digite manualmente
   - **Quantidade**: 1 a 30 leads
2. Clique **🚀 Disparar busca**
3. Um workflow do GitHub Actions será iniciado automaticamente
4. Quando finalizar, os leads aparecerão na aba **📋 Meus Leads**

### Gerenciar Leads

- Filtre por nicho, região ou status
- Clique **💬 WhatsApp** para abrir conversa direta
- Mude o status: Novo → Contatado → Convertido / Descartado

## Estrutura do Projeto

```
lead-prospector/
├── .github/workflows/
│   └── scraper.yml          # Workflow do GitHub Actions
├── scraper/
│   ├── scraper.py           # Script principal (Playwright)
│   └── requirements.txt     # Dependências Python
├── database/
│   └── schema.sql           # Schema SQL para Supabase
├── frontend/
│   └── index.html           # Painel web (single-file)
└── README.md
```

## Execução Manual do Scraper (local)

```bash
cd scraper
pip install -r requirements.txt
playwright install chromium

export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_KEY="eyJ..."

python scraper.py --nicho "cabeleireiro" --regiao "São Paulo, SP" --quantidade 10
```

## Decisões Técnicas

- **Python + Playwright**: escolhido pela excelente API async, suporte nativo a stealth mode, e SDK Supabase maduro em Python.
- **Frontend vanilla (sem framework)**: zero build step, deployável em qualquer lugar. O Supabase JS CDN elimina a necessidade de backend.
- **Upsert por telefone**: evita duplicatas naturalmente. O telefone é o identificador único mais confiável para leads brasileiros.
- **GitHub Actions em repo público**: zero custo para minutos de CI/CD. O `workflow_dispatch` permite trigger via API com parâmetros dinâmicos.
- **Delays aleatórios**: cada ação do scraper tem um delay randômico entre 1.5-6s para simular comportamento humano e evitar detecção.
- **Instagram check em página separada**: usa uma segunda aba do navegador para buscar Instagram sem perder o contexto do Google Maps.

## Limites e Considerações

- Google Maps pode bloquear scraping intensivo. Use quantidades moderadas (≤ 15 por execução).
- O scraper depende de seletores do DOM do Google Maps, que podem mudar. Se parar de funcionar, verifique os seletores em `scraper.py`.
- Para produção, considere usar a service_role key do Supabase nos secrets do GitHub Actions.
