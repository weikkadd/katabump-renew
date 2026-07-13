#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import random
import subprocess
import requests
from seleniumbase import SB

# 从环境变量获取账号密码和 TG 配置
EMAIL        = os.environ.get("KATABUMP_EMAIL") or ""    # 登录邮箱
PASSWORD     = os.environ.get("KATABUMP_PASSWORD") or "" # 账号密码
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID") or ""        # tg通知 chat id(可选)
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""      # tg通知bot token(可选)

BASE_URL = "https://dashboard.katabump.com"  # 网站链接

#  Telegram 推送模块
def send_tg_message(status_icon, status_text, time_left="", server_url=None):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过 Telegram 推送。")
        return

    # 获取北京时间 (UTC+8)
    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    # 邮箱脱敏：保留用户名前2位和后2位，中间用****代替
    if '@' in EMAIL:
        name, domain = EMAIL.split('@', 1)
        if len(name) > 4:
            masked_email = f"{name[:2]}****{name[-2:]}@{domain}"
        else:
            masked_email = f"{name}@{domain}"
    else:
        masked_email = EMAIL[:2] + '****'

    # 优先用传入的 server_url (含服务器 ID 的完整链接)
    # 没有就用 BASE_URL (主域名)
    display_url = server_url if server_url else BASE_URL

    text = (
        f"🇫🇷 katabump 续期通知\n\n"
        f"{status_icon} {status_text}\n"
        f"👤 续期账户: {masked_email}\n"
        f"⏱️ 续期时间: {current_time_str}\n"
        f"🌐 {display_url}"
    )

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text
    }
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("📩 Telegram 通知发送成功！")
        else:
            print(f"⚠️ Telegram 通知发送失败: {r.text}")
    except Exception as e:
        print(f"⚠️ Telegram 通知发送异常: {e}")

#  页面注入脚本
_EXPAND_JS = """
(function() {
    var ts = document.querySelector('input[name="cf-turnstile-response"]');
    if (!ts) return 'no-turnstile';
    var el = ts;
    for (var i = 0; i < 20; i++) {
        el = el.parentElement;
        if (!el) break;
        var s = window.getComputedStyle(el);
        if (s.overflow === 'hidden' || s.overflowX === 'hidden' || s.overflowY === 'hidden')
            el.style.overflow = 'visible';
        el.style.minWidth = 'max-content';
    }
    document.querySelectorAll('iframe').forEach(function(f){
        if (f.src && f.src.includes('challenges.cloudflare.com')) {
            f.style.width = '300px'; f.style.height = '65px';
            f.style.minWidth = '300px';
            f.style.visibility = 'visible'; f.style.opacity = '1';
        }
    });
    return 'done';
})()
"""

_EXISTS_JS = """
(function(){
    return document.querySelector('input[name="cf-turnstile-response"]') !== null;
})()
"""

_SOLVED_JS = """
(function(){
    var i = document.querySelector('input[name="cf-turnstile-response"]');
    return !!(i && i.value && i.value.length > 20);
})()
"""

_WININFO_JS = """
(function(){
    return {
        sx: window.screenX || 0,
        sy: window.screenY || 0,
        oh: window.outerHeight,
        ih: window.innerHeight
    };
})()
"""

# ===== 自动续期相关 =====

# 在模态框内查找 iframe 并展开，返回点击坐标
_ALTCHA_EXPAND_JS = """
(function() {
    var modal = document.querySelector('div.modal.show') || document;
    var iframes = modal.querySelectorAll('iframe');
    for (var i = 0; i < iframes.length; i++) {
        var r = iframes[i].getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            iframes[i].style.width  = '300px';
            iframes[i].style.height = '150px';
            iframes[i].style.minWidth  = '300px';
            iframes[i].style.minHeight = '150px';
            iframes[i].style.visibility = 'visible';
            iframes[i].style.opacity = '1';
            var el = iframes[i];
            for (var j = 0; j < 10; j++) {
                el = el.parentElement;
                if (!el) break;
                el.style.overflow = 'visible';
            }
            var r2 = iframes[i].getBoundingClientRect();
            return { cx: Math.round(r2.x + 30), cy: Math.round(r2.y + r2.height / 2) };
        }
    }
    return null;
})()
"""

# 检测 ALTCHA 是否已验证通过
_ALTCHA_SOLVED_JS = """
(function(){
    var modal = document.querySelector('div.modal.show') || document;
    // hidden input 有值
    var inputs = modal.querySelectorAll('input[type="hidden"]');
    for (var i = 0; i < inputs.length; i++) {
        var n = (inputs[i].name || '').toLowerCase();
        if ((n.includes('altcha') || n.includes('captcha')) &&
            inputs[i].value && inputs[i].value.length > 20) return true;
    }
    // checkbox 变为 disabled
    var cbs = modal.querySelectorAll('input[type="checkbox"]');
    for (var j = 0; j < cbs.length; j++) {
        if (cbs[j].disabled) return true;
    }
    // widget data-state 属性
    var w = modal.querySelector('[data-state="verified"],.altcha--verified,.altcha-verified');
    if (w) return true;
    return false;
})()
"""

