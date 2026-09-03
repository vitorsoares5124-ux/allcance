#!/usr/bin/env python3
"""
Lead Prospector — Gerador de Proposta Comercial
Pipeline sob demanda:
1. Diagnóstico do site (Playwright + IA)
2. Geração de mockup de landing page "depois" (IA + Playwright screenshot)
3. Montagem da proposta comercial (IA + comparação Antes/Depois)
4. Renderização em PDF (Playwright page.pdf()) e Upload para Supabase Storage
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

# Chaves de IA suportadas (Gemini / Groq / OpenAI / Anthropic)
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# ============================================================
# Utilitários de Chamada de IA
# ============================================================

def call_llm(prompt: str, system_prompt: str = "", model_tier: str = "flash") -> str:
    """
    Executa chamada para o provedor de IA disponível (Gemini -> Groq -> OpenAI -> Anthropic).
    model_tier: 'flash' (gratuito/rápido) ou 'pro' (maior capacidade de redação)
    """
    # 1. Google Gemini (Free tier disponível)
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
                print(f"  [IA Info] Tentativa no Gemini ({model}) retornou: {e}. Tentando fallback...")

    # 2. Groq (Llama 3 / Mixtral - Free tier rápido)
    if GROQ_API_KEY:
        url = "https://api.groq.com/openai/v1/chat/completions"
        model = "llama-3.3-70b-versatile" if model_tier == "pro" else "llama-3.1-8b-instant"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        body = json.dumps({"model": model, "messages": messages, "temperature": 0.3}).encode('utf-8')
        req = urllib.request.Request(
            url, data=body,
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GROQ_API_KEY}'},
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"  [IA Warning] Erro no Groq: {e}")

    # 3. OpenAI (GPT-4o / GPT-4o-mini)
    if OPENAI_API_KEY:
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o" if model_tier == "pro" else "gpt-4o-mini"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        body = json.dumps({"model": model, "messages": messages, "temperature": 0.4}).encode('utf-8')
        req = urllib.request.Request(
            url, data=body,
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_API_KEY}'},
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"  [IA Warning] Erro na OpenAI: {e}")

    # Fallback determinístico (se nenhuma chave de IA for configurada)
    print("  [IA Notice] Nenhuma API Key de IA configurada. Usando gerador analítico de fallback.")
    return generate_rule_based_fallback(prompt, model_tier)


def generate_rule_based_fallback(prompt: str, model_tier: str) -> str:
    """Gera templates consistentes caso nenhuma API externa de IA esteja conectada."""
    if "Analise e retorne APENAS um JSON válido" in prompt:
        return json.dumps({
            "tem_whatsapp_visivel": False,
            "tem_cta_claro": False,
            "problemas_copy": [
                "Texto genérico sem proposta de valor clara e convincente",
                "Ausência de prova social relevante e depoimentos de clientes",
                "Falta de chamada para ação (CTA) direta para contato imediato"
            ],
            "problemas_layout": [
                "Hierarquia visual confusa e elementos mal distribuídos",
                "Contraste baixo e tipografia de difícil leitura no celular",
                "Ausência de botão flutuante de WhatsApp para conversão rápida"
            ],
            "score_urgencia": 8.5,
            "resumo": "Site com estrutura desatualizada, baixa taxa de conversão e sem foco em captação de clientes no mobile."
        }, ensure_ascii=False, indent=2)
    
    if "Você é um web designer" in prompt:
        return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Proposta de Novo Design</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
body { background: #0a0a0c; color: #f4f4f5; line-height: 1.6; }
.hero { padding: 80px 24px; text-align: center; background: radial-gradient(circle at top, #1e1e24 0%, #0a0a0c 100%); }
.badge { display: inline-block; padding: 6px 16px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 100px; font-size: 13px; font-weight: 600; color: #a1a1aa; margin-bottom: 20px; }
h1 { font-size: 42px; font-weight: 800; line-height: 1.2; margin-bottom: 20px; background: linear-gradient(135deg, #fff 0%, #a1a1aa 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
p.lead { font-size: 18px; color: #a1a1aa; max-width: 650px; margin: 0 auto 32px; }
.btn-cta { display: inline-flex; align-items: center; gap: 10px; background: #25d366; color: #000; font-weight: 700; padding: 16px 36px; border-radius: 12px; text-decoration: none; font-size: 16px; box-shadow: 0 8px 24px rgba(37,211,102,0.3); }
.features { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; max-width: 1000px; margin: 60px auto; padding: 0 24px; }
.card { background: #141418; border: 1px solid #27272a; padding: 32px; border-radius: 16px; text-align: left; }
.card h3 { font-size: 20px; margin-bottom: 12px; color: #fff; }
.card p { color: #a1a1aa; font-size: 14px; }
</style>
</head>
<body>
<div class="hero">
  <div class="badge">✦ Atendimento Especializado & Exclusivo</div>
  <h1>Soluções de Alto Padrão com Atendimento Imediato</h1>
  <p class="lead">Experiência, agilidade e resultados comprovados para clientes exigentes.</p>
  <a href="#" class="btn-cta">💬 Falar com Especialista no WhatsApp</a>
</div>
<div class="features">
  <div class="card">
    <h3>⚡ Agilidade e Eficiência</h3>
    <p>Atendimento rápido e personalizado para sanar suas dúvidas com máxima prioridade.</p>
  </div>
  <div class="card">
    <h3>⭐ Excelência Comprovada</h3>
    <p>Histórico consistente de satisfação e foco em soluções definitivas para seu caso.</p>
  </div>
  <div class="card">
    <h3>🔒 Segurança e Confiança</h3>
    <p>Profissionais qualificados prontos para defender seus interesses e gerar valor.</p>
  </div>
</div>
</body>
</html>"""

    return """
<p>Analisamos detalhadamente a presença digital do seu negócio e identificamos oportunidades cruciais para alavancar a atração de clientes e sua taxa de conversão.</p>
"""


