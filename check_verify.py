import pyautogui
import time
from random_drag import random_drag


# 验证弹窗附近检测点坐标
# 你需要自己修改为稳定的位置
VERIFY_PIXEL_X = 1949
VERIFY_PIXEL_Y = 907


def check_verify():

    r, g, b = pyautogui.pixel(
        VERIFY_PIXEL_X,
        VERIFY_PIXEL_Y
    )

    print("验证检测点颜色:", r, g, b)

    # 弹窗出现后的灰色
    if (
        abs(r - 127) < 5 and
        abs(g - 127) < 5 and
        abs(b - 127) < 5
    ):
        return True

    return False



def wait_verify():

    print("等待验证窗口出现...")

    while True:

        if check_verify():

            print("检测到验证窗口，正在验证")
            random_drag(
                762, 678,   # 起点
                1223, 677    # 终点
            )

            return True


        time.sleep(0.05)


if __name__ == "__main__":
    print("1秒后进行验证")
    time.sleep(1)

    wait_verify()