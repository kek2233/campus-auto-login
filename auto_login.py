# -*- coding: utf-8 -*-
"""校园网自动连接 - 纯后台静默版，连上自动退出"""
import os, sys, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campus as core

NO_WINDOW = 0x08000000


def main():
    # 检查是否已在线
    if core.is_online():
        return  # 已在线，直接退出

    # 读取配置
    cfg = core.load_config()
    if not cfg.get("username") or not cfg.get("password"):
        return  # 没配置账号，不弹任何提示，直接退出

    # 尝试登录，最多重试3次
    for i in range(3):
        try:
            ok = core.try_login(cfg)
            if ok and core.is_online():
                return  # 成功，退出
        except Exception:
            pass
        time.sleep(2)


if __name__ == "__main__":
    main()