# ============================================================
# Passo 1: Diagnóstico do Site
# ============================================================

async def step1_diagnose_site(page, lead: Dict[str, Any]) -> Tuple[Dict[str, Any], bytes, List[str]]:
    """
    Captura o HTML, screenshot antes e lista de imagens reais do site do lead.
    Em seguida, solicita o diagnóstico para a IA.
    """
    site_url = lead.get('site_url')
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')
    
    screenshot_before = b""
    image_urls = []
    html_content = ""

    if lead.get('tem_site') and site_url:
        print(f"📍 [Passo 1] Navegando no site original: {site_url}")
        try:
            if not site_url.startswith('http'):
                site_url = 'https://' + site_url
            
            await page.goto(site_url, timeout=25000, wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)
            
            # Screenshot do Antes
            screenshot_before = await page.screenshot(type='png', full_page=False)
            
            # Extrair HTML simplificado e imagens
            extracted = await page.evaluate('''() => {
                const imgs = Array.from(document.querySelectorAll('img'))
                    .map(img => img.src)
                    .filter(src => src && src.startsWith('http') && !src.includes('data:') && !src.includes('pixel') && !src.includes('analytics'))
                    .slice(0, 10);
                
                // Texto do body limpo
                const bodyText = document.body.innerText.substring(0, 8000);
                const title = document.title;
                const metaDesc = document.querySelector('meta[name="description"]')?.content || '';
                const hasViewport = !!document.querySelector('meta[name="viewport"]');
                
                return {
                    imgs,
                    html: `Título: ${title}\\nMeta Description: ${metaDesc}\\nViewport Mobile: ${hasViewport}\\n\\nConteúdo do Site:\\n${bodyText}`
                };
            }''')
            
            image_urls = extracted.get('imgs', [])
            html_content = extracted.get('html', '')
            print(f"  ✓ Site carregado com sucesso. {len(image_urls)} imagens extraídas.")
            
        except Exception as e:
            print(f"  ⚠ Não foi possível acessar o site original ({e}). Gerando análise contextual.")
            html_content = f"Site inacessível ou com erro de carregamento: {site_url}"

    # Se não tiver site ou se falhou
    if not html_content or not lead.get('tem_site'):
        print(f"📍 [Passo 1] Lead sem site. Gerando diagnóstico de ausência de presença digital.")
        diagnostico = {
            "tem_whatsapp_visivel": False,
            "tem_cta_claro": False,
            "problemas_copy": [
                "Empresa não possui site próprio, dependendo exclusivamente de canais de terceiros",
                "Falta de proposta de valor estruturada e autoridade institucional na web",
                "Ausência de prova social centralizada e catálogo oficial de serviços"
            ],
            "problemas_layout": [
                "Inexistência de página profissional adaptada para dispositivos móveis",
                "Falta de botão direto e canal centralizado de agendamento 24 horas",
                "Ausência de otimização para buscas locais no Google (SEO local)"
            ],
            "score_urgencia": 9.2,
            "resumo": "A empresa não possui website próprio, perdendo diariamente clientes qualificados que buscam pelo serviço no Google."
        }
        
        # Gerar screenshot placeholder elegante para "Antes"
        placeholder_html = f"""
        <html>
        <body style="margin:0; background:#18181b; color:#a1a1aa; display:flex; flex-direction:column; align-items:center; justify-content:center; height:600px; font-family:sans-serif; text-align:center; padding:20px;">
          <div style="font-size:54px; margin-bottom:16px;">🚫</div>
          <h2 style="color:#f4f4f5; margin-bottom:8px;">Nenhum Website Encontrado</h2>
          <p style="max-width:400px; font-size:15px; line-height:1.5;">O negócio '{nome}' atualmente não possui landing page ou site próprio registrado no Google Maps.</p>
        </body>
        </html>
        """
        await page.set_content(placeholder_html)
        screenshot_before = await page.screenshot(type='png')
        return diagnostico, screenshot_before, []

    # Prompt Passo 1
    prompt_diag = f"""Você é um analista de presença digital. Receberá o HTML de um site de pequeno negócio.

Analise e retorne APENAS um JSON válido, sem texto antes ou depois, no formato:

{{
  "tem_whatsapp_visivel": boolean,
  "tem_cta_claro": boolean,
  "problemas_copy": ["problema 1", "problema 2"],
  "problemas_layout": ["problema 1", "problema 2"],
  "score_urgencia": number (0 a 10, onde 10 = precisa urgente de um site novo),
  "resumo": "uma frase curta resumindo o principal problema"
}}

Critérios de copy: texto genérico, ausência de proposta de valor clara, falta de prova social, tom desalinhado com o público, sem chamada para ação.
Critérios de layout: hierarquia visual confusa, sem responsividade aparente (verifique meta viewport), cores com baixo contraste, excesso de elementos, navegação confusa.

Seja direto e específico — cite o que está errado, não genérico.

HTML do site:
{html_content}"""

    raw_response = call_llm(prompt_diag, model_tier="flash")
    
    # Extrai o bloco JSON
    try:
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if json_match:
            diagnostico = json.loads(json_match.group(0))
        else:
            diagnostico = json.loads(raw_response)
    except Exception as e:
        print(f"  ⚠ Erro ao parsear JSON da IA: {e}. Usando fallback.")
        diagnostico = {
            "tem_whatsapp_visivel": False,
            "tem_cta_claro": False,
            "problemas_copy": ["Proposta de valor genérica", "Sem chamadas claras para contato"],
            "problemas_layout": ["Design desatualizado", "Baixa conversão no mobile"],
            "score_urgencia": 8.0,
            "resumo": "Site com estrutura antiga e pouca capacidade de conversão de visitantes em clientes."
        }

    return diagnostico, screenshot_before, image_urls