#  底层输入工具 (保留作为回退)
def js_fill_input(sb, selector: str, text: str):
    safe_text = text.replace('\\', '\\\\').replace('"', '\\"')
    sb.execute_script(f"""
    (function(){{
        var el = document.querySelector('{selector}');
        if (!el) return;
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        if (nativeInputValueSetter) {{
            nativeInputValueSetter.call(el, "{safe_text}");
        }} else {{
            el.value = "{safe_text}";
        }}
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }})()
    """)


#  人类化输入工具：逐字符输入，带随机延迟和鼠标移动
#  Cloudflare invisible Turnstile 会检测 keystroke 事件和输入节奏
#  瞬间填充 (js_fill_input) 会被识别为机器，必须模拟真实打字
def human_type(sb, selector: str, text: str):
    """模拟人类打字：点击输入框 → 逐字符输入 → 随机延迟"""
    try:
        # 1. 点击输入框获取焦点 (产生 click/focus 事件)
        el = sb.find_element(selector, timeout=5)
        el.click()
        time.sleep(0.3 + random.random() * 0.4)

        # 2. 清空输入框 (如果有内容)
        el.send_keys("\b" * 50)  # backspace 多次确保清空
        time.sleep(0.2)

        # 3. 逐字符输入，每个字符间隔 50-200ms (模拟人类打字节奏)
        for char in text:
            el.send_keys(char)
            time.sleep(0.05 + random.random() * 0.15)

        # 4. 输入完成后短暂停顿
        time.sleep(0.3 + random.random() * 0.5)

    except Exception as e:
        print(f"  ⚠️ human_type 失败，回退到 js_fill_input: {e}")
        js_fill_input(sb, selector, text)


#  人类化鼠标移动：在页面上随机移动鼠标，产生 mousemove 事件
#  Cloudflare 会检测鼠标移动轨迹，纯键盘操作会被识别为机器
def human_mouse_move(sb, steps: int = 5):
    """在页面上随机移动鼠标，模拟人类浏览行为"""
    try:
        for _ in range(steps):
            # 随机坐标 (屏幕范围内)
            x = random.randint(200, 1500)
            y = random.randint(200, 800)
            sb.execute_script(f"""
                (function() {{
                    var evt = new MouseEvent('mousemove', {{
                        bubbles: true,
                        cancelable: true,
                        clientX: {x},
                        clientY: {y}
                    }});
                    document.dispatchEvent(evt);
                }})()
            """)
            time.sleep(0.2 + random.random() * 0.5)
    except Exception:
        pass


#  人类化页面滚动：随机滚动页面
def human_scroll(sb):
    """随机滚动页面，模拟人类浏览"""
    try:
        for _ in range(2):
            scroll_y = random.randint(100, 500)
            sb.execute_script(f"window.scrollBy(0, {scroll_y});")
            time.sleep(0.5 + random.random() * 1.0)
        # 滚回顶部
        sb.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
    except Exception:
        pass

def _activate_window():
    for cls in ["chrome", "chromium", "Chromium", "Chrome", "google-chrome"]:
        try:
            r = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], capture_output=True, text=True, timeout=3)
            wids = [w for w in r.stdout.strip().split("\n") if w.strip()]
            if wids:
                subprocess.run(["xdotool", "windowactivate", "--sync", wids[0]], timeout=3, stderr=subprocess.DEVNULL)
                time.sleep(0.2)
                return
        except Exception:
            pass
    try:
        subprocess.run(["xdotool", "getactivewindow", "windowactivate"], timeout=3, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def _xdotool_click(x: int, y: int):
    _activate_window()
    try:
        subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y)], timeout=3, stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        subprocess.run(["xdotool", "click", "1"], timeout=2, stderr=subprocess.DEVNULL)
    except Exception:
        os.system(f"xdotool mousemove {x} {y} click 1 2>/dev/null")

