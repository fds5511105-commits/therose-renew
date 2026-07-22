#!/usr/bin/env python3

import os, re, sys, time, requests
from datetime import datetime
from seleniumbase import SB

EMAIL = os.environ.get("EMAIL") or ""
PASSWORD = os.environ.get("PASSWORD") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or ""
PROXY_URL = os.environ.get("PROXY") or ""

LOGIN_URL = "https://client.therose.cloud/login"
REPO_URL = "https://github.com/btpp05/therose-renew"

if not EMAIL or not PASSWORD:
    print("❌ 请设置环境变量 EMAIL 和 PASSWORD")
    sys.exit(1)

def send_tg(token, chat_id, message):
    if not token or not chat_id:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": message}, timeout=10)
        print("📨 Telegram 通知已发送")
    except Exception as e:
        print(f"❌ Telegram 发送异常: {e}")

def send_tg_photo(token, chat_id, photo_path, caption=""):
    if not token or not chat_id or not os.path.exists(photo_path):
        return
    try:
        with open(photo_path, "rb") as f:
            resp = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                                 data={"chat_id": chat_id, "caption": caption},
                                 files={"photo": f}, timeout=15)
        if resp.status_code == 200:
            print(f"📸 截图已发 TG")
        else:
            print(f"❌ TG 截图发送失败: {resp.text[:200]}")
    except Exception as e:
        print(f"❌ TG 截图发送异常: {e}")

def get_page_errors(sb):
    try:
        src = sb.get_page_source()
        for pat in [r'incorrect', r'invalid', r'wrong', r'error', r'fail',
                    r'Verification failed', r'not found', r'错误', r'失败']:
            m = re.search(pat, src, re.IGNORECASE)
            if m:
                s = max(0, m.start() - 120)
                return re.sub(r'<[^>]+>', ' ', src[s:m.end() + 120]).strip()[:300]
    except:
        pass
    return None

def login(sb):
    print("🌐 打开登录页面...")
    sb.open(LOGIN_URL)
    sb.wait_for_ready_state_complete()
    time.sleep(2)

    print("📧 填写邮箱...")
    sb.type('#login_form_email', EMAIL, timeout=10)
    print("🔑 填写密码...")
    sb.type('#login_form_password', PASSWORD, timeout=10)
    time.sleep(1)

    print("🛡️ 处理 Turnstile...")
    try:
        try:
            sb.wait_for_element_present("iframe[src*='captcha'], .cf-turnstile, iframe.cf-turnstile-widget", timeout=10)
        except Exception:
            pass
        time.sleep(2)
        clicked = False
        try:
            sb.uc_gui_click_captcha()
            clicked = True
            print("✅ uc_gui_click_captcha 已点击")
        except Exception as e:
            print(f"⚠️ uc_gui_click_captcha 失败: {e}")
        # 兜底：直接点 .cf-turnstile 控件
        if not clicked:
            try:
                sb.uc_click('.cf-turnstile, #cf-turnstile, iframe.cf-turnstile-widget', timeout=5)
                clicked = True
                print("✅ 兜底点击 Turnstile 控件")
            except Exception as e2:
                print(f"⚠️ 兜底点击也失败: {e2}")
        # 立即截图看点击后状态（spinner / 交互式挑战），区分"没点到" vs "CF 拒了"
        sb.save_screenshot("turnstile_click.png")
        send_tg_photo(TG_BOT_TOKEN, TG_CHAT_ID, "turnstile_click.png", "🛡️ Turnstile 点击后立即状态")
        print("✅ Turnstile 已点击，等待验证...")
        # 轮询 cf-turnstile-response 隐藏字段，确认 CF 真放过
        solved = False
        for _ in range(30):
            try:
                val = sb.execute_script(
                    "var el=document.querySelector('[name=\"cf-turnstile-response\"]');"
                    "return el ? (el.value || '') : '';")
                if val and len(val) > 10:
                    solved = True
                    break
            except Exception:
                pass
            time.sleep(1)
        if solved:
            print("✅ Turnstile 验证通过 (token 已获取)")
        else:
            print("⚠️ Turnstile 未在 30s 内通过，仍尝试登录")
        time.sleep(3)
        sb.save_screenshot("turnstile_after.png")

    except Exception as e:
        print(f"⚠️ Turnstile 处理异常: {e}")

    print("🔑 点击登录按钮...")
    sb.uc_click('button:contains("Sign in")')

    for _ in range(30):
        cur = sb.get_current_url()
        title = sb.get_title() or ""
        print(f"📄 {cur} | {title}")
        if "login" not in cur and "client" in cur:
            print("✅ 登录成功")
            return True
        time.sleep(1)

    sb.save_screenshot("login_failed.png")
    print(f"❌ 登录失败: {sb.get_current_url()}")
    send_tg_photo(TG_BOT_TOKEN, TG_CHAT_ID, "login_failed.png", f"❌ 登录失败")
    # dump 页面可见文字（用 innerText 排除 script/style）
    try:
        body = sb.execute_script("return document.body.innerText || ''") or ""
        body = " ".join(body.split())
        print(f"📝 页面文字: {body[:600]}")
    except Exception as e:
        print(f"⚠️ 取页面文字失败: {e}")
    err = get_page_errors(sb)
    if err:
        print(f"⚠️ 报错: {err}")
    return False

def main():
    print("🚀 启动浏览器")

    sb_kwargs = {"uc": True, "headless": False}
    if PROXY_URL:
        print(f"🔗 代理: {PROXY_URL}")
        sb_kwargs["proxy"] = PROXY_URL

    with SB(**sb_kwargs) as sb:
        # IP 检测
        ip = ""
        try:
            sb.open("https://api.ipify.org?format=json")
            ip = sb.get_text('body').strip()[:50]
            print(f"📍 出口IP: {ip}")
        except:
            print("⚠️ 获取 IP 失败")

        if not login(sb):
            send_tg(TG_BOT_TOKEN, TG_CHAT_ID, f"❌ The Rose 登录失败\n🌐 IP: {ip}\n📦 {REPO_URL}")
            return

        print("📄 开始续期...")

        # 点 Extend
        try:
            btn = sb.find_element('button:contains("Extend"), span:contains("Extend")', timeout=5)
            print(f"✅ 找到 Extend 按钮")
            sb.uc_click('button:contains("Extend"), span:contains("Extend")')
            print("✅ 点击 Extend")
        except Exception as e:
            send_tg(TG_BOT_TOKEN, TG_CHAT_ID, f"❌ 未找到 Extend 按钮\n📦 {REPO_URL}")
            return

        time.sleep(2)

        # 点 Order now
        try:
            sb.find_element('button:contains("Order now")', timeout=5)
            sb.uc_click('button:contains("Order now")')
            print("✅ 点击 Order now")
        except Exception as e:
            send_tg(TG_BOT_TOKEN, TG_CHAT_ID, f"❌ 未找到 Order now 按钮\n📦 {REPO_URL}")
            return

        # 检查结果
        time.sleep(5)
        src = sb.get_page_source()
        if "successfully purchased" in src.lower():
            msg = f"✅ The Rose 续期成功！\n🌐 IP: {ip}\n📦 {REPO_URL}"
            sb.save_screenshot("success.png")
            print(msg)
            send_tg(TG_BOT_TOKEN, TG_CHAT_ID, msg)
        else:
            msg = f"❌ 续期可能失败\n🌐 IP: {ip}\n📦 {REPO_URL}"
            sb.save_screenshot("failed.png")
            print(msg)
            send_tg(TG_BOT_TOKEN, TG_CHAT_ID, msg)

    print("🏁 完毕")

if __name__ == "__main__":
    main()