#!/usr/bin/env python3
"""
Lead Prospector — Gerador de Proposta Comercial Redesenhada (Vertical, PAS, Antes/Depois Empilhado)
Pipeline completo sob demanda:
1. Captura da Situação Atual ("Antes")
2. Geração do Mockup Otimizado ("Depois")
3. Diagnóstico Estruturado PAS (Problema -> Agitação -> Consequência de Perda)
4. Renderização em PDF A4 Vertical e Upload para Supabase Storage
"""

import asyncio
import os
import re
import sys
import json
import base64
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from playwright.async_api import async_playwright

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None

# ============================================================
# Configurações e Chaves de API
# ============================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')


# ============================================================
# Utilitários de Chamada de IA
# ============================================================

def call_llm(prompt: str, system_prompt: str = "", model_tier: str = "flash") -> str:
    """Chama a IA disponível com resiliência e fallback."""
    if GEMINI_API_KEY:
        models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro"] if model_tier == "flash" else ["gemini-1.5-pro", "gemini-1.5-flash"]
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            contents = []
            if system_prompt:
                contents.append({"role": "user", "parts": [{"text": f"INSTRUÇÃO DO SISTEMA:\n{system_prompt}\n\nREQUISIÇÃO:\n{prompt}"}]})
            else:
                contents.append({"role": "user", "parts": [{"text": prompt}]})

            body = json.dumps({"contents": contents}).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    candidates = data.get('candidates', [])
                    if candidates:
                        parts = candidates[0].get('content', {}).get('parts', [])
                        if parts:
                            return parts[0].get('text', '').strip()
            except Exception as e:
                print(f"  [IA Info] Tentativa no Gemini ({model}) retornou: {e}. Tentando próximo...")

    if GROQ_API_KEY:
        url = "https://api.groq.com/openai/v1/chat/completions"
        model = "llama-3.3-70b-versatile" if model_tier == "pro" else "llama-3.1-8b-instant"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({"model": model, "messages": messages, "temperature": 0.2}).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GROQ_API_KEY}'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"  [IA Warning] Erro no Groq: {e}")

    if OPENAI_API_KEY:
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o" if model_tier == "pro" else "gpt-4o-mini"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({"model": model, "messages": messages, "temperature": 0.3}).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_API_KEY}'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"  [IA Warning] Erro na OpenAI: {e}")

    # Fallback estruturado com estrutura PAS
    return json.dumps({
        "situacao_atual_resumo": "Presença online dependente de canais de terceiros ou com baixa taxa de conversão no mobile, gerando perda silenciosa de potenciais clientes qualificados.",
        "score_presenca": 4.5,
        "problemas_pas": [
            {
                "problema": "Ausência de chamada de ação direta (CTA) para WhatsApp na primeira dobra",
                "agitacao": "O visitante entra no site interessado, não encontra um meio direto de tirar dúvidas no celular e fecha a aba.",
                "perda_ativa": "Cada dia sem um canal direto é cliente qualificado que vai buscar e contratar o concorrente no Google."
            },
            {
                "problema": "Hierarquia visual confusa e falta de prova social relevante",
                "agitacao": "Sem depoimentos e fotos reais bem posicionadas, o cliente indeciso fica inseguro sobre a qualidade do serviço.",
                "perda_ativa": "Perda de orçamentos de alto valor por falta de transmissão de autoridade imediata."
            },
            {
                "problema": "Tempo de carregamento e navegabilidade não otimizados para smartphones",
                "agitacao": "Mais de 80% das buscas locais ocorrem pelo celular; lentidão gera abandono em menos de 4 segundos.",
                "perda_ativa": "Desperdício do tráfego orgânico gerado pelas buscas da sua região."
            }
        ],
        "solucao_proposta": "Desenvolver uma nova landing page mobile-first de alta conversão, com integração direta ao WhatsApp, carregamento instantâneo e design focado em transformar visitantes em clientes pagantes."
    }, ensure_ascii=False, indent=2)


# ============================================================
# Captura de Tela do Site Original ("Antes")
# ============================================================

