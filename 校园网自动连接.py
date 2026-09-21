# -*- coding: utf-8 -*-
"""
校园网自动连接工具 v1.0
功能：
  1. 自动连接指定校园 WiFi（可跳过，有线网不需要）
  2. 定时检测是否断网（外网探测）
  3. 断网时自动完成校园网网页认证登录（自动识别 / Dr.COM / 锐捷 / 浏览器手动）
  4. 掉线后自动重连，窗口保持运行即持续监控

配置文件：config.json（与脚本同目录，首次运行自动生成）
运行日志：运行日志.log（与脚本同目录）
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
import webbrowser
import urllib.parse
import urllib.request

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOG_PATH = os.path.join(APP_DIR, "运行日志.log")

DEFAULTS = {
    "wifi_ssid": "",          # 校园网 WiFi 名称，如不填则跳过连接 WiFi
    "username": "",           # 校园网账号
    "password": "",           # 校园网密码（明文保存在本地，请勿外传）
    "login_method": "panabit",  # panabit=新疆联通校园网(自动识别验证码) drcom/ruijie/browser
    "login_url": "http://172.168.0.0:8788/",  # Panabit 门户地址
    "check_interval": 10,     # 检测间隔（秒）
}

PROBE_URLS = [
    "http://connect.rom.miui.com/generate_204",
    "http://www.gstatic.com/generate_204",
    "https://www.baidu.com",
]

USER_KEYS = {"username", "user", "userid", "user_id", "account", "user_account",
             "loginname", "name", "j_username", "user_name", "username_text", "auth_user"}
PASS_KEYS = {"password", "passwd", "pwd", "user_password", "pass",
             "j_password", "user_pwd", "auth_pass", "password_text"}


# ---------- 基础工具 ----------

def setup_console():
    """让控制台正确显示中文"""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg.update(saved)
        except Exception as e:
            log("读取配置失败：" + str(e))
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def first_run_setup():
    print("=" * 46)
    print("  首次运行，请填写校园网信息")
    print("=" * 46)
    try:
        ssid = input("① 校园网 WiFi 名称（回车跳过，有线网不用填）: ").strip()
        user = input("② 校园网账号: ").strip()
        pwd = input("③ 校园网密码: ").strip()
        method = input("④ 登录方式 [回车=panabit新疆联通校园网 | drcom | ruijie | browser]: ").strip().lower()
        url = input("⑤ 登录页网址（可选，回车自动用 http://172.168.0.0:8788）: ").strip()
    except Exception as e:
        log("输入失败：" + str(e))
        return None
    if not method:
        method = "panabit"
    if method not in ("panabit", "auto", "drcom", "ruijie", "browser"):
        log("登录方式无效，已改为 panabit")
        method = "panabit"
    if not url:
        url = "http://172.168.0.0:8788/"
    cfg = dict(DEFAULTS)
    cfg.update({"wifi_ssid": ssid, "username": user, "password": pwd,
                "login_method": method, "login_url": url})
    save_config(cfg)
    log("配置已保存：" + CONFIG_PATH)
    return cfg


# ---------- 网络探测 ----------

def http_get(url, timeout=8, follow=True):
    """GET 请求。返回 (最终地址, 状态码, 文本)。失败返回 (None, 0, '')"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
    try:
        req = urllib.request.Request(url, headers=headers)
        if not follow:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            opener = urllib.request.build_opener(NoRedirect)
            resp = opener.open(req, timeout=timeout)
        else:
            resp = urllib.request.urlopen(req, timeout=timeout)
        final = resp.geturl()
        status = resp.status
        body = resp.read(65536).decode("utf-8", "ignore")
        return final, status, body
    except urllib.error.HTTPError as e:
        return e.geturl() if e.geturl() else url, e.code, ""
    except Exception:
        return None, 0, ""


