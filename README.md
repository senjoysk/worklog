# worklog

macOSで作業ログを自動記録し、LLMで日報を生成するツール。

## 機能

- **毎分実行**: アクティブウィンドウの情報をキャプチャ
  - アプリ名・ウィンドウタイトルの取得
  - アクティブディスプレイのスクリーンショット
  - Vision Framework による OCR テキスト抽出
  - JSONL 形式でログ保存
  - **アイドル検出**: 5分以上操作がない場合は自動スキップ
  - **画面ロック検出**: ロック中は自動スキップ

- **日次実行**: 前日のログから日報を自動生成
  - Vertex AI Gemini 2.5 Flash による解析
  - Markdown 形式で保存
  - 作業ごとの合計時間を集計

- **メニューバーアプリ**: サービスの状態管理
  - メニューバーにアイコン表示（●実行中 / ○停止中）
  - キャプチャ・日報生成サービスの停止/再開
  - ログイン時に自動起動

## セットアップ

### 1. GCP認証情報の準備

```bash
# gcloud CLIでログイン
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Vertex AI APIを有効化
gcloud services enable aiplatform.googleapis.com

# サービスアカウントを作成
gcloud iam service-accounts create worklog-sa --display-name="Worklog Service Account"

# 権限を付与
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:worklog-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# キーをダウンロード
gcloud iam service-accounts keys create ~/worklog-key.json \
  --iam-account=worklog-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集:
```env
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=asia-northeast1
GCP_CREDENTIALS_JSON={"type":"service_account",...}  # JSONキーの内容をペースト
GEMINI_MODEL=gemini-2.5-flash-preview-05-20
```

### 3. ビルド

```bash
# 依存関係のインストール
pip3 install -r requirements.txt
pip3 install pyinstaller rumps

# ビルドスクリプトで全バイナリをビルド
./scripts/build.sh
```

<details>
<summary>手動でビルドする場合</summary>

```bash
# Swiftバイナリをビルド
swiftc -O -o dist/ocr_tool src/ocr_tool.swift

# Pythonバイナリをビルド
pyinstaller --onefile --name worklog --distpath dist --workpath build --specpath build --paths src --hidden-import window_info src/main.py
pyinstaller --onefile --name worklog-daily --distpath dist --workpath build --specpath build src/daily_report.py
pyinstaller --onefile --windowed --name worklog-menubar --distpath dist --workpath build --specpath build src/menubar_app.py

# コード署名（画面収録権限維持のため）
codesign --force --sign - --identifier "com.user.worklog" dist/worklog
codesign --force --sign - --identifier "com.user.worklog.ocr" dist/ocr_tool
```

</details>

### 4. インストール

```bash
chmod +x scripts/install.sh scripts/uninstall.sh
./scripts/install.sh
```

### 5. macOS権限の設定

初回実行時に以下の権限が必要です:

1. **システム設定 > プライバシーとセキュリティ > 画面収録**
   - `worklog` と `ocr_tool` を許可

2. **システム設定 > プライバシーとセキュリティ > アクセシビリティ**
   - `worklog` を許可

## 使い方

### 手動実行

```bash
# キャプチャを1回実行
./dist/worklog

# 特定日付の日報を生成
./dist/worklog-daily 2025-01-15

# 日報を再生成（スクリプト使用）
./scripts/regenerate-report.sh 2025-01-15
```

### サービスの管理

```bash
# 状態確認
launchctl list | grep worklog
# 出力例: -  0  com.user.worklog
# 最初の列: PID（待機中は -）
# 2番目の列: 終了コード（0=正常）

# 全サービスを再起動（スクリプト使用）
./scripts/restart.sh

# 手動で停止
launchctl unload ~/Library/LaunchAgents/com.user.worklog.plist
launchctl unload ~/Library/LaunchAgents/com.user.worklog.daily.plist
launchctl unload ~/Library/LaunchAgents/com.user.worklog.menubar.plist

# 手動で再開
launchctl load ~/Library/LaunchAgents/com.user.worklog.plist
launchctl load ~/Library/LaunchAgents/com.user.worklog.daily.plist
launchctl load ~/Library/LaunchAgents/com.user.worklog.menubar.plist
```

### ログの確認

```bash
# 実行ログ
tail -f logs/worklog.log

# エラーログ
tail -f logs/worklog.error.log

# キャプチャされたデータ（今日分）
tail -f logs/$(date +%Y-%m-%d).jsonl
```

### アンインストール

```bash
./scripts/uninstall.sh
```

## ファイル構成

```
worklog/
├── src/
│   ├── main.py           # キャプチャスクリプト（ソース）
│   ├── daily_report.py   # 日報生成スクリプト（ソース）
│   ├── menubar_app.py    # メニューバーアプリ（ソース）
│   ├── window_info.py    # ウィンドウ情報取得
│   └── ocr_tool.swift    # Vision Framework OCR（ソース）
├── dist/                 # ビルド成果物（Git管理外）
│   ├── worklog           # キャプチャ用バイナリ
│   ├── worklog-daily     # 日報生成用バイナリ
│   ├── worklog-menubar.app  # メニューバーアプリ
│   └── ocr_tool          # OCR用バイナリ
├── logs/
│   └── YYYY-MM-DD.jsonl  # 日付ごとのログ
├── reports/
│   └── YYYY-MM-DD.md     # 生成された日報
├── tmp/                  # 一時ファイル（スクリーンショット等）
├── launchd/
│   ├── com.user.worklog.plist        # 毎分実行用
│   ├── com.user.worklog.daily.plist  # 日次実行用
│   └── com.user.worklog.menubar.plist  # メニューバーアプリ自動起動用
├── scripts/
│   ├── build.sh          # 全バイナリのビルド
│   ├── install.sh        # インストール
│   ├── uninstall.sh      # アンインストール
│   ├── restart.sh        # サービス再起動
│   └── regenerate-report.sh  # 日報再生成
├── .env                  # 環境変数（Git管理外）
├── .env.example
└── requirements.txt
```

## ログ形式（JSONL）

```json
{"timestamp": "2025-01-15T14:32:00", "app": "Visual Studio Code", "window_title": "main.py - worklog", "display": 1, "ocr_text": "..."}
```

## 日報形式

```markdown
# 2025-01-15 日報

## 作業内容
（作業ごとに合計時間を記載）
- worklogプロジェクトの開発 (3h)
- ドキュメント作成 (2h)

## 使用アプリ
| アプリ名 | 使用時間 | 主な用途 |
|---------|---------|---------|
| VS Code | 4時間30分 | コーディング |
| Chrome | 2時間 | 調査・ドキュメント閲覧 |

## 得られた知見・メモ
- Vision Frameworkは日本語OCRも対応

## 作業中のもの
- README.mdの完成
```

## トラブルシューティング

### スクリーンショットが取れない
→ 画面収録の権限を確認

### ウィンドウ名が取れない
→ アクセシビリティの権限を確認

### 日報が生成されない
→ `.env` のGCP認証情報を確認
→ `logs/daily_report.error.log` を確認

### launchdが動かない
```bash
# ログを確認
cat ~/Work/senjoysk/worklog/logs/worklog.error.log

# plistの文法チェック
plutil ~/Library/LaunchAgents/com.user.worklog.plist
```
