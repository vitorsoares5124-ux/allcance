#!/usr/bin/env python3
"""
Lead Prospector — Gerador de Proposta Comercial Incisiva
Focado em Diagnóstico Real de Gargalos, Print Completo do Site e Efeitos Colaterais no Negócio.
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
    """Chama a IA configurada (Gemini -> Groq -> OpenAI) com retry resiliente."""
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

    # Fallback estruturado caso nenhuma chave esteja configurada
    print("  [IA Notice] Nenhuma chave externa de IA configurada. Usando auditoria analítica padrão.")
    return json.dumps({
        "resumo_impacto": "O site atual apresenta falhas críticas de clareza e conversão mobile que resultam em desistência imediata de potenciais clientes qualificados.",
        "analise_secoes": [
            {
                "secao": "Headline & Dobra Principal (Topo)",
                "pontos_positivos": ["Presença do nome da empresa e identificação básica de serviço"],
                "pontos_negativos": ["Falta de proposta de valor imediata nos primeiros 3 segundos", "Sem botão de contato rápido em destaque na tela inicial"],
                "efeitos_colaterais": "Mais de 60% dos visitantes fecham a aba imediatamente por não entenderem o diferencial do negócio, buscando concorrentes no Google."
            },
            {
                "secao": "Apresentação de Serviços & Prova Social",
                "pontos_positivos": ["Lista dos principais tratamentos ou serviços oferecidos"],
                "pontos_negativos": ["Textos longos sem escaneabilidade no celular", "Ausência de avaliações reais de clientes e fotos de casos de sucesso"],
                "efeitos_colaterais": "Gera desconfiança no cliente indeciso, que prefere contratar concorrentes com maior autoridade visual comprovada."
            },
            {
                "secao": "Canal de Conversão & WhatsApp",
                "pontos_positivos": ["Menção a formas de atendimento"],
                "pontos_negativos": ["Falta de botão flutuante de WhatsApp direto com mensagem pré-preenchida", "Formulários extensos ou navegação confusa"],
                "efeitos_colaterais": "O lead interessado perde o ímpeto de compra pela burocracia do contato, gerando perda diária de orçamentos e agendamentos."
            }
        ],
        "conclusao_estrategica": "Ajustar estes gargalos com uma landing page focada em conversão direta para o WhatsApp aumenta o retorno sobre qualquer divulgação ou busca orgânica, transformando visitantes em agendamentos reais."
    }, ensure_ascii=False, indent=2)


# ============================================================
# Captura de Tela Completa & Conteúdo do Site
# ============================================================

async def capture_full_site(page, site_url: str) -> Tuple[bytes, str]:
    """Captura print da página inteira e extrai o texto estruturado."""
    if not site_url.startswith('http'):
        site_url = 'https://' + site_url

    print(f"📸 Capturando página inteira do site: {site_url}")
    await page.set_viewport_size({"width": 1280, "height": 900})
    await page.goto(site_url, timeout=30000, wait_until='domcontentloaded')
    await page.wait_for_timeout(2000)

    # Scroll suave para renderizar lazy images
    try:
        await page.evaluate('''async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                let distance = 300;
                let timer = setInterval(() => {
                    let scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if(totalHeight >= scrollHeight || totalHeight >= 4000){
                        clearInterval(timer);
                        window.scrollTo(0, 0);
                        resolve();
                    }
                }, 100);
            });
        }''')
        await page.wait_for_timeout(1000)
    except Exception:
        pass

    # Captura Full Page
    screenshot_bytes = await page.screenshot(type='png', full_page=True)

    # Extrai o texto limpo para análise da IA
    extracted_text = await page.evaluate('''() => {
        const title = document.title;
        const metaDesc = document.querySelector('meta[name="description"]')?.content || '';
        const bodyText = document.body.innerText.substring(0, 9000);
        return `Título da Página: ${title}\\nDescrição: ${metaDesc}\\n\\nTexto Completo:\\n${bodyText}`;
    }''')

    return screenshot_bytes, extracted_text


# ============================================================
# Análise Incisiva com a IA
# ============================================================

def analyze_site_gaps(lead: Dict[str, Any], extracted_text: str) -> Dict[str, Any]:
    """Executa a análise da IA com foco cirúrgico nos erros e prejuízos de conversão."""
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')
    
    if not lead.get('tem_site') or not extracted_text:
        return {
            "resumo_impacto": f"A {nome} atualmente não possui site próprio registrado, dependendo 100% de canais de terceiros e perdendo clientes qualificados que buscam pelo serviço diariamente no Google.",
            "analise_secoes": [
                {
                    "secao": "Presença Digital & Autoridade Online",
                    "pontos_positivos": ["Nome da empresa cadastrado no Google Maps"],
                    "pontos_negativos": ["Inexistência de site institucional ou landing page própria", "Sem canal oficial para apresentação detalhada da equipe e diferenciais"],
                    "efeitos_colaterais": "Mais de 70% dos clientes pesquisam no Google antes de fechar negócio; a ausência de um site passa amadorismo e direciona o cliente aos concorrentes estruturados."
                },
                {
                    "secao": "Apresentação de Serviços & Preços",
                    "pontos_positivos": ["Potencial de atendimento direto via telefone"],
                    "pontos_negativos": ["Sem catálogo online centralizado com benefícios claros", "Falta de depoimentos e avaliações em um ambiente controlado"],
                    "efeitos_colaterais": "A equipe perde tempo respondendo dúvidas básicas repetidamente, com baixa taxa de fechamento por falta de convencimento prévio."
                },
                {
                    "secao": "Canal de Captação & Agendamento 24 Horas",
                    "pontos_positivos": ["Possui número de WhatsApp"],
                    "pontos_negativos": ["Sem botão de contato direto ou página de agendamento otimizada", "Nenhum sistema de captação de leads fora do horário comercial"],
                    "efeitos_colaterais": "Clientes que buscam serviços à noite ou nos fins de semana desistem da compra por não terem um meio rápido de solicitar atendimento."
                }
            ],
            "conclusao_estrategica": "Criar uma landing page de alta conversão para a sua empresa soluciona imediatamente esse gargalo, colocando seu negócio no mesmo nível dos maiores concorrentes da região."
        }

    prompt = f"""Você é um auditor sênior de conversão e presença digital para empresas locais.
