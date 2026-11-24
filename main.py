#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SnapPaste - 一键复制粘贴 + 截图贴图 (合并版)
================================================
由「一键复制粘贴工具」(2012, Delphi 加壳版) 重写、并合入 Snipaste 核心功能而来:
  文字: 多次复制队列 / 顺序·全部粘贴 / 分割·正则 / 大小写 / 搜索 / 去重 / 锁定
  图片: F1 区域截图 (窗口吸附·取色) / 标注编辑器 / F3 贴图钉屏 / 历史画廊
  识别: OCR / 二维码·条码 (可选引擎 rapidocr-onnxruntime / opencv)
  热键: 7 个动作全部预设可自定义, 保存于 Config.ini, 改键立即生效
v1.3 二次审查修复 (详见 docs/二次审查报告.md):
  搜索过滤下选错记录 / 全局热键跨线程调 Tk / 同秒截图覆盖 / 配置追加重复段 /
  大图编辑器溢出 / 贴图滚轮双倍缩放 / OCR 引擎重复加载 等
依赖: Pillow (截图必需); keyboard (全局热键, 可选); 其余见 requirements.txt
运行: python main.py    打包: build_windows.bat (PyInstaller, 无加壳, 无联网)
"""
import configparser, ctypes, datetime, json, os, queue, re, sys, time
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageGrab, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "SnapPaste 复制粘贴+截图贴图"
VERSION = "1.4.8"  # v1.4.8: 去掉「加载配置/保存配置」按钮 (用户反馈没意义), 所有设置改完自动保存且重开恢复 (分隔方式/自定义分隔符/间隔/分割字符/分割位置)
# v1.4.7: 新增一键截图翻译 (F4 预设, 自动检测源语言, 目标语言主窗口可设中文/English) + v1.4.6 的工具栏同窗/图片复制双通道/窗口自适应高度
# v1.4.6: 标注工具栏改冻结屏同窗 Frame (独立小窗真机反复不显示) + 图片复制补全 Win32 签名并加 PowerShell 备用通道 + 主窗口按内容自适应高度 (底部不再被裁)
# v1.4.5: 数据目录改到 %APPDATA%\SnapPaste, 桌面只剩单个 EXE (老数据首次运行自动从 EXE 旁搬移) + v1.4.4 的 Esc 焦点修复
# v1.4.4: 修复框选/检测元素阶段 Esc 退不出 (覆盖层被热键从别的程序唤起时抢不到键盘焦点, Esc 落到原程序): 打开覆盖层时用 AttachThreadInput 强抢前台焦点, 并挂临时全局 Esc (覆盖层关闭即注销)
# v1.4.3: 系统托盘 (点 X 隐藏到右下角托盘, 双击图标打开, 右键菜单截图/贴图/退出; 依赖 pystray) / 标注工具栏改两排并加固放置 + 选区右键菜单兜底 / 识别线条黄改蓝 / 放大镜改 PixPin 式网格+蓝色十字+深色信息卡 (坐标/色块/HEX/RGB 跟随光标) / 文字贴图加关闭提示
# v1.4.2: 工具栏改两排并加固放置 (真机出现标注后找不到保存/复制: 工具栏尺寸在窗口未映射时取到 1x1 被放错位; 改用请求尺寸+显式尺寸+置顶, 并加选区右键菜单兜底) / 文字贴图加关闭提示与右键菜单
# v1.4.1: 热键吞键 (F7 不再被 WPS 抢) / WPS 打字粘贴 / 粘后自动删 / 截图翻译 / UI 检测三模式 / 贴图动作组 / 长截图 / GIF 录制 / 序号标注 / F5 截图并复制 / 三次审查修复
MAX_RECORDS = 2000  # 记录上限: 超出时自动丢弃最旧的未锁定记录, 防 records.json 无限膨胀
# 开箱即用预设热键: 用户不用自己设置, 打开就能用; 想改再去「热键设置」
DEFAULT_HOTKEYS = {"HotKey8": "F6", "HotKey9": "F7", "HotKey10": "F8",
                   "HotKey11": "F9", "HotKey12": "SHIFT+F9"}
# Snipaste 习惯键: F1 截图 / F3 贴图, 放在 Config.ini [Snip] 段
DEFAULT_SNIP_KEYS = {"SnipKey": "F1", "PinKey": "F3", "CopyKey": "F5", "TransKey": "F4", "DelayKey": "无",
                     "ClosePinsKey": "无", "TogglePinsKey": "无", "RestorePinKey": "无", "ClickThroughKey": "无"}
# 数据目录: 源码运行时在 main.py 旁; 打成 EXE 后数据统一放 %APPDATA%\SnapPaste,
# 桌面上只剩一个 SnapPaste.exe (v1.4.5, 用户反馈 Config/records/Language/shots/ding 散落一桌)。
# 注意也不能用 _MEIPASS 临时目录: 那是单文件解压目录, 关程序就全丢 (v1.3.2 审查发现)。
if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE = getattr(sys, "_MEIPASS", EXE_DIR)  # EXE 内置的默认文件 (打包时 --add-data 带入)
    BASE = os.path.join(os.environ.get("APPDATA") or EXE_DIR, "SnapPaste")
    try: os.makedirs(BASE, exist_ok=True)
    except Exception: BASE = EXE_DIR  # AppData 建不了时退回 EXE 旁 (老行为, 至少能用)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
    BUNDLE = BASE
    EXE_DIR = BASE
CONFIG_PATH = os.path.join(BASE, "Config.ini")
RECORDS_PATH = os.path.join(BASE, "records.json")

def _migrate_old_data():
    """老版本 (<=v1.4.4) 数据在 EXE 旁: 首次用 AppData 数据目录时整套搬过来, 配置/记录/截图不丢"""
    if not getattr(sys, "frozen", False) or os.path.abspath(BASE) == os.path.abspath(EXE_DIR): return
    if os.path.exists(os.path.join(BASE, "Config.ini")): return  # 新目录已有数据, 不再搬
    import shutil
    for rel in ("Config.ini", "records.json", "ding.wav",
                os.path.join("Language", "Chinese.ini"), os.path.join("Language", "English.ini")):
        src, dst = os.path.join(EXE_DIR, rel), os.path.join(BASE, rel)
        if os.path.exists(src) and not os.path.exists(dst):
            try: os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(src, dst)
            except Exception: pass
    old_shots, new_shots = os.path.join(EXE_DIR, "shots"), os.path.join(BASE, "shots")
    if os.path.isdir(old_shots):
        try:
            os.makedirs(new_shots, exist_ok=True)
            for name in os.listdir(old_shots):
                s, d = os.path.join(old_shots, name), os.path.join(new_shots, name)
                if os.path.isfile(s) and not os.path.exists(d):
                    try: shutil.copy(s, d)
                    except Exception: pass
        except Exception: pass

def ensure_runtime_files():
    """EXE 首次运行: 先搬老数据 (EXE 旁 -> AppData), 再把内置默认文件释放到数据目录; 已存在的不覆盖"""
    import shutil
    _migrate_old_data()
    for rel in ("Config.ini", "ding.wav", os.path.join("Language", "Chinese.ini"), os.path.join("Language", "English.ini")):
        src, dst = os.path.join(BUNDLE, rel), os.path.join(BASE, rel)
        if not os.path.exists(dst) and os.path.exists(src):
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(src, dst)
            except Exception: pass

# Win32 SendInput 结构: 必须带完整 union, 否则 sizeof(INPUT) 不是系统要求的 40 字节 (x64), 调用会被拒绝
class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_uint32),
                ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_void_p)]
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_int), ("dy", ctypes.c_int), ("mouseData", ctypes.c_uint32),
                ("dwFlags", ctypes.c_uint32), ("time", ctypes.c_uint32),
                ("dwExtraInfo", ctypes.c_void_p)]
class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_uint32), ("wParamL", ctypes.c_ushort), ("wParamH", ctypes.c_ushort)]
class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]
class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("u", _INPUTUNION)]

def enable_hidpi():
    if sys.platform == "win32":
        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try: ctypes.windll.user32.SetProcessDPIAware()
            except Exception: pass

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_runtime_files()
        enable_hidpi()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("680x580"); self.minsize(600, 500)  # v1.3: 内容区变高, 旧 460 高会裁掉底部状态栏
        self.records = []          # [{"text": str, "locked": bool}]
        self._visible = []         # 列表框行号 -> records 下标 (搜索过滤时两者不一致, 必须映射)
        self._ui_queue = queue.Queue()  # 全局热键在 keyboard 线程触发, 只能排队回主线程执行 Tk 操作
        self._pins = []                # 当前所有贴图窗口 (供 关闭全部/隐藏全部/穿透 等动作统一管理)
        self._last_closed_pin = None   # 最近关闭的那张贴图的图片, 供「恢复上次关闭的贴图」
        self._pins_clickthrough = False
        self._snip_finish_mode = None  # 本次截图的特殊完成方式 (如 "copy" = 框选完直接复制, 不停留标注)
        self._tray = None              # 系统托盘图标 (pystray), 没装该库时为 None, 点 X 直接退出
        self._tray_notified = False    # 「已隐藏到托盘」的气泡只提示一次
        self.paste_index = 0
        self._hk_handles = []      # keyboard 包返回的句柄, 改热键时注销旧的
        self._oc_handle = None     # 全局切换热键的句柄 (单独管理, 关掉全部热键时它要留着)
        self._hk_enabled = True
        self._mini_win = None; self._mini_after = None
        self._tk_sequences = []    # 窗口内绑定的序列, 改热键时解绑旧的
        self.cfg = self.load_config()
        self._load_lang()
        self.build_ui()
        self._fit_window_to_content()
        self.load_records()
        self.refresh_list()
        self.refresh_shots()
        self.apply_hotkeys()
        self.apply_autorun()
        self._setup_tray()
        if self.cfg.get("Config", "MiniFormSet", fallback="0") == "1": self.after(300, self.show_mini)  # 常显模式: 启动即显示迷你窗口
        self.after(60, self._poll_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    def _fit_window_to_content(self):
        # 按内容实际需要的尺寸定窗口大小: 写死的 680x580 在高缩放 (125%/150%) 屏幕上装不下全部功能,
        # 底部截图按钮和状态栏会被裁掉, 要手动往下拉高才看得全 (真机反馈)。打开即按内容定高, 最小高度也锁到内容高度。
        try:
            self.update_idletasks()
            req_w, req_h = self.winfo_reqwidth(), self.winfo_reqheight()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w = min(max(680, req_w), sw)
            h = min(req_h, max(500, sh - 50))
            self.geometry(f"{w}x{h}")
            self.minsize(min(620, w), h)
        except Exception: pass
    def _poll_ui_queue(self):
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                try: fn()
                except Exception: pass
        except queue.Empty: pass
        try: self.after(60, self._poll_ui_queue)
        except tk.TclError: pass

    # ---------- config (兼容原版字段) ----------
    def load_config(self):
        c = configparser.ConfigParser()
        defaults = {f"HotKey{i}": "无" for i in range(13)}; defaults.update(DEFAULT_HOTKEYS)
        c.read_dict({"Config": {"SleepTime": "80", "WaveSet": "0", "AutoRun": "0", "Language": "Chinese", "PasteEnter": "0", "PasteRemove": "1",
                                "MiniFormTime": "5", "MiniFormSet": "0", "AddChar": "1", "LetterSet": "0"},
                     "HotKey": defaults, "Snip": dict(DEFAULT_SNIP_KEYS),
                     "OCHotKey": {"HotKey": "无", "OCAutoSet": "0"}})
        if os.path.exists(CONFIG_PATH):
            # 原版是 GBK, 新版是 UTF-8: 依次尝试, 不再乱码
            for enc in ("utf-8-sig", "gbk"):
                try: c.read(CONFIG_PATH, encoding=enc); break
                except Exception: continue
        return c
    def _load_lang(self):
        """语言: 读 Language/<Language>.ini 的 [UI] 段 (沿用原版的语言文件机制); 缺键时回退到代码里的中文原文"""
        self.lang = self.cfg.get("Config", "Language", fallback="Chinese").strip() or "Chinese"
        self._strings = {}
        p = os.path.join(BASE, "Language", f"{self.lang}.ini")
        if os.path.exists(p):
            lp = configparser.ConfigParser()
            for enc in ("utf-8-sig", "gbk"):
                try: lp.read(p, encoding=enc); break
                except Exception: continue
            if lp.has_section("UI"): self._strings = dict(lp.items("UI"))
    def t(self, key, zh):
        return self._strings.get(key, zh)
    def save_config(self):
        # v1.1 修复: 原地更新已有 key, 保住 Config.ini 里的注释和排版 (旧版 configparser.write 会全抹掉)
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "w", encoding="utf-8") as f: self.cfg.write(f)
            return
        lines = open(CONFIG_PATH, encoding="utf-8").read().splitlines()
        pending = {(sec, k.lower()): v for sec in self.cfg.sections() for k, v in self.cfg.items(sec)}
        out, cur = [], None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                cur = stripped[1:-1].strip()
            elif cur and "=" in line and not stripped.startswith((";", "#")):
                key = line.split("=", 1)[0].strip().lower()
                if (cur, key) in pending:
                    line = f"{line.split('=', 1)[0].strip()}={pending.pop((cur, key))}"
            out.append(line)
        # 文件里没有的键: 段已存在就插入该段末尾; 段不存在才在文件尾新建段。
        # (旧写法一律在文件尾追加 [段], 会造出重复段, 下次读取 DuplicateSectionError 后静默丢配置)
        by_sec = {}
        known_case = {k.lower(): k for k in list(DEFAULT_HOTKEYS) + list(DEFAULT_SNIP_KEYS) +
                      ["SleepTime", "WaveSet", "WaveFile", "AutoRun", "AutoSet", "MiniFormTime", "MiniFormSet", "Language", "PasteEnter", "PasteRemove",
                       "SplitPos", "AddChar", "LetterSet", "HotKey", "OCAutoSet", "Form1XY", "Form2XY", "UIDetect", "HistoryMax", "DelaySeconds",
                       "Separator", "CustomSep", "SplitChar", "RegexSel", "CaseSel", "TransTarget"]}
        for (sec, k), v in pending.items(): by_sec.setdefault(sec, []).append((known_case.get(k, k), v))
        for sec, items in by_sec.items():
            headers = [i for i, ln in enumerate(out) if ln.strip().lower() == f"[{sec.lower()}]"]
            if headers:
                nxt = next((i for i in range(headers[0] + 1, len(out)) if out[i].strip().startswith("[")), len(out))
                out[nxt:nxt] = [f"{k}={v}" for k, v in items]
            else:
                out += [f"[{sec}]"] + [f"{k}={v}" for k, v in items]
        with open(CONFIG_PATH, "w", encoding="utf-8") as f: f.write("\n".join(out) + "\n")
    @property
    def sleep_ms(self): return max(10, self.cfg.getint("Config", "SleepTime", fallback=80))

    # ---------- UI ----------
    def build_ui(self):
        bar = ttk.Frame(self); bar.pack(fill="x", padx=8, pady=6)
        for txt, cmd in [(self.t("hotkey_settings", "热键设置"), self.open_hotkey_dialog),
                         (self.t("import_text", "导入文本"), self.import_txt), (self.t("export_text", "导出文本"), self.export_txt)]:
            ttk.Button(bar, text=txt, command=cmd).pack(side="left", padx=2)
        self.search_var = tk.StringVar(); self.search_var.trace_add("write", lambda *a: self.refresh_list())
        ttk.Entry(bar, textvariable=self.search_var, width=14).pack(side="right")
        ttk.Label(bar, text=self.t("search", "搜索:")).pack(side="right")
        self.lang_var = tk.StringVar(value=self.lang)
        lang_box = ttk.Combobox(bar, textvariable=self.lang_var, width=9, state="readonly", values=["Chinese", "English"])
        lang_box.pack(side="right", padx=(0, 6)); lang_box.bind("<<ComboboxSelected>>", self._switch_language)
        ttk.Label(bar, text=self.t("lang_label", "语言:")).pack(side="right")

        mid = ttk.Frame(self); mid.pack(fill="both", expand=True, padx=8)
        # 记录列表按原版分两列: 序号 | 文本内容 (Treeview; 内部沿用 listbox 这个名字, 行 id 存 _row_iids 与 _visible 对齐)
        self.listbox = ttk.Treeview(mid, columns=("no", "text"), show="headings", selectmode="browse")
        self.listbox.heading("no", text=self.t("col_no", "序号")); self.listbox.heading("text", text=self.t("col_text", "文本内容"))
        self.listbox.column("no", width=52, anchor="center", stretch=False); self.listbox.column("text", anchor="w")
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, command=self.listbox.yview); sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=sb.set)
        self._row_iids = []
        ops = ttk.Frame(mid); ops.pack(side="left", fill="y", padx=6)
        for txt, cmd in [(self.t("lock_unlock", "锁定/解锁"), self.toggle_lock), (self.t("delete_selected", "删除选定"), self.delete_sel),
                         (self.t("delete_all", "删除全部"), self.delete_all), (self.t("move_up", "上移"), lambda: self.move(-1)),
                         (self.t("move_down", "下移"), lambda: self.move(1)), (self.t("dedupe", "去重"), self.dedupe)]:
            ttk.Button(ops, text=txt, command=cmd).pack(fill="x", pady=2)

        opt = ttk.LabelFrame(self, text=self.t("paste_options", "粘贴选项")); opt.pack(fill="x", padx=8, pady=6)
        opt1 = ttk.Frame(opt); opt1.pack(fill="x")
        opt2 = ttk.Frame(opt); opt2.pack(fill="x", pady=(4, 0))
        self.sep_var = tk.StringVar(value=self.cfg.get("Config", "Separator", fallback="enter"))
        for txt, val in [(self.t("sep_enter", "记录间回车"), "enter"), (self.t("sep_tab", "记录间 TAB"), "tab"), (self.t("sep_none", "无分隔"), "none")]:
            ttk.Radiobutton(opt1, text=txt, variable=self.sep_var, value=val, command=self._save_entry_settings).pack(side="left", padx=4)
        ttk.Label(opt1, text=self.t("custom", "自定义:")).pack(side="left")
        self.custom_sep_var = tk.StringVar(value=self.cfg.get("Config", "CustomSep", fallback=""))
        self.custom_sep = ttk.Entry(opt1, width=6, textvariable=self.custom_sep_var); self.custom_sep.pack(side="left")
        self.custom_sep.bind("<FocusOut>", lambda _e: self._save_entry_settings()); self.custom_sep.bind("<Return>", lambda _e: self._save_entry_settings())
        ttk.Label(opt1, text=self.t("interval", "间隔(ms):")).pack(side="left", padx=(10,0))
        self.sleep_var = tk.StringVar(value=str(self.sleep_ms))
        _sle = ttk.Entry(opt1, textvariable=self.sleep_var, width=6); _sle.pack(side="left")
        _sle.bind("<FocusOut>", lambda _e: self._save_entry_settings()); _sle.bind("<Return>", lambda _e: self._save_entry_settings())
        self.autorun_var = tk.BooleanVar(value=self.cfg.get("Config", "AutoRun", fallback="0") == "1")
        ttk.Checkbutton(opt1, text=self.t("autorun", "开机自动运行"), variable=self.autorun_var, command=self._toggle_autorun).pack(side="left", padx=(10, 0))
        self.paste_enter_var = tk.BooleanVar(value=self.cfg.get("Config", "PasteEnter", fallback="0") == "1")
        ttk.Checkbutton(opt2, text=self.t("paste_enter", "顺序粘贴后自动回车"), variable=self.paste_enter_var, command=self._toggle_paste_enter).pack(side="left", padx=4)
        self.paste_remove_var = tk.BooleanVar(value=self.cfg.get("Config", "PasteRemove", fallback="1") == "1")
        ttk.Checkbutton(opt2, text=self.t("paste_remove", "顺序粘贴后自动删除该条"), variable=self.paste_remove_var, command=self._toggle_paste_remove).pack(side="left", padx=(10, 0))

        mini = ttk.LabelFrame(self, text=self.t("mini_frame", "迷你窗口 (复制/粘贴时自动悬浮)")); mini.pack(fill="x", padx=8, pady=6)
        ttk.Label(mini, text=self.t("mini_time", "悬浮显示时间(秒, 0=不显示):")).pack(side="left")
        self.mini_time_var = tk.StringVar(value=self.cfg.get("Config", "MiniFormTime", fallback="5"))
        _me = ttk.Entry(mini, textvariable=self.mini_time_var, width=5); _me.pack(side="left")
        _me.bind("<FocusOut>", lambda _e: self._save_mini_settings()); _me.bind("<Return>", lambda _e: self._save_mini_settings())
        self.mini_always_var = tk.BooleanVar(value=self.cfg.get("Config", "MiniFormSet", fallback="0") == "1")
        ttk.Checkbutton(mini, text=self.t("mini_always", "常显 (不自动隐藏)"), variable=self.mini_always_var, command=self._save_mini_settings).pack(side="left", padx=6)
        ttk.Button(mini, text=self.t("mini_show_btn", "立即显示"), command=lambda: self.show_mini()).pack(side="left", padx=4)

        act = ttk.Frame(self); act.pack(fill="x", padx=8, pady=4)
        for txt, cmd in [(self.t("multi_copy_btn", "多次复制 (加入队列)"), self.multi_copy), (self.t("paste_next_btn", "顺序粘贴下一条"), self.paste_next),
                         (self.t("paste_all_btn", "全部粘贴"), self.paste_all), (self.t("power_paste_btn", "强力粘贴选定"), self.paste_selected)]:
            ttk.Button(act, text=txt, command=cmd).pack(side="left", padx=2)

        split = ttk.LabelFrame(self, text=self.t("split_frame", "剪切/复制时分割 (可选)")); split.pack(fill="x", padx=8, pady=6)
        ttk.Label(split, text=self.t("split_char", "分割字符:")).pack(side="left")
        self.split_var = tk.StringVar(value=self.cfg.get("Config", "SplitChar", fallback=""))
        self.split_entry = ttk.Entry(split, width=8, textvariable=self.split_var); self.split_entry.pack(side="left")
        self.split_entry.bind("<FocusOut>", lambda _e: self._save_entry_settings()); self.split_entry.bind("<Return>", lambda _e: self._save_entry_settings())
        self.regex_var = tk.StringVar(value=self.cfg.get("Config", "RegexSel", fallback=""))
        ttk.Combobox(split, textvariable=self.regex_var, width=14, values=["", self.t("regex_numbers", "所有数字"), self.t("regex_lower", "所有小写字母"), self.t("regex_upper", "所有大写字母"), self.t("regex_enter", "回车符"), self.t("regex_tab", "制表符")]).pack(side="left", padx=4)
        self.case_var = tk.StringVar(value=self.cfg.get("Config", "CaseSel", fallback=""))
        ttk.Combobox(split, textvariable=self.case_var, width=10, values=["", self.t("case_upper", "转大写"), self.t("case_lower", "转小写")]).pack(side="left", padx=4)
        self._splitpos_values = [self.t("splitpos_none", "不保留分隔符"), self.t("splitpos_after", "分隔符留在前段"), self.t("splitpos_before", "分隔符留在后段")]
        try: _sp_idx = int(self.cfg.get("Config", "SplitPos", fallback="0"))
        except Exception: _sp_idx = 0
        self.splitpos_var = tk.StringVar(value=self._splitpos_values[_sp_idx if 0 <= _sp_idx < 3 else 0])
        ttk.Combobox(split, textvariable=self.splitpos_var, width=12, values=self._splitpos_values).pack(side="left", padx=4)
        ttk.Button(split, text=self.t("split_import_btn", "按分割导入剪贴板"), command=self.import_clipboard_split).pack(side="left", padx=4)

        snip = ttk.LabelFrame(self, text=self.t("snip_frame", "截图贴图 (合并自 Snipaste 核心功能, 需 Pillow)"))
        snip.pack(fill="x", padx=8, pady=6)
        snip2 = ttk.Frame(snip); snip2.pack(fill="x")
        ttk.Label(snip2, text=self.t("ui_detect", "UI 检测:")).pack(side="left", padx=(2, 0), pady=2)
        self.ui_detect_var = tk.StringVar(value=self.cfg.get("Snip", "UIDetect", fallback="2"))
        for txt, val in [(self.t("detect_none", "不检测"), "0"), (self.t("detect_win", "仅窗口"), "1"), (self.t("detect_elem", "检测元素"), "2")]:
            ttk.Radiobutton(snip2, text=txt, variable=self.ui_detect_var, value=val, command=self._save_ui_detect).pack(side="left", padx=2)
        snip3 = ttk.Frame(snip); snip3.pack(fill="x")
        ttk.Label(snip3, text=self.t("trans_target", "截图翻译目标语言:")).pack(side="left", padx=(2, 0), pady=2)
        self.trans_target_var = tk.StringVar(value="中文" if self.trans_target() == "zh-CN" else "English")
        ttk.Combobox(snip3, textvariable=self.trans_target_var, values=["中文", "English"], width=8, state="readonly").pack(side="left", padx=2)
        self.trans_target_var.trace_add("write", lambda *_: self._save_trans_target())
        for txt, cmd in [(self.t("snip_region", "区域截图 (F1)"), self.snip_region), (self.t("snip_copy_btn", "截图并复制 (F5)"), self.snip_copy), (self.t("snip_trans_btn", "截图翻译 (F4)"), self.snip_translate), (self.t("pin_clip", "贴剪贴板 (F3)"), self.pin_clipboard),
                         (self.t("pin_selected", "钉住选中截图"), self.pin_selected_shot), (self.t("gallery", "历史画廊"), self.open_gallery),
                         (self.t("ocr_selected", "OCR 选中截图"), self.ocr_selected_shot), (self.t("open_shots_dir", "打开截图文件夹"), self.open_shots_dir)]:
            ttk.Button(snip, text=txt, command=cmd).pack(side="left", padx=2, pady=4)
        self.shots_list = tk.Listbox(snip, height=3); self.shots_list.pack(side="left", fill="x", expand=True, padx=6, pady=4)
        self.shots_list.bind("<<ListboxSelect>>", self.preview_shot)
        self.shot_preview = tk.Label(snip, text=self.t("shot_preview", "(选中截图\n看预览)"), fg="gray"); self.shot_preview.pack(side="left", padx=4)

        self.status = tk.StringVar(value=self.t("ready", "就绪"))
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x", padx=8, pady=4)
        self.bind("<Delete>", lambda e: self.delete_sel())
        for _v in (self.regex_var, self.case_var, self.splitpos_var):  # 分割区的下拉改完即存
            _v.trace_add("write", lambda *_: self._save_entry_settings())

    def _toggle_autorun(self):
        if not self.cfg.has_section("Config"): self.cfg.add_section("Config")
        self.cfg.set("Config", "AutoRun", "1" if self.autorun_var.get() else "0")
        self.save_config(); self.apply_autorun()
    def _toggle_paste_enter(self):
        if not self.cfg.has_section("Config"): self.cfg.add_section("Config")
        self.cfg.set("Config", "PasteEnter", "1" if self.paste_enter_var.get() else "0")
        self.save_config()
    def _save_entry_settings(self):
        # 分隔方式/自定义分隔符/间隔/分割字符/分割区下拉: 改完即存 (v1.4.8 起去掉「保存配置」按钮, 全部设置自动保存)
        if not self.cfg.has_section("Config"): self.cfg.add_section("Config")
        self.cfg.set("Config", "Separator", self.sep_var.get())
        self.cfg.set("Config", "CustomSep", self.custom_sep_var.get())
        v = (self.sleep_var.get() or "80").strip()
        self.cfg.set("Config", "SleepTime", v if v.isdigit() else "80")
        self.cfg.set("Config", "SplitChar", self.split_var.get())
        self.cfg.set("Config", "RegexSel", self.regex_var.get())
        self.cfg.set("Config", "CaseSel", self.case_var.get())
        try: idx = self._splitpos_values.index(self.splitpos_var.get())
        except Exception: idx = 0
        self.cfg.set("Config", "SplitPos", str(idx))
        self.save_config()
    def _save_ui_detect(self):
        if not self.cfg.has_section("Snip"): self.cfg.add_section("Snip")
        self.cfg.set("Snip", "UIDetect", self.ui_detect_var.get()); self.save_config()
    def _save_trans_target(self):
        if not self.cfg.has_section("Snip"): self.cfg.add_section("Snip")
        self.cfg.set("Snip", "TransTarget", "zh-CN" if self.trans_target_var.get() == "中文" else "en")
        self.save_config()
    def _toggle_paste_remove(self):
        if not self.cfg.has_section("Config"): self.cfg.add_section("Config")
        self.cfg.set("Config", "PasteRemove", "1" if self.paste_remove_var.get() else "0")
        self.save_config()
    def _save_mini_settings(self):
        if not self.cfg.has_section("Config"): self.cfg.add_section("Config")
        try: secs = max(0, int(self.mini_time_var.get()))
        except Exception: secs = 5
        self.mini_time_var.set(str(secs))
        self.cfg.set("Config", "MiniFormTime", str(secs))
        self.cfg.set("Config", "MiniFormSet", "1" if self.mini_always_var.get() else "0")
        self.save_config()
        if self.mini_always_var.get(): self.show_mini()
    def apply_autorun(self):
        """开机自启 (原版 AutoRun): 写/删 HKCU Run 项; 只对 Windows 生效"""
        if sys.platform != "win32": return
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if self.cfg.get("Config", "AutoRun", fallback="0") == "1":
                exe = sys.executable
                cmd = f'"{exe}"' if getattr(sys, "frozen", False) else f'"{exe}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(key, "SnapPaste", 0, winreg.REG_SZ, cmd)
            else:
                try: winreg.DeleteValue(key, "SnapPaste")
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception: pass
    def _refresh_mini(self):
        """迷你窗口的列表与主列表保持同步 (迷你窗不带搜索过滤, 行号即记录号; 同样分 序号|文本内容 两列)"""
        try:
            if self._mini_win is None or not self._mini_win.winfo_exists() or not hasattr(self, "_mini_list"): return
            sel_row = self._mini_row()
            self._mini_list.delete(*self._mini_list.get_children()); self._mini_iids = []
            for i, r in enumerate(self.records):
                prefix = "🔒 " if r["locked"] else ""
                no = f"▶{i + 1}" if i == self.paste_index else str(i + 1)
                self._mini_iids.append(self._mini_list.insert("", "end", values=(no, f"{prefix}{r['text'][:80]}")))
            if 0 <= sel_row < len(self._mini_iids): self._mini_list.selection_set(self._mini_iids[sel_row])
        except Exception: pass
    def _mini_row(self):
        try:
            sel = self._mini_list.selection()
            return self._mini_iids.index(sel[0]) if sel and sel[0] in self._mini_iids else -1
        except Exception: return -1
    def show_mini(self, text=None):
        """迷你窗口 (原版 MiniForm): 独立小窗, 里面是完整记录列表 + 锁定/删除/删除全部/上移/下移按钮;
        双击某行 = 从该行开始顺序粘贴。MiniFormSet=1 常显, 否则操作后显示 MiniFormTime 秒"""
        always = self.cfg.get("Config", "MiniFormSet", fallback="0") == "1"
        secs = self.cfg.getint("Config", "MiniFormTime", fallback=5)
        if not always and secs <= 0: return
        try:
            if self._mini_win is None or not self._mini_win.winfo_exists():
                w = tk.Toplevel(self); w.title("迷你窗口"); w.attributes("-topmost", True)
                w.geometry(f"300x360+{max(0, w.winfo_screenwidth() - 330)}+80")
                w.protocol("WM_DELETE_WINDOW", self._hide_mini)
                frame = ttk.Frame(w); frame.pack(fill="both", expand=True, padx=4, pady=4)
                self._mini_list = ttk.Treeview(frame, columns=("no", "text"), show="headings", selectmode="browse", height=12)
                self._mini_list.heading("no", text=self.t("col_no", "序号")); self._mini_list.heading("text", text=self.t("col_text", "文本内容"))
                self._mini_list.column("no", width=44, anchor="center", stretch=False); self._mini_list.column("text", anchor="w")
                self._mini_iids = []
                sb = ttk.Scrollbar(frame, orient="vertical", command=self._mini_list.yview)
                self._mini_list.config(yscrollcommand=sb.set)
                self._mini_list.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
                bar = ttk.Frame(w); bar.pack(fill="x", padx=4, pady=(0, 4))
                def mini_lock():
                    i = self._mini_row()
                    if i >= 0: self.records[i]["locked"] = not self.records[i]["locked"]; self.save_records(); self.refresh_list()
                def mini_del():
                    i = self._mini_row()
                    if i >= 0 and not self.records[i]["locked"]:
                        del self.records[i]
                        if i < self.paste_index: self.paste_index -= 1
                        self.save_records(); self.refresh_list()
                def mini_move(d):
                    i = self._mini_row(); j = i + d
                    if 0 <= i < len(self.records) and 0 <= j < len(self.records):
                        self.records[i], self.records[j] = self.records[j], self.records[i]
                        self.save_records(); self.refresh_list()
                        # selection_set 是叠加的: 先清掉 _refresh_mini 恢复的旧选中, 否则会同时选中两行, 下次操作删错条
                        self._mini_list.selection_remove(*self._mini_list.selection())
                        self._mini_list.selection_set(self._mini_iids[j])
                def mini_goto(_e=None):
                    i = self._mini_row()
                    if i >= 0: self.paste_index = i; self.refresh_list()
                ttk.Button(bar, text="锁定", width=5, command=mini_lock).pack(side="left", padx=1)
                ttk.Button(bar, text="删除", width=5, command=mini_del).pack(side="left", padx=1)
                ttk.Button(bar, text="删全部", width=6, command=self.delete_all).pack(side="left", padx=1)
                ttk.Button(bar, text="↑", width=3, command=lambda: mini_move(-1)).pack(side="left", padx=1)
                ttk.Button(bar, text="↓", width=3, command=lambda: mini_move(1)).pack(side="left", padx=1)
                self._mini_list.bind("<Double-Button-1>", mini_goto)
                self._mini_win = w
            self._refresh_mini()
            w = self._mini_win; w.deiconify(); w.lift()
            if self._mini_after: self.after_cancel(self._mini_after); self._mini_after = None
            if not always: self._mini_after = self.after(secs * 1000, self._hide_mini)
        except Exception: pass
    def _hide_mini(self):
        self._mini_after = None
        try:
            if self._mini_win is not None: self._mini_win.withdraw()
        except Exception: pass
    def _switch_language(self, _e=None):
        new = self.lang_var.get().strip()
        if new == self.lang: return
        if not self.cfg.has_section("Config"): self.cfg.add_section("Config")
        self.cfg.set("Config", "Language", new); self.save_config()
        messagebox.showinfo(self.t("lang_label", "语言:"), self.t("lang_applied", "语言设置已保存, 重启软件后生效"))

    # ---------- records ----------
    def refresh_list(self):
        q = self.search_var.get().strip()
        self.listbox.delete(*self.listbox.get_children()); self._visible = []; self._row_iids = []
        for i, r in enumerate(self.records):
            if q and q not in r["text"]: continue
            self._visible.append(i)
            prefix = "🔒 " if r["locked"] else ""
            self._row_iids.append(self.listbox.insert("", "end", values=(i + 1, f"{prefix}{r['text'][:120]}")))
        self.status.set(f"{self.t('status_total', '当前记录总数')}: {len(self.records)}  |  {self.t('status_progress', '粘贴进度')}: {self.paste_index}/{len(self.records)}")
        self._refresh_mini()
    def load_records(self):
        if os.path.exists(RECORDS_PATH):
            try: self.records = json.loads(open(RECORDS_PATH, encoding="utf-8").read())
            except Exception: self.records = []
    def save_records(self):
        with open(RECORDS_PATH, "w", encoding="utf-8") as f: json.dump(self.records, f, ensure_ascii=False, indent=1)
    def add_record(self, text, dedupe=True):
        text = text.strip("\r\n")
        if not text: return
        if self.case_var.get() in ("转大写", "UPPERCASE"): text = text.upper()
        if self.case_var.get() in ("转小写", "lowercase"): text = text.lower()
        if dedupe and any(r["text"] == text for r in self.records): return
        self.records.append({"text": text, "locked": False})
        while len(self.records) > MAX_RECORDS:  # 上限保护: 丢最旧的未锁定记录 (刚加的和锁定的不动)
            idx = next((i for i, r in enumerate(self.records[:-1]) if not r["locked"]), None)
            if idx is None: break
            del self.records[idx]
        self.save_records()
    def selected_idx(self):
        """列表选中的是第几条 records (经搜索过滤映射); 没选返回 -1"""
        s = self.listbox.selection()
        if not s or s[0] not in self._row_iids: return -1
        return self._visible[self._row_iids.index(s[0])]
    def toggle_lock(self):
        i = self.selected_idx()
        if i >= 0: self.records[i]["locked"] = not self.records[i]["locked"]; self.save_records(); self.refresh_list()
    def delete_sel(self):
        i = self.selected_idx()
        if i >= 0 and not self.records[i]["locked"]:
            del self.records[i]
            if i < self.paste_index: self.paste_index -= 1  # 删了已粘过的, 进度跟着退一格, 不跳条
            self.save_records(); self.refresh_list()
        elif i >= 0: messagebox.showinfo("提示", "该记录已锁定, 先解锁再删除")
    def delete_all(self):
        removable = [r for r in self.records if not r["locked"]]
        if removable and not messagebox.askyesno("删除全部", f"确定删除全部 {len(removable)} 条未锁定记录？锁定的会保留。"):
            return
        self.records = [r for r in self.records if r["locked"]]; self.paste_index = 0; self.save_records(); self.refresh_list()
    def move(self, d):
        i = self.selected_idx(); j = i + d
        if 0 <= i < len(self.records) and 0 <= j < len(self.records):
            self.records[i], self.records[j] = self.records[j], self.records[i]; self.save_records(); self.refresh_list()
            if j in self._visible: self.listbox.selection_set(self._row_iids[self._visible.index(j)])
    def dedupe(self):
        seen, out = set(), []
        for r in self.records:
            if r["text"] not in seen: seen.add(r["text"]); out.append(r)
        self.records = out; self.save_records(); self.refresh_list()

    # ---------- clipboard ----------
    def clip_get(self):
        try: return self.clipboard_get()
        except tk.TclError: return ""
    @staticmethod
    def _win32_set_clipboard_text(text):
        """用 Win32 API 直接写剪贴板 (CF_UNICODETEXT, 立即提供数据)。
        Tk 的剪贴板是延迟渲染, WPS 等软件粘贴时可能取到空; 原版 (原生程序) 用的就是这条路。"""
        if sys.platform != "win32": return False
        try:
            u, k = ctypes.windll.user32, ctypes.windll.kernel32
            k.GlobalAlloc.restype = ctypes.c_void_p; k.GlobalLock.restype = ctypes.c_void_p
            k.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]  # 尺寸是 SIZE_T (64 位): 不声明会被按 32 位传, 高位带垃圾可能分配失败
            k.GlobalFree.argtypes = [ctypes.c_void_p]
            u.OpenClipboard.argtypes = [ctypes.c_void_p]
            u.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]; u.SetClipboardData.restype = ctypes.c_void_p
            data = (text + "\0").encode("utf-16-le")
            h = k.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
            if not h: return False
            ptr = k.GlobalLock(h); ctypes.memmove(ptr, data, len(data)); k.GlobalUnlock(h)
            opened = False
            for _ in range(5):  # 剪贴板可能被别的程序短暂占用, 重试几次
                if u.OpenClipboard(None): opened = True; break
                time.sleep(0.02)
            if not opened: k.GlobalFree(ctypes.c_void_p(h)); return False
            try:
                u.EmptyClipboard()
                if not u.SetClipboardData(13, h):  # CF_UNICODETEXT; 成功后内存归系统, 不能再 Free
                    k.GlobalFree(ctypes.c_void_p(h)); return False
                return True
            finally: u.CloseClipboard()
        except Exception: return False
    def clip_set(self, text):
        if self._win32_set_clipboard_text(text): return
        self.clipboard_clear(); self.clipboard_append(text); self.update()
    def separator(self):
        if self.custom_sep.get(): return self.custom_sep.get()
        return {"enter": "\n", "tab": "\t", "none": ""}[self.sep_var.get()]
    # ---------- v1.3.3 真机修复: F6/F7/F8 要真的替用户按 Ctrl+C / Ctrl+V ----------
    # 旧实现只读现成剪贴板: 在别的软件里选好文字按 F6, 剪贴板没变 -> 入队空/旧内容 -> 等于没反应。
    def _foreground_is_self(self):
        if sys.platform != "win32": return True
        try:
            fg = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            return pid.value == os.getpid()
        except Exception: return False
    @staticmethod
    def _foreground_process_name():
        """前台窗口所属进程名 (小写, 如 et.exe); 取不到返回 ''"""
        if sys.platform != "win32": return ""
        try:
            u = ctypes.windll.user32; k = ctypes.windll.kernel32
            fg = u.GetForegroundWindow(); pid = ctypes.c_ulong()
            u.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            h = k.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h: return ""
            try:
                buf = ctypes.create_unicode_buffer(1024); size = ctypes.c_ulong(1024)
                if not k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)): return ""
                return buf.value.rsplit("\\", 1)[-1].lower()
            finally: k.CloseHandle(h)
        except Exception: return ""
    @staticmethod
    def _scan(vk):
        """虚拟键码 -> 硬件扫描码。WPS 等软件会忽略没有扫描码的模拟按键 (原版原生程序带扫描码, 所以能用)"""
        try: return ctypes.windll.user32.MapVirtualKeyW(vk, 0)
        except Exception: return 0
    def _send_combo(self, vk_key):
        """向当前前台窗口发送 Ctrl+<vk_key> (0x43=复制 / 0x56=粘贴); SendInput -> keybd_event -> keyboard 三层兜底"""
        if sys.platform == "win32":
            VK_CONTROL, KEYUP = 0x11, 0x0002
            try:
                def ev(vk, up=False):
                    i = _INPUT(); i.type = 1; i.u.ki.wVk = vk; i.u.ki.wScan = self._scan(vk)
                    i.u.ki.dwFlags = KEYUP if up else 0; return i
                seq = (_INPUT * 4)(ev(VK_CONTROL), ev(vk_key), ev(vk_key, True), ev(VK_CONTROL, True))
                if ctypes.windll.user32.SendInput(4, seq, ctypes.sizeof(_INPUT)) == 4: return True
            except Exception: pass
            try:
                u = ctypes.windll.user32
                u.keybd_event(VK_CONTROL, self._scan(VK_CONTROL), 0, 0); u.keybd_event(vk_key, self._scan(vk_key), 0, 0)
                u.keybd_event(vk_key, self._scan(vk_key), KEYUP, 0); u.keybd_event(VK_CONTROL, self._scan(VK_CONTROL), KEYUP, 0)
                return True
            except Exception: pass
        try:
            import keyboard
            combo = {0x41: "ctrl+a", 0x58: "ctrl+x", 0x43: "ctrl+c", 0x56: "ctrl+v"}.get(vk_key)
            if combo: keyboard.send(combo); return True
        except Exception: pass
        return False
    def _clip_sequence(self):
        if sys.platform == "win32":
            try: return ctypes.windll.user32.GetClipboardSequenceNumber()
            except Exception: pass
        return None
    def multi_cut(self): self.multi_copy(cut=True)  # 多次剪切: 与多次复制成对 (原版 HotKey7)
    def multi_copy(self, cut=False):
        before_seq, before_text = self._clip_sequence(), None
        if not self._foreground_is_self():
            before_text = self.clip_get()
            self._send_combo(0x58 if cut else 0x43)  # 替用户在当前软件里按 Ctrl+X / Ctrl+C
            deadline = time.time() + max(0.3, self.sleep_ms / 1000 * 6)  # 等剪贴板真的变了再读, 最多约 0.5 秒
            while time.time() < deadline:
                seq = self._clip_sequence()
                if seq is not None and before_seq is not None:
                    if seq != before_seq: break
                elif self.clip_get() != before_text: break
                time.sleep(0.03)
        n = len(self.records)
        text = self.clip_get()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) > 1:
            for ln in lines: self.add_record(ln)  # v1.3.4: WPS 表格/列表整块复制时按行自动拆成多条, F7 才能一条条粘
        else:
            self.add_record(text)
        if len(self.records) > n:
            self.beep()  # 真入队了才响, 没选中文字时不假响
            self.show_mini(f"{self.t('mini_total', '共')} {len(self.records)} {self.t('mini_records', '条')} · {self.t('mini_next', '下一条')}: {self.records[self.paste_index]['text'][:26] if self.records else ''}")
        self.refresh_list()
    def _send_enter(self):
        """向当前前台窗口发送一次回车 (确认/提交); SendInput -> keybd_event -> keyboard 三层兜底"""
        if sys.platform == "win32":
            try:
                def ev(up=False):
                    i = _INPUT(); i.type = 1; i.u.ki.wVk = 0x0D; i.u.ki.wScan = self._scan(0x0D)
                    i.u.ki.dwFlags = 0x0002 if up else 0; return i
                seq = (_INPUT * 2)(ev(), ev(True))
                if ctypes.windll.user32.SendInput(2, seq, ctypes.sizeof(_INPUT)) == 2: return True
            except Exception: pass
            try:
                u = ctypes.windll.user32
                u.keybd_event(0x0D, self._scan(0x0D), 0, 0); u.keybd_event(0x0D, self._scan(0x0D), 0x0002, 0); return True
            except Exception: pass
        try:
            import keyboard; keyboard.send("enter"); return True
        except Exception: return False
    # WPS Office 的进程: 它的表格对模拟 Ctrl+V 不买账 (v1.4.0 真机验证: 热键/剪贴板/迷你窗都正常, 就是不落字),
    # 对这类目标改走逐字打字 (与强力粘贴同路, 不依赖剪贴板和粘贴命令, 单元格里打字即输入)
    _WPS_PROCS = ("et.exe", "wps.exe", "wpp.exe")
    def _paste_text(self, text, enter=False):
        self.clip_set(text)
        if not self._foreground_is_self():
            time.sleep(0.03)
            if self._foreground_process_name() in self._WPS_PROCS:
                self._type_text(text)  # WPS: 逐字打进目标窗口
            else:
                self._send_combo(0x56)  # Ctrl+V: 真的粘进目标窗口, 不只是放剪贴板
            if enter:  # 粘完稍等目标程序处理完再回车确认 (太快回车会赶在粘贴落地之前)
                time.sleep(0.15); self._send_enter()
        self.beep()
    def paste_next(self):
        if not self.records: return
        if self.paste_index >= len(self.records): self.paste_index = 0
        rec = self.records[self.paste_index]
        self._paste_text(rec["text"], enter=self.paste_enter_var.get())
        if self.paste_remove_var.get() and not rec["locked"]:
            # 粘完即删 (消费模式): 删掉刚粘的这条, 下一条自动顶到当前位置, 序号不用前进
            del self.records[self.paste_index]
            if self.paste_index >= len(self.records): self.paste_index = 0
            self.save_records()
        else:
            self.paste_index += 1
        self.refresh_list(); self.show_mini()
    def paste_all(self):
        if not self.records: return
        self._paste_text(self.separator().join(r["text"] for r in self.records)); self.show_mini()
    def paste_selected(self):
        i = self.selected_idx()
        if i >= 0:
            time.sleep(self.sleep_ms / 1000); self.clip_set(self.records[i]["text"]); self.beep()
            if not self._foreground_is_self(): self._type_text(self.records[i]["text"])  # 强力粘贴: 逐字打进目标窗口
    # ---------- 原版基础热键组 (HotKey1-5) 与强力粘贴 ----------
    def act_select_all(self):
        if not self._foreground_is_self(): self._send_combo(0x41)  # Ctrl+A
    def act_cut(self):
        if not self._foreground_is_self(): self._send_combo(0x58)  # Ctrl+X
    def act_copy(self):
        if not self._foreground_is_self(): self._send_combo(0x43)  # Ctrl+C
    def act_paste(self):
        if not self._foreground_is_self(): self._send_combo(0x56)  # Ctrl+V
    def act_power_paste(self):
        text = self.clip_get()
        if text and not self._foreground_is_self(): self._type_text(text)
    def _type_text(self, text):
        """逐字输入 (强力粘贴): 对付屏蔽 Ctrl+V 的窗口; Win32 用 SendInput Unicode, 其余兜底 keyboard.write"""
        if sys.platform == "win32":
            try:
                u = ctypes.windll.user32
                def ev(scan, vk=0, up=False, unicode_=False):
                    i = _INPUT(); i.type = 1; i.u.ki.wVk = vk; i.u.ki.wScan = scan
                    i.u.ki.dwFlags = (0x0004 if unicode_ else 0) | (0x0002 if up else 0); return i
                batch = []
                for ch in text:
                    if ch == "\r": continue
                    if ch == "\n": batch += [ev(0, 0x0D), ev(0, 0x0D, up=True)]
                    elif ch == "\t": batch += [ev(0, 0x09), ev(0, 0x09, up=True)]
                    else: batch += [ev(ord(ch), unicode_=True), ev(ord(ch), up=True, unicode_=True)]
                for j in range(0, len(batch), 200):  # 分批发送, 防超长文本一次塞爆
                    chunk = (_INPUT * len(batch[j:j+200]))(*batch[j:j+200])
                    u.SendInput(len(batch[j:j+200]), chunk, ctypes.sizeof(_INPUT))
                return True
            except Exception: pass
        try:
            import keyboard; keyboard.write(text); return True
        except Exception: return False
    def import_clipboard_split(self):
        text = self.clip_get()
        if not text: return
        pattern = {"所有数字": r"\d+", "所有小写字母": r"[a-z]+", "所有大写字母": r"[A-Z]+",
                   "All Numbers": r"\d+", "All lowercase letters": r"[a-z]+", "All UPPERCASE letters": r"[A-Z]+",
                   "回车符": None, "制表符": None, "Enter (newline)": None, "Tab": None}.get(self.regex_var.get(), None)
        sep_used = None
        if self.regex_var.get() in ("回车符", "Enter (newline)"): parts = text.splitlines()
        elif self.regex_var.get() in ("制表符", "Tab"): parts = text.split("\t"); sep_used = "\t"
        elif pattern: parts = re.findall(pattern, text)
        elif self.split_entry.get(): sep_used = self.split_entry.get(); parts = text.split(sep_used)
        else: parts = [text]
        # 分隔符保存位置 (原版「分割字符串前/后」): 留在前段末尾或后段开头, 只对字面分隔符生效
        if sep_used and len(parts) > 1:
            pos = self.splitpos_var.get()
            if pos in ("分隔符留在前段", "Separator stays with previous"): parts = [p + sep_used for p in parts[:-1]] + parts[-1:]
            elif pos in ("分隔符留在后段", "Separator stays with next"): parts = parts[:1] + [sep_used + p for p in parts[1:]]
        for p in parts: self.add_record(p)
        self.refresh_list()
    def beep(self):
        # WaveSet 在 Config.ini 里是 [Wave] 段的键 (旧版误读 [Config] 段, 改了也不生效)
        wave_on = self.cfg.get("Wave", "WaveSet", fallback=self.cfg.get("Config", "WaveSet", fallback="0"))
        if wave_on == "1" and sys.platform == "win32":
            try:
                import winsound; winsound.PlaySound(os.path.join(BASE, "ding.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception: pass

    # ---------- import/export/config ----------
    def import_txt(self):
        p = filedialog.askopenfilename(filetypes=[("文本/INI", "*.txt *.ini"), ("全部", "*.*")])
        if p:
            raw = open(p, "rb").read(); lines = []
            for enc in ("utf-8-sig", "gbk"):
                try: lines = raw.decode(enc).splitlines(); break
                except Exception: lines = []
            for ln in lines: self.add_record(ln)
            self.refresh_list()
    def export_txt(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("文本", "*.txt")])
        if p: open(p, "w", encoding="utf-8").write(self.separator().join(r["text"] for r in self.records))
    def delete_last(self):
        for i in range(len(self.records) - 1, -1, -1):
            if not self.records[i]["locked"]:
                del self.records[i]
                if i < self.paste_index: self.paste_index -= 1
                break
        self.save_records(); self.refresh_list()

    # ---------- 自定义热键 ----------
    # Config.ini [HotKey] 字段 -> (显示名, 动作). 用户在「热键设置」里改; 也可直接改 ini, 重启后生效。
    def hotkey_actions(self):
        # (section, key, 显示名, 动作)
        return [("HotKey", "HotKey1", self.t("hk_select_all", "全选"), self.act_select_all),
                ("HotKey", "HotKey2", self.t("hk_cut", "剪切"), self.act_cut),
                ("HotKey", "HotKey3", self.t("hk_copy", "复制"), self.act_copy),
                ("HotKey", "HotKey4", self.t("hk_paste", "粘贴"), self.act_paste),
                ("HotKey", "HotKey5", self.t("hk_power_paste", "强力粘贴"), self.act_power_paste),
                ("HotKey", "HotKey7", self.t("hk_multi_cut", "多次剪切"), self.multi_cut),
                ("HotKey", "HotKey8", self.t("hk_multi_copy", "多次复制"), self.multi_copy), ("HotKey", "HotKey9", self.t("hk_paste_next", "顺序粘贴"), self.paste_next),
                ("HotKey", "HotKey10", self.t("hk_paste_all", "全部粘贴"), self.paste_all), ("HotKey", "HotKey11", self.t("hk_delete_last", "删除最后一条"), self.delete_last),
                ("HotKey", "HotKey12", self.t("hk_delete_all", "删除全部记录"), self.delete_all),
                ("Snip", "SnipKey", self.t("hk_snip", "区域截图"), self.snip_region), ("Snip", "PinKey", self.t("hk_pin", "贴剪贴板"), self.pin_clipboard),
                ("Snip", "CopyKey", self.t("hk_snip_copy", "截图并复制"), self.snip_copy), ("Snip", "TransKey", self.t("hk_snip_trans", "截图翻译"), self.snip_translate),
                ("Snip", "DelayKey", self.t("hk_snip_delay", "延时截图"), self.snip_delayed),
                ("Snip", "ClosePinsKey", self.t("hk_close_pins", "关闭所有贴图"), self.close_all_pins), ("Snip", "TogglePinsKey", self.t("hk_toggle_pins", "隐藏/显示所有贴图"), self.toggle_pins_visible),
                ("Snip", "RestorePinKey", self.t("hk_restore_pin", "恢复上次关闭的贴图"), self.restore_last_pin), ("Snip", "ClickThroughKey", self.t("hk_click_through", "贴图鼠标穿透开关"), self.toggle_pins_clickthrough)]
    @staticmethod
    def normalize_hotkey(raw):
        """'无'/空 -> None; 其余统一成 keyboard 包格式, 如 'ctrl+alt+v' / 'f6'"""
        if not raw: return None
        s = raw.strip().lower().replace(" ", "").replace("＋", "+")
        if s in ("无", "none", "no", "-"): return None
        s = s.replace("control", "ctrl").replace("windows", "win").replace("window", "win")
        return s or None
    @staticmethod
    def tk_sequence(hk):
        """把 'ctrl+alt+v'/'f6' 转成 Tk 绑定序列; 转不了的返回 None (仍可走全局热键)"""
        if not hk: return None
        parts = hk.split("+"); key, mods = parts[-1], parts[:-1]
        mod_map = {"ctrl": "Control", "alt": "Alt", "shift": "Shift"}
        if any(m not in mod_map for m in mods): return None
        key_tk = key.upper() if re.fullmatch(r"f\d{1,2}", key) else (key.upper() if len(key) == 1 else key.capitalize())
        prefix = "-".join(mod_map[m] for m in mods)
        return f"<{prefix + '-' if prefix else ''}{key_tk}>"
    def apply_hotkeys(self):
        # 注销旧的全局热键和窗口绑定
        try:
            import keyboard
            for h in self._hk_handles:
                try: keyboard.remove_hotkey(h)
                except Exception: pass
            if self._oc_handle is not None:
                try: keyboard.remove_hotkey(self._oc_handle)
                except Exception: pass
                self._oc_handle = None
        except Exception: keyboard = None
        self._hk_handles = []
        for seq in self._tk_sequences:
            try: self.unbind(seq)
            except Exception: pass
        self._tk_sequences = []
        # 按当前配置重新注册
        labels, global_ok = [], False
        for section, cfg_key, label, fn in self.hotkey_actions():
            hk = self.normalize_hotkey(self.cfg.get(section, cfg_key, fallback="无"))
            if not hk: continue
            labels.append(f"{hk.upper()} {label}")
            seq = self.tk_sequence(hk)
            if seq:
                self.bind(seq, lambda e, f=fn: f()); self._tk_sequences.append(seq)
            if keyboard is not None:
                # keyboard 在它自己的线程里回调, 直接操作 Tk 会随机崩溃: 只入队, 主线程轮询执行
                # suppress=True: 按键被我们"吃掉", 不再传给前台软件 —— 否则像 F7 在 WPS 表格里会同时触发
                # WPS 自己的拼写检查, 弹窗抢走焦点, 粘贴就落空 (原版用系统热键注册, 本来就是吃掉的)
                try: self._hk_handles.append(keyboard.add_hotkey(hk, lambda f=fn: self._ui_queue.put(f), suppress=True)); global_ok = True
                except Exception:
                    try: self._hk_handles.append(keyboard.add_hotkey(hk, lambda f=fn: self._ui_queue.put(f))); global_ok = True
                    except Exception: pass
        scope = "全局热键" if global_ok else "窗口内热键 (装 keyboard 包后可全局)"
        self.status.set(f"{scope}已启用: " + (" / ".join(labels) if labels else "未设置, 点「热键设置」添加"))
        # 全局切换热键 (原版 [OCHotKey]): 单独注册, 不归 toggle 管, 这样关掉后还能按它恢复
        self._oc_handle = None
        oc = self.normalize_hotkey(self.cfg.get("OCHotKey", "HotKey", fallback="无"))
        if oc and keyboard is not None:
            try: self._oc_handle = keyboard.add_hotkey(oc, lambda: self._ui_queue.put(self.toggle_hotkeys), suppress=True)
            except Exception:
                try: self._oc_handle = keyboard.add_hotkey(oc, lambda: self._ui_queue.put(self.toggle_hotkeys))
                except Exception: pass
        self._hk_enabled = True
    def toggle_hotkeys(self):
        """全局切换: 一键停用/恢复全部动作热键 (切换键本身始终有效)"""
        try: import keyboard
        except Exception: keyboard = None
        if self._hk_enabled:
            if keyboard is not None:
                for h in self._hk_handles:
                    try: keyboard.remove_hotkey(h)
                    except Exception: pass
            self._hk_handles = []; self._hk_enabled = False
            self.status.set(self.t("hk_off", "全局热键已关闭 (按全局切换热键恢复)"))
        else:
            self.apply_hotkeys()
            self.status.set(self.t("hk_on", "全局热键已开启"))
    def open_hotkey_dialog(self):
        win = tk.Toplevel(self); win.title(self.t("hotkey_settings", "热键设置")); win.geometry("460x640"); win.transient(self); win.grab_set()
        ttk.Label(win, text="点「录入」后直接按下组合键, 或手动输入。任何按键都可以设, 包括 F1、F2、Ctrl+C 这类常用键, 按你的习惯来。\n留空或填「无」= 不启用该热键。同一个键设给两个功能时, 会提示你确认, 后设的生效、先设的自动清空。").pack(padx=10, pady=8, anchor="w")
        # 动作已有 20 行: 列表区做成可滚动, 保证底部的「应用」按钮在任何屏幕上都够得到 (旧版固定高度会把最后几行挤出窗口)
        wrap = ttk.Frame(win); wrap.pack(fill="both", expand=True, padx=4)
        cv = tk.Canvas(wrap, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        inner = ttk.Frame(cv)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        win_id = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win_id, width=e.width))
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(int(-e.delta / 120), "units"))
        win.bind("<Destroy>", lambda e: cv.unbind_all("<MouseWheel>") if e.widget is win else None)
        vars_ = {}
        for section, cfg_key, label, _fn in self.hotkey_actions() + [("OCHotKey", "HotKey", self.t("hk_toggle", "全局切换热键"), None)]:
            row = ttk.Frame(inner); row.pack(fill="x", padx=10, pady=3)
            ttk.Label(row, text=label, width=14).pack(side="left")
            var = tk.StringVar(value=self.cfg.get(section, cfg_key, fallback="无")); vars_[(section, cfg_key)] = var
            entry = ttk.Entry(row, textvariable=var, width=20); entry.pack(side="left")
            def capture(var=var, entry=entry):
                entry.focus_set(); var.set("请按键…")
                def on_key(e):
                    mods = []
                    if e.state & 0x4: mods.append("ctrl")
                    if e.state & 0x20000 or e.state & 0x8: mods.append("alt")
                    if e.state & 0x1: mods.append("shift")
                    key = e.keysym.lower()
                    if key in ("control_l", "control_r", "alt_l", "alt_r", "shift_l", "shift_r"): return "break"
                    var.set("+".join(mods + [key])); entry.unbind("<KeyPress>"); return "break"
                entry.bind("<KeyPress>", on_key)
            ttk.Button(row, text="录入", command=capture).pack(side="left", padx=4)
            ttk.Button(row, text="清除", command=lambda v=var: v.set("无")).pack(side="left")
        def save():
            # 不避开任何热键: 重复不再直接拦下, 而是问一句 —— 确认后后设的生效, 先设的自动清空
            entries = [(key, var, self.normalize_hotkey(var.get())) for key, var in vars_.items()]
            by_hk = {}
            for key, var, hk in entries:
                if hk: by_hk.setdefault(hk, []).append(key)
            conflicts = {hk: keys for hk, keys in by_hk.items() if len(keys) > 1}
            if conflicts:
                label_of = {(s, c): l for s, c, l, _f in self.hotkey_actions() + [("OCHotKey", "HotKey", self.t("hk_toggle", "全局切换热键"), None)]}
                detail = "\n".join(f"{hk.upper()}: " + "、".join(label_of.get(k, k[1]) for k in keys) for hk, keys in conflicts.items())
                if not messagebox.askyesno("热键设置", f"下面这些键被设给了多个功能:\n{detail}\n\n点「是」: 后设的生效, 先设的自动清空; 点「否」: 回去改。", parent=win):
                    return
                for hk, keys in conflicts.items():
                    for k in keys[:-1]: vars_[k].set("无")
                entries = [(key, var, self.normalize_hotkey(var.get())) for key, var in vars_.items()]
            for (section, cfg_key), var, hk in entries:
                if not self.cfg.has_section(section): self.cfg.add_section(section)
                self.cfg.set(section, cfg_key, hk.upper() if hk else "无")
            self.save_config(); self.apply_hotkeys(); win.destroy()
            messagebox.showinfo("热键设置", "已保存并立即生效, 不用重启。")
        btns = ttk.Frame(win); btns.pack(pady=10)
        ttk.Button(btns, text="应用", command=save).pack(side="left", padx=6)
        def restore():
            for k, v in DEFAULT_HOTKEYS.items(): vars_[("HotKey", k)].set(v)
            for k, v in DEFAULT_SNIP_KEYS.items(): vars_[("Snip", k)].set(v)
        ttk.Button(btns, text="恢复预设", command=restore).pack(side="left", padx=6)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=6)
    # ---------- 截图 / 贴图 (Snipaste 核心) ----------
    @property
    def shots_dir(self):
        d = os.path.join(BASE, "shots"); os.makedirs(d, exist_ok=True); return d
    def refresh_shots(self):
        if not hasattr(self, "shots_list"): return
        self.shots_list.delete(0, "end")
        for f in sorted(os.listdir(self.shots_dir), reverse=True):
            if f.lower().endswith(".png"): self.shots_list.insert("end", f)
    def save_shot(self, img):
        now = datetime.datetime.now()  # 带毫秒: 旧版只到秒, 1 秒内连截两张会同名互相覆盖
        name = now.strftime("shot_%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}.png"
        path = os.path.join(self.shots_dir, name); img.save(path)
        try:  # 历史截图只保留最近 HistoryMax 张 (默认 100, 对齐 Snipaste 设置), 防文件夹无限膨胀
            keep = int(self.cfg.get("Snip", "HistoryMax", fallback="100"))
            files = sorted((os.path.join(self.shots_dir, f) for f in os.listdir(self.shots_dir)
                            if f.startswith("shot_") and f.endswith(".png")), key=os.path.getmtime)
            for p in files[:max(0, len(files) - keep)]:
                try: os.remove(p)
                except OSError: pass
        except Exception: pass
        self.refresh_shots(); return path
    def open_shots_dir(self):
        if sys.platform == "win32": os.startfile(self.shots_dir)  # noqa: S606
        else: messagebox.showinfo("截图文件夹", self.shots_dir)
    # ---------- 长截图 (滚动拼接) 与 GIF 录制 (参考 PixPin) ----------
    @staticmethod
    def _stitch_frames(frames):
        """把等宽的滚动帧纵向拼成长图: 以相邻帧的行签名找最大重叠 (容忍少量行误差, 吸收抗锯齿差异),
        只追加新露出的部分; 滚到底的重复帧被完全吸收。纯逻辑, 可单测。"""
        if not frames: return None
        def row_sigs(img):
            small = img.convert("L").resize((24, img.height)); px = small.load()
            return [tuple(px[x, y] for x in range(24)) for y in range(img.height)]
        def rows_close(a, b): return all(abs(p - q) <= 10 for p, q in zip(a, b))
        acc = frames[0].convert("RGB"); prev = acc; prev_sigs = row_sigs(prev)
        for fr in frames[1:]:
            fr = fr.convert("RGB")
            if fr.width != acc.width: fr = fr.resize((acc.width, fr.height))
            h = fr.height; sigs = row_sigs(fr); best = 0
            anchor = prev_sigs[-1]  # 上一帧的底行应在本帧中出现的位置 -> 候选重叠量, 逐个验证
            cands = [j + 1 for j in range(h - 1, -1, -1) if rows_close(sigs[j], anchor)]
            for k in cands:
                if k > prev.height: continue
                off = prev.height - k
                bad = sum(1 for i in range(k) if not rows_close(prev_sigs[off + i], sigs[i]))
                if bad <= max(2, k // 40): best = k; break
            if best < h:
                add = fr.crop((0, best, fr.width, h))
                new = Image.new("RGB", (acc.width, acc.height + add.height))
                new.paste(acc, (0, 0)); new.paste(add, (0, acc.height)); acc = new
            prev = fr; prev_sigs = sigs
        return acc
    def _run_long_capture(self, box):
        """长截图执行 (覆盖层已关闭): 鼠标停在选区中心自动向下滚动, 逐帧抓取拼接; Esc 中止, 画面不再变化自动结束, 完成后打开标注编辑器。"""
        if sys.platform != "win32":
            self.deiconify(); self.status.set("长截图目前仅支持 Windows"); return
        u = ctypes.windll.user32
        u.mouse_event.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
        x1, y1, x2, y2 = box
        u.SetCursorPos((x1 + x2) // 2, (y1 + y2) // 2); time.sleep(0.2)
        frames, last_sig, still = [], None, 0
        for _ in range(30):
            if u.GetAsyncKeyState(0x1B) & 0x8000: break  # Esc 中止
            fr = ImageGrab.grab(bbox=(x1, y1, x2, y2)); frames.append(fr)
            sig = fr.resize((8, 8)).tobytes()
            if sig == last_sig:
                still += 1
                if still >= 2: break  # 连续两帧没变化 = 滚到底了
            else: still = 0
            last_sig = sig
            u.mouse_event(0x0800, 0, 0, (-600) & 0xFFFFFFFF, None)  # MOUSEEVENTF_WHEEL 向下滚一格
            time.sleep(0.35)
        self.deiconify()
        if not frames: return
        img = self._stitch_frames(frames)
        if img is None: return
        self.save_shot(img); self.status.set(f"长截图完成: {img.width}×{img.height}, 已打开编辑器 (可标注/复制/钉图)")
        self.open_editor(img)
    def _run_gif_record(self, box, max_seconds=30, fps=8):
        """录制选区为 GIF 动图: 非阻塞逐帧抓取, 屏幕角落有小控制窗 (计时+停止), 结束自动存进截图文件夹。"""
        if not HAS_PIL: return
        rec = {"stop": False, "frames": [], "t0": time.time()}
        ctrl = tk.Toplevel(self); ctrl.overrideredirect(True); ctrl.attributes("-topmost", True)
        lab = tk.Label(ctrl, text="● GIF 录制中 0s", bg="#222222", fg="#FF6666", font=("Microsoft YaHei", 10))
        lab.pack(side="left", padx=6, pady=4)
        tk.Button(ctrl, text="停止", command=lambda: rec.update(stop=True)).pack(side="left", padx=4, pady=4)
        ctrl.update_idletasks()
        ctrl.geometry(f"+{max(0, ctrl.winfo_screenwidth() - ctrl.winfo_reqwidth() - 16)}+{max(0, ctrl.winfo_screenheight() - ctrl.winfo_reqheight() - 60)}")
        def finish():
            try: ctrl.destroy()
            except Exception: pass
            self.deiconify()
            frames = rec["frames"]
            if len(frames) < 2: self.status.set("GIF 太短, 已取消"); return
            path = os.path.join(self.shots_dir, time.strftime("gif_%Y%m%d_%H%M%S.gif"))
            try:
                frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0)
                self.status.set(f"GIF 已保存: {path} ({len(frames)} 帧)")
                messagebox.showinfo("GIF 录制完成", f"已保存到:\n{path}\n共 {len(frames)} 帧", parent=self)
            except Exception as e: messagebox.showerror("GIF 保存失败", str(e), parent=self)
        def tick():
            if rec["stop"] or time.time() - rec["t0"] > max_seconds: finish(); return
            try:
                fr = ImageGrab.grab(bbox=box)
                if fr.width > 1280: fr = fr.resize((1280, max(1, int(fr.height * 1280 / fr.width))))
                rec["frames"].append(fr.convert("RGB"))
                lab.config(text=f"● GIF 录制中 {time.time() - rec['t0']:.0f}s · {len(rec['frames'])} 帧")
            except Exception: pass
            ctrl.after(int(1000 / fps), tick)
        tick()
    def _force_foreground(self, win):
        # 把覆盖层抢到前台并拿到键盘焦点: 截图是被全局热键从别的程序 (如 Chrome) 里唤起的,
        # 普通 focus_set 抢不过 Windows 的前台锁定, Esc 等按键会落到原程序身上
        # (真机反馈: 框选/检测元素阶段按 Esc 退不出截图)。用 AttachThreadInput 借前台线程的输入队列再 SetForegroundWindow。
        try: win.focus_force()
        except Exception: pass
        if sys.platform != "win32": return
        try:
            u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
            hwnd = u32.GetAncestor(win.winfo_id(), 2)  # GA_ROOT
            fg = u32.GetForegroundWindow()
            if fg and fg != hwnd:
                tid_fg = u32.GetWindowThreadProcessId(fg, None)
                tid_me = k32.GetCurrentThreadId()
                u32.AttachThreadInput(tid_me, tid_fg, True)
                u32.SetForegroundWindow(hwnd); u32.BringWindowToTop(hwnd)
                u32.AttachThreadInput(tid_me, tid_fg, False)
            else:
                u32.SetForegroundWindow(hwnd)
        except Exception: pass

    def snip_region(self):
        if not HAS_PIL:
            messagebox.showerror("缺少 Pillow", "截图功能需要 Pillow: pip install Pillow"); return
        self.withdraw(); self.update(); time.sleep(0.3)
        try:
            try: full = ImageGrab.grab(all_screens=True)  # 多显示器抓虚拟桌面 (旧 Pillow 无此参数时回退)
            except TypeError: full = ImageGrab.grab()
            full = full.convert("RGB")  # 统一 RGB: 调色板/灰度图取色和标注才不失真
        except Exception as e:
            self.deiconify(); messagebox.showerror("截图失败", str(e)); return
        try: ui_mode = int(self.cfg.get("Snip", "UIDetect", fallback="2"))  # UI 检测: 0 不检测 / 1 仅窗口 / 2 检测元素
        except Exception: ui_mode = 2
        top_windows = self._enum_top_windows() if ui_mode else []
        snap_rects = [r for _, r in top_windows]  # Windows 下枚举真实窗口; 其他系统为空, 自动退回自由框选
        hwnd_of = {r: h for h, r in top_windows}
        finish_mode = self._snip_finish_mode; self._snip_finish_mode = None  # 消费本次截图的特殊完成方式
        sel_win = tk.Toplevel(self); sel_win.attributes("-fullscreen", True); sel_win.attributes("-topmost", True)
        canvas = tk.Canvas(sel_win, cursor="crosshair", highlightthickness=0); canvas.pack(fill="both", expand=True)
        photo = ImageTk.PhotoImage(full); canvas.create_image(0, 0, anchor="nw", image=photo); canvas.image = photo
        state = {"x": 0, "y": 0, "rect": None, "snap": None, "hex": "", "phase": "select",
                 "box": None, "ops": [], "op_items": [], "undone": [], "tool": None,
                 "color": "#FF0000", "width": 3, "drag": None, "tb": None}
        def show_info(e, extra=""):
            canvas.delete("info")
            if snap_rects and not (e.state & 0x0100):  # 没按住鼠标时: 吸附高亮鼠标所在窗口 (单击即截整窗)
                snap = self.pick_window(e.x, e.y, snap_rects)
                if ui_mode == 2 and snap:  # 检测元素: 先在该窗口内找更小的子控件矩形 (悬停层, 纯 Win32)
                    key = (e.x // 4, e.y // 4, snap)
                    if state.get("child_key") != key:
                        child = self._smallest_child_rect(hwnd_of.get(snap), e.x, e.y)
                        state["child_key"] = key; state["child_rect"] = child
                    child = state.get("child_rect")
                    if child and (child[2] - child[0]) * (child[3] - child[1]) < (snap[2] - snap[0]) * (snap[3] - snap[1]): snap = child
                state["snap"] = snap
                canvas.delete("snap")
                if snap: canvas.create_rectangle(*snap, outline="#1E90FF", width=2, tags="snap")  # 识别线: 蓝色实线 (用户反馈黄色刺眼、虚线不如实线清楚, 对照 PixPin)
            try: r, g, b = full.getpixel((e.x, e.y))[:3]; state["hex"] = f"#{r:02X}{g:02X}{b:02X}"; state["rgb"] = (r, g, b)
            except Exception: state["rgb"] = None
            # 放大镜 + 信息卡 (PixPin 式): 带像素网格和蓝色十字的放大图在上, 深色信息卡贴在下方,
            # 坐标/色块/HEX/RGB/操作提示都跟着光标走 (用户对照 PixPin 反馈: 这样看起来清楚; 旧版是文字飘在屏幕左上角)
            try:
                R, Z = 12, state.get("zoom", 6)
                x0, y0 = max(0, e.x - R), max(0, e.y - R)
                x1c, y1c = min(full.width, e.x + R + 1), min(full.height, e.y + R + 1)
                zoom = full.crop((x0, y0, x1c, y1c)).resize(((x1c - x0) * Z, (y1c - y0) * Z), Image.NEAREST).convert("RGB")
                zd = ImageDraw.Draw(zoom)
                for gx in range(0, zoom.width, Z): zd.line([gx, 0, gx, zoom.height], fill=(190, 190, 190))   # 像素网格
                for gy in range(0, zoom.height, Z): zd.line([0, gy, zoom.width, gy], fill=(190, 190, 190))
                ccx, ccy = (e.x - x0) * Z, (e.y - y0) * Z  # 中心像素: 蓝色十字带 + 描边, 一眼看清当前取的是哪个像素
                zd.line([ccx + Z // 2, 0, ccx + Z // 2, zoom.height], fill=(30, 144, 255), width=2)
                zd.line([0, ccy + Z // 2, zoom.width, ccy + Z // 2], fill=(30, 144, 255), width=2)
                zd.rectangle([ccx, ccy, ccx + Z - 1, ccy + Z - 1], outline=(30, 144, 255), width=2)
                state["loupe"] = ImageTk.PhotoImage(zoom)
                PH = 58  # 信息卡高度
                pw = max(zoom.width, 216)  # 信息卡宽度: 要放得下拖动时的「选区 WxH」
                total_h = zoom.height + PH
                lx = e.x + 24 if e.x + 24 + pw < full.width else e.x - 24 - pw
                ly = e.y + 24 if e.y + 24 + total_h < full.height else e.y - 24 - total_h
                canvas.delete("loupe")
                ix = lx + (pw - zoom.width) // 2  # 放大图在卡片上方居中
                canvas.create_image(ix, ly, anchor="nw", image=state["loupe"], tags="loupe")
                canvas.create_rectangle(lx, ly, lx + pw, ly + total_h, outline="#1E90FF", width=1, tags="loupe")
                py0 = ly + zoom.height
                canvas.create_rectangle(lx, py0, lx + pw, ly + total_h, fill="#222222", outline="", tags="loupe")
                rgb = state.get("rgb")
                if rgb:
                    canvas.create_rectangle(lx + 8, py0 + 7, lx + 20, py0 + 19, fill="#%02X%02X%02X" % rgb, outline="white", tags="loupe")
                    canvas.create_text(lx + 26, py0 + 13, anchor="w", tags="loupe", fill="white", font=("Consolas", 10, "bold"),
                                       text=f"({e.x},{e.y}) {state['hex']} {extra}")
                    canvas.create_text(lx + 8, py0 + 32, anchor="w", tags="loupe", fill="white", font=("Consolas", 9),
                                       text=f"RGB({rgb[0]}, {rgb[1]}, {rgb[2]})")
                canvas.create_text(lx + 8, py0 + 49, anchor="w", tags="loupe", fill="#AAAAAA", font=("Microsoft YaHei UI", 8),
                                   text="C 复制颜色值 · +/- 调放大镜倍数")
            except Exception: pass
        def on_key(e):
            if e.keysym in ("plus", "equal", "KP_Add"): state["zoom"] = min(16, state.get("zoom", 6) + 1); return
            if e.keysym in ("minus", "KP_Subtract"): state["zoom"] = max(2, state.get("zoom", 6) - 1); return
            if e.keysym.lower() == "c" and state.get("hex") and not (e.state & 0x0004):
                self.clip_set(state["hex"])
                canvas.delete("copied")
                canvas.create_text(e.x + 14, e.y - 14, anchor="w", tags="copied", fill="#00FF88",
                                   font=("Consolas", 12, "bold"), text=f"已复制 {state['hex']}")
                sel_win.after(900, lambda: canvas.delete("copied"))
        sel_win.bind("<KeyPress>", on_key); sel_win.focus_set()
        self._force_foreground(sel_win)  # 抢键盘焦点, 保证框选阶段 Esc/+/-/C 都落在截图窗上
        def down(e): state.update(x=e.x, y=e.y); canvas.delete("snap"); show_info(e)
        def drag(e):
            if state["rect"]: canvas.delete(state["rect"])
            state["rect"] = canvas.create_rectangle(state["x"], state["y"], e.x, e.y, outline="#1E90FF", width=2)
            show_info(e, f"| 选区 {abs(e.x-state['x'])}x{abs(e.y-state['y'])}")
        canvas.bind("<Motion>", show_info)
        def up(e):
            box = (min(state["x"], e.x), min(state["y"], e.y), max(state["x"], e.x), max(state["y"], e.y))
            if box[2] - box[0] <= 5 and box[3] - box[1] <= 5 and state.get("snap"):
                box = tuple(state["snap"])
                if ui_mode == 2:  # 检测元素: 单击时用 UI Automation 把选区精修到真正的控件 (按钮/输入框等)
                    r = self._uia_rect_at(e.x, e.y)
                    if r and r[0] <= e.x <= r[2] and r[1] <= e.y <= r[3] and \
                       (r[2] - r[0]) * (r[3] - r[1]) < (box[2] - box[0]) * (box[3] - box[1]):
                        box = (max(0, r[0]), max(0, r[1]), min(full.width, r[2]), min(full.height, r[3]))
            if box[2] - box[0] > 5 and box[3] - box[1] > 5:
                if finish_mode == "copy":  # 截图并复制: 框选完直接出图进剪贴板, 不停留标注
                    final = full.crop(box); self.save_shot(final); close_overlay(); self._copy_image_to_clipboard(final)
                elif finish_mode == "translate":  # 截图翻译: 框选完直接 OCR 并翻译到目标语言, 不停留标注
                    final = full.crop(box); self.save_shot(final); close_overlay(); self.translate_image(final, self.trans_target())
                else: enter_adjust(box)
            else: close_overlay()
        canvas.bind("<ButtonPress-1>", down); canvas.bind("<B1-Motion>", drag); canvas.bind("<ButtonRelease-1>", up)
        # ---------- 第二阶段 (Snipaste 式): 选区停在冻结屏上, 就地调整 + 标注 + 工具栏 ----------
        def close_overlay():
            try:
                if state.get("tb") is not None: state["tb"].destroy()
            except Exception: pass
            try: sel_win.destroy()
            except Exception: pass
            self.deiconify()
        # 全局 Esc 兜底: 就算焦点一时没抢过来 (还停在原程序身上), 框选/调整阶段按 Esc 也能退出;
        # 覆盖层销毁时自动注销 (finish/取消/长截图/GIF 所有出口都销毁 sel_win), 不影响平时用 Esc
        state["esc_hk"] = None
        try:
            import keyboard as _kb
            state["esc_hk"] = _kb.add_hotkey("esc", lambda: self._ui_queue.put(close_overlay), suppress=True)
        except Exception: pass
        def _drop_esc_hk(e):
            if e.widget is not sel_win: return
            if state.get("esc_hk") is not None:
                try:
                    import keyboard as _kb2; _kb2.remove_hotkey(state["esc_hk"])
                except Exception: pass
                state["esc_hk"] = None
        sel_win.bind("<Destroy>", _drop_esc_hk)
        def handles_of(box):
            x1, y1, x2, y2 = box; mx, my = (x1 + x2) // 2, (y1 + y2) // 2
            return [(x1, y1), (mx, y1), (x2, y1), (x1, my), (x2, my), (x1, y2), (mx, y2), (x2, y2)]
        def draw_sel():
            canvas.delete("sel")
            x1, y1, x2, y2 = state["box"]; W, H = full.width, full.height
            for r in ((0, 0, W, y1), (0, y2, W, H), (0, y1, x1, y2), (x2, y1, W, y2)):  # 选区外压暗
                if r[2] > r[0] and r[3] > r[1]: canvas.create_rectangle(*r, fill="black", stipple="gray50", outline="", tags="sel")
            canvas.create_rectangle(x1, y1, x2, y2, outline="#1E90FF", width=2, tags="sel")
            for hx, hy in handles_of(state["box"]):
                canvas.create_rectangle(hx - 4, hy - 4, hx + 4, hy + 4, fill="white", outline="#1E90FF", width=1, tags="sel")
            label = f"{x1},{y1}  {x2 - x1} × {y2 - y1} px"
            ly = y1 - 20 if y1 >= 22 else y1 + 6
            tid = canvas.create_text(x1 + 2, ly, anchor="nw", text=label, fill="white", font=("Consolas", 10, "bold"), tags="sel")
            bb = canvas.bbox(tid)
            if bb:
                bg = canvas.create_rectangle(bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2, fill="#333333", outline="", tags="sel")
                canvas.tag_lower(bg, tid)
            canvas.tag_raise("op")  # 标注画在选区框之上
        def place_toolbar():
            tb = state.get("tb")
            if tb is None: return
            tb.update_idletasks()
            tw, th = tb.winfo_reqwidth(), tb.winfo_reqheight()  # 用请求尺寸: 窗口未真正映射时 winfo_width 可能只有 1, 工具栏会被放错位 (真机出现过工具栏找不到)
            if tw <= 1 or th <= 1: tw, th = 700, 76
            x1, y1, x2, y2 = state["box"]
            tx = min(max(0, x1), max(0, full.width - tw))
            ty = y2 + 8 if y2 + 8 + th <= full.height else (y1 - th - 8 if y1 - th - 8 >= 0 else max(0, full.height - th))
            tb.place(x=tx, y=ty, width=tw, height=th)  # 同窗 Frame: place 到冻结屏画布之上, 坐标就是画布坐标
            tb.lift()
        def shift_ops(dx, dy):
            if dx or dy:
                for items in state["op_items"]:
                    for it in items: canvas.move(it, dx, dy)
        def draw_op(op):
            """把一条标注画到冻结屏画布上 (坐标: 存的是相对选区原点的图内坐标, 这里加回原点)"""
            ox, oy = state["box"][0], state["box"][1]
            t, c, w = op["type"], op["color"], op["width"]; ids = []
            if t in ("rect", "mosaic", "blur"):
                x1, y1, x2, y2 = [v + (ox if k % 2 == 0 else oy) for k, v in enumerate(op["box"])]
                kw = dict(outline=c, width=w) if t == "rect" else dict(fill="#888888", stipple="gray25", outline=c, width=1)
                ids.append(canvas.create_rectangle(x1, y1, x2, y2, tags="op", **kw))
            elif t == "ellipse":
                x1, y1, x2, y2 = [v + (ox if k % 2 == 0 else oy) for k, v in enumerate(op["box"])]
                ids.append(canvas.create_oval(x1, y1, x2, y2, outline=c, width=w, tags="op"))
            elif t == "seq":
                x, y = op["at"][0] + ox, op["at"][1] + oy; r = 11 + w * 2
                ids.append(canvas.create_oval(x - r, y - r, x + r, y + r, fill=c, outline="white", width=2, tags="op"))
                ids.append(canvas.create_text(x, y, text=str(op["n"]), fill="white", font=("Microsoft YaHei", max(9, int(r * 0.95)), "bold"), tags="op"))
            elif t in ("line", "arrow"):
                x1, y1, x2, y2 = [v + (ox if k % 2 == 0 else oy) for k, v in enumerate(op["box"])]
                ids.append(canvas.create_line(x1, y1, x2, y2, fill=c, width=w, tags="op"))
                if t == "arrow":
                    import math; ang = math.atan2(y2 - y1, x2 - x1); L = 10 + w * 2
                    for da in (2.8, -2.8):
                        ids.append(canvas.create_line(x2, y2, x2 + L * math.cos(ang + da), y2 + L * math.sin(ang + da), fill=c, width=w, tags="op"))
            elif t == "pen":
                pts = [(x + ox, y + oy) for x, y in op["points"]]
                if len(pts) > 1: ids.append(canvas.create_line(pts, fill=c, width=w, tags="op"))
            elif t == "text":
                ids.append(canvas.create_text(op["at"][0] + ox, op["at"][1] + oy, anchor="nw", text=op["text"],
                                              fill=c, font=("Microsoft YaHei", 14 + w * 3), tags="op"))
            return ids
        def finish(kind):
            box = state["box"]; final = self.render_ops(full.crop(box), state["ops"])
            self.save_shot(final); close_overlay()
            if kind == "pin": self.pin_image(final)
            elif kind == "copy":
                if not self._copy_image_to_clipboard(final):
                    messagebox.showinfo("复制到剪贴板", "图片复制失败, 已存进截图历史, 可在历史里打开")
            elif kind == "save": self._save_as(final)
        def build_toolbar():
            # 工具栏是冻结屏窗口内部的一个 Frame, 不再是独立小窗 (v1.4.6): 独立 Toplevel 在真机上
            # 反复出现不显示 (窗口层级/焦点/放置时机都可能出问题), 同窗 Frame 不存在这些问题, 必然可见。
            # 按键也不用单独绑: 按钮和 sel_win 同窗, Esc/方向键/回车经 bindtags 都会走到 sel_win 的绑定。
            tb = tk.Frame(sel_win, bg="#F2F2F2", bd=1, relief="solid")
            state["tb"] = tb
            r1 = tk.Frame(tb, bg="#F2F2F2"); r1.pack(fill="x")
            r2 = tk.Frame(tb, bg="#F2F2F2"); r2.pack(fill="x")
            tool_btns = {}
            def set_tool(name):
                state["tool"] = name
                for k2, b in tool_btns.items(): b.configure(bg="#BDD7EE" if k2 == name else "#F2F2F2")
            for txt, name in [("移动", None), ("矩形", "rect"), ("椭圆", "ellipse"), ("箭头", "arrow"), ("直线", "line"),
                              ("画笔", "pen"), ("文字", "text"), ("序号", "seq"), ("马赛克", "mosaic"), ("模糊", "blur")]:
                b = tk.Button(r1, text=txt, font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2",
                              command=lambda n=name: set_tool(n)); b.pack(side="left", padx=1, pady=2); tool_btns[name] = b
            set_tool(None)
            for cname in ("#FF0000", "#FFD800", "#00B050", "#0070FF", "#000000", "#FFFFFF"):
                tk.Button(r1, bg=cname, width=2, relief="ridge",
                          command=lambda cc=cname: state.update(color=cc)).pack(side="left", padx=1)
            width_var = tk.IntVar(value=3)
            ttk.Combobox(r1, textvariable=width_var, values=[1, 2, 3, 5, 8], width=3).pack(side="left", padx=2)
            width_var.trace_add("write", lambda *_: state.update(width=width_var.get()))
            def do_undo():
                if state["ops"]:
                    state["undone"].append(state["ops"].pop())
                    for it in state["op_items"].pop(): canvas.delete(it)
            def do_redo():
                if state["undone"]:
                    op = state["undone"].pop(); state["ops"].append(op); state["op_items"].append(draw_op(op))
            tk.Button(r1, text="撤销", font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2", command=do_undo).pack(side="left", padx=1)
            tk.Button(r1, text="重做", font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2", command=do_redo).pack(side="left", padx=1)
            tk.Button(r2, text="OCR", font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2",
                      command=lambda: self.recognize(self.render_ops(full.crop(state["box"]), state["ops"]), "ocr")).pack(side="left", padx=1)
            tk.Button(r2, text="翻译", font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2",
                      command=lambda: self.translate_image(self.render_ops(full.crop(state["box"]), state["ops"]))).pack(side="left", padx=1)
            def do_long():
                box = state["box"]
                try: tb.destroy()
                except Exception: pass
                try: sel_win.destroy()
                except Exception: pass
                self.after(350, lambda: self._run_long_capture(box))  # 等覆盖层完全消失再开始滚动截图
            def do_gif():
                box = state["box"]
                try: tb.destroy()
                except Exception: pass
                try: sel_win.destroy()
                except Exception: pass
                self.after(250, lambda: self._run_gif_record(box))
            tk.Button(r2, text="长截图", font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2", command=do_long).pack(side="left", padx=1)
            tk.Button(r2, text="GIF录制", font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2", command=do_gif).pack(side="left", padx=1)
            for txt, kind in [("钉图", "pin"), ("保存", "save")]:
                tk.Button(r2, text=txt, font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2",
                          command=lambda k=kind: finish(k)).pack(side="left", padx=1)
            tk.Button(r2, text="✕", font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2", command=close_overlay).pack(side="left", padx=1)
            tk.Button(r2, text="✓ 复制", font=("Microsoft YaHei", 9, "bold"), relief="flat", bg="#BDD7EE",
                      command=lambda: finish("copy")).pack(side="left", padx=1)
            def _no_focus(w):  # 工具栏按钮不抢键盘焦点, 焦点留在选区窗, Esc 等快捷键始终有效 (含两排子框架, 递归处理)
                for ch in w.winfo_children():
                    try: ch.configure(takefocus=0)
                    except Exception: pass
                    _no_focus(ch)
            _no_focus(tb)
        def restart_from(e):
            """调整阶段点到选区外: 不用 Esc 重来, 清掉当前选区/标注, 直接从点击处重新框选"""
            try:
                if state.get("tb") is not None: state["tb"].destroy(); state["tb"] = None
            except Exception: pass
            canvas.delete("sel"); canvas.delete("op"); canvas.delete("info"); canvas.delete("loupe")
            state.update(phase="select", ops=[], undone=[], op_items=[], drag=None, rect=None, tool=None, snap=None)
            canvas.bind("<Motion>", show_info)
            canvas.bind("<ButtonPress-1>", down); canvas.bind("<B1-Motion>", drag); canvas.bind("<ButtonRelease-1>", up)
            sel_win.bind("<KeyPress>", on_key)
            down(e)
        def adj_down(e):
            x1, y1, x2, y2 = state["box"]
            for idx, (hx, hy) in enumerate(handles_of(state["box"])):
                if abs(e.x - hx) <= 6 and abs(e.y - hy) <= 6:
                    state["drag"] = ("resize", idx, state["box"]); return
            if state["tool"] and x1 <= e.x <= x2 and y1 <= e.y <= y2:
                if state["tool"] == "seq":  # 序号是点击放置: 点一下落一个号, 自动递增
                    n = 1 + sum(1 for o in state["ops"] if o["type"] == "seq")
                    op = {"type": "seq", "at": (e.x - x1, e.y - y1), "n": n, "color": state["color"], "width": state["width"]}
                    state["ops"].append(op); state["undone"].clear(); state["op_items"].append(draw_op(op)); state["drag"] = None
                    return
                state["drag"] = ("draw", (e.x - x1, e.y - y1), [(e.x - x1, e.y - y1)], None)
                if state["tool"] == "text":
                    from tkinter import simpledialog
                    txt = simpledialog.askstring("文字标注", "输入文字:", parent=sel_win)
                    if txt:
                        op = {"type": "text", "at": (e.x - x1, e.y - y1), "text": txt, "color": state["color"], "width": state["width"]}
                        state["ops"].append(op); state["undone"].clear(); state["op_items"].append(draw_op(op))
                    state["drag"] = None
                return
            if x1 <= e.x <= x2 and y1 <= e.y <= y2: state["drag"] = ("move", (e.x, e.y), state["box"])
            else: restart_from(e)  # 点在选区外 -> 从这里重新框选
        def adj_drag(e):
            d = state.get("drag")
            if not d: return
            x1, y1, x2, y2 = state["box"]
            if d[0] == "move":
                dx, dy = e.x - d[1][0], e.y - d[1][1]
                dx = min(max(dx, -x1), full.width - x2); dy = min(max(dy, -y1), full.height - y2)
                state["box"] = (x1 + dx, y1 + dy, x2 + dx, y2 + dy); shift_ops(dx, dy); draw_sel(); place_toolbar()
            elif d[0] == "resize":
                idx, (ox1, oy1, ox2, oy2) = d[1], d[2]
                nx1, ny1, nx2, ny2 = ox1, oy1, ox2, oy2
                if idx in (0, 3, 5): nx1 = min(max(0, e.x), ox2 - 8)
                if idx in (2, 4, 7): nx2 = max(min(full.width, e.x), ox1 + 8)
                if idx in (0, 1, 2): ny1 = min(max(0, e.y), oy2 - 8)
                if idx in (5, 6, 7): ny2 = max(min(full.height, e.y), oy1 + 8)
                shift_ops(nx1 - x1, ny1 - y1)
                state["box"] = (nx1, ny1, nx2, ny2); draw_sel(); place_toolbar()
            elif d[0] == "draw":
                kind, start, points, temp = d
                if temp: canvas.delete(temp)
                cx, cy = e.x - x1, e.y - y1; tool = state["tool"]; c, w = state["color"], state["width"]
                if tool == "pen":
                    points.append((cx, cy))
                    temp = canvas.create_line([(px + x1, py + y1) for px, py in points], fill=c, width=w, tags="op")
                elif tool in ("rect", "mosaic", "blur"):
                    temp = canvas.create_rectangle(start[0] + x1, start[1] + y1, e.x, e.y, outline=c, width=w, tags="op")
                elif tool == "ellipse":
                    temp = canvas.create_oval(start[0] + x1, start[1] + y1, e.x, e.y, outline=c, width=w, tags="op")
                else:
                    temp = canvas.create_line(start[0] + x1, start[1] + y1, e.x, e.y, fill=c, width=w, tags="op")
                state["drag"] = (kind, start, points, temp)
        def adj_up(e):
            d = state.get("drag"); state["drag"] = None
            if not d or d[0] != "draw": return
            _, start, points, temp = d
            if temp: canvas.delete(temp)
            x1, y1 = state["box"][0], state["box"][1]
            ex, ey = e.x - x1, e.y - y1; tool = state["tool"]; c, w = state["color"], state["width"]
            if tool == "pen":
                if len(points) < 2: return
                op = {"type": "pen", "points": list(points), "color": c, "width": w}
            elif tool in ("rect", "ellipse", "mosaic", "blur"):
                op = {"type": tool, "box": (min(start[0], ex), min(start[1], ey), max(start[0], ex), max(start[1], ey)), "color": c, "width": w}
            elif tool in ("arrow", "line"):
                op = {"type": tool, "box": (start[0], start[1], ex, ey), "color": c, "width": w}
            else: return
            state["ops"].append(op); state["undone"].clear(); state["op_items"].append(draw_op(op))
        def key_undo():
            if state["ops"]:
                state["undone"].append(state["ops"].pop())
                for it in state["op_items"].pop(): canvas.delete(it)
        def key_redo():
            if state["undone"]:
                op = state["undone"].pop(); state["ops"].append(op); state["op_items"].append(draw_op(op))
        def adj_key(e):
            if state["phase"] != "adjust": return
            step = 10 if (e.state & 0x0001) else 1
            x1, y1, x2, y2 = state["box"]; dx = dy = 0
            if e.keysym == "Left": dx = -step
            elif e.keysym == "Right": dx = step
            elif e.keysym == "Up": dy = -step
            elif e.keysym == "Down": dy = step
            elif e.keysym == "Return": finish("copy"); return
            elif e.keysym.lower() == "c" and (e.state & 0x0004): finish("copy"); return  # Ctrl+C 直接复制成品图
            elif e.keysym.lower() == "z" and (e.state & 0x0004): key_undo(); return      # Ctrl+Z 撤销标注
            elif e.keysym.lower() == "y" and (e.state & 0x0004): key_redo(); return      # Ctrl+Y 重做
            elif e.keysym.lower() == "s" and (e.state & 0x0004): finish("save"); return  # Ctrl+S 另存为
            elif e.keysym.lower() == "t" and (e.state & 0x0004): finish("pin"); return   # Ctrl+T 转贴图
            else: return
            dx = min(max(dx, -x1), full.width - x2); dy = min(max(dy, -y1), full.height - y2)
            if dx or dy:
                state["box"] = (x1 + dx, y1 + dy, x2 + dx, y2 + dy); shift_ops(dx, dy); draw_sel(); place_toolbar()
        def enter_adjust(box):
            state["phase"] = "adjust"; state["box"] = box
            canvas.delete("info"); canvas.delete("loupe"); canvas.delete("snap")
            if state["rect"]: canvas.delete(state["rect"]); state["rect"] = None
            draw_sel(); build_toolbar(); place_toolbar()
            canvas.bind("<Motion>", lambda e: state.update(hex=_hex_at(e)))
            canvas.bind("<ButtonPress-1>", adj_down); canvas.bind("<B1-Motion>", adj_drag); canvas.bind("<ButtonRelease-1>", adj_up)
            canvas.bind("<Double-Button-1>", lambda e: finish("copy"))
            # 右键菜单兜底: 万一工具栏没显示出来, 保存/复制/钉图从这里也能完成 (真机反馈过工具栏找不到)
            adj_menu = tk.Menu(sel_win, tearoff=0)
            adj_menu.add_command(label="✓ 复制 (Enter)", command=lambda: finish("copy"))
            adj_menu.add_command(label="钉图 (Ctrl+T)", command=lambda: finish("pin"))
            adj_menu.add_command(label="另存为 (Ctrl+S)", command=lambda: finish("save"))
            adj_menu.add_separator()
            adj_menu.add_command(label="OCR 识别", command=lambda: self.recognize(self.render_ops(full.crop(state["box"]), state["ops"]), "ocr"))
            adj_menu.add_command(label="翻译图中文字", command=lambda: self.translate_image(self.render_ops(full.crop(state["box"]), state["ops"])))
            adj_menu.add_separator()
            adj_menu.add_command(label="取消截图 (Esc)", command=close_overlay)
            canvas.bind("<Button-3>", lambda e: adj_menu.tk_popup(e.x_root, e.y_root))
            sel_win.bind("<KeyPress>", lambda e: (adj_key(e), on_key(e))[0] if e.keysym in ("Left", "Right", "Up", "Down", "Return") or (e.keysym.lower() in ("c", "z", "y", "s", "t") and (e.state & 0x0004)) else on_key(e))
            sel_win.focus_set(); self._force_foreground(sel_win)
        def _hex_at(e):
            try: r, g, b = full.getpixel((e.x, e.y))[:3]; return f"#{r:02X}{g:02X}{b:02X}"
            except Exception: return state.get("hex", "")
        sel_win.bind("<Escape>", lambda e: close_overlay())
    def pin_clipboard(self):
        # Snipaste 的 F3: 剪贴板是图就贴图, 是文字就贴文字条
        if HAS_PIL:
            try: data = ImageGrab.grabclipboard()
            except Exception: data = None
            if data is not None and hasattr(data, "save"):
                self.pin_image(data.convert("RGB") if data.mode not in ("RGB", "RGBA") else data); return
            if isinstance(data, list) and data and os.path.isfile(str(data[0])):
                try: self.pin_image(Image.open(str(data[0]))); return
                except Exception: pass
        text = self.clip_get()
        if text: self.pin_text(text)
        else: messagebox.showinfo("贴剪贴板", "剪贴板里暂时没有图片或文字")
    def preview_shot(self, _e=None):
        sel = self.shots_list.curselection()
        if not sel or not HAS_PIL: return
        try:
            im = Image.open(os.path.join(self.shots_dir, self.shots_list.get(sel[0]))); im.thumbnail((120, 80))
            self._preview_photo = ImageTk.PhotoImage(im); self.shot_preview.config(image=self._preview_photo, text="")
        except Exception: pass
    def pin_selected_shot(self):
        sel = self.shots_list.curselection() if hasattr(self, "shots_list") else ()
        if not sel or not HAS_PIL: return
        self.pin_image(Image.open(os.path.join(self.shots_dir, self.shots_list.get(sel[0]))))
    def _draggable(self, win):
        pos = {}
        def down(e): pos.update(x=e.x_root - win.winfo_x(), y=e.y_root - win.winfo_y())
        def move(e): win.geometry(f"+{e.x_root - pos['x']}+{e.y_root - pos['y']}")
        for w in [win] + win.winfo_children():
            w.bind("<ButtonPress-1>", down); w.bind("<B1-Motion>", move)
    # ---------- 贴图管理动作 (对齐 Snipaste「快捷键/动作」页, 都可在热键设置里绑键) ----------
    def snip_copy(self):
        """截图并复制: 框选完直接复制到剪贴板, 不停留标注"""
        self._snip_finish_mode = "copy"; self.snip_region()
    def snip_translate(self):
        """截图翻译: 框选完直接 OCR + 自动检测源语言 + 翻译到设置的目标语言 (默认中文), 不停留标注"""
        self._snip_finish_mode = "translate"; self.snip_region()
    def snip_delayed(self):
        """延时截图: 倒计时后才开始, 方便截菜单/提示框这类一动鼠标就消失的画面"""
        try: secs = float(self.cfg.get("Snip", "DelaySeconds", fallback="3"))
        except Exception: secs = 3.0
        self.status.set(f"{secs:g} 秒后开始截图, 先把要截的画面准备好…")
        self.after(int(secs * 1000), self.snip_region)
    def close_all_pins(self):
        for w in list(self._pins):
            try: w.destroy()
            except Exception: pass
    def toggle_pins_visible(self):
        if not self._pins: return
        hide = any(w.winfo_viewable() for w in self._pins if w.winfo_exists())
        for w in list(self._pins):
            try: w.withdraw() if hide else w.deiconify()
            except Exception: pass
    def restore_last_pin(self):
        if self._last_closed_pin is not None: self.pin_image(self._last_closed_pin)
    def toggle_pins_clickthrough(self):
        """贴图鼠标穿透开关: 开后贴图不挡鼠标, 点它等于点它下面的窗口 (再按一次关掉)"""
        self._pins_clickthrough = not self._pins_clickthrough
        for w in list(self._pins): self._apply_clickthrough(w, self._pins_clickthrough)
        self.status.set("贴图鼠标穿透: " + ("开 (贴图不再挡鼠标)" if self._pins_clickthrough else "关"))
    @staticmethod
    def _apply_clickthrough(win, on):
        if sys.platform != "win32": return
        try:
            u = ctypes.windll.user32
            root = u.GetAncestor(win.winfo_id(), 2)  # GA_ROOT: winfo_id 是内层窗, 要取顶层 HWND
            style = u.GetWindowLongW(root, -20)  # GWL_EXSTYLE
            style = (style | 0x00080000 | 0x00000020) if on else (style & ~0x00000020)  # WS_EX_LAYERED | WS_EX_TRANSPARENT
            u.SetWindowLongW(root, -20, style)
        except Exception: pass
    def pin_image(self, img):
        win = tk.Toplevel(self); win.overrideredirect(True); win.attributes("-topmost", True)
        win.geometry("+120+120"); state = {"img": img.copy(), "scale": 1.0, "photo": None}
        self._pins.append(win)
        def _on_destroy(e):
            if e.widget is not win: return
            if win in self._pins: self._pins.remove(win)
            self._last_closed_pin = state["img"]
        win.bind("<Destroy>", _on_destroy)
        if self._pins_clickthrough: win.after(50, lambda: self._apply_clickthrough(win, True))
        label = tk.Label(win, bd=2, relief="solid"); label.pack()
        def render():
            w, h = state["img"].size; nw, nh = max(20, int(w * state["scale"])), max(20, int(h * state["scale"]))
            state["photo"] = ImageTk.PhotoImage(state["img"].resize((nw, nh), Image.LANCZOS)); label.config(image=state["photo"])
        render()
        menu = tk.Menu(win, tearoff=0)
        menu.add_command(label="标注这张图", command=lambda: (win.destroy(), self.open_editor(state["img"])))
        menu.add_command(label="OCR 识别这张图", command=lambda: self.recognize(state["img"], "ocr"))
        menu.add_command(label="翻译图中文字", command=lambda: self.translate_image(state["img"]))
        menu.add_command(label="扫这张图的码", command=lambda: self.recognize(state["img"], "code"))
        menu.add_command(label="旋转 90°", command=lambda: (state.update(img=state["img"].rotate(-90, expand=True)), render()))
        alpha = tk.Menu(menu, tearoff=0)
        for pct in (100, 80, 60, 40):
            alpha.add_command(label=f"不透明度 {pct}%", command=lambda a=pct/100: win.attributes("-alpha", a))
        menu.add_cascade(label="透明度", menu=alpha)
        menu.add_command(label="复制图片到剪贴板", command=lambda: self._copy_image_to_clipboard(state["img"]))
        menu.add_command(label="另存为 PNG", command=lambda: self._save_as(state["img"]))
        menu.add_command(label="关闭贴图 (双击也可)", command=win.destroy)
        # 事件只绑在 label 上并 return "break": 旧版 win 和 label 各绑一份, 事件沿 bindtags 传播会缩放两次
        def on_wheel(e):
            state.update(scale=min(4, max(0.1, state["scale"] * (1.1 if e.delta > 0 else 0.9)))); render(); return "break"
        def on_menu(e): menu.tk_popup(e.x_root, e.y_root); return "break"
        win.bind("<Button-3>", on_menu)
        label.bind("<Button-3>", on_menu)
        label.bind("<MouseWheel>", on_wheel)
        label.bind("<Double-Button-1>", lambda e: (win.destroy(), "break")[1])
        hint = ttk.Label(win, text="拖动移动 · 滚轮缩放 · 双击关闭 · 右键可识别整图文字"); hint.pack(); hint.bind("<MouseWheel>", on_wheel)
        self._draggable(win)  # 最后绑, 覆盖子控件的按下事件为拖动 (根坐标计算, 不受子控件位置影响)
    def _save_as(self, img):
        p = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if p: img.save(p)
    def _copy_image_to_clipboard(self, img):
        """把图片放进系统剪贴板 (Snipaste 截图完成的主动作): 先走 Win32 CF_DIB, 失败再走 PowerShell 备用通道。
        v1.4.5 真机仍报复制失败: Win32 通道里 GlobalAlloc 的尺寸参数 (SIZE_T) 没声明类型, 64 位下可能传错;
        这次补全所有参数签名, 并加一条和 OCR 共用、真机验证过的 PowerShell 桥作双保险。"""
        if sys.platform != "win32": return False
        return self._copy_image_win32(img) or self._copy_image_powershell(img)

    def _copy_image_powershell(self, img):
        """备用通道: 借 PowerShell 的 Windows.Forms 把图片放进剪贴板。图片路径走环境变量传, 避开中文路径编码问题。"""
        import subprocess, tempfile
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".png"); os.close(fd)
            img.save(path, "PNG")
            ps = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
                  "$img = [System.Drawing.Image]::FromFile($env:SP_CLIP_PATH); "
                  "[System.Windows.Forms.Clipboard]::SetImage($img); $img.Dispose()")
            env = dict(os.environ); env["SP_CLIP_PATH"] = path
            r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                               capture_output=True, timeout=20, env=env,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0: return False
            try: return bool(ctypes.windll.user32.IsClipboardFormatAvailable(8))  # CF_DIB 在 = 图已进剪贴板
            except Exception: return True
        except Exception: return False
        finally:
            if path:
                try: os.remove(path)
                except Exception: pass

    def _copy_image_win32(self, img):
        """Win32 CF_DIB 通道。剪贴板常被别的程序短暂占用: 打开要重试, 只试一次很容易失败。"""
        try:
            import io
            bio = io.BytesIO(); img.convert("RGB").save(bio, "BMP")
            data = bio.getvalue()[14:]  # 去掉 BITMAPFILEHEADER, 剩下就是 DIB
            user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
            kernel32.GlobalAlloc.restype = ctypes.c_void_p
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            user32.SetClipboardData.restype = ctypes.c_void_p
            user32.GetClipboardData.restype = ctypes.c_void_p
            h = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
            if not h: return False
            ptr = kernel32.GlobalLock(h)
            if not ptr: kernel32.GlobalFree(ctypes.c_void_p(h)); return False
            ctypes.memmove(ptr, data, len(data)); kernel32.GlobalUnlock(h)
            opened = False
            for _ in range(10):  # 重试打开剪贴板 (50ms 间隔, 最多约 0.5 秒)
                if user32.OpenClipboard(None): opened = True; break
                time.sleep(0.05)
            if not opened: kernel32.GlobalFree(ctypes.c_void_p(h)); return False
            try:
                user32.EmptyClipboard()
                if not user32.SetClipboardData(8, h):  # CF_DIB = 8; 成功后内存归系统, 不能再 Free
                    kernel32.GlobalFree(ctypes.c_void_p(h)); return False
                return bool(user32.GetClipboardData(8))  # 回读确认数据真的在剪贴板里
            finally: user32.CloseClipboard()
        except Exception: return False
    # ---------- 标注编辑器 (v1.1, 对标 Snipaste 标注) ----------
    @staticmethod
    def _font(size):
        for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                     "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            if os.path.exists(path):
                try: return ImageFont.truetype(path, size)
                except Exception: pass
        return ImageFont.load_default()
    @classmethod
    def render_ops(cls, base, ops):
        """把标注操作列表画到图上, 返回新图。ops 可撤销重绘, 单元测试也走这里。"""
        img = base.convert("RGB").copy(); d = ImageDraw.Draw(img)
        for op in ops:
            t, c, w = op["type"], op["color"], op["width"]
            if t == "rect": d.rectangle(op["box"], outline=c, width=w)
            elif t == "ellipse": d.ellipse(op["box"], outline=c, width=w)
            elif t == "line": d.line(op["box"], fill=c, width=w)
            elif t == "pen":
                if len(op["points"]) > 1: d.line(op["points"], fill=c, width=w, joint="curve")
            elif t == "arrow":
                x1, y1, x2, y2 = op["box"]; d.line(op["box"], fill=c, width=w)
                import math; ang = math.atan2(y2 - y1, x2 - x1); L = 10 + w * 2
                for da in (2.8, -2.8):
                    d.line([x2, y2, x2 + L * math.cos(ang + da), y2 + L * math.sin(ang + da)], fill=c, width=w)
            elif t == "text": d.text(op["at"], op["text"], fill=c, font=cls._font(14 + w * 3))
            elif t == "seq":
                x, y = op["at"]; r = 11 + w * 2; n = str(op["n"])
                d.ellipse([x - r, y - r, x + r, y + r], fill=c, outline="white", width=2)
                f = cls._font(int(r * 1.15))
                try:
                    bb = d.textbbox((0, 0), n, font=f)
                    d.text((x - (bb[2] - bb[0]) / 2 - bb[0], y - (bb[3] - bb[1]) / 2 - bb[1]), n, fill="white", font=f)
                except Exception: d.text((x - 4, y - 6), n, fill="white", font=f)
            elif t == "blur":
                x1, y1, x2, y2 = [int(v) for v in op["box"]]
                if x2 - x1 > 4 and y2 - y1 > 4:
                    region = img.crop((x1, y1, x2, y2)).filter(ImageFilter.GaussianBlur(8))
                    img.paste(region, (x1, y1)); d = ImageDraw.Draw(img)
            elif t == "mosaic":
                x1, y1, x2, y2 = [int(v) for v in op["box"]]
                if x2 - x1 > 4 and y2 - y1 > 4:
                    region = img.crop((x1, y1, x2, y2))
                    small = region.resize((max(1, (x2-x1)//12), max(1, (y2-y1)//12)), Image.NEAREST)
                    img.paste(small.resize(region.size, Image.NEAREST), (x1, y1)); d = ImageDraw.Draw(img)
        return img
    def open_editor(self, base_img):
        if not HAS_PIL: return
        base = base_img.convert("RGB")
        win = tk.Toplevel(self); win.title("标注 - 画完点「完成并钉图」"); win.attributes("-topmost", True)
        tool = tk.StringVar(value="rect"); color = tk.StringVar(value="#FF0000"); width = tk.IntVar(value=3)
        ops, undone, state = [], [], {"start": None, "points": [], "temp": None}
        bar = ttk.Frame(win); bar.pack(fill="x", padx=6, pady=4)
        for txt, val in [("矩形", "rect"), ("椭圆", "ellipse"), ("箭头", "arrow"), ("直线", "line"),
                         ("画笔", "pen"), ("文字", "text"), ("序号", "seq"), ("马赛克", "mosaic"), ("模糊", "blur")]:
            ttk.Radiobutton(bar, text=txt, variable=tool, value=val).pack(side="left", padx=1)
        for cname in ("#FF0000", "#FFD800", "#00B050", "#0070FF", "#000000", "#FFFFFF"):
            tk.Button(bar, bg=cname, width=2, command=lambda cc=cname: color.set(cc)).pack(side="left", padx=1)
        ttk.Combobox(bar, textvariable=width, values=[1, 2, 3, 5, 8], width=3).pack(side="left", padx=3)
        # 大图按比例缩小显示 (旧版按原图尺寸开窗, 截大区域/4K 时窗口超出屏幕点不到按钮)
        scale = min(1.0, 1500 / base.width, 880 / base.height)
        dw, dh = max(1, int(base.width * scale)), max(1, int(base.height * scale))
        canvas = tk.Canvas(win, width=dw, height=dh, highlightthickness=1, highlightbackground="gray")
        canvas.pack(padx=6, pady=4)
        def to_img(e): return (int(e.x / scale), int(e.y / scale))  # 显示坐标 -> 原图坐标, ops 永远存原图坐标
        def redraw():
            rendered = self.render_ops(base, ops)
            if scale < 1.0: rendered = rendered.resize((dw, dh), Image.LANCZOS)
            state["photo"] = ImageTk.PhotoImage(rendered)
            canvas.delete("all"); canvas.create_image(0, 0, anchor="nw", image=state["photo"])
        redraw()
        def down(e):
            state["start"] = to_img(e); state["start_disp"] = (e.x, e.y)
            state["points"] = [to_img(e)]; state["points_disp"] = [(e.x, e.y)]
            if tool.get() == "text":
                from tkinter import simpledialog
                txt = simpledialog.askstring("文字标注", "输入文字:", parent=win)
                if txt: ops.append({"type": "text", "at": state["start"], "text": txt, "color": color.get(), "width": width.get()}); undone.clear(); redraw()
                state["start"] = None
            if tool.get() == "seq":
                n = 1 + sum(1 for o in ops if o["type"] == "seq")
                ops.append({"type": "seq", "at": state["start"], "n": n, "color": color.get(), "width": width.get()}); undone.clear(); redraw()
                state["start"] = None
        def drag(e):
            if state["start"] is None: return
            if state["temp"]: canvas.delete(state["temp"])
            x1, y1 = state["start_disp"]
            if tool.get() == "pen":
                state["points"].append(to_img(e)); state["points_disp"].append((e.x, e.y))
                state["temp"] = canvas.create_line(state["points_disp"], fill=color.get(), width=width.get())
            elif tool.get() in ("rect", "mosaic", "blur"): state["temp"] = canvas.create_rectangle(x1, y1, e.x, e.y, outline=color.get(), width=width.get())
            elif tool.get() == "ellipse": state["temp"] = canvas.create_oval(x1, y1, e.x, e.y, outline=color.get(), width=width.get())
            else: state["temp"] = canvas.create_line(x1, y1, e.x, e.y, fill=color.get(), width=width.get())
        def up(e):
            if state["start"] is None: return
            x1, y1 = state["start"]; ex, ey = to_img(e); t = tool.get()
            if t == "pen": ops.append({"type": "pen", "points": list(state["points"]), "color": color.get(), "width": width.get()}); undone.clear()
            elif t in ("rect", "ellipse", "arrow", "line", "mosaic", "blur"):
                ops.append({"type": t, "box": (min(x1, ex), min(y1, ey), max(x1, ex), max(y1, ey)) if t in ("rect", "ellipse", "mosaic", "blur") else (x1, y1, ex, ey),
                            "color": color.get(), "width": width.get()}); undone.clear()
            state["start"] = None; state["temp"] = None; redraw()
        canvas.bind("<ButtonPress-1>", down); canvas.bind("<B1-Motion>", drag); canvas.bind("<ButtonRelease-1>", up)
        btns = ttk.Frame(win); btns.pack(fill="x", padx=6, pady=6)
        def do_undo():
            if ops: undone.append(ops.pop()); redraw()
        def do_redo():
            if undone: ops.append(undone.pop()); redraw()
        ttk.Button(btns, text="撤销", command=do_undo).pack(side="left", padx=2)
        ttk.Button(btns, text="重做", command=do_redo).pack(side="left", padx=2)
        ttk.Button(btns, text="OCR 识别文字", command=lambda: self.recognize(self.render_ops(base, ops), "ocr")).pack(side="left", padx=2)
        ttk.Button(btns, text="扫二维码/条码", command=lambda: self.recognize(self.render_ops(base, ops), "code")).pack(side="left", padx=2)
        ttk.Button(btns, text="清空标注", command=lambda: (ops.clear(), undone.clear(), redraw())).pack(side="left", padx=2)
        def finish(pin=True):
            final = self.render_ops(base, ops); self.save_shot(final); win.destroy()
            if pin: self.pin_image(final)
        def finish_copy():
            final = self.render_ops(base, ops); self.save_shot(final)
            ok = self._copy_image_to_clipboard(final); win.destroy()
            if not ok: messagebox.showinfo("复制到剪贴板", "图片复制到剪贴板失败, 已存进截图历史, 可在历史里打开")
        def finish_save_as():
            final = self.render_ops(base, ops); self.save_shot(final); win.destroy(); self._save_as(final)
        win.bind("<Control-c>", lambda e: finish_copy()); win.bind("<Control-C>", lambda e: finish_copy())  # Ctrl+C 直接复制
        win.bind("<Escape>", lambda e: win.destroy())  # Esc 放弃这张图
        ttk.Button(btns, text="完成并钉图", command=lambda: finish(True)).pack(side="right", padx=2)
        ttk.Button(btns, text="复制到剪贴板", command=finish_copy).pack(side="right", padx=2)
        ttk.Button(btns, text="另存为", command=finish_save_as).pack(side="right", padx=2)
        ttk.Button(btns, text="只保存不钉图", command=lambda: finish(False)).pack(side="right", padx=2)
        ttk.Button(btns, text="放弃", command=win.destroy).pack(side="right", padx=2)

    # ---------- 窗口吸附 (v1.2, Windows) ----------
    @staticmethod
    def pick_window(x, y, rects):
        """返回包含 (x,y) 的最小窗口矩形 (面积最小的最上层近似), 没有返回 None。纯逻辑, 可单测。"""
        hits = [r for r in rects if r[0] <= x <= r[2] and r[1] <= y <= r[3] and r[2] > r[0] and r[3] > r[1]]
        return min(hits, key=lambda r: (r[2] - r[0]) * (r[3] - r[1])) if hits else None
    @staticmethod
    def list_window_rects():
        if sys.platform != "win32": return []
        try:
            import ctypes.wintypes as wt
            user32 = ctypes.windll.user32; rects = []
            CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
            def cb(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    r = wt.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
                    if r.right - r.left > 20 and r.bottom - r.top > 20: rects.append((r.left, r.top, r.right, r.bottom))
                return True
            user32.EnumWindows(CB(cb), 0); return rects
        except Exception: return []
    @staticmethod
    def _enum_top_windows():
        """枚举顶层可见窗口, 返回 [(hwnd, rect)]; 非 Windows 返回空"""
        if sys.platform != "win32": return []
        try:
            import ctypes.wintypes as wt
            user32 = ctypes.windll.user32; out = []
            CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
            def cb(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    r = wt.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
                    if r.right - r.left > 20 and r.bottom - r.top > 20: out.append((hwnd, (r.left, r.top, r.right, r.bottom)))
                return True
            user32.EnumWindows(CB(cb), 0); return out
        except Exception: return []
    @staticmethod
    def _smallest_child_rect(hwnd, x, y):
        """枚举 hwnd 的子窗口, 返回包含 (x,y) 的最小子窗口矩形 (控件级检测的第一层, 纯 Win32); 无则 None"""
        if sys.platform != "win32" or not hwnd: return None
        try:
            import ctypes.wintypes as wt
            user32 = ctypes.windll.user32; found = []
            CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
            def cb(h, _):
                try:
                    if user32.IsWindowVisible(h):
                        r = wt.RECT(); user32.GetWindowRect(h, ctypes.byref(r))
                        if r.left <= x <= r.right and r.top <= y <= r.bottom and r.right > r.left and r.bottom > r.top:
                            found.append((r.left, r.top, r.right, r.bottom))
                except Exception: pass
                return True
            user32.EnumChildWindows(hwnd, CB(cb), 0)
            return min(found, key=lambda r: (r[2] - r[0]) * (r[3] - r[1])) if found else None
        except Exception: return None
    # UI Automation 取元素矩形脚本 (与 OCR 同一条 PowerShell 桥, 系统自带能力, 零依赖)
    _WIN_UIA_PS1 = (
        "Add-Type -AssemblyName UIAutomationClient; Add-Type -AssemblyName UIAutomationTypes; "
        "try {{ $el = [System.Windows.Automation.AutomationElement]::FromPoint((New-Object System.Windows.Point({x}, {y}))); "
        "if ($el) {{ $r = $el.Current.BoundingRectangle; "
        "[Console]::Out.Write(\"$([int]$r.Left),$([int]$r.Top),$([int]$r.Right),$([int]$r.Bottom)\") }} }} catch {{}}")
    @classmethod
    def _uia_rect_at(cls, x, y):
        """用 UI Automation 取 (x,y) 处界面元素的矩形 (按钮/输入框等控件级); 失败返回 None。
        只在单击选区时调用一次 (PowerShell 冷启动约几百毫秒), 不用于悬停高亮。"""
        if sys.platform != "win32": return None
        try:
            import subprocess
            ps = cls._WIN_UIA_PS1.format(x=int(x), y=int(y))
            p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                               capture_output=True, timeout=5, creationflags=0x08000000)  # CREATE_NO_WINDOW
            parts = p.stdout.decode("utf-8", "ignore").strip().split(",")
            if len(parts) != 4: return None
            l, t, r, b = (int(v) for v in parts)
            return (l, t, r, b) if r - l >= 4 and b - t >= 4 else None
        except Exception: return None

    # ---------- OCR / 扫码 (v1.2, 可选引擎, 没装时优雅提示) ----------
    _ocr_engine = None  # RapidOCR 实例缓存: 旧版每次识别都重建引擎、重加载模型 (数秒), 只建一次
    # Windows 内置 OCR 脚本 (与 Snipaste 同款引擎 Windows.Media.Ocr, 零依赖, EXE 里也能用)
    _WIN_OCR_PS1 = r"""
