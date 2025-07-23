import os
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin

import imghdr
import shutil

# 目标页面地址
url = " "

# 配置 Selenium 的 Chrome 选项（无界面模式）
chrome_options = Options()
chrome_options.add_argument("--headless")         # 无界面
chrome_options.add_argument("--disable-gpu")      # 禁用 GPU
chrome_options.add_argument("--window-size=1920,1080")

# 初始化 ChromeDriver（确保 chromedriver 在系统 PATH 或指定其路径）
driver = webdriver.Chrome(options=chrome_options)

# 打开目标页面
driver.get(url)

# 渐进式分段滚动，直到图片数量不再增加
last_img_count = 0
no_change_count = 0
max_no_change = 3
max_scroll_times = 10000

for i in range(max_scroll_times):
    # 分段滚动到页面不同高度，模拟用户慢慢下滑
    for scroll_position in [0.3, 0.6, 0.8, 1.0]:
        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {scroll_position});")
        time.sleep(1)
    # 晃动滚动条，进一步触发懒加载
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 100);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    img_tags = soup.select("#img_list div img")
    print(f"第{i+1}次滚动后，图片数：{len(img_tags)}")
    if len(img_tags) == last_img_count:
        no_change_count += 1
        if no_change_count >= max_no_change:
            print(f"连续{max_no_change}次图片数量未增加，停止滚动。")
            break
    else:
        no_change_count = 0
    last_img_count = len(img_tags)

# 最终获取所有图片标签
html = driver.page_source
driver.quit()
soup = BeautifulSoup(html, "html.parser")
img_tags = soup.select("#img_list div img")
print(f"共找到 {len(img_tags)} 张图片")

# 创建用于保存图片的文件夹
os.makedirs("images", exist_ok=True)

# 设置请求头
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# 遍历图片标签并依次下载图片
for idx, img in enumerate(img_tags, start=1):
    src = img.get("src")
    if not src:
        continue
    # 如果图片地址以 "//" 开头，补全为 "https://"
    if src.startswith("//"):
        src = "https:" + src
    img_url = urljoin(url, src)
    print(f"正在下载第 {idx} 张图片：{img_url}")
    try:
        with requests.get(img_url, headers=headers, stream=True) as img_resp:
            if img_resp.status_code == 200:
                # 先读取部分内容以确定图片类型
                img_data = img_resp.raw.read(32)
                img_type = imghdr.what(None, h=img_data)
                if img_type:
                    ext = f".{img_type}"
                else:
                    ext = os.path.splitext(img_url)[1] or ".jpg"
                filename = os.path.join("images", f"{idx:03d}{ext}")
                # 将已读取的部分和剩余内容写入文件
                with open(filename, "wb") as f:
                    f.write(img_data)
                    shutil.copyfileobj(img_resp.raw, f)
            else:
                print(f"下载第 {idx} 张图片失败，状态码：{img_resp.status_code}")
    except Exception as e:
        print(f"下载第 {idx} 张图片时发生异常：{e}")

print("所有图片下载完成！")
