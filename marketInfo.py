import asyncio
import feedparser
from telegram import Bot
from datetime import datetime
from dotenv import load_dotenv
import os
import yfinance as yf
import html
import requests  # RSS 직접 가져오기 위해 추가

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("TELEGRAM_TOKEN 또는 CHAT_ID가 .env 파일에 없습니다!")

bot = Bot(token=BOT_TOKEN)

def get_us_market_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    summary = f"<b>【미국장 아침 브리핑 - {today} (서울 시간 기준)】</b>\n\n"

    # 1. 주요 지수 (yfinance)
    try:
        tickers = {
            '다우존스': '^DJI',
            'S&P 500': '^GSPC',
            '나스닥': '^IXIC'
        }
        summary += "<b>📊 주요 지수 (최신 종가 / 변화율)</b>\n"
        for name, symbol in tickers.items():
            info = yf.Ticker(symbol).info
            price = info.get('regularMarketPrice') or info.get('previousClose', 'N/A')
            pct = info.get('regularMarketChangePercent', 'N/A')
            summary += f"・<b>{name}</b>: {price:,.2f} ({pct:+.2f}%)\n"
        summary += "\n"
    except Exception as e:
        summary += f"(지수 오류: {str(e)})\n\n"

    # 2. 섹터 동향
    try:
        sectors = {
            '기술 (IT)': 'XLK',
            '금융': 'XLF',
            '에너지': 'XLE',
            '소비재': 'XLY',
            '헬스케어': 'XLV',
            '산업': 'XLI'
        }
        summary += "<b>섹터별 변화율 (최근 종가 기준)</b>\n"
        for name, etf in sectors.items():
            pct = yf.Ticker(etf).info.get('regularMarketChangePercent', 'N/A')
            summary += f"・<b>{name}</b>: {pct:+.2f}%\n"
        summary += "\n"
    except Exception:
        summary += "(섹터 로드 실패)\n\n"

    # 3. 헤드라인 - requests + User-Agent로 우회 시도
    summary += "<b>🔥 오늘의 최신 경제 헤드라인 (최근 5개)</b>\n"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
        }
        url = 'https://www.yna.co.kr/rss/economy.xml'
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        if not feed.entries:
            summary += "(RSS에서 항목을 찾지 못했습니다)\n\n"
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

    # 4. 주목 포인트
    summary += "<b>📅 오늘 주목할 이벤트 & 포인트</b>\n"
    summary += "• Walmart 실적 발표 → 소비 심리 & 소매 섹터 방향성\n"
    summary += "• 유가 상승 지속 → 에너지 섹터 지지\n"
    summary += "• Fed 회의록 소화 중 → 금리 인하 기대 vs 인플레 우려\n"
    summary += "• AI/빅테크 랠리 여부 → Nvidia, Amazon 등 움직임\n\n"

    summary += "더 자세한 내용은 Yahoo Finance, CNBC에서 확인하세요!\n"
    summary += "#미국장 #경제브리핑"

    # 디버깅용 출력
    print("\n=== 실제로 보낼 메시지 일부 (디버깅용) ===\n")
    print(summary[:1200])
    print("\n==================================\n")

    return summary

async def send_message():
    try:
        message = get_us_market_summary()
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=False
        )
        print(f"[{datetime.now()}] 브리핑 전송 완료!")
    except Exception as e:
        print(f"전송 실패: {e}")

if __name__ == "__main__":
    print("테스트 시작")
    asyncio.run(send_message())
    print("완료!")