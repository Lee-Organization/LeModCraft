import os
import sys
import json
import uuid
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import requests  # for IP check


# =========================================================
#  INSTALL PATH (FROM ARGS OR SELF)
# =========================================================
def get_install_path():
    if "--install-path" in sys.argv:
        try:
            idx = sys.argv.index("--install-path")
            return sys.argv[idx + 1]
        except (ValueError, IndexError):
            pass
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_install_path()
ACCOUNT_DIR = os.path.join(BASE_DIR, "account")
MAIL_PATH = os.path.join(ACCOUNT_DIR, "mail.json")
IDENTITY_PATH = os.path.join(ACCOUNT_DIR, "identity.json")

os.makedirs(ACCOUNT_DIR, exist_ok=True)


# =========================================================
#  DEVICE / IP HELPERS
# =========================================================
def get_device_id():
    # Simple device ID based on MAC
    return hex(uuid.getnode())


def get_ip():
    try:
        return requests.get("https://api.ipify.org", timeout=3).text.strip()
    except Exception:
        return "unknown"


# =========================================================
#  MAIL SYSTEM
# =========================================================
def add_mail(msg_type, title, message, extra=None):
    if os.path.exists(MAIL_PATH):
        with open(MAIL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    entry = {
        "type": msg_type,
        "title": title,
        "message": message,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "read": False
    }
    if extra:
        entry.update(extra)

    data.append(entry)

    with open(MAIL_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def load_mail():
    if not os.path.exists(MAIL_PATH):
        return []
    with open(MAIL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_mail(data):
    with open(MAIL_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# =========================================================
#  IDENTITY / ACCOUNT
# =========================================================
def load_identity():
    if not os.path.exists(IDENTITY_PATH):
        return None
    with open(IDENTITY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_identity(email):
    identity = {
        "email": email,
        "device_id": get_device_id(),
        "signup_ip": get_ip(),
        "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    with open(IDENTITY_PATH, "w", encoding="utf-8") as f:
        json.dump(identity, f, indent=4)
    return identity


def security_check(identity):
    if not identity:
        return

    current_device = get_device_id()
    current_ip = get_ip()

    # Device mismatch
    if identity.get("device_id") != current_device:
        add_mail(
            "security",
            "New Device Login Detected",
            "Your account was accessed from a different device.",
            {"device_id": current_device}
        )

    # IP mismatch
    stored_ip = identity.get("signup_ip", "unknown")
    if stored_ip != "unknown" and current_ip != "unknown" and stored_ip != current_ip:
        add_mail(
            "security",
            "New IP Address Detected",
            f"Your account was accessed from a new IP: {current_ip}",
            {"ip": current_ip}
        )


# =========================================================
#  MAIN APP WINDOW
# =========================================================
class LeModCraftApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("LeModCraft")
        self.geometry("900x600")
        self.minsize(800, 500)

        # THEMES
        self.themes = {
            "dark": {
                "bg": "#1e1e1e",
                "sidebar": "#252526",
                "top": "#333333",
                "text": "#ffffff",
                "accent": "#0e639c"
            },
            "light": {
                "bg": "#f0f0f0",
                "sidebar": "#dcdcdc",
                "top": "#c8c8c8",
                "text": "#000000",
                "accent": "#0078d4"
            },
            "hacker": {
                "bg": "#000000",
                "sidebar": "#001100",
                "top": "#002200",
                "text": "#00ff00",
                "accent": "#00aa00"
            }
        }
        self.current_theme = "dark"

        self.identity = load_identity()
        security_check(self.identity)

        self.pages = {}
        self.sidebar_buttons = {}

        self.apply_theme()
        self.create_topbar()
        self.create_sidebar()
        self.create_content()
        self.load_pages()
        self.show_page("Home")

    # ================= THEME =================
    def apply_theme(self):
        theme = self.themes[self.current_theme]
        self.bg_dark = theme["bg"]
        self.bg_sidebar = theme["sidebar"]
        self.bg_top = theme["top"]
        self.fg_text = theme["text"]
        self.accent = theme["accent"]

        self.configure(bg=self.bg_dark)

        for page in getattr(self, "pages", {}).values():
            try:
                page.apply_theme()
            except AttributeError:
                pass

        for btn in self.sidebar_buttons.values():
            btn.configure(
                bg=self.bg_sidebar,
                fg=self.fg_text,
                activebackground=self.accent,
                activeforeground="white"
            )

        if hasattr(self, "topbar"):
            self.topbar.configure(bg=self.bg_top)
            for w in self.topbar.winfo_children():
                try:
                    w.configure(bg=self.bg_top, fg=self.fg_text)
                except:
                    pass

    # ================= TOP BAR =================
    def create_topbar(self):
        self.topbar = tk.Frame(self, bg=self.bg_top, height=40)
        self.topbar.pack(fill="x", side="top")

        tk.Label(
            self.topbar,
            text="LeModCraft Launcher",
            bg=self.bg_top,
            fg=self.fg_text,
            font=("Segoe UI", 14, "bold")
        ).pack(side="left", padx=15)

        self.account_label = tk.Label(
            self.topbar,
            text=self.get_account_label_text(),
            bg=self.bg_top,
            fg=self.fg_text,
            font=("Segoe UI", 10)
        )
        self.account_label.pack(side="right", padx=15)

    def get_account_label_text(self):
        if self.identity:
            return f"Logged in as {self.identity.get('email', 'Unknown')}"
        return "Not logged in"

    def update_account_label(self):
        self.account_label.config(text=self.get_account_label_text())

    # ================= SIDEBAR =================
    def create_sidebar(self):
        self.sidebar = tk.Frame(self, bg=self.bg_sidebar, width=180)
        self.sidebar.pack(fill="y", side="left")

        buttons = [
            ("Home", "Home"),
            ("Instances", "Instances"),
            ("Versions", "Versions"),
            ("Mods", "Mods"),
            ("Mail", "Mail"),
            ("Settings", "Settings"),
        ]

        for text, page_name in buttons:
            btn = tk.Button(
                self.sidebar,
                text=text,
                command=lambda n=page_name: self.show_page(n),
                bg=self.bg_sidebar,
                fg=self.fg_text,
                activebackground=self.accent,
                activeforeground="white",
                bd=0,
                font=("Segoe UI", 12),
                pady=10
            )
            btn.pack(fill="x")
            self.sidebar_buttons[page_name] = btn

    # ================= CONTENT =================
    def create_content(self):
        self.content = tk.Frame(self, bg=self.bg_dark)
        self.content.pack(fill="both", expand=True, side="right")

    # ================= PAGES =================
    def load_pages(self):
        self.pages["Home"] = HomePage(self.content, self)
        self.pages["Instances"] = InstancesPage(self.content, self)
        self.pages["Versions"] = VersionsPage(self.content, self)
        self.pages["Mods"] = ModsPage(self.content, self)
        self.pages["Mail"] = MailPage(self.content, self)
        self.pages["Settings"] = SettingsPage(self.content, self)

    def show_page(self, name):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)

    # ================= ACCOUNT =================
    def open_signup_window(self):
        win = tk.Toplevel(self)
        win.title("Sign Up / Log In")
        win.geometry("320x260")
        win.configure(bg=self.bg_dark)

        tk.Label(win, text="Email:", bg=self.bg_dark, fg=self.fg_text).pack(pady=5)
        email_entry = tk.Entry(win)
        email_entry.pack()

        tk.Label(win, text="Password:", bg=self.bg_dark, fg=self.fg_text).pack(pady=5)
        password_entry = tk.Entry(win, show="*")
        password_entry.pack()

        def submit():
            email = email_entry.get().strip()
            pwd = password_entry.get().strip()
            if not email or not pwd:
                messagebox.showerror("Error", "Please enter email and password.")
                return

            self.identity = save_identity(email)
            add_mail(
                "system",
                "Account Created",
                "Your LeModCraft account has been created on this device."
            )
            self.update_account_label()
            messagebox.showinfo("Success", "Account created and logged in.")
            win.destroy()

        tk.Button(
            win,
            text="Submit",
            command=submit,
            bg=self.bg_sidebar,
            fg=self.fg_text
        ).pack(pady=20)


# =========================================================
#  BASE PAGE
# =========================================================
class BasePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=app.bg_dark)
        self.app = app

    def apply_theme(self):
        self.configure(bg=self.app.bg_dark)
        for w in self.winfo_children():
            try:
                if isinstance(w, tk.Label):
                    w.configure(bg=self.app.bg_dark, fg=self.app.fg_text)
                elif isinstance(w, tk.Button):
                    w.configure(
                        bg=self.app.bg_sidebar,
                        fg=self.app.fg_text,
                        activebackground=self.app.accent,
                        activeforeground="white"
                    )
                elif isinstance(w, tk.Listbox):
                    w.configure(
                        bg=self.app.bg_sidebar,
                        fg=self.app.fg_text
                    )
            except:
                pass


# =========================================================
#  PAGES
# =========================================================
class HomePage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        tk.Label(self, text="Home", font=("Segoe UI", 20)).pack(pady=20)
        tk.Label(self, text="Welcome to LeModCraft Launcher.").pack(pady=5)


class InstancesPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        tk.Label(self, text="Instances", font=("Segoe UI", 20)).pack(pady=20)
        tk.Label(self, text="Instance management will go here.").pack(pady=5)


class VersionsPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        tk.Label(self, text="Versions", font=("Segoe UI", 20)).pack(pady=20)
        tk.Label(self, text="Version management will go here.").pack(pady=5)


class ModsPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        tk.Label(self, text="Mods", font=("Segoe UI", 20)).pack(pady=20)
        tk.Label(self, text="Mod browser / uploader will go here.").pack(pady=5)

        tk.Label(
            self,
            text="Posting mods requires an account.",
            font=("Segoe UI", 10)
        ).pack(pady=10)

        tk.Button(
            self,
            text="Post New Mod",
            command=self.post_mod
        ).pack(pady=5)

    def post_mod(self):
        if not self.app.identity:
            messagebox.showwarning(
                "Account Required",
                "You must create an account on this device to post mods."
            )
            return

        add_mail(
            "system",
            "Mod Submitted",
            "Your mod has been submitted for review."
        )
        messagebox.showinfo("Submitted", "Your mod has been submitted (placeholder).")


class MailPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)

        tk.Label(self, text="Mail", font=("Segoe UI", 20)).pack(pady=20)

        self.listbox = tk.Listbox(
            self,
            bg=self.app.bg_sidebar,
            fg=self.app.fg_text,
            font=("Segoe UI", 11),
            height=15
        )
        self.listbox.pack(fill="both", expand=True, padx=20, pady=10)

        btn_row = tk.Frame(self, bg=self.app.bg_dark)
        btn_row.pack(pady=5)

        tk.Button(
            btn_row,
            text="Refresh",
            command=self.load_mail
        ).pack(side="left", padx=5)

        tk.Button(
            btn_row,
            text="View",
            command=self.view_selected
        ).pack(side="left", padx=5)

        tk.Button(
            btn_row,
            text="Mark All Read",
            command=self.mark_all_read
        ).pack(side="left", padx=5)

        self.load_mail()

    def load_mail(self):
        self.listbox.delete(0, tk.END)
        self.mail_data = load_mail()
        for i, msg in enumerate(reversed(self.mail_data)):
            prefix = "[UNREAD] " if not msg.get("read", False) else ""
            self.listbox.insert(
                tk.END,
                f"{prefix}{msg.get('title', 'No title')} - {msg.get('time', '')}"
            )

    def view_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        index_from_end = sel[0]
        real_index = len(self.mail_data) - 1 - index_from_end
        msg = self.mail_data[real_index]

        win = tk.Toplevel(self)
        win.title(msg.get("title", "Message"))
        win.geometry("400x300")
        win.configure(bg=self.app.bg_dark)

        tk.Label(
            win,
            text=msg.get("title", "Message"),
            font=("Segoe UI", 14, "bold"),
            bg=self.app.bg_dark,
            fg=self.app.fg_text
        ).pack(pady=10)

        text = tk.Text(
            win,
            bg=self.app.bg_sidebar,
            fg=self.app.fg_text,
            wrap="word"
        )
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("1.0", msg.get("message", ""))
        text.config(state="disabled")

        msg["read"] = True
        save_mail(self.mail_data)
        self.load_mail()

    def mark_all_read(self):
        for msg in self.mail_data:
            msg["read"] = True
        save_mail(self.mail_data)
        self.load_mail()


class SettingsPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)

        tk.Label(self, text="Settings", font=("Segoe UI", 20)).pack(pady=20)

        # THEME
        tk.Label(self, text="Theme:", font=("Segoe UI", 14)).pack(pady=(10, 5))

        theme_var = tk.StringVar(value=app.current_theme)

        def change_theme():
            app.current_theme = theme_var.get()
            app.apply_theme()

        for theme in ["dark", "light", "hacker"]:
            tk.Radiobutton(
                self,
                text=theme.capitalize(),
                variable=theme_var,
                value=theme,
                command=change_theme,
                bg=self.app.bg_dark,
                fg=self.app.fg_text,
                selectcolor=self.app.bg_sidebar,
                font=("Segoe UI", 12)
            ).pack(anchor="w", padx=40)

        # ACCOUNT
        tk.Label(self, text="Account", font=("Segoe UI", 16)).pack(pady=(30, 10))

        self.status_label = tk.Label(
            self,
            text=self.get_status_text(),
            font=("Segoe UI", 11)
        )
        self.status_label.pack(pady=5)

        tk.Button(
            self,
            text="Sign Up / Log In",
            command=self.open_signup
        ).pack(pady=10)

        tk.Label(
            self,
            text="Posting mods requires an account on this device.",
            font=("Segoe UI", 9)
        ).pack(pady=5)

    def get_status_text(self):
        if self.app.identity:
            return f"Logged in as {self.app.identity.get('email', 'Unknown')}"
        return "Not logged in"

    def open_signup(self):
        self.app.open_signup_window()
        self.status_label.config(text=self.get_status_text())


# =========================================================
#  RUN
# =========================================================
if __name__ == "__main__":
    app = LeModCraftApp()
    app.mainloop()
