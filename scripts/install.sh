#!/bin/bash
# worklog インストールスクリプト

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "=== worklog インストール ==="

# 1. Python依存関係のインストール
echo "Python依存関係をインストール中..."
pip3 install -r "$PROJECT_DIR/requirements.txt"

# 2. ディレクトリを作成
echo "ディレクトリを作成中..."
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/reports"
mkdir -p "$PROJECT_DIR/tmp"
mkdir -p "$LAUNCH_AGENTS_DIR"

# 3. .envファイルの確認
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ""
    echo "警告: .env ファイルが見つかりません"
    echo ".env.example をコピーして設定してください:"
    echo "  cp $PROJECT_DIR/.env.example $PROJECT_DIR/.env"
    echo "  # その後、GCP認証情報を設定"
    echo ""
fi

# 4. launchd plistをコピー
echo "launchd設定をインストール中..."
cp "$PROJECT_DIR/launchd/com.user.worklog.plist" "$LAUNCH_AGENTS_DIR/"
cp "$PROJECT_DIR/launchd/com.user.worklog.daily.plist" "$LAUNCH_AGENTS_DIR/"
cp "$PROJECT_DIR/launchd/com.user.worklog.menubar.plist" "$LAUNCH_AGENTS_DIR/"

# 5. launchdに登録
echo "サービスを起動中..."
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.worklog.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.worklog.daily.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.worklog.menubar.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/com.user.worklog.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.user.worklog.daily.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.user.worklog.menubar.plist"

echo ""
echo "=== インストール完了 ==="
echo ""
echo "worklogは毎分実行されます。"
echo "日報は毎日 00:05 に生成されます。"
echo "メニューバーアプリが起動しました。"
echo ""
echo "ログファイル:"
echo "  $PROJECT_DIR/logs/"
echo ""
echo "日報ファイル:"
echo "  $PROJECT_DIR/reports/"
echo ""
echo "サービスの状態確認:"
echo "  launchctl list | grep worklog"
echo ""
echo "注意: 初回実行時に「画面収録」と「アクセシビリティ」の"
echo "権限を求められる場合があります。許可してください。"
