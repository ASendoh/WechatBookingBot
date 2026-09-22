import pyautogui
import keyboard

from check_verify import wait_verify
from enter_booking import enter_booking
from refresh_booking import refresh_booking
from resize_wechat import resize_wechat
from select_court import select_court
from select_tomorrow_test import select_tomorrow
from submit_booking import submit_booking

# 关闭 PyAutoGUI 操作后的统一暂停，必要的等待由各步骤显式控制。
pyautogui.PAUSE = 0

# 保留 PyAutoGUI 的紧急停止功能。
pyautogui.FAILSAFE = True


def recover_page():
    if refresh_booking():
        return True
    if keyboard.is_pressed("esc"):
        return False
    print("刷新失败，重新尝试进入预约页面")
    return enter_booking()


def main():
    print("程序开始，任意等待阶段均可按 Esc 停止")
    if not enter_booking() or not resize_wechat():
        return

    round_number = 0
    while not keyboard.is_pressed("esc"):
        round_number += 1
        print(f"开始第 {round_number} 轮预约")

        if not select_tomorrow():
            if not recover_page():
                break
            continue

        selected = select_court()
        if keyboard.is_pressed("esc"):
            break
        if not selected:
            print("没有选中任何时段，不提交；刷新后重新开始")
            if not recover_page():
                break
            continue

        if not submit_booking() or not wait_verify():
            break
        if not recover_page():
            break

    print("程序已安全停止")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, pyautogui.FailSafeException):
        print("程序已由用户紧急停止")
