import os
import time
import logging
import requests
import re
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.ext import Application
from redis import Redis
from googletrans import Translator

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ТОКЕН ТЕПЕРЬ ТОЛЬКО ИЗ RENDER!
TOKEN = os.getenv("BOT_TOKEN")
CHAN1 = int(os.getenv('CHAN1', '0'))
CHAN2 = int(os.getenv('CHAN2', '0'))
REDIS_URL = os.getenv('REDIS_URL')

r = Redis.from_url(REDIS_URL) if REDIS_URL else None
tr = Translator()

SOURCES = [
    {"n": "Good Judgment", "u": "https://goodjudgment.com/open-questions/", "s": ".question-title a", "b": "https://goodjudgment.com"},
    {"n": "Johns Hopkins", "u": "https://centerforhealthsecurity.org/news/", "s": "h3.post-title a", "b": "https://centerforhealthsecurity.org"},
    {"n": "Metaculus", "u": "https://www.metaculus.com/questions/", "s": ".question-name a", "b": "https://www.metaculus.com"},
    {"n": "DNI", "u": "https://www.dni.gov/index.php/gt2040-home", "s": "h3 a, h2 a", "b": "https://www.dni.gov"},
    {"n": "RAND", "u": "https://www.rand.org/pubs.html", "s": "h3.pub-title a", "b": "https://www.rand.org"},
    {"n": "WEF", "u": "https://www.weforum.org/agenda/", "s": "h3[data-module='article-title'] a", "b": "https://www.weforum.org"},
    {"n": "CSIS", "u": "https://www.csis.org/analysis", "s": "h3.field--name-title a", "b": "https://www.csis.org"},
    {"n": "Atlantic", "u": "https://www.atlanticcouncil.org/blogs/", "s": "h3.post-title a", "b": "https://www.atlanticcouncil.org"},
    {"n": "Chatham", "u": "https://www.chathamhouse.org/publications", "s": "h3.publication-title a", "b": "https://www.chathamhouse.org"},
    {"n": "Economist", "u": "https://www.economist.com", "s": "h3.teaser__headline a", "b": "https://www.economist.com"},
    {"n": "Bloomberg", "u": "https://www.bloomberg.com", "s": "h3.storyItem__headline a", "b": "https://www.bloomberg.com"},
    {"n": "Reuters Inst", "u": "https://reutersinstitute.politics.ox.ac.uk/news", "s": "h3.news-title a", "b": "https://reutersinstitute.politics.ox.ac.uk"},
    {"n": "Foreign Affairs", "u": "https://www.foreignaffairs.com/articles", "s": "h3.view-content-title a", "b": "https://www.foreignaffairs.com"},
    {"n": "CFR", "u": "https://www.cfr.org/news", "s": "h3.node__title a", "b": "https://www.cfr.org"},
    {"n": "BBC Future", "u": "https://www.bbc.com/future", "s": "h2[data-testid='card-headline'] a", "b": "https://www.bbc.com"},
    {"n": "Future Timeline", "u": "https://futuretimeline.net", "s": "h3.entry-title a", "b": "https://futuretimeline.net"},
    {"n": "Carnegie", "u": "https://carnegieendowment.org/publications", "s": "h3.pub-title a", "b": "https://carnegieendowment.org"},
    {"n": "Bruegel", "u": "https://www.bruegel.org/publications", "s": "h3.publication-title a", "b": "https://www.bruegel.org"},
    {"n": "E3G", "u": "https://www.e3g.org/news/", "s": "h3.post-title a", "b": "https://www.e3g.org"},
]

KEYWORDS = [
    r"\brussia\b", r"\bukraine\b", r"\bputin\b", r"\bzelensky\b", r"\bsanction",
    r"\bsvo\b", r"\bвойна\b", r"\bwar\b", r"\battack\b", r"\bdrone\b", r"\bmissile\b",
    r"\bbitcoin\b", r"\bbtc\b", r"\bethereum\b", r"\bcrypto\b", r"\bcbdc\b",
    r"\bpandemic\b", r"\bvaccine\b", r"\bvirus\b", r"\blab leak\b"
]

def match(text): return any(re.search(k, text, re.I) for k in KEYWORDS)
def get_lead(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        s = BeautifulSoup(r.text, 'html.parser')
        p = s.find('p') or s.find('.lead') or s.find('.summary')
        return p.get_text(strip=True)[:300] if p else ''
    except: return ''

def collect():
    news = []
    for src in SOURCES:
        try:
            resp = requests.get(src['u'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for h in soup.select(src['s'])[:2]:
                title = h.get_text(strip=True)
                a = h if h.name == 'a' else h.find('a')
                if not a: continue
                link = a['href']
                if not link.startswith('http'):
                    link = src['b'].rstrip('/') + '/' + link.lstrip('/')
                if r and r.sismember('seen', link): continue
                lead = get_lead(link)
                if not match(title + ' ' + lead): continue
                news.append({'t': title, 'l': lead, 'url': link, 'src': src['n']})
                if r: r.sadd('seen', link)
        except: pass
    return news

async def job(context):
    if not CHAN1 or not CHAN2:
        log.error("CHAN1/CHAN2 не указаны!")
        return
    items = collect()
    if not items:
        log.info("Новостей по теме нет")
        return
    log.info(f"Найдено {len(items)} новостей")
    for item in items:
        try:
            t = tr.translate(item['t'], dest='ru').text
            l = tr.translate(item['l'], dest='ru').text if item['l'] else ''
        except:
            t, l = item['t'], item['l']
        msg = f"**{item['src'].upper()}**: {t}\n{l}\nИсточник: {item['url']}"
        await context.bot.send_message(CHAN1, msg, parse_mode='Markdown')
        await context.bot.send_message(CHAN2, msg, parse_mode='Markdown')
        log.info(f"ОТПРАВЛЕНО: {t[:40]}")
        time.sleep(50)

async def main():
    app = Application.builder().token(TOKEN).build()
    app.job_queue.run_repeating(job, interval=900, first=10)
    log.info("БОТ ЗАПУЩЕН! 19 источников → 2 канала → каждые 15 минут")
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
