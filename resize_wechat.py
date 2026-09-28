import win32gui
import win32con
import time
import pyautogui

from config import (BOOKING_WINDOW_MAXIMIZED, ENTRY_WINDOW_RECT,
                    RESIZE_LAYOUT_WAIT, WINDOW_POS, WINDOW_SIZE)


def wechat_in_front(hwnd=None, activate=False):
    hwnd = hwnd or win32gui.FindWindow(None, "微信")
    if not hwnd:
        print("校准警告：没有找到微信窗口，已停止点击。", flush=True)
        return False
    if win32gui.GetForegroundWindow() == hwnd:
        return True
    if activate:
        for _ in range(3):
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
            if win32gui.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.1)
    print("校准警告：微信未处于最前方，已停止点击以避免误点。", flush=True)
    return False


def click_wechat(*point):
    if not wechat_in_front():
        raise RuntimeError("微信未处于最前方，已停止本轮")
    pyautogui.click(*point)


def restore_entry_window():
    """校准后先还原入口页面布局，再点击羽毛球入口。"""
    if ENTRY_WINDOW_RECT is None:
        return True
    hwnd = win32gui.FindWindow(None, "微信")
    if not hwnd:
        print("没有找到微信窗口")
        return False
    if (win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED
            or win32gui.IsIconic(hwnd)):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(hwnd, None, *ENTRY_WINDOW_RECT, win32con.SWP_NOZORDER)
    time.sleep(RESIZE_LAYOUT_WAIT)
    if not wechat_in_front(hwnd, activate=True):
        return False
    print("已恢复微信入口窗口，准备识别页面")
    return True


def resize_wechat():

    # 查找微信窗口
    hwnd = win32gui.FindWindow(
        None,
        "微信"
    )

    if hwnd == 0:
        print("没有找到微信窗口")
        return False

    if (win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED
            or win32gui.IsIconic(hwnd)):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

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
    if BOOKING_WINDOW_MAXIMIZED:
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

    # 等待页面按新尺寸完成重新布局，再使用调整后的固定坐标。
    time.sleep(RESIZE_LAYOUT_WAIT)
    print(f"调整完成：位置 {WINDOW_POS}，尺寸 {WINDOW_SIZE}")
    return wechat_in_front(hwnd, activate=True)


if __name__ == "__main__":
    print("3秒后调整微信窗口")
    time.sleep(3)

    resize_wechat()
