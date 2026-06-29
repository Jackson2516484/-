import os
import time
import re
import sys
import random
import ddddocr
import requests
from playwright.sync_api import sync_playwright

USER_EMAIL = os.getenv("USER_EMAIL", "")
USER_PASSWORD = os.getenv("USER_PASSWORD", "")

def send_wxpusher(msg):
    """发送微信推送通知"""
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
    """启动强力绕盾模式上下文"""
    # 强制在 Linux 下启用图形化加速特征
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--window-size=1280,720",
            "--start-maximized"
        ]
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    # 彻底抹除自动化 WebDriver 痕迹
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    """)
    return browser, context.new_page()

def human_like_click(page, locator):
    """拟态真人鼠标轨迹点击，破除 Cloudflare 人机行为分析"""
    try:
        box = locator.bounding_box()
        if box:
            x = box["x"] + box["width"] / 2 + random.uniform(-5, 5)
            y = box["y"] + box["height"] / 2 + random.uniform(-5, 5)
            page.mouse.move(x, y, steps=random.randint(10, 20))
            time.sleep(random.uniform(0.1, 0.3))
            page.mouse.down()
            time.sleep(random.uniform(0.05, 0.15))
            page.mouse.up()
            return True
    except Exception:
        pass
    return False

def bypass_cf(page):
    """主动式 Cloudflare Turnstile 击穿逻辑"""
    print("🛡️ 开始检测并物理击穿 Cloudflare 安全验证...")
    for _ in range(12):
        # 如果邮箱框出来了，说明根本没盾或盾已解开
        if page.locator("input[placeholder*='邮箱']").is_visible():
            print("✅ 页面已通畅，验证完毕！")
            return True
        
        # 寻找 CF 验证的专属 iframe 框架或复选框
        cf_frames = page.frames
        for frame in cf_frames:
            if "cloudflare" in frame.url.lower() or "turnstile" in frame.url.lower():
                cb = frame.locator("input[type='checkbox'], .cb-lb, #challenge-stage").first
                if cb.is_visible():
                    print("⚡ 捕获到 CF 互动盾复选框，执行拟态击穿点击...")
                    human_like_click(page, cb)
                    time.sleep(4)
        
        time.sleep(2)
    return False

def solve_math_captcha(page):
    """全局数字运算验证解决器（每次变动题型）"""
    try:
        if page.locator("text=请计算").is_visible(timeout=2000) or page.locator("input[placeholder='请输入答案']").is_visible(timeout=1000):
            body_text = page.locator("body").inner_text()
            match = re.search(r'请计算[:：]\s*(-?\d+)\s*([\+\-\*])\s*(-?\d+)', body_text)
            if match:
                n1, op, n2 = match.group(1), match.group(2), match.group(3)
                ans = int(eval(f"{n1} {op} {n2}"))
                print(f"🧮 自动计算算术验证: {n1} {op} {n2} = {ans}")
                
                ans_input = page.locator("input[placeholder*='答案']")
                if ans_input.is_visible():
                    ans_input.fill(str(ans))
                    time.sleep(1)
                    page.locator("text=验证答案").click()
                    time.sleep(2)
                    return True
    except Exception:
        pass
    return False

def main():
    if not USER_EMAIL or not USER_PASSWORD:
        print("❌ 致命错误：环境变量未配置！")
        sys.exit(1)

    ocr = ddddocr.DdddOcr(show_ad=False)
    os.makedirs("screenshots", exist_ok=True)
    notify_msg = ""

    with sync_playwright() as p:
        browser, page = init_browser(p)

        try:
            print("1️⃣ 访问登录页...")
            page.goto("https://nat.freecloud.ltd/login", timeout=60000)
            time.sleep(5)
            
            # 主动物理击穿 CF 盾
            if not bypass_cf(page):
                print("⚠️ 未能通过常规击穿判定，尝试终极盲等...")
                page.wait_for_selector("input[placeholder*='邮箱']", timeout=25000)

            print("2️⃣ 执行登录流程...")
            for attempt in range(5):
                page.fill("input[placeholder*='邮箱']", USER_EMAIL)
                page.fill("input[type='password']", USER_PASSWORD)

                captcha_img = page.locator("img[src*='captcha']").first
                if captcha_img.is_visible():
                    captcha_img.screenshot(path="screenshots/captcha.png")
                    with open("screenshots/captcha.png", "rb") as f:
                        code = ocr.classification(f.read())
                    print(f"🤖 图形验证码 OCR 识别结果: {code}")
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
                print("❌ 重试登录失败")
                page.screenshot(path="screenshots/login_failed.png")
                sys.exit(1)

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
                notify_msg += "✅ 签到执行完毕\n"
            else:
                notify_msg += "ℹ️ 今日已签到\n"
            
            page.screenshot(path="screenshots/after_sign.png")

            print("4️⃣ 扫描主机并续费...")
            page.goto("https://nat.freecloud.ltd/user") 
            time.sleep(3)
            solve_math_captcha(page)
            
            hrefs = page.evaluate("Array.from(document.querySelectorAll('a')).map(a => a.href).filter(h => h.includes('servicedetail?id='))")
            hrefs = list(set(hrefs))
            renewed_count = 0
            
            if hrefs:
                for href in hrefs:
                    page.goto(href)
                    time.sleep(3)
                    solve_math_captcha(page)
                    renew_btn = page.locator("button:has-text('续费'), a:has-text('续费')").first
                    if renew_btn.is_visible():
                        renew_btn.click()
                        time.sleep(2)
                        confirm = page.locator("button:has-text('确定'), button:has-text('确认'), button:has-text('支付')").first
                        if confirm.is_visible():
                            confirm.click()
                            time.sleep(2)
                        renewed_count += 1
            
            notify_msg += f"🎉 续费实例数量: {renewed_count}\n"
            page.screenshot(path="screenshots/after_renew.png")
            send_wxpusher(notify_msg)

        except Exception as e:
            print(f"❌ 任务运行报错: {e}")
            page.screenshot(path="screenshots/fatal_error.png")
            send_wxpusher(f"❌ NAT自动任务报错:\n{e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
