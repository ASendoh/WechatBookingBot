import time
import keyboard
import pyautogui

from resize_wechat import click_wechat

from check_selected import AVAILABLE, SELECTED, classify_color, get_state
from config import (
    COURT_X,
    ENABLE_MORNING_TEST_FALLBACK,
    MORNING_TEST_TIME,
    POLL_INTERVAL,
    SOLD_OUT_CONFIRM_SECONDS,
    TIME_Y,
    TOMORROW_DOUBLE_CLICK_INTERVAL,
    TOMORROW_LOAD_SECONDS,
    TOMORROW_POS,
    TOMORROW_RETRIES,
    TOMORROW_SELECTED_POS,
    times,
)

SOLD_OUT = "已抢空"


def tomorrow_is_selected(screenshot):
    click_x, _ = TOMORROW_POS
    line_x, y = TOMORROW_SELECTED_POS
    # 旧校准可能误取左侧“今天”的横线；两点相距太远时以第二天点击点为准。
    x = line_x if abs(line_x - click_x) <= 45 else click_x
    return any(
        classify_color(screenshot.getpixel((sample_x, sample_y))) == SELECTED
        for sample_x in range(x - 30, x + 31)
        for sample_y in range(y - 10, y + 11)
    )


def find_available_court(screenshot, time_names):
    for time_name in time_names:
        y = TIME_Y[time_name]
        for court, x in COURT_X.items():
            state, _ = get_state(x, y, screenshot)
            if state == AVAILABLE:
                return time_name, court
    return None


def all_courts_gray(screenshot, time_names):
    # 格子须为浅灰，格间须为白色；整片灰色遮罩不能算已加载的网格。
    for time_name in time_names:
        gap_x = (COURT_X[1] + COURT_X[2]) // 2
        if min(screenshot.getpixel((gap_x, TIME_Y[time_name]))) < 250:
            return False
        for x in COURT_X.values():
            _, colours = get_state(x, TIME_Y[time_name], screenshot)
            if not all(220 <= min(rgb) <= max(rgb) <= 245
                       and max(rgb) - min(rgb) <= 5 for rgb in colours):
                return False
    return True


def select_tomorrow():
    for attempt in range(1, TOMORROW_RETRIES + 1):
        if keyboard.is_pressed("esc"):
            print("检测到 Esc，停止选择第二天")
            return False

        print(f"第 {attempt} 次点击第二天")
        click_wechat(*TOMORROW_POS)
        # 双击间隔由 config.py 的 TOMORROW_DOUBLE_CLICK_INTERVAL 控制。
        time.sleep(TOMORROW_DOUBLE_CLICK_INTERVAL)
        click_wechat(*TOMORROW_POS)

        # 单次检测等待时长由 config.py 的 TOMORROW_LOAD_SECONDS 控制。
        deadline = time.monotonic() + TOMORROW_LOAD_SECONDS
        selected_message_shown = False
        morning_test_ready = None
        gray_since = None
        while time.monotonic() < deadline:
            if keyboard.is_pressed("esc"):
                print("检测到 Esc，停止选择第二天")
                return False
            screenshot = pyautogui.screenshot()
            if not tomorrow_is_selected(screenshot):
                time.sleep(POLL_INTERVAL)
                continue
            evening = find_available_court(screenshot, times)
            if evening:
                print(f"第二天页面加载成功，检测到 {evening[1]}号场 {evening[0]} 可预约")
                return True
            if ENABLE_MORNING_TEST_FALLBACK:
                morning_test_ready = morning_test_ready or find_available_court(
                    screenshot, (MORNING_TEST_TIME,)
                )
            scan_times = (*times, MORNING_TEST_TIME) if ENABLE_MORNING_TEST_FALLBACK else times
            if all_courts_gray(screenshot, scan_times):
                if gray_since is None:
                    gray_since = time.monotonic()
                if time.monotonic() - gray_since >= SOLD_OUT_CONFIRM_SECONDS:
                    print("目标时段全部场地持续灰色，判定已抢空")
                    return SOLD_OUT
            else:
                gray_since = None
            if not selected_message_shown:
                print("第二天标签已选中，但目标时段可预约场地尚未加载")
                selected_message_shown = True
            time.sleep(POLL_INTERVAL)

        if morning_test_ready:
            print(
                f"目标时段均不可预约，启用早场测试："
                f"{morning_test_ready[1]}号场 {morning_test_ready[0]} 可预约"
            )
            return True

        print("未检测到可预约格子，准备重试")

    print("多次点击第二天仍未确认成功")
    return False
