#!/usr/bin/env python3
"""アクティブウィンドウの情報を取得するモジュール"""

import subprocess
import json
from typing import Optional
from dataclasses import dataclass


@dataclass
class WindowInfo:
    """ウィンドウ情報"""
    app_name: str
    window_title: str
    window_bounds: Optional[dict] = None  # {x, y, width, height}


def get_active_window_info() -> Optional[WindowInfo]:
    """AppleScriptでアクティブウィンドウの情報を取得"""

    applescript = '''
    use framework "AppKit"
    use scripting additions

    set frontApp to (info for (path to frontmost application))
    set appName to short name of frontApp

    set windowTitle to ""

    try
        tell application "System Events"
            tell (first process whose frontmost is true)
                set windowTitle to name of front window
            end tell
        end tell
    end try

    -- 改行区切りで出力（Python側でJSONに変換）
    return appName & linefeed & windowTitle
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return None

        output = result.stdout.strip()
        lines = output.split('\n', 1)  # 最大2分割
        app_name = lines[0] if len(lines) > 0 else ''
        window_title = lines[1] if len(lines) > 1 else ''

        return WindowInfo(
            app_name=app_name,
            window_title=window_title
        )

    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"Error getting window info: {e}")
        return None


def get_active_display_number() -> int:
    """
    アクティブウィンドウがあるディスプレイ番号を取得
    戻り値: 1 = メインディスプレイ, 2 = 外部ディスプレイ, etc.
    """

    applescript = '''
    use framework "AppKit"
    use scripting additions

    -- アクティブウィンドウの位置を取得
    set windowX to 0
    try
        tell application "System Events"
            tell (first process whose frontmost is true)
                set windowPos to position of front window
                set windowX to item 1 of windowPos
            end tell
        end tell
    end try

    -- 各スクリーンの情報を取得してウィンドウがどのスクリーンにあるか判定
    set screenList to current application's NSScreen's screens()
    set screenCount to count of screenList

    set displayNum to 1
    repeat with i from 1 to screenCount
        set scr to item i of screenList
        set scrFrame to scr's frame()
        set scrX to (current application's NSMinX(scrFrame)) as integer
        set scrWidth to (current application's NSWidth(scrFrame)) as integer

        if windowX >= scrX and windowX < (scrX + scrWidth) then
            set displayNum to i
            exit repeat
        end if
    end repeat

    return displayNum
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return int(result.stdout.strip())

    except (subprocess.TimeoutExpired, ValueError, Exception):
        pass

    return 1  # デフォルトはメインディスプレイ


def get_display_count() -> int:
    """接続されているディスプレイの数を取得"""

    applescript = '''
    use framework "AppKit"
    set screenList to current application's NSScreen's screens()
    return count of screenList
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return int(result.stdout.strip())

    except (subprocess.TimeoutExpired, ValueError, Exception):
        pass

    return 1


if __name__ == '__main__':
    # テスト実行
    info = get_active_window_info()
    if info:
        print(f"App: {info.app_name}")
        print(f"Window: {info.window_title}")

    display = get_active_display_number()
    print(f"Active Display: {display}")

    count = get_display_count()
    print(f"Display Count: {count}")