#  获取 Turnstile iframe 精确坐标的 JS (考虑窗口偏移)
#  放宽匹配条件：除了 challenges.cloudflare.com，还匹配其他 Turnstile 特征
_TURNSTILE_COORDS_JS = """
(function(){
    var iframes = document.querySelectorAll('iframe');
    var iframe = null;
    // 1. 优先匹配 challenges.cloudflare.com
    for (var i = 0; i < iframes.length; i++) {
        if (iframes[i].src && iframes[i].src.indexOf('challenges.cloudflare.com') !== -1) {
            iframe = iframes[i];
            break;
        }
    }
    // 2. 回退：匹配任何 cloudflare 相关的 iframe
    if (!iframe) {
        for (var i = 0; i < iframes.length; i++) {
            if (iframes[i].src && (iframes[i].src.indexOf('cloudflare') !== -1 || iframes[i].src.indexOf('turnstile') !== -1)) {
                iframe = iframes[i];
                break;
            }
        }
    }
    // 3. 回退：匹配带 data-sitekey 的容器内的 iframe
    if (!iframe) {
        var ts = document.querySelector('[data-sitekey]') || document.querySelector('.cf-turnstile');
        if (ts) {
            var innerIframe = ts.querySelector('iframe');
            if (innerIframe) iframe = innerIframe;
        }
    }
    // 4. 回退：找任何尺寸接近 Turnstile widget (300x65) 的可见 iframe
    if (!iframe) {
        for (var i = 0; i < iframes.length; i++) {
            var r = iframes[i].getBoundingClientRect();
            if (r.width > 200 && r.width < 400 && r.height > 40 && r.height < 100) {
                iframe = iframes[i];
                break;
            }
        }
    }
    if (!iframe) return null;
    var r = iframe.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return null;
    return {
        x: Math.round(r.x + 30),  // checkbox 在 iframe 左侧约 30px
        y: Math.round(r.y + r.height / 2),
        width: Math.round(r.width),
        height: Math.round(r.height),
        screenX: window.screenX || 0,
        screenY: window.screenY || 0,
        outerHeight: window.outerHeight || 0,
        innerHeight: window.innerHeight || 0,
        src: iframe.src ? iframe.src.substring(0, 80) : ''
    };
})()
"""

#  诊断脚本：列出页面上所有 iframe 的信息 (调试用)
_DIAG_IFRAMES_JS = """
(function(){
    var iframes = document.querySelectorAll('iframe');
    var result = [];
    for (var i = 0; i < iframes.length; i++) {
        var r = iframes[i].getBoundingClientRect();
        result.push({
            idx: i,
            src: iframes[i].src ? iframes[i].src.substring(0, 100) : '(empty)',
            x: Math.round(r.x),
            y: Math.round(r.y),
            w: Math.round(r.width),
            h: Math.round(r.height),
            visible: r.width > 0 && r.height > 0
        });
    }
    // 也检查 input[name=cf-turnstile-response] 是否存在
    var ts = document.querySelector('input[name="cf-turnstile-response"]');
    return {
        iframeCount: iframes.length,
        iframes: result,
        hasTurnstileInput: !!ts,
        turnstileValue: ts ? ts.value.substring(0, 30) : ''
    };
})()
"""

def _xdotool_click_turnstile(sb) -> bool:
    """用 xdotool 手动点击 Turnstile checkbox (uc_gui_click_captcha 失败时的备选方案)"""
    try:
        coords = sb.execute_script(_TURNSTILE_COORDS_JS)
    except Exception:
        coords = None

    if not coords:
        print("  ⚠️ 无法获取 Turnstile iframe 坐标")
        # 诊断：打印页面上所有 iframe 信息
        try:
            diag = sb.execute_script(_DIAG_IFRAMES_JS)
            print(f"  📊 诊断: iframe 总数={diag['iframeCount']}, hasTurnstileInput={diag['hasTurnstileInput']}, turnstileValue='{diag.get('turnstileValue','')}'")
            for f in diag.get('iframes', [])[:5]:
                print(f"     [{f['idx']}] src={f['src']} pos=({f['x']},{f['y']}) size={f['w']}x{f['h']} visible={f['visible']}")
        except Exception as e:
            print(f"  ⚠️ 诊断脚本也失败: {e}")
        return False

    # 计算屏幕绝对坐标 (考虑浏览器窗口偏移和标题栏)
    bar = coords.get("outerHeight", 0) - coords.get("innerHeight", 0)
    if bar < 0: bar = 0
    abs_x = coords["x"] + coords.get("screenX", 0)
    abs_y = coords["y"] + coords.get("screenY", 0) + bar

    print(f"  📍 Turnstile iframe 坐标: 页面({coords['x']},{coords['y']}) → 屏幕({abs_x},{abs_y}) [bar={bar}] src={coords.get('src','')[:50]}")

    # 激活窗口
    _activate_window()
    time.sleep(0.3)

    try:
        # 移动 + 点击 (不用 --sync 避免挂起)
        subprocess.run(["xdotool", "mousemove", str(abs_x), str(abs_y)], timeout=3, stderr=subprocess.DEVNULL)
        time.sleep(0.2 + random.random() * 0.3)
        subprocess.run(["xdotool", "click", "1"], timeout=3, stderr=subprocess.DEVNULL)
        print(f"  🖱️ xdotool 已点击 ({abs_x}, {abs_y})")
        return True
    except Exception as e:
        print(f"  ⚠️ xdotool 点击失败: {e}")
        # 最后尝试 os.system
        try:
            os.system(f"xdotool mousemove {abs_x} {abs_y} click 1 2>/dev/null")
            return True
        except Exception:
            return False


