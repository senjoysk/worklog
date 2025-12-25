# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

macOSで作業ログを自動記録し、Vertex AI Geminiで日報を生成するツール。launchdでバックグラウンド実行される。

## Build Commands

```bash
# 依存関係インストール
pip3 install -r requirements.txt
pip3 install pyinstaller rumps

# 全バイナリをビルド
swiftc -O -o dist/ocr_tool src/ocr_tool.swift
pyinstaller --onefile --name worklog --distpath dist --workpath build --specpath build --paths src --hidden-import window_info src/main.py
pyinstaller --onefile --name worklog-daily --distpath dist --workpath build --specpath build src/daily_report.py
pyinstaller --onefile --windowed --name worklog-menubar --distpath dist --workpath build --specpath build src/menubar_app.py

# 画面収録権限が維持されるよう固定識別子で署名（重要）
codesign --force --sign - --identifier "com.user.worklog" dist/worklog
codesign --force --sign - --identifier "com.user.worklog.ocr" dist/ocr_tool

# インストール/アンインストール
./scripts/install.sh
./scripts/uninstall.sh
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
1. **main.py** (毎分実行): ウィンドウ情報取得 → スクリーンショット → OCR → JSONL保存
2. **daily_report.py** (日次実行): JSONL読み込み → 解析 → Gemini API → Markdown保存
3. **menubar_app.py**: launchdサービスの状態監視・制御UI

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
- `com.user.worklog.menubar` - ログイン時起動（RunAtLoad）

## macOS権限要件
- **画面収録**: worklog, ocr_tool
- **アクセシビリティ**: worklog
