#!/bin/bash
# 日報を再生成するスクリプト
# 使用法:
#   ./scripts/regenerate-report.sh 2025-12-23          # 日付指定
#   ./scripts/regenerate-report.sh logs/2025-12-23.jsonl  # ファイル指定

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -z "$1" ]; then
    echo "Usage: $0 <date|file>"
    echo "  date: YYYY-MM-DD format (e.g., 2025-12-23)"
    echo "  file: path to .jsonl log file"
    exit 1
fi

ARG="$1"

# ファイルパスか日付かを判定
if [[ "$ARG" == *.jsonl ]]; then
    # ファイルパスの場合、ファイル名から日付を抽出
    FILENAME=$(basename "$ARG" .jsonl)
    DATE="$FILENAME"
elif [[ "$ARG" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    DATE="$ARG"
else
    echo "Error: Invalid argument '$ARG'"
    echo "  Expected YYYY-MM-DD or path to .jsonl file"
    exit 1
fi

echo "Regenerating report for: $DATE"
"$PROJECT_DIR/dist/worklog-daily" "$DATE"