#  人机验证处理（针对 invisible/managed Turnstile 优化）
def handle_turnstile(sb) -> bool:
    print("🔍 处理 Cloudflare Turnstile 验证...")
    time.sleep(2)

    # 检查是否已静默通过
    if sb.execute_script(_SOLVED_JS):
        print("✅ 已静默通过")
        return True

    # 尝试展开 Turnstile（防止被父容器 overflow:hidden 裁剪）
    for _ in range(3):
        try: sb.execute_script(_EXPAND_JS)
        except Exception: pass
        time.sleep(0.5)

    # === 检测 Turnstile 模式 ===
    # invisible/managed 模式: iframe 是 1x1 像素，src 为空，没有 checkbox
    # 交互式模式: iframe 是 300x65，有 checkbox 可点击
    is_invisible = False
    try:
        diag = sb.execute_script(_DIAG_IFRAMES_JS)
        if diag and diag.get('iframeCount', 0) > 0:
            f = diag['iframes'][0]
            if f['w'] <= 5 and f['h'] <= 5:
                is_invisible = True
                print(f"  📊 检测到 invisible/managed Turnstile (iframe {f['w']}x{f['h']})")
                print("  ⏳ invisible 模式：等待 Cloudflare 自动验证，不主动点击...")
    except Exception:
        pass

    # === 阶段 1: 等待自动验证 (最多 20 秒) ===
    # invisible Turnstile 通常会自动完成，不需要点击
    # 主动点击反而会触发反自动化检测
    if is_invisible:
        for wait_sec in range(20):
            if sb.execute_script(_SOLVED_JS):
                print(f"✅ Turnstile 自动通过（等待 {wait_sec + 1}s）")
                return True
            time.sleep(1)
        print(f"⚠️ 等待 20s 未自动通过")

    # === 阶段 2: uc_gui_click_captcha (3 次) ===
    # 如果是交互式 Turnstile 或 invisible 等待失败，尝试点击
    print(f"\n🖱️ 尝试 uc_gui_click_captcha (3 次)...")
    for attempt in range(3):
        if sb.execute_script(_SOLVED_JS):
            print(f"✅ Turnstile 通过（uc_gui 第 {attempt} 次尝试）")
            return True

        print(f"🖱️ 第 {attempt + 1} 次调用 uc_gui_click_captcha...")
        try:
            sb.uc_gui_click_captcha()
        except Exception as e:
            print(f"⚠️ uc_gui_click_captcha 调用异常: {e}")

        # 等待验证结果（最多 8 秒）
        for _ in range(16):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                print(f"✅ Turnstile 通过（uc_gui 第 {attempt + 1} 次尝试）")
                return True

        print(f"⚠️ uc_gui 第 {attempt + 1} 次未通过，重试...")

    # === 阶段 3: xdotool 手动点击 (仅对交互式 Turnstile 有效) ===
    # 检查是否是交互式 Turnstile (有可见 iframe)
    is_interactive = False
    try:
        diag = sb.execute_script(_DIAG_IFRAMES_JS)
        if diag and diag.get('iframeCount', 0) > 0:
            f = diag['iframes'][0]
            if f['w'] > 100 and f['h'] > 30:
                is_interactive = True
    except Exception:
        pass

    if is_interactive:
        print(f"\n🖱️ uc_gui_click_captcha 3 次失败，切换到 xdotool 手动点击...")
        for attempt in range(3):
            if sb.execute_script(_SOLVED_JS):
                print(f"✅ Turnstile 通过（xdotool 第 {attempt} 次尝试）")
                return True

            try: sb.execute_script(_EXPAND_JS)
            except Exception: pass
            time.sleep(0.5)

            print(f"🖱️ 第 {attempt + 1} 次 xdotool 点击...")
            clicked = _xdotool_click_turnstile(sb)
            if not clicked:
                print(f"⚠️ xdotool 点击失败，重试...")

            for _ in range(16):
                time.sleep(0.5)
                if sb.execute_script(_SOLVED_JS):
                    print(f"✅ Turnstile 通过（xdotool 第 {attempt + 1} 次尝试）")
                    return True

            print(f"⚠️ xdotool 第 {attempt + 1} 次未通过，重试...")
    else:
        print("\n⚠️ invisible Turnstile，无 checkbox 可点击，已尝试等待 + uc_gui_click_captcha")

    # === 阶段 4: 最后再等待 10 秒 (有时验证会延迟完成) ===
    print("\n⏳ 最后等待 10 秒看是否延迟通过...")
    for wait_sec in range(10):
        if sb.execute_script(_SOLVED_JS):
            print(f"✅ Turnstile 延迟通过（{wait_sec + 1}s）")
            return True
        time.sleep(1)

    print("  ❌ Turnstile 所有尝试均失败")
    return False

