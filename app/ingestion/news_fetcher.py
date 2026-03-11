import re
from typing import Dict, Any, Optional

import requests
from bs4 import BeautifulSoup


def extract_naver_news_text(soup: BeautifulSoup) -> str:
    candidates = [
        "#dic_area",
        "#newsct_article",
        ".newsct_article _article_body",
        ".go_trans._article_content",
    ]

    for selector in candidates:
        node = soup.select_one(selector)
        if node:
            text = clean_text(node.get_text(" ", strip=True))
            if len(text) > 100:
                return text

    return ""

def extract_naver_news_date(soup: BeautifulSoup) -> Optional[str]:
    meta_candidates = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "nv:news:published_date"}),
        ("meta", {"name": "publish-date"}),
    ]

    for tag_name, attrs in meta_candidates:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get("content"):
            return clean_text(tag["content"])

    # 본문 상단 날짜 영역 fallback
    date_selectors = [
        ".media_end_head_info_datestamp_time",
        ".media_end_head_info_datestamp",
        ".datedate",
    ]

    for selector in date_selectors:
        node = soup.select_one(selector)
        if node:
            text = clean_text(node.get_text(" ", strip=True))
            if text:
                return text

    return None

def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.text:
        return clean_text(soup.title.text)

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return clean_text(og_title["content"])

    return "Untitled"


def extract_source(url: str, soup: BeautifulSoup) -> str:
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        return clean_text(og_site["content"])

    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    if match:
        return match.group(1)

    return "Unknown"


def extract_date(soup: BeautifulSoup) -> Optional[str]:
    date_meta_candidates = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "pubdate"}),
        ("meta", {"name": "publish-date"}),
        ("meta", {"name": "date"}),
        ("meta", {"name": "article:published_time"}),
    ]

    for tag_name, attrs in date_meta_candidates:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get("content"):
            return clean_text(tag["content"])

    return None


def extract_main_text(soup: BeautifulSoup) -> str:
    # 우선 article 태그 시도
    article = soup.find("article")
    if article:
        paragraphs = [clean_text(p.get_text(" ", strip=True)) for p in article.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        if paragraphs:
            return " ".join(paragraphs)

    # fallback: 전체 p 태그 중 긴 문장들 수집
    paragraphs = [clean_text(p.get_text(" ", strip=True)) for p in soup.find_all("p")]
    paragraphs = [p for p in paragraphs if len(p) > 30]

    return " ".join(paragraphs[:30])


def fetch_news_from_url(url: str, timeout: int = 10) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title = extract_title(soup)
    source = extract_source(url, soup)
    if "n.news.naver.com" in url or "news.naver.com" in url:
        date = extract_naver_news_date(soup)
        text = extract_naver_news_text(soup)
        if not text:
            text = extract_main_text(soup)
    else:
        date = extract_date(soup)
        text = extract_main_text(soup)

    return {
        "url": url,
        "title": title,
        "source": source,
        "date": date,
        "text": text,
    }