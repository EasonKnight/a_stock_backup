#!/usr/bin/env python
"""
A股策略全量回测（委托 core.platform.run）
==========================================
直接调用 platform.py 的 run() 函数，支持所有策略类型。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.platform import run

if __name__ == "__main__":
    run()