#  账户登录
def login(sb) -> bool:
    print(f"🌐 打开登录页面: {BASE_URL}/auth/login")
    sb.uc_open_with_reconnect(BASE_URL + "/auth/login", reconnect_time=8)
    time.sleep(6)

    # 先等待 Cloudflare 验证通过（最多等 30 秒）
    print("⏳ 等待 Cloudflare 验证通过...")
    cf_passed = False
    for i in range(30):
        page_src = sb.get_page_source() or ""
        if 'input[name="email"]' in page_src.lower() or 'name="email"' in page_src.lower():
            cf_passed = True
            print(f"✅ Cloudflare 验证已通过（{i+1}s）")
            break
        time.sleep(1)
    if not cf_passed:
        print("⚠️ Cloudflare 验证可能未通过，继续尝试...")

    try:
        sb.wait_for_element('input[name="email"]', timeout=15)
    except Exception:
        # 尝试大写选择器作为后备
        try:
            sb.wait_for_element('input[name="Email"]', timeout=5)
        except Exception:
            print("❌ 页面未加载出登录表单")
            cur_url = sb.get_current_url()
            page_title = sb.get_title() or ""
            print(f"  当前 URL: {cur_url}")
            print(f"  当前标题: {page_title}")
            sb.save_screenshot("login_load_fail.png")
            return False

    print("🍪 关闭可能的 Cookie 弹窗...")
    try:
        for btn in sb.find_elements("button"):
            if "Accept" in (btn.text or ""):
                btn.click()
                time.sleep(0.5)
                break
    except Exception:
        pass

    # === 关键：模拟人类行为，让 Cloudflare invisible Turnstile 采集到真实指纹 ===
    # Cloudflare 会检测：鼠标移动、滚动、点击、打字节奏等
    # 如果只是瞬间填充表单，会被判定为机器，Turnstile 拒绝发 token
    print("🖱️ 模拟人类浏览行为 (鼠标移动 + 滚动)...")
    human_mouse_move(sb, steps=4)
    human_scroll(sb)
    human_mouse_move(sb, steps=3)
    time.sleep(1 + random.random() * 2)

    print(f"📧 填写邮箱 (逐字符输入)...")
    human_type(sb, 'input[name="email"]', EMAIL)
    time.sleep(0.5 + random.random() * 1.0)
    
    print("🔑 填写密码 (逐字符输入)...")
    human_type(sb, 'input[name="password"]', PASSWORD)
    time.sleep(1 + random.random() * 1.5)

    # 再移动一下鼠标，模拟填完表单后的犹豫
    human_mouse_move(sb, steps=2)
    time.sleep(0.5 + random.random() * 1.0)

    # 等待 Turnstile 验证框出现（最多 10 秒）
    print("⏳ 等待 Turnstile 验证框出现...")
    ts_found = False
    for i in range(10):
        if sb.execute_script(_EXISTS_JS):
            ts_found = True
            print(f"✅ 检测到 Turnstile（{i+1}s）")
            break
        time.sleep(1)

    if ts_found:
        if not handle_turnstile(sb):
            print("❌ 登录界面的 Turnstile 验证失败")
            sb.save_screenshot("login_turnstile_fail.png")
            return False
    else:
        print("ℹ️ 未检测到 Turnstile")

    print("🖱️ 敲击回车提交表单...")
    sb.press_keys('input[name="password"]', '\n')

    print("⏳ 等待登录跳转...")
    # 登录成功后可能跳转到:
    # 1. /dashboard (首页)
    # 2. /servers/edit?id=xxx (服务器详情页)
    # 3. /servers (服务器列表)
    # 只要离开 /auth/login 且在 dashboard.katabump.com 域名内，就算成功
    for _ in range(12):
        time.sleep(1)
        cur_url = sb.get_current_url().lower()
        page_title = sb.get_title() or ""
        # 不在登录页 + 在 katabump 域名内 = 登录成功
        if "/auth/login" not in cur_url and "katabump.com" in cur_url:
            # 排除登录失败重定向 (带 error 参数)
            if "error=" not in cur_url:
                break

    cur_url = sb.get_current_url()
    cur_url_lower = cur_url.lower()
    page_title = sb.get_title() or ""
    if "/auth/login" not in cur_url_lower and "katabump.com" in cur_url_lower and "error=" not in cur_url_lower:
        print(f"✅ 登录成功！(URL: {cur_url}, Title: {page_title})")
        return True
        
    print(f"❌ 登录失败，页面未跳转到账户页。(URL: {cur_url}, Title: {page_title})")
    sb.save_screenshot("login_failed.png")
    return False

