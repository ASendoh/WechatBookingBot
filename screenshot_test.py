import pyautogui
import time

print("3秒后截图微信区域")

time.sleep(3)

img = pyautogui.screenshot(
    region=(0, 0, 760, 1400)
)

img.save("wechat_area.png")

print("完成")