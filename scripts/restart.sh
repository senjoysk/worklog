#!/bin/bash
# worklog サービス再起動スクリプト

set -e

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "=== worklog サービス再起動 ==="
echo ""

# 1. サービスを停止
echo "サービスを停止中..."
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.worklog.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.worklog.daily.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.worklog.weekly.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.worklog.menubar.plist" 2>/dev/null || true

# メニューバーアプリを終了
pkill -f "worklog-menubar" 2>/dev/null || true

sleep 1

# 2. サービスを開始
echo "サービスを開始中..."
launchctl load "$LAUNCH_AGENTS_DIR/com.user.worklog.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.user.worklog.daily.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.user.worklog.weekly.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.user.worklog.menubar.plist"

echo ""
echo "=== 再起動完了 ==="
echo ""
echo "サービスの状態:"
launchctl list | grep worklog || echo "  (サービスが見つかりません)"
