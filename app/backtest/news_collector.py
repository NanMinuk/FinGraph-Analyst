"""
날짜별 뉴스 자동 수집기
========================
네이버 뉴스 검색에서 날짜 범위 내 뉴스를 수집하고
/ingest API로 자동 전송합니다.

사용법:
  python -m app.backtest.news_collector \
    --company 삼성전자 \
    --start 2026-03-01 \
    --end 2026-03-31 \
    --per-day 10
"""

import argparse
import time
import os
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_URL", "http://localhost:8000")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Encoding": "gzip, deflate",
}


# ─────────────────────────────────────────────
# 날짜별 뉴스 URL 수집
# ─────────────────────────────────────────────

def fetch_news_urls_for_date(query: str, target_date: date, max_count: int = 10) -> list[str]:
    """특정 날짜의 뉴스 URL 수집"""
    date_str = target_date.strftime("%Y.%m.%d")
    date_param = target_date.strftime("%Y%m%d")

    urls = []
    start = 1

    while len(urls) < max_count:
        search_url = (
            f"https://search.naver.com/search.naver"
            f"?where=news&query={requests.utils.quote(query)}"
            f"&sort=1"
            f"&ds={date_str}&de={date_str}"
            f"&nso=so:dd,p:from{date_param}to{date_param}"
            f"&start={start}"
        )

        try:
            resp = requests.get(search_url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"    [오류] {e}")
            break

        # 네이버 뉴스 링크만 추출
        new_links = [
            a.get("href")
            for a in soup.find_all("a", href=True)
            if "n.news.naver.com" in a.get("href", "")
            and a.get("href") not in urls
        ]

        if not new_links:
            break

        urls.extend(new_links)
        start += 10
        time.sleep(0.3)

    return urls[:max_count]


def collect_urls_by_date(
    company: str,
    start: date,
    end: date,
    per_day: int = 10,
) -> dict[date, list[str]]:
    """날짜 범위 내 날짜별 URL 수집"""
    by_date = {}

    d = start
    while d <= end:
        print(f"  {d} 수집 중...", end=" ", flush=True)
        urls = fetch_news_urls_for_date(company, d, per_day)
        if urls:
            by_date[d] = urls
            print(f"{len(urls)}개")
        else:
            print("없음")
        d += timedelta(days=1)
        time.sleep(0.5)

    return by_date


# ─────────────────────────────────────────────
# /ingest API 전송
# ─────────────────────────────────────────────

def send_to_ingest(urls: list[str]) -> dict:
    resp = requests.post(
        f"{API_BASE}/ingest",
        json={"urls": urls},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


# ─────────────────────────────────────────────
# main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="날짜별 뉴스 자동 수집")
    parser.add_argument("--company", required=True, help="검색 키워드 (예: 삼성전자)")
    parser.add_argument("--start",   required=True, help="시작일 (예: 2026-03-01)")
    parser.add_argument("--end",     required=True, help="종료일 (예: 2026-03-31)")
    parser.add_argument("--per-day", type=int, default=10, help="하루 최대 기사 수 (기본: 10)")
    parser.add_argument("--dry-run", action="store_true", help="URL만 수집하고 ingest 안 함")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end   = datetime.strptime(args.end,   "%Y-%m-%d").date()

    print(f"\n수집 대상: {args.company} / {start} ~ {end} (하루 최대 {args.per_day}개)")
    print("=" * 50)

    by_date = collect_urls_by_date(args.company, start, end, args.per_day)

    total = sum(len(v) for v in by_date.values())
    print(f"\n총 {len(by_date)}일치 {total}개 URL 수집 완료")

    if args.dry_run:
        print("\n[dry-run 모드 — ingest 생략]")
        for d in sorted(by_date):
            print(f"\n{d} ({len(by_date[d])}개)")
            for url in by_date[d]:
                print(f"  {url}")
        return

    # 날짜별 ingest
    print("\nIngest 시작...")
    success, failed = 0, 0

    for d in sorted(by_date):
        urls = by_date[d]
        print(f"\n{d} ({len(urls)}개) 전송 중...", end=" ", flush=True)
        try:
            result = send_to_ingest(urls)
            print("완료")
            success += len(urls)
        except Exception as e:
            print(f"실패: {e}")
            failed += len(urls)
        time.sleep(1)

    print(f"\n{'='*50}")
    print(f"완료: 성공 {success}개 / 실패 {failed}개")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
