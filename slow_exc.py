import os
import time
import random
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin

import imghdr
import shutil

# 目标页面地址
url = ""

# 配置 Selenium 的 Chrome 选项
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-dev-shm-usage")  # 解决内存不足问题
chrome_options.add_argument("--no-sandbox")  # 提高稳定性

# 初始化 ChromeDriver
driver = webdriver.Chrome(options=chrome_options)

# 提取所有页面链接（从网站页面数获取）
def get_all_page_urls(base_url):
    driver.get(base_url)
    time.sleep(3)
    
    # 查找页面导航元素，获取总页数
    try:
        # 找到页码信息 - 根据网站实际情况调整选择器
        pagination = driver.find_element(By.CSS_SELECTOR, ".pageinfo")
        total_pages = int(pagination.text.split('/')[-1].strip())
        print(f"检测到共有 {total_pages} 页内容")
    except Exception as e:
        print(f"获取页数失败，将使用默认单页模式: {e}")
        total_pages = 1
    
    # 构建所有页面的URL
    page_urls = []
    for page in range(1, total_pages + 1):
        # 构建各页URL - 根据网站URL结构调整
        if page == 1:
            page_urls.append(base_url)
        else:
            page_url = base_url.replace('.html', f'-page-{page}.html')
            page_urls.append(page_url)
    
    return page_urls

# 从单个页面提取图片URL
def extract_images_from_page(page_url):
    print(f"正在处理页面: {page_url}")
    driver.get(page_url)
    
    # 初始等待，让页面基本内容加载完成
    time.sleep(5)
    
    # 获取初始页面高度
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    # 持续滚动直到页面高度不再变化（说明已到底部）
    scroll_attempts = 0
    max_attempts = 10  # 增加最大尝试次数
    
    print("开始渐进式滚动页面...")
    while scroll_attempts < max_attempts:
        # 渐进式滚动 - 分多次滚动到底部
        for scroll_position in [0.3, 0.6, 0.8, 1.0]:
            driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {scroll_position});")
            time.sleep(1)  # 每次滚动后等待，让内容有时间加载
        
        # 强制等待更长时间，确保懒加载内容被触发并完成加载
        time.sleep(3)
        
        # 检查页面高度是否变化
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            scroll_attempts += 1
            print(f"页面高度未变化，第 {scroll_attempts}/{max_attempts} 次确认...")
            
            # 尝试晃动滚动，有时候可以触发额外的加载
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 100);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        else:
            # 高度变化，重置计数
            scroll_attempts = 0
            last_height = new_height
            print(f"页面高度变化，继续滚动... 新高度: {new_height}")
    
    print("页面滚动完成，已达到底部或最大尝试次数")
    
    # 最后再执行一次完整滚动，确保所有内容都被加载
    for i in range(10):
        pos = i / 10.0
        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {pos});")
        time.sleep(0.5)
    
    # 检查是否有"加载更多"或"下一页"按钮
    try:
        # 扩展按钮查找范围
        load_more_selectors = [
            "//a[contains(text(), '加载更多')]",
            "//a[contains(text(), '下一页')]",
            "//button[contains(text(), '加载更多')]",
            "//span[contains(text(), '加载更多')]",
            "//div[contains(@class, 'load-more')]",
            "//div[contains(@class, 'next-page')]"
        ]
        
        for selector in load_more_selectors:
            buttons = driver.find_elements(By.XPATH, selector)
            for button in buttons:
                if button.is_displayed():
                    print(f"找到并点击按钮: '{button.text.strip() or '加载更多按钮'}'")
                    driver.execute_script("arguments[0].scrollIntoView();", button)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", button)
                    print("点击了加载更多按钮")
                    time.sleep(5)  # 增加等待时间，确保内容加载
                    
                    # 再次滚动确保新加载的内容可见
                    for scroll_pos in [0.3, 0.6, 0.8, 1.0]:
                        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {scroll_pos});")
                        time.sleep(1)
    except Exception as e:
        print(f"查找/点击加载更多按钮时出错: {e}")
    
    # 最终等待，确保所有图片都完全加载
    print("最终等待页面完全加载...")
    time.sleep(8)
    
    # 获取页面源码并解析
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    
    # 添加更多可能的图片选择器
    img_tags = []
    selectors = [
        "#img_list div img",
        ".img_list img",
        ".pic_box img",
        ".gallery img",
        "img.lazy",
        "img[data-original]",  # 直接选取有data-original属性的img标签
        "img[src*='.jpg'], img[src*='.jpeg'], img[src*='.png'], img[src*='.gif']",
        ".mainbody img",
        "article img",
        ".content img",
        "img[src]:not([src=''])",  # 所有有效src的图片
    ]
    
    for selector in selectors:
        found_tags = soup.select(selector)
        if found_tags:
            img_tags.extend(found_tags)
            print(f"使用选择器 '{selector}' 找到 {len(found_tags)} 张图片")
    
    # 增强的去重逻辑
    unique_srcs = set()
    unique_img_tags = []
    
    for img in img_tags:
        # 获取所有可能的图片地址属性
        src = None
        for attr in ['src', 'data-src', 'data-original', 'data-lazy-src', 'data-url']:
            if img.get(attr):
                src = img[attr]
                break
                
        if src and src not in unique_srcs and not src.endswith('.svg'):
            # 过滤掉小图标和透明占位图
            if 'icon' not in src.lower() and 'blank' not in src.lower():
                unique_srcs.add(src)
                unique_img_tags.append(img)
    
    print(f"当前页面总共找到 {len(unique_img_tags)} 张不重复图片")
    return unique_img_tags

