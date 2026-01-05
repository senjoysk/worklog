#!/usr/bin/env python3
"""
worklog - メニューバーアプリ
サービスの状態確認・停止・再開を行う
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import objc
import rumps
from Foundation import NSObject, NSWorkspace, NSNotificationCenter
from Cocoa import NSWorkspaceDidWakeNotification

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
DAILY_BINARY = PROJECT_ROOT / 'dist' / 'worklog-daily'


def needs_daily_report(target_date: str) -> bool:
    """指定日の日報生成が必要かチェック"""
    report_file = REPORTS_DIR / f'{target_date}.md'
    return not report_file.exists()


def has_log_for_date(target_date: str) -> bool:
    """指定日のログファイルが存在するかチェック"""
    log_file = LOGS_DIR / f'{target_date}.jsonl'
    return log_file.exists()


class WakeObserver(NSObject):
    """スリープ復帰を監視するオブザーバー"""

    def initWithCallback_(self, callback):
        self = objc.super(WakeObserver, self).init()
        if self is None:
            return None
        self.callback = callback
        return self

    def handleWake_(self, notification):
        """スリープから復帰したときに呼ばれる"""
        if self.callback:
            self.callback()


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

        # スリープ復帰監視を設定
        self._setup_wake_observer()

        # 5分ごとに日報チェック（スリープ復帰後の確実な実行のため）
        rumps.Timer(self._check_and_generate_daily_report, 300).start()

        # 起動時にも日報チェック（スリープ中に起動しなかった場合の対応）
        self._check_and_generate_daily_report()

    def _setup_wake_observer(self):
        """スリープ復帰の監視を設定"""
        self.wake_observer = WakeObserver.alloc().initWithCallback_(
            self._on_wake_from_sleep
        )
        workspace = NSWorkspace.sharedWorkspace()
        nc = workspace.notificationCenter()
        nc.addObserver_selector_name_object_(
            self.wake_observer,
            "handleWake:",
            NSWorkspaceDidWakeNotification,
            None
        )

    def _on_wake_from_sleep(self):
        """スリープから復帰したときの処理"""
        # 少し待ってからチェック（ネットワーク接続の安定を待つ）
        rumps.Timer(self._check_and_generate_daily_report, 30).start()

    def _check_and_generate_daily_report(self, _=None):
        """欠けている日報があれば生成する（過去10日分をチェック）"""
        today = datetime.now().date()

        for i in range(1, 11):  # 1〜10日前
            target = (today - timedelta(days=i)).strftime('%Y-%m-%d')

            if not has_log_for_date(target):
                continue

            if not needs_daily_report(target):
                continue

            # 日報生成を実行（1回に1つだけ、API負荷軽減）
            self._run_daily_report(target)
            return

    def _run_daily_report(self, target_date: str):
        """日報生成を実行"""
        if not DAILY_BINARY.exists():
            print(f"Daily binary not found: {DAILY_BINARY}")
            return

        try:
            env = os.environ.copy()
            env['WORKLOG_ROOT'] = str(PROJECT_ROOT)
            subprocess.Popen(
                [str(DAILY_BINARY), target_date],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"Started daily report generation for {target_date}")
        except Exception as e:
            print(f"Failed to start daily report: {e}")

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
