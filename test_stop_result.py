"""结局判断的无点击自检：python test_stop_result.py。"""

from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from PIL import Image, ImageDraw

import main
import select_court as court_picker
import select_tomorrow_test as tomorrow
from config import COURT_X, TIME_Y, times


def run_tests():
    tab = Image.new("RGB", (200, 200), "white")
    with (patch.object(tomorrow, "TOMORROW_POS", (100, 65)),
          patch.object(tomorrow, "TOMORROW_SELECTED_POS", (8, 100))):
        ImageDraw.Draw(tab).line((120, 108, 135, 108), fill=(153, 0, 153))
        assert tomorrow.tomorrow_is_selected(tab)
        tab = Image.new("RGB", (200, 200), "white")
        ImageDraw.Draw(tab).line((1, 108, 28, 108), fill=(153, 0, 153))
        assert not tomorrow.tomorrow_is_selected(tab)

    screen = Image.new("RGB", (max(COURT_X.values()) + 100, max(TIME_Y.values()) + 100), "white")
    assert not tomorrow.all_courts_gray(screen, times)  # 尚无格子不能算已抢空。
    assert not tomorrow.all_courts_gray(
        Image.new("RGB", screen.size, (235, 235, 235)), times
    )  # 整片灰色遮罩不是场地网格。
    draw = ImageDraw.Draw(screen)
    for time_name in times:
        for x in COURT_X.values():
            y = TIME_Y[time_name]
            draw.rectangle((x - 40, y - 25, x + 40, y + 25), fill=(235, 235, 235))
    assert tomorrow.all_courts_gray(screen, times)
    gray_screen = screen.copy()
    x, y = COURT_X[1], TIME_Y[times[0]]
    draw.rectangle((x - 40, y - 25, x + 40, y + 25), fill="white")
    assert not tomorrow.all_courts_gray(screen, times)  # 任何白格都不算全灰。

    morning_page = gray_screen.copy()
    morning_draw = ImageDraw.Draw(morning_page)
    morning_y = TIME_Y[tomorrow.MORNING_TEST_TIME]
    for x in COURT_X.values():
        morning_draw.rectangle((x - 40, morning_y - 25, x + 40, morning_y + 25), fill=(235, 235, 235))
    for court in (13, 14):
        x = COURT_X[court]
        morning_draw.rectangle(
            (x - 40, morning_y - 25, x + 40, morning_y + 25),
            fill="white", outline=(235, 235, 235),
        )
    tab_x, tab_y = tomorrow.TOMORROW_SELECTED_POS
    morning_draw.line((tab_x + 20, tab_y + 8, tab_x + 28, tab_y + 8), fill=(153, 0, 153))
    clock = {"now": 0.0}
    with (patch.object(tomorrow, "ENABLE_MORNING_TEST_FALLBACK", True),
          patch.object(court_picker, "ENABLE_MORNING_TEST_FALLBACK", True),
          patch.object(tomorrow.time, "monotonic", side_effect=lambda: clock["now"]),
          patch.object(tomorrow.time, "sleep", side_effect=lambda seconds: clock.__setitem__("now", clock["now"] + seconds)),
          patch.object(tomorrow.keyboard, "is_pressed", return_value=False),
          patch.object(tomorrow, "click_wechat"),
          patch.object(tomorrow.pyautogui, "screenshot", return_value=morning_page),
          patch.object(court_picker, "click_wechat") as click,
          patch.object(court_picker, "click_succeeded", return_value=True),
          redirect_stdout(StringIO())):
        assert tomorrow.select_tomorrow() is True
        assert court_picker.select_court() == [(tomorrow.MORNING_TEST_TIME, 14)]
        click.assert_called_once()

    new_times = ["10:30-11:30", "11:30-12:30"]
    new_page = gray_screen.copy()
    new_draw = ImageDraw.Draw(new_page)
    new_rows = {new_times[0]: 500, new_times[1]: 568}
    for y in new_rows.values():
        for x in COURT_X.values():
            new_draw.rectangle((x - 40, y - 25, x + 40, y + 25), fill=(235, 235, 235))
    for time_name, court in ((new_times[0], 14), (new_times[1], 13)):
        x, y = COURT_X[court], new_rows[time_name]
        new_draw.rectangle((x - 40, y - 25, x + 40, y + 25), fill="white", outline=(235, 235, 235))
    new_draw.line((tab_x + 20, tab_y + 8, tab_x + 28, tab_y + 8), fill=(153, 0, 153))
    clock = {"now": 0.0}
    with (patch.dict(TIME_Y, new_rows),
          patch.object(tomorrow, "times", new_times),
          patch.object(court_picker, "times", new_times),
          patch.object(tomorrow, "ENABLE_MORNING_TEST_FALLBACK", False),
          patch.object(court_picker, "ENABLE_MORNING_TEST_FALLBACK", False),
          patch.object(tomorrow.time, "monotonic", side_effect=lambda: clock["now"]),
          patch.object(tomorrow.time, "sleep", side_effect=lambda seconds: clock.__setitem__("now", clock["now"] + seconds)),
          patch.object(tomorrow.keyboard, "is_pressed", return_value=False),
          patch.object(tomorrow, "click_wechat"),
          patch.object(tomorrow.pyautogui, "screenshot", return_value=new_page),
          patch.object(court_picker, "click_wechat") as click,
          patch.object(court_picker, "click_succeeded", return_value=True),
          redirect_stdout(StringIO())):
        assert tomorrow.select_tomorrow() is True
        assert court_picker.select_court() == [(new_times[1], 13), (new_times[0], 14)]
        assert click.call_count == 2

    clock = {"now": 0.0}
    with (patch.object(tomorrow.time, "monotonic", side_effect=lambda: clock["now"]),
          patch.object(tomorrow.time, "sleep", side_effect=lambda seconds: clock.__setitem__("now", clock["now"] + seconds)),
          patch.object(tomorrow.keyboard, "is_pressed", return_value=False),
          patch.object(tomorrow, "click_wechat") as click,
          patch.object(tomorrow, "tomorrow_is_selected", return_value=True),
          patch.object(tomorrow.pyautogui, "screenshot", return_value=gray_screen)):
        assert tomorrow.select_tomorrow() == tomorrow.SOLD_OUT
        assert click.call_count == 2
        assert clock["now"] >= tomorrow.SOLD_OUT_CONFIRM_SECONDS

    payment = Image.new("RGB", (2000, 1400), "white")
    draw = ImageDraw.Draw(payment)
    draw.rectangle((1800, 1320, 1999, 1399), fill=(153, 0, 153))
    assert not main.payment_page(payment, (0, 0, 2000, 1400))
    draw.rectangle((0, 1320, 1999, 1399), fill=(153, 0, 153))
    assert main.payment_page(payment, (0, 0, 2000, 1400))

    with (patch.object(main, "CALIBRATION_PATH", None),
          patch.object(main, "restore_entry_window", return_value=True),
          patch.object(main, "enter_booking", return_value=True),
          patch.object(main, "resize_wechat", return_value=True),
          patch.object(main.keyboard, "is_pressed", return_value=False),
          patch.object(main, "select_tomorrow", return_value=tomorrow.SOLD_OUT),
          patch.object(main, "select_court") as select,
          patch.object(main, "recover_page") as recover):
        main.run_booking()
        select.assert_not_called()
        recover.assert_not_called()

    with (patch.object(main, "CALIBRATION_PATH", None),
          patch.object(main, "restore_entry_window", return_value=True),
          patch.object(main, "enter_booking", return_value=True),
          patch.object(main, "resize_wechat", return_value=True),
          patch.object(main.keyboard, "is_pressed", return_value=False),
          patch.object(main, "select_tomorrow", return_value=True),
          patch.object(main, "select_court", return_value=[("19:00-20:00", 1)]),
          patch.object(main, "submit_booking", return_value=True),
          patch.object(main, "wait_verify", return_value=True),
          patch.object(main, "wait_payment", return_value=True),
          patch.object(main, "recover_page") as recover):
        main.run_booking()
        recover.assert_not_called()

    with (patch.object(main, "CALIBRATION_PATH", None),
          patch.object(main, "restore_entry_window", return_value=True),
          patch.object(main, "enter_booking", return_value=True),
          patch.object(main, "resize_wechat", return_value=True),
          patch.object(main.keyboard, "is_pressed", return_value=False),
          patch.object(main, "select_tomorrow", return_value=True),
          patch.object(main, "select_court", return_value=[("19:00-20:00", 1)]),
          patch.object(main, "submit_booking", return_value=True),
          patch.object(main, "wait_verify", return_value=None),
          patch.object(main, "recover_page", return_value=False) as recover):
        main.run_booking()
        recover.assert_called_once_with()

    print("停止结局判断自检通过")


if __name__ == "__main__":
    run_tests()
