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
VERSION = "1.3.4"  # v1.3.4: F6 多行内容按行自动拆条 (WPS 表格/列表) + v1.3.3 的 Ctrl+C/V 真机修复
MAX_RECORDS = 2000  # 记录上限: 超出时自动丢弃最旧的未锁定记录, 防 records.json 无限膨胀
# 开箱即用预设热键: 用户不用自己设置, 打开就能用; 想改再去「热键设置」
DEFAULT_HOTKEYS = {"HotKey8": "F6", "HotKey9": "F7", "HotKey10": "F8",
                   "HotKey11": "F9", "HotKey12": "SHIFT+F9"}
# Snipaste 习惯键: F1 截图 / F3 贴图, 放在 Config.ini [Snip] 段
DEFAULT_SNIP_KEYS = {"SnipKey": "F1", "PinKey": "F3"}
# 数据目录: 源码运行时在 main.py 旁; 打成 EXE (PyInstaller) 后必须在 EXE 旁,
# 否则 Config/records/shots 会写进单文件解压的临时目录, 关程序就全丢 (v1.3.2 审查发现)
if getattr(sys, "frozen", False):
    BASE = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE = getattr(sys, "_MEIPASS", BASE)  # EXE 内置的默认文件 (打包时 --add-data 带入)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
    BUNDLE = BASE
CONFIG_PATH = os.path.join(BASE, "Config.ini")
RECORDS_PATH = os.path.join(BASE, "records.json")

