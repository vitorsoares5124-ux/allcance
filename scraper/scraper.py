#!/usr/bin/env python3
"""
Lead Prospector — Google Maps Scraper
Extrai leads de empresas do Google Maps usando Playwright.
Salva os dados no Supabase (ou JSON local como fallback).
"""

import asyncio
import random
import os
import re
import sys
import json
import argparse
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

try:
    from supabase import create_client
except ImportError:
    create_client = None

# ============================================================
# Configuração
# ============================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')


# ============================================================
# Helpers
# ============================================================

async def random_delay(page, min_ms=1500, max_ms=4000):
    """Delay aleatório para simular comportamento humano."""
    delay = random.randint(min_ms, max_ms)
    await page.wait_for_timeout(delay)


def clean_phone(raw):
    """Limpa número de telefone, mantendo apenas dígitos e +."""
    cleaned = re.sub(r'[^\d+]', '', raw)
    # Adiciona código do Brasil se não tiver
    if cleaned and not cleaned.startswith('+'):
        if len(cleaned) >= 10:  # DDD + número
            cleaned = '+55' + cleaned
    return cleaned


# ============================================================
# Scraper — Google Maps
# ============================================================

async def accept_cookies(page):
    """Aceita cookies/termos se aparecerem."""
    selectors = [
        'button:has-text("Aceitar tudo")',
        'button:has-text("Accept all")',
        'button:has-text("Concordo")',
        'form[action*="consent"] button',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await random_delay(page, 1000, 2000)
                return
        except Exception:
            continue


async def scroll_results_feed(page, times=5):
    """Scrolla o painel de resultados do Google Maps para carregar mais itens."""
    feed = page.locator('div[role="feed"]')
    for i in range(times):
        try:
            await feed.evaluate('el => el.scrollBy(0, 800)')
            await random_delay(page, 1500, 3000)
        except Exception:
            break


async def collect_result_urls(page, max_urls):
    """Coleta URLs dos resultados do feed do Google Maps."""
    feed = page.locator('div[role="feed"]')
    links = feed.locator('a[href*="/maps/place/"]')
    total = await links.count()

    urls = []
    seen = set()
    for i in range(min(total, max_urls)):
        try:
            href = await links.nth(i).get_attribute('href')
            if href and href not in seen:
                seen.add(href)
                urls.append(href)
        except Exception:
            continue
    return urls


async def extract_lead_details(page, nicho, regiao):
    """Extrai dados de um negócio a partir do painel de detalhes do Google Maps."""

    lead = {
        'nome': '',
        'telefone': '',
        'endereco': '',
        'nicho': nicho,
        'regiao': regiao,
        'tem_site': False,
        'site_url': None,
        'tem_instagram': False,
        'instagram_handle': None,
        'status': 'novo',
    }

    # --- Nome (h1) ---
    try:
        h1 = page.locator('h1').first
        nome = await h1.text_content(timeout=5000)
        lead['nome'] = nome.strip() if nome else ''
    except Exception:
        return None

    if not lead['nome']:
        return None

    # --- Telefone ---
    # Google Maps usa data-item-id="phone:tel:+55..."
    try:
        phone_btn = page.locator('[data-item-id^="phone:tel:"]').first
        item_id = await phone_btn.get_attribute('data-item-id', timeout=3000)
        if item_id:
            raw = item_id.replace('phone:tel:', '')
            lead['telefone'] = clean_phone(raw)
    except Exception:
        pass

    # Fallback: busca por link tel:
    if not lead['telefone']:
        try:
            tel_link = page.locator('a[href^="tel:"]').first
            href = await tel_link.get_attribute('href', timeout=2000)
            if href:
                lead['telefone'] = clean_phone(href.replace('tel:', ''))
        except Exception:
            pass

    # Sem telefone = lead inútil para prospecção via WhatsApp
    if not lead['telefone']:
        return None

    # --- Endereço ---
    try:
        addr_btn = page.locator('[data-item-id^="address"]').first
        # O texto do endereço fica dentro do botão
        addr_text = await addr_btn.locator('.Io6YTe, .rogA2c').first.text_content(timeout=3000)
        lead['endereco'] = addr_text.strip() if addr_text else ''
    except Exception:
        pass

    # --- Website ---
    try:
        site_link = page.locator('a[data-item-id^="authority"]').first
        href = await site_link.get_attribute('href', timeout=3000)
        if href:
            lead['tem_site'] = True
            lead['site_url'] = href
    except Exception:
        pass

    return lead


async def check_instagram(page, business_name):
    """Busca o Instagram do negócio via pesquisa Google."""
    try:
        query = f'"{business_name}" site:instagram.com'
        url = f'https://www.google.com/search?q={quote_plus(query)}&hl=pt-BR'

        await page.goto(url, wait_until='domcontentloaded')
        await random_delay(page, 2000, 4000)

        # Busca links do Instagram nos resultados
        ig_links = page.locator('a[href*="instagram.com/"]')
        count = await ig_links.count()

        IGNORE_HANDLES = {'p', 'explore', 'accounts', 'about', 'reel',
                          'reels', 'stories', 'directory', 'developer',
                          'legal', 'tags', 'locations'}

        for i in range(min(count, 5)):
            href = await ig_links.nth(i).get_attribute('href')
            if href and 'instagram.com/' in href:
                match = re.search(r'instagram\.com/([a-zA-Z0-9_.]+)', href)
                if match:
                    handle = match.group(1).lower()
                    if handle not in IGNORE_HANDLES:
                        return True, f'@{handle}'

        return False, None

    except Exception as e:
        print(f'  ⚠ Erro ao buscar Instagram: {e}')
        return False, None


async def scrape_maps(nicho, regiao, quantidade):
    """Pipeline principal: busca Google Maps → extrai leads → checa Instagram."""

    print(f'\n{"="*60}')
    print(f'🔍 Lead Prospector — Google Maps Scraper')
    print(f'   Nicho: {nicho}')
    print(f'   Região: {regiao}')
    print(f'   Quantidade: {quantidade}')
    print(f'{"="*60}\n')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
            ]
        )

        context = await browser.new_context(
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
            geolocation={'latitude': -23.5505, 'longitude': -46.6333},
            permissions=['geolocation'],
            viewport={'width': 1366, 'height': 768},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/121.0.0.0 Safari/537.36'
            ),
        )

        page = await context.new_page()
        ig_page = await context.new_page()  # Página separada para buscar Instagram

        # --- 1. Navega para o Google Maps com a busca ---
        if regiao.lower() in ('brasil', 'brasil todo'):
            query = f'{nicho} no Brasil'
        else:
            query = f'{nicho} em {regiao}'

        search_url = f'https://www.google.com/maps/search/{quote_plus(query)}'
        print(f'📍 Navegando: {search_url}')

        await page.goto(search_url, wait_until='domcontentloaded')
        await random_delay(page, 3000, 6000)

        # Aceita cookies
        await accept_cookies(page)

        # --- 2. Aguarda e scrolla o feed de resultados ---
        feed = page.locator('div[role="feed"]')
        try:
            await feed.wait_for(timeout=15000)
            print('✅ Feed de resultados carregado')
        except Exception:
            print('❌ Feed não encontrado. A busca pode não ter retornado resultados.')
            await browser.close()
            return []

        # Scrolla para carregar mais resultados
        print('📜 Scrollando para carregar mais resultados...')
        await scroll_results_feed(page, times=5)

        # --- 3. Coleta URLs dos resultados ---
        urls = await collect_result_urls(page, quantidade * 3)
        print(f'📋 {len(urls)} URLs de resultados coletadas\n')

        if not urls:
            print('❌ Nenhum resultado encontrado.')
            await browser.close()
            return []

        # --- 4. Extrai detalhes de cada resultado ---
        leads = []

        for idx, url in enumerate(urls):
            if len(leads) >= quantidade:
                break

            try:
                print(f'--- [{idx+1}/{len(urls)}] ---')
                await page.goto(url, wait_until='domcontentloaded')
                await random_delay(page, 2000, 4000)

                lead = await extract_lead_details(page, nicho, regiao)

                if lead:
                    # Busca Instagram em página separada
                    print(f'  📸 Buscando Instagram: "{lead["nome"]}"...')
                    lead['tem_instagram'], lead['instagram_handle'] = (
                        await check_instagram(ig_page, lead['nome'])
                    )

                    leads.append(lead)
                    site_flag = '🌐' if lead['tem_site'] else '  '
                    ig_flag = lead.get('instagram_handle') or '—'
                    print(f'  ✅ [{len(leads)}/{quantidade}] {lead["nome"]}')
                    print(f'     📞 {lead["telefone"]} | {site_flag} Site | 📸 {ig_flag}')
                else:
                    print(f'  ⏭ Sem telefone, pulando...')

            except Exception as e:
                print(f'  ❌ Erro: {e}')
                continue

            await random_delay(page, 1000, 3000)

        await browser.close()

        print(f'\n{"="*60}')
        print(f'🏁 Total de leads extraídos: {len(leads)}')
        print(f'{"="*60}\n')

        return leads


