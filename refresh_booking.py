import time

import keyboard
import pyautogui

from config import POLL_INTERVAL, REFRESH_POS, REFRESH_WAIT_SECONDS


def refresh_booking():
    if keyboard.is_pressed("esc"):
        print("检测到 Esc，停止刷新")
        return False

    print("点击微信顶部刷新按钮")
    pyautogui.click(*REFRESH_POS)

    deadline = time.monotonic() + REFRESH_WAIT_SECONDS
    while time.monotonic() < deadline:
        if keyboard.is_pressed("esc"):
            print("检测到 Esc，停止刷新")
            return False
        time.sleep(POLL_INTERVAL)

    print("刷新等待结束，下一步重新点击第二天")
    return True
