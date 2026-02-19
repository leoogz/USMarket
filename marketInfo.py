import asyncio
import feedparser
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime
from dotenv import load_dotenv
import os

# ---------------- 설정 부분 ----------------
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("TELEGRAM_TOKEN 또는 CHAT_ID가 .env 파일에 없습니다! 확인해주세요.")

bot = Bot(token=BOT_TOKEN)

# ---------------- 뉴스 & 지표 가져오기 함수 ----------------
def get_us_market_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    summary = f"【미국장 아침 브리핑 테스트 - {today}】\n\n"

    # 1. 주요 뉴스 (연합뉴스 경제 RSS - 한국 시간 기준 최신)
    feed = feedparser.parse('https://www.yna.co.kr/rss/economy.xml')
    
    summary += "🔥 주요 경제 뉴스 (최근 5개)\n"
    for entry in feed.entries[:5]:
        title = entry.title
        link = entry.link
        published = entry.get('published', 'N/A')
        summary += f"📰 {title}\n   {published}\n   {link[:100]}...\n\n"

    # 2. 미국 주요 지수 (네이버 금융 크롤링)
    try:
        url = "https://finance.naver.com/world/"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')

        # 2026년 현재 페이지 구조 기준으로 업데이트된 선택자 예시
        # (개발자 도구 F12로 확인 추천 - li 요소 안에 a[href]와 .num 클래스 사용)
        indices = {
            '다우존스 (DJI)': 'DJI',
            '나스닥 (IXIC)': 'IXIC',
            'S&P 500 (SPX)': 'SPX'
        }

        summary += "📊 미국 주요 지수 (네이버 금융 기준, 최신 종가)\n"
        for name, symbol in indices.items():
            # 해당 symbol이 포함된 링크 안의 .num 요소 찾기
            elem = soup.find('a', href=lambda h: h and symbol in h)
            if elem:
                num_elem = elem.find_next(class_='num') or elem.find(class_='num')
                change_elem = elem.find_next(class_=['num_up', 'num_down']) or elem.find(['num_up', 'num_down'])
                
                value = num_elem.text.strip() if num_elem else "N/A"
                change = change_elem.text.strip() if change_elem else ""
                summary += f"・{name}: {value} {change}\n"
            else:
                summary += f"・{name}: 데이터 없음\n"

    except Exception as e:
        summary += f"(지수 가져오기 실패: {str(e)})\n\n"

    summary += "\n더 자세한 내용은 Yahoo Finance나 CNBC 확인하세요!\n#미국장 #경제브리핑 (테스트 모드)"

    return summary

# ---------------- Telegram 보내기 (비동기) ----------------
async def send_message():
    try:
        message = get_us_market_summary()
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        print(f"[{datetime.now()}] 브리핑 전송 완료! Telegram 확인하세요.")
    except Exception as e:
        print(f"전송 실패: {e}")
        print("가능한 원인: CHAT_ID 잘못됨, 토큰 문제, 네트워크 등")

# ---------------- 즉시 실행 (테스트용) ----------------
if __name__ == "__main__":
    print("경제 뉴스 봇 테스트 모드 시작!")
    print("지금 바로 Telegram으로 브리핑을 보냅니다...")

    asyncio.run(send_message())

    print("테스트 완료! 잘 보냈으면 .env와 코드가 제대로 동작하는 것")
    print("스케줄 넣고 싶을 때 주석 풀고 launchd 등으로 백그라운 실행을 알아보자")