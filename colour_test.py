import pyautogui
import time


print("开始检测鼠标位置颜色")
print("按 Ctrl+C 结束")

try:
    while True:

        # 获取鼠标位置
        x, y = pyautogui.position()

        # 截取当前屏幕
        screenshot = pyautogui.screenshot()

        # 获取该点颜色
        r, g, b = screenshot.getpixel((x, y))

        print(
            f"位置: ({x},{y})  RGB: ({r},{g},{b})"
        )

        time.sleep(0.2)

except KeyboardInterrupt:
    print("检测结束")