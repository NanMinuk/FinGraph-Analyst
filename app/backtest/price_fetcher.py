"""
주가 데이터 수집
================
FinanceDataReader로 종목 주가를 가져옵니다.
"""

from datetime import date
from typing import Optional
import pandas as pd


def fetch_stock_prices(
    ticker: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    종목 주가 데이터 반환.

    Returns:
        DataFrame with columns: Date, Open, High, Low, Close, Volume
        Date가 index
    """
    try:
        import FinanceDataReader as fdr
    except ImportError:
        raise ImportError("pip install finance-datareader 를 먼저 실행하세요.")

    df = fdr.DataReader(ticker, start=str(start), end=str(end))
    df.index = pd.to_datetime(df.index).date
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df = df.sort_index()
    return df


def get_daily_returns(df: pd.DataFrame) -> pd.Series:
    """날짜별 일간 수익률 (종가 기준)"""
    return df["Close"].pct_change()


def get_forward_return(
    df: pd.DataFrame,
    signal_date: date,
    hold_days: int = 1,
) -> Optional[float]:
    """
    signal_date 종가에 매수 → hold_days 후 종가에 청산 수익률.
    거래일 기준으로 계산합니다.
    """
    dates = sorted(df.index)

    try:
        idx = dates.index(signal_date)
    except ValueError:
        # signal_date가 거래일이 아니면 다음 거래일 사용
        future = [d for d in dates if d >= signal_date]
        if not future:
            return None
        idx = dates.index(future[0])

    buy_idx = idx
    sell_idx = buy_idx + hold_days

    if sell_idx >= len(dates):
        return None

    buy_price  = df.loc[dates[buy_idx],  "Close"]
    sell_price = df.loc[dates[sell_idx], "Close"]

    return (sell_price - buy_price) / buy_price
