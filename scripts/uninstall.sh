#!/bin/bash
# worklog アンインストールスクリプト

set -e

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "=== worklog アンインストール ==="

# 1. launchdから削除
echo "サービスを停止中..."
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.worklog.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.worklog.daily.plist" 2>/dev/null || true

# 2. plistファイルを削除
echo "設定ファイルを削除中..."
rm -f "$LAUNCH_AGENTS_DIR/com.user.worklog.plist"
rm -f "$LAUNCH_AGENTS_DIR/com.user.worklog.daily.plist"

echo ""
echo "=== アンインストール完了 ==="
echo ""
echo "注意: ログと日報ファイルは削除されていません。"
echo "必要に応じて手動で削除してください。"
