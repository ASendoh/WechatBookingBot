import time

import pyautogui
import keyboard
import win32gui

from calibration import check_layout, load_profile
from check_page import check_page
from check_selected import SELECTED, classify_color
from check_verify import wait_verify
from config import (CALIBRATION_PATH, ENTRY_UNKNOWN_GRACE_SECONDS,
                    PAYMENT_APPEAR_TIMEOUT_SECONDS, POLL_INTERVAL)
from enter_booking import enter_booking
from license_client import LicenseError, booking_guard
from move_mouse import move_mouse
from refresh_booking import refresh_booking
from resize_wechat import resize_wechat, restore_entry_window
from select_court import select_court
from select_tomorrow_test import SOLD_OUT, select_tomorrow
from submit_booking import submit_booking

# 关闭 PyAutoGUI 操作后的统一暂停，必要的等待由各步骤显式控制。
pyautogui.PAUSE = 0

# 保留 PyAutoGUI 的紧急停止功能。
pyautogui.FAILSAFE = True


def payment_page(screenshot, rect):
    left, top, right, bottom = rect
    y = bottom - 25
    xs = [left + round((right - left) * fraction) for fraction in (0.1, 0.3, 0.7, 0.9)]
    if not (0 <= y < screenshot.height and all(0 <= x < screenshot.width for x in xs)):
        return False
    return all(classify_color(screenshot.getpixel((x, y))) == SELECTED for x in xs)


def wait_payment():
    print(f"验证已完成，最多等待 {PAYMENT_APPEAR_TIMEOUT_SECONDS} 秒检测付款页面")
    deadline = time.monotonic() + PAYMENT_APPEAR_TIMEOUT_SECONDS
    while not keyboard.is_pressed("esc"):
        hwnd = win32gui.FindWindow(None, "微信")
        if hwnd and win32gui.GetForegroundWindow() == hwnd:
            if payment_page(pyautogui.screenshot(), win32gui.GetWindowRect(hwnd)):
                return True
        if time.monotonic() >= deadline:
            break
        time.sleep(POLL_INTERVAL)
    return False


def recover_page():
    if not refresh_booking():
        return False
    if check_page(verbose=False):
        print("刷新后仍在预约页面，继续选择第二天")
        return True

    print("刷新后未看到预约页标题，恢复入口窗口并重新进入")
    if not restore_entry_window():
        return False
    if check_page(verbose=False):
        print("恢复窗口后预约页已显示")
        return resize_wechat()

    move_mouse()  # 入口图像可能不在可见区域；只使用校准过的点击坐标。
    deadline = time.monotonic() + ENTRY_UNKNOWN_GRACE_SECONDS
    while time.monotonic() < deadline:
        if keyboard.is_pressed("esc"):
            print("检测到 Esc，停止重新进入预约页面")
            return False
        if check_page(verbose=False):
            print("重新进入预约页面成功")
            return resize_wechat()
        time.sleep(POLL_INTERVAL)
    print("刷新后仍未看到预约页标题，停止本轮以免误点")
    return False


def run_booking():
    print("程序开始，任意等待阶段均可按 Esc 停止")
    if not restore_entry_window() or not enter_booking() or not resize_wechat():
        return

    round_number = 0
    layout_checked = False
    while not keyboard.is_pressed("esc"):
        round_number += 1
        print(f"开始第 {round_number} 轮预约")

        tomorrow_ready = select_tomorrow()
        if CALIBRATION_PATH and not layout_checked:
            try:
                warning = check_layout(pyautogui.screenshot(), load_profile(CALIBRATION_PATH))
            except Exception as error:  # 非关键复核不能中断正在进行的预约。
                warning = f"运行时复核未完成：{error}；本轮继续，停止后请检查校准。"
            if warning:
                print(f"校准警告：{warning}", flush=True)
            layout_checked = True

        if tomorrow_ready == SOLD_OUT:
            print("本轮结果：目标时段已抢空，停止今天的预约")
            break

        if not tomorrow_ready:
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

        if not submit_booking():
            break
        verified = wait_verify()
        if verified is False:
            break
        if verified is True and wait_payment():
            print("本轮结果：已进入确认订单页面，停止今天的预约；请自行完成付款")
            break
        if keyboard.is_pressed("esc"):
            break
        print("未确认付款页面，刷新后重新选择")
        if not recover_page():
            break

    print("程序已安全停止")


def main():
    try:
        with booking_guard():
            run_booking()
    except LicenseError as error:
        print(f"本轮结果：云端许可：{error}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, pyautogui.FailSafeException):
        print("程序已由用户紧急停止")
