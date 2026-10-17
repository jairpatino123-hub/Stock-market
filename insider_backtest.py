"""Backtest an insider-filing-count strategy against buy-and-hold.

Expected input CSV: insider_signals.csv
Required columns:
    filingDate, insider_filing_count

Example:
    python insider_backtest.py --ticker AAPL --threshold 2 --holding-period 10

Install dependencies:
    pip install yfinance pandas numpy
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


def backtest_with_real_insiders(
    stock_ticker: str,
    insider_signals_df: pd.DataFrame,
    threshold: int = 1,
    holding_period: int = 5,
) -> pd.DataFrame:
    """Backtest a long-only strategy using daily SEC insider-filing counts.

    A signal is generated when insider_filing_count >= threshold. The position
    starts on the next trading day to avoid using a signal before it is known,
    and stays active for up to holding_period trading days.

    Note: filing counts alone do not indicate whether insiders bought or sold.
    This is a simple research example, not investment advice.
    """
    required = {"filingDate", "insider_filing_count"}
    missing = required.difference(insider_signals_df.columns)
    if missing:
        raise ValueError(f"insider_signals_df is missing required columns: {sorted(missing)}")
    if threshold < 1:
        raise ValueError("threshold must be at least 1")
    if holding_period < 1:
        raise ValueError("holding_period must be at least 1")
    if insider_signals_df.empty:
        raise ValueError("insider_signals_df is empty")

    signals = insider_signals_df.loc[:, ["filingDate", "insider_filing_count"]].copy()
    signals["filingDate"] = pd.to_datetime(signals["filingDate"], errors="coerce", utc=True)
    signals = signals.dropna(subset=["filingDate"])
    # Convert timestamps to timezone-naive calendar dates before joining daily bars.
    signals["filingDate"] = signals["filingDate"].dt.tz_convert(None).dt.normalize()
    signals["insider_filing_count"] = pd.to_numeric(
        signals["insider_filing_count"], errors="coerce"
    ).fillna(0)
    # Combine multiple source rows for the same date into one daily count.
    signals = signals.groupby("filingDate", as_index=False)["insider_filing_count"].sum()
    if signals.empty:
        raise ValueError("No valid filingDate values were found")

    start_date = signals["filingDate"].min().strftime("%Y-%m-%d")
    # yfinance treats end as exclusive, so add one day to include the final signal date.
    end_date = (signals["filingDate"].max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"Downloading stock data for {stock_ticker} ({start_date} to {end_date})...")
    stock_data = yf.download(
        stock_ticker,
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False,
    )
    if stock_data.empty:
        raise RuntimeError(f"No price data returned for ticker {stock_ticker!r}")

    if isinstance(stock_data.columns, pd.MultiIndex):
        stock_data.columns = stock_data.columns.get_level_values(0)

    if "Close" not in stock_data.columns:
        raise RuntimeError("Downloaded price data does not contain a Close column")

    df = pd.DataFrame(index=pd.to_datetime(stock_data.index).tz_localize(None))
    df.index.name = "date"
    df["close"] = pd.to_numeric(stock_data["Close"], errors="coerce")
    df["daily_return"] = df["close"].pct_change()

    signals = signals.set_index("filingDate")
    signals.index.name = "date"
    df = df.join(signals, how="left")
    df["insider_filing_count"] = df["insider_filing_count"].fillna(0)

    df["signal"] = (df["insider_filing_count"] >= threshold).astype(int)
    # Shift by one trading day so the strategy cannot earn the signal day's return.
    df["position"] = (
        df["signal"].rolling(window=holding_period, min_periods=1).max().shift(1).fillna(0)
    )
    df["strategy_return"] = df["daily_return"].fillna(0) * df["position"]
    df["cum_stock_return"] = (1 + df["daily_return"].fillna(0)).cumprod() - 1
    df["cum_strategy_return"] = (1 + df["strategy_return"]).cumprod() - 1

    buy_hold = df["cum_stock_return"].iloc[-1]
    strategy = df["cum_strategy_return"].iloc[-1]
    print("\n--- Backtest Results (adjusted close; excludes fees/slippage) ---")
    print(f"Ticker: {stock_ticker.upper()}")
    print(f"Threshold: {threshold} filing(s); holding period: {holding_period} trading days")
    print(f"Buy & Hold Cumulative Return: {buy_hold:.2%}")
    print(f"Insider Strategy Cumulative Return: {strategy:.2%}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest an insider-filing-count strategy.")
    parser.add_argument("--ticker", default="AAPL", help="Stock ticker (default: AAPL)")
    parser.add_argument("--signals", default="insider_signals.csv", help="CSV input path")
    parser.add_argument("--threshold", type=int, default=2, help="Minimum daily filing count (default: 2)")
    parser.add_argument("--holding-period", type=int, default=10, help="Trading days to hold (default: 10)")
    parser.add_argument("--output", default="backtest_results.csv", help="Output CSV path")
    args = parser.parse_args()

    input_path = Path(args.signals)
    if not input_path.exists():
        raise SystemExit(
            f"Could not find {input_path}. Provide a CSV with filingDate and "
            "insider_filing_count columns (for example, --signals insider_signals.csv)."
        )

    insider_df = pd.read_csv(input_path)
    strategy_df = backtest_with_real_insiders(
        args.ticker,
        insider_df,
        threshold=args.threshold,
        holding_period=args.holding_period,
    )
    columns = [
        "close",
        "insider_filing_count",
        "signal",
        "position",
        "daily_return",
        "strategy_return",
        "cum_stock_return",
        "cum_strategy_return",
    ]
    strategy_df[columns].to_csv(args.output, index=True, index_label="date")
    print(f"\nSaved daily results to {args.output}")
    print(strategy_df[columns].tail().to_string())


if __name__ == "__main__":
    main()
