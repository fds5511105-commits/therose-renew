#!/usr/bin/env python3

import os,re,sys,time,requests
from seleniumbase import SB

# 环境变量 
EMAIL = os.environ.get("EMAIL") or ""
PASSWORD = os.environ.get("PASSWORD") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or ""
PROXY_URL = os.environ.get("PROXY") or ""  # 代理

BASE_URL = "https://client.therose.cloud/login"
REPO_URL = "https://github.com/btpp05/therose-renew"

if not EMAIL or not PASSWORD:
    print("❌ 请设置环境变量 EMAIL 和 PASSWORD")
    sys.exit(1)

def send_tg(token, chat_id, message):
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        if resp.status_code == 200:
            print("📨 Telegram 通知已发送")
        else:
            print(f"❌ Telegram 发送失败: {resp.text}")
    except Exception as e:
        print(f"❌ Telegram 发送异常: {e}")

def send_tg_photo(token, chat_id, photo_path, caption=""):
    if not token or not chat_id:
        return
    if not os.path.exists(photo_path):
        return
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            resp = requests.post(url, data={"chat_id": chat_id, "caption": caption},
                                files={"photo": f}, timeout=15)
        if resp.status_code == 200:
            print(f"📸 截图已发 TG: {photo_path}")
        else:
            print(f"❌ TG 截图发送失败: {resp.text[:200]}")
    except Exception as e:
        print(f"❌ TG 截图发送异常: {e}")

def get_page_errors(sb):
    """从页面源码抓取报错信息"""
    try:
        src = sb.get_page_source()
        keywords = [r'incorrect', r'invalid', r'wrong', r'error', r'fail',
                    r'not found', r'错误', r'失败', r'不正确', r'locked']
        for pat in keywords:
            m = re.search(pat, src, re.IGNORECASE)
            if m:
                s = max(0, m.start() - 120)
                err = re.sub(r'<[^>]+>', ' ', src[s:m.end() + 120]).strip()
                return err[:300]
    except:
        pass
    return None

def click_extend_button(sb):
    selectors = [
        'span:contains("Extend")',
        'button:contains(title="Extend")',
    ]
    for sel in selectors:
        try:
            if sb.find_element(sel, timeout=2):
                print(f"✅ 找到按钮，选择器: {sel}")
                sb.uc_click(sel, timeout=5)
                print("✅ 点击成功")
                return True, {}
        except:
            continue
    try:
        btn = sb.find_element('button:contains("Extend")', timeout=2)
        sb.driver.execute_script("arguments[0].click();", btn)
        print("✅ 通过 JavaScript 点击成功")
        return True, {}
    except Exception as e:
        return False, {"error": str(e)}

def check_renewal_success(sb):
    """检查是否出现续期成功的提示"""
    success_selectors = [
        '.alert-success',
        '.alert.alert-success',
        'div[role="alert"].alert-success',
        'div.alert-success',
        'span:contains("successfully purchased")',
        'div:contains("successfully purchased")'
    ]
    
    print("⏳ 等待5秒检查续期结果...")
    time.sleep(5)
    
    for selector in success_selectors:
        try:
            element = sb.find_element(selector, timeout=2)
            if element:
                text = element.text
                print(f"✅ 发现成功提示！选择器: {selector}")
                print(f"📝 提示内容: {text}")
                return True, text
        except:
            continue
    
    try:
        page_source = sb.get_page_source()
        if "successfully purchased" in page_source.lower():
            print("✅ 页面源码中发现 'successfully purchased' 关键词")
            return True, "服务器已成功续期"
    except:
        pass
    
    return False, "未检测到续期成功提示"