# ============================================================
# Passo 2: Geração do Mockup "Depois"
# ============================================================

async def step2_generate_mockup(page, lead: Dict[str, Any], diagnostico: Dict[str, Any], image_urls: List[str]) -> Tuple[str, bytes]:
    """
    Solicita à IA a criação de uma Landing Page melhorada (Passo 2) e tira o screenshot "Depois".
    """
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')
    
    prompt_mockup = f"""Você é um web designer. Vai gerar um HTML completo de landing page melhorada para um negócio, a partir do diagnóstico abaixo.

Regras:
- Reaproveite EXATAMENTE as imagens fornecidas na lista (use as URLs originais, não invente): {json.dumps(image_urls)}
- Corrija cada problema listado no diagnóstico
- Use HTML + CSS inline ou em <style>, sem dependências externas além de fontes do Google Fonts
- Estrutura: hero com proposta de valor clara, seção de benefícios, prova social (placeholder se não houver dado real), CTA com WhatsApp em destaque
- Design moderno, mobile-first, cores derivadas da paleta original do site (se identificável no HTML original) ou uma paleta neutra profissional se não for possível

Nicho do negócio: {nicho}
Nome do negócio: {nome}
Imagens disponíveis: {json.dumps(image_urls)}
Diagnóstico (problemas a corrigir): {json.dumps(diagnostico, ensure_ascii=False)}

Retorne APENAS o HTML completo, pronto para renderizar, sem explicações."""

    print(f"🎨 [Passo 2] Gerando código do novo Mockup para '{nome}'...")
    raw_html = call_llm(prompt_mockup, model_tier="flash")
    
    # Limpa markdown blocks se houver (```html ... ```)
    clean_html = re.sub(r'^```html\s*', '', raw_html, flags=re.MULTILINE)
    clean_html = re.sub(r'```\s*$', '', clean_html, flags=re.MULTILINE).strip()
    
    if not clean_html.startswith('<'):
        clean_html = generate_rule_based_fallback(prompt_mockup, "flash")

    # Renderizar no Playwright e tirar screenshot
    await page.set_viewport_size({"width": 1200, "height": 800})
    await page.set_content(clean_html, wait_until='load')
    await page.wait_for_timeout(1500)
    
    screenshot_after = await page.screenshot(type='png', full_page=False)
    print("  ✓ Screenshot do mockup gerado com sucesso.")
    
    return clean_html, screenshot_after


