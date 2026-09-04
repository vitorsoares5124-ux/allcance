#!/usr/bin/env python3
"""
Lead Prospector — Gerador de Proposta Comercial / Diagnóstico Visual em PDF
1. Captura de prints das dobras específicas do site do próprio lead
2. Diagnóstico cirúrgico por IA (Pontos Negativos e Gargalos Visuais)
3. Sem containers, fundo 100% preto, texto branco
4. Destaque em vermelho exclusivamente na palavra "Pontos negativos:"
5. Botão / CTA de fechamento para WhatsApp
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

    return ""


# ============================================================
# Análise Diagnóstica por IA
# ============================================================

def analyze_site_problems(lead: Dict[str, Any], extracted_text: str) -> List[Dict[str, Any]]:
    """Gera os gargalos reais do site apontando problemas visuais específicos."""
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')

    if not lead.get('tem_site') or not extracted_text:
        return [
            {
                "titulo": "Ausência de Landing Page e Presença Própria",
                "pontos_negativos": "A empresa depende exclusivamente de listagens secundárias e não possui um canal oficial para converter tráfego qualificado. Clientes que buscam no Google são direcionados para concorrentes com sites estruturados."
            },
            {
                "titulo": "Falta de Chamada Direta para o WhatsApp",
                "pontos_negativos": "Sem um meio de contato imediato na primeira tela mobile, o potencial cliente interessado abandona a busca por não encontrar agilidade no atendimento."
            },
            {
                "titulo": "Inexistência de Prova Social e Diferenciais Claros",
                "pontos_negativos": "Sem catálogo visual de serviços, depoimentos de clientes e garantias visíveis, o negócio perde vendas para concorrentes com maior autoridade digital."
            }
        ]

    prompt = f"""Você é um auditor de conversão web. Analise o conteúdo extraído do site da empresa '{nome}' ({nicho}) e identifique de 2 a 3 problemas reais de conversão e layout.

Retorne APENAS um JSON no formato:
{{
  "problemas": [
    {{
      "titulo": "Título curto do problema (ex: Ausência de Chamada para Ação no Topo)",
      "pontos_negativos": "Texto direto e conciso explicando o impacto real na conversão e perda de clientes."
    }},
    {{
      "titulo": "Título curto do segundo problema",
      "pontos_negativos": "Texto direto explicando o impacto na conversão."
    }}
  ]
}}

