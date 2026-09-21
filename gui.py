# -*- coding: utf-8 -*-
"""校园网自动连接 - 浅色标签页风格 GUI"""
import os, sys, threading, time, subprocess
import tkinter as tk
from tkinter import scrolledtext, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campus as core

# 配色（浅色风格）
BG       = "#f0f0f0"
PANEL    = "#ffffff"
FG       = "#333333"
DIM      = "#888888"
ACCENT   = "#2e9e7b"
ACCENT_H = "#268868"
RED      = "#e74c3c"
GREEN    = "#2e9e7b"
BORDER   = "#dddddd"
ENTRY_BG = "#f5f5f5"

NO_WINDOW = 0x08000000
APP_DIR = core.APP_DIR


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = core.load_config()
        self.running = True
        self.online = False
        self._build_ui()
        if not self.cfg.get("username") or not self.cfg.get("password"):
            self.root.after(300, lambda: self._switch_tab(1))
        self.root.after(500, self._start_monitor)

    def _build_ui(self):
        self.root.title("校园网自动连接")
        self.root.configure(bg=BG)
        self.root.geometry("680x480")
        self.root.minsize(600, 420)

        # 顶部状态栏
        top = tk.Frame(self.root, bg=PANEL, height=40)
        top.pack(fill="x")
        top.pack_propagate(False)
        self.lbl_ip = tk.Label(top, text="IP：检测中…", bg=PANEL, fg=FG,
                               font=("Microsoft YaHei UI", 9))
        self.lbl_ip.pack(side="left", padx=12)
        self.lbl_status = tk.Label(top, text="● 未登录", bg=PANEL, fg=RED,
                                    font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_status.pack(side="left", padx=8)
        tk.Label(top, text="设备：校园网认证", bg=PANEL, fg=DIM,
                 font=("Microsoft YaHei UI", 9)).pack(side="right", padx=12)

        # 账号密码栏
        acc = tk.Frame(self.root, bg=PANEL)
        acc.pack(fill="x")
        tk.Label(acc, text="账号：", bg=PANEL, fg=FG,
                 font=("Microsoft YaHei UI", 10)).pack(side="left", padx=(12, 4), pady=8)
        self.e_user = tk.Entry(acc, width=18, font=("Microsoft YaHei UI", 10),
                               bg=ENTRY_BG, relief="solid", bd=1)
        self.e_user.pack(side="left", pady=8)
        self.e_user.insert(0, self.cfg.get("username", ""))
        tk.Label(acc, text="密码：", bg=PANEL, fg=FG,
                 font=("Microsoft YaHei UI", 10)).pack(side="left", padx=(12, 4), pady=8)
        self.e_pwd = tk.Entry(acc, width=18, show="*", font=("Microsoft YaHei UI", 10),
                              bg=ENTRY_BG, relief="solid", bd=1)
        self.e_pwd.pack(side="left", pady=8)
        self.e_pwd.insert(0, self.cfg.get("password", ""))
        self.var_remember = tk.IntVar(value=1)
        tk.Checkbutton(acc, text="记住密码", variable=self.var_remember,
                       bg=PANEL, fg=FG, font=("Microsoft YaHei UI", 9)).pack(side="left", padx=8, pady=8)
        self.btn_login = tk.Button(acc, text="登录", command=self._login,
                                   bg=ACCENT, fg="white", relief="flat",
                                   font=("Microsoft YaHei UI", 10, "bold"),
                                   padx=18, pady=4, cursor="hand2", bd=0,
                                   activebackground=ACCENT_H, activeforeground="white")
        self.btn_login.pack(side="right", padx=12, pady=6)

        # 标签栏
        tabs = tk.Frame(self.root, bg=PANEL)
        tabs.pack(fill="x")
        self.btns = {}
        for i, name in enumerate(["首页", "设置", "运行日志"]):
            b = tk.Label(tabs, text=name, bg=PANEL, fg=FG,
                         font=("Microsoft YaHei UI", 10), padx=16, pady=8,
                         cursor="hand2")
            b.pack(side="left", padx=(4, 0), pady=(2, 0))
            b.bind("<Button-1>", lambda e, idx=i: self._switch_tab(idx))
            self.btns[i] = b
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # 内容区
        self.container = tk.Frame(self.root, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.pages = [tk.Frame(self.container, bg=BG) for _ in range(3)]
        self._build_home(self.pages[0])
        self._build_settings(self.pages[1])
        self._build_log(self.pages[2])

        # 底部状态栏
        bottom = tk.Frame(self.root, bg=PANEL, height=28)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)
        self.lbl_line = tk.Label(bottom, text="日志 0 行", bg=PANEL, fg=DIM,
                                 font=("Microsoft YaHei UI", 8))
        self.lbl_line.pack(side="left", padx=12, pady=4)
        tk.Label(bottom, text="就绪", bg=PANEL, fg=DIM,
                 font=("Microsoft YaHei UI", 8)).pack(side="left", padx=12, pady=4)

        self._switch_tab(0)

    def _build_home(self, page):
        tk.Label(page, text="", bg=BG).pack(pady=30)
        self.lbl_hi_status = tk.Label(page, text="检测中…", bg=BG, fg=DIM,
                                      font=("Microsoft YaHei UI", 18, "bold"))
        self.lbl_hi_status.pack(pady=10)
        self.lbl_hi_detail = tk.Label(page, text="", bg=BG, fg=DIM,
                                      font=("Microsoft YaHei UI", 10))
        self.lbl_hi_detail.pack(pady=4)
        self.btn_manual = tk.Button(page, text="立即连接", command=self._manual,
                                     bg=ACCENT, fg="white", relief="flat",
                                     font=("Microsoft YaHei UI", 12, "bold"),
                                     padx=30, pady=8, cursor="hand2", bd=0,
                                     activebackground=ACCENT_H)
        self.btn_manual.pack(pady=20)
        tk.Label(page, text="自动监控已开启，掉线会自动重连", bg=BG, fg=DIM,
                 font=("Microsoft YaHei UI", 9)).pack(pady=10)

    def _build_settings(self, page):
        f = tk.Frame(page, bg=BG)
        f.pack(padx=40, pady=20, anchor="w")
        self.entries = {}
        rows = [
            ("校园网 WiFi 名", "e_wifi", self.cfg.get("wifi_ssid", "")),
            ("检测间隔（秒）", "e_interval", str(self.cfg.get("check_interval", 10))),
        ]
        for i, (label, key, val) in enumerate(rows):
            tk.Label(f, text=label + "：", bg=BG, fg=FG,
                     font=("Microsoft YaHei UI", 10)).grid(row=i, column=0, sticky="w", pady=6)
            e = tk.Entry(f, width=30, font=("Microsoft YaHei UI", 10),
                         bg=ENTRY_BG, relief="solid", bd=1)
            e.grid(row=i, column=1, pady=6, padx=8)
            e.insert(0, val)
            self.entries[key] = e
        tk.Label(f, text="（WiFi 名留空则自动连接当前已连的校园网）", bg=BG, fg=DIM,
                 font=("Microsoft YaHei UI", 9)).grid(row=len(rows), column=1, sticky="w", pady=4)
        tk.Button(f, text="保存设置", command=self._save_settings,
                  bg=ACCENT, fg="white", relief="flat",
                  font=("Microsoft YaHei UI", 10), padx=20, pady=4,
                  cursor="hand2", bd=0).grid(row=len(rows)+1, column=0, pady=16, sticky="w")
        tk.Button(f, text="开启/关闭开机自启", command=self._toggle_autostart,
                  bg="#4a6fa5", fg="white", relief="flat",
                  font=("Microsoft YaHei UI", 10), padx=20, pady=4,
                  cursor="hand2", bd=0).grid(row=len(rows)+1, column=1, pady=16, sticky="w")

    def _build_log(self, page):
        self.log = scrolledtext.ScrolledText(page, bg=PANEL, fg=FG,
                                             font=("Consolas", 9), wrap="word",
                                             relief="flat", state="disabled", borderwidth=0)
        self.log.pack(fill="both", expand=True, padx=2, pady=2)

    def _switch_tab(self, idx):
        for i, page in enumerate(self.pages):
            if i == idx:
                page.pack(fill="both", expand=True)
                self.btns[i].config(bg=BORDER, fg=ACCENT)
            else:
                page.pack_forget()
                self.btns[i].config(bg=PANEL, fg=FG)

    def log_line(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", "[%s] %s\n" % (ts, msg))
        self.log.see("end")
        self.log.configure(state="disabled")
        n = int(self.log.index("end-1c").split(".")[0])
        self.lbl_line.config(text="日志 %d 行" % n)

    def set_status(self, online, detail=""):
        if online:
            self.lbl_status.config(text="● 已登录", fg=GREEN)
            self.lbl_hi_status.config(text="已联网", fg=GREEN)
        else:
            self.lbl_status.config(text="● 未登录", fg=RED)
            self.lbl_hi_status.config(text="未联网", fg=RED)
        self.lbl_hi_detail.config(text=detail)

    def _login(self):
        u = self.e_user.get().strip()
        p = self.e_pwd.get().strip()
        if not u or not p:
            messagebox.showwarning("提示", "请输入账号和密码")
            return
        self.cfg["username"] = u
        self.cfg["password"] = p
        self.cfg["login_method"] = "panabit"
        self.cfg["login_url"] = "http://172.168.0.0:8788/"
        if self.var_remember.get():
            core.save_config(self.cfg)
        self.log_line("手动登录…")
        self.btn_login.config(state="disabled", text="登录中…")
        threading.Thread(target=self._do_login, daemon=True).start()

    def _manual(self):
        self._login()

    def _do_login(self):
        try:
            ok = core.try_login(self.cfg)
            self.root.after(0, lambda: self.btn_login.config(state="normal", text="登录"))
            self.root.after(0, lambda o=ok: self.log_line("登录%s" % ("成功 ✅" if o else "失败")))
            self.root.after(0, lambda: self._refresh_status())
        except Exception as e:
            self.root.after(0, lambda: self.btn_login.config(state="normal", text="登录"))
            self.root.after(0, lambda e=e: self.log_line("登录出错：" + str(e)))

    def _save_settings(self):
        self.cfg["wifi_ssid"] = self.entries["e_wifi"].get().strip()
        try:
            self.cfg["check_interval"] = int(self.entries["e_interval"].get().strip())
        except:
            self.cfg["check_interval"] = 10
        core.save_config(self.cfg)
        self.log_line("设置已保存")
        messagebox.showinfo("提示", "设置已保存")

    def _toggle_autostart(self):
        startup = os.path.join(os.environ["APPDATA"],
                               r"Microsoft\Windows\Start Menu\Programs\Startup")
        lnk = os.path.join(startup, "校园网自动连接.lnk")
        try:
            if os.path.exists(lnk):
                os.remove(lnk)
                self.log_line("已关闭开机自启")
                messagebox.showinfo("开机自启", "已关闭")
            else:
                target = sys.executable if getattr(sys, "frozen", False) else \
                         "D:\\python\\pythonw.exe"
                ps = "$ws=New-Object -ComObject WScript.Shell;" \
                     "$l=$ws.CreateShortcut('%s');" \
                     "$l.TargetPath='%s';" \
                     "$l.WorkingDirectory='%s';" \
                     "$l.Save()" % (lnk, target, APP_DIR)
                subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, creationflags=NO_WINDOW)
                self.log_line("已开启开机自启")
                messagebox.showinfo("开机自启", "已开启")
        except Exception as e:
            self.log_line("操作失败：" + str(e))

    def _start_monitor(self):
        threading.Thread(target=self._monitor, daemon=True).start()

    def _monitor(self):
        first = True
        while self.running:
            try:
                online = core.is_online()
                ssid, ip = "—", "—"
                try:
                    ssid = core.current_ssid() or "—"
                    ip = core.local_ip() or "—"
                except:
                    pass
                detail = "WiFi：%s    IP：%s" % (ssid, ip)
                self.root.after(0, lambda o=online, d=detail: self.set_status(o, d))
                self.root.after(0, lambda i=ip: self.lbl_ip.config(text="IP：" + i))
                if not online and self.cfg.get("username"):
                    self.root.after(0, lambda: self.log_line("未联网，自动登录…"))
                    self._do_login()
                elif first and online:
                    first = False
                    self.root.after(0, lambda: self.log_line("已联网，正常运行中"))
            except Exception as e:
                self.root.after(0, lambda e=e: self.log_line("监控异常：" + str(e)))
            time.sleep(self.cfg.get("check_interval", 10))

    def _refresh_status(self):
        try:
            online = core.is_online()
            self.set_status(online, "")
        except:
            pass

    def on_close(self):
        self.running = False
        self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