def is_online(probe_urls=None):
    """判断是否真正能上外网。返回 True/False"""
    for url in (probe_urls or PROBE_URLS):
        final, status, body = http_get(url, timeout=6)
        if not final:
            continue
        base = url.split("?")[0].rstrip("/")
        fbase = final.split("?")[0].rstrip("/")
        # 被重定向到别的地址 = 被认证页劫持 = 未联网
        if fbase != base:
            continue
        if status == 204:
            return True
        if status == 200 and base.startswith("https://www.baidu.com"):
            return True
        # 200 但返回的是 HTML（认证页伪装）则视为离线
        if "<html" in body.lower() or "<!doctype" in body.lower():
            continue
        if status == 200:
            return True
    return False


def default_gateway():
    """解析当前上网网卡对应的默认网关（跳过 VPN / 虚拟网卡）"""
    try:
        out = subprocess.run(["ipconfig"], capture_output=True, text=True,
                             encoding="gbk", errors="ignore", timeout=10).stdout
        # 按适配器切段（段首行顶格且以冒号结尾）
        sections = []
        cur = []
        for ln in out.splitlines():
            if ln and not ln[0].isspace() and ln.rstrip().endswith(":"):
                if cur:
                    sections.append(cur)
                cur = [ln]
            else:
                cur.append(ln)
        if cur:
            sections.append(cur)
        if not sections:
            return ""
        lip = local_ip()
        for sec in sections:
            text = "\n".join(sec)
            if lip and lip in text:
                for ln in sec:
                    m = re.search(r"(?:默认网关|Default Gateway)[^:]*:\s*(\S+)", ln)
                    if m and m.group(1) not in ("0.0.0.0",):
                        return m.group(1)
        # 回退：找第一个有真实 IPv4 且有网关的网卡
        for sec in sections:
            text = "\n".join(sec)
            has_real = re.search(r"(?:IPv4 地址|IPv4 Address)[^:]*:\s*((?!169\.254)\d+\.\d+\.\d+\.\d+)", text)
            if not has_real:
                continue
            for ln in sec:
                m = re.search(r"(?:默认网关|Default Gateway)[^:]*:\s*(\S+)", ln)
                if m and m.group(1) not in ("0.0.0.0",):
                    return m.group(1)
    except Exception:
        pass
    return ""


