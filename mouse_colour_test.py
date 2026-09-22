import time

import keyboard
import pyautogui


INTERVAL_SECONDS = 0.5


print("开始检测鼠标坐标和颜色，每0.5秒输出一次，按 Esc 结束")

while not keyboard.is_pressed("esc"):
    x, y = pyautogui.position()
    r, g, b = pyautogui.pixel(x, y)
    print(f"坐标: ({x}, {y})  RGB: ({r}, {g}, {b})")
    time.sleep(INTERVAL_SECONDS)

print("检测结束")
