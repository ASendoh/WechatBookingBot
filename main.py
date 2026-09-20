import pyautogui

from enter_booking import enter_booking
from resize_wechat import resize_wechat
from select_tomorrow_test import select_tomorrow
from select_court import select_court
from submit_booking import submit_booking

# 关闭 PyAutoGUI 操作后的统一暂停，必要的等待由各步骤显式控制。
pyautogui.PAUSE = 0

# 保留 PyAutoGUI 的紧急停止功能。
pyautogui.FAILSAFE = True


print("程序开始")

enter_booking()       # 1. 进入预约页面
select_tomorrow()     # 2. 点击第二天
resize_wechat()       # 3. 调整窗口大小
select_court()        # 4. 依次选择配置中的场地和时段
submit_booking()      # 5. 保持原逻辑，继续点击提交预约

print("流程测试完成")