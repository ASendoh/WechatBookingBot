import time
import keyboard
import pyautogui

from check_selected import AVAILABLE, SELECTED, classify_color, get_state
from config import (
    COURT_X,
    ENABLE_MORNING_TEST_FALLBACK,
    MORNING_TEST_TIME,
    POLL_INTERVAL,
    TIME_Y,
    TOMORROW_DOUBLE_CLICK_INTERVAL,
    TOMORROW_LOAD_SECONDS,
    TOMORROW_POS,
    TOMORROW_RETRIES,
    TOMORROW_SELECTED_POS,
    times,
)


def tomorrow_is_selected(screenshot):
    x, y = TOMORROW_SELECTED_POS
    return any(
        classify_color(screenshot.getpixel((sample_x, sample_y))) == SELECTED
        for sample_x in range(x - 12, x + 13)
        for sample_y in range(y - 3, y + 4)
    )


def find_available_court(screenshot, time_names):
    for time_name in time_names:
        y = TIME_Y[time_name]
        for court, x in COURT_X.items():
            state, _ = get_state(x, y, screenshot)
            if state == AVAILABLE:
                return time_name, court
    return None


def select_tomorrow() -> bool:
    for attempt in range(1, TOMORROW_RETRIES + 1):
        if keyboard.is_pressed("esc"):
            print("检测到 Esc，停止选择第二天")
            return False

        print(f"第 {attempt} 次点击第二天")
        pyautogui.click(*TOMORROW_POS)
        # 双击间隔由 config.py 的 TOMORROW_DOUBLE_CLICK_INTERVAL 控制。
        time.sleep(TOMORROW_DOUBLE_CLICK_INTERVAL)
        pyautogui.click(*TOMORROW_POS)

        # 单次检测等待时长由 config.py 的 TOMORROW_LOAD_SECONDS 控制。
        deadline = time.monotonic() + TOMORROW_LOAD_SECONDS
        selected_message_shown = False
        morning_test_ready = None
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
            if not selected_message_shown:
                print("第二天标签已选中，但晚间可预约场地尚未加载")
                selected_message_shown = True
            time.sleep(POLL_INTERVAL)

        if morning_test_ready:
            print(
                f"晚场均不可预约，启用早场测试："
                f"{morning_test_ready[1]}号场 {morning_test_ready[0]} 可预约"
            )
            return True

        print("未检测到可预约格子，准备重试")

    print("多次点击第二天仍未确认成功")
    return False
