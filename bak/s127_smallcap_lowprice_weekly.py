"""
S127 小盘低价周频
========================
S67的低价股周频逻辑 + 成交额筛选。
在CSI1000中选成交额最低的30% + 价格后30%分位。
核心假设：低价+小盘=双因子叠加效果。
"""
LABEL = "S127 小盘低价周频"
FOLDER = "S127-小盘低价周频"
FREQ = "weekly"
TAGS = ["smallcap", "lowprice", "weekly"]
POOL = "csi1000"

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from core.backtest_utils import (
    DataLoader, BacktestEngine, Visualizer, TradingRules, RESULTS_BASE,
    print_stats, COMMISSION, SLIPPAGE, weekly_filter, stock_pool_mask,)

STOCK_POOL = "csi1000"

def generate_signal(close, dates=None, volume=None, **kw):
    first = weekly_filter(dates)
    n_stocks, n_days = close.shape
    signal = np.zeros(close.shape, dtype=bool)

    for t in range(5, n_days):
        if not first[t]:
            continue
        c = close[:, t]
        v = volume[:, t] if volume is not None else np.ones(n_stocks)

        valid = (c > 1.0) & (c <= 200)
        if valid.sum() < 50:
            signal[:, t] = valid
            continue

        # 条件1：成交额后30%（小盘筛选）
        amt = c * v
        amt_valid = amt[valid]
        if len(amt_valid) < 20:
            signal[:, t] = valid
            continue
        amt_thr = np.nanpercentile(amt_valid, 30)
        cond_small = (amt <= amt_thr) & valid
        if cond_small.sum() < 20:
            amt_thr40 = np.nanpercentile(amt_valid, 40)
            cond_small = (amt <= amt_thr40) & valid
        if cond_small.sum() < 15:
            signal[:, t] = valid
            continue

        # 条件2：价格后30%分位（低价筛选）
        price_thr30 = np.nanpercentile(c[cond_small], 30)
        cond_lowprice = (c <= price_thr30) & cond_small

        if cond_lowprice.sum() < 15:
            price_thr40 = np.nanpercentile(c[cond_small], 40)
            cond_lowprice = (c <= price_thr40) & cond_small

        cond = cond_lowprice
        if cond.sum() < 10:
            cond = cond_small
        signal[:, t] = cond

    for t in range(1, n_days):
        if not first[t]:
            signal[:, t] = signal[:, t-1]
    return signal


def main():
    label = "S127 小盘低价周频"
    folder = "S127-小盘低价周频"
    print("=" * 60); print(f"  {label}"); print("=" * 60)
    loader = DataLoader().load()
    close = loader.close; dates = loader.dates
    print(f"[生成信号] {label}...")
    signal = generate_signal(close, dates, volume=loader.volume)
    per_day = signal.sum(axis=0)
    print(f"日均持股: {per_day.mean():.0f} 只, 信号天数: {(per_day > 0).sum()}")
    rules = TradingRules(close, loader.open_price, loader.volume,
                         loader.codes, loader.names_arr,
                         loader.is_st, loader.exchange)
    engine = BacktestEngine(commission=COMMISSION, slippage=SLIPPAGE)
    engine.run(close, signal, dates, trading_rules=rules)
    print_stats(engine.stats)
    Visualizer.plot_and_save(engine, os.path.join(RESULTS_BASE, folder), label)
    print("=" * 60)

if __name__ == "__main__":
    main()
