#!/usr/bin/env python3
"""
worklog - メニューバーアプリ
サービスの状態確認・停止・再開を行う
"""

import os
import sys
import subprocess
from pathlib import Path

import rumps

PLIST_DIR = os.path.expanduser("~/Library/LaunchAgents")
SERVICES = {
    "capture": "com.user.worklog",
    "daily": "com.user.worklog.daily",
}


def get_project_root() -> Path:
    """プロジェクトルートを取得"""
    if 'WORKLOG_ROOT' in os.environ:
        return Path(os.environ['WORKLOG_ROOT'])
    if getattr(sys, 'frozen', False):
        # .app bundle: /path/to/dist/worklog-menubar.app/Contents/MacOS/worklog-menubar
        # → dist の親がプロジェクトルート
        exe_path = Path(sys.executable)
        if '.app' in str(exe_path):
            # .app/Contents/MacOS/binary → .app → dist → project_root
            for parent in exe_path.parents:
                if parent.suffix == '.app':
                    return parent.parent.parent
        return exe_path.parent.parent
    return Path(__file__).parent.parent


PROJECT_ROOT = get_project_root()
LOGS_DIR = PROJECT_ROOT / 'logs'
REPORTS_DIR = PROJECT_ROOT / 'reports'


class WorklogMenubarApp(rumps.App):
    def __init__(self):
        super().__init__("Worklog", title="●")

        # メニュー構成
        self.capture_status = rumps.MenuItem("Capture: ...")
        self.capture_toggle = rumps.MenuItem("Stop Capture", callback=self.toggle_capture)
        self.daily_status = rumps.MenuItem("Daily: ...")
        self.daily_toggle = rumps.MenuItem("Stop Daily", callback=self.toggle_daily)

        self.menu = [
            self.capture_status,
            self.capture_toggle,
            None,  # セパレータ
            self.daily_status,
            self.daily_toggle,
            None,
            rumps.MenuItem("Open Logs", callback=self.open_logs),
            rumps.MenuItem("Open Reports", callback=self.open_reports),
            None,
        ]

        # 5秒ごとに状態チェック
        rumps.Timer(self.update_status, 5).start()
        self.update_status(None)

    def is_running(self, service_id: str) -> bool:
        """サービスが実行中かどうかを確認"""
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True
        )
        return service_id in result.stdout

    def update_status(self, _):
        """メニューの状態を更新"""
        cap_running = self.is_running(SERVICES["capture"])
        daily_running = self.is_running(SERVICES["daily"])

        # アイコン更新（キャプチャが動いていれば●）
        self.title = "●" if cap_running else "○"

        # メニュー項目更新
        self.capture_status.title = f"Capture: {'Running' if cap_running else 'Stopped'}"
        self.capture_toggle.title = "Stop Capture" if cap_running else "Start Capture"
        self.daily_status.title = f"Daily: {'Running' if daily_running else 'Stopped'}"
        self.daily_toggle.title = "Stop Daily" if daily_running else "Start Daily"

    def toggle_capture(self, _):
        """キャプチャサービスを停止/再開"""
        self._toggle_service(SERVICES["capture"])

    def toggle_daily(self, _):
        """日報生成サービスを停止/再開"""
        self._toggle_service(SERVICES["daily"])

    def _toggle_service(self, service_id: str):
        """サービスを停止/再開"""
        plist = f"{PLIST_DIR}/{service_id}.plist"
        if self.is_running(service_id):
            subprocess.run(["launchctl", "unload", plist])
        else:
            subprocess.run(["launchctl", "load", plist])
        self.update_status(None)

    def open_logs(self, _):
        """ログフォルダをFinderで開く"""
        subprocess.run(["open", str(LOGS_DIR)])

    def open_reports(self, _):
        """日報フォルダをFinderで開く"""
        subprocess.run(["open", str(REPORTS_DIR)])


if __name__ == "__main__":
    WorklogMenubarApp().run()
