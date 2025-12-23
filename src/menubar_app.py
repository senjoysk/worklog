#!/usr/bin/env python3
"""
worklog - メニューバーアプリ
サービスの状態確認・停止・再開を行う
"""

import os
import subprocess

import rumps

PLIST_DIR = os.path.expanduser("~/Library/LaunchAgents")
SERVICES = {
    "capture": "com.user.worklog",
    "daily": "com.user.worklog.daily",
}


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


if __name__ == "__main__":
    WorklogMenubarApp().run()
