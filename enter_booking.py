import time

from move_mouse import move_mouse
from check_page import check_page


def enter_booking():

    while True:

        print("尝试进入羽毛球预约页面")

        # 点击羽毛球馆
        move_mouse()

        # 检测是否进入
        if check_page():

            print("成功进入预约页面")
            return True

        else:

            print("进入失败，重新尝试")
            time.sleep(0.1)