import pyautogui
import time


def submit_booking():

    print("点击提交预约")

    # 提交预约按钮坐标
    x = 1911
    y = 1357

    pyautogui.moveTo(
        x,
        y,
    )

    pyautogui.click()

    print("提交预约点击完成")