import time

from enter_booking import enter_booking
from resize_wechat import resize_wechat
from select_tomorrow_test import select_tomorrow
from select_court import select_court
from submit_booking import submit_booking


print("程序开始")

enter_booking()       # 1. 进入预约页面

select_tomorrow()     # 2. 点击第二天

resize_wechat()       # 3. 调整窗口大小

select_court()        # 4. 点击场地

submit_booking()      # 5. 点击提交预约

print("流程测试完成")