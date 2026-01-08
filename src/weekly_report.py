#!/usr/bin/env python3
"""
worklog - 週報生成スクリプト
金曜18時に実行され、月〜金のログを解析してLLMで週報を生成する
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
    if 'WORKLOG_ROOT' in os.environ:
        return Path(os.environ['WORKLOG_ROOT'])
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.parent
    return Path(__file__).parent.parent


PROJECT_ROOT = get_project_root()
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / '.env')

LOGS_DIR = PROJECT_ROOT / 'logs'
REPORTS_DIR = PROJECT_ROOT / 'reports'
SLACK_POSTED_FILE = REPORTS_DIR / '.slack_posted'


def get_credentials():
    """GCP認証情報を取得"""
    import json as json_module
    from google.oauth2 import service_account

    credentials_json = os.getenv('GCP_CREDENTIALS_JSON')
    if credentials_json:
        credentials_info = json_module.loads(credentials_json)
        return service_account.Credentials.from_service_account_info(credentials_info)
    return None


def get_week_dates(target_date: datetime) -> list:
    """対象日を含む週の月〜金の日付リストを取得"""
    # 月曜日を基準に計算
    weekday = target_date.weekday()
    monday = target_date - timedelta(days=weekday)

    dates = []
    for i in range(5):  # 月〜金
        date = monday + timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))
    return dates


def get_week_number(target_date: datetime) -> str:
    """ISO週番号を取得 (例: 2026-W01)"""
    iso_cal = target_date.isocalendar()
    return f"{iso_cal[0]}-W{iso_cal[1]:02d}"


def load_log_file(date: str) -> list:
    """指定日付のログファイルを読み込み"""
    log_file = LOGS_DIR / f'{date}.jsonl'

    if not log_file.exists():
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


def load_week_logs(dates: list) -> dict:
    """週の全ログを読み込み"""
    week_logs = {}
    for date in dates:
        entries = load_log_file(date)
        if entries:
            week_logs[date] = entries
    return week_logs


def analyze_week_logs(week_logs: dict) -> dict:
    """週のログを解析して統計情報を抽出"""
    all_entries = []
    daily_stats = {}

    for date, entries in week_logs.items():
        all_entries.extend(entries)

        # 日ごとの統計
        app_usage = defaultdict(int)
        for entry in entries:
            app = entry.get('app', 'Unknown')
            app_usage[app] += 1

        daily_stats[date] = {
            'total_entries': len(entries),
            'app_usage': dict(app_usage)
        }

    if not all_entries:
        return {}

    # 週全体のアプリ使用時間
    app_usage = defaultdict(int)
    app_windows = defaultdict(set)

    for entry in all_entries:
        app = entry.get('app', 'Unknown')
        window = entry.get('window_title', '')
        app_usage[app] += 1
        if window:
            app_windows[app].add(window)

    return {
        'total_entries': len(all_entries),
        'app_usage': dict(app_usage),
        'app_windows': {k: list(v) for k, v in app_windows.items()},
        'daily_stats': daily_stats,
        'dates': list(week_logs.keys())
    }


def create_weekly_summary_for_llm(week_logs: dict, analysis: dict) -> str:
    """LLMに渡すための週次サマリーを作成"""
    lines = []
    lines.append("# 週間作業ログデータ\n")

    # 基本情報
    lines.append("## 記録概要")
    lines.append(f"- 対象日: {', '.join(analysis.get('dates', []))}")
    lines.append(f"- 総記録数: {analysis.get('total_entries', 0)}件（約{analysis.get('total_entries', 0)}分）\n")

    # 日ごとの作業時間
    lines.append("## 日ごとの作業時間")
    for date, stats in analysis.get('daily_stats', {}).items():
        minutes = stats.get('total_entries', 0)
        hours = minutes // 60
        mins = minutes % 60
        lines.append(f"- {date}: {hours}時間{mins}分")

    # 週全体のアプリ使用時間
    lines.append("\n## 週全体のアプリ使用時間")
    app_usage = analysis.get('app_usage', {})
    sorted_apps = sorted(app_usage.items(), key=lambda x: x[1], reverse=True)
    for app, minutes in sorted_apps[:10]:
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            lines.append(f"- {app}: {hours}時間{mins}分")
        else:
            lines.append(f"- {app}: {mins}分")

    # 主なウィンドウタイトル
    lines.append("\n## 作業内容の手がかり（ウィンドウタイトル）")
    app_windows = analysis.get('app_windows', {})
    for app in list(dict(sorted_apps[:5]).keys()):
        windows = app_windows.get(app, [])
        if windows:
            lines.append(f"\n### {app}")
            unique_windows = list(set(windows))[:15]
            for window in unique_windows:
                if window:
                    lines.append(f"  - {window}")

    # OCRテキストのサンプル（各日から抽出）
    lines.append("\n## 画面内容サンプル（OCR抽出）")
    for date, entries in week_logs.items():
        if entries:
            lines.append(f"\n### {date}")
            samples = []
            for entry in entries[::20]:  # 20件ごとにサンプリング
                ocr = entry.get('ocr_text', '')
                if ocr and len(ocr) > 50:
                    sample = ocr[:300].replace('\n', ' ')
                    samples.append(f"[{entry.get('app', '')}] {sample}")
            for sample in samples[:3]:
                lines.append(f"- {sample}...")

    return '\n'.join(lines)


def generate_weekly_report_with_llm(summary: str, week_number: str, dates: list) -> str:
    """Vertex AI Geminiで週報を生成"""
    import vertexai
    from vertexai.generative_models import GenerativeModel

    project_id = os.getenv('GCP_PROJECT_ID')
    location = os.getenv('GCP_LOCATION', 'asia-northeast1')
    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')

    if not project_id:
        raise ValueError("GCP_PROJECT_ID is not set")

    credentials = get_credentials()
    vertexai.init(project=project_id, location=location, credentials=credentials)

    model = GenerativeModel(model_name)

    date_range = f"{dates[0]} 〜 {dates[-1]}" if dates else week_number

    prompt = f"""以下は{date_range}の週間作業ログデータです。これを解析して週報を作成してください。