def local_ip():
    """获取本机在当前网络下的 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 53))  # UDP connect 不发包，仅用于确定出口网卡
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("169.254."):
            return ip
    except Exception:
        pass
    return ""


def local_mac():
    try:
        return "%012X" % uuid.getnode()
    except Exception:
        return "000000000000"


def detect_portal():
    """探测认证门户地址。优先跟随探测 URL 的重定向，其次尝试网关"""
    for url in PROBE_URLS:
        try:
            final, status, body = http_get(url, timeout=8, follow=True)
            if not final:
                continue
            base = url.split("?")[0].rstrip("/")
            fbase = final.split("?")[0].rstrip("/")
            if fbase != base:
                return final
        except Exception:
            continue
    gw = default_gateway()
    if gw and gw not in ("0.0.0.0",):
        return "http://" + gw
    return ""


# ---------- WiFi 连接 ----------

def saved_profiles():
    try:
        out = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True,
                             text=True, encoding="gbk", errors="ignore", timeout=10).stdout
        names = re.findall(r":\s*([^:\r\n]+)", out)
        return [n.strip() for n in names]
    except Exception:
        return []


def current_ssid():
    try:
        out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True,
                             text=True, encoding="gbk", errors="ignore", timeout=10).stdout
        m = re.search(r"SSID\s*:\s*(.+)", out)
        return m.group(1).strip() if m else ""
    except Exception:
        return ""


def connect_wifi(ssid):
    if not ssid:
        return True
    if current_ssid() == ssid:
        return True
    if ssid not in saved_profiles():
        log("未找到已保存的 WiFi「" + ssid + "」，请先手动连接一次保存密码。")
        return False
    log("正在连接 WiFi：「" + ssid + "」……")
    try:
        subprocess.run(["netsh", "wlan", "connect", "name=" + ssid],
                       capture_output=True, timeout=15)
    except Exception:
        pass
    for _ in range(12):  # 最多等 60 秒
        time.sleep(5)
        if current_ssid() == ssid:
            log("WiFi 已连接")
            return True
    log("WiFi 连接失败（可能信号弱或需要手动连接）")
    return False


# ---------- 网页认证登录 ----------

def parse_forms(html, page_url):
    """解析页面中的表单，返回 [{action, method, inputs:[{name,type,value}]}]"""
    forms = []
    for fm in re.finditer(r"<form\b[^>]*>", html, re.I):
        attrs = fm.group(0)
        am = re.search(r'action\s*=\s*["\']?([^"\'>\s]+)', attrs, re.I)
        mm = re.search(r'method\s*=\s*["\']?([^"\'>\s]+)', attrs, re.I)
        end = html.find("</form>", fm.end())
        inner = html[fm.end(): (end if end != -1 else fm.end() + 8000)]
        inputs = []
        for inp in re.finditer(r"<input\b[^>]*>", inner, re.I):
            ia = inp.group(0)
            nm = re.search(r'name\s*=\s*["\']?([^"\'>\s]+)', ia, re.I)
            if not nm:
                continue
            tm = re.search(r'type\s*=\s*["\']?([^"\'>\s]+)', ia, re.I)
            vm = re.search(r'value\s*=\s*["\']?([^"\'>\s]*)', ia, re.I)
            inputs.append({
                "name": nm.group(1),
                "type": (tm.group(1) if tm else "text").lower(),
                "value": vm.group(1) if vm else "",
            })
        forms.append({
            "action": (am.group(1) if am else page_url),
            "method": (mm.group(1) if mm else "get").lower(),
            "inputs": inputs,
        })
    return forms


def submit_form(form, page_url, user, pwd):
    """填充并提交表单，返回 (状态码, 响应文本)"""
    data = {}
    for i in form["inputs"]:
        nl = i["name"].lower()
        if i["type"] == "hidden":
            data[i["name"]] = i["value"]
        elif nl in USER_KEYS:
            data[i["name"]] = user
        elif nl in PASS_KEYS:
            data[i["name"]] = pwd
        else:
            data[i["name"]] = i["value"] or ""
    action = urllib.parse.urljoin(page_url, form["action"])
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
                   "Content-Type": "application/x-www-form-urlencoded"}
        if form["method"] == "get":
            action = action + ("&" if "?" in action else "?") + urllib.parse.urlencode(data)
            req = urllib.request.Request(action, headers=headers)
        else:
            req = urllib.request.Request(action, data=urllib.parse.urlencode(data).encode(),
                                         headers=headers)
        resp = urllib.request.urlopen(req, timeout=12)
        return resp.status, resp.read(65536).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def form_login(portal_url, user, pwd):
    """通用网页表单登录：抓登录页 → 解析表单 → 提交账号密码 → 是否联网"""
    final, status, html = http_get(portal_url, timeout=12)
    if not final or not html:
        return False
    forms = parse_forms(html, final)
    if not forms:
        return False
    for form in forms:
        code, text = submit_form(form, final, user, pwd)
        if code == 0:
            continue
        if is_online():
            return True
        # 部分认证页登录后返回包含 success 的文本
        if "success" in text.lower() and ("登录" in text or "success" in text.lower()):
            time.sleep(3)
            if is_online():
                return True
    return False


def drcom_login(gw, user, pwd):
    """Dr.COM eportal 认证（很多高校在用）"""
    if not gw:
        return False
    ip = local_ip()
    mac = local_mac()
    params = {
        "callback": "dr1003", "login_method": "1",
        "user_account": user, "user_password": pwd,
        "wlan_user_ip": ip, "wlan_user_ipv6": "",
        "wlan_user_mac": mac, "wlan_ac_ip": "", "wlan_ac_name": "",
        "jsVersion": "4.1", "terminal_type": "1", "lang": "zh-cn", "v": "1003",
    }
    for port in ("801", ""):
        url = "http://{}:{}/eportal/?c=Portal&a=login&{}".format(
            gw, port, urllib.parse.urlencode(params))
        final, status, body = http_get(url, timeout=10)
        if body and "success" in body.lower():
            time.sleep(3)
            return is_online()
    return False


def ruijie_login(gw, user, pwd):
    """锐捷 SAM 网页认证"""
    if not gw:
        return False
    data = urllib.parse.urlencode({
        "user_name": user, "user_password": pwd,
        "wlan_user_ip": local_ip(), "service": "internet",
    }).encode()
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"}
        req = urllib.request.Request("http://%s/portal_io/login" % gw,
                                     data=data, headers=headers)
        resp = urllib.request.urlopen(req, timeout=10)
        body = resp.read(4096).decode("utf-8", "ignore")
        if "success" in body.lower():
            time.sleep(3)
            return is_online()
    except Exception:
        pass
    return False


# ---------- Panabit（新疆联通校园宽带）专用登录 ----------

_PANABIT_OCR = None


def _get_ocr():
    global _PANABIT_OCR
    if _PANABIT_OCR is None:
        import ddddocr
        _PANABIT_OCR = ddddocr.DdddOcr(show_ad=False)
    return _PANABIT_OCR


def _des_encrypt(text, key=b"12345678"):
    """与门户 JS encryptByDES 一致：DES/ECB/PKCS7，Base64 输出"""
    import base64
    from Crypto.Cipher import DES
    from Crypto.Util.Padding import pad
    cipher = DES.new(key, DES.MODE_ECB)
    return base64.b64encode(cipher.encrypt(pad(text.encode("utf-8"), 8))).decode()


def panabit_login(user, pwd, portal_base="http://172.168.0.0:8788"):
    """Panabit 门户登录：带会话 cookie，自动识别验证码，失败重试"""
    import http.cookiejar
    portal_base = portal_base.rstrip("/")
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"

    def get(path):
        req = urllib.request.Request(portal_base + path, headers={"User-Agent": ua})
        return opener.open(req, timeout=10).read()

    for attempt in range(4):
        try:
            root = get("/").decode("gbk", "ignore")
            m = re.search(r'mainFrame[^>]*src="([^"]+)"', root)
            if not m:
                log("未找到登录主框架")
                return False
            idx = get(m.group(1)).decode("utf-8", "ignore")
            fields = {}
            for fm in re.finditer(r'<input[^>]*>', idx, re.I):
                tag = fm.group(0)
                nm = re.search(r'name="([^"]+)"', tag, re.I)
                vm = re.search(r'value="([^"]*)"', tag, re.I)
                if nm:
                    fields[nm.group(1)] = vm.group(1) if vm else ""
            img = get("/createVerifycode?id=verifycode&t=" + str(int(time.time() * 1000)))
            code = _get_ocr().classification(img)
            code = re.sub(r"\D", "", code)[:4]
            log("Panabit 第 %d 次尝试，验证码=%s" % (attempt + 1, code or "识别为空"))
            if not code:
                continue
            fields["UserName"] = _des_encrypt(user)
            fields["PassWord"] = _des_encrypt(pwd)
            fields["verifycode"] = _des_encrypt(code)
            data = urllib.parse.urlencode(fields).encode()
            req = urllib.request.Request(portal_base + "/authServlet", data=data,
                                         headers={"User-Agent": ua,
                                                  "Content-Type": "application/x-www-form-urlencoded"})
            opener.open(req, timeout=12).read(2048)
            time.sleep(3)
            if is_online():
                log("✅ Panabit 登录成功")
                return True
            log("本次登录未通过，刷新验证码重试……")
            time.sleep(1)
        except Exception as e:
            log("Panabit 登录异常：" + str(e))
            time.sleep(2)
    return False


_last_browser_open = 0.0
BROWSER_COOLDOWN = 300  # 登录页最多每 5 分钟打开一次，避免反复弹窗


def open_portal_browser(target):
    """打开认证登录页（带冷却，避免每次检测都弹窗）"""
    global _last_browser_open
    now = time.time()
    if now - _last_browser_open < BROWSER_COOLDOWN:
        return
    _last_browser_open = now
    if target:
        log("正在打开登录页：" + target)
        webbrowser.open(target)


def try_login(cfg):
    """根据配置尝试登录，返回是否已联网"""
    user = cfg.get("username", "")
    pwd = cfg.get("password", "")
    method = cfg.get("login_method", "auto")
    portal = (cfg.get("login_url") or "").strip() or detect_portal()

    if method == "browser" or not user or not pwd:
        target = portal or ("http://" + default_gateway())
        open_portal_browser(target)
        return False

    # auto：先试通用网页表单，再试 Dr.COM / 锐捷
    if method == "panabit":
        if panabit_login(user, pwd, cfg.get("login_url") or "http://172.168.0.0:8788"):
            return True
        log("Panabit 自动登录未通过（可能密码错误），打开登录页请手动完成。")
        open_portal_browser(cfg.get("login_url") or "http://172.168.0.0:8788/")
        return False
    if method in ("auto", "form"):
        if portal:
            log("检测到认证门户：" + portal)
            if form_login(portal, user, pwd):
                return True
            log("网页表单登录未成功，尝试其他方式……")
    if method in ("auto", "drcom"):
        if drcom_login(default_gateway(), user, pwd):
            return True
    if method in ("auto", "ruijie"):
        if ruijie_login(default_gateway(), user, pwd):
            return True

    log("自动登录未成功（可能有验证码/滑块，或账号密码错误），打开登录页请手动完成。")
    target = portal or ("http://" + default_gateway())
    open_portal_browser(target)
    return False


# ---------- 主流程 ----------

def monitor_loop(cfg):
    """持续监控：掉线自动重连"""
    while True:
        try:
            if cfg.get("wifi_ssid") and current_ssid() != cfg.get("wifi_ssid"):
                connect_wifi(cfg.get("wifi_ssid"))
                time.sleep(3)

            if is_online():
                time.sleep(cfg.get("check_interval", 10))
                continue

            log("检测到未联网，尝试自动登录……")
            if try_login(cfg):
                log("✅ 登录成功，已联网")
            else:
                log("登录未完成，等待下次检测……")
            time.sleep(8)
        except KeyboardInterrupt:
            log("已手动停止")
            break
        except Exception as e:
            log("运行异常：" + str(e))
            time.sleep(cfg.get("check_interval", 10))


def main():
    setup_console()
    if "--setup" in sys.argv:
        cfg = first_run_setup()
        if cfg and cfg.get("username"):
            log("设置完成，可直接双击启动监控。")
        return

    cfg = load_config()
    if not cfg.get("username") or not cfg.get("password"):
        log("尚未配置账号密码，进入首次设置……")
        cfg = first_run_setup()
        if not cfg or not cfg.get("username"):
            log("未完成设置，程序退出。重新双击即可再设置。")
            return

    log("校园网自动连接程序已启动（关闭本窗口即停止监控）")
    log("WiFi：「%s」 登录方式：%s 检测间隔：%s 秒" % (
        cfg.get("wifi_ssid") or "不自动连WiFi", cfg.get("login_method"), cfg.get("check_interval")))
    monitor_loop(cfg)


def autostart():
    """开机自启模式：无窗口后台运行，日志写入 运行日志.log"""
    cfg = load_config()
    if not cfg.get("username") or not cfg.get("password"):
        # 还没填过账号密码：弹出一个可见的设置窗口让用户填写
        try:
            py = os.path.join(os.path.dirname(sys.executable), "python.exe")
            subprocess.Popen([py, os.path.abspath(__file__), "--setup"],
                             creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        except Exception:
            pass
        return

    log("开机自启：等待网络就绪后开始监控……")
    time.sleep(30)  # 开机后等 WiFi/网络稳定
    log("校园网自动连接程序已启动（开机自启，日志见 运行日志.log）")
    monitor_loop(cfg)


if __name__ == "__main__":
    if "--test" in sys.argv:
        setup_console()
        print("在线状态：", "在线" if is_online() else "离线")
        print("网关：", default_gateway())
        print("本机IP：", local_ip())
        print("当前WiFi：", current_ssid())
        print("认证门户：", detect_portal() or "未探测到（当前可能已联网）")
    elif "--autostart" in sys.argv:
        autostart()
    else:
        main()
