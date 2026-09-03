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
    proposta_pdf_url TEXT,
    proposta_status  TEXT DEFAULT 'nao_gerada',
    diagnostico_json JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Adiciona novas colunas caso a tabela já exista
ALTER TABLE leads ADD COLUMN IF NOT EXISTS proposta_pdf_url TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS proposta_status TEXT DEFAULT 'nao_gerada';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS diagnostico_json JSONB;

-- Índices para filtros frequentes
CREATE INDEX IF NOT EXISTS idx_leads_nicho ON leads (nicho);
CREATE INDEX IF NOT EXISTS idx_leads_regiao ON leads (regiao);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads (created_at DESC);

-- ============================================================
-- Row Level Security (RLS)
-- ============================================================

ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir leitura pública' AND tablename = 'leads') THEN
        CREATE POLICY "Permitir leitura pública" ON leads FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir inserção' AND tablename = 'leads') THEN
        CREATE POLICY "Permitir inserção" ON leads FOR INSERT WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir atualização' AND tablename = 'leads') THEN
        CREATE POLICY "Permitir atualização" ON leads FOR UPDATE USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir deleção' AND tablename = 'leads') THEN
        CREATE POLICY "Permitir deleção" ON leads FOR DELETE USING (true);
    END IF;
END $$;

-- ============================================================
-- Storage Bucket: propostas
-- ============================================================

INSERT INTO storage.buckets (id, name, public) 
VALUES ('propostas', 'propostas', true)
ON CONFLICT (id) DO NOTHING;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir upload público no bucket propostas' AND tablename = 'objects') THEN
        CREATE POLICY "Permitir upload público no bucket propostas" ON storage.objects
            FOR INSERT WITH CHECK (bucket_id = 'propostas');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir leitura pública no bucket propostas' AND tablename = 'objects') THEN
        CREATE POLICY "Permitir leitura pública no bucket propostas" ON storage.objects
            FOR SELECT USING (bucket_id = 'propostas');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir atualização pública no bucket propostas' AND tablename = 'objects') THEN
        CREATE POLICY "Permitir atualização pública no bucket propostas" ON storage.objects
            FOR UPDATE USING (bucket_id = 'propostas');
    END IF;
END $$;
