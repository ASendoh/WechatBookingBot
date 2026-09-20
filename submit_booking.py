import pyautogui


def submit_booking() -> None:
    print("点击提交预约")

    # 提交预约按钮坐标
    x = 1911
    y = 1357

    pyautogui.click(x, y)

    print("提交预约点击完成")