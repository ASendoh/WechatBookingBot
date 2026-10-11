import time

import pyautogui
import keyboard
import win32gui

import ai_assist
from ai_assist import assistant as ai_assistant
from calibration import check_layout, load_profile
from check_page import check_entry, check_page
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
PAYMENT_READY = "payment_ready"


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

    if not check_entry(verbose=False):
        print("刷新后仍是未知页面，交由异常恢复处理；不点击场馆入口")
        return False
    move_mouse()
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


def capture_wechat():
    hwnd = win32gui.FindWindow(None, "微信")
    if not hwnd or win32gui.GetForegroundWindow() != hwnd:
        raise RuntimeError("微信不在前台，不能发送其他窗口的截图")
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return pyautogui.screenshot(region=(left, top, right - left, bottom - top))


def payment_appeared_during_recovery():
    try:
        image = capture_wechat()
        return payment_page(image, (0, 0, image.width, image.height))
    except pyautogui.FailSafeException:
        raise
    except Exception:
        return False


def recover_with_ai(reason):
    if keyboard.is_pressed("esc"):
        return False
    action = None
    if ai_assist.ENABLE_AI_ASSIST:
        print(f"异常：{reason}；询问 AI，最多等待 3 秒", flush=True)
        try:
            action = ai_assistant.decide(reason, capture_wechat, lambda: keyboard.is_pressed("esc"))
        except pyautogui.FailSafeException:
            raise
        except Exception as error:
            print(f"AI 不可用：{error}", flush=True)
    else:
        print(f"异常：{reason}；AI 已暂时停用，直接执行本地刷新恢复", flush=True)
    if keyboard.is_pressed("esc"):
        return False
    if payment_appeared_during_recovery():
        return PAYMENT_READY
    if ai_assist.ENABLE_AI_ASSIST:
        print(f"AI 决策：{action}" if action else "未收到有效 AI 答复，立即刷新继续", flush=True)
    try:
        if action == "reenter":
            if restore_entry_window() and check_entry(verbose=False) and enter_booking() and resize_wechat():
                return True
        # 刷新按钮使用预约窗口坐标；先恢复窗口，避免在错误位置点击。
        if not resize_wechat():
            return False
        return recover_page()
    except pyautogui.FailSafeException:
        raise
    except Exception as error:
        print(f"恢复暂未完成，将继续尝试：{error}", flush=True)
        return False


def run_booking():
    print("程序开始，任意等待阶段均可按 Esc 停止")
    prepared = False
    round_number = 0
    layout_checked = False
    while not keyboard.is_pressed("esc"):
        stage = "进入预约页"
        try:
            if not prepared:
                if not restore_entry_window() or not enter_booking() or not resize_wechat():
                    raise RuntimeError("微信不在场馆首页或预约页，或窗口无法恢复")
                prepared = True
            round_number += 1
            print(f"开始第 {round_number} 轮预约")

            stage = "选择第二天"
            tomorrow_ready = select_tomorrow()
            if tomorrow_ready == SOLD_OUT:
                print("本轮结果：目标时段已抢空，停止今天的预约")
                break
            if CALIBRATION_PATH and not layout_checked:
                layout_checked = True
                warning = check_layout(pyautogui.screenshot(), load_profile(CALIBRATION_PATH))
                if warning:
                    print(f"校准警告：{warning}", flush=True)
                    raise RuntimeError(warning)

            if not tomorrow_ready:
                raise RuntimeError("第二天或场地页面未正常显示")

            stage = "选择场地"
            selected = select_court()
            if keyboard.is_pressed("esc"):
                break
            if not selected:
                raise RuntimeError("没有选中时段，无法继续提交")

            stage = "提交预约"
            if not submit_booking():
                if keyboard.is_pressed("esc"):
                    break
                raise RuntimeError("提交预约未完成")
            stage = "等待验证或付款页"
            verified = wait_verify()
            if verified is False:
                break
            if verified is True and wait_payment():
                print("本轮结果：已进入确认订单页面，停止今天的预约；请自行完成付款")
                break
            if keyboard.is_pressed("esc"):
                break
            raise RuntimeError("未检测到验证窗口" if verified is None else "未确认付款页面")
        except (pyautogui.FailSafeException, LicenseError):
            raise
        except Exception as error:
            prepared = recover_with_ai(f"{stage}：{error}")
            if prepared == PAYMENT_READY:
                print("本轮结果：已进入确认订单页面，停止今天的预约；请自行完成付款")
                break
            if not prepared and not keyboard.is_pressed("esc"):
                time.sleep(POLL_INTERVAL)

    print("程序已安全停止")


def main():
    try:
        if ai_assist.ENABLE_AI_ASSIST:
            try:
                ai_assistant.start()
            except Exception as error:
                print(f"AI 启动失败，继续本地抢场：{error}", flush=True)
        else:
            print("AI 功能已暂时停用，使用本地抢场规则", flush=True)
        with booking_guard():
            run_booking()
    except LicenseError as error:
        print(f"本轮结果：云端许可：{error}", flush=True)
    finally:
        if ai_assist.ENABLE_AI_ASSIST:
            ai_assistant.close()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, pyautogui.FailSafeException):
        print("程序已由用户紧急停止")