# 主函数
def main():
    total_images = []
    
    try:
        # 获取所有页面URL
        page_urls = get_all_page_urls(url)
        print(f"共检测到 {len(page_urls)} 个页面")
        
        # 处理每个页面
        for page_idx, page_url in enumerate(page_urls, 1):
            print(f"\n===== 处理第 {page_idx}/{len(page_urls)} 页 =====")
            try:
                img_tags = extract_images_from_page(page_url)
                total_images.extend(img_tags)
                print(f"当前已找到总计 {len(total_images)} 张图片")
            except Exception as e:
                print(f"处理页面 {page_url} 时出错: {e}")
                # 尝试重启浏览器
                try:
                    driver.quit()
                    time.sleep(2)
                    driver = webdriver.Chrome(options=chrome_options)
                except:
                    pass
            
            # 页面间休息，避免请求过快
            pause_time = random.uniform(3, 6)
            print(f"页面处理完成，休息 {pause_time:.1f} 秒...")
            time.sleep(pause_time)
        
        print(f"\n全部页面处理完毕，共找到 {len(total_images)} 张图片")
        
        # 保存文件夹修正 - 使用"test2"文件夹
        os.makedirs("test2", exist_ok=True)
        
        # 设置请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": url,
        }
        
        # 下载图片
        for idx, img in enumerate(total_images, start=1):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if not src:
                continue
                
            # 补全URL
            if src.startswith("//"):
                src = "https:" + src
            img_url = urljoin(url, src)
            
            print(f"正在下载第 {idx}/{len(total_images)} 张图片: {img_url}")
            
            # 随机延迟
            time.sleep(random.uniform(1, 3))
            
            try:
                with requests.get(img_url, headers=headers, timeout=(10, 30), stream=True) as img_resp:
                    if img_resp.status_code == 200:
                        # 处理图片类型
                        content_type = img_resp.headers.get('Content-Type', '').lower()
                        
                        # 先读取部分确定类型
                        img_data = img_resp.raw.read(32)
                        img_type = imghdr.what(None, h=img_data)
                        
                        # 确定扩展名
                        if img_type:
                            ext = f".{img_type}"
                        elif 'gif' in content_type:
                            ext = '.gif'
                        elif 'png' in content_type:
                            ext = '.png'
                        else:
                            ext = os.path.splitext(img_url)[1] or ".jpg"
                            
                        filename = os.path.join("test2", f"{idx:04d}{ext}")
                        
                        # 保存图片
                        with open(filename, "wb") as f:
                            f.write(img_data)
                            shutil.copyfileobj(img_resp.raw, f)
                            
                        print(f"✓ 已保存: {filename}")
                    else:
                        print(f"× 下载失败，状态码: {img_resp.status_code}")
                        
            except Exception as e:
                print(f"× 下载出错: {e}")
                
            # 每下载10张暂停一下
            if idx % 50 == 0:
                pause = random.uniform(3, 6)
                print(f"已下载 {idx} 张图片，暂停 {pause:.1f} 秒...")
                time.sleep(pause)
                
        print(f"所有图片下载完成! 共下载 {len(total_images)} 张图片。")
        
    finally:
        # 确保浏览器关闭
        driver.quit()

if __name__ == "__main__":
    main()