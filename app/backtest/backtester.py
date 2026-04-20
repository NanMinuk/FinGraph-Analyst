"""
백테스팅 엔진
=============
매매 시그널 + 주가 데이터 → 수익률 지표 계산
"""

from datetime import date
from typing import Optional
import pandas as pd

from app.backtest.price_fetcher import get_forward_return


def run_backtest(
    signals: dict[date, str],
    price_df: pd.DataFrame,
    hold_days: int = 1,
) -> dict:
    """
    T+N 전략: 시그널 당일 매수 → N거래일 후 청산.
    거래일만 사용, 같은 거래일 중복 방지.
    """
    trades = []
    used_buy_dates = set()
    trading_days = sorted(price_df.index)
    trading_day_set = set(trading_days)

    for signal_date, signal in sorted(signals.items()):
        if signal not in ("buy", "sell"):
            continue

        # 비거래일이면 다음 거래일로
        future = [d for d in trading_days if d >= signal_date]
        if not future:
            continue
        actual_buy_date = future[0]

        if actual_buy_date in used_buy_dates:
            continue
        used_buy_dates.add(actual_buy_date)

        ret = get_forward_return(price_df, actual_buy_date, hold_days)
        if ret is None:
            continue

        actual_return = ret if signal == "buy" else -ret

        trades.append({
            "date": str(actual_buy_date),
            "signal": signal,
            "return": round(float(actual_return), 6),
            "win": bool(actual_return > 0),
        })

    metrics = compute_metrics(trades)
    bnh = buy_and_hold_return(price_df)

    return {
        "trades": trades,
        "metrics": metrics,
        "buy_and_hold_return": round(bnh, 4) if bnh is not None else None,
    }


def run_position_backtest(
    signals: dict[date, str],
    price_df: pd.DataFrame,
) -> dict:
    """
    포지션 전략: buy 시그널에 진입 → sell 시그널에 청산.
    연속 buy는 유지, sell이 와야 팔고, 다음 buy에 재진입.
    거래일만 사용.
    """
    trading_days = sorted(price_df.index)
    trading_day_set = set(trading_days)

    # 시그널을 거래일만 필터링
    trading_signals = {
        d: s for d, s in signals.items() if d in trading_day_set
    }

    trades = []
    in_position = False
    entry_date = None
    entry_price = None

    for signal_date in sorted(trading_signals.keys()):
        signal = trading_signals[signal_date]
        price = float(price_df.loc[signal_date, "Close"])

        if signal == "buy" and not in_position:
            in_position = True
            entry_date = signal_date
            entry_price = price

        elif signal == "sell" and in_position:
            ret = (price - entry_price) / entry_price
            trades.append({
                "entry_date": str(entry_date),
                "exit_date": str(signal_date),
                "signal": "buy→sell",
                "return": round(float(ret), 6),
                "win": bool(ret > 0),
            })
            in_position = False
            entry_date = None
            entry_price = None

    # 기간 종료 시 포지션이 남아있으면 마지막 거래일 종가에 청산
    if in_position and entry_price is not None:
        last_date = trading_days[-1]
        last_price = float(price_df["Close"].iloc[-1])
        ret = (last_price - entry_price) / entry_price
        trades.append({
            "entry_date": str(entry_date),
            "exit_date": str(last_date),
            "signal": "buy→종료청산",
            "return": round(float(ret), 6),
            "win": bool(ret > 0),
        })

    metrics = compute_metrics(trades)
    bnh = buy_and_hold_return(price_df)

    return {
        "trades": trades,
        "metrics": metrics,
        "buy_and_hold_return": round(bnh, 4) if bnh is not None else None,
    }


def compute_metrics(trades: list[dict]) -> dict:
    """성과 지표 계산"""
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": None,
            "avg_return": None,
            "cumulative_return": None,
            "sharpe_ratio": None,
        }

    returns = [t["return"] for t in trades]
    wins    = [t for t in trades if t["win"]]

    win_rate = len(wins) / len(trades)
    avg_return = sum(returns) / len(returns)
    cumulative = 1.0
    for r in returns:
        cumulative *= (1 + r)
    cumulative_return = cumulative - 1.0

    import statistics
    if len(returns) > 1:
        std = statistics.stdev(returns)
        sharpe = (avg_return / std) * (252 ** 0.5) if std > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        "total_trades":       len(trades),
        "win_rate":           round(win_rate, 4),
        "avg_return":         round(avg_return, 4),
        "cumulative_return":  round(cumulative_return, 4),
        "sharpe_ratio":       round(sharpe, 4),
    }


def buy_and_hold_return(price_df: pd.DataFrame) -> Optional[float]:
    """단순 보유 수익률 (첫날 종가 → 마지막날 종가)"""
    if price_df.empty or len(price_df) < 2:
        return None
    first = price_df["Close"].iloc[0]
    last  = price_df["Close"].iloc[-1]
    return (last - first) / first


def format_report(result: dict, ticker: str, strategy: str = "T+1") -> str:
    """결과를 텍스트 리포트로 포맷"""
    m   = result["metrics"]
    bnh = result["buy_and_hold_return"]
    trades = result["trades"]

    lines = [
        f"{'='*50}",
        f"  백테스팅 결과 — {ticker} ({strategy})",
        f"{'='*50}",
        f"  총 거래 횟수  : {m['total_trades']}회",
        f"  승률          : {m['win_rate']:.1%}" if m["win_rate"] is not None else "  승률: N/A",
        f"  평균 수익률   : {m['avg_return']:.2%}" if m["avg_return"] is not None else "  평균 수익률: N/A",
        f"  누적 수익률   : {m['cumulative_return']:.2%}" if m["cumulative_return"] is not None else "  누적 수익률: N/A",
        f"  샤프 비율     : {m['sharpe_ratio']:.2f}" if m["sharpe_ratio"] is not None else "  샤프 비율: N/A",
        f"  Buy & Hold    : {bnh:.2%}" if bnh is not None else "  Buy & Hold: N/A",
        "",
    ]

    if bnh is not None and m["cumulative_return"] is not None:
        diff = m["cumulative_return"] - bnh
        lines.append(f"  전략 초과수익 : {diff:+.2%}")

    lines += ["", "  거래 내역:"]
    for t in trades:
        mark = "✓" if t["win"] else "✗"
        if "entry_date" in t:
            lines.append(f"  {mark} {t['entry_date']}→{t['exit_date']} [{t['signal']}] {t['return']:+.2%}")
        else:
            lines.append(f"  {mark} {t['date']} [{t['signal']:4s}] {t['return']:+.2%}")

    lines.append(f"{'='*50}")
    return "\n".join(lines)
