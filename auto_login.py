# -*- coding: utf-8 -*-
"""校园网自动连接 - 纯后台静默版，自动切换WiFi+自动认证，连上自动退出"""
import os, sys, time, subprocess, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campus as core

NO_WINDOW = 0x08000000


def get_all_wifi():
    """获取附近所有校园WiFi列表，按信号强度排序"""
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, text=True, encoding="gbk", errors="ignore",
            timeout=10, creationflags=NO_WINDOW
        ).stdout
    except Exception:
        return []

    networks = []
    current_ssid = None
    current_signal = 0

    for line in out.splitlines():
        line = line.strip()
        # 遇到新的SSID行，保存上一个
        m = re.match(r"^SSID\s+\d+\s*:\s*(.+)", line)
        if m and not line.startswith("BSSID"):
            if current_ssid and current_signal > 0:
                networks.append((current_ssid, current_signal))
            current_ssid = m.group(1).strip()
            current_signal = 0
            continue
        m = re.match(r"^Signal\s*:\s*(\d+)%", line)
        if m and current_ssid:
            current_signal = int(m.group(1))

    # 保存最后一个
    if current_ssid and current_signal > 0:
        networks.append((current_ssid, current_signal))

    # 只保留校园WiFi（CU_开头），按信号从高到低排序
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
    # 先检查是否已在线
    if core.is_online():
        return  # 已在线，直接退出

    # 读取配置
    cfg = core.load_config()
    if not cfg.get("username") or not cfg.get("password"):
        return  # 没配置账号，直接退出

    # 获取所有校园WiFi
    wifi_list = get_all_wifi()
    if not wifi_list:
        return  # 没找到校园WiFi

    # 逐个尝试连接
    for ssid, signal in wifi_list[:5]:  # 试前5个信号最好的
        # 连接WiFi
        if not connect_wifi(ssid):
            continue

        # 等一下获取IP
        time.sleep(3)

        # 尝试认证
        for retry in range(2):
            try:
                ok = core.try_login(cfg)
                if ok and core.is_online():
                    return  # 成功，退出
            except Exception:
                pass
            time.sleep(2)

    # 所有WiFi都试完了还没连上，退出


if __name__ == "__main__":
    main()
