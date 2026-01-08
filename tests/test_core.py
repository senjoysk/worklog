#!/usr/bin/env python3
"""コア機能のユニットテスト"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# srcをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestIsScreenLocked(unittest.TestCase):
    """is_screen_locked の出力解析テスト"""

    @patch('subprocess.run')
    def test_locked_returns_true(self, mock_run):
        """'locked' 出力で True を返す"""
        from main import is_screen_locked
        mock_run.return_value = MagicMock(stdout='locked\n')
        self.assertTrue(is_screen_locked())

    @patch('subprocess.run')
    def test_unlocked_returns_false(self, mock_run):
        """'unlocked' 出力で False を返す（'locked' を含むが False）"""
        from main import is_screen_locked
        mock_run.return_value = MagicMock(stdout='unlocked\n')
        self.assertFalse(is_screen_locked())

    @patch('subprocess.run')
    def test_unknown_returns_false(self, mock_run):
        """'unknown' 出力で False を返す"""
        from main import is_screen_locked
        mock_run.return_value = MagicMock(stdout='unknown\n')
        self.assertFalse(is_screen_locked())

    @patch('subprocess.run')
    def test_empty_returns_false(self, mock_run):
        """空出力で False を返す"""
        from main import is_screen_locked
        mock_run.return_value = MagicMock(stdout='')
        self.assertFalse(is_screen_locked())

    @patch('subprocess.run')
    def test_exception_returns_false(self, mock_run):
        """例外発生時に False を返す"""
        from main import is_screen_locked
        mock_run.side_effect = Exception("test error")
        self.assertFalse(is_screen_locked())


class TestGetActiveWindowInfo(unittest.TestCase):
    """get_active_window_info の行分割解析テスト"""

    @patch('subprocess.run')
    def test_normal_output(self, mock_run):
        """正常な2行出力を正しく解析"""
        from window_info import get_active_window_info
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Safari\nGoogle - Search\n'
        )
        result = get_active_window_info()
        self.assertIsNotNone(result)
        self.assertEqual(result.app_name, 'Safari')
        self.assertEqual(result.window_title, 'Google - Search')

    @patch('subprocess.run')
    def test_title_with_special_chars(self, mock_run):
        """特殊文字（"や\）を含むタイトルを正しく解析"""
        from window_info import get_active_window_info
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Terminal\necho "hello \\ world"\n'
        )
        result = get_active_window_info()
        self.assertIsNotNone(result)
        self.assertEqual(result.app_name, 'Terminal')
        self.assertEqual(result.window_title, 'echo "hello \\ world"')

    @patch('subprocess.run')
    def test_title_with_newline(self, mock_run):
        """タイトルに改行を含む場合（最初の改行で分割）"""
        from window_info import get_active_window_info
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Code\nfile.py - Project\nMore info\n'
        )
        result = get_active_window_info()
        self.assertIsNotNone(result)
        self.assertEqual(result.app_name, 'Code')
        # 2行目以降は全てタイトルとして扱う
        self.assertEqual(result.window_title, 'file.py - Project\nMore info')

    @patch('subprocess.run')
    def test_empty_title(self, mock_run):
        """タイトルが空の場合"""
        from window_info import get_active_window_info
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Finder\n'
        )
        result = get_active_window_info()
        self.assertIsNotNone(result)
        self.assertEqual(result.app_name, 'Finder')
        self.assertEqual(result.window_title, '')

    @patch('subprocess.run')
    def test_error_returns_none(self, mock_run):
        """エラー時に None を返す"""
        from window_info import get_active_window_info
        mock_run.return_value = MagicMock(returncode=1, stdout='')
        result = get_active_window_info()
        self.assertIsNone(result)


class TestMarkdownToSlack(unittest.TestCase):
    """markdown_to_slack の変換テスト"""

    def setUp(self):
        from daily_report import markdown_to_slack
        self.convert = markdown_to_slack

    def test_h1_to_bold(self):
        """# 見出しが太字に変換される"""
        result = self.convert('# Title')
        self.assertIn('*Title*', result)

    def test_h2_to_bold(self):
        """## 見出しが太字に変換される"""
        result = self.convert('## Section')
        self.assertIn('*Section*', result)

    def test_h3_to_bold(self):
        """### 見出しが太字に変換される"""
        result = self.convert('### Subsection')
        self.assertIn('*Subsection*', result)

    def test_bold_conversion(self):
        """**bold** が *bold* に変換される"""
        result = self.convert('This is **important** text')
        self.assertIn('*important*', result)
        self.assertNotIn('**', result)

    def test_table_to_list(self):
        """テーブルがリスト形式に変換される"""
        table = """| App | Time | Usage |
|-----|------|-------|
| Safari | 2h | Browsing |
| Code | 3h | Development |"""
        result = self.convert(table)
        # テーブルがリスト形式になっている
        self.assertIn('•', result)
        self.assertIn('Safari', result)
        self.assertIn('Code', result)

    def test_normal_text_preserved(self):
        """通常テキストは保持される"""
        result = self.convert('Normal text here')
        self.assertIn('Normal text here', result)

    def test_list_items_preserved(self):
        """リストアイテムは保持される"""
        result = self.convert('- Item 1\n- Item 2')
        self.assertIn('- Item 1', result)
        self.assertIn('- Item 2', result)


if __name__ == '__main__':
    unittest.main()
