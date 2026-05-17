#!/usr/bin/env python
"""
A股策略平台 — Windows 桌面版
=============================
扫描 results/ 目录，列表展示策略，点击排序，查看详情（图表+指标）。
"""
import os, sys, csv, subprocess, re, json

from tkinter import *
from tkinter import ttk, font, simpledialog, messagebox
from PIL import Image, ImageTk

# ── 配色方案（现代舒适深色主题 Modern Comfort Dark）──
# 来源：color_code.txt — 护眼中深灰背景 + 低饱和度柔和色调
BG_DEEP      = "#0d1117"       # 最深背景（窗口底层）
BG_PRIMARY   = "#161b22"       # 主背景（主要工作区）
BG_SECONDARY = "#21262d"       # 次级背景（卡片、侧边栏）
BG_TERTIARY  = "#30363d"       # 三级背景（输入框、表头、按钮常态）
BG_ELEVATED  = "#3c444d"       # 提升表面（悬停/激活状态）
BG_CARD      = "#1c2128"       # 卡片专用背景

FG_PRIMARY   = "#f0f6fc"       # 主文字（柔和白色）
FG_SECONDARY = "#8b949e"       # 次要文字（标签、正文）
FG_MUTED     = "#6e7681"       # 弱化文字（注释、占位符）
FG_GHOST     = "#484f58"       # 幽灵文字（禁用状态）
FG_GREEN     = "#56d364"       # 青绿（正收益）
FG_RED       = "#f85149"       # 红色（负收益）

ACCENT_BLUE       = "#58a6ff"  # 主蓝色（链接、主要按钮）
ACCENT_BLUE_DIM   = "#2563dc"  # 蓝色暗调（按钮默认态）
ACCENT_BLUE_SOFT  = "#1f6feb"  # 柔和蓝（选中状态、激活标签）
ACCENT_TEAL       = "#56d364"  # 青绿色（成功状态、正收益）
ACCENT_TEAL_DIM   = "#2d8a3a"  # 青绿暗调
ACCENT_TEAL_BG    = "#132238"  # 青绿背景（成功提示底色）
ACCENT_AMBER      = "#f0883e"  # 琥珀色（警告、注意提示）
ACCENT_AMBER_DIM  = "#db6d28"  # 琥珀暗调
ACCENT_GOLD       = "#e3b341"  # 金色（金额、高亮数据）
ACCENT_RED        = "#f85149"  # 红色（错误、危险操作）
ACCENT_RED_DIM    = "#aa2020"  # 红色暗调
ACCENT_RED_BG     = "#2d0c0f"  # 红色背景（错误提示底色）
ACCENT_PURPLE     = "#bc8cff"  # 紫色（特殊功能、高级选项）
ACCENT_PURPLE_DIM = "#6d28b8"  # 紫色暗调

# 按钮深色（比 DIM 更深，文字更清晰）
BTN_TEAL   = "#1a5c1e"
BTN_BLUE   = "#1a4ab8"
BTN_PURPLE = "#4a1a8f"
BTN_RED    = "#8a1212"

BORDER       = "#30363d"       # 常规边框
BORDER_LIGHT = "#3c444d"       # 亮边框（悬停、焦点）
BORDER_GLOW  = "#58a6ff"       # 发光边框（焦点/选中）
DIVIDER      = "#21262d"       # 分割线
TABLE_STRIPE = "#151b24"       # 斑马纹（奇数行）
TABLE_HOVER  = "#252b33"       # 行悬停背景
TABLE_SELECT = "#7c3aed"       # 行选中背景（亮紫，文字清晰）

RESULTS = os.path.expanduser("~/Desktop/a_stock_trade/results")
STRATEGIES_DIR = os.path.expanduser("~/Desktop/a_stock_trade/strategies")
LIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live")


def load_live_strategies():
    """读取 live/strategies.json 返回策略列表"""
    path = os.path.join(LIVE_DIR, "strategies.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_STOCK_MAP_CACHE = None

def load_stock_name_map(force_reload=False):
    """从预计算 data/stock_map.json 加载股票索引→(名称, 最新价) 映射。
    若底层 NPZ 数据文件更新，自动从 NPZ 重生成 JSON。
    """
    global _STOCK_MAP_CACHE
    if _STOCK_MAP_CACHE is not None and not force_reload:
        return _STOCK_MAP_CACHE

    base = os.path.dirname(os.path.abspath(__file__))
    npz_path = os.path.join(base, "data", "a_stock_kline_3y.npz")
    json_path = os.path.join(base, "data", "stock_map.json")

    # 若 NPZ 比 JSON 新，自动重生成
    if os.path.exists(npz_path) and (
        not os.path.exists(json_path)
        or os.path.getmtime(npz_path) > os.path.getmtime(json_path)
    ):
        m = _build_stock_map_from_npz(npz_path)
        _STOCK_MAP_CACHE = m
        # 写回 JSON 供后续快速加载
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in m.items()},
                          f, ensure_ascii=False, indent=None, separators=(",", ":"))
        except Exception:
            pass
        return m

    # 读预存 JSON
    if os.path.exists(json_path):
        try:
            with open(json_path, encoding="utf-8") as f:
                raw = json.load(f)
            _STOCK_MAP_CACHE = {int(k): v for k, v in raw.items()}
            return _STOCK_MAP_CACHE
        except Exception:
            pass

    # 最后回退：从 NPZ 直接加载
    if os.path.exists(npz_path):
        _STOCK_MAP_CACHE = _build_stock_map_from_npz(npz_path)
        return _STOCK_MAP_CACHE

    _STOCK_MAP_CACHE = {}
    return {}


def _build_stock_map_from_npz(npz_path):
    """从 NPZ 提取 stock_idx → [name, last_close]"""
    import numpy as np
    d = np.load(npz_path, allow_pickle=True)
    codes = d["codes"]
    names = d["names"]
    close = d["close"]
    result = {}
    for i in range(len(codes)):
        idx = int(codes[i])
        name = str(names[i])
        cl = close[i]
        mask = ~np.isnan(cl)
        if mask.any():
            last_idx = np.where(mask)[0][-1]
            result[idx] = [name, round(float(cl[last_idx]), 2)]
        else:
            result[idx] = [name, 0.0]
    return result