# ===== 自动续期流程 =====

def _read_alert(sb):
    """读取页面第一个 Bootstrap alert 的文本，找不到返回空串"""
    try:
        el = sb.find_element("div.alert", timeout=4)
        return (el.text or "").strip()
    except Exception:
        return ""


def _goto_server_detail(sb) -> bool:
    """在 Dashboard 首页查找并点击 See 进入服务器详情页
    如果登录后已在 /servers/edit?id=xxx，直接返回 True"""
    print("\n🖥️  正在进入服务器续期页...")
    time.sleep(3)

    # 检查是否已直接在服务器详情页 (登录后可能直接跳转)
    cur_url = sb.get_current_url()
    if "/servers/edit" in cur_url or "/servers/" in cur_url:
        print(f"✅ 已在服务器详情页: {cur_url}")
        return True

    time.sleep(2)

    # 检查页面顶部是否已有"还无法续期"全局提示
    alert_text = _read_alert(sb)
    if alert_text and "can't renew" in alert_text.lower():
        print(f"ℹ️  页面顶部提示: {alert_text}")
        send_tg_message("ℹ️", "⚠️ 未到续期时间", alert_text)
        return False

    # 多种选择器尝试查找 See 链接
    selectors = [
        'a[href*="/servers/edit?id="]',
        'td a[href*="/servers/edit"]',
        'table a[href*="/servers/edit"]',
        'table td a',
    ]

    see_link = None
    for sel in selectors:
        try:
            see_link = sb.find_element(sel, timeout=8)
            print(f"✅ 通过选择器找到链接: {sel}")
            break
        except Exception:
            continue

    # 选择器全部失败，尝试通过文本内容查找
    if see_link is None:
        print("⚠️ 选择器未命中，尝试文本匹配...")
        try:
            for a in sb.find_elements("a"):
                if (a.text or "").strip().lower() == "see":
                    see_link = a
                    print("✅ 通过文本 'See' 找到链接")
                    break
        except Exception:
            pass

    if see_link is None:
        # 打印调试信息帮助排查
        cur_url = sb.get_current_url()
        title = sb.get_title() or ""
        print(f"❌ 未找到 'See' 链接")
        print(f"当前 URL: {cur_url}")
        print(f"页面标题: {title}")
        try:
            links = sb.find_elements("a")
            print(f"     页面共 {len(links)} 个链接:")
            for a in links[:20]:
                href = a.get_attribute("href") or ""
                txt  = (a.text or "").strip()[:30]
                if href:
                    print(f"       - [{txt}] -> {href}")
        except Exception:
            pass
        sb.save_screenshot("servers_page_fail.png")
        return False

    print("🖱️  点击 'See' 进入服务器详情页...")
    see_link.click()
    time.sleep(5)
    print(f"📄 当前页面: {sb.get_current_url()}")
    return True


def _open_renew_modal(sb) -> bool:
    """滚动到 Renew 按钮并点击，打开模态框"""
    print("\n🔄 查找 Renew 按钮...")
    try:
        renew_btn = sb.find_element('button[data-bs-target="#renew-modal"]', timeout=10)
    except Exception:
        try:
            renew_btn = sb.find_element('button.btn.btn-outline-primary', timeout=5)
        except Exception:
            print("  ❌ 未找到 Renew 按钮")
            return False

    sb.execute_script("""
        (function(){
            var btn = document.querySelector('button[data-bs-target="#renew-modal"]')
                     || document.querySelector('button.btn.btn-outline-primary');
            if (btn) btn.scrollIntoView({behavior:'smooth',block:'center'});
        })()
    """)
    time.sleep(0.8)
    renew_btn.click()
    print("🖱️ 已点击 Renew 按钮，等待 ALTCHA 验证框...")
    time.sleep(3)

    try:
        sb.find_element('div.modal.show', timeout=5)
        print("✅ Renew 模态框已弹出")
        return True
    except Exception:
        print("⚠️ 模态框未弹出")
        return False