Conteúdo do site:
{extracted_text}"""

    raw_response = call_llm(prompt, model_tier="pro")
    try:
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        data = json.loads(match.group(0)) if match else json.loads(raw_response)
        probs = data.get('problemas', [])
        if probs:
            return probs
    except Exception as e:
        print(f"  ⚠ Erro ao parsear JSON de diagnósticos ({e}). Usando fallback.")

    return [
        {
            "titulo": "Ausência de Chamada para Ação (CTA) no Topo",
            "pontos_negativos": "O visitante entra no site pelo celular e não encontra um botão direto para contato imediato via WhatsApp, resultando em abandono prematuro."
        },
        {
            "titulo": "Hierarquia Visual Confusa e Blocos Poluídos",
            "pontos_negativos": "Falta de contraste e alinhamento visual entre seções, dificultando a leitura rápida dos diferenciais da empresa."
        },
        {
            "titulo": "Falta de Elementos de Prova Social e Autoridade",
            "pontos_negativos": "Sem depoimentos visíveis ou garantias de atendimento na área de maior atenção visual do visitante."
        }
    ]


# ============================================================
# Captura de Screenshots de Seções Específicas
# ============================================================

async def capture_sections_and_diagnose(page, lead_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    """Navega no site do lead, extrai texto e captura prints das dobras correspondentes a cada problema."""
    site_url = lead_data.get('site_url')
    if not site_url:
        problemas = analyze_site_problems(lead_data, "")
        return problemas, ""

    if not site_url.startswith('http'):
        site_url = 'https://' + site_url

    print(f"📸 Acessando site do lead para auditoria: {site_url}")
    extracted_text = ""
    try:
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto(site_url, timeout=30000, wait_until='domcontentloaded')
        await page.wait_for_timeout(2000)

        extracted_text = await page.evaluate('''() => {
            const title = document.title || '';
            const meta = document.querySelector('meta[name="description"]')?.content || '';
            const text = document.body.innerText.substring(0, 8000);
            return `Título: ${title}\\nDescrição: ${meta}\\n\\nConteúdo:\\n${text}`;
        }''')
    except Exception as e:
        print(f"  ⚠ Erro ao carregar site ({e}). Usando fallback de visualização.")

    problemas = analyze_site_problems(lead_data, extracted_text)

    # Capturar prints das dobras específicas
    sec_configs = [
        {"selectors": ['header', 'nav', '#hero', '.hero', '.banner', '.header'], "clip": {"x": 0, "y": 0, "width": 1280, "height": 550}},
        {"selectors": ['#services', '.services', '#about', '.about', 'section:nth-of-type(2)'], "clip": {"x": 0, "y": 450, "width": 1280, "height": 550}},
        {"selectors": ['#contact', '.contact', 'footer', '.footer', '#testimonials', '.testimonials'], "clip": {"x": 0, "y": 950, "width": 1280, "height": 550}},
    ]

    for idx, prob in enumerate(problemas):
        config = sec_configs[idx % len(sec_configs)]
        screenshot_bytes = None

        if extracted_text:
            # Tentar locator específico
            for sel in config["selectors"]:
                try:
                    loc = page.locator(sel).first
                    if await loc.is_visible(timeout=1000):
                        screenshot_bytes = await loc.screenshot(type='png')
                        break
                except Exception:
                    pass

            # Fallback para clip de viewport por coordenadas de dobra
            if not screenshot_bytes:
                try:
                    screenshot_bytes = await page.screenshot(type='png', clip=config["clip"])
                except Exception:
                    try:
                        screenshot_bytes = await page.screenshot(type='png')
                    except Exception:
                        pass

        if screenshot_bytes:
            prob['print_b64'] = base64.b64encode(screenshot_bytes).decode('utf-8')
        else:
            # Placeholder visual limpo em HTML para empresas sem print direto
            placeholder_html = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body style="margin:0; padding:30px; background:#0a0a0a; color:#ffffff; font-family:sans-serif; height:240px; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; border:1px solid #222222;">
              <div style="font-size:28px; margin-bottom:10px;">🔍</div>
              <div style="font-size:14px; font-weight:700; color:#ffffff; margin-bottom:4px;">Evidência de Ausência de Canal Próprio</div>
              <div style="font-size:12px; color:#888888;">{prob['titulo']}</div>
            </body>
            </html>
            """
            await page.set_content(placeholder_html)
            ph_bytes = await page.screenshot(type='png')
            prob['print_b64'] = base64.b64encode(ph_bytes).decode('utf-8')

    return problemas, extracted_text


# ============================================================
# Montagem do Template Redesenhado (Fundo Preto, Sem Containers)
# ============================================================

