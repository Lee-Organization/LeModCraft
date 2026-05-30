import tkinter as tk
from tkinter import messagebox
import os, json, socket, subprocess, re, shutil

# =========================================================
#  PATHS
# =========================================================

BASE = os.path.abspath(os.path.dirname(__file__))

DATA_DIR = os.path.join(BASE, "data")
MAIL_DIR = os.path.join(BASE, "mail")

SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
OUTBOX_FILE = os.path.join(DATA_DIR, "outbox.json")

# Ensure folders exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MAIL_DIR, exist_ok=True)

# =========================================================
#  AUTO-DETECT WIFI IP
# =========================================================

def get_wifi_ip():
    try:
        output = subprocess.check_output("ipconfig", shell=True).decode(errors="ignore")
        sections = output.split("\r\n\r\n")

        for sec in sections:
            if ("Wireless LAN adapter" in sec) or ("Wi-Fi" in sec) or ("WLAN" in sec):
                match = re.search(r"IPv4 Address[^\:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", sec)
                if match:
                    return match.group(1)

        return "127.0.0.1"
    except:
        return "127.0.0.1"

# =========================================================
#  SETTINGS
# =========================================================

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {
            "theme": "dark",
            "account": {
                "logged_in": False,
                "username": "",
                "email": ""
            },
            "mail_server_ip": get_wifi_ip()
        }

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if data == "":
                raise Exception("Empty settings")

            settings = json.loads(data)

        if "mail_server_ip" not in settings:
            settings["mail_server_ip"] = get_wifi_ip()

        return settings

    except:
        defaults = {
            "theme": "dark",
            "account": {
                "logged_in": False,
                "username": "",
                "email": ""
            },
            "mail_server_ip": get_wifi_ip()
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(defaults, f, indent=4)
        return defaults

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

settings = load_settings()

# =========================================================
#  ACCOUNTS.JSON SYSTEM
# =========================================================

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return {}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if data == "":
                return {}
            return json.loads(data)
    except:
        return {}

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=4)

def signup(email, password):
    accounts = load_accounts()

    if email in accounts:
        return False, "Account already exists."

    device = socket.gethostname()
    ip = socket.gethostbyname(socket.gethostname())

    accounts[email] = {
        "password": password,
        "device": device,
        "ip": ip
    }

    save_accounts(accounts)
    return True, "Account created."

def login(email, password):
    accounts = load_accounts()

    if email not in accounts:
        return False, "Account does not exist."

    acc = accounts[email]

    if acc["password"] != password:
        return False, "Incorrect password."

    if acc["device"] != socket.gethostname():
        return False, "Device mismatch."

    if acc["ip"] != socket.gethostbyname(socket.gethostname()):
        return False, "IP mismatch."

    return True, "Login successful."

def delete_account(email):
    accounts = load_accounts()

    if email not in accounts:
        return False, "Account does not exist."

    del accounts[email]
    save_accounts(accounts)
    return True, "Account deleted."

# =========================================================
#  OUTBOX
# =========================================================

