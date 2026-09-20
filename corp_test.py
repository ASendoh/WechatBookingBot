from PIL import Image

img = Image.open("wechat_area.png")

# 截取顶部标题区域
crop = img.crop((0, 70, 400, 150))

crop.save("title_test.png")

print("完成")