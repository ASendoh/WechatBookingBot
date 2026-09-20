import pyautogui
import time
import cv2
import numpy as np


# 羽毛球入口坐标
BADMINTON_POS = (194, 1135)


def is_booking_page():

    # 截取微信区域
    screen = pyautogui.screenshot(
        region=(0, 0, 760, 1400)
    )

    screen = cv2.cvtColor(
        np.array(screen),
        cv2.COLOR_RGB2BGR
    )

    template = cv2.imread(
        "booking_template.png"
    )

    result = cv2.matchTemplate(
        screen,
        template,
        cv2.TM_CCOEFF_NORMED
    )

    _, max_value, _, _ = cv2.minMaxLoc(result)

    print("页面检测:", round(max_value, 3))

    return max_value > 0.85


def enter_booking():

    print("开始进入预约页面")

    while True:

        # 点击羽毛球入口
        pyautogui.click(
            BADMINTON_POS[0],
            BADMINTON_POS[1]
        )

        time.sleep(0.3)

        # 判断是否进入
        if is_booking_page():

            print("进入预约页面成功")
            break


print("5秒后开始")

time.sleep(5)

enter_booking()