def load_outbox():
    if not os.path.exists(OUTBOX_FILE):
        return []
    with open(OUTBOX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_outbox(data):
    with open(OUTBOX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# =========================================================
#  MAIL
# =========================================================

def load_mail():
    mails = []
    for file in os.listdir(MAIL_DIR):
        path = os.path.join(MAIL_DIR, file)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                mails.append((os.path.splitext(file)[0], f.read()))
    return mails

# =========================================================
#  THEME
# =========================================================

def apply_theme(theme):
    global BG, FG, CARD, ACCENT

    if theme == "light":
        BG = "#ffffff"
        FG = "#000000"
        CARD = "#f0f0f0"
        ACCENT = "#3a86ff"
    elif theme == "hacker":
        BG = "#000000"
        FG = "#00ff00"
        CARD = "#001100"
        ACCENT = "#00ff00"
    else:
        BG = "#1e1e1e"
        FG = "#ffffff"
        CARD = "#2b2b2b"
        ACCENT = "#3a86ff"

apply_theme(settings["theme"])

# =========================================================
#  UI
# =========================================================

class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LeModCraft Launcher")
        self.geometry("900x600")
        self.configure(bg=BG)

        self.sidebar = tk.Frame(self, width=200, bg=CARD)
        self.sidebar.pack(side="left", fill="y")

        self.page_frame = tk.Frame(self, bg=BG)
        self.page_frame.pack(side="right", fill="both", expand=True)

        self.pages = {}

        self.build_sidebar()
        self.build_pages()
        self.show_page("Home")

    def build_sidebar(self):
        buttons = [
            ("Home", lambda: self.show_page("Home")),
            ("Instances", lambda: self.show_page("Instances")),
            ("Versions", lambda: self.show_page("Versions")),
            ("Mods", lambda: self.show_page("Mods")),
            ("Mail", lambda: self.show_page("Mail")),
            ("Settings", lambda: self.show_page("Settings")),
        ]

        for text, cmd in buttons:
            tk.Button(
                self.sidebar,
                text=text,
                bg=CARD,
                fg=FG,
                font=("Arial", 14),
                relief="flat",
                command=cmd
            ).pack(fill="x", pady=5)

    def build_pages(self):
        self.pages["Home"] = self.make_page("Home Page")
        self.pages["Instances"] = self.make_page("Instances Page")
        self.pages["Versions"] = self.make_page("Versions Page")
        self.pages["Mods"] = self.make_page("Mods Page")
        self.pages["Mail"] = self.build_mail_page()
        self.pages["Settings"] = self.build_settings_page()

    def make_page(self, text):
        frame = tk.Frame(self.page_frame, bg=BG)
        tk.Label(frame, text=text, font=("Arial", 24), bg=BG, fg=FG).pack(pady=20)
        return frame

    def show_page(self, name):
        if name == "Settings":
            self.pages["Settings"] = self.build_settings_page()
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)

    # ---------------- MAIL PAGE ----------------
    def build_mail_page(self):
        frame = tk.Frame(self.page_frame, bg=BG)

        tk.Label(frame, text="Mail", font=("Arial", 24, "bold"), bg=BG, fg=FG).pack(pady=20)

        tk.Button(
            frame,
            text="New Mail",
            bg=ACCENT,
            fg="white",
            command=lambda: open_mail_editor(self)
        ).pack(pady=10)

        self.mail_list = tk.Frame(frame, bg=BG)
        self.mail_list.pack(fill="both", expand=True, padx=20, pady=10)

        self.refresh_mail()

        return frame

    def refresh_mail(self):
        for widget in self.mail_list.winfo_children():
            widget.destroy()

        if not settings["account"]["logged_in"]:
            tk.Label(self.mail_list, text="Log in to view mail.", bg=BG, fg=FG).pack()
            return

        mails = load_mail()

        if not mails:
            tk.Label(self.mail_list, text="No mail.", bg=BG, fg=FG).pack()
            return

        for subject, body in mails:
            item = tk.Frame(self.mail_list, bg=CARD, pady=10, padx=10)
            item.pack(fill="x", pady=5)

            tk.Label(item, text=subject, font=("Arial", 16, "bold"), bg=CARD, fg=FG).pack(anchor="w")
            tk.Label(item, text=body, font=("Arial", 12), bg=CARD, fg=FG, wraplength=600, justify="left").pack(anchor="w")

    # ---------------- SETTINGS PAGE ----------------
    def build_settings_page(self):
        frame = tk.Frame(self.page_frame, bg=BG)

        # THEME
        theme_frame = tk.Frame(frame, bg=BG)
        theme_frame.pack(anchor="w", padx=20, pady=20)

        tk.Label(theme_frame, text="Theme", font=("Arial", 18, "bold"), bg=BG, fg=FG).pack(anchor="w")

        theme_var = tk.StringVar(value=settings["theme"])

        def save_theme():
            settings["theme"] = theme_var.get()
            save_settings()
            apply_theme(settings["theme"])
            apply_theme_live(self)

        for t in ["dark", "light", "hacker"]:
            tk.Radiobutton(
                theme_frame,
                text=t.capitalize(),
                variable=theme_var,
                value=t,
                bg=BG,
                fg=FG,
                selectcolor=BG,
                command=save_theme
            ).pack(anchor="w")

        # ACCOUNT
        account_frame = tk.Frame(frame, bg=BG)
        account_frame.pack(anchor="w", padx=20, pady=20)

        tk.Label(account_frame, text="Account", font=("Arial", 18, "bold"), bg=BG, fg=FG).pack(anchor="w")

        self.account_label = tk.Label(account_frame, text="", bg=BG, fg=FG, font=("Arial", 14))
        self.account_label.pack(anchor="w", pady=5)

        self.account_button = tk.Button(account_frame, text="", font=("Arial", 14), bg=ACCENT, fg="white")
        self.account_button.pack(anchor="w", pady=5)

        update_account_ui(self)

        # DANGER ZONE
        danger_frame = tk.Frame(frame, bg=BG)
        danger_frame.pack(fill="x", padx=20, pady=40)

        tk.Label(
            danger_frame,
            text="Danger Zone",
            font=("Arial", 18, "bold"),
            fg="#ff5555",
            bg=BG
        ).pack(anchor="w", pady=(0, 10))

        tk.Button(
            danger_frame,
            text="Delete Account",
            font=("Arial", 14),
            bg="#ff4444",
            fg="white",
            activebackground="#cc0000",
            command=lambda: try_delete_account(self)
        ).pack(anchor="w")

        return frame

# =========================================================
#  MAIL EDITOR
# =========================================================

def open_mail_editor(app):
    if not settings["account"]["logged_in"]:
        messagebox.showerror("Error", "Log in first.")
        return

    win = tk.Toplevel(app)
    win.title("New Mail")
    win.geometry("400x400")
    win.configure(bg=BG)

    tk.Label(win, text="Subject:", bg=BG, fg=FG).pack(anchor="w", padx=20)
    subject_entry = tk.Entry(win, width=40)
    subject_entry.pack(padx=20, pady=5)

    tk.Label(win, text="Message:", bg=BG, fg=FG).pack(anchor="w", padx=20)
    body_text = tk.Text(win, width=40, height=15, bg=CARD, fg=FG)
    body_text.pack(padx=20, pady=5)

    def save_mail():
        subject = subject_entry.get().strip()
        body = body_text.get("1.0", "end").strip()

        if not subject:
            messagebox.showerror("Error", "Subject required.")
            return

        # Save locally
        mail_path = os.path.join(MAIL_DIR, subject + ".txt")
        with open(mail_path, "w", encoding="utf-8") as f:
            f.write(body)

        # TCP SEND
        target_ip = settings.get("mail_server_ip", get_wifi_ip())

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_ip, 50505))
                payload = f"{subject}|{body}"
                s.sendall(payload.encode("utf-8"))
                s.recv(1024)
        except:
            out = load_outbox()
            out.append({
                "ip": target_ip,
                "subject": subject,
                "body": body
            })
            save_outbox(out)

        win.destroy()
        app.refresh_mail()

    tk.Button(win, text="Save", bg=ACCENT, fg="white", command=save_mail).pack(pady=10)