# ============================================================
# Passo 3: Montagem da Proposta Comercial
# ============================================================

def step3_generate_proposal_text(lead: Dict[str, Any], diagnostico: Dict[str, Any]) -> str:
    """
    Gera o conteúdo textual consultivo da proposta comercial via IA (Passo 3).
    """
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')
    phone_clean = re.sub(r'[^\d]', '', lead.get('telefone', ''))
    link_whatsapp = f"https://wa.me/{phone_clean}" if phone_clean else "https://wa.me/5511999999999"
    
    prompt_proposal = f"""Você vai gerar o conteúdo textual de uma proposta comercial em HTML, para ser convertida em PDF.

Estrutura obrigatória:
1. Cabeçalho: nome do negócio, data
2. Seção "Situação atual" — resumo do diagnóstico em linguagem simples, sem jargão técnico, destacando os pontos negativos de forma direta mas profissional (não ofensiva)
3. Seção "O que identificamos" — lista dos problemas de copy e layout, em bullets
4. Seção "Proposta" — breve texto convidando pra ver o mockup anexado, reforçando o ganho esperado (mais conversão, mais profissionalismo)
5. Rodapé com botão/link de contato via WhatsApp: {link_whatsapp}

Tom: consultivo, direto, sem exagero. Nada de "revolucionar seu negócio" — seja específico e factual.

Diagnóstico: {json.dumps(diagnostico, ensure_ascii=False)}
Nome do negócio: {nome}
Nicho: {nicho}
Link WhatsApp: {link_whatsapp}

Retorne APENAS o HTML da proposta, pronto para renderizar em PDF."""

    print(f"📝 [Passo 3] Redigindo proposta comercial estruturada...")
    raw_text = call_llm(prompt_proposal, model_tier="pro")
    
    clean_text = re.sub(r'^```html\s*', '', raw_text, flags=re.MULTILINE)
    clean_text = re.sub(r'```\s*$', '', clean_text, flags=re.MULTILINE).strip()
    return clean_text


# ============================================================
# Passo 4: Montagem do Template Final do PDF e Renderização
# ============================================================

