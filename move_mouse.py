import pyautogui


def move_mouse() -> None:
    print("准备点击羽毛球入口")

    x = 194
    y = 1135

    pyautogui.click(x, y)

    print("羽毛球入口点击完成")