{summary}

---

以下の形式で週報を作成してください：

# {week_number} 週報（{date_range}）

## 今週の作業サマリー
（主要な作業を箇条書きで。合計時間も記載）
例: - ○○プロジェクトの開発 (12h)
    - △△の調査・設計 (5h)

## 使用アプリ（週間）
| アプリ名 | 使用時間 | 主な用途 |
|---------|---------|---------|
（使用時間が長い順に上位5件）

## 日別の活動概要
（各日の主な作業を1-2行で）

## 学習・調査メモ
（今週調べたこと、学んだこと、気づきなど。OCRテキストやウィンドウタイトルから推測）

## 振り返り
（今週の良かった点、改善すべき点、気づきなど）

## 来週の準備事項
（作業中のタスク、来週やるべきこと、土日で準備できることなど）

---
注意:
- 推測は明示する
- 個人情報やセンシティブな情報は伏せる
- 簡潔に要点をまとめる
- 金曜日のデータは18時時点の暫定データの可能性がある
"""

    response = model.generate_content(prompt)
    return response.text


def save_report(content: str, week_number: str):
    """週報をMarkdownファイルとして保存"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / f'{week_number}.md'

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Report saved: {report_file}")


def markdown_to_slack(text: str) -> str:
    """MarkdownをSlack mrkdwn形式に変換"""
    import re
    lines = text.split('\n')
    result = []
    in_table = False
    table_rows = []

    for line in lines:
        if '|' in line and line.strip().startswith('|'):
            in_table = True
            if re.match(r'^\|[\s\-:]+\|', line):
                continue
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if cells:
                table_rows.append(cells)
            continue
        elif in_table:
            if table_rows:
                headers = table_rows[0] if table_rows else []
                for row in table_rows[1:]:
                    if len(row) >= len(headers):
                        parts = [f"{headers[i]}: {row[i]}" for i in range(len(headers)) if row[i]]
                        result.append(f"• {' / '.join(parts)}")
                table_rows = []
            in_table = False

        if line.startswith('# '):
            result.append(f"\n*{line[2:].strip()}*")
        elif line.startswith('## '):
            result.append(f"\n*{line[3:].strip()}*")
        elif line.startswith('### '):
            result.append(f"*{line[4:].strip()}*")
        else:
            converted = re.sub(r'\*\*(.+?)\*\*', r'*\1*', line)
            result.append(converted)

    if table_rows:
        headers = table_rows[0] if table_rows else []
        for row in table_rows[1:]:
            if len(row) >= len(headers):
                parts = [f"{headers[i]}: {row[i]}" for i in range(len(headers)) if row[i]]
                result.append(f"• {' / '.join(parts)}")

    return '\n'.join(result)


def is_slack_posted(identifier: str) -> bool:
    """指定識別子がSlackに投稿済みかチェック"""
    if not SLACK_POSTED_FILE.exists():
        return False
    return identifier in SLACK_POSTED_FILE.read_text().splitlines()


def mark_slack_posted(identifier: str):
    """Slack投稿済みとしてマーク"""
    SLACK_POSTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SLACK_POSTED_FILE, 'a') as f:
        f.write(f"{identifier}\n")


def post_to_slack(content: str, week_number: str) -> bool:
    """週報をSlackに投稿"""
    # 既に投稿済みならスキップ
    if is_slack_posted(week_number):
        print(f"Already posted to Slack for {week_number}, skipping")
        return False

    slack_token = os.getenv('SLACK_BOT_TOKEN')
    channel_id = os.getenv('SLACK_CHANNEL_ID')

    if not slack_token or not channel_id:
        print("Slack settings not configured, skipping Slack post")
        return False

    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError

        client = WebClient(token=slack_token)

        slack_content = markdown_to_slack(content)
        response = client.chat_postMessage(
            channel=channel_id,
            text=f"📊 *{week_number} 週報*\n{slack_content}",
            mrkdwn=True
        )

        # 投稿成功したら記録
        mark_slack_posted(week_number)
        print(f"Posted to Slack: {response['ts']}")
        return True

    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}")
        return False
    except Exception as e:
        print(f"Failed to post to Slack: {e}")
        return False


def main():
    """メイン処理"""
    # 対象日を取得（引数で指定も可能、デフォルトは今日）
    if len(sys.argv) > 1:
        target_date = datetime.strptime(sys.argv[1], '%Y-%m-%d')
    else:
        target_date = datetime.now()

    week_number = get_week_number(target_date)
    dates = get_week_dates(target_date)

    print(f"Generating weekly report for: {week_number}")
    print(f"Date range: {dates[0]} to {dates[-1]}")

    # 週のログを読み込み
    week_logs = load_week_logs(dates)
    if not week_logs:
        print(f"No log entries found for week {week_number}")
        return 1

    total_entries = sum(len(entries) for entries in week_logs.values())
    print(f"Loaded {total_entries} entries from {len(week_logs)} days")

    # ログを解析
    analysis = analyze_week_logs(week_logs)

    # LLM用のサマリーを作成
    summary = create_weekly_summary_for_llm(week_logs, analysis)

    # LLMで週報を生成
    try:
        report = generate_weekly_report_with_llm(summary, week_number, dates)
    except Exception as e:
        print(f"Error generating report: {e}")
        return 1

    # 保存
    save_report(report, week_number)

    # Slackに投稿
    post_to_slack(report, week_number)

    print("Done!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