def _solve_altcha(sb) -> bool:
    """处理 ALTCHA 人机验证"""
    print("\n🔐 处理 ALTCHA 人机验证...")
    time.sleep(2)

    # 先检查是否已自动通过
    if sb.execute_script(_ALTCHA_SOLVED_JS):
        print("✅ ALTCHA 已自动通过")
        return True

    # 展开模态框内 iframe 并获取坐标
    coords = None
    try:
        coords = sb.execute_script(_ALTCHA_EXPAND_JS)
    except Exception:
        pass

    if coords:
        print(f"  📍 找到模态框内 iframe 坐标: ({coords['cx']}, {coords['cy']})")

    # 最多尝试 3 轮
    for attempt in range(3):
        if sb.execute_script(_ALTCHA_SOLVED_JS):
            print(f"✅ ALTCHA 验证通过（第 {attempt + 1} 轮）")
            return True

        # 策略 1: xdotool 物理点击 iframe 坐标
        if coords:
            try:
                wi = sb.execute_script(_WININFO_JS)
            except Exception:
                wi = {"sx": 0, "sy": 0, "oh": 800, "ih": 768}
            bar = wi["oh"] - wi["ih"]
            ax  = coords["cx"] + wi["sx"]
            ay  = coords["cy"] + wi["sy"] + bar
            print(f"🖱️  ALTCHA点击复选框  ({ax}, {ay})")
            _xdotool_click(ax, ay)

        # 策略 2: SeleniumBase 原生点击模态框内 iframe 元素
        try:
            iframes = sb.find_elements('div.modal.show iframe')
            for iframe in iframes:
                try:
                    iframe.click()
                    print("🖱️  SeleniumBase 点击模态框 iframe")
                except Exception:
                    pass
        except Exception:
            pass

        # 策略 3: JS 遍历模态框内所有可点击元素
        sb.execute_script("""
            (function(){
                var modal = document.querySelector('div.modal.show');
                if (!modal) return;
                // 点击 iframe
                var iframes = modal.querySelectorAll('iframe');
                for (var i = 0; i < iframes.length; i++) {
                    iframes[i].click();
                    iframes[i].dispatchEvent(new MouseEvent('click', {bubbles:true}));
                }
                // 点击含 checkbox 的 label
                var labels = modal.querySelectorAll('label');
                for (var j = 0; j < labels.length; j++) {
                    var txt = (labels[j].textContent || '').toLowerCase();
                    if (txt.includes('robot') || txt.includes('captcha') || txt.includes('verify'))
                        labels[j].click();
                }
                // 点击 checkbox
                var cbs = modal.querySelectorAll('input[type="checkbox"]');
                for (var k = 0; k < cbs.length; k++) {
                    if (!cbs[k].disabled) {
                        cbs[k].click();
                        cbs[k].dispatchEvent(new MouseEvent('click', {bubbles:true}));
                    }
                }
            })()
        """)

        # 等待验证结果
        for _ in range(6):
            time.sleep(1)
            if sb.execute_script(_ALTCHA_SOLVED_JS):
                print(f"✅ ALTCHA 验证通过（第 {attempt + 1} 轮）")
                return True

        print(f"  ⚠️ 第 {attempt + 1} 轮未通过，重试...")
        # 重新获取坐标（iframe 可能已重新渲染）
        try:
            new_coords = sb.execute_script(_ALTCHA_EXPAND_JS)
            if new_coords:
                coords = new_coords
        except Exception:
            pass

    print("  ❌ ALTCHA 3 轮均失败")
    return False


def _submit_renew(sb):
    """点击模态框内的 Renew 提交按钮"""
    print("🖱️  点击模态框中的 Renew 按钮...")
    try:
        submit = sb.find_element('div.modal.show button.btn-primary', timeout=5)
        submit.click()
    except Exception:
        sb.execute_script("""
            (function(){
                var m = document.querySelector('div.modal.show');
                if (!m) return;
                var bs = m.querySelectorAll('button');
                for (var i = 0; i < bs.length; i++)
                    if (/renew/i.test(bs[i].textContent)) bs[i].click();
            })()
        """)
    time.sleep(3)


def _check_renew_result(sb):
    """读取页面 alert 提示，判断续期结果并推送 TG 通知"""
    print("\n📋 检查续期结果...")
    alert_text = _read_alert(sb)
    if not alert_text:
        time.sleep(3)
        alert_text = _read_alert(sb)

    if alert_text:
        print(f"📩 页面提示: {alert_text}")
        low = alert_text.lower()
        # 获取当前服务器详情页 URL (含 ?id=xxx) 用于 TG 通知
        try:
            cur_url = sb.get_current_url()
        except Exception:
            cur_url = None
        if "can't renew" in low or "unable" in low:
            send_tg_message("⏳", "未到续期时间", alert_text, server_url=cur_url)
        elif any(kw in low for kw in ( "renewed", "success", "extended")):
            send_tg_message("✅", "续期成功", alert_text, server_url=cur_url)
        else:
            send_tg_message("ℹ️", "续期操作已执行", alert_text, server_url=cur_url)
    else:
        print("ℹ️ 未检测到明确的提示框，可能续期操作未生效")
        try:
            cur_url = sb.get_current_url()
        except Exception:
            cur_url = None
        send_tg_message("ℹ️", "续期操作已执行", "未检测到明确提示", server_url=cur_url)


