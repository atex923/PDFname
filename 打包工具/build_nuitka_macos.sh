#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3.13}"
APP_SOURCE="PDF更名搬移平車_V3.2.0_Nuitka優化版.py"
OUTPUT_DIR="build_nuitka"

"${PYTHON_BIN}" -m nuitka \
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
  --report="${OUTPUT_DIR}/nuitka-report.xml" \
  --output-dir="${OUTPUT_DIR}" \
  --remove-output \
  "${APP_SOURCE}"
