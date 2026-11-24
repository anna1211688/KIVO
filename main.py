#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPST - 一键复制粘贴 + 截图贴图 (原 SnapPaste, v1.4.15 起改名 SPST)
================================================
由「一键复制粘贴工具」(2012, Delphi 加壳版) 重写、并合入 Snipaste 核心功能而来:
  文字: 多次复制队列 / 顺序·全部粘贴 / 分割·正则 / 大小写 / 搜索 / 去重 / 锁定
  图片: F1 区域截图 (窗口吸附·取色) / 标注编辑器 / F3 贴图钉屏 / 历史截图
  识别: OCR / 二维码·条码 (可选引擎 rapidocr-onnxruntime / opencv)
  热键: 7 个动作全部预设可自定义, 保存于 Config.ini, 改键立即生效
v1.3 二次审查修复 (详见 docs/二次审查报告.md):
  搜索过滤下选错记录 / 全局热键跨线程调 Tk / 同秒截图覆盖 / 配置追加重复段 /
  大图编辑器溢出 / 贴图滚轮双倍缩放 / OCR 引擎重复加载 等
依赖: Pillow (截图必需); keyboard (全局热键, 可选); 其余见 requirements.txt
运行: python main.py    打包: build_windows.bat (PyInstaller, 无加壳, 无联网)
"""
import base64, configparser, ctypes, datetime, json, os, queue, re, sys, time
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageGrab, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "SPST 复制粘贴+截图贴图"
# SPST 图标 (256×256 PNG 的 base64 内嵌: 窗口/托盘图标共用, 不依赖外部文件; 源图在 branding/spst_icon_1024.png)
_ICON_PNG_B64 = (
    "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"
)
VERSION = "1.4.15"  # v1.4.15: 正式改名 SPST (标题/托盘/自启项/EXE 名 SPST.exe, 数据目录 %APPDATA%\SPST 并自动搬移旧 SnapPaste 数据); 新图标+logo (SPST 字母融入剪贴板图标, 内嵌窗口/托盘, SPST.ico 作 EXE 图标); 性能优化 (热键队列轮询 60->15ms, 截图干等 300->120ms, 窗口隐藏时不重建列表); 新增「系统设置」窗口 (开机自启/语言/提示音/迷你窗口归拢)
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
# 数据目录: 源码运行时在 main.py 旁; 打成 EXE 后数据统一放 %APPDATA%\SPST,
# 桌面上只剩一个 SPST.exe (v1.4.5 起数据进 AppData; v1.4.15 改名前是 %APPDATA%\SnapPaste, 老数据自动搬移)。
# 注意也不能用 _MEIPASS 临时目录: 那是单文件解压目录, 关程序就全丢 (v1.3.2 审查发现)。
if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE = getattr(sys, "_MEIPASS", EXE_DIR)  # EXE 内置的默认文件 (打包时 --add-data 带入)
    BASE = os.path.join(os.environ.get("APPDATA") or EXE_DIR, "SPST")
    try: os.makedirs(BASE, exist_ok=True)
    except Exception: BASE = EXE_DIR  # AppData 建不了时退回 EXE 旁 (老行为, 至少能用)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
    BUNDLE = BASE
    EXE_DIR = BASE
CONFIG_PATH = os.path.join(BASE, "Config.ini")
RECORDS_PATH = os.path.join(BASE, "records.json")

def _atomic_write(path, text):
    """原子写: 先写临时文件再 os.replace 换名。直接覆盖写时若断电/崩溃, 文件会写一半损坏,
    记录和配置 (含翻译密钥) 就全丢了; 原子写保证磁盘上永远是完整的新版或旧版。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: f.write(text)
    os.replace(tmp, path)

