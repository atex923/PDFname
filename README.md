# PDFname

PDF 更名、預覽、OCR 框選辨識與檔案搬移工具。

## 最新版本

- `V3.2.0`
- 最新完整碼：[`PDF更名搬移平車_V3.2.0_優化完整碼.py`](PDF更名搬移平車_V3.2.0_優化完整碼.py)
- 正常版 `.py`：[`PDF更名搬移平車_V3.2.0.py`](PDF更名搬移平車_V3.2.0.py)
- 可直接執行的 `.pyw`：[`PDF更名搬移平車_V3.2.0.pyw`](PDF更名搬移平車_V3.2.0.pyw)

舊版程式已移到 [`歷史區`](歷史區/)，修改紀錄請看 [`HISTORY.md`](HISTORY.md)。

## Nuitka 打包

- Nuitka 優化版：[`PDF更名搬移平車_V3.2.0_Nuitka優化版.py`](PDF更名搬移平車_V3.2.0_Nuitka優化版.py)
- macOS 打包腳本：[`build_nuitka_macos.sh`](build_nuitka_macos.sh)
- 打包指南：[`Nuitka打包指南.md`](Nuitka打包指南.md)

## 功能摘要

- PDF 預覽、上下頁、滑鼠縮放、拖曳瀏覽
- PDF 更名與前名調整
- 刪除與回復
- 點擊欄位排序
- 右側預覽區框選 OCR 辨識
- 搬移目的資料夾瀏覽與回復移動

## 建議安裝

```bash
pip install customtkinter PyMuPDF pillow numpy
pip install paddleocr paddlepaddle
```

備用 OCR：

```bash
pip install rapidocr-onnxruntime
pip install easyocr
```
