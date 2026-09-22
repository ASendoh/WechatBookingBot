import time
import winsound

import keyboard
import pyautogui

from config import (
    POLL_INTERVAL,
    VERIFY_AFTER_PLAY_WAIT_SECONDS,
    VERIFY_APPEAR_TIMEOUT_SECONDS,
    VERIFY_GREY,
    VERIFY_MANUAL_REMINDER_SECONDS,
    VERIFY_PIXEL_POS,
    VERIFY_PLAY_START_DELAY_SECONDS,
    VERIFY_STABLE_SECONDS,
    VERIFY_TOLERANCE,
)
from mouse_recorder import play


def check_verify():
    rgb = pyautogui.pixel(*VERIFY_PIXEL_POS)
    return all(abs(channel - VERIFY_GREY) < VERIFY_TOLERANCE for channel in rgb)


def wait_or_stop(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if keyboard.is_pressed("esc"):
            return False
        time.sleep(POLL_INTERVAL)
    return True


def wait_verify():
    print("等待验证窗口出现...")
    appear_deadline = time.monotonic() + VERIFY_APPEAR_TIMEOUT_SECONDS
    while not keyboard.is_pressed("esc"):
        if check_verify():
            print("检测到验证窗口，准备执行一次已录制操作")
            if not wait_or_stop(VERIFY_PLAY_START_DELAY_SECONDS):
                return False
            play()
            if not wait_or_stop(VERIFY_AFTER_PLAY_WAIT_SECONDS):
                return False
            manual_wait = check_verify()
            if manual_wait:
                play()
            else:
                print("验证遮罩已消失，等待稳定确认")
            break
        if time.monotonic() >= appear_deadline:
            print(f"{VERIFY_APPEAR_TIMEOUT_SECONDS}秒内未检测到验证窗口，刷新后重新选择")
            return True
        time.sleep(POLL_INTERVAL)
    else:
        print("检测到 Esc，停止等待验证")
        return False

    stable_since = None
    next_reminder = time.monotonic() + VERIFY_MANUAL_REMINDER_SECONDS if manual_wait else None
    while not keyboard.is_pressed("esc"):
        if check_verify():
            stable_since = None
            if next_reminder is not None and time.monotonic() >= next_reminder:
                play()
                next_reminder = time.monotonic() + VERIFY_MANUAL_REMINDER_SECONDS
        else:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= VERIFY_STABLE_SECONDS:
                print("验证遮罩已稳定消失")
                return True
        time.sleep(POLL_INTERVAL)

    print("检测到 Esc，停止等待验证")
    return False


if __name__ == "__main__":
    print("1秒后开始等待人工验证")
    time.sleep(1)
    wait_verify()