def _migrate_old_data():
    """老数据搬移 (新目录还没有 Config.ini 时才搬, 已存在的文件不覆盖):
    ① 改名前的 %APPDATA%\\SnapPaste (v1.4.15 改名为 SPST) ② 更早的老版本 (<=v1.4.4) 放在 EXE 旁的数据"""
    if not getattr(sys, "frozen", False) or os.path.abspath(BASE) == os.path.abspath(EXE_DIR): return
    if os.path.exists(os.path.join(BASE, "Config.ini")): return  # 新目录已有数据, 不再搬
    import shutil
    def _copy_from(src_dir):
        for rel in ("Config.ini", "records.json", "ding.wav",
                    os.path.join("Language", "Chinese.ini"), os.path.join("Language", "English.ini")):
            src, dst = os.path.join(src_dir, rel), os.path.join(BASE, rel)
            if os.path.exists(src) and not os.path.exists(dst):
                try: os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(src, dst)
                except Exception: pass
        old_shots, new_shots = os.path.join(src_dir, "shots"), os.path.join(BASE, "shots")
        if os.path.isdir(old_shots):
            try:
                os.makedirs(new_shots, exist_ok=True)
                for name in os.listdir(old_shots):
                    s, d = os.path.join(old_shots, name), os.path.join(new_shots, name)
                    if os.path.isfile(s) and not os.path.exists(d):
                        try: shutil.copy(s, d)
                        except Exception: pass
            except Exception: pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        old_base = os.path.join(appdata, "SnapPaste")
        if os.path.abspath(old_base) != os.path.abspath(BASE): _copy_from(old_base)
    _copy_from(EXE_DIR)

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
        try:  # 窗口图标 (标题栏/任务栏) 用内嵌的 SPST 图标
            self._icon_photo = tk.PhotoImage(data=_ICON_PNG_B64); self.iconphoto(True, self._icon_photo)
        except Exception: pass
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
        self.after(15, self._poll_ui_queue)  # 15ms 轮询: 热键动作最多等 15ms 就执行 (旧 60ms 每次按键先白等)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Map>", self._on_main_map)  # 主窗口从托盘恢复显示时, 补刷隐藏期间标脏的列表
        self.bind("<Escape>", lambda e: self.on_close())  # Esc 关闭主窗口 (同点 X: 隐藏到托盘)
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
        try: self.after(15, self._poll_ui_queue)
        except tk.TclError: pass

    def _on_main_map(self, e=None):
        if e is not None and e.widget is not self: return
        if getattr(self, "_list_dirty", False): self.refresh_list()
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
        # 语言文件是程序自带资源而不是用户数据: 优先读 EXE 内置的那份 (BUNDLE), 升级后新文案立刻生效;
        # 早期版本把语言文件释放到数据目录 (AppData) 且从不更新, 旧文件会一直盖住新文案 —— 真机上已经去掉的
        # 「(合并自 Snipaste 核心功能, 需 Pillow)」还一直显示就是这个原因; 数据目录里的只作兜底。
        p = os.path.join(BUNDLE, "Language", f"{self.lang}.ini")
        if not os.path.exists(p): p = os.path.join(BASE, "Language", f"{self.lang}.ini")
        if os.path.exists(p):
            lp = configparser.ConfigParser()
            for enc in ("utf-8-sig", "gbk"):
                try: lp.read(p, encoding=enc); break
                except Exception: continue
            if lp.has_section("UI"): self._strings = dict(lp.items("UI"))
    def t(self, key, zh):
        return self._strings.get(key, zh)
    def save_config(self):
        # 保存配置绝不能把程序搞崩: 整个过程兜底, 失败就静默放弃这次保存 (下次改设置还会再存)
        try: self._save_config_inner()
        except Exception: pass
    def _save_config_inner(self):
        # v1.1 修复: 原地更新已有 key, 保住 Config.ini 里的注释和排版 (旧版 configparser.write 会全抹掉)
        if not os.path.exists(CONFIG_PATH):
            import io
            buf = io.StringIO(); self.cfg.write(buf); _atomic_write(CONFIG_PATH, buf.getvalue())
            return
        raw = open(CONFIG_PATH, "rb").read()
        for enc in ("utf-8-sig", "gbk"):  # 用户手动改过 ini 时可能是 GBK, 读不出就别硬读 (旧版直接抛异常, 设置一保存就报错)
            try: lines = raw.decode(enc).splitlines(); break
            except Exception: lines = []
        else: lines = []
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
                       "Separator", "CustomSep", "SplitChar", "RegexSel", "CaseSel", "TransTarget",
                       "Service", "BaiduAppId", "BaiduKey", "YoudaoAppId", "YoudaoSecret", "GoogleKey", "TransCompare"]}
        for (sec, k), v in pending.items(): by_sec.setdefault(sec, []).append((known_case.get(k, k), v))
        for sec, items in by_sec.items():
            headers = [i for i, ln in enumerate(out) if ln.strip().lower() == f"[{sec.lower()}]"]
            if headers:
                nxt = next((i for i in range(headers[0] + 1, len(out)) if out[i].strip().startswith("[")), len(out))
                out[nxt:nxt] = [f"{k}={v}" for k, v in items]
            else:
                out += [f"[{sec}]"] + [f"{k}={v}" for k, v in items]
        _atomic_write(CONFIG_PATH, "\n".join(out) + "\n")
    @property
    def sleep_ms(self): return max(10, self.cfg.getint("Config", "SleepTime", fallback=80))

    # ---------- UI ----------
    def build_ui(self):
        bar = ttk.Frame(self); bar.pack(fill="x", padx=8, pady=6)
        for txt, cmd in [(self.t("hotkey_settings", "热键设置"), self.open_hotkey_dialog),
                         (self.t("system_settings", "系统设置"), self.open_system_settings),
                         (self.t("import_text", "导入文本"), self.import_txt), (self.t("export_text", "导出文本"), self.export_txt)]:
            ttk.Button(bar, text=txt, command=cmd).pack(side="left", padx=2)
        self.search_var = tk.StringVar(); self.search_var.trace_add("write", lambda *a: self._schedule_search_refresh())
        ttk.Entry(bar, textvariable=self.search_var, width=14).pack(side="right")
        ttk.Label(bar, text=self.t("search", "搜索:")).pack(side="right")
        self.lang_var = tk.StringVar(value=self.lang)  # 语言切换的界面已搬进「系统设置」窗口, 这里只留变量

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
        self.autorun_var = tk.BooleanVar(value=self.cfg.get("Config", "AutoRun", fallback="0") == "1")  # 开机自启的勾选框已搬进「系统设置」
        self.wave_var = tk.BooleanVar(value=self.cfg.get("Wave", "WaveSet", fallback=self.cfg.get("Config", "WaveSet", fallback="0")) == "1")  # 提示音开关 (在系统设置里)
        self.paste_enter_var = tk.BooleanVar(value=self.cfg.get("Config", "PasteEnter", fallback="0") == "1")
        ttk.Checkbutton(opt2, text=self.t("paste_enter", "顺序粘贴后自动回车"), variable=self.paste_enter_var, command=self._toggle_paste_enter).pack(side="left", padx=4)
        self.paste_remove_var = tk.BooleanVar(value=self.cfg.get("Config", "PasteRemove", fallback="1") == "1")
        ttk.Checkbutton(opt2, text=self.t("paste_remove", "顺序粘贴后自动删除该条"), variable=self.paste_remove_var, command=self._toggle_paste_remove).pack(side="left", padx=(10, 0))

        # 迷你窗口的设置界面已搬进「系统设置」窗口, 这里只建变量供各处读写 (改设置走 _save_mini_settings)
        self.mini_time_var = tk.StringVar(value=self.cfg.get("Config", "MiniFormTime", fallback="5"))
        self.mini_always_var = tk.BooleanVar(value=self.cfg.get("Config", "MiniFormSet", fallback="0") == "1")

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

        snip = ttk.LabelFrame(self, text=self.t("snip_frame", "截图贴图"))
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
        ttk.Button(snip3, text="翻译服务", command=self.open_translate_settings).pack(side="left", padx=4)
        self._snip_key_btns = []  # 带热键标注的四个按钮: 标注要跟热键设置同步 (改了键这里跟着变, 设「无」就不带括号)
        for cfg_key, txt, cmd in [("SnipKey", self.t("snip_region", "区域截图 (F1)"), self.snip_region),
                                  ("CopyKey", self.t("snip_copy_btn", "截图并复制 (F5)"), self.snip_copy),
                                  ("TransKey", self.t("snip_trans_btn", "截图翻译 (F4)"), self.snip_translate),
                                  ("PinKey", self.t("pin_clip", "贴剪贴板 (F3)"), self.pin_clipboard)]:
            b = ttk.Button(snip, text=txt, command=cmd); b.pack(side="left", padx=2, pady=4)
            self._snip_key_btns.append((cfg_key, re.sub(r"\s*\([^)]*\)\s*$", "", txt), b))
        for txt, cmd in [(self.t("pin_selected", "钉住选中截图"), self.pin_selected_shot), (self.t("gallery", "历史截图"), self.open_gallery),
                         (self.t("ocr_selected", "OCR 选中截图"), self.ocr_selected_shot), (self.t("open_shots_dir", "打开截图文件夹"), self.open_shots_dir)]:
            ttk.Button(snip, text=txt, command=cmd).pack(side="left", padx=2, pady=4)
        self._refresh_snip_btn_labels()
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
                winreg.SetValueEx(key, "SPST", 0, winreg.REG_SZ, cmd)
                try: winreg.DeleteValue(key, "SnapPaste")  # 清理改名前的自启项, 免得它还指向旧 exe
                except FileNotFoundError: pass
            else:
                for legacy in ("SPST", "SnapPaste"):
                    try: winreg.DeleteValue(key, legacy)
                    except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception: pass
    def _refresh_mini(self):
        """迷你窗口的列表与主列表保持同步 (迷你窗不带搜索过滤, 行号即记录号; 同样分 序号|文本内容 两列)"""
        try:
            if self._mini_win is None or not self._mini_win.winfo_exists() or not hasattr(self, "_mini_list"): return
            if not self._mini_win.winfo_viewable(): return  # 迷你窗藏着时不重建 (show_mini 显示后会专门刷一次)
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
                w.bind("<Escape>", lambda e: self._hide_mini())  # Esc 隐藏迷你窗口
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
            w = self._mini_win; w.deiconify(); w.lift(); self._refresh_mini()  # 先显示再刷: _refresh_mini 对不可见窗口会跳过
            if self._mini_after: self.after_cancel(self._mini_after); self._mini_after = None
            if not always: self._mini_after = self.after(secs * 1000, self._hide_mini)
        except Exception: pass
    def _hide_mini(self):
        self._mini_after = None
        try:
            if self._mini_win is not None: self._mini_win.withdraw()
        except Exception: pass
    def _toggle_wave(self):
        if not self.cfg.has_section("Wave"): self.cfg.add_section("Wave")
        self.cfg.set("Wave", "WaveSet", "1" if self.wave_var.get() else "0")
        self.save_config()
    def open_system_settings(self):
        """系统设置窗口: 开机自启/语言/提示音/迷你窗口从主窗口各处归拢到一起 (用户要求归类), 改完即存, Esc 关闭"""
        if getattr(self, "_sys_win", None) is not None:
            try: self._sys_win.lift(); self._sys_win.focus_set(); return
            except Exception: self._sys_win = None
        win = tk.Toplevel(self); self._sys_win = win
        win.title(self.t("system_settings", "系统设置")); win.resizable(False, False); win.attributes("-topmost", True)
        def close():
            self._sys_win = None; win.destroy()
        win.protocol("WM_DELETE_WINDOW", close); win.bind("<Escape>", lambda e: close())
        frm = ttk.Frame(win); frm.pack(padx=12, pady=10)
        ttk.Checkbutton(frm, text=self.t("autorun", "开机自动运行"), variable=self.autorun_var, command=self._toggle_autorun).pack(anchor="w", pady=3)
        lrow = ttk.Frame(frm); lrow.pack(fill="x", pady=3)
        ttk.Label(lrow, text=self.t("lang_label", "语言:")).pack(side="left")
        lang_box = ttk.Combobox(lrow, textvariable=self.lang_var, width=9, state="readonly", values=["Chinese", "English"])
        lang_box.pack(side="left", padx=4); lang_box.bind("<<ComboboxSelected>>", self._switch_language)
        ttk.Label(lrow, text=self.t("lang_restart_hint", "(重启后生效)"), foreground="#888888").pack(side="left")
        ttk.Checkbutton(frm, text=self.t("wave_sound", "提示音 (复制/粘贴成功时响一声)"), variable=self.wave_var, command=self._toggle_wave).pack(anchor="w", pady=3)
        mfrm = ttk.LabelFrame(frm, text=self.t("mini_frame", "迷你窗口 (复制/粘贴时自动悬浮)")); mfrm.pack(fill="x", pady=(8, 2))
        mrow = ttk.Frame(mfrm); mrow.pack(fill="x", pady=4, padx=4)
        ttk.Label(mrow, text=self.t("mini_time", "悬浮显示时间(秒, 0=不显示):")).pack(side="left")
        me = ttk.Entry(mrow, textvariable=self.mini_time_var, width=5); me.pack(side="left")
        me.bind("<FocusOut>", lambda _e: self._save_mini_settings()); me.bind("<Return>", lambda _e: self._save_mini_settings())
        ttk.Checkbutton(mrow, text=self.t("mini_always", "常显 (不自动隐藏)"), variable=self.mini_always_var, command=self._save_mini_settings).pack(side="left", padx=6)
        ttk.Button(mfrm, text=self.t("mini_show_btn", "立即显示"), command=lambda: self.show_mini()).pack(anchor="w", padx=4, pady=(0, 4))
        ttk.Button(frm, text=self.t("close", "关闭"), command=close).pack(pady=(10, 0))
    def _switch_language(self, _e=None):
        new = self.lang_var.get().strip()
        if new == self.lang: return
        if not self.cfg.has_section("Config"): self.cfg.add_section("Config")
        self.cfg.set("Config", "Language", new); self.save_config()
        messagebox.showinfo(self.t("lang_label", "语言:"), self.t("lang_applied", "语言设置已保存, 重启软件后生效"))

    # ---------- records ----------
    def _schedule_search_refresh(self):
        """搜索框逐字输入防抖 120ms: 记录多时每敲一个字都全量重建列表会明显卡顿"""
        if getattr(self, "_search_after", None):
            try: self.after_cancel(self._search_after)
            except Exception: pass
        self._search_after = self.after(120, self.refresh_list)
    def refresh_list(self):
        q = self.search_var.get().strip()
        self._visible = [i for i, r in enumerate(self.records) if not q or q in r["text"]]  # 可见行映射是纯数据, 先算好 (别的逻辑要用)
        self.status.set(f"{self.t('status_total', '当前记录总数')}: {len(self.records)}  |  {self.t('status_progress', '粘贴进度')}: {self.paste_index}/{len(self.records)}")
        if not self.winfo_viewable():
            # 主窗口没显示 (在托盘里) 时重建上百行列表看不见也用不上, 每次 F6/F7 都白花几十毫秒:
            # 只标脏, 窗口重新显示时由 <Map> 钩子补刷一次
            self._list_dirty = True; self._row_iids = []; self._refresh_mini(); return
        self._list_dirty = False
        self.listbox.delete(*self.listbox.get_children()); self._row_iids = []
        for i in self._visible:
            r = self.records[i]
            prefix = "🔒 " if r["locked"] else ""
            self._row_iids.append(self.listbox.insert("", "end", values=(i + 1, f"{prefix}{r['text'][:120]}")))
        self._refresh_mini()
    def load_records(self):
        # 主文件损坏 (异常退出等) 时回退到上次的备份, 别让整个队列静默清零
        for p in (RECORDS_PATH, RECORDS_PATH + ".bak"):
            if os.path.exists(p):
                try:
                    data = json.loads(open(p, encoding="utf-8").read())
                    if isinstance(data, list): self.records = data; return
                except Exception: continue
        self.records = []
    def save_records(self):
        text = json.dumps(self.records, ensure_ascii=False, indent=1)
        _atomic_write(RECORDS_PATH, text)
        try: _atomic_write(RECORDS_PATH + ".bak", text)  # 同步留一份备份, 供下次启动损坏时回退
        except Exception: pass
    def add_record(self, text, dedupe=True, save=True):
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
        if save: self.save_records()  # 批量场景由调用方最后统一 save 一次, 免得几百行粘贴写几百遍文件卡顿
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
                time.sleep(0.015)
        n = len(self.records)
        text = self.clip_get()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) > 1:
            for ln in lines: self.add_record(ln, save=False)  # v1.3.4: WPS 表格/列表整块复制时按行自动拆成多条; 批量加只在最后存一次盘
            self.save_records()
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
        for p in parts: self.add_record(p, save=False)
        self.save_records(); self.refresh_list()
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
            for ln in lines: self.add_record(ln, save=False)
            self.save_records(); self.refresh_list()
    def export_txt(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("文本", "*.txt")])
        if p:
            with open(p, "w", encoding="utf-8") as f: f.write(self.separator().join(r["text"] for r in self.records))
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
        if not re.fullmatch(r"[a-z0-9_+-]+", s): return None  # 只接受合法键名: 录入中途的「请按键…」等值直接作废, 免得绑定时报错
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
    def _refresh_snip_btn_labels(self):
        """主窗口截图按钮上的 (F1) 标注跟随当前热键设置刷新 (apply_hotkeys 后调用, 启动时也调一次)"""
        for cfg_key, base, btn in getattr(self, "_snip_key_btns", []):
            try:
                hk = self.cfg.get("Snip", cfg_key, fallback=DEFAULT_SNIP_KEYS.get(cfg_key, "无")).strip()
                btn.config(text=base if hk in ("", "无") else f"{base} ({hk})")
            except Exception: pass
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
                try: self.bind(seq, lambda e, f=fn: f()); self._tk_sequences.append(seq)
                except Exception: pass  # 个别键名 Tk 绑不了也不许拖垮整轮热键注册 (全局热键那条路还在)
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
        self._refresh_snip_btn_labels()  # 热键刚按新设置注册完, 主窗口按钮标注同步刷新
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
        win.bind("<Escape>", lambda e: win.destroy())  # Esc 关闭
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
            if f.lower().endswith((".png", ".gif")): self.shots_list.insert("end", f)
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
        """长截图执行 (覆盖层已关闭): 鼠标停在选区中心自动向下滚动, 逐帧抓取拼接; Esc 中止, 画面不再变化自动结束, 完成后打开标注编辑器。
        抓取+拼接放后台线程: 旧版在主线程跑十几秒, 期间界面冻结、热键排队全堵住 (像死机)。"""
        if sys.platform != "win32":
            self._restore_main_after_snip(); self.status.set("长截图目前仅支持 Windows"); return
        import threading
        def work():
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
            img = self._stitch_frames(frames) if frames else None
            def done():
                self._restore_main_after_snip()
                if img is None: return
                self.save_shot(img); self.status.set(f"长截图完成: {img.width}×{img.height}, 已打开编辑器 (可标注/复制/钉图)")
                self.open_editor(img)
            self._ui_queue.put(done)
        threading.Thread(target=work, daemon=True).start()
    def _run_gif_record(self, box, max_seconds=30, fps=8):
        """录制选区为 GIF 动图: 非阻塞逐帧抓取, 屏幕角落有小控制窗 (计时+停止), 结束自动存进截图文件夹。"""
        if not HAS_PIL: return
        rec = {"stop": False, "frames": [], "t0": time.time()}
        ctrl = tk.Toplevel(self); ctrl.overrideredirect(True); ctrl.attributes("-topmost", True)
        lab = tk.Label(ctrl, text="● GIF 录制中 0s", bg="#222222", fg="#FF6666", font=("Microsoft YaHei", 10))
        lab.pack(side="left", padx=6, pady=4)
        tk.Button(ctrl, text="停止", command=lambda: rec.update(stop=True)).pack(side="left", padx=4, pady=4)
        ctrl.bind("<Escape>", lambda e: rec.update(stop=True))  # Esc 停止录制
        ctrl.update_idletasks()
        ctrl.geometry(f"+{max(0, ctrl.winfo_screenwidth() - ctrl.winfo_reqwidth() - 16)}+{max(0, ctrl.winfo_screenheight() - ctrl.winfo_reqheight() - 60)}")
        def finish():
            try: ctrl.destroy()
            except Exception: pass
            self._restore_main_after_snip()
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

    _WM_POS = {"平铺": "tile", "右下角": "br", "左下角": "bl", "右上角": "tr", "左上角": "tl",
               "顶部居中": "tc", "底部居中": "bc", "居中": "center"}
    def _ask_watermark(self, parent, default_color="#FF0000"):
        """水印参数对话框 (仿 PixPin 水印): 文字/位置/不透明度/大小/间距/字体; 点确定返回参数 dict, 取消返回 None"""
        res = {}
        win = tk.Toplevel(parent); win.title("添加水印"); win.attributes("-topmost", True); win.resizable(False, False)
        frm = ttk.Frame(win); frm.pack(padx=12, pady=10)
        ttk.Label(frm, text="水印文字:").grid(row=0, column=0, sticky="e", pady=3)
        txt_var = tk.StringVar()
        ent = ttk.Entry(frm, textvariable=txt_var, width=26); ent.grid(row=0, column=1, pady=3); ent.focus_set()
        ttk.Label(frm, text="位置:").grid(row=1, column=0, sticky="e", pady=3)
        pos_var = tk.StringVar(value="平铺")
        ttk.Combobox(frm, textvariable=pos_var, values=list(self._WM_POS), width=10, state="readonly").grid(row=1, column=1, sticky="w", pady=3)
        ttk.Label(frm, text="不透明度:").grid(row=2, column=0, sticky="e", pady=3)
        opa_var = tk.DoubleVar(value=30); opa_txt = tk.StringVar(value="30%")
        opa_var.trace_add("write", lambda *_: opa_txt.set(f"{int(opa_var.get())}%"))
        srow = ttk.Frame(frm); srow.grid(row=2, column=1, sticky="w", pady=3)
        ttk.Scale(srow, from_=5, to=100, variable=opa_var, length=130).pack(side="left")
        ttk.Label(srow, textvariable=opa_txt, width=4).pack(side="left")
        ttk.Label(frm, text="大小:").grid(row=3, column=0, sticky="e", pady=3)
        size_var = tk.IntVar(value=18)
        ttk.Spinbox(frm, from_=8, to=120, textvariable=size_var, width=6).grid(row=3, column=1, sticky="w", pady=3)
        ttk.Label(frm, text="间距 (平铺):").grid(row=4, column=0, sticky="e", pady=3)
        gap_var = tk.IntVar(value=20)
        ttk.Spinbox(frm, from_=0, to=200, textvariable=gap_var, width=6).grid(row=4, column=1, sticky="w", pady=3)
        ttk.Label(frm, text="字体:").grid(row=5, column=0, sticky="e", pady=3)
        font_var = tk.StringVar(value="微软雅黑")
        ttk.Combobox(frm, textvariable=font_var, values=list(self._FONT_FILES), width=14, state="readonly").grid(row=5, column=1, sticky="w", pady=3)
        ttk.Label(frm, text="颜色用当前标注颜色; 平铺会把水印重复盖满整张图。", foreground="#888888").grid(row=6, column=0, columnspan=2, pady=(4, 0), sticky="w")
        btns = ttk.Frame(win); btns.pack(pady=(2, 10))
        def ok():
            text = txt_var.get().strip()
            if not text: ent.focus_set(); return
            try: size = max(8, min(120, int(size_var.get())))
            except Exception: size = 18
            try: gap = max(0, min(200, int(gap_var.get())))
            except Exception: gap = 20
            res.update(text=text, pos=self._WM_POS.get(pos_var.get(), "tile"),
                       alpha=int(max(5, min(100, opa_var.get())) * 2.55), size=size, gap=gap,
                       font=font_var.get(), color=default_color)
            win.destroy()
        ttk.Button(btns, text="确定", command=ok).pack(side="left", padx=4)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=4)
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Return>", lambda e: ok())
        try: win.grab_set()
        except Exception: pass
        parent.wait_window(win)
        return res or None
    def _choose_color(self, current, parent=None):
        """弹出系统取色器让用户自定义颜色, 返回大写 #RRGGBB; 取消或出错返回 None。"""
        try:
            from tkinter import colorchooser
            _rgb, hexv = colorchooser.askcolor(color=current, title="自定义颜色", parent=parent)
            return hexv.upper() if hexv else None
        except Exception:
            return None
    def _restore_main_after_snip(self):
        """截图结束时把主窗口恢复成截图前的样子, 不许自己弹到最前面。
        旧实现无条件 deiconify: 在别的软件里按热键截图复制完, 主窗口会弹出来挡住正在用的软件 (真机反馈)。
        现在: 截图前藏在托盘里就继续藏着; 截图前露着但不在最前 (人在别的软件里) 就静默放回并沉到后面;
        只有截图前主窗口就在最前 (在主窗口里点的截图按钮) 才照常恢复到前面。"""
        if not getattr(self, "_snip_was_visible", True): return
        self.deiconify()
        if not getattr(self, "_snip_was_foreground", True):
            try: self.lower()
            except Exception: pass
    def snip_region(self):
        if getattr(self, "_snip_active", False): return  # 已有一张截图进行中: 忽略重复触发, 防两层覆盖层/两个全局 Esc 互相打架
        if not HAS_PIL:
            messagebox.showerror("缺少 Pillow", "截图功能需要 Pillow: pip install Pillow"); return
        self._snip_was_visible = self.winfo_viewable() == 1  # 截图前主窗口的状态, 结束时按原样恢复 (见 _restore_main_after_snip)
        self._snip_was_foreground = self._foreground_is_self()
        self.withdraw(); self.update(); time.sleep(0.12)  # 等自家窗口从屏幕上消失再抓屏; 旧值 300ms 纯是干等 (真机反馈迟钝)
        try:
            try: full = ImageGrab.grab(all_screens=True)  # 多显示器抓虚拟桌面 (旧 Pillow 无此参数时回退)
            except TypeError: full = ImageGrab.grab()
            if full.mode != "RGB": full = full.convert("RGB")  # 统一 RGB (抓屏通常已是 RGB, 省掉整图拷贝): 调色板/灰度图取色和标注才不失真
        except Exception as e:
            self._restore_main_after_snip(); messagebox.showerror("截图失败", str(e)); return
        try: ui_mode = int(self.cfg.get("Snip", "UIDetect", fallback="2"))  # UI 检测: 0 不检测 / 1 仅窗口 / 2 检测元素
        except Exception: ui_mode = 2
        top_windows = self._enum_top_windows() if ui_mode else []
        snap_rects = [r for _, r in top_windows]  # Windows 下枚举真实窗口; 其他系统为空, 自动退回自由框选
        hwnd_of = {r: h for h, r in top_windows}
        finish_mode = self._snip_finish_mode; self._snip_finish_mode = None  # 消费本次截图的特殊完成方式
        self._snip_active = True
        sel_win = tk.Toplevel(self); sel_win.attributes("-fullscreen", True); sel_win.attributes("-topmost", True)
        canvas = tk.Canvas(sel_win, cursor="crosshair", highlightthickness=0); canvas.pack(fill="both", expand=True)
        photo = ImageTk.PhotoImage(full); canvas.create_image(0, 0, anchor="nw", image=photo); canvas.image = photo
        state = {"x": 0, "y": 0, "rect": None, "snap": None, "hex": "", "phase": "select",
                 "box": None, "ops": [], "op_items": [], "undone": [], "tool": None,
                 "color": "#FF0000", "width": 3, "drag": None, "tb": None}
        def show_info(e, extra=""):
            _now = time.time()
            if _now - state.get("_info_t", 0) < 0.033: return  # 节流到约 30 帧/秒: 放大镜每帧要裁图+缩放+画网格, 不节流截图时明显发卡
            state["_info_t"] = _now
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
                    final = full.crop(box); self.save_shot(final); close_overlay(); self.translate_image_inplace(final, self.trans_target())
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
            self._restore_main_after_snip()
        # 全局 Esc 兜底: 就算焦点一时没抢过来 (还停在原程序身上), 框选/调整阶段按 Esc 也能退出;
        # 覆盖层销毁时自动注销 (finish/取消/长截图/GIF 所有出口都销毁 sel_win), 不影响平时用 Esc
        state["esc_hk"] = None
        try:
            import keyboard as _kb
            state["esc_hk"] = _kb.add_hotkey("esc", lambda: self._ui_queue.put(close_overlay), suppress=True)
        except Exception: pass
        def _drop_esc_hk(e):
            if e.widget is not sel_win: return
            self._snip_active = False  # 覆盖层销毁 = 本次截图结束, 放行下一次截图 (与摘全局 Esc 同一个销毁钩子, 免得两个 <Destroy> 绑定互相覆盖)
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
            elif t == "watermark":
                # 冻结屏预览: 画布文字没有透明度, 用实色把位置/平铺密度先画出来, 成品再按不透明度渲染
                bw, bh = state["box"][2] - ox, state["box"][3] - oy
                size = int(op.get("size", 18)); gap = int(op.get("gap", 20)); text = op.get("text", "")
                tw = max(10, int(size * 0.92 * len(text))); th = max(8, size); m = max(6, size // 2); spots = []
                pos = op.get("pos", "tile")
                if pos == "tile":
                    yy = 0
                    while yy < bh:
                        xx = 0
                        while xx < bw:
                            spots.append((xx, yy)); xx += tw + max(8, gap * 3)
                        yy += th + max(8, gap * 2)
                elif pos == "br": spots = [(bw - tw - m, bh - th - m)]
                elif pos == "bl": spots = [(m, bh - th - m)]
                elif pos == "tr": spots = [(bw - tw - m, m)]
                elif pos == "tl": spots = [(m, m)]
                elif pos == "tc": spots = [((bw - tw) // 2, m)]
                elif pos == "bc": spots = [((bw - tw) // 2, bh - th - m)]
                else: spots = [((bw - tw) // 2, (bh - th) // 2)]
                for sx, sy in spots[:150]:
                    ids.append(canvas.create_text(sx + ox, sy + oy, anchor="nw", text=text,
                                                  fill=op.get("color", c), font=("Microsoft YaHei", max(8, int(size * 0.75))), tags="op"))
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
            for txt, name in [("矩形", "rect"), ("椭圆", "ellipse"), ("箭头", "arrow"), ("直线", "line"),
                              ("画笔", "pen"), ("文字", "text"), ("序号", "seq"), ("马赛克", "mosaic"), ("模糊", "blur")]:
                b = tk.Button(r1, text=txt, font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2",
                              command=lambda n=name: set_tool(n)); b.pack(side="left", padx=1, pady=2); tool_btns[name] = b
            set_tool("pen")  # 默认画笔 (原「移动」工具已按用户要求去掉, 选区内拖动不再平移选区)
            for cname in ("#FF0000", "#FFD800", "#00B050", "#0070FF", "#000000", "#FFFFFF"):
                tk.Button(r1, bg=cname, width=2, relief="ridge",
                          command=lambda cc=cname: state.update(color=cc)).pack(side="left", padx=1)
            def pick_custom():
                hk = state.get("esc_hk")
                if hk is not None:  # 取色器打开期间先摘掉全局 Esc: 在取色器里按 Esc 取消不该把整个截图也退掉
                    try:
                        import keyboard as _kb; _kb.remove_hotkey(hk)
                    except Exception: pass
                    state["esc_hk"] = None
                picked = self._choose_color(state["color"], sel_win)
                if sel_win.winfo_exists() and state.get("esc_hk") is None:  # 取色器关掉后把全局 Esc 装回去
                    try:
                        import keyboard as _kb
                        state["esc_hk"] = _kb.add_hotkey("esc", lambda: self._ui_queue.put(close_overlay), suppress=True)
                    except Exception: pass
                if picked:
                    state.update(color=picked); custom_btn.configure(bg=picked)
            custom_btn = tk.Button(r1, text="自定义", font=("Microsoft YaHei", 9), relief="ridge", bg="#F2F2F2", command=pick_custom)
            custom_btn.pack(side="left", padx=1)
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
                      command=lambda: self.translate_image_inplace(self.render_ops(full.crop(state["box"]), state["ops"]))).pack(side="left", padx=1)
            def do_watermark():
                hk = state.get("esc_hk")
                if hk is not None:  # 对话框打开期间先摘全局 Esc (同取色器),免得在对话框里按 Esc 把整个截图退掉
                    try:
                        import keyboard as _kb; _kb.remove_hotkey(hk)
                    except Exception: pass
                    state["esc_hk"] = None
                params = self._ask_watermark(sel_win, state["color"])
                if sel_win.winfo_exists() and state.get("esc_hk") is None:
                    try:
                        import keyboard as _kb
                        state["esc_hk"] = _kb.add_hotkey("esc", lambda: self._ui_queue.put(close_overlay), suppress=True)
                    except Exception: pass
                if params:
                    op = {"type": "watermark", "width": state["width"], **params}
                    state["ops"].append(op); state["undone"].clear(); state["op_items"].append(draw_op(op))
            tk.Button(r2, text="水印", font=("Microsoft YaHei", 9), relief="flat", bg="#F2F2F2", command=do_watermark).pack(side="left", padx=1)
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
            adj_menu.add_command(label="翻译图中文字", command=lambda: self.translate_image_inplace(self.render_ops(full.crop(state["box"]), state["ops"])))
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
                try:
                    with Image.open(str(data[0])) as _im: self.pin_image(_im.copy()); return
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
        with Image.open(os.path.join(self.shots_dir, self.shots_list.get(sel[0]))) as _im: self.pin_image(_im.copy())
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
        win.bind("<Escape>", lambda e: win.destroy())  # Esc 关闭贴图 (贴图有焦点时)
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
        menu.add_command(label="翻译图中文字", command=lambda: self.translate_image_inplace(state["img"]))
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
            state["scale"] = min(4, max(0.1, state["scale"] * (1.1 if e.delta > 0 else 0.9)))
            if not state.get("render_pending"):  # 滚轮连发时合并: 每格都整图缩放重绘一次会卡, 攒 40ms 只画最新尺寸
                state["render_pending"] = True
                def _do_render():
                    state["render_pending"] = False
                    try: render()
                    except Exception: pass
                win.after(40, _do_render)
            return "break"
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
            elif t == "watermark":
                text = op.get("text", "")
                if text:
                    size = int(op.get("size", 18)); gap = int(op.get("gap", 20))
                    alpha = max(0, min(255, int(op.get("alpha", 76))))
                    col = op.get("color", "#FF0000")
                    try: rgb = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5))
                    except Exception: rgb = (255, 0, 0)
                    fnt = cls._load_font(size, op.get("font"))
                    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                    od = ImageDraw.Draw(overlay)
                    Wd, Hd = img.size
                    bb = od.textbbox((0, 0), text, font=fnt); tw, th = max(1, bb[2] - bb[0]), max(1, bb[3] - bb[1])
                    pos = op.get("pos", "tile"); m = max(6, size // 2); spots = []
                    if pos == "tile":  # 平铺: 按字宽+间距横竖重复盖满整图
                        yy = 0
                        while yy < Hd:
                            xx = 0
                            while xx < Wd:
                                spots.append((xx, yy)); xx += tw + max(8, gap * 3)
                            yy += th + max(8, gap * 2)
                    elif pos == "br": spots = [(Wd - tw - m, Hd - th - m)]
                    elif pos == "bl": spots = [(m, Hd - th - m)]
                    elif pos == "tr": spots = [(Wd - tw - m, m)]
                    elif pos == "tl": spots = [(m, m)]
                    elif pos == "tc": spots = [((Wd - tw) // 2, m)]
                    elif pos == "bc": spots = [((Wd - tw) // 2, Hd - th - m)]
                    else: spots = [((Wd - tw) // 2, (Hd - th) // 2)]  # 居中
                    for sx, sy in spots: od.text((sx - bb[0], sy - bb[1]), text, font=fnt, fill=rgb + (alpha,))
                    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
                    d = ImageDraw.Draw(img)
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
        def pick_custom_ed():
            picked = self._choose_color(color.get(), win)
            if picked:
                color.set(picked); custom_btn_ed.configure(bg=picked)
        custom_btn_ed = tk.Button(bar, text="自定义", command=pick_custom_ed)
        custom_btn_ed.pack(side="left", padx=1)
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
        def add_watermark():
            params = self._ask_watermark(win, color.get())
            if params:
                ops.append({"type": "watermark", "width": width.get(), **params}); undone.clear(); redraw()
        ttk.Button(btns, text="水印", command=add_watermark).pack(side="left", padx=2)
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
    # 带行坐标的 OCR 脚本 (嵌图翻译用): 每行输出 文字 + 包围盒 (词矩形并集), JSON 一行一个对象
    _WIN_OCR_LINES_PS1 = r"""
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
  $lines = @()
  foreach ($line in $result.Lines) {
    $x1 = 1e9; $y1 = 1e9; $x2 = -1; $y2 = -1
    foreach ($word in $line.Words) {
      $r = $word.BoundingRect
      if ($r.X -lt $x1) { $x1 = $r.X }; if ($r.Y -lt $y1) { $y1 = $r.Y }
      if ($r.X + $r.Width -gt $x2) { $x2 = $r.X + $r.Width }; if ($r.Y + $r.Height -gt $y2) { $y2 = $r.Y + $r.Height }
    }
    if ($x2 -gt $x1) { $lines += [PSCustomObject]@{ t = $line.Text; x = [int]$x1; y = [int]$y1; w = [int]($x2 - $x1); h = [int]($y2 - $y1) } }
  }
  [System.IO.File]::WriteAllText($OutPath, ($lines | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding $false))
} catch {
  [System.IO.File]::WriteAllText($OutPath, ('ERROR: ' + $_.Exception.Message), (New-Object System.Text.UTF8Encoding $false))
}
"""
    @classmethod
    def _ocr_windows_lines(cls, img):
        """Windows 内置 OCR 带行坐标版: 返回 [{'t','x','y','w','h'}...]; 引擎不可用返回 None, 没文字返回 []"""
        if sys.platform != "win32": return None
        import subprocess, tempfile, json as _json
        tmp = tempfile.mkdtemp(prefix="snappaste_ocrl_")
        img_path, out_path, ps_path = (os.path.join(tmp, n) for n in ("in.png", "out.json", "ocrl.ps1"))
        try:
            img.save(img_path)
            with open(ps_path, "w", encoding="utf-8") as f: f.write(cls._WIN_OCR_LINES_PS1)
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path,
                            "-ImgPath", img_path, "-OutPath", out_path],
                           capture_output=True, timeout=30, creationflags=0x08000000)
            if not os.path.exists(out_path): return None
            txt = open(out_path, encoding="utf-8-sig").read().strip()
            if txt.startswith("ERROR:"): return None
            if not txt: return []
            data = _json.loads(txt)
            if isinstance(data, dict): data = [data]  # 只有一行时 ConvertTo-Json 给的是对象不是数组
            out = []
            for d in data:
                t = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", str(d.get("t", ""))).strip()
                if t: out.append({"t": t, "x": int(d["x"]), "y": int(d["y"]), "w": int(d["w"]), "h": int(d["h"])})
            return out
        except Exception:
            return None
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
    @classmethod
    def ocr_lines(cls, img):
        """带行坐标的 OCR (嵌图翻译用): Windows 内置 -> RapidOCR (自带框); 都不可用返回 None"""
        lines = cls._ocr_windows_lines(img)
        if lines is not None: return lines
        try:
            from rapidocr_onnxruntime import RapidOCR
            import numpy as np
            if cls._ocr_engine is None: cls._ocr_engine = RapidOCR()
            result, _ = cls._ocr_engine(np.array(img.convert("RGB")))
            out = []
            for box, text, _score in (result or []):
                xs = [p[0] for p in box]; ys = [p[1] for p in box]
                out.append({"t": text.strip(), "x": int(min(xs)), "y": int(min(ys)),
                            "w": int(max(xs) - min(xs)), "h": int(max(ys) - min(ys))})
            return [o for o in out if o["t"]]
        except ImportError: return None
        except Exception: return []
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
        """识别放后台线程跑: Windows 内置 OCR 要走 PowerShell (一两秒起), 在主线程跑会把整个界面冻住像死机;
        结果排队回主线程再弹窗。"""
        import threading
        def work():
            res = self.ocr_image(img) if kind == "ocr" else self.decode_codes(img)
            self._ui_queue.put(lambda: self._show_recognize_result(kind, res))
        threading.Thread(target=work, daemon=True).start()
    def _show_recognize_result(self, kind, res):
        if kind == "ocr":
            if res is None:
                hint = ("OCR 用的是 Windows 自带识别引擎, 现在不可用, 多半是系统没装中文语言包:\n"
                        "到 Windows「设置 → 时间和语言 → 语言和区域」添加「中文(简体)」, 装好后重启本软件再试。") \
                    if getattr(sys, "frozen", False) else \
                    ("还没装 OCR 引擎, 装一次即可 (离线可用):\n\npip install rapidocr-onnxruntime\n\n或装 Tesseract 程序 + pip install pytesseract")
                messagebox.showinfo("OCR 未启用", hint); return
            self.show_text_result("OCR 识别结果", res or "(没识别到文字, 换个更清晰的截图试试)", translate=True)
        else:
            if res is None:
                messagebox.showinfo("扫码未启用", "还没装扫码引擎, 装一次即可:\n\npip install opencv-python-headless"); return
            self.show_text_result("扫码结果", "\n".join(res) if res else "(没扫到二维码/条码)")
    # ---------- 截图翻译: OCR 出的文字自动英<->中互译 ----------
    def translate_text(self, text):
        """把文字在 英文<->简体中文 间翻译 (含汉字则译成英文, 否则译成中文)。
        优先用设置里配置的翻译服务 (百度/有道, 自备密钥), 否则用免费在线接口; 全部失败返回 None。"""
        text = (text or "").strip()
        if not text: return ""
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)
        return self.translate_text_to(text, "en" if has_cjk else "zh-CN")
    # ---------- 翻译服务接口 (像 PixPin 一样可填自己的 APP ID/密钥) ----------
    def _trans_cfg(self):
        g = lambda k, d="": (self.cfg.get("Translate", k, fallback=d) or d).strip()
        svc = g("Service", "free") or "free"
        return {"service": svc if svc in ("free", "baidu", "youdao", "google") else "free",
                "baidu_id": g("BaiduAppId"), "baidu_key": g("BaiduKey"),
                "youdao_id": g("YoudaoAppId"), "youdao_secret": g("YoudaoSecret"),
                "google_key": g("GoogleKey")}
    @staticmethod
    def _baidu_translate(q, target, appid, key):
        """百度翻译开放平台: sign = md5(appid+q+salt+密钥), 成功返回译文, 出错抛异常 (带错误码)。"""
        import urllib.request, urllib.parse, json as _json, hashlib, random
        salt = str(random.randint(10000, 99999))
        sign = hashlib.md5((appid + q + salt + key).encode("utf-8")).hexdigest()
        url = "https://fanyi-api.baidu.com/api/trans/vip/translate?" + urllib.parse.urlencode(
            {"q": q, "from": "auto", "to": "zh" if target == "zh-CN" else "en",
             "appid": appid, "salt": salt, "sign": sign})
        req = urllib.request.Request(url, headers={"User-Agent": "SPST"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = _json.loads(r.read().decode("utf-8"))
        if d.get("error_code"): raise RuntimeError(f"百度翻译错误 {d.get('error_code')}: {d.get('error_msg', '')}")
        return "\n".join(seg.get("dst", "") for seg in d.get("trans_result") or [])
    @staticmethod
    def _youdao_translate(q, target, appkey, secret):
        """有道翻译 (网易智云) v3 签名: sha256(appKey+input+salt+curtime+密钥), 成功返回译文, 出错抛异常。"""
        import urllib.request, urllib.parse, json as _json, hashlib, time as _time, uuid
        salt = str(uuid.uuid4()); curtime = str(int(_time.time()))
        inp = q if len(q) <= 20 else q[:10] + str(len(q)) + q[-10:]  # v3 规则: 长句取首尾各 10 字 + 总长
        sign = hashlib.sha256((appkey + inp + salt + curtime + secret).encode("utf-8")).hexdigest()
        data = urllib.parse.urlencode({"q": q, "from": "auto", "to": "zh-CHS" if target == "zh-CN" else "en",
                                       "appKey": appkey, "salt": salt, "sign": sign,
                                       "signType": "v3", "curtime": curtime}).encode("utf-8")
        req = urllib.request.Request("https://openapi.youdao.com/api", data=data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "SPST"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = _json.loads(r.read().decode("utf-8"))
        if str(d.get("errorCode", "0")) != "0": raise RuntimeError(f"有道翻译错误码 {d.get('errorCode')}")
        return "\n".join(d.get("translation") or [])
    @staticmethod
    def _google_translate(q, target, apikey):
        """谷歌云翻译 API v2 (只需 API 密钥): 成功返回译文 (HTML 实体已还原), 出错抛异常。"""
        import urllib.request, urllib.parse, json as _json, html as _html
        url = "https://translation.googleapis.com/language/translate/v2?key=" + urllib.parse.quote(apikey)
        data = urllib.parse.urlencode({"q": q, "target": target, "format": "text"}).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "SPST"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = _json.loads(r.read().decode("utf-8"))
        if d.get("error"): raise RuntimeError(f"谷歌翻译错误 {d['error'].get('code')}: {d['error'].get('message', '')}")
        trs = (d.get("data") or {}).get("translations") or []
        return _html.unescape(trs[0].get("translatedText", "")) if trs else ""
    def open_translate_settings(self):
        """翻译服务设置窗 (仿 PixPin): 选服务 + 填 APP ID/密钥 + 测试; 密钥只存本机 Config.ini 的 [Translate] 段。"""
        tc = self._trans_cfg()
        names = {"free": "免费接口 (无需密钥)", "baidu": "百度翻译开放平台", "youdao": "有道翻译", "google": "谷歌翻译 (Google Cloud)"}
        creds = {"baidu": [tc["baidu_id"], tc["baidu_key"]], "youdao": [tc["youdao_id"], tc["youdao_secret"]],
                 "google": ["", tc["google_key"]]}
        cur = {"service": tc["service"]}
        win = tk.Toplevel(self); win.title("翻译服务设置"); win.geometry("470x300"); win.attributes("-topmost", True)
        win.bind("<Escape>", lambda e: win.destroy())  # Esc 关闭 (不保存)
        ttk.Label(win, text="翻译服务:").grid(row=0, column=0, sticky="e", padx=8, pady=8)
        svc_var = tk.StringVar(value=names[cur["service"]])
        id_var, key_var = tk.StringVar(), tk.StringVar()
        svc = ttk.Combobox(win, textvariable=svc_var, values=list(names.values()), width=26, state="readonly")
        svc.grid(row=0, column=1, sticky="w", pady=8)
        ttk.Label(win, text="APP ID:").grid(row=1, column=0, sticky="e", padx=8, pady=6)
        id_entry = ttk.Entry(win, textvariable=id_var, width=38); id_entry.grid(row=1, column=1, sticky="w", pady=6)
        ttk.Label(win, text="密钥:").grid(row=2, column=0, sticky="e", padx=8, pady=6)
        key_entry = ttk.Entry(win, textvariable=key_var, width=38, show="*"); key_entry.grid(row=2, column=1, sticky="w", pady=6)
        def load_fields():
            pair = creds.get(cur["service"], ["", ""])
            id_var.set(pair[0]); key_var.set(pair[1])
            # 谷歌只需要 API 密钥 (没有 APP ID); 免费接口两个都不用填
            id_entry.configure(state="normal" if cur["service"] in ("baidu", "youdao") else "disabled")
            key_entry.configure(state="disabled" if cur["service"] == "free" else "normal")
        def on_svc(*_):
            creds[cur["service"]] = [id_var.get().strip(), key_var.get().strip()]  # 先收走当前服务的输入再切换
            cur["service"] = {v: k for k, v in names.items()}[svc_var.get()]
            load_fields()
        svc_var.trace_add("write", on_svc)
        ttk.Label(win, text="百度/有道到各自开放平台免费申请 APP ID 和密钥; 谷歌在 Google Cloud 开通翻译 API 后创建 API 密钥 (只需填密钥栏)。\n密钥只保存在本机, 不上传别处; 没填或接口出错时自动用免费接口翻译。", foreground="#888888").grid(row=3, column=0, columnspan=2, padx=8, pady=4, sticky="w")
        test_var = tk.StringVar()
        ttk.Label(win, textvariable=test_var, foreground="#0070FF", wraplength=440).grid(row=4, column=0, columnspan=2, padx=8, sticky="w")
        btns = ttk.Frame(win); btns.grid(row=5, column=0, columnspan=2, pady=10)
        def do_test():
            creds[cur["service"]] = [id_var.get().strip(), key_var.get().strip()]
            svc_key, pair = cur["service"], creds.get(cur["service"], ["", ""])
            test_var.set("测试中...")
            import threading
            def work():
                try:
                    if svc_key == "baidu":
                        if not all(pair): raise RuntimeError("先填 APP ID 和密钥")
                        r = self._baidu_translate("Hello, nice to meet you.", "zh-CN", pair[0], pair[1])
                    elif svc_key == "youdao":
                        if not all(pair): raise RuntimeError("先填 APP ID 和密钥")
                        r = self._youdao_translate("Hello, nice to meet you.", "zh-CN", pair[0], pair[1])
                    elif svc_key == "google":
                        if not pair[1]: raise RuntimeError("先填 API 密钥")
                        r = self._google_translate("Hello, nice to meet you.", "zh-CN", pair[1])
                    else:
                        r = self.translate_text_to("Hello, nice to meet you.", "zh-CN")
                    msg = f"测试成功: Hello, nice to meet you. → {r}" if r else "测试失败: 没拿到译文"
                except Exception as e:
                    msg = f"测试失败: {e}"
                self._ui_queue.put(lambda: test_var.set(msg))
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(btns, text="测试", command=do_test).pack(side="left", padx=4)
        def do_save():
            creds[cur["service"]] = [id_var.get().strip(), key_var.get().strip()]
            if not self.cfg.has_section("Translate"): self.cfg.add_section("Translate")
            self.cfg.set("Translate", "Service", cur["service"])
            self.cfg.set("Translate", "BaiduAppId", creds["baidu"][0]); self.cfg.set("Translate", "BaiduKey", creds["baidu"][1])
            self.cfg.set("Translate", "YoudaoAppId", creds["youdao"][0]); self.cfg.set("Translate", "YoudaoSecret", creds["youdao"][1])
            self.cfg.set("Translate", "GoogleKey", creds["google"][1])
            self.save_config()
            self.status.set(f"翻译服务已保存: {names[cur['service']]}")
            win.destroy()
        ttk.Button(btns, text="保存", command=do_save).pack(side="left", padx=4)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=4)
        load_fields()
    def trans_target(self):
        """截图翻译的目标语言: [Snip] TransTarget, zh-CN (默认) 或 en, 主窗口可改"""
        v = (self.cfg.get("Snip", "TransTarget", fallback="zh-CN") or "zh-CN").strip()
        return v if v in ("zh-CN", "en") else "zh-CN"
    def translate_text_to(self, text, target):
        """把文字翻译到指定目标语言, 源语言自动检测 (一键截图翻译 F4 用)。
        设置了百度/有道接口时优先用它, 失败自动回退免费接口 (Google 主, MyMemory 备);
        原文已是中文且目标也是中文时原样返回; 全部失败返回 None。"""
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
            req = urllib.request.Request(url, headers={"User-Agent": "SPST"})
            with urllib.request.urlopen(req, timeout=12) as r:
                d = _json.loads(r.read().decode("utf-8"))
            return (d.get("responseData") or {}).get("translatedText") or ""
        def via_api(q):
            tc = self._trans_cfg()
            if tc["service"] == "baidu" and tc["baidu_id"] and tc["baidu_key"]:
                return self._baidu_translate(q, target, tc["baidu_id"], tc["baidu_key"])
            if tc["service"] == "youdao" and tc["youdao_id"] and tc["youdao_secret"]:
                return self._youdao_translate(q, target, tc["youdao_id"], tc["youdao_secret"])
            if tc["service"] == "google" and tc["google_key"]:
                return self._google_translate(q, target, tc["google_key"])
            return ""
        out = []
        for g in groups:
            t = ""
            try: t = via_api(g)
            except Exception: t = ""
            if not t:
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
    _FONT_CACHE = {}
    _FONT_FILES = {"微软雅黑": "msyh.ttc", "微软雅黑 Light": "msyhl.ttc", "宋体": "simsun.ttc", "新宋体": "simsun.ttc",
                   "黑体": "simhei.ttf", "楷体": "simkai.ttf", "仿宋": "simfang.ttf", "等线": "Deng.ttf", "等线 Light": "Dengl.ttf"}
    @classmethod
    def _load_font(cls, size, font_name=None):
        key = (size, font_name)
        if key in cls._FONT_CACHE: return cls._FONT_CACHE[key]
        from PIL import ImageFont
        font = None
        paths = []
        if font_name and font_name in cls._FONT_FILES: paths.append("C:\\Windows\\Fonts\\" + cls._FONT_FILES[font_name])
        paths += [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                  "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
        for path in paths:
            try:
                if os.path.exists(path): font = ImageFont.truetype(path, size); break
            except Exception: pass
        if font is None: font = ImageFont.load_default()
        if len(cls._FONT_CACHE) < 96: cls._FONT_CACHE[key] = font
        return font
    @staticmethod
    def _render_translated(img, lines, translations):
        """有道式嵌图翻译: 每行采样原文底色盖住原文, 再按框高自适应字号把译文写回原位置。"""
        from PIL import ImageDraw
        src = img.convert("RGB"); out = src.copy()
        dr = ImageDraw.Draw(out); px = src.load()
        W, H = out.size
        for ln, tr in zip(lines, translations):
            if not tr: continue
            x, y, w, h = ln["x"], ln["y"], ln["w"], ln["h"]
            if w <= 0 or h <= 0: continue
            pad = max(1, h // 6)
            bx1, by1 = max(0, x - pad), max(0, y - pad // 2)
            bx2, by2 = min(W - 1, x + w + pad), min(H - 1, y + h + pad // 2)
            border = []
            for xx in range(bx1, bx2 + 1, max(1, (bx2 - bx1) // 24)):
                border.append(px[xx, by1]); border.append(px[xx, by2])
            for yy in range(by1, by2 + 1, max(1, (by2 - by1) // 8)):
                border.append(px[bx1, yy]); border.append(px[bx2, yy])
            border.sort()
            bg = border[len(border) // 2] if border else (255, 255, 255)
            dr.rectangle([bx1, by1, bx2, by2], fill=bg)
            lum = (0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]) / 255.0
            fg = (0, 0, 0) if lum >= 0.5 else (255, 255, 255)
            size = max(8, int(h * 0.95)); font = App._load_font(size)
            while size > 8 and dr.textlength(tr, font=font) > w:
                size = max(8, size - 2); font = App._load_font(size)
            dr.text((x, y + max(0, (h - size) // 2)), tr, fill=fg, font=font)
        return out
    def _translate_lines(self, lines, target):
        """逐行翻译 (嵌图翻译用): 纯数字/符号行原样保留; 返回 (译文列表, 是否有任一行译成功)。"""
        translations, any_ok = [], False
        for ln in lines:
            t = ln["t"]
            if not re.search(r"[A-Za-z\u4e00-\u9fff]", t):
                translations.append(t); continue
            r = self.translate_text_to(t, target)
            if r: any_ok = True; translations.append(r)
            else: translations.append(t)
        return translations, any_ok
    def translate_image_inplace(self, img, target=None):
        """有道式截图翻译: OCR 每行文字+位置 -> 逐行翻译 -> 译文绘回原图 -> 弹翻译结果窗 (可切换目标语言/对照开关)。
        拿不到行坐标时回退到原来的纯文字翻译流程。"""
        import threading
        def work():
            lines = self.ocr_lines(img)
            if not lines:
                self.translate_image(img, target); return
            tgt = target
            if tgt is None:
                joined = "".join(l["t"] for l in lines)
                tgt = "en" if any("\u4e00" <= ch <= "\u9fff" for ch in joined) else "zh-CN"
            translations, any_ok = self._translate_lines(lines, tgt)
            if not any_ok:
                self._ui_queue.put(lambda: messagebox.showinfo("截图翻译", "翻译失败: 在线翻译接口没连上, 检查网络后重试。")); return
            self._ui_queue.put(lambda: self.show_translate_compare(img, lines, tgt, translations))
        threading.Thread(target=work, daemon=True).start()
    def show_translate_compare(self, orig, lines, target, translations):
        """截图翻译结果窗 (仿有道): 顶部 检测到源语言 ⇄ 目标语言 (中文/English 可切换, 切换即重新翻译);
        「对照翻译」开 = 原图+译图双语对照, 关 = 只显示译图; 译图可复制/保存/钉图, 译文可复制。"""
        import threading
        joined = "".join(l["t"] for l in lines)
        src_name = "中文" if any("\u4e00" <= ch <= "\u9fff" for ch in joined) else "英语"
        st = {"target": target, "translations": list(translations),
              "img": self._render_translated(orig, lines, translations)}
        win = tk.Toplevel(self); win.title("截图翻译结果"); win.attributes("-topmost", True)
        win.bind("<Escape>", lambda e: win.destroy())  # Esc 关闭结果窗
        try: win.focus_force()
        except Exception: pass
        head = ttk.Frame(win); head.pack(side="top", fill="x", padx=8, pady=6)
        ttk.Label(head, text=f"检测到{src_name}").pack(side="left")
        ttk.Label(head, text=" ⇄ ").pack(side="left")
        tgt_var = tk.StringVar(value="中文" if target == "zh-CN" else "English")
        tgt_combo = ttk.Combobox(head, textvariable=tgt_var, values=["中文", "English"], width=8, state="readonly")
        tgt_combo.pack(side="left")
        compare_var = tk.BooleanVar(value=(self.cfg.get("Snip", "TransCompare", fallback="1") or "1") != "0")
        ttk.Checkbutton(head, text="对照翻译", variable=compare_var).pack(side="left", padx=10)
        busy_var = tk.StringVar(); ttk.Label(head, textvariable=busy_var, foreground="#0070FF").pack(side="left", padx=4)
        bar = ttk.Frame(win); bar.pack(side="bottom", fill="x", padx=8, pady=6)
        body = ttk.Frame(win); body.pack(fill="both", expand=True)
        ow, oh = orig.size
        def layout():
            for c in body.winfo_children(): c.destroy()
            side = ow >= oh
            if compare_var.get():
                scale = min(1.0, 740 / ow, 840 / oh) if side else min(1.0, 760 / ow, 700 / oh)
            else:
                scale = min(1.0, 1480 / ow, 860 / oh)
            def photo(im):
                if scale < 1.0: im = im.resize((max(1, int(ow * scale)), max(1, int(oh * scale))), Image.LANCZOS)
                return ImageTk.PhotoImage(im)
            win._photos = []
            def pane(title, im):
                ph = photo(im); win._photos.append(ph)
                f = ttk.Frame(body)
                ttk.Label(f, text=title).pack()
                tk.Label(f, image=ph).pack()
                return f
            if compare_var.get():
                if side:
                    pane("原图", orig).pack(side="left", padx=6, pady=6)
                    pane("译图", st["img"]).pack(side="left", padx=6, pady=6)
                else:
                    pane("原图", orig).pack(padx=6, pady=6)
                    pane("译图", st["img"]).pack(padx=6, pady=6)
            else:
                pane("译图", st["img"]).pack(padx=6, pady=6)
        def on_compare():
            if not self.cfg.has_section("Snip"): self.cfg.add_section("Snip")
            self.cfg.set("Snip", "TransCompare", "1" if compare_var.get() else "0"); self.save_config()
            layout()
        for wdg in head.winfo_children():
            if isinstance(wdg, ttk.Checkbutton): wdg.configure(command=on_compare)
        def retranslate(*_):
            new_tgt = "zh-CN" if tgt_var.get() == "中文" else "en"
            if new_tgt == st["target"]: return
            tgt_combo.configure(state="disabled"); busy_var.set("翻译中…")
            def work():
                trs, ok = self._translate_lines(lines, new_tgt)
                def done():
                    tgt_combo.configure(state="readonly"); busy_var.set("")
                    if not ok:
                        busy_var.set("翻译失败, 已保留当前译文")
                        tgt_var.set("中文" if st["target"] == "zh-CN" else "English"); return
                    st["target"] = new_tgt; st["translations"] = trs
                    st["img"] = self._render_translated(orig, lines, trs)
                    layout()
                self._ui_queue.put(done)
            threading.Thread(target=work, daemon=True).start()
        tgt_var.trace_add("write", retranslate)
        copy_btn = ttk.Button(bar, text="复制原文")
        def do_copy():
            self.clip_set("\n".join(l["t"] for l in lines))  # 复制识别出的原文本 (用户要求: 不再复制译图, 译图已有保存/钉图)
            copy_btn.config(text="已复制 ✓")
            win.after(1200, lambda: copy_btn.config(text="复制原文"))
        copy_btn.config(command=do_copy); copy_btn.pack(side="left", padx=2)
        ttk.Button(bar, text="保存译图", command=lambda: (self.save_shot(st["img"]), self.status.set("译图已存进历史截图"))).pack(side="left", padx=2)
        ttk.Button(bar, text="钉住译图", command=lambda: self.pin_image(st["img"])).pack(side="left", padx=2)
        ttk.Button(bar, text="复制译文", command=lambda: self.clip_set("\n".join(st["translations"]))).pack(side="left", padx=2)
        ttk.Button(bar, text="关闭", command=win.destroy).pack(side="right", padx=2)
        layout()
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
        win.bind("<Escape>", lambda e: win.destroy())  # Esc 关闭结果窗 (与截图翻译结果窗一致)
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
                if line.strip(): self.add_record(line, save=False); added += 1
            if added: self.save_records()
            self.refresh_list(); messagebox.showinfo("文字队列", f"已加入 {added} 条到文字队列, 之后按 F7 就能逐条粘贴", parent=win)
        ttk.Button(bar, text="加入文字队列 (配合 F7 粘贴)", command=to_queue).pack(side="left", padx=2)
        if translate:
            ttk.Button(bar, text="翻译 (英↔中)", command=lambda: self.translate_and_show(box.get("1.0", "end").strip())).pack(side="left", padx=2)
        ttk.Button(bar, text="关闭", command=win.destroy).pack(side="right", padx=2)
    def ocr_selected_shot(self):
        sel = self.shots_list.curselection() if hasattr(self, "shots_list") else ()
        if not sel or not HAS_PIL: messagebox.showinfo("OCR", "先在截图列表里选一张"); return
        with Image.open(os.path.join(self.shots_dir, self.shots_list.get(sel[0]))) as _im: self.recognize(_im.copy(), "ocr")

    def _pin_file(self, name):
        """从历史文件钉图: 打开后立刻复制一份并关文件, 不让文件句柄一直挂在贴图上"""
        with Image.open(os.path.join(self.shots_dir, name)) as _im: self.pin_image(_im.copy())
    # ---------- 截图历史画廊 (v1.2) ----------
    def open_gallery(self):
        if not HAS_PIL: return
        win = tk.Toplevel(self); win.title("历史截图"); win.geometry("760x500")
        win.bind("<Escape>", lambda e: win.destroy())  # Esc 关闭
        def shot_files():
            try: return [f for f in sorted(os.listdir(self.shots_dir), reverse=True)
                         if f.lower().endswith((".png", ".gif"))]
            except Exception: return []
        bar = ttk.Frame(win); bar.pack(fill="x", padx=8, pady=6)
        count_var = tk.StringVar(); ttk.Label(bar, textvariable=count_var).pack(side="left")
        outer = ttk.Frame(win); outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer); sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        grid = ttk.Frame(canvas); grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=grid, anchor="nw"); canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        win._photos = []
        def render():
            for c in grid.winfo_children(): c.destroy()
            win._photos = []
            all_files = shot_files()
            files = all_files[:60]  # 只展示最近 60 个, 防几百个时全量解码卡顿
            count_var.set(f"共 {len(all_files)} 个" + (" (只显示最近 60 个)" if len(all_files) > 60 else ""))
            if not files:
                ttk.Label(grid, text="还没有截图, 先按 F1 截一张").pack(padx=20, pady=20); return
            for i, name in enumerate(files):
                cell = ttk.Frame(grid); cell.grid(row=i // 4, column=i % 4, padx=8, pady=8)
                try:
                    im = Image.open(os.path.join(self.shots_dir, name)); thumb = im.copy(); thumb.thumbnail((160, 110))
                    photo = ImageTk.PhotoImage(thumb); win._photos.append(photo)
                    tk.Label(cell, image=photo).pack()
                except Exception: pass
                label = ("GIF " if name.lower().endswith(".gif") else "") + (name[5:20] if name.startswith("shot_") else name[4:19])
                ttk.Label(cell, text=label, font=("", 8)).pack()
                btns = ttk.Frame(cell); btns.pack()
                ttk.Button(btns, text="钉图", width=6, command=lambda n=name: self._pin_file(n)).pack(side="left", padx=1)
                def delete(n=name, cell=cell):
                    try: os.remove(os.path.join(self.shots_dir, n))
                    except Exception: pass
                    cell.destroy(); self.refresh_shots(); render()
                ttk.Button(btns, text="删除", width=6, command=delete).pack(side="left", padx=1)
        def delete_all():
            files = shot_files()
            if not files:
                messagebox.showinfo("历史截图", "没有可删除的历史截图。", parent=win); return
            if not messagebox.askyesno("删除全部", f"确定要删除全部 {len(files)} 个历史截图/录制文件吗? 删除后不能恢复。", parent=win): return
            n = 0
            for f in files:
                try: os.remove(os.path.join(self.shots_dir, f)); n += 1
                except Exception: pass
            self.refresh_shots(); render()
            self.status.set(f"已删除全部历史截图 ({n} 个)")
        ttk.Button(bar, text="删除全部", command=delete_all).pack(side="right")
        render()

    def pin_text(self, text):
        win = tk.Toplevel(self); win.overrideredirect(True); win.attributes("-topmost", True); win.geometry("+140+140")
        win.bind("<Escape>", lambda e: win.destroy())  # Esc 关闭贴图 (贴图有焦点时)
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
        try:  # 优先用内嵌的新图标 (与 EXE 图标同一张图)
            import io
            return Image.open(io.BytesIO(base64.b64decode(_ICON_PNG_B64))).convert("RGBA")
        except Exception: pass
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
                pystray.MenuItem("退出 SPST", lambda icon, item: self._ui_queue.put(self._quit_app)),
            )
            self._tray = pystray.Icon("SPST", self._make_tray_icon(), "SPST 剪贴板工作台", menu)
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
            try: self._tray.notify("SPST 还在后台运行: 点托盘图标打开主窗口, 右键托盘图标可以退出", "已隐藏到托盘")
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
