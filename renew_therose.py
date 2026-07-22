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
        # 截图看点击后状态（本地留档；仅未通过时才发 TG，避免刷屏）
        sb.save_screenshot("turnstile_click.png")
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
            send_tg_photo(TG_BOT_TOKEN, TG_CHAT_ID, "turnstile_click.png", "🛡️ Turnstile 未通过（调试）")
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

    sb_kwargs: dict = {"uc": True, "headless": False}
    proxy_user = proxy_pass = None
    proxy_arg = PROXY_URL
    if PROXY_URL:
        # Chrome 不认 URL 内嵌的 SOCKS5 凭据 → 用 SeleniumBase 的 proxy_user/proxy_pass
        # （会生成代理认证扩展，正确处理 SOCKS5 auth）
        try:
            from urllib.parse import urlparse, unquote
            p = urlparse(PROXY_URL)
            if p.username or p.password:
                proxy_user = unquote(p.username or "")
                proxy_pass = unquote(p.password or "")
                scheme = "socks5" if p.scheme.startswith("socks") else p.scheme
                proxy_arg = f"{scheme}://{p.hostname}:{p.port}"
        except Exception:
            pass
        print(f"🔗 代理: {proxy_arg}")
        sb_kwargs["proxy"] = proxy_arg
        if proxy_user:
            sb_kwargs["proxy_user"] = proxy_user
            sb_kwargs["proxy_pass"] = proxy_pass

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

        # 读服务器到期时间，判断是否在「到期前 30 分钟」续期窗口内
        # 面板规则：Renewal is available only within 30 minutes before expiration
        def get_valid_until():
            try:
                sb.open("https://client.therose.cloud/panel?routeName=servers")
                time.sleep(3)
                txt = sb.execute_script("return (document.body.innerText||'').replace(/\\s+/g,' ').trim()")
                m = re.search(r"Valid until (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", txt)
                return (m.group(1) if m else None), txt
            except Exception as e:
                return None, ""

        valid_str, _ = get_valid_until()
        print("📅 当前 Valid until:", valid_str)
        if not valid_str:
            sb.save_screenshot("err_novalid.png")
            send_tg_photo(TG_BOT_TOKEN, TG_CHAT_ID, "err_novalid.png", f"❌ 读不到 Valid until（可能服务器已过期/消失）\n🌐 IP: {ip}\n📦 {REPO_URL}")
            return
        try:
            expiry = datetime.strptime(valid_str, "%Y-%m-%d %H:%M")
        except Exception:
            send_tg(TG_BOT_TOKEN, TG_CHAT_ID, f"❌ Valid until 解析失败: {valid_str}\n🌐 IP: {ip}\n📦 {REPO_URL}")
            return
        mins_left = (expiry - datetime.utcnow()).total_seconds() / 60.0
        print(f"⏳ 距到期约 {mins_left:.0f} 分钟")

        # 续期窗口：到期前 30 分钟内（且未过期）；否则静默跳过，不刷 TG
        if mins_left > 30 or mins_left <= 0:
            print("ℹ️ 不在续期窗口（需到期前 30 分钟内），本次跳过")
            return

        # ---- 进入续期流程（窗口内）----
        confirm_sel = ('button:contains("Order now"), button:contains("Confirm"), '
                       'button:contains("Pay"), button:contains("提交"), '
                       'button:contains("下单"), a:contains("Order now")')
        renewed = False
        for attempt in range(3):
            try:
                sb.open("https://client.therose.cloud/panel?routeName=servers")
                time.sleep(2)
                sb.uc_click('button:contains("Extend"), a:contains("Extend")', timeout=10)
                print(f"✅ 点击 Extend (尝试 {attempt+1})")
            except Exception as e:
                print(f"⚠️ 点击 Extend 失败: {e}")
                sb.save_screenshot("err_extend.png")
                send_tg_photo(TG_BOT_TOKEN, TG_CHAT_ID, "err_extend.png", f"❌ 未找到 Extend 按钮\n🌐 IP: {ip}\n📦 {REPO_URL}")
                return
            time.sleep(4)
            # 选时长（如有 select/radio，默认第一个）
            try:
                sb.execute_script(
                    "var s=document.querySelector('select');"
                    "if(s&&s.options.length){s.selectedIndex=0;s.dispatchEvent(new Event('change',{bubbles:true}));}"
                    "var r=document.querySelector('input[type=radio]');if(r)r.click();")
            except Exception:
                pass
            time.sleep(1)
            # 点 Order now（0 币免费，直接下单）
            try:
                sb.uc_click(confirm_sel, timeout=10)
                print("✅ 点击 Order now")
            except Exception as e:
                print(f"⚠️ 点击 Order now 失败: {e}")
                sb.save_screenshot("err_order.png")
                send_tg_photo(TG_BOT_TOKEN, TG_CHAT_ID, "err_order.png", f"❌ 未找到 Order now 按钮\n🌐 IP: {ip}\n📦 {REPO_URL}")
                return
            time.sleep(5)
            # 验证：回 servers 页看 Valid until 是否后推
            valid2, txt2 = get_valid_until()
            print(f"📅 续期后 Valid until: {valid2} (尝试 {attempt+1})")
            if valid2 and valid2 != valid_str:
                renewed = True
                msg = f"✅ The Rose 续期成功！新到期 {valid2}\n🌐 IP: {ip}\n📦 {REPO_URL}"
                print(msg)
                send_tg(TG_BOT_TOKEN, TG_CHAT_ID, msg)
                break
            else:
                print(f"⚠️ 第 {attempt+1} 次未生效，稍后重试")
                time.sleep(20)
        if not renewed:
            sb.save_screenshot("failed.png")
            send_tg_photo(TG_BOT_TOKEN, TG_CHAT_ID, "failed.png", f"❌ 续期未生效（窗口内多次失败）\n🌐 IP: {ip}\n📦 {REPO_URL}")
            print("❌ 续期未生效")

    print("🏁 完毕")

if __name__ == "__main__":
    main()