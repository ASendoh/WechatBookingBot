import pyautogui
import time
import keyboard

from config import (
    POLL_INTERVAL,
    VERIFY_GREY,
    VERIFY_PIXEL_POS,
    VERIFY_STABLE_SECONDS,
    VERIFY_TOLERANCE,
)
from mouse_recorder import play

def check_verify():
    rgb = pyautogui.pixel(*VERIFY_PIXEL_POS)
    return all(abs(channel - VERIFY_GREY) < VERIFY_TOLERANCE for channel in rgb)



def wait_verify():
    print("等待验证窗口出现...")
    while not keyboard.is_pressed("esc"):
        if check_verify():
            print("检测到验证窗口，请用户手动完成滑块验证")
            time.sleep(0.5) 
            play()
            break
        time.sleep(POLL_INTERVAL)
    else:
        print("检测到 Esc，停止等待验证")
        return False

    stable_since = None
    while not keyboard.is_pressed("esc"):
        if check_verify():
            stable_since = None
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
