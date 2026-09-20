import pyautogui
import cv2
import numpy as np
import time


def check_page():
    # 截取微信区域
    screen = pyautogui.screenshot(
        region=(0, 70, 400, 100)
    )

    # PIL转OpenCV格式
    screen = cv2.cvtColor(
        np.array(screen),
        cv2.COLOR_RGB2BGR
    )

    # 读取模板
    template = cv2.imread(
        "booking_template.png"
    )

    # 模板匹配
    result = cv2.matchTemplate(
        screen,
        template,
        cv2.TM_CCOEFF_NORMED
    )

    # 最大匹配值
    _, max_value, _, _ = cv2.minMaxLoc(result)

    print("匹配度：", max_value)

    return max_value > 0.85


if __name__ == "__main__":
    check_page()