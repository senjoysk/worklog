# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

macOSで作業ログを自動記録し、Vertex AI Geminiで日報を生成するツール。launchdでバックグラウンド実行される。

## Build Commands

```bash
# 依存関係インストール
pip3 install -r requirements.txt
pip3 install pyinstaller rumps

# 全バイナリをビルド（推奨）
./scripts/build.sh

# インストール/アンインストール
./scripts/install.sh
./scripts/uninstall.sh

# サービス再起動
./scripts/restart.sh

# 日報再生成
./scripts/regenerate-report.sh 2025-01-15
```

## Manual Execution

```bash
# キャプチャを1回実行
./dist/worklog

# 特定日付の日報を生成
./dist/worklog-daily 2025-01-15

# メニューバーアプリ起動
open dist/worklog-menubar.app
```

## Architecture

### データフロー
1. **main.py** (毎分実行): アイドル/ロック検出 → ウィンドウ情報取得 → スクリーンショット → OCR → JSONL保存
   - 5分以上アイドル or 画面ロック中はスキップ
2. **daily_report.py** (日次実行): JSONL読み込み → 解析 → Gemini API → Markdown保存 → Slack投稿
3. **weekly_report.py** (週次実行): 月〜金のJSONL読み込み → 週次解析 → Gemini API → Markdown保存 → Slack投稿
4. **menubar_app.py**: launchdサービスの状態監視・制御UI

### コンポーネント依存関係
```
main.py
  └── window_info.py (PyObjC経由でアクティブウィンドウ取得)
  └── ocr_tool (Swiftバイナリ、Vision Framework使用)

daily_report.py
  └── .env (GCP認証情報)
  └── Vertex AI Gemini API

menubar_app.py
  └── rumps (メニューバーUI)
  └── launchctl (サービス制御)
```

### パス解決
スクリプトとPyInstallerバイナリ両方で動作するよう、`get_project_root()` で以下の順にプロジェクトルートを決定:
1. 環境変数 `WORKLOG_ROOT`
2. `sys.frozen` (PyInstallerバイナリ) → `sys.executable` の親の親
3. `__file__` の親の親

### launchdサービス
- `com.user.worklog` - 毎分実行（StartInterval: 60）
- `com.user.worklog.daily` - 毎日00:05実行（StartCalendarInterval）
- `com.user.worklog.weekly` - 毎週金曜18:00実行（StartCalendarInterval）
- `com.user.worklog.menubar` - ログイン時起動（RunAtLoad）

## 設定値（main.py）
- `IDLE_THRESHOLD_SECONDS = 300` - アイドル検出閾値（5分）
- `MAX_OCR_TEXT_LENGTH = 5000` - OCRテキスト最大長

## macOS権限要件
- **画面収録**: worklog, ocr_tool
- **アクセシビリティ**: worklog
