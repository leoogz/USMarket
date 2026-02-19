import asyncio
import feedparser
from telegram import Bot
from datetime import datetime
from dotenv import load_dotenv
import os
import yfinance as yf
import html
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import io
import time
from bs4 import BeautifulSoup

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_TOKEN이 .env에 없습니다!")

bot = Bot(token=BOT_TOKEN)

async def get_all_chat_ids():
    chat_ids = set()
    try:
        updates = await bot.get_updates(offset=-1, limit=100, timeout=30)
        for update in updates:
            if update.message:
                chat_ids.add(str(update.message.chat.id))
            elif update.channel_post:
                chat_ids.add(str(update.channel_post.chat.id))
            elif update.my_chat_member:
                chat_ids.add(str(update.my_chat_member.chat.id))
        return list(chat_ids)
    except Exception as e:
        print(f"채팅방 목록 가져오기 실패: {e}")
        return []

def capture_finviz_map():
    try:
        options = Options()
        #options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.set_page_load_timeout(300)

        driver.get("https://finviz.com/map.ashx?t=sec_all&st=w4")
        time.sleep(15)

        driver.execute_script("""
            document.querySelectorAll('header, footer, .fv-ad, .fv-right-panel, #cookie-notice, .modal, .banner').forEach(el => el.remove());
            document.body.style.margin = '0';
            document.body.style.padding = '0';
        """)

        map_element = driver.find_element(By.CSS_SELECTOR, "#map")
        map_png = map_element.screenshot_as_png

        img = Image.open(io.BytesIO(map_png))
        img = img.resize((1200, 800), Image.LANCZOS)

        bio = io.BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)

        driver.quit()
        return bio
    except Exception as e:
        print(f"핀비즈 캡처 실패: {e}")
        return None

