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

# ВСЁ БЕЗОПАСНО — ТОЛЬКО ИЗ RENDER
TOKEN = os.getenv("BOT_TOKEN")
CHAN1 = int(os.getenv("CHAN1", "0"))
CHAN2 = int(os.getenv("CHAN2", "0"))
REDIS_URL = os.getenv("REDIS_URL")

if not TOKEN:
    log.error("ОШИБКА: BOT_TOKEN не найден! Добавь в Render → Environment")
    exit(1)

r = Redis.from_url(REDIS_URL) if REDIS_URL else None
tr = Translator()

SOURCES = [
    {"n":"Economist","u":"https://www.economist.com","s":"h3.teaser__headline a","b":"https://www.economist.com"},
    {"n":"Bloomberg","u":"https://www.bloomberg.com","s":"h3.storyItem__headline a","b":"https://www.bloomberg.com"},
    {"n":"BBC Future","u":"https://www.bbc.com/future","s":"h2[data-testid='card-headline'] a","b":"https://www.bbc.com"},
    {"n":"CSIS","u":"https://www.csis.org/analysis","s":"h3.field--name-title a","b":"https://www.csis.org"},
    {"n":"RAND","u":"https://www.rand.org/pubs.html","s":"h3.pub-title a","b":"https://www.rand.org"},
]

KEYWORDS = [r"russia", r"ukraine", r"putin", r"zelensky", r"war", r"bitcoin", r"btc", r"pandemic", r"vaccine"]

def match(text): return any(re.search(k, text, re.I) for k in KEYWORDS)

def get_lead(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7)
        s = BeautifulSoup(r.text, 'html.parser')
        p = s.find('p')
        return p.get_text(strip=True)[:250] if p else ''
    except: return ''

def collect():
    news = []
    for src in SOURCES:
        try:
            resp = requests.get(src['u'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for h in soup.select(src['s'])[:2]:
                title = h.get_text(strip=True)
                link = h['href'] if h.name=='a' else h.find('a')['href']
                if not link.startswith('http'):
                    link = src['b'].rstrip('/') + '/' + link.lstrip('/')
                if r and r.sismember('seen', link): continue
                lead = get_lead(link)
                if not match(title + lead): continue
                news.append({'t':title, 'l':lead, 'url':link, 'src':src['n']})
                if r: r.sadd('seen', link)
        except: pass
    return news

async def job(context):
    if CHAN1 == 0 or CHAN2 == 0:
        log.error("CHAN1 или CHAN2 = 0 → проверь Environment!")
        return
    items = collect()
    if not items:
        log.info("Новостей нет")
        return
    for item in items:
        try:
            t = tr.translate(item['t'], dest='ru').text
            l = tr.translate(item['l'], dest='ru').text if item['l'] else ''
        except: t, l = item['t'], item['l']
        msg = f"**{item['src'].upper()}**: {t}\n{l}\nИсточник: {item['url']}"
        await context.bot.send_message(CHAN1, msg, parse_mode='Markdown')
        await context.bot.send_message(CHAN2, msg, parse_mode='Markdown')
        log.info(f"ОТПРАВЛЕНО → {t[:50]}")
        time.sleep(50)

async def main():
    app = Application.builder().token(TOKEN).build()
    app.job_queue.run_repeating(job, interval=900, first=15)
    log.info("БОТ ЗАПУЩЕН — 5 источников, 2 канала, 15 минут")
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
