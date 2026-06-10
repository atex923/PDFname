# PDFname

PDF 更名、預覽、OCR 框選辨識與檔案搬移工具。

## 最新主程式

目前最新版是 `V3.2.0`。

請優先使用根目錄這個檔案：

[`PDF更名搬移平車_V3.2.0.py`](PDF更名搬移平車_V3.2.0.py)

## 其他資料夾

- [`其他執行版本`](其他執行版本/)：完整碼備份與 `.pyw` 版本。
- [`打包工具`](打包工具/)：Nuitka 優化版、打包腳本與打包指南。
- [`歷史區`](歷史區/)：舊版程式。
- [`HISTORY.md`](HISTORY.md)：修改歷程。

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