# =========================================================
#  ACCOUNT UI
# =========================================================

def update_account_ui(app):
    if settings["account"]["logged_in"]:
        app.account_label.config(text=f"Logged in as: {settings['account']['username']}")
        app.account_button.config(text="Log Out", command=lambda: logout(app))
    else:
        app.account_label.config(text="Not logged in")
        app.account_button.config(text="Sign Up / Log In", command=lambda: open_login_window(app))

def logout(app):
    settings["account"] = {
        "logged_in": False,
        "username": "",
        "email": ""
    }
    save_settings()
    update_account_ui(app)
    app.refresh_mail()
    messagebox.showinfo("Logged Out", "You have been logged out.")

def try_delete_account(app):
    if not settings["account"]["logged_in"]:
        messagebox.showerror("Error", "You must be logged in to delete your account.")
        return
    open_delete_account_window(app)

# =========================================================
#  LOGIN WINDOW
# =========================================================

def open_login_window(app):
    win = tk.Toplevel(app)
    win.title("Login")
    win.geometry("350x350")
    win.configure(bg=BG)

    tk.Label(win, text="Email:", bg=BG, fg=FG).pack(anchor="w", padx=20)
    email_entry = tk.Entry(win, width=35)
    email_entry.pack(padx=20, pady=5)

    tk.Label(win, text="Password:", bg=BG, fg=FG).pack(anchor="w", padx=20)
    pass_entry = tk.Entry(win, width=35, show="*")
    pass_entry.pack(padx=20, pady=5)

    def do_login():
        ok, msg = login(email_entry.get(), pass_entry.get())

        if not ok:
            messagebox.showerror("Error", msg)
            return

        settings["account"] = {
            "logged_in": True,
            "username": email_entry.get(),
            "email": email_entry.get()
        }
        save_settings()
        update_account_ui(app)
        app.refresh_mail()
        win.destroy()

    tk.Button(win, text="Login", bg=ACCENT, fg="white", command=do_login).pack(pady=10)

    tk.Button(
        win,
        text="Create Account",
        bg=CARD,
        fg=FG,
        command=lambda: open_signup_window(app, win)
    ).pack(pady=10)

