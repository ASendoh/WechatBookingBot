import pyautogui
from PIL import Image
import time


print("1秒后截图生成模板")

time.sleep(1)


# 截取微信窗口标题区域
img = pyautogui.screenshot(
    region=(0, 70, 400, 100)
)


# 保存完整截图（调试用）
img.save("booking_template.png")



print("模板生成完成")