def save_live_strategies(strategies):
    """覆盖写入 live/strategies.json"""
    path = os.path.join(LIVE_DIR, "strategies.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(strategies, f, ensure_ascii=False, indent=2)


def calc_strat_positions(folder):
    """读取回测结果的 position_matrix.csv + 股票映射，返回 [(code, name, lots, price, amount), ...]
    可在子线程中安全调用。"""
    csv_path = os.path.join(RESULTS, folder, "position_matrix.csv")
    if not os.path.exists(csv_path):
        return None
    import csv
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        last_row = None
        for row in reader:
            if row:
                last_row = row
    if not last_row:
        return None
    stock_map = load_stock_name_map()
    positions = []
    for i in range(1, min(len(header), len(last_row))):
        val_str = last_row[i].strip()
        if not val_str or val_str == "0":
            continue
        try:
            amount = float(val_str)
        except ValueError:
            continue
        idx_val = header[i].strip()
        try:
            stock_idx = int(idx_val)
        except ValueError:
            continue
        np = stock_map.get(stock_idx)
        name, price = np if np else (idx_val, 0)
        if price > 0:
            shares = int(amount / price / 100) * 100
            lots = shares // 100
            final_amount = round(shares * price, 0)
        else:
            lots = 0
            final_amount = round(amount, 0)
        if lots > 0:
            # 补回前导0，恢复6位股票代码
            code_6 = idx_val.zfill(6)
            positions.append((code_6, name, lots,
                              round(price, 2), final_amount))
    return positions


def load_live_positions():
    """读取 live/positions.json 返回持仓列表"""
    path = os.path.join(LIVE_DIR, "positions.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_stats(csv_path):
    """读取 stats.csv 返回 dict"""
    if not os.path.exists(csv_path):
        return {}
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            return row
    return {}


def _parse_label(src_path):
    """从策略文件提取 label 和 folder（与 platform.py _read_meta 逻辑一致）"""
    try:
        with open(src_path, encoding="utf-8") as f:
            content = f.read()
        # 只读大写 LABEL/FOLDER（与 platform.py 的 _read_meta 一致）
        m = re.search(r'LABEL\s*=\s*["\'](.+?)["\']', content)
        label = m.group(1) if m else None
        m2 = re.search(r'FOLDER\s*=\s*["\'](.+?)["\']', content)
        folder = m2.group(1) if m2 else None
        # 无大写时回退到文件名（与 _read_meta 的 setdefault 一致）
        if not label:
            label = os.path.splitext(os.path.basename(src_path))[0]
        if not folder:
            folder = os.path.splitext(os.path.basename(src_path))[0]
        return label, folder
    except Exception:
        name = os.path.splitext(os.path.basename(src_path))[0]
        return name, name


def scan_strategies():
    """
    从 strategies/ 下读取全部策略文件（s* 旧信号 + a* alpha 模式），
    同时查找 results/ 下的回测结果。
    返回 [(name, stats_dict, equity_png_path, src_path, created), ...]
    """
    import glob

    # 1. 扫描 strategies/ 下的所有策略文件
    strategy_files = sorted(glob.glob(os.path.join(STRATEGIES_DIR, "*.py")))
    strategy_files = [f for f in strategy_files if os.path.basename(f) != "__init__.py"]

    # 2. 扫描 results/ 建立 folder → (stats, equity) 映射
    results_map = {}
    if os.path.isdir(RESULTS):
        for d in os.listdir(RESULTS):
            full = os.path.join(RESULTS, d)
            if not os.path.isdir(full) or d == "30策略对比":
                continue
            stats = read_stats(os.path.join(full, "stats.csv"))
            equity = os.path.join(full, "equity_curve.png")
            if not os.path.exists(equity):
                equity = ""
            results_map[d] = (stats, equity)

    # 3. 按文件顺序构建结果列表
    dirs = []
    seen_folders = set()
    for src_path in strategy_files:
        # 跳过调优/开发文件
        base = os.path.basename(src_path)
        if base == "s31_tune.py":
            continue
        label, folder = _parse_label(src_path)
        if not label or folder in seen_folders:
            continue
        seen_folders.add(folder)
        stats, equity = results_map.get(folder, ({}, ""))
        created = _fmt_time(src_path)
        dirs.append((label, stats, equity, src_path, created))

    return dirs


def _parse_pct(s):
    """把 '+134.17%' 或 '-48.88%' 转成 float；'—' 返回 None"""
    if not s or s == "—":
        return None
    s = s.replace("%", "").replace("+", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_num(s):
    """把 '0.72' 转成 float；'—' 返回 None"""
    if not s or s == "—":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_time(s):
    """把 '05-16 13:40' 转成可排序的数值（分钟数）"""
    if not s:
        return None
    try:
        parts = s.split()
        if len(parts) != 2:
            return None
        md = parts[0].split("-")
        hm = parts[1].split(":")
        if len(md) != 2 or len(hm) != 2:
            return None
        month, day = int(md[0]), int(md[1])
        hour, minute = int(hm[0]), int(hm[1])
        return month * 43200 + day * 1440 + hour * 60 + minute
    except:
        return None


# 列配置：(id, 显示名, 宽度, 解析函数, 从 stats 取值的 key)
COLUMNS = [
    ("name",    "策略名称", 180, None, None),
    ("ret",     "总收益率", 100, _parse_pct, "总收益率"),
    ("csi_sharpe", "中证信息比",  90, _parse_num, "中证信息比"),
    ("eq_sharpe",  "等权信息比",  90, _parse_num, "信息比率"),
    ("turnover",   "日均换手",   85, _parse_pct, "日均换手"),
    ("dd",      "最大回撤", 100, _parse_pct, "最大回撤"),
    ("created", "创建时间", 110, _parse_time, None),
]


def _fmt_time(fp):
    """返回文件的创建时间字符串"""
    try:
        ts = os.path.getctime(fp)
        from datetime import datetime
        return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
    except:
        return ""


class App(Tk):
    STAT_KEYS = [
        "总收益率", "年化收益率", "夏普比率", "最大回撤",
        "日均持股", "日均换手", "总交易成本", "基准收益",
        "超额收益", "信息比率", "中证信息比", "交易天数", "胜率", "盈亏比",
    ]

    def __init__(self):
        super().__init__()
        self.title("A股策略平台")
        self.state("zoomed")
        self.configure(bg=BG_PRIMARY)
        self.sort_col = "created"
        self.sort_rev = True

        self._build_styles()
        self._build_ui()

        # 数据
        self.strategies = scan_strategies()
        self.current_equity = ""
        self._tk_img = None
        self._selected_src = None
        self._selected_name = None
        self._sort_strategies("created", reverse=True)
        self.populate_tree()
        self.tree.heading("created", text="创建时间 ▼")
        # 窗口关闭时清理子进程
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """关闭窗口前清理所有后台子进程"""
        import subprocess
        # kill 所有后台 Python 子进程
        if hasattr(self, "_live_procs"):
            for p in self._live_procs:
                if p.poll() is None:
                    try: p.kill()
                    except: pass
        self.destroy()

    # ── 样式 ───────────────────────────────────────────────

    def _build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=BG_SECONDARY, foreground=FG_PRIMARY,
                        fieldbackground=BG_SECONDARY, rowheight=30,
                        font=("Microsoft YaHei", 10, "bold"), borderwidth=0)
        style.configure("Treeview.Heading", background=BG_SECONDARY, foreground=ACCENT_BLUE,
                        font=("Microsoft YaHei", 10, "bold"), borderwidth=0, relief="flat")
        style.map("Treeview", background=[("selected", TABLE_SELECT)],
                  foreground=[("selected", FG_PRIMARY)])
        style.map("Treeview.Heading", background=[("active", BG_ELEVATED)])
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        for name in ("Main.TNotebook", "TNotebook"):
            s = ttk.Style()
            s.theme_use("clam")
            s.configure(name, background=BG_PRIMARY, borderwidth=0)
            s.configure(name + ".Tab", background=BG_TERTIARY,
                        foreground=FG_SECONDARY if name == "Main.TNotebook" else FG_PRIMARY,
                        padding=[16, 4], font=("Microsoft YaHei", 10))
            s.map(name + ".Tab", background=[("selected", BG_SECONDARY)],
                  foreground=[("selected", FG_PRIMARY)])

    # ── 布局 ───────────────────────────────────────────────

    def _build_ui(self):
        self.rowconfigure(0, weight=0); self.rowconfigure(1, weight=0); self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        title_lbl = Label(self, text="📊  A股策略平台",
                          font=("Microsoft YaHei", 18, "bold"),
                          fg=ACCENT_BLUE, bg=BG_PRIMARY, anchor="w", padx=16, pady=10)
        title_lbl.grid(row=0, column=0, sticky="ew")
        Frame(self, height=1, bg=BORDER).grid(row=1, column=0, sticky="ew")

        main_notebook = ttk.Notebook(self, style="Main.TNotebook")
        main_notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.main_notebook = main_notebook

        self._build_backtest_tab(main_notebook)
        self._build_live_tab(main_notebook)

    def _build_backtest_tab(self, notebook):
        tab = Frame(notebook, bg=BG_PRIMARY)
        notebook.add(tab, text="📊 策略回测")
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=0); tab.columnconfigure(1, weight=1)

        # ── 左侧：策略列表 ──
        left = Frame(tab, bg=BG_PRIMARY)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        hdr = Frame(left, bg=BG_PRIMARY)
        hdr.pack(fill=X, pady=(0, 4))
        Label(hdr, text="策略列表", font=("Microsoft YaHei", 12, "bold"),
              fg=ACCENT_BLUE, bg=BG_PRIMARY).pack(side=LEFT)
        for txt, cmd, clr in [("↻", self.refresh, None), ("💰", self.open_balance, ACCENT_GOLD)]:
            kwargs = dict(font=("Microsoft YaHei", 11, "bold") if txt == "↻" else ("Segoe UI Emoji", 12),
                          fg=FG_PRIMARY if clr is None else clr, bg=BG_TERTIARY, bd=0, padx=8, pady=0,
                          activebackground=BG_ELEVATED, cursor="hand2", relief="flat", highlightthickness=0)
            if clr:
                kwargs["activeforeground"] = clr
            else:
                kwargs["activeforeground"] = FG_PRIMARY
            Button(hdr, text=txt, command=cmd, **kwargs).pack(side=RIGHT, padx=(4, 0) if txt == "↻" else (0, 2))

        run_bar = Frame(left, bg=BG_PRIMARY)
        run_bar.pack(fill=X, pady=(0, 4))
        btns = [("▶ 全量回测", BTN_TEAL, ACCENT_TEAL_DIM, self.run_all),
                ("▶ 运行选中", BTN_BLUE, ACCENT_BLUE_DIM, self.run_selected),
                ("🤖 自动研发", BTN_PURPLE, ACCENT_PURPLE_DIM, self.auto_develop),
                ("⏹ 停止", BTN_RED, ACCENT_RED_DIM, self.stop_dev)]
        self._run_sel_ref = None
        for txt, clr, hvr, cmd in btns:
            btn = Button(run_bar, text=txt, font=("Microsoft YaHei", 10),
                         fg=FG_PRIMARY, bg=clr, bd=0, padx=8, pady=3,
                         activebackground=hvr, activeforeground=FG_PRIMARY,
                         disabledforeground=FG_GHOST, command=cmd, cursor="hand2")
            btn.pack(side=LEFT, fill=X, expand=True, padx=(3, 0) if txt != "▶ 全量回测" else (0, 3))
            if txt == "▶ 运行选中":
                self.run_sel_btn = btn
            elif txt == "🤖 自动研发":
                self.auto_btn = btn
            elif txt == "⏹ 停止":
                self.stop_btn = btn; btn.config(state="disabled")

        self.tree = ttk.Treeview(left, columns=("name","ret","csi_sharpe","eq_sharpe","turnover","dd","created"),
                                 show="headings", height=35, selectmode="browse")
        self.tree.tag_configure("odd", background=TABLE_STRIPE)
        self.tree.tag_configure("even", background=BG_SECONDARY)
        self.tree.tag_configure("live", background="#1a3a1a", foreground="#ffffff")
        for cid, ct, cw, _, _ in COLUMNS:
            self.tree.heading(cid, text=ct, command=lambda c=cid: self.sort_by(c))
            self.tree.column(cid, width=cw, minwidth=cw, anchor="center" if cid != "name" else "w")
        vsb = Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb.pack(side=RIGHT, fill=Y)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-3>", self.show_strat_menu)

        self.strat_menu = Menu(self, tearoff=False, bg=BG_TERTIARY, fg=FG_PRIMARY,
                               activebackground=BG_ELEVATED, activeforeground=FG_PRIMARY,
                               font=("Microsoft YaHei", 10), bd=0)
        self.strat_menu.add_command(label="➕ 添加到实盘", command=self.add_selected_to_live)

        # ── 右侧：详情面板 ──
        right = Frame(tab, bg=BG_SECONDARY, bd=1, relief="solid",
                      highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.rowconfigure(2, weight=1); right.columnconfigure(0, weight=1)

        # 研发日志
        self.dev_frame = Frame(right, bg=BG_PRIMARY, bd=1, relief="flat",
                               highlightbackground=ACCENT_GOLD, highlightthickness=1)
        self.dev_label = Label(self.dev_frame, text="⏳ 等待研发...",
                               font=("Microsoft YaHei", 13, "bold"),
                               fg=ACCENT_GOLD, bg=BG_PRIMARY, pady=3, anchor="w")
        self.dev_label.pack(fill=X, padx=6)
        self.dev_text = Text(self.dev_frame, height=7, font=("Consolas", 13),
                             fg=FG_PRIMARY, bg=BG_PRIMARY, wrap="word", bd=0, padx=6, pady=4)
        self.dev_text.tag_configure("chat_user", foreground="#58a6ff", font=("Consolas", 13, "bold"))
        self.dev_text.tag_configure("chat_ai", foreground="#56d364")
        self.dev_text.tag_configure("chat_tool", foreground="#bc8cff")
        self.dev_text.tag_configure("chat_code", foreground="#e3b341")
        self.dev_text.tag_configure("chat_err", foreground="#f85149", font=("Consolas", 13, "bold"))
        self.dev_text.tag_configure("chat_sep", foreground="#484f58")
        self.dev_text.pack(fill=BOTH, expand=True, padx=4, pady=(0, 4))
        self.dev_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(4, 0))
        self.dev_frame.grid_remove()

        # 详情标题
        self.detail_title = Label(right, text="选择左侧策略查看详情",
                                  font=("Microsoft YaHei", 14, "bold"),
                                  fg=FG_PRIMARY, bg=BG_SECONDARY, pady=10, padx=12, anchor="w")
        self.detail_title.grid(row=1, column=0, sticky="ew")
        Frame(right, height=1, bg=BORDER).grid(row=1, column=0, sticky="ew", pady=(0, 0))

        # 详情 Notebook
        self.notebook = ttk.Notebook(right)
        self.notebook.grid(row=2, column=0, sticky="nsew", pady=(4, 0))

        chart_tab = Frame(self.notebook, bg=BG_SECONDARY)
        self.notebook.add(chart_tab, text="📈 净值曲线")
        chart_tab.rowconfigure(0, weight=1); chart_tab.columnconfigure(0, weight=1)
        self.img_canvas = Canvas(chart_tab, bg=BG_SECONDARY, highlightthickness=0)
        self.img_canvas.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        code_tab = Frame(self.notebook, bg=BG_SECONDARY)
        self.notebook.add(code_tab, text="📄 策略代码")
        code_tab.rowconfigure(1, weight=1); code_tab.columnconfigure(0, weight=1)

        tb = Frame(code_tab, bg=BG_SECONDARY)
        tb.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.save_btn = Button(tb, text="💾 保存", font=("Microsoft YaHei", 10),
                               bg=BTN_TEAL, fg=FG_PRIMARY, bd=0, padx=12, pady=2,
                               activebackground=ACCENT_TEAL_DIM, activeforeground=FG_PRIMARY,
                               command=self.save_code, cursor="hand2")
        self.save_btn.pack(side=LEFT, padx=(4, 4))
        self.revert_btn = Button(tb, text="↩ 撤销修改", font=("Microsoft YaHei", 10),
                                 bg=FG_MUTED, fg=FG_PRIMARY, bd=0, padx=12, pady=2,
                                 activebackground=BG_ELEVATED, activeforeground=FG_PRIMARY,
                                 command=self.revert_code, cursor="hand2")
        self.revert_btn.pack(side=LEFT, padx=(4, 4))
        self.code_status = Label(tb, text="", font=("Microsoft YaHei", 9),
                                 fg=FG_SECONDARY, bg=BG_SECONDARY)
        self.code_status.pack(side=RIGHT, padx=(0, 8))

        self.code_text = Text(code_tab, font=("Consolas", 11), fg=FG_PRIMARY,
                              bg=BG_TERTIARY, wrap="none", bd=0, padx=8, pady=8,
                              undo=True, maxundo=50, insertbackground=FG_PRIMARY)
        for tag, clr in [("kw", ACCENT_PURPLE), ("str", ACCENT_GOLD), ("cmt", FG_MUTED),
                         ("num", ACCENT_PURPLE), ("dec", ACCENT_TEAL), ("bif", ACCENT_BLUE)]:
            self.code_text.tag_configure(tag, foreground=clr)
        self.code_text.bind("<KeyRelease>", lambda e: self._highlight_code())
        self.code_text.grid(row=1, column=0, sticky="nsew")
        self.code_text.bind("<Control-s>", lambda e: self.save_code())
        self.code_text.bind("<Control-S>", lambda e: self.save_code())
        code_vsb = Scrollbar(code_tab, orient="vertical", command=self.code_text.yview)
        code_vsb.grid(row=1, column=1, sticky="ns")
        code_hsb = Scrollbar(code_tab, orient="horizontal", command=self.code_text.xview)
        code_hsb.grid(row=2, column=0, sticky="ew")
        self.code_text.configure(yscrollcommand=code_vsb.set, xscrollcommand=code_hsb.set)
        self.current_src_path = None

        # 底部指标 + 按钮
        btm = Frame(right, bg=BG_SECONDARY)
        btm.grid(row=3, column=0, sticky="ew", pady=6)
        self.stats_text = Text(btm, height=3, font=("Consolas", 10), fg=FG_PRIMARY,
                               bg=BG_TERTIARY, bd=0, wrap="word", padx=10, pady=6, relief="flat")
        for tag, clr in [("stat_key", FG_SECONDARY), ("stat_val_pos", ACCENT_TEAL),
                         ("stat_val_neg", ACCENT_RED), ("stat_val", ACCENT_BLUE)]:
            self.stats_text.tag_configure(tag, foreground=clr)
        self.stats_text.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))
        self.open_btn = Button(btm, text="📂 打开原图", font=("Microsoft YaHei", 10),
                               bg=BTN_BLUE, fg=FG_PRIMARY, bd=0, padx=14, pady=4,
                               activebackground=ACCENT_BLUE_DIM, activeforeground=FG_PRIMARY,
                               command=self.open_chart, cursor="hand2")
        self.open_btn.pack(side=RIGHT, padx=(4, 0))
        self.open_btn.config(state="disabled")

    def _build_live_tab(self, notebook):
        tab = Frame(notebook, bg=BG_SECONDARY)
        notebook.add(tab, text="🔴 实盘策略")
        self.live_tab = tab
        tab.rowconfigure(0, weight=1); tab.columnconfigure(0, weight=1)

        def make_section(parent):
            f = Frame(parent, bg=BG_SECONDARY)
            f.rowconfigure(1, weight=1); f.columnconfigure(0, weight=1)
            return f

        def make_aligned_bar(parent, col_cfgs):
            bar = Frame(parent, bg=BG_TERTIARY, height=26)
            labels = []
            for i, (cid, ctext, cw) in enumerate(col_cfgs):
                anchor = "w" if i == 0 else "e"
                lbl = Label(bar, text="", font=("Microsoft YaHei", 9, "bold"),
                            fg=ACCENT_BLUE, bg=BG_TERTIARY, anchor=anchor)
                lbl.grid(row=0, column=i, sticky="ew", padx=6)
                bar.columnconfigure(i, weight=0, minsize=cw)
                labels.append(lbl)
            return bar, labels

        pw = ttk.PanedWindow(tab, orient=VERTICAL)
        pw.grid(row=0, column=0, sticky="nsew", padx=8)

        # Pane 1: 实盘策略列表
        strat_sec = make_section(pw)
        hdr = Frame(strat_sec, bg=BG_SECONDARY)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        Label(hdr, text="📋 实盘策略", font=("Microsoft YaHei", 12, "bold"),
              fg=FG_PRIMARY, bg=BG_SECONDARY).pack(side=LEFT)

        STRAT_COLS = [("name","策略名称",160),("status","状态",80),
                      ("capital_pct","分配金额",110),("signal","最新信号",100),
                      ("cum_return","累计收益",100),("created","创建日期",110)]
        self.strat_tree = ttk.Treeview(strat_sec,
            columns=("name","status","capital_pct","signal","cum_return","created"),
            show="headings", height=5, selectmode="browse")
        for cid, ct, cw in STRAT_COLS:
            self.strat_tree.heading(cid, text=ct)
            self.strat_tree.column(cid, width=cw, minwidth=cw, anchor="w" if cid=="name" else "center")
        vsb_s = Scrollbar(strat_sec, orient="vertical", command=self.strat_tree.yview)
        self.strat_tree.configure(yscrollcommand=vsb_s.set)
        self.strat_tree.grid(row=1, column=0, sticky="nsew")
        vsb_s.grid(row=1, column=1, sticky="ns")
        # 最后更新时间
        self.live_update_label = Label(strat_sec, text="",
            font=("Microsoft YaHei", 9), fg=FG_MUTED, bg=BG_SECONDARY, anchor="w")
        self.live_update_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 0))
        self.strat_tree.bind("<<TreeviewSelect>>", self.on_live_strat_select)
        self.strat_tree.bind("<Button-3>", self.show_live_strat_menu)
        self.strat_tree.bind("<Double-1>", self.on_live_strat_double)
        self.live_strat_menu = Menu(self, tearoff=False, bg=BG_TERTIARY, fg=FG_PRIMARY,
                                    activebackground=BG_ELEVATED, activeforeground=FG_PRIMARY,
                                    font=("Microsoft YaHei", 10), bd=0)
        self.live_strat_menu.add_command(label="✏️ 设置分配金额", command=self.edit_allocation_amount)
        self.live_strat_menu.add_command(label="❌ 从实盘移除", command=self.remove_from_live)
        pw.add(strat_sec, weight=2)

        # Pane 2: 组合持仓
        pos_sec = make_section(pw)
        hdr2 = Frame(pos_sec, bg=BG_SECONDARY)
        hdr2.grid(row=0, column=0, columnspan=2, sticky="ew")
        Label(hdr2, text="📊 组合持仓（等比缩仓）", font=("Microsoft YaHei", 12, "bold"),
              fg=FG_PRIMARY, bg=BG_SECONDARY).pack(side=LEFT)
        POS_COLS = [("code","股票代码",120),("pname","股票名称",105),
                    ("lots","总手数",75),("price","参考价",85),
                    ("amount","总市值",100),("strategies","涉及策略",100)]
        self.pos_tree = ttk.Treeview(pos_sec,
            columns=("code","pname","lots","price","amount","strategies"),
            show="headings", height=5, selectmode="browse")
        for cid, ct, cw in POS_COLS:
            self.pos_tree.heading(cid, text=ct)
            self.pos_tree.column(cid, width=cw, minwidth=cw, anchor="w" if cid=="pname" else "center")
        vsb_p = Scrollbar(pos_sec, orient="vertical", command=self.pos_tree.yview)
        self.pos_tree.configure(yscrollcommand=vsb_p.set)
        self.pos_tree.grid(row=1, column=0, sticky="nsew")
        vsb_p.grid(row=1, column=1, sticky="ns")
        self.pos_bar, self.pos_bar_lbls = make_aligned_bar(pos_sec, POS_COLS)
        for lbl in self.pos_bar_lbls:
            lbl.config(font=("Microsoft YaHei", 12, "bold"))
        self.pos_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        pw.add(pos_sec, weight=1)

        # Pane 3: 策略持仓
        sp_sec = make_section(pw)
        self.sp_header = Frame(sp_sec, bg=BG_SECONDARY)
        self.sp_header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.sp_title_lbl = Label(self.sp_header,
            text="🎯 选择上方策略查看持仓计算", font=("Microsoft YaHei", 12, "bold"),
            fg=FG_SECONDARY, bg=BG_SECONDARY)
        self.sp_title_lbl.pack(side=LEFT)
        SP_COLS = [("code","股票代码",120),("pname","股票名称",105),
                   ("direction","方向",70),("lots","目标手数",90),
                   ("price","参考价",90),("amount","占用资金",100),("pct","占比",75)]
        self.sp_tree = ttk.Treeview(sp_sec,
            columns=("code","pname","direction","lots","price","amount","pct"),
            show="headings", height=5, selectmode="browse")
        for cid, ct, cw in SP_COLS:
            self.sp_tree.heading(cid, text=ct)
            self.sp_tree.column(cid, width=cw, minwidth=cw, anchor="center")
        self.sp_tree.column("pname", anchor="w")
        vsb_sp = Scrollbar(sp_sec, orient="vertical", command=self.sp_tree.yview)
        self.sp_tree.configure(yscrollcommand=vsb_sp.set)
        self.sp_tree.grid(row=1, column=0, sticky="nsew")
        vsb_sp.grid(row=1, column=1, sticky="ns")
        self.sp_bar, self.sp_bar_lbls = make_aligned_bar(sp_sec, SP_COLS)
        for lbl in self.sp_bar_lbls:
            lbl.config(font=("Microsoft YaHei", 12, "bold"))
        self.sp_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        pw.add(sp_sec, weight=1)

        self.refresh_live()

    # ── 排序工具 ──────────────────────────────────────────

    def _sort_strategies(self, col_id=None, reverse=None):
        if col_id is None:
            col_id = self.sort_col
        if reverse is None:
            reverse = self.sort_rev
        self.sort_col = col_id
        self.sort_rev = reverse
        self.strategies.sort(
            key=lambda item: self._get_sort_key(col_id, item),
            reverse=reverse
        )

    # ── 刷新 ───────────────────────────────────────────────

    def refresh(self):
        """重新扫描策略列表并刷新界面"""
        prev_name = self._selected_name
        self.strategies = scan_strategies()
        self._sort_strategies("created", reverse=True)
        self.populate_tree()
        # 更新表头箭头
        for cid, col_text, _, _, _ in COLUMNS:
            arrow = " ▼" if cid == "created" else ""
            self.tree.heading(cid, text=col_text + arrow)
        # 如果之前有选中的策略，尝试重新选中并展示
        if prev_name:
            for entry in self.strategies:
                n, stats, equity, src_path = entry[0], entry[1], entry[2], entry[3]
                if n == prev_name:
                    self._selected_name = n
                    self._selected_src = src_path
                    self.show_detail(n, stats, equity, src_path)
                    for row in self.tree.get_children():
                        vals = self.tree.item(row, "values")
                        if vals and vals[0] == n:
                            self.tree.selection_set(row)
                            self.tree.focus(row)
                            self.tree.see(row)
                            break
                    return
        self.detail_title.config(text="选择左侧策略查看详情")
        self.stats_text.delete("1.0", END)
        self.img_canvas.delete("all")
        self.code_text.delete("1.0", END)
        self.current_equity = ""
        self.current_src_path = None
        self._selected_src = None
        self._selected_name = None
        self.open_btn.config(state="disabled")
        self.run_sel_btn.config(state="disabled")
    # ── 实盘刷新 ─────────────────────────────────────────────

    def refresh_live(self):
        """刷新实盘策略和持仓列表"""
        strategies = load_live_strategies()
        for row in self.strat_tree.get_children():
            self.strat_tree.delete(row)
        total_amt = 0
        for s in strategies:
            vals = (s.get("name",""), s.get("status",""), s.get("capital_pct",""),
                    s.get("signal",""), s.get("cum_return",""), s.get("created",""))
            try:
                cap = float((s.get("capital_pct") or "").strip().replace(",", ""))
            except (ValueError, TypeError, AttributeError):
                cap = 0
            tags = ("live",) if cap > 0 else ()
            self.strat_tree.insert("", END, values=vals, tags=tags)
            try:
                raw = (s.get("capital_pct") or "").strip().replace(",", "")
                total_amt += float(raw) if raw else 0
            except (ValueError, TypeError):
                total_amt += 0
        # 合计行
        total_str = f"{total_amt:,.0f}" if total_amt > 0 else ""
        self.strat_tree.insert("", END,
            values=("📊 合计", "", total_str, "", "", ""),
            tags=("total",))
        self.strat_tree.tag_configure("total",
            font=("Microsoft YaHei", 10, "bold"),
            foreground=ACCENT_TEAL)
        self.strat_tree.tag_configure("live",
            background="#1a3a1a", foreground="#ffffff")

        # 刷新组合持仓
        self.refresh_combined_positions()
        # 更新最后刷新时间
        from datetime import datetime
        self.live_update_label.config(text=f"⏱ 最后更新: {datetime.now():%m-%d %H:%M}")

    def refresh_combined_positions(self):
        """聚合持仓 → 按总分配金额等比缩放 → 过滤<1万的股票"""
        for row in self.pos_tree.get_children():
            self.pos_tree.delete(row)

        live = load_live_strategies()

        # 1. 计算总分配金额
        total_alloc = 0
        for s in live:
            try:
                raw = (s.get("capital_pct") or "").strip().replace(",", "")
                total_alloc += float(raw) if raw else 0
            except (ValueError, TypeError):
                pass

        # 2. 聚合持仓（全策略叠加）
        agg = {}
        stock_map = load_stock_name_map()
        for s in live:
            pos = s.get("positions")
            if not pos:
                continue
            sname = s.get("name", "?")
            for code, name, lots, _, amount in pos:
                code = code.zfill(6)
                if code not in agg:
                    agg[code] = {"name": name, "lots": 0, "amount": 0,
                                 "strategies": set()}
                agg[code]["lots"] += lots
                agg[code]["amount"] += amount
                agg[code]["strategies"].add(sname)
                np = stock_map.get(int(code))
                if np:
                    agg[code]["name"] = np[0]

        if not agg:
            self.pos_bar_lbls[0].config(text="无持仓数据")
            for lbl in self.pos_bar_lbls[1:]:
                lbl.config(text="")
            return

        # 3. 逐步缩仓：从最大市值股开始逐只加入，
        #    等比缩放后每只实际金额≥1万则保留，否则停止
        items = [(code, d) for code, d in agg.items()]
        items.sort(key=lambda x: x[1]["amount"], reverse=True)
        best = []
        for k in range(1, len(items) + 1):
            subset = items[:k]
            sum_sub = sum(d["amount"] for _, d in subset)
            scale = total_alloc / sum_sub if sum_sub > 0 else 0

            ok = True
            candidate = []
            for code, d in subset:
                scaled_amt = d["amount"] * scale
                # 先换算为整数手数，再用实际金额判断
                price_per_lot = d["amount"] / d["lots"] if d["lots"] > 0 else 0
                new_lots = max(1, int(scaled_amt / price_per_lot)) if price_per_lot > 0 else 1
                actual_amt = new_lots * price_per_lot
                if actual_amt < 10000:
                    ok = False
                    break
                candidate.append((code, d["name"], new_lots, actual_amt,
                                  d["strategies"], price_per_lot / 100))

            if ok:
                best = candidate
            else:
                break

        adjusted = best
        if not adjusted:
            adjusted_text = "总分配金额过低，无法持有任何股票" if total_alloc > 0 else "待设置分配金额"
            self.pos_bar_lbls[0].config(text=adjusted_text)
            for lbl in self.pos_bar_lbls[1:]:
                lbl.config(text="")
            return

        # 4. 按金额降序
        adjusted.sort(key=lambda x: x[3], reverse=True)

        # 5. 渲染
        total_amt = total_lots = 0
        n_orig = len(agg)
        for code, name, lots, amount, strats, pps in adjusted:
            total_lots += lots
            total_amt += amount
            n_strats = len(strats)
            strats_str = f"{n_strats}个策略" if n_strats > 1 else next(iter(strats))
            self.pos_tree.insert("", END,
                values=(code, name, str(lots), f"{pps:.2f}",
                        f"{amount:.0f}", strats_str))

        avg_price = total_amt / (total_lots * 100) if total_lots > 0 else 0
        self.pos_bar_lbls[0].config(text=f"合计{len(adjusted)}只({n_orig}→{len(adjusted)})")
        self.pos_bar_lbls[1].config(text="")
        self.pos_bar_lbls[2].config(text=str(total_lots))
        self.pos_bar_lbls[3].config(text=f"{avg_price:.2f}")
        self.pos_bar_lbls[4].config(text=f"{total_amt:,.0f}")
        self.pos_bar_lbls[5].config(text=f"分配 ¥{total_alloc:,.0f}")

    def refresh_live_strat_detail(self, strat_name=None):
        """从 live 策略的预计算 positions 渲染策略持仓表格（无 IO，立即完成）"""
        # 清空
        for row in self.sp_tree.get_children():
            self.sp_tree.delete(row)
        for lbl in self.sp_bar_lbls:
            lbl.config(text="")

        if not strat_name:
            self.sp_title_lbl.config(text="🎯 选择上方策略查看持仓计算",
                                     fg=FG_SECONDARY)
            return

        live = load_live_strategies()
        found = None
        for s in live:
            if s["name"] == strat_name:
                found = s
                break
        if not found:
            self.sp_title_lbl.config(text=f"🎯  {strat_name}", fg=FG_PRIMARY)
            self.sp_tree.insert("", END,
                values=("", "⚠ 无数据", "", "", "", "", ""))
            return

        folder = found.get("folder", "")
        self.sp_title_lbl.config(
            text=f"🎯  {strat_name}" + (f"  —  {folder}" if folder else ""),
            fg=FG_PRIMARY)

        pos = found.get("positions")
        if pos is None:
            self.sp_tree.insert("", END,
                values=("", "⏳ 持仓计算中...", "", "", "", "", ""))
            return
        if not pos:
            self.sp_tree.insert("", END,
                values=("", "无持仓", "", "", "", "", ""))
            return

        total_amount = 0
        for code, name, lots, price, amount in pos:
            code = code.zfill(6)
            direction = "做多"
            total_amount += amount
            self.sp_tree.insert("", END,
                values=(code, name, direction, str(lots),
                        f"{price:.2f}", f"{amount:.0f}", ""))
        # 列对齐合计条
        total_lots = sum(p[2] for p in pos)
        avg_price = total_amount / (total_lots * 100) if total_lots > 0 else 0
        self.sp_bar_lbls[0].config(text=f"合计 {len(pos)}只")
        self.sp_bar_lbls[1].config(text="")
        self.sp_bar_lbls[2].config(text="")
        self.sp_bar_lbls[3].config(text=str(total_lots))
        self.sp_bar_lbls[4].config(text=f"{avg_price:.2f}")
        self.sp_bar_lbls[5].config(text=f"{total_amount:,.0f}")
        self.sp_bar_lbls[6].config(text="")

    def on_live_strat_select(self, event=None):
        """选中实盘策略后，直接从预存数据渲染，无 IO"""
        sel = self.strat_tree.selection()
        if not sel:
            return
        item = self.strat_tree.item(sel[0])
        vals = item["values"]
        strat_name = vals[0] if vals else ""
        self.refresh_live_strat_detail(strat_name)

    def on_live_strat_double(self, event):
        """双击实盘策略行 → 编辑分配金额"""
        try:
            iid = self.strat_tree.identify_row(event.y)
            if not iid:
                return
            vals = self.strat_tree.item(iid, "values")
            if not vals or vals[0] == "📊 合计":
                return
            region = self.strat_tree.identify_region(event.x)
            if region != "cell":
                return
            col = int(self.strat_tree.identify_column(event.x).replace("#", "")) - 1
            if col == 2:  # 分配金额列
                self.edit_allocation_amount()
        except Exception:
            pass

    def show_live_strat_menu(self, event):
        """实盘策略列表右键菜单"""
        iid = self.strat_tree.identify_row(event.y)
        if iid:
            self.strat_tree.selection_set(iid)
            self.live_strat_menu.post(event.x_root, event.y_root)

    def remove_from_live(self):
        """从实盘策略列表中移除选中的策略"""
        sel = self.strat_tree.selection()
        if not sel:
            return
        item = self.strat_tree.item(sel[0])
        vals = item["values"]
        name = vals[0] if vals else ""
        if not name:
            return
        strategies = load_live_strategies()
        strategies = [s for s in strategies if s.get("name") != name]
        save_live_strategies(strategies)
        self.strat_tree.delete(sel[0])
        self.refresh_combined_positions()
        self.refresh_live_strat_detail(None)

    def edit_allocation_amount(self):
        """编辑选中策略的分配金额"""
        sel = self.strat_tree.selection()
        if not sel:
            return
        item = self.strat_tree.item(sel[0])
        vals = item["values"]
        if not vals:
            return
        name = vals[0]
        cur = vals[2] if len(vals) > 2 else "100000"
        new_val = simpledialog.askstring(
            "分配金额", f"请输入「{name}」的分配金额（元）：\n留空或取消保持原值",
            initialvalue=cur,
            parent=self
        )
        if new_val is None:  # 取消
            return
        if new_val == "":
            new_val = cur
        # 验证数字
        try:
            v = float(new_val)
            if v <= 0:
                messagebox.showwarning("无效金额", "分配金额必须大于0", parent=self)
                return
            new_val = str(int(v)) if v == int(v) else str(v)
        except ValueError:
            messagebox.showwarning("无效金额", "请输入有效数字", parent=self)
            return
        strategies = load_live_strategies()
        for s in strategies:
            if s["name"] == name:
                s["capital_pct"] = new_val
                break
        save_live_strategies(strategies)
        self.refresh_live()
        self.refresh_live_strat_detail(None)

    # ── 运行回测 ───────────────────────────────────────────

    def open_balance(self):
        """打开 DeepSeek 账户余额窗口"""
        BalanceWindow(self)

    def stop_dev(self):
        """中断正在研发的进程"""
        if hasattr(self, "_dev_proc") and self._dev_proc and not self._dev_proc.poll():
            self._dev_proc.kill()
            self._dev_proc = None
        self._dev_running = False
        self._dev_stopped = True
        self.dev_label.config(text="⛔ 已停止", fg=FG_RED)
        self.dev_text.insert(END, "\n⛔ 用户中断，进程已终止\n")
        self.auto_btn.config(text="🤖 自动研发", bg=BTN_PURPLE)
        self.stop_btn.config(state="disabled")

    def run_all(self):
        """打开终端窗口运行全量回测"""
        import subprocess
        d = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen(f'start "全量回测" cmd.exe /c "cd /d {d} && python -m core.platform run"',
                         shell=True)

    def run_selected(self):
        """打开终端窗口运行选中的策略，完成后自动刷新"""
        import subprocess, os, threading
        src = self._selected_src
        name = self._selected_name or "选中策略"
        if not src or not os.path.exists(src):
            return
        d = os.path.dirname(os.path.abspath(__file__))
        # 在新窗口中运行，不等待
        proc = subprocess.Popen(
            f'cd /d "{d}" && python "{src}" && pause',
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            shell=True
        )
        # 后台线程等待进程结束后刷新
        def wait_and_refresh():
            proc.wait()
            self.after(500, self.refresh)
        threading.Thread(target=wait_and_refresh, daemon=True).start()

    def _run_all_live_strategies(self):
        """后台运行所有实盘策略，超时自动终止，完成后刷新"""
        import glob, subprocess, threading
        if getattr(self, "_live_running", False):
            return
        self._live_running = True
        strategies = load_live_strategies()
        if not strategies:
            self._live_running = False
            return
        d = os.path.dirname(os.path.abspath(__file__))
        procs = []
        for s in strategies:
            name = s.get("name", "")
            if not name:
                continue
            prefix = name.split("-")[0].split(" ")[0].lower()
            candidates = glob.glob(os.path.join(STRATEGIES_DIR, f"{prefix}_*.py"))
            if not candidates:
                candidates = glob.glob(os.path.join(STRATEGIES_DIR, f"{prefix}*.py"))
            if candidates:
                src = candidates[0]
                p = subprocess.Popen(
                    ["python", src],
                    cwd=d, creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                procs.append(p)
        if not procs:
            self._live_running = False
            return
        self._live_procs = procs
        def wait_all():
            for p in procs:
                try:
                    p.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=5)
            self._live_running = False
            self.after(500, self.refresh_live)
        threading.Thread(target=wait_all, daemon=True).start()
    def auto_develop(self):
        """启动 Hermes（后台隐藏），在左侧面板显示进度和结果"""
        import subprocess, threading, queue, os

        prompt = "调用你的股票量化策略开发skill，新编写一个量化策略"

        # 防止重复点击
        if getattr(self, "_dev_running", False):
            return
        self._dev_running = True

        # 显示研发面板
        self.dev_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(4, 0))
        self.dev_label.config(text="⏳ 正在启动 Hermes...", fg=ACCENT_BLUE)
        self.dev_text.delete("1.0", END)
        self.dev_text.insert("1.0", "已启动 Hermes 后台进程...\n")
        self.auto_btn.config(text="⏳ 研发中", bg=ACCENT_PURPLE_DIM, fg=FG_PRIMARY, state="normal")
        self.auto_btn.update()
        self.stop_btn.config(state="normal")
        self._dev_running = True
        self._dev_stopped = False
        self._dev_proc = None
        self._dev_queue = queue.Queue()
        q = self._dev_queue

        def run_hermes():
            try:
                env = os.environ.copy()
                env["USERPROFILE"] = "C:\\Users\\Mayn"
                proc = subprocess.Popen(
                    ["hermes", "-z", prompt],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    env=env, encoding="utf-8", errors="replace"
                )
                self._dev_proc = proc
                out_lines = []
                try:
                    for line in proc.stdout:
                        out_lines.append(line)
                        if len(out_lines) <= 5:
                            q.put(("line", line.rstrip()))
                except (BrokenPipeError, OSError):
                    pass  # 进程被终止，管道断开
                proc.wait()
                # 仅在未被手动停止时通知完成
                if not getattr(self, "_dev_stopped", False):
                    q.put(("done", "".join(out_lines)))
            except Exception as e:
                if not getattr(self, "_dev_stopped", False):
                    q.put(("error", str(e)))

        thread = threading.Thread(target=run_hermes, daemon=True)
        thread.start()

        elapsed = [0]
        def poll():
            try:
                while True:
                    if getattr(self, "_dev_stopped", False):
                        # 清空队列，防止停止后残留消息
                        while not q.empty():
                            try: q.get_nowait()
                            except: break
                        return
                    typ, data = q.get_nowait()
                    if typ == "line":
                        self.dev_text.insert(END, data + "\n")
                        self.dev_text.see(END)
                    elif typ == "done":
                        self.dev_label.config(text="✅ 研发完成！", fg=FG_GREEN)
                        self.dev_text.insert(END, "\n" + "="*50 + "\n")
                        self.dev_text.insert(END, data.strip())
                        self.dev_text.see(END)
                        self.auto_btn.config(text="🤖 自动研发", bg=BTN_PURPLE)
                        self.stop_btn.config(state="disabled")
                        self._dev_running = False
                        self.after(500, self.refresh)  # 研发完成自动刷新
                        return
                    elif typ == "error":
                        self.dev_label.config(text=f"❌ 错误", fg=FG_RED)
                        self.dev_text.insert(END, f"\n错误: {data}\n")
                        self.auto_btn.config(text="🤖 自动研发", bg=BTN_PURPLE)
                        self.stop_btn.config(state="disabled")
                        self._dev_running = False
                        self.after(500, self.refresh)
                        return
            except queue.Empty:
                pass
            if thread.is_alive():
                elapsed[0] += 1
                self.dev_label.config(text=f"⏳ 正在研发中... 已等待 {elapsed[0]} 秒", fg=FG_GREEN)
                self.after(1000, poll)
            else:
                self.dev_label.config(text="✅ 完成", fg=FG_GREEN)
                self.auto_btn.config(text="🤖 自动研发", bg=BTN_PURPLE)
                self.stop_btn.config(state="disabled")
                self._dev_running = False

        poll()

    # ── 排序 ──────────────────────────────────────────────

    def sort_by(self, col_id):
        """点击列头排序"""
        # 切换方向：同列反转，不同列默认降序
        if col_id == self.sort_col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col = col_id
            # 名称列默认升序，数值列默认降序
            self.sort_rev = (col_id != "name")

        # 排序数据
        self.strategies.sort(
            key=lambda item: self._get_sort_key(col_id, item),
            reverse=self.sort_rev
        )
        self.populate_tree()

        # 表头标记
        for cid, col_text, _, _, _ in COLUMNS:
            arrow = ""
            if cid == col_id:
                arrow = " ▲" if not self.sort_rev else " ▼"
            self.tree.heading(cid, text=col_text + arrow)

    def populate_tree(self):
        # 清空并重新插入
        for row in self.tree.get_children():
            self.tree.delete(row)
        live_names = {s["name"] for s in load_live_strategies()}
        # 实盘策略置顶
        live_entries = [e for e in self.strategies if e[0] in live_names]
        other_entries = [e for e in self.strategies if e[0] not in live_names]
        sorted_entries = live_entries + other_entries
        for i, entry in enumerate(sorted_entries):
            name, stats = entry[0], entry[1]
            created = entry[4] if len(entry) > 4 else ""
            ret = stats.get("总收益率", "—")
            dd = stats.get("最大回撤", "—")
            tag = "odd" if i % 2 else "even"
            if name in live_names:
                tag = "live"
            csi_ir = stats.get("中证信息比", "—")
            eq_ir = stats.get("信息比率", "—")
            turnover = stats.get("日均换手", "—")
            self.tree.insert("", END,
                values=(name, ret, csi_ir, eq_ir, turnover, dd, created),
                tags=(tag,))

    def _get_sort_key(self, col_id, item):
        """对一条策略数据返回可排序的 key"""
        name = item[0]
        stats = item[1]
        for idx, (cid, _, _, parser, stat_key) in enumerate(COLUMNS):
            if cid == col_id:
                if col_id == "name":
                    return name.lower()
                if parser and stat_key:
                    val = stats.get(stat_key, "—")
                    parsed = parser(val)
                    return parsed if parsed is not None else float("-inf")
                # 有解析函数但数据来自策略元组（如创建时间）
                if parser:
                    # 创建时间在数据元组索引4，不是COLUMNS索引5
                    if col_id == "created":
                        val = item[4] if len(item) > 4 else ""
                    else:
                        val = item[idx] if idx < len(item) else ""
                    parsed = parser(val)
                    return parsed if parsed is not None else float("-inf")
                return ""
        return ""

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        name = item["values"][0]
        for entry in self.strategies:
            n, stats, equity, src_path = entry[0], entry[1], entry[2], entry[3]
            if n == name:
                self.show_detail(n, stats, equity, src_path)
                self._selected_src = src_path
                self._selected_name = n
                self.run_sel_btn.config(state="normal")
                break

    def show_strat_menu(self, event):
        """右键弹出策略菜单"""
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.strat_menu.post(event.x_root, event.y_root)

    def add_selected_to_live(self):
        """将选中的回测策略添加到实盘策略列表，后台线程计算持仓"""
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        name = item["values"][0]
        # 在 self.strategies 中查找完整数据
        stats = {}
        src_path = None
        for entry in self.strategies:
            if entry[0] == name:
                stats = entry[1]
                src_path = entry[3]
                break
        cum_ret = stats.get("总收益率", "—")
        created = item["values"][6] if len(item["values"]) > 6 else ""

        # 从源文件解析 FOLDER（结果目录名）
        folder = ""
        if src_path and os.path.exists(src_path):
            m = re.search(r'FOLDER\s*=\s*["\'](.+?)["\']',
                          open(src_path, encoding="utf-8").read())
            if m:
                folder = m.group(1)

        # 先保存基本数据（无持仓），立即刷新列表
        new_strat = {
            "name": name, "status": "运行中", "capital_pct": "100000",
            "signal": "—", "cum_return": cum_ret, "created": created,
            "folder": folder, "positions": None,
        }
        strategies = load_live_strategies()
        if any(s["name"] == name for s in strategies):
            return
        strategies.append(new_strat)
        save_live_strategies(strategies)
        self.refresh_live()

        # 后台线程计算持仓
        if folder:
            import threading
            result = {}

            def worker():
                try:
                    result["positions"] = calc_strat_positions(folder)
                except Exception as e:
                    result["error"] = str(e)

            def poll():
                if not result:
                    self.after(200, poll)
                    return
                if "error" in result:
                    return
                pos = result.get("positions")
                # 更新 JSON 中的 positions 字段
                live = load_live_strategies()
                for s in live:
                    if s["name"] == name:
                        s["positions"] = pos
                        break
                save_live_strategies(live)
                # 刷新组合持仓
                self.refresh_combined_positions()
                # 如果当前选中的就是这个策略，立即刷新下方表格
                sel_now = self.strat_tree.selection()
                if sel_now:
                    sel_item = self.strat_tree.item(sel_now[0])
                    if sel_item["values"] and sel_item["values"][0] == name:
                        self.refresh_live_strat_detail(name)

            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            self.after(200, poll)

    def show_detail(self, name, stats, equity, src_path):
        self.detail_title.config(text=f"📈  {name}")
        self.current_equity = equity

        self.stats_text.delete("1.0", END)
        for k in self.STAT_KEYS:
            if k in stats:
                v = stats[k]
                self.stats_text.insert(END, f"  {k}:  ", "stat_key")
                is_pct = "%" in v
                if is_pct or any(c in v for c in ("+", "-")):
                    try:
                        nv = float(v.replace("%", "").replace("+", "").replace(",", "").strip())
                        tag = "stat_val_pos" if nv >= 0 else "stat_val_neg"
                    except ValueError:
                        tag = "stat_val"
                else:
                    tag = "stat_val"
                self.stats_text.insert(END, v + "\n", tag)

        # 图表（支持自适应缩放）
        self._raw_pil_img = None
        self.img_canvas.delete("all")
        self.open_btn.config(state="normal" if equity else "disabled")

        if equity and os.path.exists(equity):
            try:
                self._raw_pil_img = Image.open(equity)
                self._render_chart()
            except Exception:
                pass
        # 绑定窗口大小变化事件（先解绑避免重复绑定）
        self.img_canvas.bind("<Configure>", self._on_canvas_resize, add="+")

        # 代码
        self._load_code(src_path or name)

    def _on_canvas_resize(self, event=None):
        """画布大小变化时重绘图表"""
        if self._raw_pil_img:
            self._render_chart()

    def _render_chart(self):
        """缩放并渲染图表到画布"""
        if not self._raw_pil_img:
            return
        try:
            self.img_canvas.delete("all")
            cw = self.img_canvas.winfo_width() - 16
            ch = self.img_canvas.winfo_height() - 16
            if cw < 100 or ch < 100:
                return
            img = self._raw_pil_img
            # 按比例缩放，适配画布
            ratio = min(cw / img.width, ch / img.height)
            new_w = max(200, int(img.width * ratio))
            new_h = max(150, int(img.height * ratio))
            img_small = img.resize((new_w, new_h), Image.LANCZOS)
            self._tk_img = ImageTk.PhotoImage(img_small)
            # 居中显示
            x = (cw - new_w) // 2 + 8
            y = (ch - new_h) // 2 + 8
            self.img_canvas.create_image(x, y, anchor="nw", image=self._tk_img)
        except Exception:
            pass

    def open_chart(self):
        if self.current_equity and os.path.exists(self.current_equity):
            subprocess.Popen(["cmd.exe", "/c", "start", "", self.current_equity],
                             shell=True)

    def _load_code(self, path_or_name):
        """加载策略源码到代码标签页（可编辑）。
        传入 src_path 直接加载，传入 name 则从 strategies/ 查找。
        """
        if os.path.isfile(path_or_name):
            src_path = path_or_name
        else:
            # fallback: 从 name 推导
            name = path_or_name
            import glob
            prefix = name.split("-")[0].split(" ")[0].lower()
            candidates = glob.glob(os.path.join(STRATEGIES_DIR, f"{prefix}_*.py"))
            if not candidates:
                candidates = glob.glob(os.path.join(STRATEGIES_DIR, f"{prefix}*.py"))
            src_path = candidates[0] if candidates else None

        self.code_text.delete("1.0", END)
        self.code_status.config(text="")
        if src_path and os.path.exists(src_path):
            with open(src_path, encoding="utf-8") as f:
                self.code_text.insert("1.0", f.read())
            self.current_src_path = src_path
        else:
            self.code_text.insert("1.0", f"# 未找到策略源码: {path_or_name}")
            self.current_src_path = None
        self.code_text.edit_reset()  # 清除 undo 历史
        self._highlight_code()  # 语法高亮

    def _highlight_code(self):
        """Python 语法高亮"""
        import re
        # 清除所有高亮标签
        for tag in ("kw", "str", "cmt", "num", "dec", "bif"):
            self.code_text.tag_remove(tag, "1.0", END)

        content = self.code_text.get("1.0", END)
        # 注释（# 开头，优先处理防止被其他规则匹配）
        for m in re.finditer(r'#[^\n]*', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.code_text.tag_add("cmt", start, end)
        # 字符串（单引号/双引号/三引号）
        for m in re.finditer(r'""".*?"""|\'\'\'.*?\'\'\'|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'',
                             content, re.DOTALL):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.code_text.tag_add("str", start, end)
        # 关键字
        keywords = r'\b(?:def|class|if|elif|else|for|while|return|import|from|as|pass|break|continue|and|or|not|in|is|None|True|False|raise|try|except|finally|with|yield|async|await|lambda|global|nonlocal|del|assert)\b'
        for m in re.finditer(keywords, content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.code_text.tag_add("kw", start, end)
        # 装饰器
        for m in re.finditer(r'@\w+', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.code_text.tag_add("dec", start, end)
        # 数字
        for m in re.finditer(r'\b\d+\.?\d*(?:[eE][+-]?\d+)?\b', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.code_text.tag_add("num", start, end)
        # 内置函数
        builtins = r'\b(?:print|len|range|int|float|str|list|dict|set|tuple|open|type|isinstance|hasattr|getattr|setattr|super|zip|map|filter|sorted|reversed|enumerate|abs|max|min|sum|round|any|all|bool|input|format|chr|ord|hex|bin|oct|eval|exec|repr|object|staticmethod|classmethod|property|__init__|__str__|__repr__|__call__)\b'
        for m in re.finditer(builtins, content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.code_text.tag_add("bif", start, end)

    def save_code(self):
        """保存编辑后的代码到源文件"""
        path = self.current_src_path
        if not path:
            self.code_status.config(text="⚠ 未关联源文件，无法保存", fg=ACCENT_GOLD)
            return
        code = self.code_text.get("1.0", "end-1c")
        try:
            # 语法检查：compile 一下
            compile(code, path, "exec")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            self.code_status.config(text="✅ 保存成功", fg=FG_GREEN)
            self.code_text.edit_modified(False)
        except SyntaxError as e:
            self.code_status.config(
                text=f"❌ 语法错误: 第{e.lineno}行 {e.msg}", fg=FG_RED)
        except Exception as e:
            self.code_status.config(
                text=f"❌ 保存失败: {e}", fg=FG_RED)

    def revert_code(self):
        """放弃编辑，重新从磁盘加载"""
        path = self.current_src_path
        if not path:
            return
        if self.code_text.edit_modified():
            self.code_status.config(text="↩ 已撤销修改", fg=FG_SECONDARY)
        else:
            self.code_status.config(text="已还原", fg=FG_SECONDARY)
        self._load_code(os.path.basename(path))


# ── DeepSeek 余额查询 ─────────────────────────────────────

def fetch_deepseek_balance(api_key):
    """调用 DeepSeek /user/balance 接口，返回 dict 或抛出异常"""
    import json, urllib.request
    url = "https://api.deepseek.com/user/balance"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "application/json")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read().decode())


def estimate_deepseek_consumption():
    """解析 Hermes agent.log，估算本月 DeepSeek API 消费量（token 数和花费金额）"""
    import re, os, datetime

    log_path = os.path.normpath(os.path.expanduser(
        "~/AppData/Local/hermes/logs/agent.log"))
    if not os.path.exists(log_path):
        return None

    # 获取本月起止日期
    now = datetime.datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_prefix = month_start.strftime("%Y-%m")  # 如 "2026-05"

    # 模型定价（$ / 1M tokens）
    PRICES = {
        "deepseek-v4-flash":     {"input": 0.30, "output": 0.50, "cache_input": 0.03},
        "deepseek-v4-pro":       {"input": 0.50, "output": 0.80, "cache_input": 0.05},
        "deepseek-chat":         {"input": 0.28, "output": 0.42, "cache_input": 0.028},
        "deepseek-reasoner":     {"input": 0.55, "output": 2.19, "cache_input": 0.055},
        "deepseek-reasoner-v4":  {"input": 0.60, "output": 2.50, "cache_input": 0.06},
    }
    DEFAULT_PRICE = {"input": 0.30, "output": 0.50, "cache_input": 0.03}

    # 正则：匹配成功 API 调用行
    # 格式: "2026-05-16 14:42:08,708 INFO ... API call #N: model=... in=X out=Y total=Z ... cache=HIT/TOTAL (PCT%)"
    pattern = re.compile(
        r"API call #\d+: model=(\S+) provider=deepseek in=(\d+) out=(\d+)"
    )
    cache_pattern = re.compile(r"cache=(\d+)/(\d+)")

    total_input = 0
    total_output = 0
    total_cache = 0
    total_calls = 0

    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            # 只处理本月
            if not line.startswith(month_prefix):
                continue
            m = pattern.search(line)
            if not m:
                continue
            model = m.group(1)
            in_tokens = int(m.group(2))
            out_tokens = int(m.group(3))
            total_calls += 1

            # 检测 cache
            cm = cache_pattern.search(line)
            cache_tokens = int(cm.group(1)) if cm else 0

            total_input += in_tokens
            total_output += out_tokens
            total_cache += cache_tokens

    if total_calls == 0:
        return {"calls": 0, "cost": 0.0, "token_str": "0 tokens"}

    # 按 v4-flash 定价估算花费（自用按最常用模型算）
    p = PRICES.get("deepseek-v4-flash", DEFAULT_PRICE)
    cost_input = (total_input - total_cache) * p["input"] / 1_000_000
    cost_cache = total_cache * p["cache_input"] / 1_000_000
    cost_output = total_output * p["output"] / 1_000_000
    total_cost = cost_input + cost_cache + cost_output

    # 友好显示 token 量
    def fmt_tokens(n):
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n/1_000:.0f}K"
        return str(n)

    token_str = (
        f"输入 {fmt_tokens(total_input)} | 输出 {fmt_tokens(total_output)} "
        f"| 缓存 {fmt_tokens(total_cache)}"
    )

    return {
        "calls": total_calls,
        "cost": round(total_cost, 2),
        "token_str": token_str,
        "tokens": {"input": total_input, "output": total_output, "cache": total_cache},
    }


class BalanceWindow(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("💰 DeepSeek 账户余额")
        self.geometry("380x280")
        self.resizable(False, False)
        self.configure(bg=BG_PRIMARY)
        self.transient(parent)          # 置顶于主窗口
        self.grab_set()                 # 模态

        # 居中
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = 380, 280
        self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")

        # 标题
        title = Label(self, text="DeepSeek 账户余额",
                      font=("Microsoft YaHei", 14, "bold"),
                      fg=FG_PRIMARY, bg=BG_PRIMARY, pady=12)
        title.pack()

        # 加载状态
        self.loading = Label(self, text="⏳ 查询中...",
                             font=("Microsoft YaHei", 10),
                             fg=FG_SECONDARY, bg=BG_PRIMARY)
        self.loading.pack(pady=20)

        # 内容帧（初始隐藏）
        self.info_frame = Frame(self, bg=BG_PRIMARY)

        self.cur_label = Label(self.info_frame, text="",
                               font=("Microsoft YaHei", 11),
                               fg=FG_PRIMARY, bg=BG_PRIMARY, anchor="w")
        self.cur_label.pack(fill=X, pady=3, padx=30)
        self.total_label = Label(self.info_frame, text="",
                                 font=("Microsoft YaHei", 11),
                                 fg=FG_GREEN, bg=BG_PRIMARY, anchor="w")
        self.total_label.pack(fill=X, pady=3, padx=30)
        self.granted_label = Label(self.info_frame, text="",
                                   font=("Microsoft YaHei", 11),
                                   fg=ACCENT_BLUE, bg=BG_PRIMARY, anchor="w")
        self.granted_label.pack(fill=X, pady=3, padx=30)
        self.topped_label = Label(self.info_frame, text="",
                                  font=("Microsoft YaHei", 11),
                                  fg=ACCENT_GOLD, bg=BG_PRIMARY, anchor="w")
        self.topped_label.pack(fill=X, pady=3, padx=30)
        self.status_label = Label(self.info_frame, text="",
                                  font=("Microsoft YaHei", 12, "bold"),
                                  fg=FG_GREEN, bg=BG_PRIMARY, anchor="w")
        self.status_label.pack(fill=X, pady=6, padx=30)

        # 本月消费
        self.consumption_label = Label(self.info_frame, text="",
                                       font=("Microsoft YaHei", 10),
                                       fg=ACCENT_BLUE, bg=BG_PRIMARY, anchor="w")
        self.consumption_label.pack(fill=X, pady=(0, 2), padx=30)

        # 刷新按钮
        btn_frame = Frame(self.info_frame, bg=BG_PRIMARY)
        btn_frame.pack(pady=8)
        refresh_btn = Button(btn_frame, text="↻ 刷新",
                             font=("Microsoft YaHei", 10),
                             fg=FG_PRIMARY, bg=BG_TERTIARY, bd=0,
                             padx=16, pady=4,
                             activebackground=BG_ELEVATED, activeforeground=FG_PRIMARY,
                             command=self.refresh, cursor="hand2")
        refresh_btn.pack()

        # 错误信息
        self.error_label = Label(self, text="",
                                 font=("Microsoft YaHei", 9),
                                 fg=FG_RED, bg=BG_PRIMARY, wraplength=340)
        self.error_label.pack(pady=(0, 10))

        # 自动查询
        self.after(200, self.refresh)

    def refresh(self):
        """重新查询余额"""
        import os, json
        self.loading.pack(pady=20)
        self.info_frame.pack_forget()
        self.error_label.config(text="")

        # 从 auth.json 读取 key
        api_key = ""
        auth_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "..", "AppData", "Local", "hermes", "auth.json")
        auth_path = os.path.normpath(os.path.expanduser(auth_path))
        try:
            if os.path.exists(auth_path):
                with open(auth_path) as f:
                    data = json.load(f)
                pool = data.get("credential_pool", {})
                ds_keys = pool.get("deepseek", [])
                if ds_keys:
                    api_key = ds_keys[0].get("access_token", "")
        except Exception:
            pass

        if not api_key:
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")

        if not api_key:
            self.loading.pack_forget()
            self.error_label.config(
                text="❌ 未找到 DeepSeek API Key\n请检查 auth.json 或 DEEPSEEK_API_KEY 环境变量")
            return

        # 后台线程查询，避免阻塞 UI
        import threading
        result = {}

        def worker():
            try:
                data = fetch_deepseek_balance(api_key)
                result["ok"] = data
            except Exception as e:
                result["err"] = str(e)
                return

            # 异步估算本月消费量
            try:
                consumption = estimate_deepseek_consumption()
                result["consumption"] = consumption
            except Exception:
                pass

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        self._poll_worker(thread, result)

    def _poll_worker(self, thread, result):
        if thread.is_alive():
            self.after(200, lambda: self._poll_worker(thread, result))
            return
        self.loading.pack_forget()

        if "err" in result:
            self.error_label.config(text=f"❌ 查询失败: {result['err']}")
            return

        data = result["ok"]
        infos = data.get("balance_infos", [])
        if not infos:
            self.error_label.config(text="❌ 未获取到余额信息")
            return

        info = infos[0]
        currency = info.get("currency", "CNY")
        total = info.get("total_balance", "—")
        granted = info.get("granted_balance", "—")
        topped = info.get("topped_up_balance", "—")
        available = data.get("is_available", False)

        symbol = "¥" if currency == "CNY" else "$"
        self.cur_label.config(text=f"币种：  {currency}")
        self.total_label.config(text=f"总余额：  {symbol}{total}")
        self.granted_label.config(text=f"赠送余额：{symbol}{granted}")
        self.topped_label.config(text=f"充值余额：{symbol}{topped}")

        if available:
            status_text = "✅ 余额充足"
            status_color = FG_GREEN
        else:
            status_text = "⚠️ 余额不足"
            status_color = ACCENT_GOLD
        self.status_label.config(text=status_text, fg=status_color)

        # 显示本月消费估算
        consumption = result.get("consumption")
        if consumption:
            calls = consumption["calls"]
            cost = consumption["cost"]
            token_str = consumption["token_str"]
            self.consumption_label.config(
                text=f"📊 本月调用：{calls} 次 | 约 ${cost:.2f}\n{token_str}")
        else:
            self.consumption_label.config(text="📊 本月消费：日志不足（仅显示5月12日起数据）")

        self.info_frame.pack(fill=BOTH, expand=True, padx=10)


if __name__ == "__main__":
    app = App()
    app.mainloop()
