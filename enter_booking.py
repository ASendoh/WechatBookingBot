import time
import keyboard

from move_mouse import move_mouse
from check_page import check_entry, check_page
from config import ENTRY_UNKNOWN_GRACE_SECONDS, PAGE_LOAD_SECONDS, POLL_INTERVAL


def enter_booking():
    unknown_since = None
    while True:
        if keyboard.is_pressed("esc"):
            print("检测到 Esc，停止进入预约页面")
            return False

        if check_page(verbose=False):
            print("预约页面已打开，跳过入口点击")
            return True
        if not check_entry(verbose=False):
            unknown_since = unknown_since or time.monotonic()
            if time.monotonic() - unknown_since >= ENTRY_UNKNOWN_GRACE_SECONDS:
                print("校准警告：微信既不在场馆首页、也不在预约页；已停止本轮，避免误点。", flush=True)
                return False
            time.sleep(POLL_INTERVAL)
            continue
        unknown_since = None

        print("尝试进入羽毛球预约页面")

        # 点击羽毛球馆
        move_mouse()

        deadline = time.monotonic() + PAGE_LOAD_SECONDS
        while time.monotonic() < deadline:
            if keyboard.is_pressed("esc"):
                print("检测到 Esc，停止进入预约页面")
                return False
            if check_page(verbose=False):
                print("成功进入预约页面")
                return True
            time.sleep(POLL_INTERVAL)

        print("进入失败，重新尝试")
