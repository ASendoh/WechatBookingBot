import pyautogui
from PIL import Image

from calibration import template_score
from config import (ENTRY_CHECK_REGION, ENTRY_TEMPLATE_PATH,
                    PAGE_CHECK_REGION, PAGE_TEMPLATE_PATH)


def matches_region(region, path, verbose=True):
    screen = pyautogui.screenshot(region=region)
    with Image.open(path) as template:
        max_value = template_score(screen, template)
    if verbose:
        print("页面匹配度：", round(max_value, 3))
    return max_value > 0.85


def check_page(verbose=True):
    return matches_region(PAGE_CHECK_REGION, PAGE_TEMPLATE_PATH, verbose)


def check_entry(verbose=True):
    if ENTRY_TEMPLATE_PATH is None:  # 未校准的 main.py 保持旧版手动测试方式。
        return True
    return matches_region(ENTRY_CHECK_REGION, ENTRY_TEMPLATE_PATH, verbose)


if __name__ == "__main__":
    check_page()
