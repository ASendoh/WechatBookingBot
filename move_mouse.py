import pyautogui
import time


def move_mouse():

    print("准备点击羽毛球入口")

    time.sleep(1)

    x = 194
    y = 1135

    pyautogui.moveTo(
        x,
        y,
        duration=0.1
    )

    pyautogui.click()

    print("羽毛球入口点击完成")