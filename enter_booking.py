import time
import keyboard

from move_mouse import move_mouse
from check_page import check_page
from config import PAGE_LOAD_SECONDS, POLL_INTERVAL


def enter_booking():

    while True:
        if keyboard.is_pressed("esc"):
            print("检测到 Esc，停止进入预约页面")
            return False

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
