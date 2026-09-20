import win32gui
import win32con
import time


def resize_wechat():

    # 查找微信窗口
    hwnd = win32gui.FindWindow(
        None,
        "微信"
    )

    if hwnd == 0:
        print("没有找到微信窗口")
        return

    print("找到微信窗口")

    # 获取当前窗口位置
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)

    print("当前窗口：")
    print(left, top, right, bottom)

    # 设置目标尺寸
    width = 2000
    height = 1400

    win32gui.SetWindowPos(
        hwnd,
        None,
        left,
        top,
        width,
        height,
        win32con.SWP_NOZORDER
    )

    print("调整完成")


if __name__ == "__main__":
    print("3秒后调整微信窗口")
    time.sleep(3)

    resize_wechat()