def renew_server(sb):
    """登录成功后调用：自动进入详情页 -> Renew -> ALTCHA -> 提交"""
    print("\n" + "#" * 25)
    print("  开始自动续期流程")
    print("#" * 25)

    if not _goto_server_detail(sb):
        return

    if not _open_renew_modal(sb):
        return

    altcha_ok = _solve_altcha(sb)
    if not altcha_ok:
        print("⚠️ ALTCHA 验证未通过，仍尝试提交 Renew...")

    _submit_renew(sb)
    _check_renew_result(sb)


#  脚本执行入口 (可选代理)
def process_account(email, password, sb_kwargs):
    """处理单个账号的续期流程"""
    global EMAIL, PASSWORD
    EMAIL = email
    PASSWORD = password

    # 邮箱脱敏日志
    if '@' in email:
        name, domain = email.split('@', 1)
        masked = f"{name[:2]}****{name[-2:]}@{domain}" if len(name) > 4 else f"{name}@{domain}"
    else:
        masked = email[:2] + '****'
    print(f"\n{'=' * 25}")
    print(f"  处理账号: {masked}")
    print(f"{'=' * 25}")

    print("🚀 启动浏览器...")
    with SB(**sb_kwargs) as sb:
        try:
            sb.open("https://api.ip.sb/ip")
            print(f"📍  当前出口IP: {sb.get_text('body')}")
        except Exception:
            pass

        if login(sb):
            renew_server(sb)   # 登录成功后自动续期
        else:
            print("\n❌ 登录失败，终止后续续期操作。")
            send_tg_message("❌", "登录失败", f"账号: {masked}")


def get_accounts():
    """从环境变量读取账号列表，兼容两种格式:
    1. USERS_JSON: [{"username":"...", "password":"..."}, ...]  (weikkadd 格式)
    2. KATABUMP_EMAIL + KATABUMP_PASSWORD: 单账号 (eooce 格式)
    """
    accounts = []

    # 优先尝试 USERS_JSON (多账号)
    users_json = os.environ.get("USERS_JSON", "").strip()
    if users_json:
        try:
            data = __import__("json").loads(users_json)
            if isinstance(data, list):
                for u in data:
                    email = u.get("username") or u.get("email") or ""
                    pwd = u.get("password") or ""
                    if email and pwd:
                        accounts.append((email, pwd))
            elif isinstance(data, dict) and "users" in data:
                for u in data["users"]:
                    email = u.get("username") or u.get("email") or ""
                    pwd = u.get("password") or ""
                    if email and pwd:
                        accounts.append((email, pwd))
        except Exception as e:
            print(f"⚠️ 解析 USERS_JSON 失败: {e}")

    # 回退到单账号环境变量
    if not accounts:
        email = os.environ.get("KATABUMP_EMAIL", "").strip()
        pwd = os.environ.get("KATABUMP_PASSWORD", "").strip()
        if email and pwd:
            accounts.append((email, pwd))

    return accounts


def main():
    print("#" * 25)
    print("   katabump 自动登录续期")
    print("#" * 25)

    accounts = get_accounts()
    if not accounts:
        print("❌ 未找到任何账号配置 (USERS_JSON 或 KATABUMP_EMAIL/PASSWORD)")
        return

    print(f"📋 共 {len(accounts)} 个账号待处理")

    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    sb_kwargs = {"uc": True, "headless": False}

    if IS_PROXY:
        print(f"🔗 挂载代理: {proxy_str}")
        sb_kwargs["proxy"] = proxy_str
    else:
        print("🌐 未使用代理，直连访问")

    for idx, (email, pwd) in enumerate(accounts, 1):
        print(f"\n\n>>> 账号 {idx}/{len(accounts)} <<<")
        try:
            process_account(email, pwd, sb_kwargs)
        except Exception as e:
            print(f"❌ 账号处理异常: {e}")
            # 截图辅助诊断
            try:
                import traceback
                traceback.print_exc()
            except Exception:
                pass

    print(f"\n{'#' * 25}")
    print(f"  全部账号处理完成")
    print(f"{'#' * 25}")


if __name__ == "__main__":
    main()
