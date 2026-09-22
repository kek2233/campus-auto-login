# -*- coding: utf-8 -*-
"""校园网自动连接 - 后台常驻版，持续监控，掉线自动重连"""
import os, sys, time, subprocess, re, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campus as core

NO_WINDOW = 0x08000000
APP_DIR = core.APP_DIR
CONFIG_PATH = os.path.join(APP_DIR, "config.json")


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_all_wifi():
    """获取附近所有校园WiFi列表，按信号强度排序"""
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, timeout=10, creationflags=NO_WINDOW
        ).stdout.decode("utf-8", errors="ignore")
    except Exception:
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
        subprocess.run(
            ["netsh", "wlan", "connect", f"name={ssid}"],
            capture_output=True, timeout=15, creationflags=NO_WINDOW
        )
        time.sleep(5)
        return core.current_ssid() == ssid
    except Exception:
        return False


def main():
    print("校园网自动连接后台服务已启动")
    check_interval = 30  # 每30秒检测一次

    while True:
        try:
            # 读取配置
            cfg = load_config()
            if not cfg.get("username") or not cfg.get("password"):
                print("未配置账号，等待配置...")
                time.sleep(60)
                continue

            # 检查是否在线
            if core.is_online():
                print(time.strftime("%H:%M:%S"), "已在线，正常运行")
                time.sleep(check_interval)
                continue

            print(time.strftime("%H:%M:%S"), "检测到未联网，开始自动连接...")

            # 获取所有校园WiFi
            wifi_list = get_all_wifi()
            if not wifi_list:
                print("没找到校园WiFi，重试...")
                time.sleep(10)
                continue

            # 先试当前WiFi，不行再切换
            current_ssid = core.current_ssid()
            if current_ssid.startswith("CU_"):
                # 当前已经是校园WiFi，直接尝试认证
                print(f"当前WiFi: {current_ssid}，尝试认证...")
                for retry in range(3):
                    try:
                        ok = core.try_login(cfg)
                        if ok and core.is_online():
                            print("认证成功！")
                            break
                    except Exception as e:
                        print(f"认证失败: {e}")
                    time.sleep(3)

                if core.is_online():
                    time.sleep(check_interval)
                    continue

            # 当前WiFi不行，切换到信号最好的
            print("切换到信号最好的WiFi...")
            for ssid, signal in wifi_list[:3]:
                print(f"尝试连接 {ssid} (信号{signal}%)...")
                if not connect_wifi(ssid):
                    print(f"连接 {ssid} 失败")
                    continue

                # 连接成功，尝试认证
                print(f"已连接 {ssid}，开始认证...")
                time.sleep(3)
                for retry in range(3):
                    try:
                        ok = core.try_login(cfg)
                        if ok and core.is_online():
                            print("认证成功！")
                            break
                    except Exception as e:
                        print(f"认证失败: {e}")
                    time.sleep(3)

                if core.is_online():
                    break

            time.sleep(check_interval)

        except Exception as e:
            print(f"出错: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
