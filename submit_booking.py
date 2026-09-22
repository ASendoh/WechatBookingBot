import pyautogui
import keyboard
import time

from config import SLIDER_START_POS, SUBMIT_POS
from mouse_recorder import play


def submit_booking() -> bool:
    if keyboard.is_pressed("esc"):
        print("检测到 Esc，不提交预约")
        return False

    print("点击提交预约")
    pyautogui.click(*SUBMIT_POS)
    print("提交预约点击完成")
    #pyautogui.moveTo(*SLIDER_START_POS)

    return True
