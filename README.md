# Katabump 自动续期工具

基于 **SeleniumBase UC 模式** 绕过 Cloudflare Turnstile 验证码，支持 sing-box 全协议代理、多账号、Telegram 通知、人类行为模拟。

## ✨ 特性

- 🤖 **SeleniumBase UC 模式** — 修补 Chrome 二进制，深度反检测，绕过 Cloudflare
- 🖱️ **`uc_gui_click_captcha()`** — SeleniumBase 内置方法，通过 PyAutoGUI 发送真实 X11 鼠标事件（`isTrusted=true`）
- 👤 **人类行为模拟** — 逐字符输入、鼠标移动、页面滚动，让 invisible Turnstile 采集真实指纹
- 🌐 **全协议代理** — sing-box 支持 vless/vmess/trojan/tuic/anytls/hysteria2/socks5
- 👥 **多账号支持** — 一个 `USERS_JSON` 配置多个账号，批量续期
- 📲 **Telegram 通知** — 续期成功/失败/跳过时推送截图
- ⏰ **定时任务** — GitHub Actions 每天 UTC 0:00 自动运行

## 🚀 GitHub Actions 云端运行 (推荐)

### 1. Fork 本仓库

### 2. 配置 Secrets

进入 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 名称 | 是否必填 | 说明 |
|-------------|----------|------|
| `USERS_JSON` | ✅ 必填 | JSON 数组：`[{"username":"email@example.com","password":"pwd"}]`（支持多账号） |
| `PROXY_URL` | ❌ 可选 | 代理链接（vless/vmess/trojan/tuic/anytls/hysteria2/socks5） |
| `TG_BOT_TOKEN` | ❌ 可选 | Telegram Bot Token |
| `TG_CHAT_ID` | ❌ 可选 | Telegram Chat ID |

**`USERS_JSON` 格式示例**（单账号）：
```json
[{"username":"your_email@gmail.com","password":"your_password"}]
```

**多账号示例**：
```json
[{"username":"email1@gmail.com","password":"pwd1"},{"username":"email2@gmail.com","password":"pwd2"}]
```

### 3. 运行

- **定时运行**：每天 UTC 0:00（北京时间 8:00）自动触发
- **手动运行**：进入 **Actions** → 选 `Katabump 自动续期` → **Run workflow**

### 4. 截图留存

每次运行（无论成功与否）通过 `Upload Screenshots` 步骤自动上传截图到 Artifacts。

## 🔧 代理说明

⚠️ Cloudflare Turnstile 对 IP 信誉有要求，**机房 IP（AWS/GCP/Azure）可能过不了**，建议用住宅代理。

推荐的住宅代理：[B2proxy](https://www.b2proxy.com/signup?code=0F5133)

支持的协议（与 v2rayN 兼容的节点链接）：
- `vless://uuid@server:port?security=reality&sni=...&type=ws&...`
- `vmess://base64encoded...`
- `trojan://password@server:port?sni=...&type=ws&...`
- `tuic://uuid:password@server:port...`
- `anytls://uuid@server:port...`
- `hysteria2://base64@server:port...`
- `socks5://user:pass@server:port` 或 `socks://user:pass@server:port`

## 🛠️ 项目结构

| 文件 | 说明 |
|------|------|
| `app.py` | 主程序（Python + SeleniumBase） |
| `.github/workflows/renew.yml` | GitHub Actions 工作流配置 |

## 💻 本地运行 (可选)

```bash
# 安装依赖
sudo apt-get install -y xvfb x11-utils xdotool scrot fonts-noto-cjk
pip install seleniumbase requests
seleniumbase install chromedriver

# 设置环境变量
export USERS_JSON='[{"username":"your@email.com","password":"pwd"}]'

# 可选: 配置代理
# export NODE_LINK='vless://...'
# bash <(wget -qO- https://main.ssss.nyc.mn/setup_proxy.sh)

# 运行
xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python3 app.py
```

## 🔧 工作原理

1. **启动浏览器** — SeleniumBase UC 模式，修补 Chrome 自动化指纹
2. **打开登录页** — `uc_open_with_reconnect` 等待 Cloudflare 验证
3. **模拟人类行为** — 鼠标移动 + 页面滚动，采集真实行为指纹
4. **逐字符输入** — 邮箱/密码逐字符输入，带随机延迟（50-200ms）
5. **Turnstile 验证** — 检测 invisible/managed 模式，优先等待自动验证，失败后用 `uc_gui_click_captcha()` 点击
6. **登录提交** — 在密码框按回车提交（避开按钮点击检测）
7. **进入详情页** — 点击 "See" 链接（如已在详情页则跳过）
8. **ALTCHA 验证** — Renew 模态框的 ALTCHA 人机验证
9. **提交续期** — 点击 Renew 按钮，读取结果并推送 Telegram 通知

## 📋 续期结果说明

脚本会识别以下情况并推送不同的 Telegram 通知：

- ✅ **续期成功** — `renewed` / `success` / `extended`
- ⏳ **未到续期时间** — `You can't renew your server yet. You will be able to as of ...`
- ❌ **登录失败** — 密码错误 / Turnstile 未通过 / 网络问题

## 📝 致谢

- [eooce/katabump-renew](https://github.com/eooce/katabump-renew) — 原始 SeleniumBase 方案参考
- [XCQ0607/katabump](https://github.com/XCQ0607/katabump) — 早期 Playwright 方案