def login(sb, email, password):
    print("🌐 打开登录页面...")
    sb.open(BASE_URL)
    sb.wait_for_ready_state_complete()
    time.sleep(2)

    print("📧 填写邮箱...")
    sb.type('#login_form_email', email, timeout=10)
    print("🔑 填写密码...")
    sb.type('#login_form_password', password, timeout=10)
    time.sleep(1)

    print("🛡 处理 Turnstile...")
    try:
        try:
            sb.wait_for_element_present("iframe[src*='captcha'], .cf-turnstile, iframe.cf-turnstile-widget", timeout=10)
        except Exception:
            pass
        time.sleep(2)
        sb.uc_gui_click_captcha()
        print("✅ Turnstile 验证已处理")
        time.sleep(8)
        # 截图发TG诊断
        sb.save_screenshot("turnstile_after.png")
        send_tg_photo(TG_BOT_TOKEN, TG_CHAT_ID, "turnstile_after.png", "🛡️ Turnstile 处理后截图（看盾的勾打上没）")
    except Exception as e:
        print(f"⚠️ Turnstile 处理异常: {e}")

    print("🔑 点击登录按钮...")
    sb.uc_click('button:contains("Sign in")')

    for _ in range(30):
        current_url = sb.get_current_url()
        page_title = sb.get_title() or ""
        print(f"📄 当前 URL: {current_url} | Title: {page_title}")
        if "panel" in current_url or "dashboard" in current_url or "client" in current_url.lower():
            print("✅ 登录成功，已跳转到 Dashboard")
            return True, current_url
        time.sleep(1)

    print(f"❌ 登录失败，当前 URL: {sb.get_current_url()}")
    # 截图发TG诊断
    sb.save_screenshot("login_failed.png")
    send_tg_photo(TG_BOT_TOKEN, TG_CHAT_ID, "login_failed.png", f"❌ 登录失败，URL: {sb.get_current_url()}")
    err = get_page_errors(sb)
    if err:
        print(f"⚠️ 页面报错: {err}")
    return False, sb.get_current_url()

def main():
    print("🚀 启动浏览器")

    sb_kwargs = {"uc": True, "headless": False}
    if PROXY_URL:
        print(f"🔗 使用代理: {PROXY_URL}")
        sb_kwargs["proxy"] = PROXY_URL

    with SB(**sb_kwargs) as sb:
        # 检测出口IP
        proxy_ip = ""
        try:
            sb.open("https://api.ipify.org?format=json")
            ip_text = sb.get_text("body")
            proxy_ip = ip_text.strip()[:50]
            print(f"📍 当前出口IP: {proxy_ip}")
        except:
            print("⚠️ 获取 IP 失败")

        success, url = login(sb, EMAIL, PASSWORD)
        
        if not success:
            msg = f"❌ 登录失败\n🌐 IP: {proxy_ip}\n📦 仓库: {REPO_URL}"
            print(msg)
            send_tg(TG_BOT_TOKEN, TG_CHAT_ID, msg)
            return

        print("📄 开始续期流程...")
        
        ok, info = click_extend_button(sb)
        if not ok:
            msg = f"❌ 点击 Extend 按钮失败: {info.get('error')}\n📦 仓库: {REPO_URL}"
            print(msg)
            send_tg(TG_BOT_TOKEN, TG_CHAT_ID, msg)
            return
        
        time.sleep(1)
        
        try:
            button = sb.find_element('button:contains("Order now")', timeout=5)
            if button:
                print("🛒 点击 Order now 按钮...")
                sb.uc_click('button:contains("Order now")')
                print("✅ 已点击 Order now 按钮")
            else:
                msg = f"❌ 未找到 Order now 按钮\n📦 仓库: {REPO_URL}"
                print(msg)
                send_tg(TG_BOT_TOKEN, TG_CHAT_ID, msg)
                return
        except Exception as e:
            msg = f"❌ 点击 Order now 失败: {e}\n📦 仓库: {REPO_URL}"
            print(msg)
            send_tg(TG_BOT_TOKEN, TG_CHAT_ID, msg)
            return
        
        print("🔍 检查续期结果...")
        renewal_success, renewal_msg = check_renewal_success(sb)
        
        if renewal_success:
            msg = f"✅ The Rose Cloud 续期成功！\n{renewal_msg}\n🌐 IP: {proxy_ip}\n📦 仓库: {REPO_URL}"
            print(msg)
            sb.save_screenshot("renewal_success.png")
        else:
            msg = f"❌ 续期可能失败: {renewal_msg}\n🌐 IP: {proxy_ip}\n📦 仓库: {REPO_URL}"
            print(msg)
            sb.save_screenshot("renewal_failed.png")
        
        send_tg(TG_BOT_TOKEN, TG_CHAT_ID, msg)

    print("🏁 脚本执行完毕")

if __name__ == "__main__":
    main()