param([string]$ImgPath, [string]$OutPath)
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
  $null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
  $null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
  $null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
  $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  function Await($op, $type) { $m = $asTask.MakeGenericMethod($type); $t = $m.Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImgPath)) ([Windows.Storage.StorageFile])
  $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
  if ($null -eq $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language 'zh-Hans-CN')) }
  if ($null -eq $engine) { throw 'NO_OCR_LANGUAGE' }
  $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  [System.IO.File]::WriteAllText($OutPath, $result.Text, (New-Object System.Text.UTF8Encoding $false))
} catch {
  [System.IO.File]::WriteAllText($OutPath, ('ERROR: ' + $_.Exception.Message), (New-Object System.Text.UTF8Encoding $false))
}
"""
    @classmethod
    def _ocr_windows_builtin(cls, img):
        """Windows 自带 OCR: 有结果返回文字, 没文字返回 '', 引擎/语言包不可用返回 None"""
        if sys.platform != "win32": return None
        import subprocess, tempfile
        tmp = tempfile.mkdtemp(prefix="snappaste_ocr_")
        img_path, out_path, ps_path = (os.path.join(tmp, n) for n in ("in.png", "out.txt", "ocr.ps1"))
        try:
            img.save(img_path)
            with open(ps_path, "w", encoding="utf-8") as f: f.write(cls._WIN_OCR_PS1)
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path,
                            "-ImgPath", img_path, "-OutPath", out_path],
                           capture_output=True, timeout=30, creationflags=0x08000000)
            if not os.path.exists(out_path): return None
            txt = open(out_path, encoding="utf-8-sig").read().strip()
            if txt.startswith("ERROR:"):
                return None if "NO_OCR_LANGUAGE" in txt else ""
            # Windows OCR 会在汉字之间插空格, 清理掉 CJK 之间的空格
            return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", txt)
        except Exception:
            return None
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
    @classmethod
    def ocr_image(cls, img):
        """有引擎返回识别文字 (可能为空串); 没引擎返回 None。优先级: Windows 内置 OCR -> RapidOCR -> pytesseract"""
        builtin = cls._ocr_windows_builtin(img)
        if builtin is not None: return builtin
        try:
            from rapidocr_onnxruntime import RapidOCR
            import numpy as np
            if cls._ocr_engine is None: cls._ocr_engine = RapidOCR()
            result, _ = cls._ocr_engine(np.array(img.convert("RGB")))
            return "\n".join(line[1] for line in result) if result else ""
        except ImportError: pass
        except Exception: return ""
        try:
            import pytesseract
            return pytesseract.image_to_string(img, lang="chi_sim+eng").strip()
        except ImportError: return None
        except Exception: return ""
    @staticmethod
    def decode_codes(img):
        """有引擎返回码内容列表 (可能为空); 没引擎返回 None。引擎: OpenCV -> pyzbar"""
        try:
            import cv2, numpy as np
            arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR); found = []
            data, _, _ = cv2.QRCodeDetector().detectAndDecode(arr)
            if data: found.append(data)
            try:
                bdata, _, _ = cv2.barcode_BarcodeDetector().detectAndDecode(arr)
                if bdata: found += [d for d in bdata if d]
            except Exception: pass
            return found
        except ImportError: pass
        except Exception: return []
        try:
            from pyzbar.pyzbar import decode as zdecode
            return [d.data.decode("utf-8", "replace") for d in zdecode(img)]
        except ImportError: return None
        except Exception: return []
    def recognize(self, img, kind):
        if kind == "ocr":
            res = self.ocr_image(img)
            if res is None:
                hint = ("OCR 用的是 Windows 自带识别引擎, 现在不可用, 多半是系统没装中文语言包:\n"
                        "到 Windows「设置 → 时间和语言 → 语言和区域」添加「中文(简体)」, 装好后重启本软件再试。") \
                    if getattr(sys, "frozen", False) else \
                    ("还没装 OCR 引擎, 装一次即可 (离线可用):\n\npip install rapidocr-onnxruntime\n\n或装 Tesseract 程序 + pip install pytesseract")
                messagebox.showinfo("OCR 未启用", hint); return
            self.show_text_result("OCR 识别结果", res or "(没识别到文字, 换个更清晰的截图试试)", translate=True)
        else:
            res = self.decode_codes(img)
            if res is None:
                messagebox.showinfo("扫码未启用", "还没装扫码引擎, 装一次即可:\n\npip install opencv-python-headless"); return
            self.show_text_result("扫码结果", "\n".join(res) if res else "(没扫到二维码/条码)")
    # ---------- 截图翻译: OCR 出的文字自动英<->中互译 ----------
    @staticmethod
    def translate_text(text):
        """把文字在 英文<->简体中文 间翻译 (含汉字则译成英文, 否则译成中文)。
        用免费在线接口 (MyMemory 主, Google 备用), 无需密钥; 全部失败返回 None。"""
        import urllib.request, urllib.parse, json as _json
        text = (text or "").strip()
        if not text: return ""
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)
        src, dst = ("zh-CN", "en") if has_cjk else ("en", "zh-CN")
        groups, cur = [], ""  # 接口单次长度有限: 按行攒成 <=450 字符的段, 分段译后拼回
        for line in text.splitlines():
            if cur and len(cur) + len(line) + 1 > 450: groups.append(cur); cur = line
            else: cur = (cur + "\n" + line) if cur else line
        if cur: groups.append(cur)
        def via_mymemory(q):
            url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode({"q": q, "langpair": f"{src}|{dst}"})
            req = urllib.request.Request(url, headers={"User-Agent": "SnapPaste"})
            with urllib.request.urlopen(req, timeout=12) as r:
                d = _json.loads(r.read().decode("utf-8"))
            return (d.get("responseData") or {}).get("translatedText") or ""
        def via_google(q):
            url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(
                {"client": "gtx", "sl": src, "tl": dst, "dt": "t", "q": q})
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                d = _json.loads(r.read().decode("utf-8"))
            return "".join(seg[0] for seg in (d[0] or []) if seg and seg[0])
        out = []
        for g in groups:
            t = ""
            try: t = via_mymemory(g)
            except Exception: t = ""
            if not t:
                try: t = via_google(g)
                except Exception: return None
            if not t: return None
            out.append(t)
        return "\n".join(out)
    def trans_target(self):
        """截图翻译的目标语言: [Snip] TransTarget, zh-CN (默认) 或 en, 主窗口可改"""
        v = (self.cfg.get("Snip", "TransTarget", fallback="zh-CN") or "zh-CN").strip()
        return v if v in ("zh-CN", "en") else "zh-CN"
    @staticmethod
    def translate_text_to(text, target):
        """把文字翻译到指定目标语言, 源语言自动检测 (一键截图翻译 F4 用)。
        Google 接口 (sl=auto) 为主, MyMemory 备用; 原文已是中文且目标也是中文时原样返回; 全部失败返回 None。"""
        import urllib.request, urllib.parse, json as _json
        text = (text or "").strip()
        if not text: return ""
        cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        if target == "zh-CN" and cjk >= 3 and cjk * 2 >= len(text.replace(" ", "")): return text  # 基本已是中文, 不必译
        has_cjk = cjk > 0
        groups, cur = [], ""
        for line in text.splitlines():
            if cur and len(cur) + len(line) + 1 > 450: groups.append(cur); cur = line
            else: cur = (cur + "\n" + line) if cur else line
        if cur: groups.append(cur)
        def via_google(q):
            url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(
                {"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": q})
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                d = _json.loads(r.read().decode("utf-8"))
            return "".join(seg[0] for seg in (d[0] or []) if seg and seg[0])
        def via_mymemory(q):
            src = "zh-CN" if has_cjk else "en"
            url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode({"q": q, "langpair": f"{src}|{target}"})
            req = urllib.request.Request(url, headers={"User-Agent": "SnapPaste"})
            with urllib.request.urlopen(req, timeout=12) as r:
                d = _json.loads(r.read().decode("utf-8"))
            return (d.get("responseData") or {}).get("translatedText") or ""
        out = []
        for g in groups:
            t = ""
            try: t = via_google(g)
            except Exception: t = ""
            if not t:
                try: t = via_mymemory(g)
                except Exception: return None
            if not t: return None
            out.append(t)
        return "\n".join(out)
    def translate_and_show(self, text):
        """后台线程翻译 (不冻结界面), 完成后回主线程弹结果窗"""
        import threading
        def work():
            res = self.translate_text(text)
            def show():
                if res is None:
                    messagebox.showinfo("截图翻译", "翻译失败: 用的是免费在线翻译接口, 需要联网, 检查网络后重试。")
                elif not res:
                    messagebox.showinfo("截图翻译", "没有可翻译的文字。")
                else:
                    self.show_text_result("翻译结果", res)
            self._ui_queue.put(show)
        threading.Thread(target=work, daemon=True).start()
    def translate_image(self, img, target=None):
        """对一张图先 OCR 再翻译 (都在后台线程跑, 不冻结界面)。target 给定则译到该语言 (源语言自动检测), 否则英<->中互译"""
        import threading
        def work():
            text = self.ocr_image(img)
            if not text or not text.strip():
                self._ui_queue.put(lambda: messagebox.showinfo("截图翻译", "这张图没识别出文字, 换个更清晰的截图试试。")); return
            res = self.translate_text_to(text, target) if target else self.translate_text(text)
            def show():
                if res is None:
                    messagebox.showinfo("截图翻译", "翻译失败: 用的是免费在线翻译接口, 需要联网, 检查网络后重试。")
                else:
                    self.show_text_result("翻译结果", res)
            self._ui_queue.put(show)
        threading.Thread(target=work, daemon=True).start()
    def show_text_result(self, title, text, translate=False):
        win = tk.Toplevel(self); win.title(title); win.geometry("520x340"); win.attributes("-topmost", True)
        # 按钮栏必须先 pack 到底部占位: 旧写法先 pack 文本框, 它默认请求 24 行高, 超过窗高后
        # 后 pack 的按钮栏被挤到窗口外看不见 (真机实证: 结果窗只有文字没有按钮)
        bar = ttk.Frame(win); bar.pack(side="bottom", fill="x", padx=8, pady=6)
        box = tk.Text(win, wrap="word", height=10); box.pack(fill="both", expand=True, padx=8, pady=8); box.insert("1.0", text)
        copy_btn = ttk.Button(bar, text="复制结果")
        def do_copy():
            self.clip_set(box.get("1.0", "end").strip())
            copy_btn.config(text="已复制 ✓")  # 给个明确反馈, 不然点了像没反应 (真机反馈过)
            win.after(1200, lambda: copy_btn.config(text="复制结果"))
        copy_btn.config(command=do_copy); copy_btn.pack(side="left", padx=2)
        def to_queue():
            added = 0
            for line in box.get("1.0", "end").splitlines():
                if line.strip(): self.add_record(line); added += 1
            self.refresh_list(); messagebox.showinfo("文字队列", f"已加入 {added} 条到文字队列, 之后按 F7 就能逐条粘贴", parent=win)
        ttk.Button(bar, text="加入文字队列 (配合 F7 粘贴)", command=to_queue).pack(side="left", padx=2)
        if translate:
            ttk.Button(bar, text="翻译 (英↔中)", command=lambda: self.translate_and_show(box.get("1.0", "end").strip())).pack(side="left", padx=2)
        ttk.Button(bar, text="关闭", command=win.destroy).pack(side="right", padx=2)
    def ocr_selected_shot(self):
        sel = self.shots_list.curselection() if hasattr(self, "shots_list") else ()
        if not sel or not HAS_PIL: messagebox.showinfo("OCR", "先在截图列表里选一张"); return
        self.recognize(Image.open(os.path.join(self.shots_dir, self.shots_list.get(sel[0]))), "ocr")

    # ---------- 截图历史画廊 (v1.2) ----------
    def open_gallery(self):
        if not HAS_PIL: return
        win = tk.Toplevel(self); win.title("截图历史画廊"); win.geometry("760x500")
        outer = ttk.Frame(win); outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer); sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        grid = ttk.Frame(canvas); grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=grid, anchor="nw"); canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        win._photos = []
        files = [f for f in sorted(os.listdir(self.shots_dir), reverse=True) if f.lower().endswith(".png")][:60]  # 只展示最近 60 张, 防几百张时全量解码卡顿
        if not files: ttk.Label(grid, text="还没有截图, 先按 F1 截一张").pack(padx=20, pady=20)
        for i, name in enumerate(files):
            cell = ttk.Frame(grid); cell.grid(row=i // 4, column=i % 4, padx=8, pady=8)
            try:
                im = Image.open(os.path.join(self.shots_dir, name)); thumb = im.copy(); thumb.thumbnail((160, 110))
                photo = ImageTk.PhotoImage(thumb); win._photos.append(photo)
                tk.Label(cell, image=photo).pack()
            except Exception: pass
            ttk.Label(cell, text=name[5:20], font=("", 8)).pack()
            btns = ttk.Frame(cell); btns.pack()
            ttk.Button(btns, text="钉图", width=6, command=lambda n=name: self.pin_image(Image.open(os.path.join(self.shots_dir, n)))).pack(side="left", padx=1)
            def delete(n=name, cell=cell):
                try: os.remove(os.path.join(self.shots_dir, n))
                except Exception: pass
                cell.destroy(); self.refresh_shots()
            ttk.Button(btns, text="删除", width=6, command=delete).pack(side="left", padx=1)

    def pin_text(self, text):
        win = tk.Toplevel(self); win.overrideredirect(True); win.attributes("-topmost", True); win.geometry("+140+140")
        tk.Label(win, text=text[:2000], bg="#fffbe6", bd=2, relief="solid", justify="left", wraplength=420, padx=8, pady=6).pack()
        ttk.Label(win, text="文字贴图 · 拖动移动 · 双击关闭 · 右键有菜单", background="#fffbe6", foreground="#888888").pack()
        tmenu = tk.Menu(win, tearoff=0)
        tmenu.add_command(label="复制文字", command=lambda: self.clip_set(text))
        tmenu.add_command(label="关闭贴图 (双击也可)", command=win.destroy)
        win.bind("<Button-3>", lambda e: tmenu.tk_popup(e.x_root, e.y_root))
        self._draggable(win); win.bind("<Double-Button-1>", lambda e: win.destroy())
        self._pins.append(win)  # 文字贴图也登记: 「关闭所有贴图/隐藏全部」对它同样生效 (它没有图片, 不进恢复逻辑)
        win.bind("<Destroy>", lambda e: self._pins.remove(win) if e.widget is win and win in self._pins else None)

    # ---------- 系统托盘 (像 Snipaste/PixPin 一样藏在右下角) ----------
    @staticmethod
    def _make_tray_icon():
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([6, 10, 58, 60], radius=8, fill=(30, 144, 255, 255))    # 蓝色底板
        d.rounded_rectangle([16, 20, 48, 52], radius=3, fill=(255, 255, 255, 255))     # 白纸
        d.rounded_rectangle([24, 4, 40, 16], radius=4, fill=(90, 90, 90, 255))         # 夹子
        for yy, xe in ((30, 43), (38, 43), (46, 36)):
            d.line([21, yy, xe, yy], fill=(30, 144, 255, 255), width=3)
        return img

    def _setup_tray(self):
        # 托盘回调在 pystray 自己的线程里触发, 一律排队回主线程执行 (和全局热键同一机制)
        import threading
        try:
            import pystray
        except Exception:
            return  # 没装 pystray 就不启用托盘 (EXE 打包时会装上; 源码运行 pip install pystray)
        try:
            menu = pystray.Menu(
                pystray.MenuItem("显示主窗口", lambda icon, item: self._ui_queue.put(self._show_main), default=True),
                pystray.MenuItem("区域截图", lambda icon, item: self._ui_queue.put(self.snip_region)),
                pystray.MenuItem("截图并复制", lambda icon, item: self._ui_queue.put(self.snip_copy)),
                pystray.MenuItem("截图翻译", lambda icon, item: self._ui_queue.put(self.snip_translate)),
                pystray.MenuItem("贴剪贴板内容", lambda icon, item: self._ui_queue.put(self.pin_clipboard)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出 SnapPaste", lambda icon, item: self._ui_queue.put(self._quit_app)),
            )
            self._tray = pystray.Icon("SnapPaste", self._make_tray_icon(), "SnapPaste 剪贴板工作台", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception:
            self._tray = None

    def _show_main(self):
        self.deiconify(); self.lift()
        try: self.focus_force()
        except Exception: pass

    def _hide_to_tray(self):
        try: self.cfg.set("Config", "SleepTime", self.sleep_var.get() or "80")
        except Exception: pass
        self.save_config(); self.save_records()
        self.withdraw()
        if not self._tray_notified:
            self._tray_notified = True
            try: self._tray.notify("SnapPaste 还在后台运行: 点托盘图标打开主窗口, 右键托盘图标可以退出", "已隐藏到托盘")
            except Exception: pass

    def _quit_app(self):
        try: self.cfg.set("Config", "SleepTime", self.sleep_var.get() or "80")
        except Exception: pass
        self.save_config(); self.save_records()
        if self._tray is not None:
            try: self._tray.stop()
            except Exception: pass
            self._tray = None
        try:
            import keyboard; keyboard.unhook_all()
        except Exception: pass
        self.destroy()

    def on_close(self):
        # 点主窗口的 X: 有托盘就藏到右下角托盘继续后台待命 (热键照常可用), 真正退出走托盘右键菜单
        if self._tray is not None:
            self._hide_to_tray()
        else:
            self._quit_app()

if __name__ == "__main__":
    App().mainloop()
