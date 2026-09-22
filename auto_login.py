# -*- coding: utf-8 -*-
"""校园网自动连接 - 后台常驻版，持续监控，掉线自动重连"""
import os, sys, time, subprocess, re, json, traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campus as core

NO_WINDOW = 0x08000000
APP_DIR = core.APP_DIR
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOG_PATH = os.path.join(APP_DIR, "auto_login.log")


def log(msg):
    """写日志文件"""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"读取配置失败: {e}")
        return {}


def get_all_wifi():
    """获取附近所有校园WiFi列表，按信号强度排序"""
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, timeout=10, creationflags=NO_WINDOW
        ).stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        log(f"扫描WiFi失败: {e}")
        return []

    networks = []
    current_ssid = None
    current_signal = 0

    for line in out.splitlines():
        line = line.strip()
        m = re.match(r"^SSID\s+\d+\s*:\s*(.+)", line)
        if m and not line.startswith("BSSID"):
            if current_ssid and current_signal > 0:
                networks.append((current_ssid, current_signal))
            current_ssid = m.group(1).strip()
            current_signal = 0
            continue
        m = re.match(r"^(?:Signal|信号)\s*:\s*(\d+)%", line)
        if m and current_ssid:
            current_signal = int(m.group(1))

    if current_ssid and current_signal > 0:
        networks.append((current_ssid, current_signal))

    campus_wifi = [(s, sig) for s, sig in networks if s.startswith("CU_")]
    campus_wifi.sort(key=lambda x: x[1], reverse=True)
    return campus_wifi


def connect_wifi(ssid):
    """连接指定WiFi"""
    try:
        log(f"正在连接 {ssid}...")
        subprocess.run(
            ["netsh", "wlan", "connect", f"name={ssid}"],
            capture_output=True, timeout=15, creationflags=NO_WINDOW
        )
        time.sleep(5)
        result = core.current_ssid() == ssid
        log(f"连接 {ssid}: {'成功' if result else '失败'}")
        return result
    except Exception as e:
        log(f"连接WiFi异常: {e}")
        return False


def main():
    log("=" * 50)
    log("校园网自动连接后台服务启动")
    check_interval = 30

    while True:
        try:
            # 读取配置
            cfg = load_config()
            if not cfg.get("username") or not cfg.get("password"):
                log("未配置账号，等待配置...")
                time.sleep(60)
                continue

            # 检查是否在线
            online = core.is_online()
            log(f"检测在线状态: {online}")

            if online:
                time.sleep(check_interval)
                continue

            log("检测到未联网，开始自动连接...")

            # 获取所有校园WiFi
            wifi_list = get_all_wifi()
            log(f"找到 {len(wifi_list)} 个校园WiFi")
            if not wifi_list:
                log("没找到校园WiFi，重试...")
                time.sleep(10)
                continue

            # 先试当前WiFi，不行再切换
            current_ssid = core.current_ssid()
            log(f"当前WiFi: {current_ssid}")

            if current_ssid.startswith("CU_"):
                # 当前已经是校园WiFi，直接尝试认证
                log("当前已是校园WiFi，直接尝试认证...")
                for retry in range(3):
                    try:
                        log(f"第 {retry+1} 次尝试认证...")
                        ok = core.try_login(cfg)
                        log(f"认证结果: {ok}")
                        if ok and core.is_online():
                            log("认证成功！")
                            break
                    except Exception as e:
                        log(f"认证失败: {e}")
                    time.sleep(3)

                if core.is_online():
                    time.sleep(check_interval)
                    continue

            # 当前WiFi不行，切换到信号最好的
            log("切换到信号最好的WiFi...")
            for ssid, signal in wifi_list[:3]:
                log(f"尝试连接 {ssid} (信号{signal}%)...")
                if not connect_wifi(ssid):
                    continue

                # 连接成功，尝试认证
                log(f"已连接 {ssid}，开始认证...")
                time.sleep(3)
                for retry in range(3):
                    try:
                        log(f"第 {retry+1} 次尝试认证...")
                        ok = core.try_login(cfg)
                        if ok and core.is_online():
                            log("认证成功！")
                            break
                    except Exception as e:
                        log(f"认证失败: {e}")
                    time.sleep(3)

                if core.is_online():
                    break

            log("一轮连接尝试结束")
            time.sleep(check_interval)

        except Exception as e:
            log(f"主循环异常: {e}")
            log(traceback.format_exc())
            time.sleep(10)


if __name__ == "__main__":
    main()
