import pyautogui
import win32gui
from PIL import Image

from calibration import template_score
from config import (ENTRY_CHECK_REGION, ENTRY_TEMPLATE_PATH, ENTRY_WINDOW_RECT,
                    PAGE_BACKGROUND_POINT, PAGE_CHECK_REGION, PAGE_TEMPLATE_PATH,
                    WHITE_MIN)


def matches_region(region, path, verbose=True):
    screen = pyautogui.screenshot(region=region)
    with Image.open(path) as template:
        max_value = template_score(screen, template)
    if verbose:
        print("页面匹配度：", round(max_value, 3))
    return max_value > 0.85


def check_page(verbose=True):
    if not matches_region(PAGE_CHECK_REGION, PAGE_TEMPLATE_PATH, verbose):
        return False
    if ENTRY_WINDOW_RECT is None:  # 未校准时保持原来的标题识别方式。
        return True
    hwnd = win32gui.FindWindow(None, "微信")
    if not hwnd:
        return False
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    # 校准点按当前窗口映射；旧校准文件沿用原来的右侧推算点。
    point = PAGE_BACKGROUND_POINT or (
        ENTRY_WINDOW_RECT[0] + round(ENTRY_WINDOW_RECT[2] * 0.8),
        PAGE_CHECK_REGION[1] + PAGE_CHECK_REGION[3] // 2,
    )
    x = left + round((point[0] - ENTRY_WINDOW_RECT[0])
                     * (right - left) / ENTRY_WINDOW_RECT[2])
    y = top + point[1] - ENTRY_WINDOW_RECT[1]
    screen_width, screen_height = pyautogui.size()
    if not (0 <= x < screen_width and 0 <= y < screen_height):
        return False
    white = all(channel >= WHITE_MIN for channel in pyautogui.pixel(x, y)[:3])
    if verbose:
        print("页眉右侧背景：", "白色" if white else "非白色")
    return white


def check_entry(verbose=True):
    if ENTRY_TEMPLATE_PATH is None:  # 未校准的 main.py 保持旧版手动测试方式。
        return True
    return matches_region(ENTRY_CHECK_REGION, ENTRY_TEMPLATE_PATH, verbose)


if __name__ == "__main__":
    check_page()
