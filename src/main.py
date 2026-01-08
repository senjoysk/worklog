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
from typing import Optional


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

from window_info import get_active_window_info, get_active_display_number, get_display_bounds, get_display_for_window


# 設定
LOGS_DIR = PROJECT_ROOT / 'logs'
TMP_DIR = PROJECT_ROOT / 'tmp'
OCR_TOOL = PROJECT_ROOT / 'dist' / 'ocr_tool'  # コンパイル済みバイナリ

# OCRテキストの最大長（JSONLが肥大化しないように）
MAX_OCR_TEXT_LENGTH = 5000

# アイドル時間の閾値（秒）- この時間以上操作がなければスキップ
IDLE_THRESHOLD_SECONDS = 300  # 5分


def get_idle_time_seconds() -> float:
    """
    macOSのアイドル時間（最後のユーザー入力からの経過秒数）を取得
    ioregを使用してHIDIdleTimeを取得
    """
    try:
        result = subprocess.run(
            ['ioreg', '-c', 'IOHIDSystem', '-d', '4'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'HIDIdleTime' in line:
                    # "HIDIdleTime" = 1234567890 (ナノ秒)
                    parts = line.split('=')
                    if len(parts) >= 2:
                        # 数値部分を抽出
                        value_str = parts[1].strip()
                        # 数字以外の文字を除去
                        value_str = ''.join(c for c in value_str if c.isdigit())
                        if value_str:
                            idle_ns = int(value_str)
                            return idle_ns / 1_000_000_000  # ナノ秒→秒
    except Exception as e:
        print(f"Warning: Could not get idle time: {e}")
    return 0


def is_screen_locked() -> bool:
    """
    画面がロックされているかを検出
    CGSessionCopyCurrentDictionaryを使用
    """
    try:
        # Quartz経由で画面ロック状態を確認
        result = subprocess.run(
            ['python3', '-c', '''
import Quartz
d = Quartz.CGSessionCopyCurrentDictionary()
if d:
    print("locked" if d.get("CGSSessionScreenIsLocked", False) else "unlocked")
else:
    print("unknown")
'''],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() == 'locked'
    except Exception:
        return False


def should_skip_capture() -> tuple[bool, str]:
    """
    キャプチャをスキップすべきかを判定
    戻り値: (スキップするか, 理由)
    """
    # 画面ロック状態をチェック
    if is_screen_locked():
        return True, "screen_locked"

    # アイドル時間をチェック
    idle_seconds = get_idle_time_seconds()
    if idle_seconds > IDLE_THRESHOLD_SECONDS:
        return True, f"idle_{int(idle_seconds)}s"

    return False, ""


def ensure_directories():
    """必要なディレクトリを作成"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def capture_screen(output_path: Path, window_bounds: Optional[dict] = None, display_number: int = 1) -> bool:
    """
    スクリーンショットを撮影
    
    Args:
        output_path: 出力先パス
        window_bounds: ウィンドウ座標（Quartz座標系：左上原点）
        display_number: ディスプレイ番号
    """
    try:
        # ディスプレイをキャプチャ
        cmd = ['screencapture', '-x', '-D', str(display_number), str(output_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0 or not output_path.exists():
            return False
        
        # boundsがあれば切り取り
        if window_bounds:
            try:
                from PIL import Image
                from Quartz import CGDisplayBounds, CGGetActiveDisplayList
                
                # ディスプレイのQuartz座標を取得
                max_displays = 10
                (err, display_ids, count) = CGGetActiveDisplayList(max_displays, None, None)
                
                if display_number <= count:
                    display_id = display_ids[display_number - 1]
                    disp_bounds = CGDisplayBounds(display_id)
                    disp_x = disp_bounds.origin.x
                    disp_y = disp_bounds.origin.y
                    disp_w = disp_bounds.size.width
                    disp_h = disp_bounds.size.height
                    
                    # ウィンドウ座標
                    win_x = window_bounds.get('X', 0)
                    win_y = window_bounds.get('Y', 0)
                    win_w = window_bounds.get('Width', 0)
                    win_h = window_bounds.get('Height', 0)
                    
                    # ディスプレイ内相対座標
                    rel_x = win_x - disp_x
                    rel_y = win_y - disp_y
                    
                    # 画像を開いてRetinaスケールを計算
                    img = Image.open(output_path)
                    img_w, img_h = img.size
                    scale_x = img_w / disp_w
                    scale_y = img_h / disp_h
                    
                    # スケールを適用
                    crop_x = int(rel_x * scale_x)
                    crop_y = int(rel_y * scale_y)
                    crop_w = int(win_w * scale_x)
                    crop_h = int(win_h * scale_y)
                    
                    # 範囲チェック
                    crop_x = max(0, crop_x)
                    crop_y = max(0, crop_y)
                    crop_right = min(crop_x + crop_w, img_w)
                    crop_bottom = min(crop_y + crop_h, img_h)
                    
                    if crop_right > crop_x and crop_bottom > crop_y:
                        cropped = img.crop((crop_x, crop_y, crop_right, crop_bottom))
                        cropped.save(output_path)
                    
            except Exception:
                pass  # クロップ失敗時はフル画像を使用
        
        return True
        
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

    # アイドル/ロック状態をチェック
    skip, reason = should_skip_capture()
    if skip:
        print(f"[{datetime.now().isoformat()}] Skipping capture: {reason}")
        return 0

    # 1. アクティブウィンドウ情報を取得
    window_info = get_active_window_info()
    if not window_info:
        print("Warning: Could not get window info")
        app_name = ""
        window_title = ""
        window_bounds = None
    else:
        app_name = window_info.app_name
        window_title = window_info.window_title
        window_bounds = window_info.window_bounds



    # 2. アクティブディスプレイを特定（ウィンドウ座標から判断）
    if window_bounds:
        display_number = get_display_for_window(window_bounds)
    else:
        display_number = get_active_display_number()


    # 3. スクリーンショットを撮影（ディスプレイ全体→ウィンドウ領域を切り取り）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_path = TMP_DIR / f'screenshot_{timestamp}.png'

    if not capture_screen(screenshot_path, window_bounds=window_bounds, display_number=display_number):
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
