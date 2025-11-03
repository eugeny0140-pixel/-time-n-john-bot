import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from telegram.ext import Updater
import schedule
from redis import Redis
from googletrans import Translator

# Логи
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Токен
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Каналы (из env)
CHAN1 = int(os.environ.get('CHAN1', 0))   # @time_n_John
CHAN2 = int(os.environ.get('CHAN2', 0))   # @finanosint

# Redis
r = Redis.from_url(os.environ.get('REDIS_URL')) if os.environ.get('REDIS_URL') else None

# Переводчик
tr = Translator()

# 19 источников
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
   r"\brussia\b", r"\brussian\b", r"\bputin\b", r"\bmoscow\b", r"\bkremlin\b",
r"\bukraine\b", r"\bukrainian\b", r"\bzelensky\b", r"\bkyiv\b", r"\bkiev\b",
r"\bcrimea\b", r"\bdonbas\b", r"\bsanction[s]?\b", r"\bgazprom\b",
r"\bnord\s?stream\b", r"\bwagner\b", r"\blavrov\b", r"\bshoigu\b",
r"\bmedvedev\b", r"\bpeskov\b", r"\bnato\b", r"\beuropa\b", r"\busa\b",
r"\bsoviet\b", r"\bussr\b", r"\bpost\W?soviet\b",
# === СВО и Война ===
r"\bsvo\b", r"\bспецоперация\b", r"\bspecial military operation\b",
r"\bвойна\b", r"\bwar\b", r"\bconflict\b", r"\bконфликт\b",
r"\bнаступление\b", r"\boffensive\b", r"\bатака\b", r"\battack\b",
r"\bудар\b", r"\bstrike\b", r"\bобстрел\b", r"\bshelling\b",
r"\bдрон\b", r"\bdrone\b", r"\bmissile\b", r"\bракета\b",
r"\bэскалация\b", r"\bescalation\b", r"\bмобилизация\b", r"\bmobilization\b",
r"\bфронт\b", r"\bfrontline\b", r"\bзахват\b", r"\bcapture\b",
r"\bосвобождение\b", r"\bliberation\b", r"\bбой\b", r"\bbattle\b",
r"\bпотери\b", r"\bcasualties\b", r"\bпогиб\b", r"\bkilled\b",
r"\bранен\b", r"\binjured\b", r"\bпленный\b", r"\bprisoner of war\b",
r"\bпереговоры\b", r"\btalks\b", r"\bперемирие\b", r"\bceasefire\b",
r"\bсанкции\b", r"\bsanctions\b", r"\bоружие\b", r"\bweapons\b",
r"\bпоставки\b", r"\bsupplies\b", r"\bhimars\b", r"\batacms\b",
r"\bhour ago\b", r"\bчас назад\b", r"\bminutos atrás\b", r"\b小时前\b",
# === Криптовалюта (топ-20 + CBDC, DeFi, регуляция) ===
r"\bbitcoin\b", r"\bbtc\b", r"\bбиткоин\b", r"\b比特币\b",
r"\bethereum\b", r"\beth\b", r"\bэфир\b", r"\b以太坊\b",
r"\bbinance coin\b", r"\bbnb\b", r"\busdt\b", r"\btether\b",
r"\bxrp\b", r"\bripple\b", r"\bcardano\b", r"\bada\b",
r"\bsolana\b", r"\bsol\b", r"\bdoge\b", r"\bdogecoin\b",
r"\bavalanche\b", r"\bavax\b", r"\bpolkadot\b", r"\bdot\b",
r"\bchainlink\b", r"\blink\b", r"\btron\b", r"\btrx\b",
r"\bcbdc\b", r"\bcentral bank digital currency\b", r"\bцифровой рубль\b",
r"\bdigital yuan\b", r"\beuro digital\b", r"\bdefi\b", r"\bдецентрализованные финансы\b",
r"\bnft\b", r"\bnon-fungible token\b", r"\bsec\b", r"\bцб рф\b",
r"\bрегуляция\b", r"\bregulation\b", r"\bзапрет\b", r"\bban\b",
r"\bмайнинг\b", r"\bmining\b", r"\bhalving\b", r"\bхалвинг\b",
r"\bволатильность\b", r"\bvolatility\b", r"\bcrash\b", r"\bкрах\b",
r"\b刚刚\b", r"\bدقائق مضت\b",
# === Пандемия и болезни (включая биобезопасность) ===
r"\bpandemic\b", r"\bпандемия\b", r"\b疫情\b", r"\bجائحة\b",
r"\boutbreak\b", r"\bвспышка\b", r"\bэпидемия\b", r"\bepidemic\b",
r"\bvirus\b", r"\bвирус\b", r"\bвирусы\b", r"\b变异株\b",
r"\bvaccine\b", r"\bвакцина\b", r"\b疫苗\b", r"\bلقاح\b",
r"\bbooster\b", r"\bбустер\b", r"\bревакцинация\b",
r"\bquarantine\b", r"\bкарантин\b", r"\b隔离\b", r"\bحجر صحي\b",
r"\blockdown\b", r"\bлокдаун\b", r"\b封锁\b",
r"\bmutation\b", r"\bмутация\b", r"\b变异\b",
r"\bstrain\b", r"\bштамм\b", r"\bomicron\b", r"\bdelta\b",
r"\bbiosafety\b", r"\bбиобезопасность\b", r"\b生物安全\b",
r"\blab leak\b", r"\bлабораторная утечка\b", r"\b实验室泄漏\b",
r"\bgain of function\b", r"\bусиление функции\b",
r"\bwho\b", r"\bвоз\b", r"\bcdc\b", r"\bроспотребнадзор\b",
r"\binfection rate\b", r"\bзаразность\b", r"\b死亡率\b",
r"\bhospitalization\b", r"\bгоспитализация\b",
r"\bقبل ساعات\b", r"\b刚刚报告\b"]
def get_lead(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        s = BeautifulSoup(r.text, 'html.parser')
        for sel in ['.lead', 'p:first-of-type', '.summary', '.article-body p', 'p']:
            p = s.select_one(sel)
            if p and 30 < len(p.text) < 400:
                return p.text.strip()[:300]
        return ''
    except:
        return ''

def collect():
    news = []
    for src in SOURCES:
        try:
            resp = requests.get(src['u'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for h in soup.select(src['s'])[:2]:
                title = h.get_text(strip=True)
                a = h if h.name == 'a' else h.find('a')
                link = a['href'] if a and a.get('href') else None
                if not link or not title: continue
                if not link.startswith('http'):
                    link = src['b'].rstrip('/') + '/' + link.lstrip('/')
                if r and r.sismember('seen', link): continue
                lead = get_lead(link)
                news.append({'t': title, 'l': lead, 'url': link, 'src': src['n']})
                if r: r.sadd('seen', link)
        except Exception as e:
            log.error(f"{src['n']}: {e}")
    return news

def send(context):
    if CHAN1 == 0 or CHAN2 == 0:
        log.error("Укажи CHAN1 и CHAN2 в env!")
        return
    items = collect()
    if not items:
        log.info("Новостей нет")
        return
    log.info(f"Найдено {len(items)} новостей")
    for item in items:
        try:
            title_ru = tr.translate(item['t'], dest='ru').text
            lead_ru = tr.translate(item['l'], dest='ru').text if item['l'] else ''
        except:
            title_ru, lead_ru = item['t'], item['l']
        msg = f"**{item['src'].upper()}**: {title_ru}\n{lead_ru}\nИсточник: {item['url']}"
        # ОТПРАВЛЯЕМ В ОБОИ КАНАЛА ОДИНАКОВО
        context.bot.send_message(CHAN1, msg, parse_mode='Markdown')
        context.bot.send_message(CHAN2, msg, parse_mode='Markdown')
        log.info(f"Отправлено: {title_ru[:40]}...")
        time.sleep(50)  # 50 сек между новостями

def main():
    updater = Updater(TOKEN, use_context=True)
    schedule.every(14).minutes.do(send, updater.job_queue)
    updater.start_polling()
    log.info("Бот запущен! Дублирует в два канала каждые 15 мин.")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()
