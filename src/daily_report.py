#!/usr/bin/env python3
"""
worklog - 日報生成スクリプト
前日のログを解析してLLMで日報を生成する
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv


def get_project_root() -> Path:
    """プロジェクトルートを取得（バイナリ/スクリプト両対応）"""
    # 環境変数が設定されていればそれを使う
    if 'WORKLOG_ROOT' in os.environ:
        return Path(os.environ['WORKLOG_ROOT'])
    # PyInstallerでビルドされた場合
    if getattr(sys, 'frozen', False):
        # バイナリは dist/ にあるので、親がプロジェクトルート
        return Path(sys.executable).parent.parent
    # 通常のスクリプト実行
    return Path(__file__).parent.parent


PROJECT_ROOT = get_project_root()
sys.path.insert(0, str(PROJECT_ROOT))

# 環境変数を読み込み
load_dotenv(PROJECT_ROOT / '.env')

# ディレクトリ設定
LOGS_DIR = PROJECT_ROOT / 'logs'
REPORTS_DIR = PROJECT_ROOT / 'reports'


def get_credentials():
    """GCP認証情報を取得"""
    import json as json_module
    from google.oauth2 import service_account

    credentials_json = os.getenv('GCP_CREDENTIALS_JSON')
    if credentials_json:
        credentials_info = json_module.loads(credentials_json)
        return service_account.Credentials.from_service_account_info(credentials_info)
    return None


def load_log_file(date: str) -> list:
    """指定日付のログファイルを読み込み"""
    log_file = LOGS_DIR / f'{date}.jsonl'

    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return []

    entries = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return entries


def analyze_logs(entries: list) -> dict:
    """ログを解析して統計情報を抽出"""
    if not entries:
        return {}

    # アプリ使用時間を集計（1エントリ = 1分と仮定）
    app_usage = defaultdict(int)
    app_windows = defaultdict(set)

    for entry in entries:
        app = entry.get('app', 'Unknown')
        window = entry.get('window_title', '')
        app_usage[app] += 1
        if window:
            app_windows[app].add(window)

    # 時間帯別の活動
    hourly_activity = defaultdict(list)
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry['timestamp'])
            hour = ts.strftime('%H:00')
            hourly_activity[hour].append({
                'app': entry.get('app', ''),
                'window': entry.get('window_title', '')
            })
        except (KeyError, ValueError):
            continue

    return {
        'total_entries': len(entries),
        'app_usage': dict(app_usage),
        'app_windows': {k: list(v) for k, v in app_windows.items()},
        'hourly_activity': dict(hourly_activity),
        'first_entry': entries[0].get('timestamp', '') if entries else '',
        'last_entry': entries[-1].get('timestamp', '') if entries else ''
    }


def create_summary_for_llm(entries: list, analysis: dict) -> str:
    """LLMに渡すためのサマリーを作成"""
    lines = []
    lines.append("# 作業ログデータ\n")

    # 基本情報
    lines.append(f"## 記録概要")
    lines.append(f"- 記録開始: {analysis.get('first_entry', 'N/A')}")
    lines.append(f"- 記録終了: {analysis.get('last_entry', 'N/A')}")
    lines.append(f"- 総記録数: {analysis.get('total_entries', 0)}件（約{analysis.get('total_entries', 0)}分）\n")

    # アプリ使用時間
    lines.append("## アプリ使用時間")
    app_usage = analysis.get('app_usage', {})
    sorted_apps = sorted(app_usage.items(), key=lambda x: x[1], reverse=True)
    for app, minutes in sorted_apps[:10]:  # 上位10件
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            lines.append(f"- {app}: {hours}時間{mins}分")
        else:
            lines.append(f"- {app}: {mins}分")

    # 主なウィンドウタイトル（ファイル名などの手がかり）
    lines.append("\n## 作業内容の手がかり（ウィンドウタイトル）")
    app_windows = analysis.get('app_windows', {})
    for app in list(dict(sorted_apps[:5]).keys()):
        windows = app_windows.get(app, [])
        if windows:
            lines.append(f"\n### {app}")
            # 重複を排除して最大10件
            unique_windows = list(set(windows))[:10]
            for window in unique_windows:
                if window:
                    lines.append(f"  - {window}")

    # OCRテキストのサンプル（特徴的なものを抽出）
    lines.append("\n## 画面内容サンプル（OCR抽出）")
    ocr_samples = []
    for entry in entries[::10]:  # 10件ごとにサンプリング
        ocr = entry.get('ocr_text', '')
        if ocr and len(ocr) > 50:
            # 最初の500文字だけ
            sample = ocr[:500].replace('\n', ' ')
            ocr_samples.append(f"[{entry.get('app', '')}] {sample}")

    for sample in ocr_samples[:5]:
        lines.append(f"- {sample[:300]}...")

    return '\n'.join(lines)


def generate_report_with_llm(summary: str, date: str) -> str:
    """Vertex AI Geminiで日報を生成"""
    import vertexai
    from vertexai.generative_models import GenerativeModel

    project_id = os.getenv('GCP_PROJECT_ID')
    location = os.getenv('GCP_LOCATION', 'asia-northeast1')
    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')

    if not project_id:
        raise ValueError("GCP_PROJECT_ID is not set")

    # 認証情報を設定
    credentials = get_credentials()
    vertexai.init(project=project_id, location=location, credentials=credentials)

    model = GenerativeModel(model_name)

    prompt = f"""以下は{date}の作業ログデータです。これを解析して日報を作成してください。

{summary}

---

以下の形式で日報を作成してください：

# {date} 日報

## 作業内容
（時間帯ごとに主な作業内容を箇条書きで記載。推測を含む場合は「～と思われる」などを付ける）

## 使用アプリ
| アプリ名 | 使用時間 | 主な用途 |
|---------|---------|---------|
（使用時間が長い順に記載）

## 得られた知見・メモ
（OCRテキストやウィンドウタイトルから推測される学習内容や気づきがあれば記載。なければ「特になし」）

## 作業中のもの
（まだ完了していないと思われる作業やファイルがあれば記載）

---
注意:
- 推測は明示する
- 個人情報やセンシティブな情報は伏せる
- 簡潔に要点をまとめる
"""

    response = model.generate_content(prompt)
    return response.text


def save_report(content: str, date: str):
    """日報をMarkdownファイルとして保存"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / f'{date}.md'

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Report saved: {report_file}")


def main():
    """メイン処理"""
    # 前日の日付を取得（引数で指定も可能）
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        yesterday = datetime.now() - timedelta(days=1)
        target_date = yesterday.strftime('%Y-%m-%d')

    print(f"Generating daily report for: {target_date}")

    # ログを読み込み
    entries = load_log_file(target_date)
    if not entries:
        print(f"No log entries found for {target_date}")
        return 1

    print(f"Loaded {len(entries)} entries")

    # ログを解析
    analysis = analyze_logs(entries)

    # LLM用のサマリーを作成
    summary = create_summary_for_llm(entries, analysis)

    # LLMで日報を生成
    try:
        report = generate_report_with_llm(summary, target_date)
    except Exception as e:
        print(f"Error generating report: {e}")
        print("Skipping report generation (LLM unavailable)")
        return 1

    # 保存
    save_report(report, target_date)

    print("Done!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