def assemble_final_pdf_html(
    lead: Dict[str, Any],
    diagnostico: Dict[str, Any],
    proposal_text_html: str,
    img_before_b64: str,
    img_after_b64: str
) -> str:
    """
    Monta o HTML final com design moderno estilo Vercel / dark minimalista para conversão em PDF A4.
    """
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')
    regiao = lead.get('regiao', 'Brasil')
    phone = lead.get('telefone', '')
    phone_clean = re.sub(r'[^\d]', '', phone)
    wa_link = f"https://wa.me/{phone_clean}" if phone_clean else "#"
    data_hoje = datetime.now().strftime('%d/%m/%Y')
    
    score = diagnostico.get('score_urgencia', 8.0)
    resumo = diagnostico.get('resumo', 'Oportunidade imediata de aumento de conversão e captação de clientes.')
    problemas_copy = diagnostico.get('problemas_copy', [])
    problemas_layout = diagnostico.get('problemas_layout', [])

    copy_bullets = "".join([f"<li>{item}</li>" for item in problemas_copy])
    layout_bullets = "".join([f"<li>{item}</li>" for item in problemas_layout])

    full_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Proposta Comercial — {nome}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  @page {{
    size: A4;
    margin: 12mm 12mm 12mm 12mm;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, sans-serif; }}
  body {{
    background: #09090b;
    color: #f4f4f5;
    line-height: 1.5;
    font-size: 13px;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  .container {{
    max-width: 800px;
    margin: 0 auto;
    padding: 10px;
  }}
  
  /* Header */
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 1px solid #27272a;
    padding-bottom: 16px;
    margin-bottom: 20px;
  }}
  .logo-area {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .logo-badge {{
    width: 34px;
    height: 34px;
    background: linear-gradient(135deg, #ffffff 0%, #a1a1aa 100%);
    color: #000;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 16px;
  }}
  .brand-title {{
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
  }}
  .brand-sub {{
    font-size: 11px;
    color: #71717a;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .meta-right {{
    text-align: right;
    font-size: 12px;
    color: #a1a1aa;
  }}
  .meta-right strong {{
    color: #ffffff;
    display: block;
    font-size: 14px;
  }}

  /* Score Banner */
  .score-card {{
    background: #121215;
    border: 1px solid #27272a;
    border-radius: 10px;
    padding: 14px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }}
  .score-info h4 {{
    font-size: 13px;
    color: #a1a1aa;
    text-transform: uppercase;
    margin-bottom: 4px;
  }}
  .score-info p {{
    font-size: 14px;
    color: #f4f4f5;
    font-weight: 500;
  }}
  .score-num {{
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #f87171;
    font-size: 20px;
    font-weight: 800;
    padding: 6px 14px;
    border-radius: 8px;
  }}

  /* Sections */
  .section {{
    margin-bottom: 20px;
  }}
  .section-title {{
    font-size: 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #ffffff;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .section-title::before {{
    content: '';
    display: inline-block;
    width: 4px;
    height: 14px;
    background: #ffffff;
    border-radius: 2px;
  }}
  
  .card {{
    background: #141418;
    border: 1px solid #27272a;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 14px;
  }}
  
  /* Grid Diagnóstico */
  .diag-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }}
  .diag-box {{
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 12px 14px;
  }}
  .diag-box h5 {{
    font-size: 12px;
    font-weight: 600;
    color: #e4e4e7;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  ul.bullets {{
    padding-left: 18px;
    font-size: 12px;
    color: #a1a1aa;
  }}
  ul.bullets li {{
    margin-bottom: 5px;
  }}

  /* Comparativo Antes e Depois */
  .comparison-container {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-top: 10px;
  }}
  .comp-card {{
    background: #121215;
    border: 1px solid #27272a;
    border-radius: 8px;
    overflow: hidden;
  }}
  .comp-header {{
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .comp-header.before {{
    background: #1f1212;
    color: #f87171;
    border-bottom: 1px solid #3f1818;
  }}
  .comp-header.after {{
    background: #0f1f14;
    color: #4ade80;
    border-bottom: 1px solid #143820;
  }}
  .comp-img {{
    width: 100%;
    height: 180px;
    object-fit: cover;
    object-position: top;
    display: block;
    background: #000;
  }}

  /* CTA Footer */
  .footer-cta {{
    margin-top: 24px;
    background: linear-gradient(135deg, #18181b 0%, #101012 100%);
    border: 1px solid #27272a;
    border-radius: 10px;
    padding: 18px;
    text-align: center;
  }}
  .footer-cta h3 {{
    font-size: 16px;
    color: #fff;
    margin-bottom: 6px;
  }}
  .footer-cta p {{
    font-size: 12px;
    color: #a1a1aa;
    margin-bottom: 14px;
  }}
  .btn-whatsapp {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, #25d366 0%, #128c7e 100%);
    color: #ffffff !important;
    text-decoration: none;
    font-weight: 700;
    font-size: 14px;
    padding: 10px 24px;
    border-radius: 8px;
  }}
</style>
</head>
<body>
<div class="container">
  
  <!-- Header -->
  <div class="header">
    <div class="logo-area">
      <div class="logo-badge">⚡</div>
      <div>
        <div class="brand-title">Diagnóstico & Proposta Comercial</div>
        <div class="brand-sub">Otimização de Presença Digital & Alta Conversão</div>
      </div>
    </div>
    <div class="meta-right">
      <strong>{nome}</strong>
      <span>{nicho} • {regiao} • {data_hoje}</span>
    </div>
  </div>

  <!-- Score de Urgência -->
  <div class="score-card">
    <div class="score-info">
      <h4>Diagnóstico de Presença Digital</h4>
      <p>{resumo}</p>
    </div>
    <div class="score-num">
      Score: {score}/10
    </div>
  </div>

  <!-- O que identificamos -->
  <div class="section">
    <div class="section-title">O que identificamos na presença atual</div>
    <div class="diag-grid">
      <div class="diag-box">
        <h5>✍️ Oportunidades de Copy & Mensagem</h5>
        <ul class="bullets">
          {copy_bullets}
        </ul>
      </div>
      <div class="diag-box">
        <h5>🎨 Oportunidades de Layout & Conversão</h5>
        <ul class="bullets">
          {layout_bullets}
        </ul>
      </div>
    </div>
  </div>

  <!-- Comparativo Visual: Antes vs Depois -->
  <div class="section">
    <div class="section-title">Comparativo: Visual Atual vs Novo Design Proposto</div>
    <div class="comparison-container">
      <div class="comp-card">
        <div class="comp-header before">
          <span>❌ Situação Atual</span>
          <span>Original</span>
        </div>
        <img class="comp-img" src="data:image/png;base64,{img_before_b64}" alt="Antes" />
      </div>
      <div class="comp-card">
        <div class="comp-header after">
          <span>✅ Novo Design Proposto</span>
          <span>Alta Conversão</span>
        </div>
        <img class="comp-img" src="data:image/png;base64,{img_after_b64}" alt="Depois" />
      </div>
    </div>
  </div>

  <!-- Chamada para Ação / WhatsApp -->
  <div class="footer-cta">
    <h3>Vamos implementar esse novo padrão para o {nome}?</h3>
    <p>Landing page moderna, ultra rápida, adaptada para celular e integrada diretamente ao seu WhatsApp.</p>
    <a href="{wa_link}" target="_blank" class="btn-whatsapp">
      💬 Falar no WhatsApp com o Consultor
    </a>
  </div>

</div>
</body>
</html>"""
    return full_html


# ============================================================
# Upload para Supabase Storage e Atualização da Tabela
# ============================================================

def upload_pdf_to_supabase(lead_id: str, pdf_bytes: bytes) -> Optional[str]:
    """
    Envia o PDF gerado para o bucket 'propostas' no Supabase Storage.
    Retorna a URL pública.
    """
    if not SUPABASE_URL or not SUPABASE_KEY or create_client is None:
        print("  ⚠ Supabase não configurado. Salvando apenas localmente.")
        return None

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Garante que o bucket 'propostas' existe
        try:
            supabase.storage.create_bucket('propostas', options={'public': True})
        except Exception:
            pass  # Bucket já existe

        filename = f"{lead_id}_proposta.pdf"
        
        # Upload com overwrite
        res = supabase.storage.from_('propostas').upload(
            path=filename,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        
        # Obter URL pública
        public_url = supabase.storage.from_('propostas').get_public_url(filename)
        print(f"  💾 PDF enviado com sucesso para Supabase Storage: {public_url}")
        return public_url
    except Exception as e:
        print(f"  ❌ Erro ao enviar PDF para o Supabase Storage: {e}")
        return None


def update_lead_in_supabase(lead_id: str, pdf_url: str, diagnostico: Dict[str, Any]):
    """Atualiza o registro do lead no Supabase com a URL da proposta."""
    if not SUPABASE_URL or not SUPABASE_KEY or create_client is None:
        return

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        data_to_update = {
            'proposta_pdf_url': pdf_url,
            'proposta_status': 'concluida',
            'diagnostico_json': diagnostico
        }
        supabase.table('leads').update(data_to_update).eq('id', lead_id).execute()
        print(f"  ✅ Registro do lead {lead_id} atualizado no Supabase com sucesso.")
    except Exception as e:
        print(f"  ⚠ Aviso ao atualizar coluna do lead no Supabase: {e}")


# ============================================================
# Pipeline Principal
# ============================================================

async def run_pipeline(lead_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """Executa o pipeline completo de geração de proposta comercial."""
    lead_id = lead_data.get('id', 'lead_temp')
    nome = lead_data.get('nome', 'Empresa')
    
    print(f"\n{'='*65}")
    print(f"📄 INICIANDO GERAÇÃO DE PROPOSTA COMERCIAL: {nome}")
    print(f"   Lead ID: {lead_id}")
    print(f"   Site: {lead_data.get('site_url') or 'Não possui'}")
    print(f"{'='*65}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            viewport={'width': 1200, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # Passo 1: Diagnóstico do site
        diagnostico, shot_before, image_urls = await step1_diagnose_site(page, lead_data)
        
        # Passo 2: Geração do Mockup "Depois"
        _, shot_after = await step2_generate_mockup(page, lead_data, diagnostico, image_urls)
        
        # Passo 3: Texto da Proposta Comercial
        proposal_text = step3_generate_proposal_text(lead_data, diagnostico)
        
        # Passo 4: Montagem do HTML final e geração do PDF
        b64_before = base64.b64encode(shot_before).decode('utf-8')
        b64_after = base64.b64encode(shot_after).decode('utf-8')
        
        final_html = assemble_final_pdf_html(lead_data, diagnostico, proposal_text, b64_before, b64_after)
        
        print("📑 [Passo 4] Renderizando HTML final para documento PDF A4...")
        await page.set_content(final_html, wait_until='load')
        await page.wait_for_timeout(1000)
        
        pdf_bytes = await page.pdf(
            format='A4',
            print_background=True,
            margin={'top': '10mm', 'bottom': '10mm', 'left': '10mm', 'right': '10mm'}
        )
        
        await browser.close()

    # Salva arquivo localmente
    dest_file = output_path or f"proposta_{lead_id}.pdf"
    with open(dest_file, "wb") as f:
        f.write(pdf_bytes)
    print(f"💾 PDF salvo localmente: {dest_file}")

    # Upload para Supabase Storage e Update
    pdf_url = upload_pdf_to_supabase(lead_id, pdf_bytes)
    if not pdf_url:
        pdf_url = dest_file
    else:
        update_lead_in_supabase(lead_id, pdf_url, diagnostico)

    print(f"\n{'='*65}")
    print(f"🏁 PROPOSTA FINALIZADA COM SUCESSO!")
    print(f"   URL / Arquivo: {pdf_url}")
    print(f"{'='*65}\n")
    
    return pdf_url


# ============================================================
# Entrypoint CLI
# ============================================================

async def main():
    parser = argparse.ArgumentParser(description="Gerador de Proposta Comercial sob demanda")
    parser.add_argument("--lead_id", help="UUID do lead no Supabase")
    parser.add_argument("--nome", help="Nome da empresa")
    parser.add_argument("--telefone", help="Telefone / WhatsApp")
    parser.add_argument("--nicho", help="Nicho de atuação")
    parser.add_argument("--regiao", help="Região")
    parser.add_argument("--site_url", help="URL do site original")
    parser.add_argument("--output", help="Caminho do arquivo PDF de saída")
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

    # Se apenas o lead_id foi passado, buscar dados completos no Supabase
    if args.lead_id and SUPABASE_URL and SUPABASE_KEY and create_client:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            res = supabase.table('leads').select('*').eq('id', args.lead_id).single().execute()
            if res.data:
                lead_data = res.data
                print(f"✓ Dados do lead carregados do Supabase: {lead_data.get('nome')}")
        except Exception as e:
            print(f"⚠ Não foi possível carregar lead do Supabase: {e}")

    await run_pipeline(lead_data, args.output)


if __name__ == '__main__':
    asyncio.run(main())