async def capture_original_site(page, site_url: str) -> Tuple[bytes, str]:
    """Abre o site do lead, extrai textos e tira screenshot da visão principal."""
    if not site_url.startswith('http'):
        site_url = 'https://' + site_url

    print(f"📸 Capturando site original: {site_url}")
    await page.set_viewport_size({"width": 1280, "height": 800})
    await page.goto(site_url, timeout=30000, wait_until='domcontentloaded')
    await page.wait_for_timeout(2000)

    # Scroll suave inicial
    try:
        await page.evaluate('''async () => {
            window.scrollBy(0, 400);
            await new Promise(r => setTimeout(r, 600));
            window.scrollTo(0, 0);
        }''')
    except Exception:
        pass

    screenshot_bytes = await page.screenshot(type='png')

    extracted_text = await page.evaluate('''() => {
        const title = document.title || '';
        const meta = document.querySelector('meta[name="description"]')?.content || '';
        const text = document.body.innerText.substring(0, 8000);
        return `Título: ${title}\\nDescrição: ${meta}\\n\\nConteúdo:\\n${text}`;
    }''')

    return screenshot_bytes, extracted_text


# ============================================================
# Geração do Mockup "Depois" (Alta Conversão)
# ============================================================

async def generate_mockup_screenshot(page, lead: Dict[str, Any], diagnostico: Dict[str, Any]) -> bytes:
    """Gera o HTML do novo padrão otimizado e captura o screenshot."""
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Serviços Especializados')
    regiao = lead.get('regiao', 'Brasil')

    mockup_prompt = f"""Gere o código HTML + CSS inline completo de uma landing page moderna, minimalista e premium para a empresa '{nome}' ({nicho} em {regiao}).
A landing page deve ter:
- Fundo dark sofisticado (estilo Linear/Vercel: #09090b e cards #121216 com bordas sutis)
- Tipografia limpa, hierarquia perfeita
- Headline de alto impacto corrigindo as falhas do site antigo
- Badge de confiança e prova social
- Botão CTA em destaque: 'Falar com Especialista no WhatsApp'
- Grid de 3 diferenciais do negócio

Retorne APENAS o código HTML puro dentro de <html><body>...</body></html> sem crases ou markdown."""

    html_code = call_llm(mockup_prompt, model_tier="flash")
    if "<html>" not in html_code:
        # Fallback de mockup moderno de alta fidelidade
        html_code = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }}
  body {{ background: #070709; color: #f4f4f6; padding: 48px 36px; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  .nav {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 44px; padding-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.08); }}
  .brand-logo {{ font-size: 18px; font-weight: 800; color: #ffffff; }}
  .badge-tag {{ background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.35); color: #c4b5fd; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 9999px; text-transform: uppercase; }}
  .hero {{ text-align: center; margin-bottom: 40px; }}
  .hero h1 {{ font-size: 34px; font-weight: 800; line-height: 1.2; margin-bottom: 14px; background: linear-gradient(135deg, #ffffff 0%, #a1a1aa 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .hero p {{ font-size: 15px; color: #9ca3af; max-width: 640px; margin: 0 auto 24px auto; line-height: 1.5; }}
  .cta-btn {{ display: inline-flex; align-items: center; gap: 8px; background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); color: #ffffff; padding: 14px 28px; border-radius: 10px; font-weight: 700; font-size: 14px; text-decoration: none; box-shadow: 0 4px 16px rgba(139, 92, 246, 0.4); }}
  .features-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-top: 36px; }}
  .feat-card {{ background: #0f0f14; border: 1px solid rgba(255,255,255,0.08); padding: 18px; border-radius: 12px; }}
  .feat-card h4 {{ font-size: 14px; color: #ffffff; font-weight: 700; margin-bottom: 6px; }}
  .feat-card p {{ font-size: 12px; color: #71717a; }}
</style>
</head>
<body>
<div class="container">
  <div class="nav">
    <div class="brand-logo">{nome}</div>
    <span class="badge-tag">Atendimento Imediato</span>
  </div>
  <div class="hero">
    <span class="badge-tag" style="margin-bottom: 12px; display: inline-block;">Excelência & Atendimento Exclusivo</span>
    <h1>Soluções de Alto Padrão em {nicho}</h1>
    <p>Agilidade, experiência comprovada e resultados superiores para clientes exigentes em {regiao}.</p>
    <a href="#" class="cta-btn">💬 Falar com Especialista no WhatsApp</a>
  </div>
  <div class="features-grid">
    <div class="feat-card">
      <h4>⚡ Agilidade</h4>
      <p>Atendimento sem burocracia e retorno rápido.</p>
    </div>
    <div class="feat-card">
      <h4>⭐ Autoridade</h4>
      <p>Metodologia validada e foco em satisfação.</p>
    </div>
    <div class="feat-card">
      <h4>🔒 Segurança</h4>
      <p>Profissionais qualificados e estrutura moderna.</p>
    </div>
  </div>
</div>
</body>
</html>"""

    await page.set_viewport_size({"width": 1200, "height": 720})
    await page.set_content(html_code, wait_until='load')
    await page.wait_for_timeout(800)
    return await page.screenshot(type='png')


# ============================================================
# Análise Estruturada PAS via IA
# ============================================================

def analyze_site_pas(lead: Dict[str, Any], extracted_text: str) -> Dict[str, Any]:
    """Gera o diagnóstico cirúrgico na estrutura PAS (Problema -> Agitação -> Consequência de Perda)."""
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')

    if not lead.get('tem_site') or not extracted_text:
        return {
            "situacao_atual_resumo": f"A {nome} depende atualmente apenas de listagens externas no Google Maps, sem uma página própria que transmita autoridade e converta visitantes em clientes pagantes.",
            "score_presenca": 3.8,
            "problemas_pas": [
                {
                    "problema": "Inexistência de página própria (landing page) no ambiente digital",
                    "agitacao": "O potencial cliente pesquisa pelo seu serviço no Google, não encontra um site oficial com seus diferenciais e prefere opções que passam maior segurança.",
                    "perda_ativa": "Mais de 70% dos clientes pesquisam antes de contratar; sem site, a decisão de compra é direcionada diretamente para os seus concorrentes."
                },
                {
                    "problema": "Falta de catálogo estruturado de serviços e benefícios",
                    "agitacao": "A equipe perde tempo respondendo dúvidas básicas repetidamente por mensagem ou telefone, com baixa taxa de conversão.",
                    "perda_ativa": "Perda de clientes indecisos que desistem por não entenderem o valor do seu atendimento de forma rápida."
                },
                {
                    "problema": "Sem canal otimizado de captação e agendamento 24 horas",
                    "agitacao": "Visitantes que buscam serviços à noite ou nos fins de semana não encontram um meio direto e convidativo de solicitar atendimento.",
                    "perda_ativa": "Perda contínua de novos orçamentos fora do horário de expediente comercial."
                }
            ],
            "solucao_proposta": "Implementar uma landing page de alta conversão integrada diretamente ao seu WhatsApp para captar clientes todos os dias com máxima previsibilidade."
        }

    prompt = f"""Você é um auditor sênior de presença digital e conversão para negócios locais.
Sua missão é analisar o site da empresa '{nome}' ({nicho}) e gerar um diagnóstico consultivo, cirúrgico e com tom profissional na estrutura PAS (Problema → Agitação → Consequência de Perda Real).

Analise o conteúdo do site e retorne APENAS um JSON válido no seguinte formato:
{{
  "situacao_atual_resumo": "Uma ou duas frases diretas resumindo a situação atual do site e os principais gargalos de captação.",
  "score_presenca": number (entre 3.0 e 6.5, com 1 casa decimal),
  "problemas_pas": [
    {{
      "problema": "Problema específico 1 (ex: Ausência de botão flutuante de WhatsApp e CTA imediato)",
      "agitacao": "Agitação curta e real (ex: O visitante entra no site pelo celular, não encontra um meio direto de contato e fecha a aba).",
      "perda_ativa": "Consequência real no negócio (ex: Cada dia sem essa estrutura é cliente qualificado que busca e contrata o concorrente no Google)."
    }},
    {{
      "problema": "Problema específico 2 de copy/layout",
      "agitacao": "Agitação curta e real",
      "perda_ativa": "Consequência real no faturamento"
    }},
    {{
      "problema": "Problema específico 3 de velocidade/mobile",
      "agitacao": "Agitação curta e real",
      "perda_ativa": "Consequência real no faturamento"
    }}
  ],
  "solucao_proposta": "Breve parágrafo consultivo explicando como uma nova estrutura otimizada soluciona esses gargalos e maximiza novos agendamentos."
}}

Conteúdo do site:
{extracted_text}"""

    raw_response = call_llm(prompt, model_tier="pro")
    try:
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(raw_response)
    except Exception as e:
        print(f"  ⚠ Erro ao parsear JSON PAS ({e}). Usando fallback.")
        return json.loads(call_llm("", ""))


# ============================================================
# Montagem do Template Vertical em HTML/CSS
# ============================================================

def build_vertical_proposal_html(
    lead: Dict[str, Any],
    diagnostico: Dict[str, Any],
    antes_b64: str,
    depois_b64: str
) -> str:
    """Monta o documento PDF 100% vertical, com respiro, contraste antes/depois e identidade visual Allcance."""
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')
    regiao = lead.get('regiao', 'Brasil')
    phone = lead.get('telefone', '')
    phone_clean = re.sub(r'[^\d]', '', phone)
    wa_link = f"https://wa.me/{phone_clean}" if phone_clean else "#"
    data_hoje = datetime.now().strftime('%d/%m/%Y')

    resumo = diagnostico.get('situacao_atual_resumo', 'Diagnóstico de presença digital e oportunidades de conversão.')
    score = diagnostico.get('score_presenca', 5.0)
    problemas = diagnostico.get('problemas_pas', [])
    solucao = diagnostico.get('solucao_proposta', 'Implementar uma nova estrutura visual de alta conversão.')

    # Carrega a Logo Base64 se disponível
    logo_src = ""
    logo_file = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'logo_b64.txt')
    if os.path.exists(logo_file):
        try:
            with open(logo_file, 'r') as f:
                logo_src = f"data:image/png;base64,{f.read().strip()}"
        except Exception:
            pass

    # Monta os cards dos problemas na estrutura PAS
    problemas_html = ""
    for idx, p in enumerate(problemas):
        prob_title = p.get('problema', f'Gargalo {idx+1}')
        prob_agit = p.get('agitacao', 'Impacto na decisão do visitante.')
        prob_loss = p.get('perda_ativa', 'Perda contínua de oportunidades para concorrentes da região.')

        problemas_html += f"""
        <div class="pas-card">
          <div class="pas-header">
            <span class="pas-num">{idx+1}</span>
            <h4 class="pas-title">{prob_title}</h4>
          </div>
          <div class="pas-body">
            <p class="pas-agitation"><strong>Impacto direto:</strong> {prob_agit}</p>
            <div class="pas-loss-badge">
              <span class="loss-icon">⚠️</span>
              <span><strong>Prejuízo real:</strong> {prob_loss}</span>
            </div>
          </div>
        </div>
        """

    full_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Proposta Comercial — {nome}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
  @page {{
    size: A4;
    margin: 12mm 12mm 12mm 12mm;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; }}
  
  body {{
    background: #09090b;
    color: #f4f4f5;
    line-height: 1.5;
    font-size: 13px;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  .doc-wrapper {{
    max-width: 800px;
    margin: 0 auto;
  }}

  /* ============================================================
     1. CABEÇALHO (LOGO + METADADOS)
     ============================================================ */
  .section-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    margin-bottom: 26px;
  }}

  .brand-block {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}

  .brand-logo-img {{
    width: 38px;
    height: 38px;
    object-fit: contain;
    display: block;
  }}

  .brand-info {{
    display: flex;
    flex-direction: column;
  }}

  .brand-name-tag {{
    font-size: 16px;
    font-weight: 800;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .badge-brand {{
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    background: rgba(139, 92, 246, 0.18);
    color: #c4b5fd;
    border: 1px solid rgba(139, 92, 246, 0.35);
    padding: 2px 8px;
    border-radius: 9999px;
  }}

  .brand-doc-type {{
    font-size: 11px;
    color: #8b5cf6;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-top: 2px;
  }}

  .header-meta {{
    text-align: right;
  }}

  .meta-client {{
    font-size: 16px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 2px;
  }}

  .meta-details {{
    font-size: 11px;
    color: #a1a1aa;
  }}

  /* ============================================================
     SEÇÕES E TÍTULOS
     ============================================================ */
  .section-block {{
    margin-bottom: 28px;
  }}

  .section-label {{
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #8b5cf6;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  .section-title {{
    font-size: 18px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.4px;
    margin-bottom: 12px;
  }}

  /* ============================================================
     2. SITUAÇÃO ATUAL (DIAGNÓSTICO RESUMIDO)
     ============================================================ */
  .card-summary {{
    background: #121216;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-left: 4px solid #8b5cf6;
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
  }}

  .summary-text p {{
    font-size: 13px;
    color: #d4d4d8;
    line-height: 1.5;
  }}

  .score-badge {{
    background: #181820;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 10px 16px;
    text-align: center;
    min-width: 100px;
    flex-shrink: 0;
  }}

  .score-badge .score-val {{
    font-size: 20px;
    font-weight: 800;
    color: #f87171;
    font-family: 'JetBrains Mono', monospace;
  }}

  .score-badge .score-lbl {{
    font-size: 10px;
    font-weight: 700;
    color: #71717a;
    text-transform: uppercase;
  }}

  /* ============================================================
     3. PROBLEMAS IDENTIFICADOS (PAS)
     ============================================================ */
  .pas-stack {{
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}

  .pas-card {{
    background: #121216;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px 18px;
  }}

  .pas-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }}

  .pas-num {{
    background: #1c1c24;
    color: #8b5cf6;
    border: 1px solid rgba(139, 92, 246, 0.3);
    font-size: 11px;
    font-weight: 800;
    width: 22px;
    height: 22px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
  }}

  .pas-title {{
    font-size: 14px;
    font-weight: 700;
    color: #ffffff;
  }}

  .pas-agitation {{
    font-size: 12px;
    color: #a1a1aa;
    margin-bottom: 8px;
    line-height: 1.45;
  }}

  .pas-loss-badge {{
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.22);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
    color: #fca5a5;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  /* ============================================================
     4. CONTRASTE VISUAL ANTES / DEPOIS (EMPILHADO VERTICALMENTE)
     ============================================================ */
  .visual-stack {{
    display: flex;
    flex-direction: column;
    gap: 18px;
  }}

  .mockup-frame {{
    background: #121216;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    overflow: hidden;
  }}

  .frame-bar {{
    background: #181820;
    padding: 8px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }}

  .frame-tag {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  .tag-original {{ color: #f87171; }}
  .tag-proposed {{ color: #34d399; }}

  .frame-sub {{
    font-size: 10px;
    color: #71717a;
  }}

  .frame-img-box {{
    background: #000000;
    max-height: 380px;
    overflow: hidden;
    display: flex;
    align-items: flex-start;
  }}

  .frame-img-box img {{
    width: 100%;
    display: block;
    object-fit: cover;
    object-position: top;
  }}

  /* ============================================================
     5. PROPOSTA & CTA WHATSAPP
     ============================================================ */
  .section-cta {{
    background: linear-gradient(135deg, #16161e 0%, #0d0d12 100%);
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 12px;
    padding: 20px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
  }}

  .cta-desc h3 {{
    font-size: 16px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 4px;
  }}

  .cta-desc p {{
    font-size: 12px;
    color: #a1a1aa;
    line-height: 1.45;
  }}

  .btn-cta-whatsapp {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
    color: #ffffff !important;
    text-decoration: none;
    font-weight: 700;
    font-size: 13px;
    padding: 12px 22px;
    border-radius: 8px;
    white-space: nowrap;
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 4px 14px rgba(139, 92, 246, 0.4);
  }}
</style>
</head>
<body>

<div class="doc-wrapper">

  <!-- (1) CABEÇALHO COM LOGO -->
  <div class="section-header">
    <div class="brand-block">
      {f'<img class="brand-logo-img" src="{logo_src}" alt="Allcance Logo" />' if logo_src else ''}
      <div class="brand-info">
        <div class="brand-name-tag">
          Allcance
          <span class="badge-brand">Lead Intelligence</span>
        </div>
        <span class="brand-doc-type">Auditoria & Proposta Comercial</span>
      </div>
    </div>
    
    <div class="header-meta">
      <div class="meta-client">{nome}</div>
      <div class="meta-details">{nicho} • {regiao} • {data_hoje}</div>
    </div>
  </div>

  <!-- (2) SITUAÇÃO ATUAL -->
  <div class="section-block">
    <div class="section-label">⚡ DIAGNÓSTICO EXECUTIVO</div>
    <div class="card-summary">
      <div class="summary-text">
        <p>{resumo}</p>
      </div>
      <div class="score-badge">
        <div class="score-val">{score}/10</div>
        <div class="score-lbl">Score Atual</div>
      </div>
    </div>
  </div>

  <!-- (3) PROBLEMAS IDENTIFICADOS (PAS) -->
  <div class="section-block">
    <div class="section-label">🔴 GARGALOS DE CONVERSÃO IDENTIFICADOS</div>
    <div class="pas-stack">
      {problemas_html}
    </div>
  </div>

  <!-- (4) CONTRASTE ANTES / DEPOIS (EMPILHADO VERTICALMENTE) -->
  <div class="section-block">
    <div class="section-label">👁️ PROVA VISUAL COMPARATIVA</div>
    
    <div class="visual-stack">
      <!-- Antes (em cima) -->
      <div class="mockup-frame">
        <div class="frame-bar">
          <span class="frame-tag tag-original">✕ Situação Atual (Versão Original)</span>
          <span class="frame-sub">Baixa retenção e conversão mobile</span>
        </div>
        <div class="frame-img-box">
          <img src="data:image/png;base64,{antes_b64}" alt="Site Atual" />
        </div>
      </div>

      <!-- Depois (em baixo) -->
      <div class="mockup-frame">
        <div class="frame-bar">
          <span class="frame-tag tag-proposed">✓ Novo Padrão Otimizado (Alta Conversão)</span>
          <span class="frame-sub">Foco em WhatsApp, autoridade e agilidade</span>
        </div>
        <div class="frame-img-box">
          <img src="data:image/png;base64,{depois_b64}" alt="Novo Design Proposto" />
        </div>
      </div>
    </div>
  </div>

  <!-- (5) PROPOSTA E CTA WHATSAPP -->
  <div class="section-cta">
    <div class="cta-desc">
      <h3>Vamos implementar este novo padrão para o {nome}?</h3>
      <p>{solucao}</p>
    </div>
    <a href="{wa_link}" target="_blank" class="btn-cta-whatsapp">
      💬 Falar no WhatsApp
    </a>
  </div>

</div>

</body>
</html>"""
    return full_html


# ============================================================
# Upload para Supabase Storage e Atualização
# ============================================================

def upload_pdf_to_supabase(lead_id: str, pdf_bytes: bytes) -> Optional[str]:
    """Upload do PDF para o bucket 'propostas' no Supabase Storage."""
    if not SUPABASE_URL or not SUPABASE_KEY or create_client is None:
        return None

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        try:
            supabase.storage.create_bucket('propostas', options={'public': True})
        except Exception:
            pass

        filename = f"{lead_id}_proposta.pdf"
        supabase.storage.from_('propostas').upload(
            path=filename,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        return supabase.storage.from_('propostas').get_public_url(filename)
    except Exception as e:
        print(f"  ❌ Erro no upload Supabase Storage: {e}")
        return None


def update_lead_in_supabase(lead_id: str, pdf_url: str, diagnostico: Dict[str, Any]):
    """Salva URL do PDF no Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY or create_client is None:
        return
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        supabase.table('leads').update({
            'proposta_pdf_url': pdf_url,
            'proposta_status': 'concluida',
            'diagnostico_json': diagnostico
        }).eq('id', lead_id).execute()
        print(f"  ✅ Lead {lead_id} atualizado no Supabase.")
    except Exception as e:
        print(f"  ⚠ Erro ao atualizar lead: {e}")


# ============================================================
# Pipeline Principal
# ============================================================

async def run_pipeline(lead_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
    lead_id = lead_data.get('id', 'lead_temp')
    nome = lead_data.get('nome', 'Empresa')
    site_url = lead_data.get('site_url')
    
    print(f"\n{'='*65}")
    print(f"📄 GERANDO PROPOSTA COMERCIAL REDESENHADA (VERTICAL + PAS): {nome}")
    print(f"   Lead ID: {lead_id}")
    print(f"   Site: {site_url or 'Sem site registrado'}")
    print(f"{'='*65}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = await browser.new_page()

        antes_bytes = b""
        extracted_text = ""

        # 1. Captura da Situação Atual ("Antes")
        if lead_data.get('tem_site') and site_url:
            try:
                antes_bytes, extracted_text = await capture_original_site(page, site_url)
            except Exception as e:
                print(f"  ⚠ Erro ao capturar site ({e}).")
        
        if not antes_bytes:
            # Placeholder elegante para empresas sem site
            placeholder = f"""
            <html>
            <body style="margin:0; background:#121216; color:#a1a1aa; display:flex; flex-direction:column; align-items:center; justify-content:center; height:420px; font-family:sans-serif; text-align:center; padding:20px; border:1px dashed rgba(255,255,255,0.1);">
              <div style="font-size:40px; margin-bottom:10px;">🚫</div>
              <h3 style="color:#ffffff; margin-bottom:6px;">Sem Site Registrado</h3>
              <p style="font-size:12px; max-width:260px; color:#71717a;">A empresa ainda não possui site institucional ou página própria.</p>
            </body>
            </html>
            """
            await page.set_content(placeholder)
            antes_bytes = await page.screenshot(type='png')

        # 2. Diagnóstico Estruturado PAS via IA
        print("🧠 Realizando diagnóstico de gargalos e perda real (PAS) via IA...")
        diagnostico = analyze_site_pas(lead_data, extracted_text)

        # 3. Geração do Mockup "Depois"
        print("🎨 Gerando mockup de alta conversão ('Depois')...")
        depois_bytes = await generate_mockup_screenshot(page, lead_data, diagnostico)

        # 4. Renderização do Documento PDF Vertical A4
        antes_b64 = base64.b64encode(antes_bytes).decode('utf-8')
        depois_b64 = base64.b64encode(depois_bytes).decode('utf-8')
        
        final_html = build_vertical_proposal_html(lead_data, diagnostico, antes_b64, depois_b64)

        print("📑 Renderizando documento PDF A4...")
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.set_content(final_html, wait_until='load')
        await page.wait_for_timeout(1000)

        pdf_bytes = await page.pdf(
            format='A4',
            print_background=True,
            margin={'top': '10mm', 'bottom': '10mm', 'left': '10mm', 'right': '10mm'}
        )
        await browser.close()

    dest_file = output_path or f"proposta_{lead_id}.pdf"
    with open(dest_file, "wb") as f:
        f.write(pdf_bytes)

    pdf_url = upload_pdf_to_supabase(lead_id, pdf_bytes) or dest_file
    if pdf_url != dest_file:
        update_lead_in_supabase(lead_id, pdf_url, diagnostico)

    print(f"\n🏁 PROPOSTA FINALIZADA! Arquivo / URL: {pdf_url}\n")
    return pdf_url


# ============================================================
# CLI Entrypoint
# ============================================================

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lead_id", help="UUID do lead no Supabase")
    parser.add_argument("--nome", help="Nome da empresa")
    parser.add_argument("--telefone", help="Telefone / WhatsApp")
    parser.add_argument("--nicho", help="Nicho de atuação")
    parser.add_argument("--regiao", help="Região")
    parser.add_argument("--site_url", help="URL do site")
    parser.add_argument("--output", help="Arquivo de saída")
    args = parser.parse_args()

    lead_data = {
        'id': args.lead_id or 'lead_teste',
        'nome': args.nome or 'Empresa Exemplo',
        'telefone': args.telefone or '+5511999999999',
        'nicho': args.nicho or 'Geral',
        'regiao': args.regiao or 'São Paulo, SP',
        'tem_site': bool(args.site_url),
        'site_url': args.site_url or None
    }

    if args.lead_id and SUPABASE_URL and SUPABASE_KEY and create_client:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            res = supabase.table('leads').select('*').eq('id', args.lead_id).single().execute()
            if res.data:
                lead_data = res.data
        except Exception as e:
            print(f"⚠ Erro ao buscar lead no Supabase: {e}")

    await run_pipeline(lead_data, args.output)


if __name__ == '__main__':
    asyncio.run(main())
