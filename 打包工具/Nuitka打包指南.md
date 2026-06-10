# Nuitka 打包指南

## 檢查結果

- 目前 `python3` 是 Python 3.14，但 Nuitka 官方文件目前列出的支援範圍是 Python 3.4 到 3.13；建議用 `python3.13` 打包。
- 主程式使用 `tkinter`、`customtkinter`、`PyMuPDF`、`Pillow`、`numpy`。
- OCR 原本會嘗試 PaddleOCR、RapidOCR、EasyOCR。PaddleOCR / EasyOCR 會拉入大型相依套件，Nuitka 打包體積與失敗風險都高。
- 已產生 `PDF更名搬移平車_V3.2.0_Nuitka優化版.py`：優先使用 RapidOCR，PaddleOCR / EasyOCR 保留為一般 Python 執行時後備。

## 建議先安裝

```bash
python3.13 -m pip install -U pip setuptools wheel
python3.13 -m pip install -U nuitka ordered-set zstandard
python3.13 -m pip install -U customtkinter PyMuPDF pillow numpy rapidocr-onnxruntime
```

macOS 若尚未安裝編譯工具：

```bash
xcode-select --install
```

## 最佳指令

在 repo 目錄執行：

```bash
cd /Users/atex1/Documents/Codex/2026-05-29/files-mentioned-by-the-user-pdf
./build_nuitka_macos.sh
```

等同於：

```bash
python3.13 -m nuitka \
  --mode=app \
  --assume-yes-for-downloads \
  --enable-plugin=tk-inter \
  --enable-plugin=numpy \
  --include-package-data=customtkinter \
  --include-package-data=rapidocr_onnxruntime \
  --include-module=rapidocr_onnxruntime \
  --nofollow-import-to=paddleocr \
  --nofollow-import-to=paddlex \
  --nofollow-import-to=paddle \
  --nofollow-import-to=easyocr \
  --nofollow-import-to=torch \
  --nofollow-import-to=torchvision \
  --nofollow-import-to=matplotlib \
  --nofollow-import-to=pandas \
  --nofollow-import-to=scipy \
  --python-flag=no_asserts \
  --python-flag=no_docstrings \
  --product-name="PDF更名搬移平車" \
  --product-version=3.2.0 \
  --file-version=3.2.0 \
  --file-description="PDF rename, preview, OCR and move tool" \
  --report=build_nuitka/nuitka-report.xml \
  --output-dir=build_nuitka \
  --remove-output \
  PDF更名搬移平車_V3.2.0_Nuitka優化版.py
```

## 輸出位置

打包完成後，成品會在：

```text
build_nuitka/
```

macOS app bundle 會出現在該資料夾內。

## 備註

- 先使用 `--mode=app`，比 onefile 更適合 macOS GUI 與 customtkinter 資料檔。
- 如果之後一定要單檔，建議等 app bundle 測試成功後再改 onefile。
- `nuitka-report.xml` 可用來追蹤是否缺少套件資料檔或動態函式庫。
