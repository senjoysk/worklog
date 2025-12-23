#!/usr/bin/env python3
"""
worklog - メインキャプチャスクリプト
毎分実行され、アクティブウィンドウの情報とスクリーンショットをログに記録する
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path


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
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from window_info import get_active_window_info, get_active_display_number


# 設定
LOGS_DIR = PROJECT_ROOT / 'logs'
TMP_DIR = PROJECT_ROOT / 'tmp'
OCR_TOOL = PROJECT_ROOT / 'dist' / 'ocr_tool'  # コンパイル済みバイナリ

# OCRテキストの最大長（JSONLが肥大化しないように）
MAX_OCR_TEXT_LENGTH = 5000


def ensure_directories():
    """必要なディレクトリを作成"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def capture_screen(display_number: int, output_path: Path) -> bool:
    """指定ディスプレイのスクリーンショットを撮影"""
    try:
        result = subprocess.run(
            ['screencapture', '-x', '-D', str(display_number), str(output_path)],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0 and output_path.exists()
    except subprocess.TimeoutExpired:
        print("Error: screencapture timed out")
        return False
    except Exception as e:
        print(f"Error: screencapture failed: {e}")
        return False


def run_ocr(image_path: Path) -> str:
    """OCRツールを実行してテキストを抽出"""
    try:
        # コンパイル済みバイナリを実行
        result = subprocess.run(
            [str(OCR_TOOL), str(image_path)],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            text = result.stdout.strip()
            # テキストが長すぎる場合は切り詰め
            if len(text) > MAX_OCR_TEXT_LENGTH:
                text = text[:MAX_OCR_TEXT_LENGTH] + '...[truncated]'
            return text

        print(f"OCR error: {result.stderr}")
        return ""

    except subprocess.TimeoutExpired:
        print("Error: OCR timed out")
        return ""
    except Exception as e:
        print(f"Error: OCR failed: {e}")
        return ""


def get_log_file_path() -> Path:
    """今日の日付に基づいたログファイルパスを取得"""
    today = datetime.now().strftime('%Y-%m-%d')
    return LOGS_DIR / f'{today}.jsonl'


def append_log(data: dict):
    """ログファイルにJSONL形式で追記"""
    log_file = get_log_file_path()

    with open(log_file, 'a', encoding='utf-8') as f:
        json_line = json.dumps(data, ensure_ascii=False)
        f.write(json_line + '\n')


def cleanup_temp_files():
    """一時ファイルを削除"""
    for file in TMP_DIR.glob('*.png'):
        try:
            file.unlink()
        except Exception as e:
            print(f"Warning: Could not delete {file}: {e}")


def main():
    """メイン処理"""
    print(f"[{datetime.now().isoformat()}] Starting capture...")

    # ディレクトリ準備
    ensure_directories()

    # 1. アクティブウィンドウ情報を取得
    window_info = get_active_window_info()
    if not window_info:
        print("Warning: Could not get window info")
        app_name = ""
        window_title = ""
    else:
        app_name = window_info.app_name
        window_title = window_info.window_title

    # 2. アクティブディスプレイを特定
    display_number = get_active_display_number()

    # 3. スクリーンショットを撮影
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_path = TMP_DIR / f'screenshot_{timestamp}.png'

    if not capture_screen(display_number, screenshot_path):
        print("Error: Failed to capture screen")
        return 1

    # 4. OCRでテキスト抽出
    ocr_text = run_ocr(screenshot_path)

    # 5. ログに記録
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'app': app_name,
        'window_title': window_title,
        'display': display_number,
        'ocr_text': ocr_text
    }

    append_log(log_entry)

    # 6. 一時ファイルを削除
    cleanup_temp_files()

    print(f"[{datetime.now().isoformat()}] Capture complete: {app_name} - {window_title}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
