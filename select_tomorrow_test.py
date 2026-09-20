import pyautogui
import time


def select_tomorrow():

    print("移动到第二天按钮")


    x = 438
    y = 187

    pyautogui.moveTo(
        x,
        y,
    )

    print("移动完成")

    pyautogui.click(x, y)
    time.sleep(0.1)
    pyautogui.click(x, y)

    print("第二天选择完成")


if __name__ == "__main__":
    select_tomorrow()