# ============================================================
# Persistência — Supabase / JSON fallback
# ============================================================

def save_leads(leads):
    """Salva leads no Supabase. Se não configurado, salva em JSON local."""

    if not SUPABASE_URL or not SUPABASE_KEY or create_client is None:
        print('⚠ Supabase não configurado. Salvando em JSON local...')
        with open('leads_output.json', 'w', encoding='utf-8') as f:
            json.dump(leads, f, ensure_ascii=False, indent=2)
        print(f'💾 {len(leads)} leads salvos em leads_output.json')
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    saved = 0
    errors = 0

    for lead in leads:
        try:
            supabase.table('leads').upsert(
                lead,
                on_conflict='telefone'
            ).execute()
            saved += 1
            print(f'  💾 Upsert OK: {lead["nome"]}')
        except Exception as e:
            errors += 1
            print(f'  ❌ Erro ao salvar "{lead["nome"]}": {e}')

    print(f'\n✅ {saved} leads salvos no Supabase ({errors} erros)')


# ============================================================
# Entrypoint
# ============================================================

async def main():
    parser = argparse.ArgumentParser(
        description='Lead Prospector — Google Maps Scraper'
    )
    parser.add_argument(
        '--nicho', required=True,
        help='Nicho de mercado (ex: "cabeleireiro", "advogado")'
    )
    parser.add_argument(
        '--regiao', required=True,
        help='Região (ex: "São Paulo, SP", "Brasil todo")'
    )
    parser.add_argument(
        '--quantidade', type=int, default=10,
        help='Quantidade de leads a buscar (1-30, default: 10)'
    )
    args = parser.parse_args()

    quantidade = max(1, min(30, args.quantidade))

    leads = await scrape_maps(args.nicho, args.regiao, quantidade)

    if leads:
        save_leads(leads)
    else:
        print('\n⚠ Nenhum lead encontrado nesta busca.')
        sys.exit(0)


if __name__ == '__main__':
    asyncio.run(main())