def build_proposal_html(
    lead: Dict[str, Any],
    problemas_com_print: List[Dict[str, Any]]
) -> str:
    """Monta o documento PDF com fundo preto, texto branco, sem caixas e destaque exclusivo em vermelho."""
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')
    regiao = lead.get('regiao', 'Brasil')
    phone = lead.get('telefone', '')
    phone_clean = re.sub(r'[^\d]', '', phone)
    wa_link = f"https://wa.me/{phone_clean}" if phone_clean else "#"
    data_hoje = datetime.now().strftime('%d/%m/%Y')

    # Carrega a Logo Base64 se disponível
    logo_src = ""
    logo_file = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'logo_b64.txt')
    if os.path.exists(logo_file):
        try:
            with open(logo_file, 'r') as f:
                logo_src = f"data:image/png;base64,{f.read().strip()}"
        except Exception:
            pass

    blocks_html = ""
    for item in problemas_com_print:
        titulo = item.get('titulo', 'Problema Identificado')
        negativos = item.get('pontos_negativos', 'Impacto direto na conversão de novos clientes.')
        print_b64 = item.get('print_b64', '')

        blocks_html += f"""
        <div class="problem-block">
          {f'<img class="section-print" src="data:image/png;base64,{print_b64}" alt="{titulo}" />' if print_b64 else ''}
          <h3 class="problem-title">{titulo}</h3>
          <p class="problem-desc">
            <span class="negativo-label">Pontos negativos:</span> {negativos}
          </p>
        </div>
        """

    full_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Diagnóstico Comercial — {nome}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  @page {{
    size: A4;
    margin: 14mm 14mm 14mm 14mm;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; }}
  
  body {{
    background-color: #000000;
    color: #ffffff;
    line-height: 1.6;
    font-size: 14px;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  .doc-wrapper {{
    max-width: 760px;
    margin: 0 auto;
    background-color: #000000;
  }}

  /* CABEÇALHO MINIMALISTA SEM CAIXAS */
  .header {{
    margin-bottom: 36px;
    padding-bottom: 20px;
    border-bottom: 1px solid #222222;
  }}

  .brand {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
  }}

  .brand-logo-img {{
    height: 32px;
    width: auto;
    display: block;
  }}

  .brand-name {{
    font-size: 20px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.5px;
  }}

  .meta-info {{
    font-size: 13px;
    color: #a1a1aa;
    line-height: 1.5;
  }}

  .meta-info strong {{
    color: #ffffff;
  }}

  /* BLOCOS DE PROBLEMAS COM FOTO E TEXTO */
  .problem-block {{
    margin-bottom: 40px;
  }}

  .section-print {{
    width: 100%;
    max-height: 340px;
    object-fit: cover;
    object-position: top;
    border-radius: 4px;
    display: block;
    margin-bottom: 14px;
  }}

  .problem-title {{
    font-size: 17px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 6px;
    letter-spacing: -0.3px;
  }}

  .problem-desc {{
    font-size: 13.5px;
    color: #ffffff;
    line-height: 1.55;
  }}

  .negativo-label {{
    color: #ef4444;
    font-weight: 700;
  }}

  /* FECHAMENTO E BOTÃO WHATSAPP */
  .closing-block {{
    margin-top: 44px;
    padding-top: 24px;
    border-top: 1px solid #222222;
  }}

  .closing-text {{
    font-size: 15px;
    font-weight: 600;
    color: #ffffff;
    margin-bottom: 20px;
  }}

  .btn-whatsapp {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background-color: #ffffff;
    color: #000000 !important;
    font-weight: 800;
    font-size: 14px;
    padding: 14px 28px;
    border-radius: 6px;
    text-decoration: none;
  }}
</style>
</head>
<body>

<div class="doc-wrapper">

  <!-- CABEÇALHO (LOGO + ALLCANCE, LEAD, NICHO/REGIÃO, DATA) -->
  <div class="header">
    <div class="brand">
      {f'<img class="brand-logo-img" src="{logo_src}" alt="Allcance" />' if logo_src else ''}
      <span class="brand-name">Allcance</span>
    </div>
    <div class="meta-info">
      <strong>Empresa:</strong> {nome}<br>
      <strong>Segmento & Região:</strong> {nicho} • {regiao}<br>
      <strong>Data do Diagnóstico:</strong> {data_hoje}
    </div>
  </div>

  <!-- BLOCOS DE PROBLEMAS IDENTIFICADOS (PRINT + TÍTULO + PONTOS NEGATIVOS) -->
  {blocks_html}

  <!-- FECHAMENTO E CTA DE WHATSAPP -->
  <div class="closing-block">
    <div class="closing-text">
      Esses pontos estão custando conversão todos os dias.
    </div>
    <a href="{wa_link}" target="_blank" class="btn-whatsapp">
      Falar no WhatsApp
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


def update_lead_in_supabase(lead_id: str, pdf_url: str, diagnostico: List[Dict[str, Any]]):
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
    print(f"📄 GERANDO DIAGNÓSTICO VISUAL EM PDF: {nome}")
    print(f"   Lead ID: {lead_id}")
    print(f"   Site: {site_url or 'Sem site registrado'}")
    print(f"{'='*65}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = await browser.new_page()

        # 1 & 2. Captura de seções específicas e diagnóstico cirúrgico
        problemas, extracted_text = await capture_sections_and_diagnose(page, lead_data)

        # 3. Renderização do Documento PDF com Fundo Preto e Sem Containers
        final_html = build_proposal_html(lead_data, problemas)

        print("📑 Renderizando documento PDF A4...")
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.set_content(final_html, wait_until='load')
        await page.wait_for_timeout(1000)

        pdf_bytes = await page.pdf(
            format='A4',
            print_background=True,
            margin={'top': '12mm', 'bottom': '12mm', 'left': '12mm', 'right': '12mm'}
        )
        await browser.close()

    dest_file = output_path or f"proposta_{lead_id}.pdf"
    with open(dest_file, "wb") as f:
        f.write(pdf_bytes)

    pdf_url = upload_pdf_to_supabase(lead_id, pdf_bytes) or dest_file
    if pdf_url != dest_file:
        update_lead_in_supabase(lead_id, pdf_url, problemas)

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
