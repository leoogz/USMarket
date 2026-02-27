import asyncio
import feedparser
from telegram import Bot
from datetime import datetime
from dotenv import load_dotenv
import os
import json
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

# chat_ids.json 파일 경로
CHAT_IDS_FILE = os.path.join(os.path.dirname(__file__), 'chat_ids.json')

def load_chat_ids():
    """저장된 chat_id 목록을 파일에서 로드"""
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE, 'r') as f:
                return set(json.load(f))
    except Exception as e:
        print(f"chat_ids.json 로드 실패: {e}")
    return set()

def save_chat_ids(chat_ids):
    """chat_id 목록을 파일에 저장"""
    try:
        with open(CHAT_IDS_FILE, 'w') as f:
            json.dump(list(chat_ids), f)
    except Exception as e:
        print(f"chat_ids.json 저장 실패: {e}")

async def get_all_chat_ids():
    """저장된 chat_id + 새로운 업데이트에서 발견된 chat_id 반환"""
    # 1. 파일에서 기존 chat_id 로드
    chat_ids = load_chat_ids()
    
    # 2. 새 업데이트에서 chat_id 추가 수집
    try:
        updates = await bot.get_updates(limit=100, timeout=10)
        for update in updates:
            if update.message:
                chat_ids.add(str(update.message.chat.id))
            elif update.channel_post:
                chat_ids.add(str(update.channel_post.chat.id))
            elif update.my_chat_member:
                chat_ids.add(str(update.my_chat_member.chat.id))
        
        # 3. 새로 발견된 chat_id가 있으면 파일에 저장
        save_chat_ids(chat_ids)
    except Exception as e:
        print(f"업데이트 조회 실패: {e}")
    
    return list(chat_ids)

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
        tickers = {
            '다우존스': '^DJI', 
            'S&P 500': '^GSPC', 
            '나스닥': '^IXIC',
            '러셀 2000': '^RUT',
        }
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

    # VIX 공포지수
    try:
        summary += "<b>😱 VIX 공포지수</b>\n"
        vix = yf.Ticker('^VIX').info
        vix_price = vix.get('regularMarketPrice') or vix.get('previousClose', 0)
        vix_pct = vix.get('regularMarketChangePercent', 0)
        # VIX는 높을수록 공포, 낮을수록 안정
        if vix_price >= 30:
            vix_status = "🚨 극심한 공포"
        elif vix_price >= 20:
            vix_status = "⚠️ 불안"
        else:
            vix_status = "✅ 안정"
        vix_color = "🔴" if vix_pct >= 0 else "🔵"
        summary += f"・<b>VIX</b>: {vix_price:.2f} ({vix_pct:+.2f}%) {vix_color} {vix_status}\n"
        summary += "  <i>(20 미만: 안정 / 20~30: 불안 / 30 이상: 공포)</i>\n\n"
    except Exception as e:
        summary += f"(VIX 로드 실패)\n\n"

    try:
        # S&P 500 비중 상위 8개 섹터 (대표 기업 포함)
        sectors = {
            '기술': {'etf': 'XLK', 'top': 'AAPL, MSFT, NVDA'},
            '헬스케어': {'etf': 'XLV', 'top': 'UNH, JNJ, LLY'},
            '금융': {'etf': 'XLF', 'top': 'BRK.B, JPM, V'},
            '경기소비재': {'etf': 'XLY', 'top': 'AMZN, TSLA, HD'},
            '통신서비스': {'etf': 'XLC', 'top': 'META, GOOGL, NFLX'},
            '산업재': {'etf': 'XLI', 'top': 'GE, CAT, UNP'},
            '필수소비재': {'etf': 'XLP', 'top': 'PG, KO, PEP'},
            '에너지': {'etf': 'XLE', 'top': 'XOM, CVX, COP'},
        }
        summary += "<b>📈 섹터별 변화율 (S&P 500 비중순)</b>\n"
        for name, data in sectors.items():
            pct = yf.Ticker(data['etf']).info.get('regularMarketChangePercent', 'N/A')
            color = "🔴" if pct >= 0 else "🔵"
            summary += f"・<b>{name}</b>: {pct:+.2f}% {color} ({data['top']})\n"
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

    # 원자재 (금, 원유)
    try:
        summary += "<b>🛢️ 원자재</b>\n"
        # 금
        gold = yf.Ticker('GC=F').info
        gold_price = gold.get('regularMarketPrice') or gold.get('previousClose', 0)
        gold_pct = gold.get('regularMarketChangePercent', 0)
        gold_color = "🔴" if gold_pct >= 0 else "🔵"
        summary += f"・<b>금</b>: ${gold_price:,.2f} ({gold_pct:+.2f}%) {gold_color}\n"
        
        # WTI 원유
        oil = yf.Ticker('CL=F').info
        oil_price = oil.get('regularMarketPrice') or oil.get('previousClose', 0)
        oil_pct = oil.get('regularMarketChangePercent', 0)
        oil_color = "🔴" if oil_pct >= 0 else "🔵"
        summary += f"・<b>WTI 원유</b>: ${oil_price:,.2f} ({oil_pct:+.2f}%) {oil_color}\n"
        summary += "\n"
    except Exception as e:
        summary += f"(원자재 로드 실패)\n\n"

    # 미국 국채 금리
    try:
        summary += "<b>📈 미국 국채 금리</b>\n"
        tnx = yf.Ticker('^TNX').info
        tnx_price = tnx.get('regularMarketPrice') or tnx.get('previousClose', 0)
        tnx_pct = tnx.get('regularMarketChangePercent', 0)
        tnx_color = "🔴" if tnx_pct >= 0 else "🔵"
        summary += f"・<b>10년물</b>: {tnx_price:.3f}% ({tnx_pct:+.2f}%) {tnx_color}\n"
        summary += "\n"
    except Exception as e:
        summary += f"(금리 로드 실패)\n\n"

    summary += "<b>🔥 오늘의 주요 증시 뉴스 (인기순)</b>\n"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        # 네이버 증권 - 주요 뉴스 페이지에서 많이 본 뉴스 추출
        response = requests.get('https://finance.naver.com/news/mainnews.naver', headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # mode=RANK 링크가 많이 본 뉴스
        news_items = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            title = link.get_text(strip=True)
            if 'mode=RANK' in href and title and len(title) > 10:
                # article_id와 office_id 추출
                import re
                article_match = re.search(r'article_id=(\d+)', href)
                office_match = re.search(r'office_id=(\d+)', href)
                if article_match and office_match:
                    news_items.append({
                        'title': title, 
                        'href': href,
                        'article_id': article_match.group(1),
                        'office_id': office_match.group(1)
                    })
        
        if not news_items:
            summary += "(뉴스 항목 없음)\n\n"
        else:
            for item in news_items[:5]:
                title = html.escape(item['title'])
                # 네이버 뉴스 원문 링크
                news_url = f"https://n.news.naver.com/mnews/article/{item['office_id']}/{item['article_id']}"
                short_title = title[:50] + "..." if len(title) > 50 else title
                
                # 기사 본문 첫 문장 가져오기
                try:
                    article_resp = requests.get(news_url, headers=headers, timeout=5)
                    if article_resp.status_code == 200:
                        article_soup = BeautifulSoup(article_resp.content, 'html.parser')
                        # 본문 영역 찾기
                        article_body = article_soup.select_one('#dic_area, .newsct_article, article')
                        if article_body:
                            text = article_body.get_text(strip=True)
                            # 첫 80자 추출
                            snippet = text[:80].replace('\n', ' ').strip()
                            if len(text) > 80:
                                snippet += "..."
                            summary += f"• <a href=\"{news_url}\">{short_title}</a>\n  <i>→ {html.escape(snippet)}</i>\n"
                        else:
                            summary += f"• <a href=\"{news_url}\">{short_title}</a>\n"
                    else:
                        summary += f"• <a href=\"{news_url}\">{short_title}</a>\n"
                except:
                    summary += f"• <a href=\"{news_url}\">{short_title}</a>\n"
            summary += "\n"
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