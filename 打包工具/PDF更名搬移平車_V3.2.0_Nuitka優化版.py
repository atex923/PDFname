# -*- coding: utf-8 -*-
# =========================================================
# PDF更名搬移平車 Ver 3.2.0 精簡修正版 OCR 搬移整合版
# =========================================================
# 保留原功能：
# 1. PDF預覽 / 上下頁 / 滑鼠縮放 / 拖曳瀏覽
# 2. PDF更名 / 增加前名
# 3. 刪除 / 回復
# 4. 點擊欄位排序
# 5. Fluent UI、米橘色變更檔名欄、米藍色增加前名欄
#
# OCR功能：
# 1. 右側預覽區「框選辨識」
# 2. 框選後 OCR 結果顯示在右下方「測試辨識字串」
# 3. 只有勾選「框選辨識」時，點選左側欄位才會自動填入
# 4. 收文日期規則：
#    113/05/26 -> 1130526
#    113-05-26 -> 1130526
#    113.05.26 -> 1130526
#    113年5月6日 -> 1130506
#
# 建議安裝：
# pip install customtkinter PyMuPDF pillow numpy
# pip install paddleocr paddlepaddle
# 備用：
# pip install rapidocr-onnxruntime
# pip install easyocr
# =========================================================

import re
import gc
import warnings
import traceback
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import customtkinter as ctk
import fitz
import numpy as np
from PIL import Image, ImageTk, ImageEnhance, ImageFilter


# =========================================================
# Warning Filter
# =========================================================
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*RequestsDependencyWarning.*")
warnings.filterwarnings("ignore", message=".*Preferred drawing method.*")


# =========================================================
# Theme / Constants
# =========================================================
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

APP_VERSION = "3.2.0"
APP_TITLE = f"PDF更名搬移平車 V{APP_VERSION}"

BG = "#EEF2F7"
CARD = "#FFFFFF"
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
RED = "#DC2626"
RED_HOVER = "#B91C1C"
YELLOW = "#F59E0B"
YELLOW_HOVER = "#D97706"
PREVIEW_BLUE = "#EAF3FF"
PREVIEW_BORDER = "#222222"
FILENAME_BG = "#F7E8D5"
PREFIX_BG = "#DDEBFF"
OCR_BG = "#EAF7E8"
TEXT = "#111827"

FONT = ("Microsoft JhengHei UI", 11)
TREE_FONT = ("Microsoft JhengHei UI", 16)
BTN_FONT = ("Microsoft JhengHei UI", 11)
TITLE_FONT = ("Microsoft JhengHei UI", 13, "bold")


def get_signature_font():
    system = platform.system()
    if system == "Darwin":
        return ("Baskerville", 13, "italic")
    if system == "Windows":
        return ("Old English Text MT", 13)
    return ("serif", 13, "italic")


SIGN_FONT = get_signature_font()

IMAGE_OFFSET = 20
MIN_ZOOM = 0.2
MAX_ZOOM = 5.0
MAX_PREVIEW_PIXELS = 8_000_000
PREVIEW_GC_INTERVAL = 8
DATE_FORMAT = "%Y-%m-%d %H:%M"
OCR_PLACEHOLDER = "開啟「框選辨識」後，在PDF預覽區拖曳框選文字，OCR結果會顯示在這裡。"


@dataclass
class PDFState:
    folder: str = ""
    selected_pdf: str = ""
    current_pdf_path: str = ""
    current_page: int = 0
    zoom: float = 1.0
    sort_column: str = "filename"
    sort_reverse: bool = False


# =========================================================
# Helper
# =========================================================
def normalize_receive_date(text: str) -> str:
    """收文日期：民國3碼年份不補0，月日補2碼。"""
    if not text:
        return ""

    s = str(text).strip()
    replacements = {
        "中華民國": "",
        "民國": "",
        "年": "/",
        "月": "/",
        "日": "",
        "／": "/",
        "-": "/",
        "－": "/",
        ".": "/",
    }

    for old, new in replacements.items():
        s = s.replace(old, new)

    s = re.sub(r"\s+", "", s)

    match = re.search(r"(\d{2,4})/(\d{1,2})/(\d{1,2})", s)
    if match:
        year, month, day = match.groups()
        return f"{year}{month.zfill(2)}{day.zfill(2)}"

    digits = re.sub(r"\D", "", s)

    if len(digits) in (7, 8):
        return digits

    match7 = re.search(r"\d{7}", digits)
    if match7:
        return match7.group(0)

    match8 = re.search(r"\d{8}", digits)
    if match8:
        return match8.group(0)

    return digits


