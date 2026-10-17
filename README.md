# Stock-market

## Insider-filing backtest

This repository includes `insider_backtest.py`, a Python backtest that compares a simple strategy based on daily insider-filing counts with buy-and-hold returns.

### Setup

```bash
python -m pip install -r requirements.txt
```

### Prepare your input data

Create `insider_signals.csv` with these columns:

| filingDate | insider_filing_count |
|---|---:|
| 2025-01-15 | 2 |
| 2025-02-03 | 1 |

Use actual filing dates and daily filing counts from your source. The script does not retrieve SEC insider data itself; it expects this CSV as input.

### Run

```bash
python insider_backtest.py --ticker AAPL --threshold 2 --holding-period 10
```

Optional arguments:

- `--signals`: input CSV path (default: `insider_signals.csv`)
- `--threshold`: minimum filing count to trigger a signal (default: `2`)
- `--holding-period`: holding duration in trading days (default: `10`)
- `--output`: results CSV path (default: `backtest_results.csv`)

The script writes daily prices, signals, positions, daily returns, and cumulative returns to the output CSV. It uses adjusted prices, shifts positions to the next trading day to avoid earning the signal day's return, and does not include transaction costs, slippage, or taxes.

**Important:** A filing count does not distinguish insider purchases from sales and is not, by itself, a directional buy signal. This is an educational backtest, not investment advice.