def ensure_runtime_files():
    """EXE 首次运行: 把内置的默认 Config.ini / ding.wav / Language 释放到 EXE 旁; 已存在的不覆盖"""
    import shutil
    for rel in ("Config.ini", "ding.wav", os.path.join("Language", "Chinese.ini")):
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
        self.paste_index = 0
        self._hk_handles = []      # keyboard 包返回的句柄, 改热键时注销旧的
        self._tk_sequences = []    # 窗口内绑定的序列, 改热键时解绑旧的
        self.cfg = self.load_config()
        self.build_ui()
        self.load_records()
        self.refresh_list()
        self.refresh_shots()
        self.apply_hotkeys()
        self.after(60, self._poll_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
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
        c.read_dict({"Config": {"SleepTime": "80", "WaveSet": "0", "AutoRun": "0",
                                "MiniFormTime": "5", "AddChar": "1", "LetterSet": "0"},
                     "HotKey": defaults, "Snip": dict(DEFAULT_SNIP_KEYS)})
        if os.path.exists(CONFIG_PATH):
            # 原版是 GBK, 新版是 UTF-8: 依次尝试, 不再乱码
            for enc in ("utf-8-sig", "gbk"):
                try: c.read(CONFIG_PATH, encoding=enc); break
                except Exception: continue
        return c
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
                      ["SleepTime", "WaveSet", "WaveFile", "AutoRun", "AutoSet", "MiniFormTime", "MiniFormSet",
                       "SplitPos", "AddChar", "LetterSet", "HotKey", "OCAutoSet", "Form1XY", "Form2XY"]}
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
        for txt, cmd in [("加载配置", self.reload), ("保存配置", self.save_config),
                         ("热键设置", self.open_hotkey_dialog),
                         ("导入文本", self.import_txt), ("导出文本", self.export_txt)]:
            ttk.Button(bar, text=txt, command=cmd).pack(side="left", padx=2)
        self.search_var = tk.StringVar(); self.search_var.trace_add("write", lambda *a: self.refresh_list())
        ttk.Entry(bar, textvariable=self.search_var, width=18).pack(side="right")
        ttk.Label(bar, text="搜索:").pack(side="right")

        mid = ttk.Frame(self); mid.pack(fill="both", expand=True, padx=8)
        self.listbox = tk.Listbox(mid, activestyle="dotbox")
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, command=self.listbox.yview); sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=sb.set)
        ops = ttk.Frame(mid); ops.pack(side="left", fill="y", padx=6)
        for txt, cmd in [("锁定/解锁", self.toggle_lock), ("删除选定", self.delete_sel),
                         ("删除全部", self.delete_all), ("上移", lambda: self.move(-1)),
                         ("下移", lambda: self.move(1)), ("去重", self.dedupe)]:
            ttk.Button(ops, text=txt, command=cmd).pack(fill="x", pady=2)

        opt = ttk.LabelFrame(self, text="粘贴选项"); opt.pack(fill="x", padx=8, pady=6)
        self.sep_var = tk.StringVar(value="enter")
        for txt, val in [("记录间回车", "enter"), ("记录间 TAB", "tab"), ("无分隔", "none")]:
            ttk.Radiobutton(opt, text=txt, variable=self.sep_var, value=val).pack(side="left", padx=4)
        ttk.Label(opt, text="自定义:").pack(side="left"); self.custom_sep = ttk.Entry(opt, width=6); self.custom_sep.pack(side="left")
        ttk.Label(opt, text="间隔(ms):").pack(side="left", padx=(10,0))
        self.sleep_var = tk.StringVar(value=str(self.sleep_ms))
        ttk.Entry(opt, textvariable=self.sleep_var, width=6).pack(side="left")

        act = ttk.Frame(self); act.pack(fill="x", padx=8, pady=4)
        for txt, cmd in [("多次复制 (加入队列)", self.multi_copy), ("顺序粘贴下一条", self.paste_next),
                         ("全部粘贴", self.paste_all), ("强力粘贴选定", self.paste_selected)]:
            ttk.Button(act, text=txt, command=cmd).pack(side="left", padx=2)

        split = ttk.LabelFrame(self, text="剪切/复制时分割 (可选)"); split.pack(fill="x", padx=8, pady=6)
        ttk.Label(split, text="分割字符:").pack(side="left"); self.split_entry = ttk.Entry(split, width=8); self.split_entry.pack(side="left")
        self.regex_var = tk.StringVar(value="")
        ttk.Combobox(split, textvariable=self.regex_var, width=14, values=["", "所有数字", "所有小写字母", "所有大写字母", "回车符", "制表符"]).pack(side="left", padx=4)
        self.case_var = tk.StringVar(value="")
        ttk.Combobox(split, textvariable=self.case_var, width=10, values=["", "转大写", "转小写"]).pack(side="left", padx=4)
        ttk.Button(split, text="按分割导入剪贴板", command=self.import_clipboard_split).pack(side="left", padx=4)

        snip = ttk.LabelFrame(self, text="截图贴图 (合并自 Snipaste 核心功能, 需 Pillow)")
        snip.pack(fill="x", padx=8, pady=6)
        for txt, cmd in [("区域截图 (F1)", self.snip_region), ("贴剪贴板 (F3)", self.pin_clipboard),
                         ("钉住选中截图", self.pin_selected_shot), ("历史画廊", self.open_gallery),
                         ("OCR 选中截图", self.ocr_selected_shot), ("打开截图文件夹", self.open_shots_dir)]:
            ttk.Button(snip, text=txt, command=cmd).pack(side="left", padx=2, pady=4)
        self.shots_list = tk.Listbox(snip, height=3); self.shots_list.pack(side="left", fill="x", expand=True, padx=6, pady=4)
        self.shots_list.bind("<<ListboxSelect>>", self.preview_shot)
        self.shot_preview = tk.Label(snip, text="(选中截图\n看预览)", fg="gray"); self.shot_preview.pack(side="left", padx=4)

        self.status = tk.StringVar(value="就绪")
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x", padx=8, pady=4)
        self.bind("<Delete>", lambda e: self.delete_sel())

    # ---------- records ----------
    def refresh_list(self):
        q = self.search_var.get().strip(); self.listbox.delete(0, "end"); self._visible = []
        for i, r in enumerate(self.records):
            if q and q not in r["text"]: continue
            self._visible.append(i)
            prefix = "🔒 " if r["locked"] else ""
            self.listbox.insert("end", f"{i+1}. {prefix}{r['text'][:120]}")
        self.status.set(f"当前记录总数: {len(self.records)}  |  粘贴进度: {self.paste_index}/{len(self.records)}")
    def load_records(self):
        if os.path.exists(RECORDS_PATH):
            try: self.records = json.loads(open(RECORDS_PATH, encoding="utf-8").read())
            except Exception: self.records = []
    def save_records(self):
        with open(RECORDS_PATH, "w", encoding="utf-8") as f: json.dump(self.records, f, ensure_ascii=False, indent=1)
    def add_record(self, text, dedupe=True):
        text = text.strip("\r\n")
        if not text: return
        if self.case_var.get() == "转大写": text = text.upper()
        if self.case_var.get() == "转小写": text = text.lower()
        if dedupe and any(r["text"] == text for r in self.records): return
        self.records.append({"text": text, "locked": False})
        while len(self.records) > MAX_RECORDS:  # 上限保护: 丢最旧的未锁定记录 (刚加的和锁定的不动)
            idx = next((i for i, r in enumerate(self.records[:-1]) if not r["locked"]), None)
            if idx is None: break
            del self.records[idx]
        self.save_records()
    def selected_idx(self):
        """列表框选中的是第几条 records (经搜索过滤映射); 没选返回 -1"""
        s = self.listbox.curselection()
        if not s or s[0] >= len(self._visible): return -1
        return self._visible[s[0]]
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
            if j in self._visible: self.listbox.selection_set(self._visible.index(j))
    def dedupe(self):
        seen, out = set(), []
        for r in self.records:
            if r["text"] not in seen: seen.add(r["text"]); out.append(r)
        self.records = out; self.save_records(); self.refresh_list()

    # ---------- clipboard ----------
    def clip_get(self):
        try: return self.clipboard_get()
        except tk.TclError: return ""
    def clip_set(self, text):
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
    def _send_combo(self, vk_key):
        """向当前前台窗口发送 Ctrl+<vk_key> (0x43=复制 / 0x56=粘贴); SendInput -> keybd_event -> keyboard 三层兜底"""
        if sys.platform == "win32":
            VK_CONTROL, KEYUP = 0x11, 0x0002
            try:
                def ev(vk, up=False):
                    i = _INPUT(); i.type = 1; i.u.ki.wVk = vk; i.u.ki.dwFlags = KEYUP if up else 0; return i
                seq = (_INPUT * 4)(ev(VK_CONTROL), ev(vk_key), ev(vk_key, True), ev(VK_CONTROL, True))
                if ctypes.windll.user32.SendInput(4, seq, ctypes.sizeof(_INPUT)) == 4: return True
            except Exception: pass
            try:
                u = ctypes.windll.user32
                u.keybd_event(VK_CONTROL, 0, 0, 0); u.keybd_event(vk_key, 0, 0, 0)
                u.keybd_event(vk_key, 0, KEYUP, 0); u.keybd_event(VK_CONTROL, 0, KEYUP, 0)
                return True
            except Exception: pass
        try:
            import keyboard; keyboard.send("ctrl+c" if vk_key == 0x43 else "ctrl+v"); return True
        except Exception: return False
    def _clip_sequence(self):
        if sys.platform == "win32":
            try: return ctypes.windll.user32.GetClipboardSequenceNumber()
            except Exception: pass
        return None
    def multi_copy(self):
        before_seq, before_text = self._clip_sequence(), None
        if not self._foreground_is_self():
            before_text = self.clip_get()
            self._send_combo(0x43)  # 替用户在当前软件里按 Ctrl+C
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
        if len(self.records) > n: self.beep()  # 真入队了才响, 没选中文字时不假响
        self.refresh_list()
    def _paste_text(self, text):
        self.clip_set(text)
        if not self._foreground_is_self():
            time.sleep(0.03); self._send_combo(0x56)  # Ctrl+V: 真的粘进目标窗口, 不只是放剪贴板
        self.beep()
    def paste_next(self):
        if not self.records: return
        if self.paste_index >= len(self.records): self.paste_index = 0
        text = self.records[self.paste_index]["text"]; self.paste_index += 1
        self._paste_text(text); self.refresh_list()
    def paste_all(self):
        if not self.records: return
        self._paste_text(self.separator().join(r["text"] for r in self.records))
    def paste_selected(self):
        i = self.selected_idx()
        if i >= 0:
            time.sleep(self.sleep_ms / 1000); self.clip_set(self.records[i]["text"]); self.beep()
    def import_clipboard_split(self):
        text = self.clip_get()
        if not text: return
        pattern = {"所有数字": r"\d+", "所有小写字母": r"[a-z]+", "所有大写字母": r"[A-Z]+",
                   "回车符": None, "制表符": None}.get(self.regex_var.get(), None)
        if self.regex_var.get() in ("回车符",): parts = text.splitlines()
        elif self.regex_var.get() in ("制表符",): parts = text.split("\t")
        elif pattern: parts = re.findall(pattern, text)
        elif self.split_entry.get(): parts = text.split(self.split_entry.get())
        else: parts = [text]
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
    def reload(self):
        self.cfg = self.load_config(); self.sleep_var.set(str(self.sleep_ms)); self.apply_hotkeys(); self.refresh_list()
    def delete_last(self):
        for i in range(len(self.records) - 1, -1, -1):
            if not self.records[i]["locked"]:
                del self.records[i]
                if i < self.paste_index: self.paste_index -= 1
                break
        self.save_records(); self.refresh_list()

    # ---------- 自定义热键 ----------
    # Config.ini [HotKey] 字段 -> (显示名, 动作). 用户在「热键设置」里改, 也可直接改 ini 后点「加载配置」。
    def hotkey_actions(self):
        # (section, key, 显示名, 动作)
        return [("HotKey", "HotKey8", "多次复制", self.multi_copy), ("HotKey", "HotKey9", "顺序粘贴", self.paste_next),
                ("HotKey", "HotKey10", "全部粘贴", self.paste_all), ("HotKey", "HotKey11", "删除最后一条", self.delete_last),
                ("HotKey", "HotKey12", "删除全部记录", self.delete_all),
                ("Snip", "SnipKey", "区域截图", self.snip_region), ("Snip", "PinKey", "贴剪贴板", self.pin_clipboard)]
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
                try: self._hk_handles.append(keyboard.add_hotkey(hk, lambda f=fn: self._ui_queue.put(f))); global_ok = True
                except Exception: pass
        scope = "全局热键" if global_ok else "窗口内热键 (装 keyboard 包后可全局)"
        self.status.set(f"{scope}已启用: " + (" / ".join(labels) if labels else "未设置, 点「热键设置」添加"))
    def open_hotkey_dialog(self):
        win = tk.Toplevel(self); win.title("热键设置"); win.geometry("430x380"); win.transient(self); win.grab_set()
        ttk.Label(win, text="点「录入」后直接按下组合键 (如 Ctrl+Alt+V), 或手动输入。\n留空或填「无」= 不启用该热键。避开 F1(帮助)/F2(重命名) 和 Ctrl+C/V 等系统键。").pack(padx=10, pady=8, anchor="w")
        vars_ = {}
        for section, cfg_key, label, _fn in self.hotkey_actions():
            row = ttk.Frame(win); row.pack(fill="x", padx=10, pady=3)
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
            seen = {}
            for (section, cfg_key), var in vars_.items():
                hk = self.normalize_hotkey(var.get())
                if hk and hk in seen:
                    messagebox.showerror("热键设置", "热键设置重复，请重新设置！", parent=win); return
                if hk: seen[hk] = cfg_key
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
        path = os.path.join(self.shots_dir, name); img.save(path); self.refresh_shots(); return path
    def open_shots_dir(self):
        if sys.platform == "win32": os.startfile(self.shots_dir)  # noqa: S606
        else: messagebox.showinfo("截图文件夹", self.shots_dir)
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
        snap_rects = self.list_window_rects()  # Windows 下枚举真实窗口; 其他系统为空, 自动退回自由框选
        sel_win = tk.Toplevel(self); sel_win.attributes("-fullscreen", True); sel_win.attributes("-topmost", True)
        canvas = tk.Canvas(sel_win, cursor="crosshair", highlightthickness=0); canvas.pack(fill="both", expand=True)
        photo = ImageTk.PhotoImage(full); canvas.create_image(0, 0, anchor="nw", image=photo); canvas.image = photo
        state = {"x": 0, "y": 0, "rect": None, "snap": None}
        def show_info(e, extra=""):
            canvas.delete("info")
            if snap_rects and not (e.state & 0x0100):  # 没按住鼠标时: 吸附高亮鼠标所在窗口 (单击即截整窗)
                snap = self.pick_window(e.x, e.y, snap_rects); state["snap"] = snap
                canvas.delete("snap")
                if snap: canvas.create_rectangle(*snap, outline="yellow", width=2, dash=(6, 3), tags="snap")
            try: r, g, b = full.getpixel((e.x, e.y))[:3]; color = f"#{r:02X}{g:02X}{b:02X} RGB({r},{g},{b})"
            except Exception: color = ""
            canvas.create_text(10, 10, anchor="nw", tags="info", fill="yellow",
                               font=("Consolas", 12, "bold"), text=f"({e.x},{e.y}) {color} {extra}")
        def down(e): state.update(x=e.x, y=e.y); canvas.delete("snap"); show_info(e)
        def drag(e):
            if state["rect"]: canvas.delete(state["rect"])
            state["rect"] = canvas.create_rectangle(state["x"], state["y"], e.x, e.y, outline="red", width=2)
            show_info(e, f"| 选区 {abs(e.x-state['x'])}x{abs(e.y-state['y'])}")
        canvas.bind("<Motion>", show_info)
        def up(e):
            box = (min(state["x"], e.x), min(state["y"], e.y), max(state["x"], e.x), max(state["y"], e.y))
            if box[2] - box[0] <= 5 and box[3] - box[1] <= 5 and state.get("snap"): box = tuple(state["snap"])
            sel_win.destroy(); self.deiconify()
            if box[2] - box[0] > 5 and box[3] - box[1] > 5:
                self.open_editor(full.crop(box))
        canvas.bind("<ButtonPress-1>", down); canvas.bind("<B1-Motion>", drag); canvas.bind("<ButtonRelease-1>", up)
        sel_win.bind("<Escape>", lambda e: (sel_win.destroy(), self.deiconify()))
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
    def pin_image(self, img):
        win = tk.Toplevel(self); win.overrideredirect(True); win.attributes("-topmost", True)
        win.geometry("+120+120"); state = {"img": img.copy(), "scale": 1.0, "photo": None}
        label = tk.Label(win, bd=2, relief="solid"); label.pack()
        def render():
            w, h = state["img"].size; nw, nh = max(20, int(w * state["scale"])), max(20, int(h * state["scale"]))
            state["photo"] = ImageTk.PhotoImage(state["img"].resize((nw, nh), Image.LANCZOS)); label.config(image=state["photo"])
        render()
        menu = tk.Menu(win, tearoff=0)
        menu.add_command(label="标注这张图", command=lambda: (win.destroy(), self.open_editor(state["img"])))
        menu.add_command(label="OCR 识别这张图", command=lambda: self.recognize(state["img"], "ocr"))
        menu.add_command(label="扫这张图的码", command=lambda: self.recognize(state["img"], "code"))
        menu.add_command(label="旋转 90°", command=lambda: (state.update(img=state["img"].rotate(-90, expand=True)), render()))
        alpha = tk.Menu(menu, tearoff=0)
        for pct in (100, 80, 60, 40):
            alpha.add_command(label=f"不透明度 {pct}%", command=lambda a=pct/100: win.attributes("-alpha", a))
        menu.add_cascade(label="透明度", menu=alpha)
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
        hint = ttk.Label(win, text="拖动移动 · 滚轮缩放 · 双击关闭 · 右键保存"); hint.pack(); hint.bind("<MouseWheel>", on_wheel)
        self._draggable(win)  # 最后绑, 覆盖子控件的按下事件为拖动 (根坐标计算, 不受子控件位置影响)
    def _save_as(self, img):
        p = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if p: img.save(p)
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
        ops, state = [], {"start": None, "points": [], "temp": None}
        bar = ttk.Frame(win); bar.pack(fill="x", padx=6, pady=4)
        for txt, val in [("矩形", "rect"), ("椭圆", "ellipse"), ("箭头", "arrow"), ("直线", "line"),
                         ("画笔", "pen"), ("文字", "text"), ("马赛克", "mosaic"), ("模糊", "blur")]:
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
                if txt: ops.append({"type": "text", "at": state["start"], "text": txt, "color": color.get(), "width": width.get()}); redraw()
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
            if t == "pen": ops.append({"type": "pen", "points": list(state["points"]), "color": color.get(), "width": width.get()})
            elif t in ("rect", "ellipse", "arrow", "line", "mosaic", "blur"):
                ops.append({"type": t, "box": (min(x1, ex), min(y1, ey), max(x1, ex), max(y1, ey)) if t in ("rect", "ellipse", "mosaic", "blur") else (x1, y1, ex, ey),
                            "color": color.get(), "width": width.get()})
            state["start"] = None; state["temp"] = None; redraw()
        canvas.bind("<ButtonPress-1>", down); canvas.bind("<B1-Motion>", drag); canvas.bind("<ButtonRelease-1>", up)
        btns = ttk.Frame(win); btns.pack(fill="x", padx=6, pady=6)
        ttk.Button(btns, text="撤销", command=lambda: (ops.pop() if ops else None, redraw())).pack(side="left", padx=2)
        ttk.Button(btns, text="OCR 识别文字", command=lambda: self.recognize(self.render_ops(base, ops), "ocr")).pack(side="left", padx=2)
        ttk.Button(btns, text="扫二维码/条码", command=lambda: self.recognize(self.render_ops(base, ops), "code")).pack(side="left", padx=2)
        ttk.Button(btns, text="清空标注", command=lambda: (ops.clear(), redraw())).pack(side="left", padx=2)
        def finish(pin=True):
            final = self.render_ops(base, ops); self.save_shot(final); win.destroy()
            if pin: self.pin_image(final)
        ttk.Button(btns, text="完成并钉图", command=lambda: finish(True)).pack(side="right", padx=2)
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

    # ---------- OCR / 扫码 (v1.2, 可选引擎, 没装时优雅提示) ----------
    _ocr_engine = None  # RapidOCR 实例缓存: 旧版每次识别都重建引擎、重加载模型 (数秒), 只建一次
    @classmethod
    def ocr_image(cls, img):
        """有引擎返回识别文字 (可能为空串); 没引擎返回 None。引擎优先级: RapidOCR -> pytesseract"""
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
                messagebox.showinfo("OCR 未启用", "还没装 OCR 引擎, 装一次即可 (离线可用):\n\npip install rapidocr-onnxruntime\n\n或装 Tesseract 程序 + pip install pytesseract"); return
            self.show_text_result("OCR 识别结果", res or "(没识别到文字, 换个更清晰的截图试试)")
        else:
            res = self.decode_codes(img)
            if res is None:
                messagebox.showinfo("扫码未启用", "还没装扫码引擎, 装一次即可:\n\npip install opencv-python-headless"); return
            self.show_text_result("扫码结果", "\n".join(res) if res else "(没扫到二维码/条码)")
    def show_text_result(self, title, text):
        win = tk.Toplevel(self); win.title(title); win.geometry("460x300"); win.attributes("-topmost", True)
        box = tk.Text(win, wrap="word"); box.pack(fill="both", expand=True, padx=8, pady=8); box.insert("1.0", text)
        bar = ttk.Frame(win); bar.pack(fill="x", padx=8, pady=6)
        ttk.Button(bar, text="复制结果", command=lambda: self.clip_set(box.get("1.0", "end").strip())).pack(side="left", padx=2)
        def to_queue():
            added = 0
            for line in box.get("1.0", "end").splitlines():
                if line.strip(): self.add_record(line); added += 1
            self.refresh_list(); messagebox.showinfo("文字队列", f"已加入 {added} 条到文字队列, 之后按 F7 就能逐条粘贴", parent=win)
        ttk.Button(bar, text="加入文字队列 (配合 F7 粘贴)", command=to_queue).pack(side="left", padx=2)
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
        self._draggable(win); win.bind("<Double-Button-1>", lambda e: win.destroy())

    def on_close(self):
        try: self.cfg.set("Config", "SleepTime", self.sleep_var.get() or "80")
        except Exception: pass
        self.save_config(); self.save_records(); self.destroy()

if __name__ == "__main__":
    App().mainloop()
