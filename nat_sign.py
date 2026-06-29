import os
import time
import re
import sys
import ddddocr
import requests
from playwright.sync_api import sync_playwright

USER_EMAIL = os.getenv("USER_EMAIL", "")
USER_PASSWORD = os.getenv("USER_PASSWORD", "")

def send_wxpusher(msg):
    """如果有配置 WxPusher，则发送微信推送"""
    app_token = os.getenv("APP_TOKEN")
    uid = os.getenv("WX_PUSHER_UID")
    if app_token and uid:
        try:
            requests.post("https://wxpusher.zjiecode.com/api/send/message", json={
                "appToken": app_token,
                "content": msg,
                "summary": "NAT云自动任务通知",
                "contentType": 1,
                "uids": [uid]
            })
        except Exception as e:
            print(f"推送失败: {e}")

def init_browser(p):
    """初始化浏览器，加载防检测参数，绕过 Cloudflare"""
    browser = p.chromium.launch(
        headless=False, # 必须保持 False，利用 Xvfb 虚拟桌面运行，大幅降低被 CF 拦截的概率
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars"
        ]
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    # 深度注入隐藏 WebDriver 的 JS 代码 (反爬虫指纹伪装)
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    """)
    return browser, context.new_page()

def solve_math_captcha(page):
    """全局数字运算验证解决器（随时可能弹出）"""
    try:
        if page.locator("text=请计算").is_visible(timeout=2000) or page.locator("input[placeholder='请输入答案']").is_visible(timeout=1000):
            body_text = page.locator("body").inner_text()
            
            # 正则精准抓取 "请计算: 5 - 6" 里的数字和运算符
            match = re.search(r'请计算[:：]\s*(-?\d+)\s*([\+\-\*])\s*(-?\d+)', body_text)
            if match:
                n1, op, n2 = match.group(1), match.group(2), match.group(3)
                ans = int(eval(f"{n1} {op} {n2}"))
                print(f"🧮 触发数字运算验证: {n1} {op} {n2} = {ans}")
                
                ans_input = page.locator("input[placeholder*='答案']")
                if ans_input.is_visible():
                    ans_input.fill(str(ans))
                    time.sleep(1)
                    
                    submit_btn = page.locator("text=验证答案")
                    if submit_btn.is_visible():
                        submit_btn.click()
                        time.sleep(2)
                        print("✅ 数字运算验证提交成功！")
                        return True
    except Exception:
        pass
    return False

def main():
    if not USER_EMAIL or not USER_PASSWORD:
        print("❌ 致命错误：环境变量 USER_EMAIL 或 USER_PASSWORD 未设置！")
        sys.exit(1)

    print("🚀 初始化 OCR 图形识别引擎...")
    ocr = ddddocr.DdddOcr(show_ad=False)
    os.makedirs("screenshots", exist_ok=True)
    
    notify_msg = ""

    with sync_playwright() as p:
        browser, page = init_browser(p)

        try:
            # 1. 访问并穿透 Cloudflare 验证
            print("1️⃣ 访问登录页...")
            page.goto("https://nat.freecloud.ltd/login", timeout=60000)
            time.sleep(6)
            
            if "验证" in page.title() or "moment" in page.title().lower() or "Cloudflare" in page.content():
                print("🛡️ 遇到 Cloudflare 安全盾，正在模拟人类等待...")
                page.wait_for_selector("input[placeholder*='邮箱']", timeout=45000)
                print("✅ 已成功穿透 Cloudflare 防护！")

            # 2. 自动识别图形验证码并登录
            print("2️⃣ 开始登录流程...")
            for attempt in range(5):
                page.fill("input[placeholder*='邮箱']", USER_EMAIL)
                page.fill("input[type='password']", USER_PASSWORD)

                captcha_img = page.locator("img[src*='captcha']").first
                if captcha_img.is_visible():
                    captcha_img.screenshot(path="screenshots/captcha.png")
                    with open("screenshots/captcha.png", "rb") as f:
                        code = ocr.classification(f.read())
                    print(f"🤖 OCR 第 {attempt+1} 次识别结果: {code}")
                    page.fill("input[placeholder*='验证码']", code)

                page.locator("button:has-text('登录')").click()
                time.sleep(4)
                solve_math_captcha(page)

                if "login" not in page.url:
                    print("✅ 登录成功！")
                    notify_msg += "✅ 登录成功\n"
                    break
                
                if captcha_img.is_visible():
                    captcha_img.click()
                time.sleep(2)
            else:
                print("❌ 重试登录失败，脚本退出")
                page.screenshot(path="screenshots/login_failed.png")
                sys.exit(1)

            # 3. 自动签到
            print("3️⃣ 前往签到页面...")
            page.goto("https://nat.freecloud.ltd/addons?_plugin=19&_controller=index&_action=index")
            time.sleep(3)
            solve_math_captcha(page)

            sign_btn = page.locator("text=我要签到")
            if sign_btn.is_visible():
                sign_btn.click()
                time.sleep(2)
                if solve_math_captcha(page):
                    if sign_btn.is_visible():
                        sign_btn.click()
                        time.sleep(2)
                print("✅ 签到操作完毕！")
                notify_msg += "✅ 签到执行完毕\n"
            else:
                print("ℹ️ 未找到签到按钮，今日可能已签过。")
                notify_msg += "ℹ️ 今日已签到\n"
            
            page.screenshot(path="screenshots/after_sign.png")

            # 4. 遍历实例自动续费
            print("4️⃣ 开始检查主机续费...")
            page.goto("https://nat.freecloud.ltd/user") 
            time.sleep(3)
            solve_math_captcha(page)
            
            hrefs = page.evaluate("Array.from(document.querySelectorAll('a')).map(a => a.href).filter(h => h.includes('servicedetail?id='))")
            hrefs = list(set(hrefs))
            
            renewed_count = 0
            if hrefs:
                print(f"🔍 发现 {len(hrefs)} 个主机实例，进入详情页检查...")
                for href in hrefs:
                    page.goto(href)
                    time.sleep(3)
                    solve_math_captcha(page)
                    
                    renew_btn = page.locator("button:has-text('续费'), a:has-text('续费')").first
                    if renew_btn.is_visible():
                        print("💰 正在执行续费...")
                        renew_btn.click()
                        time.sleep(2)
                        confirm = page.locator("button:has-text('确定'), button:has-text('确认'), button:has-text('支付')").first
                        if confirm.is_visible():
                            confirm.click()
                            time.sleep(2)
                        renewed_count += 1
            else:
                renew_btns = page.locator("text=续费")
                for i in range(renew_btns.count()):
                    try:
                        btn = renew_btns.nth(i)
                        if btn.is_visible():
                            btn.click()
                            time.sleep(2)
                            confirm = page.locator("button:has-text('确定'), button:has-text('确认')").first
                            if confirm.is_visible():
                                confirm.click()
                            renewed_count += 1
                    except Exception:
                        pass
            
            print(f"🎉 续费流程结束，共执行续费 {renewed_count} 次。")
            notify_msg += f"🎉 尝试续费主机数: {renewed_count}\n"
            page.screenshot(path="screenshots/after_renew.png")

            send_wxpusher(notify_msg)

        except Exception as e:
            print(f"❌ 运行发生严重异常: {e}")
            page.screenshot(path="screenshots/fatal_error.png")
            send_wxpusher(f"❌ NAT任务报错:\n{e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()