#!/usr/bin/env python3
"""アクティブウィンドウの情報を取得するモジュール"""

import subprocess
import json
from typing import Optional
from dataclasses import dataclass

from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListExcludeDesktopElements,
    kCGNullWindowID
)


@dataclass
class WindowInfo:
    """ウィンドウ情報"""
    app_name: str
    window_title: str
    window_id: Optional[int] = None  # CGWindowID
    window_bounds: Optional[dict] = None  # {x, y, width, height}  # {x, y, width, height}


def _get_frontmost_window_id(app_name: str, window_title: str) -> tuple:
    """
    フロントモストウィンドウのCGWindowIDとboundsを取得
    
    CGWindowListは前面から背面の順で返されるため、
    最初に見つかった十分なサイズのウィンドウを選択
    
    Returns:
        tuple: (window_id, bounds) - boundsは {X, Y, Width, Height} の辞書
    """
    MIN_SIZE = 100  # ツールバー等を除外するための最小サイズ
    
    try:
        # すべてのオンスクリーンウィンドウを取得（デスクトップ要素は除外）
        options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        
        if not window_list:
            return None, None
        
        # 前面から順に探索し、十分なサイズのウィンドウを選択
        for window in window_list:
            owner_name = window.get('kCGWindowOwnerName', '')
            layer = window.get('kCGWindowLayer', 0)
            bounds = window.get('kCGWindowBounds', {})
            
            # レイヤー0は通常のウィンドウ
            if layer != 0:
                continue
            
            # アプリ名が一致するかチェック（部分一致も許可）
            if owner_name == app_name or app_name in owner_name or owner_name in app_name:
                bounds_dict = dict(bounds) if bounds else {}
                width = bounds_dict.get('Width', 0)
                height = bounds_dict.get('Height', 0)
                
                # 十分なサイズか確認（ツールバー等を除外）
                if width >= MIN_SIZE and height >= MIN_SIZE:
                    window_id = window.get('kCGWindowNumber')
                    return window_id, bounds_dict
        
        return None, None
        
    except Exception as e:
        print(f"Error getting window ID: {e}")
        return None, None


def get_active_window_info() -> Optional[WindowInfo]:
    """アクティブウィンドウの情報を取得（ウィンドウID・bounds含む）"""
    
    # まずAppleScriptでアプリ名とウィンドウタイトルを取得
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

    -- 改行区切りで出力
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
        lines = output.split('\n', 1)
        app_name = lines[0] if len(lines) > 0 else ''
        window_title = lines[1] if len(lines) > 1 else ''

        # ウィンドウIDとboundsを取得
        window_id, window_bounds = _get_frontmost_window_id(app_name, window_title)

        return WindowInfo(
            app_name=app_name,
            window_title=window_title,
            window_id=window_id,
            window_bounds=window_bounds
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
    set windowY to 0
    try
        tell application "System Events"
            tell (first process whose frontmost is true)
                set windowPos to position of front window
                set windowX to item 1 of windowPos
                set windowY to item 2 of windowPos
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
        set scrY to (current application's NSMinY(scrFrame)) as integer
        set scrWidth to (current application's NSWidth(scrFrame)) as integer
        set scrHeight to (current application's NSHeight(scrFrame)) as integer

        -- X座標とY座標の両方でスクリーン内かどうか判定
        if windowX >= scrX and windowX < (scrX + scrWidth) and windowY >= scrY and windowY < (scrY + scrHeight) then
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

    return 1  # デフォルトはメインディスプレイ  # デフォルトはメインディスプレイ


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


def get_display_bounds(display_number: int) -> Optional[dict]:
    """
    指定ディスプレイの座標情報を取得
    
    Args:
        display_number: ディスプレイ番号（1-indexed）
    
    Returns:
        dict: {X, Y, Width, Height} - グローバル座標系での位置とサイズ
    """
    applescript = f'''
    use framework "AppKit"
    use scripting additions
    
    set screenList to current application's NSScreen's screens()
    set screenCount to count of screenList
    
    if {display_number} > screenCount then
        return "error"
    end if
    
    set scr to item {display_number} of screenList
    set scrFrame to scr's frame()
    
    set scrX to (current application's NSMinX(scrFrame)) as integer
    set scrY to (current application's NSMinY(scrFrame)) as integer
    set scrWidth to (current application's NSWidth(scrFrame)) as integer
    set scrHeight to (current application's NSHeight(scrFrame)) as integer
    
    -- 改行区切りで出力
    return (scrX as text) & linefeed & (scrY as text) & linefeed & (scrWidth as text) & linefeed & (scrHeight as text)
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip() != "error":
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 4:
                return {
                    'X': int(lines[0]),
                    'Y': int(lines[1]),
                    'Width': int(lines[2]),
                    'Height': int(lines[3])
                }
    
    except (subprocess.TimeoutExpired, ValueError, Exception):
        pass
    
    return None


def get_display_for_window(window_bounds: dict) -> int:
    """
    ウィンドウ座標から、そのウィンドウがあるディスプレイ番号を取得
    
    Args:
        window_bounds: ウィンドウの座標（Quartz座標系：左上原点）
    
    Returns:
        int: ディスプレイ番号（1-indexed）
    """
    if not window_bounds:
        return 1
    
    try:
        from Quartz import CGDisplayBounds, CGGetActiveDisplayList, CGRectContainsPoint, CGPointMake
        
        win_x = window_bounds.get('X', 0)
        win_y = window_bounds.get('Y', 0)
        
        # 全ディスプレイを取得
        max_displays = 10
        (err, display_ids, count) = CGGetActiveDisplayList(max_displays, None, None)
        
        # ウィンドウの中心点がどのディスプレイに属するか確認
        point = CGPointMake(win_x, win_y)
        
        for i, display_id in enumerate(display_ids[:count]):
            bounds = CGDisplayBounds(display_id)
            if CGRectContainsPoint(bounds, point):
                return i + 1  # 1-indexed
        
    except Exception as e:
        print(f"Error in get_display_for_window: {e}")
    
    return 1


if __name__ == '__main__':
    # テスト実行
    info = get_active_window_info()
    if info:
        print(f"App: {info.app_name}")
        print(f"Window: {info.window_title}")
        print(f"Window ID: {info.window_id}")

    display = get_active_display_number()
    print(f"Active Display: {display}")

    count = get_display_count()
    print(f"Display Count: {count}")
