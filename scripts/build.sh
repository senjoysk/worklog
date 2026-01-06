#!/bin/bash
# worklog ビルドスクリプト

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

cd "$PROJECT_DIR"

echo "=== worklog ビルド ==="
echo ""

# 1. venv作成・有効化
if [ ! -d "$VENV_DIR" ]; then
    echo "venv を作成中..."
    python3 -m venv "$VENV_DIR"
fi

echo "venv を有効化中..."
source "$VENV_DIR/bin/activate"

echo "依存関係をインストール中..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q pyinstaller

# 2. ビルドディレクトリ準備
echo "ビルドディレクトリを準備中..."
mkdir -p dist build

# 3. Swiftバイナリをビルド
echo "ocr_tool をビルド中..."
swiftc -O -o dist/ocr_tool src/ocr_tool.swift

# 4. Pythonバイナリをビルド
echo "worklog をビルド中..."
pyinstaller -y --onefile --name worklog --distpath dist --workpath build --specpath build --paths src --hidden-import window_info src/main.py

echo "worklog-daily をビルド中..."
pyinstaller -y --onefile --name worklog-daily --distpath dist --workpath build --specpath build src/daily_report.py

echo "worklog-menubar をビルド中..."
pyinstaller -y --onefile --windowed --name worklog-menubar --distpath dist --workpath build --specpath build src/menubar_app.py

echo "worklog-weekly をビルド中..."
pyinstaller -y --onefile --name worklog-weekly --distpath dist --workpath build --specpath build src/weekly_report.py

# 5. コード署名（画面収録権限維持のため）
echo "コード署名中..."
codesign --force --sign - --identifier "com.user.worklog" dist/worklog
codesign --force --sign - --identifier "com.user.worklog.ocr" dist/ocr_tool

echo ""
echo "=== ビルド完了 ==="
echo ""
echo "生成されたバイナリ:"
ls -la dist/