# =========================================================
#  SIGNUP WINDOW
# =========================================================

def open_signup_window(app, login_window=None):
    if login_window:
        login_window.destroy()

    win = tk.Toplevel(app)
    win.title("Create Account")
    win.geometry("350x350")
    win.configure(bg=BG)

    tk.Label(win, text="Email:", bg=BG, fg=FG).pack(anchor="w", padx=20)
    email_entry = tk.Entry(win, width=35)
    email_entry.pack(padx=20, pady=5)

    tk.Label(win, text="Password:", bg=BG, fg=FG).pack(anchor="w", padx=20)
    pass_entry = tk.Entry(win, width=35, show="*")
    pass_entry.pack(padx=20, pady=5)

    def do_signup():
        ok, msg = signup(email_entry.get(), pass_entry.get())

        if not ok:
            messagebox.showerror("Error", msg)
            return

        settings["account"] = {
            "logged_in": True,
            "username": email_entry.get(),
            "email": email_entry.get()
        }
        save_settings()
        update_account_ui(app)
        app.refresh_mail()

        messagebox.showinfo("Success", "Account created and logged in!")
        win.destroy()

    tk.Button(win, text="Sign Up", bg=ACCENT, fg="white", command=do_signup).pack(pady=20)

# =========================================================
#  DELETE ACCOUNT WINDOW
# =========================================================

def open_delete_account_window(app):
    win = tk.Toplevel(app)
    win.title("Delete Account")
    win.geometry("400x250")
    win.configure(bg=BG)

    tk.Label(win, text="Delete Your Account", font=("Arial", 18, "bold"), fg=FG, bg=BG).pack(pady=10)

    tk.Label(win, text="Email:", fg=FG, bg=BG).pack(anchor="w", padx=20)
    email_entry = tk.Entry(win, width=40)
    email_entry.pack(padx=20, pady=5)
    email_entry.insert(0, settings["account"]["email"])
    email_entry.config(state="disabled")

    tk.Label(win, text="Password:", fg=FG, bg=BG).pack(anchor="w", padx=20)
    pass_entry = tk.Entry(win, width=40, show="*")
    pass_entry.pack(padx=20, pady=5)

    tk.Button(
        win,
        text="Delete Account",
        bg="#ff4444",
        fg="white",
        command=lambda: finalize_account_deletion(app, settings["account"]["email"], pass_entry.get(), win)
    ).pack(pady=20)

def finalize_account_deletion(app, email, password, window):
    ok, msg = login(email, password)

    if not ok:
        messagebox.showerror("Error", "Password incorrect.")
        return

    delete_account(email)

    settings["account"] = {
        "logged_in": False,
        "username": "",
        "email": ""
    }
    save_settings()
    update_account_ui(app)
    app.refresh_mail()

    messagebox.showinfo("Account Deleted", "Your account has been permanently deleted.")
    window.destroy()

# =========================================================
#  RUN LAUNCHER
# =========================================================

if __name__ == "__main__":
    app = Launcher()
    app.mainloop()
