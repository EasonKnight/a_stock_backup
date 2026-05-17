#!/usr/bin/env python
"""A219 ILQ长窗口40d — 延长Amihud计算窗口到40天，捕捉更稳定的非流动性溢价，减少噪声"""
LABEL="A219 非流动性溢价40d周频"; FOLDER="A219-非流动性溢价40d周频"; FREQ="weekly"; TAGS=["alpha","illiquidity","longlookback"]; POOL="csi1000"
import sys,os; sys.path.insert(0,os.path.join(os.path.dirname(__file__),".."))
import numpy as np
from core.backtest_utils import *
from core.alpha_utils import zscore_rank, decay_linear, amihud_illiq
DECAY=5; STOCK_POOL="csi1000"
def generate_alpha(close,dates=None,volume=None,**kw):
    n_s,n_d=close.shape; a=np.zeros((n_s,n_d)); f=weekly_filter(dates); h=np.zeros((n_s,n_d))
    for t in range(n_d):
        h[:,t]=amihud_illiq(close,volume,t,40)
        if not f[t]:
            if t>0: a[:,t]=a[:,t-1]
            continue
        raw=decay_linear(h,t,DECAY); v=close[:,t]>0.5; a[:,t]=zscore_rank(raw,v)
    return a
def main():
    l=LABEL; print("="*60); print(f"  {l}"); print("="*60)
    ld=DataLoader().load(); c=ld.close; d=ld.dates
    p=stock_pool_mask(ld.codes,STOCK_POOL); v=(c>0.5)&p[:,None]
    print(f"[生成] {l}..."); al=generate_alpha(c,d,volume=ld.volume); al[~v]=-np.inf
    eng=BacktestEngine(COMMISSION,SLIPPAGE,alpha_mode=True); eng.run(c,al,d,trading_rules=TradingRules(c,ld.open_price,ld.volume,ld.codes,ld.names_arr,ld.is_st,ld.exchange),valid=v)
    print_stats(eng.stats); Visualizer.print_trades(eng); Visualizer.plot_and_save(eng,os.path.join(RESULTS_BASE,FOLDER),l); print("="*60)
if __name__=="__main__": main()
