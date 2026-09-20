import pyautogui
import time

print("程序开始")

time.sleep(3)

x, y = pyautogui.position()

print("当前鼠标位置：")
print(x, y)