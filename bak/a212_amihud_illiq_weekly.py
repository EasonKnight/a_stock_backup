#!/usr/bin/env python
"""A212 非流动性溢价周频 rank(amihud_Nd) → z-score，decay_linear 平滑。流动性差=预期收益高"""
LABEL="A212 非流动性溢价周频"; FOLDER="A212-非流动性溢价周频"; FREQ="weekly"; TAGS=["alpha","illiquidity"]; POOL="csi1000"
import sys,os; sys.path.insert(0,os.path.join(os.path.dirname(__file__),".."))
import numpy as np
from core.backtest_utils import *
from core.alpha_utils import zscore_rank, decay_linear, amihud_illiq
DECAY=5; STOCK_POOL="csi1000"
def generate_alpha(close,dates=None,volume=None,**kw):
    n_stocks,n_days=close.shape; a=np.zeros((n_stocks,n_days)); f=weekly_filter(dates); h=np.zeros((n_stocks,n_days))
    for t in range(n_days):
        h[:,t]=amihud_illiq(close,volume,t,20)
        if not f[t]:
            if t>0: a[:,t]=a[:,t-1]
            continue
        raw=decay_linear(h,t,DECAY); v=close[:,t]>0.5; a[:,t]=zscore_rank(raw,v)
    return a
def main():
    l=LABEL; print("="*60); print(f"  {l}"); print("="*60)
    ld=DataLoader().load(); c=ld.close; d=ld.dates
    p=stock_pool_mask(ld.codes,STOCK_POOL); v=(c>0.5)&p[:,None]
    print(f"[生成] {l}..."); al=generate_alpha(c,d,volume=ld.volume); al[~v]=-np.inf; print(f"  日均选股: {(al>0).sum(axis=0).mean():.0f}")
    r=TradingRules(c,ld.open_price,ld.volume,ld.codes,ld.names_arr,ld.is_st,ld.exchange)
    eng=BacktestEngine(COMMISSION,SLIPPAGE,alpha_mode=True); eng.run(c,al,d,trading_rules=r,valid=v)
    print_stats(eng.stats); Visualizer.print_trades(eng); Visualizer.plot_and_save(eng,os.path.join(RESULTS_BASE,FOLDER),l); print("="*60)
if __name__=="__main__": main()