def clean_one_line(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def format_timestamp(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime(DATE_FORMAT)
    except Exception:
        return ""


def toggle_sort(current_column: str, reverse: bool, column: str):
    return (column, not reverse) if current_column == column else (column, False)


def safe_pdf_filename(filename: str) -> str:
    filename = re.sub(r'[\\/:*?"<>|]', "", filename)
    filename = re.sub(r"\s+", " ", filename).strip()
    return filename


def list_pdf_files(folder: str, sort_column: str, reverse: bool):
    result = []
    folder_path = Path(folder)

    if not folder_path.exists():
        return result

    for path in folder_path.iterdir():
        if path.is_file() and path.suffix.lower() == ".pdf":
            try:
                stat = path.stat()
                added = get_file_added_time(path, stat)
                result.append((path.name, added))
            except OSError:
                continue

    key = (lambda item: item[0].lower()) if sort_column == "filename" else (lambda item: item[1])
    return sorted(result, key=key, reverse=reverse)


def format_file_size(size: int) -> str:
    try:
        size = int(size)
    except Exception:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return str(size)


def get_file_added_time(path: Path, stat_result=None) -> float:
    """回傳檔案加入/建立時間。
    macOS 優先使用 st_birthtime；Windows 的 st_ctime 是建立時間；
    Linux 若無 birth time，退回 st_ctime。
    """
    try:
        stat_result = stat_result or path.stat()
        return getattr(stat_result, "st_birthtime", stat_result.st_ctime)
    except Exception:
        return 0.0


def list_directory_items(folder: str, sort_column: str, reverse: bool):
    result = []
    folder_path = Path(folder)

    if not folder_path.exists():
        return result

    for path in folder_path.iterdir():
        try:
            stat = path.stat()
            is_dir = path.is_dir()
            result.append({
                "name": path.name,
                "path": str(path),
                "is_dir": is_dir,
                "size": 0 if is_dir else stat.st_size,
                "created": get_file_added_time(path, stat),
                "modified": stat.st_mtime,
            })
        except OSError:
            continue

    def item_key(item):
        if sort_column == "size":
            return (item["size"], item["name"].lower())
        if sort_column == "created":
            return (item["created"], item["name"].lower())
        if sort_column == "modified":
            return (item["modified"], item["name"].lower())
        return item["name"].lower()

    folders = sorted((item for item in result if item["is_dir"]), key=item_key, reverse=reverse)
    files = sorted((item for item in result if not item["is_dir"]), key=item_key, reverse=reverse)
    return folders + files


# =========================================================
# OCR Engine
# =========================================================
class OCREngine:
    """
    延遲載入 OCR：
    Nuitka 優化版優先使用 RapidOCR，避免打包時優先拉入 PaddleOCR / EasyOCR
    及其大型相依套件。PaddleOCR、EasyOCR 仍保留為一般 Python 執行時的後備。
    """

    def __init__(self):
        self.engine_name = "尚未載入"
        self.ready = False
        self.paddleocr = None
        self.rapidocr = None
        self.easyocr_reader = None

    def load(self):
        if self.ready:
            return

        # 1. RapidOCR：速度快、相依較少，較適合 Nuitka 打包
        try:
            from rapidocr_onnxruntime import RapidOCR
            self.rapidocr = RapidOCR()
            self.engine_name = "RapidOCR"
            self.ready = True
            return
        except Exception:
            pass

        # 2. PaddleOCR：繁中、數字、英文較準，但打包體積較大
        try:
            from paddleocr import PaddleOCR

            for kwargs in (
                {"use_textline_orientation": True, "lang": "chinese_cht"},
                {"lang": "chinese_cht"},
                {"use_textline_orientation": True, "lang": "ch"},
                {"lang": "ch"},
            ):
                try:
                    self.paddleocr = PaddleOCR(**kwargs)
                    self.engine_name = "PaddleOCR"
                    self.ready = True
                    return
                except Exception:
                    continue

        except Exception:
            pass

        # 3. EasyOCR：備用，但 torch 相依很大
        try:
            import easyocr
            self.easyocr_reader = easyocr.Reader(["ch_tra", "en"], gpu=False)
            self.engine_name = "EasyOCR"
            self.ready = True
            return
        except Exception:
            pass

        self.engine_name = "未安裝OCR"
        self.ready = True

    @staticmethod
    def preprocess(img: Image.Image) -> Image.Image:
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size

        if max(w, h) < 1200:
            img = img.resize((w * 2, h * 2), getattr(Image, 'Resampling', Image).LANCZOS)

        img = ImageEnhance.Contrast(img).enhance(1.55)
        img = ImageEnhance.Sharpness(img).enhance(1.8)
        return img.filter(ImageFilter.SHARPEN)

    def recognize(self, img: Image.Image) -> str:
        if img is None:
            return ""

        self.load()

        if self.engine_name == "未安裝OCR":
            return (
                "尚未安裝 OCR 套件。\n"
                "建議：pip install paddleocr paddlepaddle\n"
                "備用：pip install rapidocr-onnxruntime numpy\n"
                "再備用：pip install easyocr numpy"
            )

        processed_img = None
        arr = None
        try:
            processed_img = self.preprocess(img)
            arr = np.asarray(processed_img)

            if self.engine_name == "PaddleOCR":
                try:
                    result = self.paddleocr.ocr(arr)
                except TypeError:
                    result = self.paddleocr.ocr(arr, cls=True)
                return self._parse_paddle_result(result)

            if self.engine_name == "RapidOCR":
                result, _ = self.rapidocr(arr)
                return "\n".join(str(item[1]) for item in result or [] if len(item) >= 2).strip()

            if self.engine_name == "EasyOCR":
                result = self.easyocr_reader.readtext(arr, detail=0, paragraph=True)
                return "\n".join(map(str, result)).strip()

        except Exception as exc:
            return f"OCR失敗：{exc}"

        finally:
            del arr
            if processed_img is not None and processed_img is not img:
                try:
                    processed_img.close()
                except Exception:
                    pass
            gc.collect()

        return ""

    @staticmethod
    def _parse_paddle_result(result) -> str:
        texts = []

        if not result:
            return ""

        for page in result:
            if not page:
                continue

            for line in page:
                try:
                    if len(line) < 2:
                        continue
                    info = line[1]
                    if isinstance(info, (list, tuple)) and info:
                        texts.append(str(info[0]))
                    else:
                        texts.append(str(info))
                except Exception:
                    continue

        return "\n".join(texts).strip()


# =========================================================
# Main
# =========================================================
class PDFRenameTool:

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1600x920")
        self.root.minsize(1180, 720)
        self.root.resizable(True, True)

        self.state = PDFState()
        self.deleted_files = []
        self.move_history = []
        self.move_folder = ""
        self.move_recent_folders = []
        self.move_sort_column = "name"
        self.move_sort_reverse = False
        self.current_mode = "rename"
        self.pdf_doc = None

        self.preview_img = None
        self.preview_pil_img = None
        self.preview_gc_counter = 0

        self.ocr_engine = OCREngine()
        self.ocr_select_mode = tk.BooleanVar(value=False)
        self.ocr_start = None
        self.ocr_rect_id = None

        self.company_options = ["中工段", "中興監造", "聖穎", "建業"]

        self.vars = {}
        self.entry_widgets = {}

        self.create_style()
        self.create_ui()

    # =====================================================
    # UI Factory
    # =====================================================
    def create_style(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", rowheight=34, font=TREE_FONT, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Microsoft JhengHei UI", 13, "bold"))

    def button(self, parent, text, command, width=90, color=PRIMARY, hover=PRIMARY_HOVER,
               text_color="white", border=False):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=26,
            corner_radius=10,
            fg_color=color,
            hover_color=hover,
            text_color=text_color,
            border_width=1 if border else 0,
            border_color=PREVIEW_BORDER,
            font=BTN_FONT,
        )

    def entry(self, parent, var, color="white"):
        return ctk.CTkEntry(
            parent,
            textvariable=var,
            height=24,
            font=FONT,
            corner_radius=10,
            fg_color=color,
        )

    def combo(self, parent, var, values):
        return ctk.CTkComboBox(
            parent,
            variable=var,
            values=values,
            height=24,
            font=FONT,
            corner_radius=10,
            state="normal",
        )

    # =====================================================
    # Layout
    # =====================================================
    def create_ui(self):
        self.root.configure(bg=BG)

        main = tk.Frame(self.root, bg=BG)
        main.pack(side="top", fill="both", expand=True)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1, minsize=500)
        main.grid_columnconfigure(1, weight=0, minsize=84)
        main.grid_columnconfigure(2, weight=2, minsize=480)
        main.grid_columnconfigure(3, weight=0, minsize=72)

        # 左半部：原本更名檔案瀏覽區保留，但可隨視窗縮放
        left = tk.Frame(main, bg=BG, width=720)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        # 中間：搬移箭頭固定放在左右兩半正中間；更名模式時只隱藏按鈕，不改變版面結構
        self.center_move_bar = tk.Frame(main, bg=BG, width=84)
        self.center_move_bar.grid(row=0, column=1, sticky="ns", padx=(0, 0), pady=12)
        self.center_move_bar.grid_propagate(False)

        # 最右側縱向分頁標籤：先固定在右側，避免長檔名把切換標籤擠出視窗
        self.tab_bar = tk.Frame(main, bg=BG, width=72)
        self.tab_bar.grid(row=0, column=3, sticky="ns", padx=(0, 12), pady=12)
        self.tab_bar.grid_propagate(False)

        # 右半部：更名預覽 / 搬移瀏覽區堆疊切換
        self.right_shell = tk.Frame(main, bg=BG)
        self.right_shell.grid(row=0, column=2, sticky="nsew", padx=(6, 6), pady=12)
        self.right_stack = tk.Frame(self.right_shell, bg=BG)
        self.right_stack.pack(side="left", fill="both", expand=True)

        self.rename_page = tk.Frame(self.right_stack, bg=BG)
        self.move_page = tk.Frame(self.right_stack, bg=BG)

        self.create_folder_area(left)
        self.create_treeview(left)
        self.create_form(left)

        self.create_preview_toolbar(self.rename_page)
        self.create_preview_area(self.rename_page)

        self.create_move_area(self.move_page)
        self.create_center_move_button()
        self.create_vertical_tabs()
        self.switch_mode("rename")
        self.create_signature_footer()

    def create_signature_footer(self):
        footer = tk.Frame(self.root, bg=BG, height=28)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)

        tk.Label(
            footer,
            text="Inspired by Atex's high thoughts.",
            bg=BG,
            fg="#374151",
            font=SIGN_FONT,
        ).pack(side="bottom", pady=(0, 6))

    def create_center_move_button(self):
        """建立左右瀏覽區中央的向右搬移按鈕。
        使用 place 固定在中間偏上位置，避免切換分頁後被 pack 版面擠到下方。
        """
        self.center_move_btn = ctk.CTkButton(
            self.center_move_bar,
            text="→",
            command=self.move_selected_files_to_right,
            width=64,
            height=86,
            corner_radius=20,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color="white",
            font=("Microsoft JhengHei UI", 34, "bold"),
        )
        self.center_move_btn.place(relx=0.5, rely=0.38, anchor="center")
        self.center_move_btn.place_forget()

    def create_vertical_tabs(self):
        self.rename_tab_btn = ctk.CTkButton(
            self.tab_bar,
            text="更\n名",
            command=lambda: self.switch_mode("rename"),
            width=52,
            height=135,
            corner_radius=14,
            font=("Microsoft JhengHei UI", 18, "bold"),
        )
        self.rename_tab_btn.pack(pady=(10, 10), padx=8)

        self.move_tab_btn = ctk.CTkButton(
            self.tab_bar,
            text="搬\n移",
            command=lambda: self.switch_mode("move"),
            width=52,
            height=135,
            corner_radius=14,
            font=("Microsoft JhengHei UI", 18, "bold"),
        )
        self.move_tab_btn.pack(pady=(0, 10), padx=8)

    def switch_mode(self, mode):
        self.current_mode = mode
        self.rename_page.pack_forget()
        self.move_page.pack_forget()

        if mode == "move":
            self.move_page.pack(fill="both", expand=True)
            self.center_move_btn.place(relx=0.5, rely=0.38, anchor="center")
            self.rename_tab_btn.configure(fg_color="#CBD5E1", text_color="black")
            self.move_tab_btn.configure(fg_color=PRIMARY, text_color="white")
            if not self.move_folder and self.state.folder:
                self.set_move_folder(self.state.folder)
        else:
            self.rename_page.pack(fill="both", expand=True)
            self.center_move_btn.place_forget()
            self.rename_tab_btn.configure(fg_color=PRIMARY, text_color="white")
            self.move_tab_btn.configure(fg_color="#CBD5E1", text_color="black")

    def create_folder_area(self, parent):
        frame = self.card(parent)
        frame.pack(fill="x", pady=(0, 10))
        frame.configure(padx=12, pady=12)

        tk.Label(frame, text="選擇資料夾", bg=CARD, fg=TEXT, font=TITLE_FONT).pack(anchor="w", pady=(0, 8))

        row = tk.Frame(frame, bg=CARD)
        row.pack(fill="x")

        self.folder_var = tk.StringVar()
        self.entry(row, self.folder_var).pack(side="left", fill="x", expand=True, padx=(0, 8))

        buttons = [
            ("瀏覽資料夾", self.browse_folder, 110, PRIMARY, PRIMARY_HOVER, "white"),
            ("刪除檔案", self.delete_pdf, 100, RED, RED_HOVER, "white"),
            ("回復刪除", self.restore_pdf, 100, YELLOW, YELLOW_HOVER, "black"),
        ]

        for text, cmd, width, color, hover, text_color in buttons:
            self.button(row, text, cmd, width, color, hover, text_color).pack(side="left", padx=2)

    def create_treeview(self, parent):
        frame = self.card(parent)
        frame.pack(fill="both", expand=True, pady=(0, 10))

        columns = ("no", "filename", "date")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")

        headers = {
            "no": ("項次", None),
            "filename": ("檔名", lambda: self.sort_tree("filename")),
            "date": ("加入時間", lambda: self.sort_tree("date")),
        }

        for col, (text, cmd) in headers.items():
            if cmd:
                self.tree.heading(col, text=text, command=cmd)
            else:
                self.tree.heading(col, text=text)

        self.tree.column("no", width=70, minwidth=70, anchor="center", stretch=False)
        self.tree.column("filename", width=430, minwidth=220, stretch=True)
        self.tree.column("date", width=180, minwidth=160, anchor="center", stretch=False)

        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=x_scroll.set)

        scroll.pack(side="right", fill="y")
        x_scroll.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select_pdf)

    def create_form(self, parent):
        outer = self.card(parent)
        outer.pack(fill="x")
        outer.configure(padx=12, pady=12)

        form = tk.Frame(outer, bg=CARD)
        form.pack(fill="x")

        fields = [
            ("發文單位", "combo"),
            ("文號", "entry"),
            ("主旨", "entry"),
            ("收文號碼", "entry"),
            ("收文日期", "entry"),
            ("增加前名", "combo"),
        ]

        for row, (title, kind) in enumerate(fields):
            tk.Label(form, text=title, bg=CARD, fg=TEXT, font=FONT).grid(row=row, column=0, sticky="w", pady=4)

            var = tk.StringVar()
            self.vars[title] = var

            if kind == "combo":
                widget = self.combo(form, var, self.company_options)
                widget.set("")
            else:
                widget = self.entry(form, var)
                widget.bind("<Button-1>", lambda _event, field=title: self.fill_field_from_ocr(field))

            self.entry_widgets[title] = widget
            widget.grid(row=row, column=1, sticky="ew", padx=8)
            var.trace_add("write", self.update_preview)

        form.columnconfigure(1, weight=1)
        self.create_bottom_rename_area(outer)

    def create_bottom_rename_area(self, parent):
        bottom = tk.Frame(parent, bg="#EAF1FF", highlightbackground="#7DA2FF", highlightthickness=1)
        bottom.pack(fill="x", pady=(14, 0))
        bottom.configure(padx=10, pady=10)

        self.preview_var = tk.StringVar()
        self.prefix_var = tk.StringVar()

        rows = [
            ("變更檔名", self.preview_var, FILENAME_BG, "更名確認", self.rename_pdf, 0),
            ("前名調整", self.prefix_var, PREFIX_BG, "增名確認", self.rename_prefix, 1),
        ]

        for label, var, color, btn_text, cmd, row in rows:
            pady = (10, 0) if row else (0, 6)

            tk.Label(bottom, text=label, bg="#EAF1FF", fg=TEXT, font=FONT).grid(
                row=row, column=0, sticky="w", pady=pady
            )

            self.entry(bottom, var, color).grid(row=row, column=1, sticky="ew", padx=8, pady=(10, 0) if row else 0)

            self.button(bottom, btn_text, cmd, width=110 if row else 100).grid(
                row=row, column=2, padx=4, pady=(10, 0) if row else 0
            )

        bottom.columnconfigure(1, weight=1)

    def create_preview_toolbar(self, parent):
        bar = tk.Frame(parent, bg=CARD, height=56)
        bar.pack(fill="x", pady=(0, 10))
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg=CARD)
        left.pack(side="left", padx=10)

        for text, cmd, width in (("－", self.zoom_out, 45), ("＋", self.zoom_in, 45), ("整頁", self.fit_page, 70)):
            self.preview_button(left, text, cmd, width).pack(side="left", padx=2, pady=10)

        self.page_var = tk.StringVar(value="0 / 0")
        tk.Label(left, textvariable=self.page_var, bg=CARD, fg=TEXT, font=FONT).pack(side="left", padx=(18, 8))

        for text, cmd in (("上一頁", self.prev_page), ("下一頁", self.next_page)):
            self.preview_button(left, text, cmd, 90).pack(side="left", padx=2)

        right = tk.Frame(bar, bg=CARD)
        right.pack(side="right", padx=10)

        self.ocr_status_var = tk.StringVar(value="OCR：尚未載入")
        tk.Label(right, textvariable=self.ocr_status_var, bg=CARD, fg=TEXT, font=FONT).pack(side="left", padx=(0, 10))

        self.ocr_check = ctk.CTkCheckBox(
            right,
            text="框選辨識",
            variable=self.ocr_select_mode,
            command=self.toggle_ocr_mode,
            font=BTN_FONT,
        )
        self.ocr_check.pack(side="left", padx=2)

    def create_preview_area(self, parent):
        frame = self.card(parent)
        frame.pack(fill="both", expand=True)

        canvas_frame = tk.Frame(frame, bg=CARD)
        canvas_frame.pack(fill="both", expand=True)

        x_scroll = tk.Scrollbar(canvas_frame, orient="horizontal")
        y_scroll = tk.Scrollbar(canvas_frame, orient="vertical")

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="white",
            highlightthickness=0,
            xscrollcommand=x_scroll.set,
            yscrollcommand=y_scroll.set,
        )

        x_scroll.config(command=self.canvas.xview)
        y_scroll.config(command=self.canvas.yview)

        x_scroll.pack(side="bottom", fill="x")
        y_scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        for event, handler in {
            "<MouseWheel>": self.mouse_zoom,
            "<ButtonPress-1>": self.canvas_mouse_down,
            "<B1-Motion>": self.canvas_mouse_move,
            "<ButtonRelease-1>": self.canvas_mouse_up,
        }.items():
            self.canvas.bind(event, handler)

        self.create_ocr_text_area(frame)

    def create_ocr_text_area(self, parent):
        frame = tk.Frame(parent, bg=CARD, height=125)
        frame.pack(fill="x", pady=(10, 0))
        frame.pack_propagate(False)

        title_row = tk.Frame(frame, bg=CARD)
        title_row.pack(fill="x", padx=10, pady=(8, 4))

        tk.Label(title_row, text="測試辨識字串", bg=CARD, fg=TEXT, font=TITLE_FONT).pack(side="left")
        self.preview_button(title_row, "清除", self.clear_ocr_text, 70).pack(side="right")

        self.ocr_text = tk.Text(frame, height=3, font=FONT, bg=OCR_BG, fg=TEXT, wrap="word", relief="solid", bd=1)
        self.ocr_text.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.set_text(self.ocr_text, OCR_PLACEHOLDER)

    def card(self, parent):
        return tk.Frame(parent, bg=CARD)

    def preview_button(self, parent, text, command, width):
        return self.button(
            parent,
            text,
            command,
            width=width,
            color=PREVIEW_BLUE,
            hover="#DCEBFF",
            text_color="black",
            border=True,
        )

    @staticmethod
    def set_text(widget, text):
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def refresh_file_views(self, refresh_move=True):
        self.load_pdfs()
        if refresh_move and self.move_folder:
            self.load_move_tree()

    def clear_current_pdf(self, clear_canvas=False):
        self.close_pdf()
        self.state.selected_pdf = ""
        self.state.current_pdf_path = ""
        self.state.current_page = 0
        self.release_preview_image(clear_canvas=clear_canvas, force_collect=True)
        self.page_var.set("0 / 0")

    def select_pdf_in_tree(self, filename):
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id, "values")
            if values and values[1] == filename:
                self.tree.selection_set(item_id)
                self.tree.see(item_id)
                return True
        return False

    def collect_preview_memory(self, force=False):
        self.preview_gc_counter += 1
        if force or self.preview_gc_counter >= PREVIEW_GC_INTERVAL:
            self.preview_gc_counter = 0
            gc.collect()

    def release_preview_image(self, clear_canvas=False, force_collect=False):
        if clear_canvas:
            self.canvas.delete("all")

        if self.preview_pil_img is not None:
            try:
                self.preview_pil_img.close()
            except Exception:
                pass

        self.preview_pil_img = None
        self.preview_img = None
        self.collect_preview_memory(force=force_collect)

    @staticmethod
    def limited_preview_zoom(page, requested_zoom):
        page_pixels = max(float(page.rect.width * page.rect.height), 1.0)
        pixel_limited_zoom = (MAX_PREVIEW_PIXELS / page_pixels) ** 0.5
        return max(MIN_ZOOM, min(requested_zoom, MAX_ZOOM, pixel_limited_zoom))

    # =====================================================
    # Move Browser
    # =====================================================
    def create_move_area(self, parent):
        top = self.card(parent)
        top.pack(fill="x", pady=(0, 10))
        top.configure(padx=12, pady=12)

        tk.Label(top, text="搬移目的資料夾", bg=CARD, fg=TEXT, font=TITLE_FONT).pack(anchor="w", pady=(0, 8))

        row = tk.Frame(top, bg=CARD)
        row.pack(fill="x")

        self.move_folder_var = tk.StringVar()
        self.move_folder_combo = ctk.CTkComboBox(
            row,
            variable=self.move_folder_var,
            values=[],
            height=28,
            font=FONT,
            corner_radius=10,
            state="normal",
            command=self.on_move_folder_combo,
        )
        self.move_folder_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.move_folder_combo.bind("<Return>", lambda _event: self.set_move_folder(self.move_folder_var.get()))

        self.button(row, "瀏覽", self.browse_move_folder, 80).pack(side="left", padx=2)
        self.button(row, "上一層", self.move_parent_folder, 85, color=PREVIEW_BLUE, hover="#DCEBFF", text_color="black", border=True).pack(side="left", padx=2)
        self.button(row, "回復移動", self.undo_last_move, 100, color=YELLOW, hover=YELLOW_HOVER, text_color="black").pack(side="left", padx=2)

        body = self.card(parent)
        body.pack(fill="both", expand=True)

        # 瀏覽區本體
        tree_area = tk.Frame(body, bg=CARD)
        tree_area.pack(fill="both", expand=True)

        columns = ("name", "size", "created", "modified")
        self.move_tree = ttk.Treeview(tree_area, columns=columns, show="headings")
        headers = {
            "name": "檔名",
            "size": "檔案大小",
            "created": "加入時間",
            "modified": "修改時間",
        }
        for col, title in headers.items():
            self.move_tree.heading(col, text=title, command=lambda c=col: self.sort_move_tree(c))

        self.move_tree.column("name", width=360, minwidth=220, stretch=True)
        self.move_tree.column("size", width=110, minwidth=90, anchor="e", stretch=False)
        self.move_tree.column("created", width=170, minwidth=150, anchor="center", stretch=False)
        self.move_tree.column("modified", width=170, minwidth=150, anchor="center", stretch=False)

        y_scroll = ttk.Scrollbar(tree_area, orient="vertical", command=self.move_tree.yview)
        self.move_tree.configure(yscrollcommand=y_scroll.set)
        self.move_tree.pack(side="left", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")
        self.move_tree.bind("<Double-1>", self.enter_selected_move_folder)

        # 左右移動欄固定放在搬移瀏覽區正下方
        x_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.move_tree.xview)
        self.move_tree.configure(xscrollcommand=x_scroll.set)
        x_scroll.pack(fill="x", padx=0, pady=(2, 0))

        bottom = self.card(parent)
        bottom.pack(fill="x", pady=(10, 0))
        bottom.configure(padx=12, pady=12)

        self.move_target_var = tk.StringVar(value="目的地：尚未選擇")
        tk.Label(bottom, textvariable=self.move_target_var, bg=CARD, fg=TEXT, font=FONT).pack(side="left", fill="x", expand=True)

    def browse_move_folder(self):
        folder = filedialog.askdirectory(initialdir=self.move_folder or self.state.folder or None)
        if folder:
            self.set_move_folder(folder)

    def on_move_folder_combo(self, value):
        self.set_move_folder(value)

    def set_move_folder(self, folder):
        if not folder:
            return
        path = Path(folder).expanduser()
        if not path.exists() or not path.is_dir():
            messagebox.showerror("錯誤", f"資料夾不存在：\n{folder}")
            return

        self.move_folder = str(path)
        self.move_folder_var.set(self.move_folder)
        self.move_target_var.set(f"目的地：{self.move_folder}")

        if self.move_folder not in self.move_recent_folders:
            self.move_recent_folders.insert(0, self.move_folder)
            self.move_recent_folders = self.move_recent_folders[:12]
            self.move_folder_combo.configure(values=self.move_recent_folders)

        self.load_move_tree()

    def load_move_tree(self):
        self.move_tree.delete(*self.move_tree.get_children())
        for item in list_directory_items(self.move_folder, self.move_sort_column, self.move_sort_reverse):
            icon_name = f"📁 {item['name']}" if item["is_dir"] else f"📄 {item['name']}"
            size_text = "<資料夾>" if item["is_dir"] else format_file_size(item["size"])
            created = format_timestamp(item["created"])
            modified = format_timestamp(item["modified"])
            self.move_tree.insert("", "end", values=(icon_name, size_text, created, modified), tags=(item["path"], "dir" if item["is_dir"] else "file"))

    def sort_move_tree(self, column):
        self.move_sort_column, self.move_sort_reverse = toggle_sort(
            self.move_sort_column, self.move_sort_reverse, column
        )
        self.load_move_tree()

    def move_parent_folder(self):
        if not self.move_folder:
            return
        parent = Path(self.move_folder).parent
        if parent and str(parent) != self.move_folder:
            self.set_move_folder(str(parent))

    def get_selected_move_path(self):
        selected = self.move_tree.selection()
        if not selected:
            return None
        tags = self.move_tree.item(selected[0], "tags")
        return Path(tags[0]) if tags else None

    def enter_selected_move_folder(self, _event=None):
        path = self.get_selected_move_path()
        if path and path.is_dir():
            self.set_move_folder(str(path))

    def get_selected_left_pdf_path(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提醒", "請先在左側檔案瀏覽區選擇要搬移的 PDF。")
            return None
        values = self.tree.item(selected[0], "values")
        if not values:
            return None
        src = Path(self.state.folder) / values[1]
        if not src.exists():
            messagebox.showerror("錯誤", f"找不到檔案：\n{src}")
            return None
        return src

    def get_move_destination_folder(self):
        selected_path = self.get_selected_move_path()
        if selected_path and selected_path.is_dir():
            return selected_path
        if self.move_folder:
            return Path(self.move_folder)
        return None

    def move_selected_files_to_right(self):
        src = self.get_selected_left_pdf_path()
        dst_folder = self.get_move_destination_folder()
        if not src or not dst_folder:
            messagebox.showwarning("提醒", "請先選擇右側目的資料夾。")
            return

        dst = dst_folder / src.name
        if dst.exists():
            messagebox.showerror("錯誤", f"目的資料夾已有同名檔案：\n{dst.name}")
            return

        try:
            if self.state.current_pdf_path and Path(self.state.current_pdf_path) == src:
                self.clear_current_pdf(clear_canvas=True)

            src.rename(dst)
            self.move_history.append((dst, src))
            self.refresh_file_views()
            self.move_target_var.set(f"已搬移到：{dst_folder}")
        except Exception as exc:
            messagebox.showerror("搬移失敗", str(exc))

    def undo_last_move(self):
        if not self.move_history:
            messagebox.showinfo("提醒", "目前沒有可回復的搬移步驟。")
            return

        moved_path, original_path = self.move_history[-1]
        if not moved_path.exists():
            messagebox.showerror("錯誤", f"找不到已搬移的檔案：\n{moved_path}")
            return
        if original_path.exists():
            messagebox.showerror("錯誤", f"原位置已有同名檔案：\n{original_path.name}")
            return

        try:
            moved_path.rename(original_path)
            self.move_history.pop()
            self.refresh_file_views()
            self.move_target_var.set(f"已回復：{original_path}")
        except Exception as exc:
            messagebox.showerror("回復失敗", str(exc))

    # =====================================================
    # OCR Fill
    # =====================================================
    def get_ocr_text(self):
        return self.ocr_text.get("1.0", "end").strip()

    def clear_ocr_text(self):
        self.set_text(self.ocr_text, "")

    def fill_field_from_ocr(self, field):
        if not self.ocr_select_mode.get():
            return

        text = self.get_ocr_text()

        if not text or OCR_PLACEHOLDER in text:
            return

        value = normalize_receive_date(text) if field == "收文日期" else clean_one_line(text)
        self.vars[field].set(value)

    # =====================================================
    # Folder / Tree
    # =====================================================
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        self.state.folder = folder
        self.folder_var.set(folder)
        self.load_pdfs()
        if not self.move_folder:
            self.set_move_folder(folder)

    def load_pdfs(self):
        self.tree.delete(*self.tree.get_children())

        pdfs = list_pdf_files(self.state.folder, self.state.sort_column, self.state.sort_reverse)

        for index, (filename, added) in enumerate(pdfs, start=1):
            date_text = format_timestamp(added)
            self.tree.insert("", "end", values=(index, filename, date_text))

    def sort_tree(self, column):
        self.state.sort_column, self.state.sort_reverse = toggle_sort(
            self.state.sort_column, self.state.sort_reverse, column
        )
        self.load_pdfs()

    def select_pdf(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return

        values = self.tree.item(selected[0], "values")
        if not values:
            return

        self.state.selected_pdf = values[1]
        self.state.current_pdf_path = str(Path(self.state.folder) / self.state.selected_pdf)
        self.state.current_page = 0

        self.open_pdf(self.state.current_pdf_path)
        self.fit_page()

    # =====================================================
    # PDF Preview
    # =====================================================
    def open_pdf(self, path):
        try:
            self.close_pdf()
            self.pdf_doc = fitz.open(path)
        except Exception as exc:
            messagebox.showerror("錯誤", str(exc))

    def close_pdf(self):
        if self.pdf_doc:
            self.pdf_doc.close()
            self.pdf_doc = None
            self.collect_preview_memory(force=True)

    def show_preview(self):
        if not self.pdf_doc:
            return

        try:
            page = self.pdf_doc.load_page(self.state.current_page)
            render_zoom = self.limited_preview_zoom(page, self.state.zoom)
            self.state.zoom = render_zoom
            matrix = fitz.Matrix(render_zoom, render_zoom)

            self.release_preview_image(clear_canvas=True)
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.preview_pil_img = img
            self.preview_img = ImageTk.PhotoImage(img)

            self.canvas.create_image(IMAGE_OFFSET, IMAGE_OFFSET, anchor="nw", image=self.preview_img, tags=("pdf_image",))
            self.canvas.config(scrollregion=self.canvas.bbox("all"))

            self.page_var.set(f"{self.state.current_page + 1} / {len(self.pdf_doc)}")
            del pix
            self.collect_preview_memory()

        except Exception as exc:
            messagebox.showerror("錯誤", f"PDF預覽失敗：{exc}")

    def fit_page(self):
        if not self.pdf_doc:
            return

        page = self.pdf_doc.load_page(self.state.current_page)
        canvas_width = max(self.canvas.winfo_width(), 820)
        self.state.zoom = max(MIN_ZOOM, (canvas_width - 80) / page.rect.width)
        self.show_preview()

    def zoom_in(self):
        self.state.zoom = min(MAX_ZOOM, self.state.zoom + 0.1)
        self.show_preview()

    def zoom_out(self):
        self.state.zoom = max(0.3, self.state.zoom - 0.1)
        self.show_preview()

    def mouse_zoom(self, event):
        if self.ocr_select_mode.get():
            return
        self.zoom_in() if event.delta > 0 else self.zoom_out()

    def next_page(self):
        if self.pdf_doc and self.state.current_page < len(self.pdf_doc) - 1:
            self.state.current_page += 1
            self.show_preview()

    def prev_page(self):
        if self.pdf_doc and self.state.current_page > 0:
            self.state.current_page -= 1
            self.show_preview()

    # =====================================================
    # Pan / OCR Selection
    # =====================================================
    def toggle_ocr_mode(self):
        enabled = self.ocr_select_mode.get()
        self.canvas.config(cursor="crosshair" if enabled else "")

        if not enabled and self.ocr_rect_id:
            self.canvas.delete(self.ocr_rect_id)
            self.ocr_rect_id = None

    def canvas_mouse_down(self, event):
        if self.ocr_select_mode.get():
            self.start_ocr_select(event)
        else:
            self.canvas.scan_mark(event.x, event.y)

    def canvas_mouse_move(self, event):
        if self.ocr_select_mode.get():
            self.move_ocr_select(event)
        else:
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def canvas_mouse_up(self, event):
        if self.ocr_select_mode.get():
            self.end_ocr_select(event)

    def start_ocr_select(self, event):
        self.ocr_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

        if self.ocr_rect_id:
            self.canvas.delete(self.ocr_rect_id)

        x, y = self.ocr_start
        self.ocr_rect_id = self.canvas.create_rectangle(x, y, x, y, outline=PRIMARY, width=2, dash=(4, 2))

    def move_ocr_select(self, event):
        if not self.ocr_start or not self.ocr_rect_id:
            return

        x0, y0 = self.ocr_start
        x1 = self.canvas.canvasx(event.x)
        y1 = self.canvas.canvasy(event.y)
        self.canvas.coords(self.ocr_rect_id, x0, y0, x1, y1)

    def end_ocr_select(self, event):
        if not self.ocr_start:
            return

        x0, y0 = self.ocr_start
        x1 = self.canvas.canvasx(event.x)
        y1 = self.canvas.canvasy(event.y)
        self.ocr_start = None

        if self.ocr_rect_id:
            self.canvas.delete(self.ocr_rect_id)
            self.ocr_rect_id = None

        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))

        if right - left < 8 or bottom - top < 8:
            return

        self.run_ocr_for_canvas_rect(left, top, right, bottom)

    def run_ocr_for_canvas_rect(self, left, top, right, bottom):
        if self.preview_pil_img is None:
            return

        img_left = IMAGE_OFFSET
        img_top = IMAGE_OFFSET
        img_right = img_left + self.preview_pil_img.width
        img_bottom = img_top + self.preview_pil_img.height

        crop_left = max(left, img_left)
        crop_top = max(top, img_top)
        crop_right = min(right, img_right)
        crop_bottom = min(bottom, img_bottom)

        if crop_right <= crop_left or crop_bottom <= crop_top:
            return

        crop_box = (
            int(crop_left - img_left),
            int(crop_top - img_top),
            int(crop_right - img_left),
            int(crop_bottom - img_top),
        )

        crop_img = None
        try:
            crop_img = self.preview_pil_img.crop(crop_box)

            self.set_text(self.ocr_text, "辨識中...")
            self.root.update_idletasks()

            result = self.ocr_engine.recognize(crop_img)
            self.ocr_status_var.set(f"OCR：{self.ocr_engine.engine_name}")

            self.set_text(self.ocr_text, result)

        except Exception as exc:
            self.set_text(self.ocr_text, f"OCR錯誤：{exc}")

        finally:
            if crop_img is not None:
                try:
                    crop_img.close()
                except Exception:
                    pass
            gc.collect()

    # =====================================================
    # Rename
    # =====================================================
    def update_preview(self, *_args):
        base_parts = [self.vars["發文單位"].get(), self.vars["文號"].get(), self.vars["主旨"].get()]
        base = "_".join(part for part in base_parts if part)

        extra = [self.vars["收文號碼"].get(), self.vars["收文日期"].get()]
        extra = [part for part in extra if part]

        filename = f"{base}({'_'.join(extra)}).pdf" if extra else f"{base}.pdf"
        self.preview_var.set(safe_pdf_filename(filename))

        prefix = self.vars["增加前名"].get()
        self.prefix_var.set(f"{prefix}_{self.state.selected_pdf}" if prefix and self.state.selected_pdf else "")

    def rename_file(self, new_name):
        new_name = safe_pdf_filename(new_name)

        if not self.state.selected_pdf or not new_name:
            return

        old_path = Path(self.state.folder) / self.state.selected_pdf
        new_path = Path(self.state.folder) / new_name

        if old_path == new_path:
            return

        if new_path.exists():
            messagebox.showerror("錯誤", f"檔案已存在：\n{new_path.name}")
            return

        try:
            self.close_pdf()
            old_path.rename(new_path)

            self.state.selected_pdf = new_path.name
            self.state.current_pdf_path = str(new_path)

            self.open_pdf(str(new_path))
            self.load_pdfs()
            self.select_pdf_in_tree(new_path.name)
            self.show_preview()

        except Exception as exc:
            messagebox.showerror("錯誤", str(exc))

    def rename_pdf(self):
        self.rename_file(self.preview_var.get())

    def rename_prefix(self):
        self.rename_file(self.prefix_var.get())

    # =====================================================
    # Delete / Restore
    # =====================================================
    def delete_pdf(self):
        if not self.state.selected_pdf:
            return

        recycle = Path(self.state.folder) / "_deleted_temp"
        recycle.mkdir(exist_ok=True)

        old_path = Path(self.state.folder) / self.state.selected_pdf
        deleted_path = recycle / self.state.selected_pdf

        if deleted_path.exists():
            messagebox.showerror("錯誤", f"暫存刪除區已有同名檔案：\n{deleted_path.name}")
            return

        try:
            self.clear_current_pdf(clear_canvas=True)
            old_path.rename(deleted_path)
            self.deleted_files.append((deleted_path, old_path))
            self.load_pdfs()

        except Exception as exc:
            messagebox.showerror("錯誤", str(exc))

    def restore_pdf(self):
        if not self.deleted_files:
            return

        deleted_path, original_path = self.deleted_files[-1]

        try:
            if original_path.exists():
                messagebox.showerror("錯誤", f"原位置已有同名檔案：\n{original_path.name}")
                return

            deleted_path.rename(original_path)
            self.deleted_files.pop()
            self.load_pdfs()

        except Exception as exc:
            messagebox.showerror("錯誤", str(exc))


# =========================================================
# Run
# =========================================================
def run_app():
    try:
        root = ctk.CTk()
    except Exception:
        root = tk.Tk()

    app = PDFRenameTool(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        run_app()
    except Exception:
        error_text = traceback.format_exc()

        try:
            log_path = Path(__file__).with_name("pdfname_error_log.txt")
            log_path.write_text(error_text, encoding="utf-8")
        except Exception:
            pass

        try:
            temp_root = tk.Tk()
            temp_root.withdraw()
            messagebox.showerror(
                "程式啟動失敗",
                "程式發生錯誤，已產生 pdfname_error_log.txt。\n\n"
                + error_text[-2000:]
            )
            temp_root.destroy()
        except Exception:
            print(error_text)
