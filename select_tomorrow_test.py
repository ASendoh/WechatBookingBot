import time
import pyautogui


def select_tomorrow() -> None:
    print("点击第二天按钮")

    x = 438
    y = 187

    # 保留两次点击，以及两次点击之间的 0.1 秒间隔。
    pyautogui.click(x, y)
    time.sleep(0.1)
    pyautogui.click(x, y)

    print("第二天点击完成")


if __name__ == "__main__":
    select_tomorrow()