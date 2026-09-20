import pyautogui
import random
import time


def random_drag(start_x, start_y, end_x, end_y):
    # 移动到起点
    pyautogui.moveTo(start_x, start_y)

    # 按住鼠标
    pyautogui.mouseDown()

    # 生成中间点
    steps = 20

    for i in range(1, steps + 1):
        # 线性插值
        x = start_x + (end_x - start_x) * i / steps
        y = start_y + (end_y - start_y) * i / steps

        # 添加随机偏移
        x += random.randint(-3, 3)
        y += random.randint(-3, 3)

        pyautogui.moveTo(
            x,
            y,
            duration=random.uniform(0.02, 0.05)
        )

    # 松开鼠标
    pyautogui.mouseUp()