def get_economic_calendar():
    """오늘의 주요 경제 이벤트를 가져옵니다."""
    events = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    # Yahoo Finance 실적 발표 일정
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        earnings_url = f"https://finance.yahoo.com/calendar/earnings?day={today}"
        response = requests.get(earnings_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            rows = soup.select('table tbody tr')
            for row in rows[:5]:
                cells = row.select('td')
                if len(cells) >= 2:
                    ticker = cells[0].get_text(strip=True)
                    company = cells[1].get_text(strip=True)
                    name = company if company else ticker
                    if name and len(name) > 1:
                        if len(name) > 30:
                            name = name[:27] + "..."
                        events.append({'time': '', 'name': f"{name} 실적 발표", 'importance': 2})
    except Exception as e:
        print(f"Yahoo 실적 로드 실패: {e}")
    
    return events[:5] if events else None

def get_us_market_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    summary = f"<b>【미국장 아침 브리핑 - {today} (서울 시간 기준)】</b>\n\n"

    try:
        tickers = {'다우존스': '^DJI', 'S&P 500': '^GSPC', '나스닥': '^IXIC'}
        summary += "<b>📊 주요 지수 (최신 종가 / 변화율)</b>\n"
        for name, symbol in tickers.items():
            info = yf.Ticker(symbol).info
            price = info.get('regularMarketPrice') or info.get('previousClose', 'N/A')
            pct = info.get('regularMarketChangePercent', 'N/A')
            color = "🔴" if pct >= 0 else "🔵"
            summary += f"・<b>{name}</b>: {price:,.2f} ({pct:+.2f}%) {color}\n"
        summary += "\n"
    except Exception as e:
        summary += f"(지수 오류: {e})\n\n"

    try:
        sectors = {'기술 (IT)': 'XLK', '금융': 'XLF', '에너지': 'XLE', '소비재': 'XLY', '헬스케어': 'XLV'}
        summary += "<b>섹터별 변화율 (최근 종가 기준)</b>\n"
        for name, etf in sectors.items():
            pct = yf.Ticker(etf).info.get('regularMarketChangePercent', 'N/A')
            color = "🔴" if pct >= 0 else "🔵"
            summary += f"・<b>{name}</b>: {pct:+.2f}% {color}\n"
        summary += "\n"
    except Exception:
        summary += "(섹터 로드 실패)\n\n"

    # 환율 정보 (원화 기준)
    try:
        summary += "<b>💱 환율 (원화 기준)</b>\n"
        currencies = {
            '달러/원': 'KRW=X',
            '엔/원 (100엔)': 'KRWJPY=X',
            '유로/원': 'EURKRW=X',
        }
        # USD/KRW
        usd_krw = yf.Ticker('KRW=X').info
        usd_price = usd_krw.get('regularMarketPrice') or usd_krw.get('previousClose', 0)
        usd_pct = usd_krw.get('regularMarketChangePercent', 0)
        usd_color = "🔴" if usd_pct >= 0 else "🔵"
        summary += f"・<b>달러/원</b>: {usd_price:,.2f}원 ({usd_pct:+.2f}%) {usd_color}\n"
        
        # JPY/KRW (100엔 기준)
        jpy_krw = yf.Ticker('JPYKRW=X').info
        jpy_price = jpy_krw.get('regularMarketPrice') or jpy_krw.get('previousClose', 0)
        jpy_pct = jpy_krw.get('regularMarketChangePercent', 0)
        jpy_color = "🔴" if jpy_pct >= 0 else "🔵"
        summary += f"・<b>엔/원 (100엔)</b>: {jpy_price * 100:,.2f}원 ({jpy_pct:+.2f}%) {jpy_color}\n"
        
        # EUR/KRW
        eur_krw = yf.Ticker('EURKRW=X').info
        eur_price = eur_krw.get('regularMarketPrice') or eur_krw.get('previousClose', 0)
        eur_pct = eur_krw.get('regularMarketChangePercent', 0)
        eur_color = "🔴" if eur_pct >= 0 else "🔵"
        summary += f"・<b>유로/원</b>: {eur_price:,.2f}원 ({eur_pct:+.2f}%) {eur_color}\n"
        summary += "\n"
    except Exception as e:
        summary += f"(환율 로드 실패: {e})\n\n"

    summary += "<b>🔥 오늘의 주요 경제 헤드라인 (최근 5개)</b>\n"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        response = requests.get('https://www.yna.co.kr/rss/economy.xml', headers=headers, timeout=15)
        response.raise_for_status()
        feed = feedparser.parse(response.content)

        if not feed.entries:
            summary += "(RSS 항목 없음)\n\n"
        else:
            for entry in feed.entries[:5]:
                title = html.escape(entry.title.strip())
                link = entry.link.strip()
                published = entry.get('published', 'N/A').strip()
                short_title = title[:70] + "..." if len(title) > 70 else title
                summary += f"• <a href=\"{link}\">{short_title}</a>\n"
                summary += f"  {published}\n\n"
    except Exception as e:
        summary += f"(뉴스 로드 실패: {str(e)})\n\n"

    summary += "<b>📅 오늘 주목할 경제 이벤트 (미국)</b>\n"
    try:
        calendar_events = get_economic_calendar()
        if calendar_events:
            for event in calendar_events:
                importance_stars = "⭐" * event['importance']
                time_str = f"[{event['time']}] " if event['time'] else ""
                summary += f"• {time_str}{event['name']} {importance_stars}\n"
        else:
            summary += "• 오늘 주요 경제 이벤트 없음\n"
    except Exception as e:
        summary += f"• (경제 캘린더 로드 실패)\n"
    summary += "\n"

    summary += "더 자세한 내용은 Yahoo Finance, CNBC에서 확인하세요!\n#미국장 #경제브리핑"

    print("\n=== 실제 메시지 일부 ===\n")
    print(summary[:1200])
    print("\n==================================\n")

    return summary

async def send_message():
    try:
        text = get_us_market_summary()

        chat_ids = await get_all_chat_ids()
        if not chat_ids:
            print("아직 인식된 채팅방이 없습니다. 봇을 톡방에 추가하고 한 번 메시지 보내주세요.")
            return

        print(f"전송 대상 채팅방 수: {len(chat_ids)}")

        # 핀비즈 맵 캡처 비활성화
        # map_image = capture_finviz_map()
        map_image = None

        for chat_id in chat_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=False
                )

                if map_image:
                    pass  # 핀비즈 맵 전송 비활성화
                    # await bot.send_photo(
                    #     chat_id=chat_id,
                    #     photo=map_image,
                    #     caption="현재 핀비즈 섹터 맵 )"
                    # )

                print(f"[{chat_id}] 전송 완료")
                await asyncio.sleep(1.5)
            except Exception as e:
                print(f"[{chat_id}] 전송 실패: {e}")

        print(f"[{datetime.now()}] 전체 전송 완료!")
    except Exception as e:
        print(f"전송 실패: {e}")

if __name__ == "__main__":
    print("테스트 시작")
    asyncio.run(send_message())
    print("완료!")