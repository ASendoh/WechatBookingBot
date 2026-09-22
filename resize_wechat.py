import win32gui
import win32con
import time

from config import RESIZE_LAYOUT_WAIT, WINDOW_POS, WINDOW_SIZE


def resize_wechat():

    # 查找微信窗口
    hwnd = win32gui.FindWindow(
        None,
        "微信"
    )

    if hwnd == 0:
        print("没有找到微信窗口")
        return False

    print("找到微信窗口")

    # 获取当前窗口位置
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)

    print("当前窗口：")
    print(left, top, right, bottom)

    # 设置目标尺寸
    x, y = WINDOW_POS
    width, height = WINDOW_SIZE

    win32gui.SetWindowPos(
        hwnd,
        None,
        x,
        y,
        width,
        height,
        win32con.SWP_NOZORDER
    )

    # 等待页面按新尺寸完成重新布局，再使用调整后的固定坐标。
    time.sleep(RESIZE_LAYOUT_WAIT)
    print(f"调整完成：位置 {WINDOW_POS}，尺寸 {WINDOW_SIZE}")
    return True


if __name__ == "__main__":
    print("3秒后调整微信窗口")
    time.sleep(3)

    resize_wechat()