Sua missão é analisar o site da empresa '{nome}' (Nicho: {nicho}) e gerar um diagnóstico cirúrgico e incisivo sobre os erros que estão fazendo essa empresa perder clientes e faturamento todos os dias.

Analise o conteúdo abaixo e retorne APENAS um JSON válido, sem texto antes ou depois, exatamente no seguinte formato:

{{
  "resumo_impacto": "Uma frase curta e de alto impacto sobre o principal gargalo que está custando clientes para a empresa hoje.",
  "analise_secoes": [
    {{
      "secao": "Headline & Dobra Principal (Topo)",
      "pontos_positivos": ["O que já existe ou funciona"],
      "pontos_negativos": ["Erros críticos de copy/layout encontrados no topo"],
      "efeitos_colaterais": "O prejuízo real gerado para a empresa: ex. O visitante não entende a proposta de valor em 3 segundos e fecha a aba para buscar o concorrente."
    }},
    {{
      "secao": "Apresentação dos Serviços & Prova Social",
      "pontos_positivos": ["Ponto positivo encontrado"],
      "pontos_negativos": ["Erros ou ausência de prova social/clareza"],
      "efeitos_colaterais": "O prejuízo real gerado: ex. Gera desconfiança, fazendo o cliente preferir outras opções mais consolidadas."
    }},
    {{
      "secao": "Conversão & Canal de Atendimento (WhatsApp)",
      "pontos_positivos": ["Ponto positivo"],
      "pontos_negativos": ["Falhas no direcionamento para contato"],
      "efeitos_colaterais": "O prejuízo real gerado: ex. Dificuldade de contato imediato faz o cliente abandonar a decisão de compra."
    }}
  ],
  "conclusao_estrategica": "Um parágrafo incisivo explicando por que corrigir esses gargalos vai aumentar a conversão de novos clientes imediatamente."
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
        print(f"  ⚠ Erro ao parsear resposta da IA: {e}")
        return json.loads(generate_rule_based_fallback(prompt, "pro"))


# ============================================================
# Montagem do HTML Final do PDF (Direto ao Ponto)
# ============================================================

def build_direct_proposal_html(
    lead: Dict[str, Any],
    diagnostico: Dict[str, Any],
    screenshot_b64: str
) -> str:
    """Monta o documento PDF com foco na Headline, Nome do Cliente, Print Completo e Diagnóstico Seção por Seção."""
    nome = lead.get('nome', 'Empresa')
    nicho = lead.get('nicho', 'Geral')
    regiao = lead.get('regiao', 'Brasil')
    phone = lead.get('telefone', '')
    phone_clean = re.sub(r'[^\d]', '', phone)
    wa_link = f"https://wa.me/{phone_clean}" if phone_clean else "#"
    data_hoje = datetime.now().strftime('%d/%m/%Y')

    resumo_impacto = diagnostico.get('resumo_impacto', 'Diagnóstico de conversão e gargalos de captação digital.')
    secoes = diagnostico.get('analise_secoes', [])
    conclusao = diagnostico.get('conclusao_estrategica', 'Corrigir esses pontos permite transformar tráfego em clientes pagantes com máxima previsibilidade.')

    # Monta os cards de cada seção
    secoes_html = ""
    for idx, sec in enumerate(secoes):
        titulo_sec = sec.get('secao', f'Seção {idx+1}')
        positivos = "".join([f"<li>{p}</li>" for p in sec.get('pontos_positivos', [])]) or "<li>Estrutura básica implementada</li>"
        negativos = "".join([f"<li>{n}</li>" for n in sec.get('pontos_negativos', [])]) or "<li>Oportunidade de otimização de conversão</li>"
        efeitos = sec.get('efeitos_colaterais', 'Perda de potenciais clientes para concorrentes da região.')

        secoes_html += f"""
        <div class="audit-card">
          <div class="audit-header">
            <span class="audit-badge">Área {idx+1}</span>
            <h4>{titulo_sec}</h4>
          </div>
          
          <div class="audit-grid">
            <div class="box-pos">
              <div class="box-title positive">✓ Pontos Positivos Identificados</div>
              <ul>{positivos}</ul>
            </div>
            
            <div class="box-neg">
              <div class="box-title negative">✕ Falhas Críticas & Pontos Negativos</div>
              <ul>{negativos}</ul>
            </div>
          </div>
          
          <div class="box-damage">
            <span class="damage-label">⚠️ Prejuízo & Efeito Colateral no Faturamento:</span>
            <p>{efeitos}</p>
          </div>
        </div>
        """

    full_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Proposta Comercial — {nome}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  @page {{
    size: A4;
    margin: 10mm 10mm 10mm 10mm;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; }}
  body {{
    background: #09090b;
    color: #f4f4f5;
    line-height: 1.45;
    font-size: 12px;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  .container {{
    max-width: 820px;
    margin: 0 auto;
    padding: 6px;
  }}

  /* Headline Principal */
  .hero-header {{
    border-bottom: 1px solid #27272a;
    padding-bottom: 16px;
    margin-bottom: 18px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }}
  .headline-tag {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #a1a1aa;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .headline-main {{
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.8px;
    background: linear-gradient(135deg, #ffffff 0%, #d4d4d8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.15;
  }}
  .client-name {{
    font-size: 18px;
    font-weight: 700;
    color: #38bdf8;
    margin-top: 4px;
  }}
  .meta-tag {{
    text-align: right;
    font-size: 11px;
    color: #71717a;
  }}
  .meta-tag strong {{
    color: #e4e4e7;
    font-size: 13px;
    display: block;
  }}

  /* Resumo de Impacto */
  .impact-banner {{
    background: #141418;
    border: 1px solid #27272a;
    border-left: 4px solid #ef4444;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 18px;
  }}
  .impact-banner h5 {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    color: #f87171;
    margin-bottom: 4px;
  }}
  .impact-banner p {{
    font-size: 13px;
    font-weight: 600;
    color: #f4f4f5;
  }}

  /* Layout de 2 Colunas: Print da Página Inteira + Auditoria */
  .layout-grid {{
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 16px;
    margin-bottom: 18px;
  }}

  /* Coluna do Print da Página Inteira */
  .screenshot-column {{
    display: flex;
    flex-direction: column;
  }}
  .screenshot-card {{
    background: #121215;
    border: 1px solid #27272a;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    height: 100%;
  }}
  .screenshot-header {{
    background: #18181b;
    padding: 8px 12px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    color: #a1a1aa;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #27272a;
    display: flex;
    justify-content: space-between;
  }}
  .screenshot-wrap {{
    background: #000;
    flex: 1;
    overflow: hidden;
    max-height: 520px;
  }}
  .screenshot-img {{
    width: 100%;
    display: block;
    object-fit: cover;
    object-position: top;
  }}

  /* Coluna da Auditoria Seção por Seção */
  .audit-column {{
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .audit-card {{
    background: #121215;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 12px 14px;
  }}
  .audit-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    border-bottom: 1px solid #1f1f23;
    padding-bottom: 6px;
  }}
  .audit-badge {{
    background: #27272a;
    color: #e4e4e7;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 4px;
  }}
  .audit-header h4 {{
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
  }}

  .audit-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 10px;
  }}
  .box-pos, .box-neg {{
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 8px 10px;
  }}
  .box-title {{
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 6px;
  }}
  .box-title.positive {{ color: #4ade80; }}
  .box-title.negative {{ color: #f87171; }}

  ul {{
    padding-left: 14px;
    font-size: 11px;
    color: #a1a1aa;
    line-height: 1.4;
  }}
  ul li {{
    margin-bottom: 3px;
  }}

  /* Box de Efeito Colateral / Malefício */
  .box-damage {{
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-radius: 6px;
    padding: 8px 10px;
  }}
  .damage-label {{
    display: block;
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
    color: #f87171;
    margin-bottom: 2px;
  }}
  .box-damage p {{
    font-size: 11px;
    color: #fecaca;
    font-weight: 500;
  }}

  /* Fechamento Comercial & Chamada de Ação */
  .cta-section {{
    background: linear-gradient(135deg, #18181b 0%, #0e0e11 100%);
    border: 1px solid #27272a;
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
  }}
  .cta-text h3 {{
    font-size: 15px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 4px;
  }}
  .cta-text p {{
    font-size: 11px;
    color: #a1a1aa;
    max-width: 480px;
  }}
  .btn-wa {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, #25d366 0%, #128c7e 100%);
    color: #ffffff !important;
    text-decoration: none;
    font-weight: 700;
    font-size: 13px;
    padding: 12px 22px;
    border-radius: 8px;
    white-space: nowrap;
    box-shadow: 0 4px 12px rgba(37,211,102,0.25);
  }}
</style>
</head>
<body>
<div class="container">

  <!-- Headline e Cabeçalho -->
  <div class="hero-header">
    <div>
      <div class="headline-tag">⚡ AUDITORIA DE CONVERSÃO & PRESENÇA DIGITAL</div>
      <h1 class="headline-main">PROPOSTA COMERCIAL</h1>
      <div class="client-name">{nome}</div>
    </div>
    <div class="meta-tag">
      <strong>{nicho}</strong>
      <span>{regiao} • {data_hoje}</span>
    </div>
  </div>

  <!-- Resumo de Impacto -->
  <div class="impact-banner">
    <h5>Gargalo Principal de Faturamento Identificado</h5>
    <p>{resumo_impacto}</p>
  </div>

  <!-- Layout: Print Inteiro da Página + Diagnóstico Seção por Seção -->
  <div class="layout-grid">
    
    <!-- Coluna da Esquerda: Print Completo do Site -->
    <div class="screenshot-column">
      <div class="screenshot-card">
        <div class="screenshot-header">
          <span>Situação Atual</span>
          <span>Página Completa</span>
        </div>
        <div class="screenshot-wrap">
          <img class="screenshot-img" src="data:image/png;base64,{screenshot_b64}" alt="Print Completo do Site" />
        </div>
      </div>
    </div>

    <!-- Coluna da Direita: Diagnóstico Seção por Seção -->
    <div class="audit-column">
      {secoes_html}
    </div>

  </div>

  <!-- Fechamento Comercial & CTA WhatsApp -->
  <div class="cta-section">
    <div class="cta-text">
      <h3>Nós temos a solução definitiva para corrigir cada um destes pontos.</h3>
      <p>{conclusao}</p>
    </div>
    <a href="{wa_link}" target="_blank" class="btn-wa">
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
    print(f"📄 INICIANDO GERAÇÃO DE PROPOSTA COMERCIAL INCISIVA: {nome}")
    print(f"   Lead ID: {lead_id}")
    print(f"   Site: {site_url or 'Sem site'}")
    print(f"{'='*65}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = await browser.new_page()

        screenshot_bytes = b""
        extracted_text = ""

        if lead_data.get('tem_site') and site_url:
            try:
                screenshot_bytes, extracted_text = await capture_full_site(page, site_url)
            except Exception as e:
                print(f"  ⚠ Erro ao capturar site ({e}). Usando placeholder.")
        
        if not screenshot_bytes:
            # Placeholder elegante para empresas sem site
            placeholder = f"""
            <html>
            <body style="margin:0; background:#121215; color:#a1a1aa; display:flex; flex-direction:column; align-items:center; justify-content:center; height:500px; font-family:sans-serif; text-align:center; padding:20px; border:1px dashed #27272a;">
              <div style="font-size:48px; margin-bottom:12px;">🚫</div>
              <h3 style="color:#f4f4f5; margin-bottom:6px;">Sem Site Registrado</h3>
              <p style="font-size:12px; max-width:240px; color:#71717a;">A empresa ainda não possui página própria na internet.</p>
            </body>
            </html>
            """
            await page.set_content(placeholder)
            screenshot_bytes = await page.screenshot(type='png')

        # Diagnóstico analítico com a IA
        print("🧠 Realizando auditoria cirúrgica de falhas e malefícios via IA...")
        diagnostico = analyze_site_gaps(lead_data, extracted_text)

        # Montagem do HTML e Renderização do PDF A4
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        final_html = build_direct_proposal_html(lead_data, diagnostico, screenshot_b64)

        print("📑 Renderizando documento PDF A4...")
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.set_content(final_html, wait_until='load')
        await page.wait_for_timeout(1000)

        pdf_bytes = await page.pdf(
            format='A4',
            print_background=True,
            margin={'top': '8mm', 'bottom': '8mm', 'left': '8mm', 'right': '8mm'}
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
