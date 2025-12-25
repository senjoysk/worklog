#!/bin/bash
# worklog ビルドスクリプト

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== worklog ビルド ==="
echo ""

# 1. ビルドディレクトリ準備
echo "ビルドディレクトリを準備中..."
mkdir -p dist build

# 2. Swiftバイナリをビルド
echo "ocr_tool をビルド中..."
swiftc -O -o dist/ocr_tool src/ocr_tool.swift

# 3. Pythonバイナリをビルド
echo "worklog をビルド中..."
pyinstaller --onefile --name worklog --distpath dist --workpath build --specpath build --paths src --hidden-import window_info src/main.py

echo "worklog-daily をビルド中..."
pyinstaller --onefile --name worklog-daily --distpath dist --workpath build --specpath build src/daily_report.py

echo "worklog-menubar をビルド中..."
pyinstaller --onefile --windowed --name worklog-menubar --distpath dist --workpath build --specpath build src/menubar_app.py

# 4. コード署名（画面収録権限維持のため）
echo "コード署名中..."
codesign --force --sign - --identifier "com.user.worklog" dist/worklog
codesign --force --sign - --identifier "com.user.worklog.ocr" dist/ocr_tool

echo ""
echo "=== ビルド完了 ==="
echo ""
echo "生成されたバイナリ:"
ls -la dist/
