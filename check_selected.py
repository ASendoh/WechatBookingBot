import pyautogui


def check_selected(x, y):

    # 获取像素颜色
    r, g, b = pyautogui.pixel(x, y)

    print("当前颜色:", r, g, b)


    # 紫色判断条件
    if r < 200 and g < 80 and b < 200:

        return True

    return False