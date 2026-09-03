-- ============================================================
-- Lead Prospector — Schema SQL (Supabase / Postgres)
-- ============================================================

-- Extensão para UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabela principal de leads
CREATE TABLE IF NOT EXISTS leads (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    nome            TEXT NOT NULL,
    telefone        TEXT NOT NULL UNIQUE,
    endereco        TEXT,
    nicho           TEXT NOT NULL,
    regiao          TEXT NOT NULL,
    tem_site        BOOLEAN DEFAULT FALSE,
    site_url        TEXT,
    tem_instagram   BOOLEAN DEFAULT FALSE,
    instagram_handle TEXT,
    status          TEXT DEFAULT 'novo' CHECK (status IN ('novo', 'contatado', 'convertido', 'descartado')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para filtros frequentes
CREATE INDEX IF NOT EXISTS idx_leads_nicho ON leads (nicho);
CREATE INDEX IF NOT EXISTS idx_leads_regiao ON leads (regiao);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads (created_at DESC);

-- ============================================================
-- Row Level Security (RLS)
-- Permite acesso público via anon key (necessário para o frontend)
-- Em produção, restrinja conforme necessário.
-- ============================================================

ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

-- Policy: leitura pública
CREATE POLICY "Permitir leitura pública" ON leads
    FOR SELECT USING (true);

-- Policy: inserção pública (para o scraper via service_role ou anon key)
CREATE POLICY "Permitir inserção" ON leads
    FOR INSERT WITH CHECK (true);

-- Policy: atualização pública (para mudar status no frontend)
CREATE POLICY "Permitir atualização" ON leads
    FOR UPDATE USING (true) WITH CHECK (true);

-- Policy: deleção pública
CREATE POLICY "Permitir deleção" ON leads
    FOR DELETE USING (true);
