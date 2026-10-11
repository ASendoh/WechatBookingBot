import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import config


class TomorrowWaitTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.clicks = []
        self.scans = []
        modules = {
            "keyboard": SimpleNamespace(is_pressed=lambda _: False),
            "pyautogui": SimpleNamespace(
                click=lambda *args: self.clicks.append(self.now),
                screenshot=lambda: object(),
            ),
            "resize_wechat": SimpleNamespace(click_wechat=lambda *args: self.clicks.append(self.now)),
            "check_selected": SimpleNamespace(
                AVAILABLE="available", SELECTED="selected",
                classify_color=None, get_state=None,
            ),
        }
        spec = importlib.util.spec_from_file_location(
            "tomorrow_under_test", Path(__file__).with_name("select_tomorrow_test.py")
        )
        self.bot = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", modules):
            spec.loader.exec_module(self.bot)
        self.bot.time = SimpleNamespace(monotonic=lambda: self.now, sleep=self.sleep)
        self.bot.TOMORROW_RETRIES = 1
        self.bot.ENABLE_MORNING_TEST_FALLBACK = False
        self.bot.find_available_court = self.scan
        self.bot.all_courts_gray = lambda *_: False

    def sleep(self, seconds):
        self.now += seconds

    def scan(self, screenshot, names):
        self.scans.append(self.now)
        return None

    def test_no_line_rechecks_after_half_second_then_double_clicks(self):
        checks = []
        self.bot.TOMORROW_RETRIES = 2
        self.bot.tomorrow_is_selected = lambda _: checks.append(self.now) or False
        self.assertFalse(self.bot.select_tomorrow())
        self.assertEqual(len(self.clicks), 4)
        self.assertAlmostEqual(checks[1] - checks[0], 0.5)
        self.assertAlmostEqual(self.clicks[2], checks[1])
        self.assertEqual(self.scans, [])

    def test_late_line_starts_separate_two_second_court_wait(self):
        self.bot.tomorrow_is_selected = lambda _: self.now >= 0.7 - 1e-9
        self.assertFalse(self.bot.select_tomorrow())
        self.assertAlmostEqual(self.scans[0], 0.7)
        self.assertGreaterEqual(self.now, 2.7 - 1e-9)
        self.assertLess(self.now, 2.81)

    def test_available_court_returns_immediately(self):
        self.bot.tomorrow_is_selected = lambda _: True
        self.bot.find_available_court = lambda *_: ("19:00-20:00", 17)
        self.assertTrue(self.bot.select_tomorrow())
        self.assertAlmostEqual(self.now, 0.2)

    def test_escape_during_line_wait_stops(self):
        self.bot.tomorrow_is_selected = lambda _: False
        self.bot.keyboard = SimpleNamespace(is_pressed=lambda _: self.now >= 0.3)
        self.assertFalse(self.bot.select_tomorrow())
        self.assertEqual(len(self.clicks), 2)
        self.assertLess(self.now, 0.7)


if __name__ == "__main__":
    unittest.main()
