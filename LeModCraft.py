import tkinter as tk
from tkinter import messagebox
import os, json, socket, subprocess, re, sys, ctypes, time

# =========================================================
#  CTRL DEBUG MODE (Baldi-style)
# =========================================================

# Detect CTRL key
def ctrl_held():
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)

# Launch EXE in MAXIMUM POWER debug mode
def run_debug_mode():
    exe_path = sys.executable
    exe_dir = os.path.dirname(exe_path)

    # PyInstaller debug flags:
    #   --debug=all         → everything
    #   --debug=imports     → every import attempt
    #   --debug=bootloader  → C-level bootloader logs
    #   --debug=noarchive   → unpacked loading (extra verbose)
    debug_flags = [
        "--debug=all",
        "--debug=imports",
        "--debug=bootloader"
    ]

    cmd_line = exe_path

    # Open CMD in the EXE folder and run the EXE with full debug
    subprocess.Popen(
        ["cmd", "/k", cmd_line],
        cwd=exe_dir
    )

    sys.exit()

# Trigger debug mode ONLY when frozen AND CTRL is held
if getattr(sys, "frozen", False) and ctrl_held():
    run_debug_mode()

# =========================================================
#  PLATFORM / PATHS / OTHERES
# =========================================================

from recources.Versions import view_edit
from recources.homepage import homepage

WINDOWS = sys.platform.startswith("win")

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(__file__)

DATA_DIR = os.path.join(BASE, "data")
MAIL_DIR = os.path.join(BASE, "mail")
RECOURCES_DIR = os.path.join(BASE, "recources")

SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
OUTBOX_FILE = os.path.join(DATA_DIR, "outbox.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MAIL_DIR, exist_ok=True)
os.makedirs(RECOURCES_DIR, exist_ok=True)

# =========================================================
#  WIN32: EMBED EXE WINDOW INTO TKINTER FRAME
# =========================================================

if WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int)
    )
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    SetParent = user32.SetParent
    MoveWindow = user32.MoveWindow
    IsWindowVisible = user32.IsWindowVisible

    def _find_window_for_pid(pid, timeout=5.0):
        start = time.time()
        hwnd_found = None

        def callback(hwnd, lParam):
            nonlocal hwnd_found
            if not IsWindowVisible(hwnd):
                return True
            pid_buf = ctypes.c_ulong()
            GetWindowThreadProcessId(hwnd, ctypes.byref(pid_buf))
            if pid_buf.value == pid:
                hwnd_found = hwnd
                return False
            return True

        while time.time() - start < timeout and hwnd_found is None:
            EnumWindows(EnumWindowsProc(callback), 0)
            if hwnd_found:
                break
            time.sleep(0.1)

        return hwnd_found

    def embed_exe_into_frame(exe_path, frame):
        try:
            p = subprocess.Popen([exe_path])
        except Exception as e:
            print(f"Failed to start EXE {exe_path}: {e}")
            return None

        hwnd = _find_window_for_pid(p.pid)
        if not hwnd:
            print(f"Could not find window for EXE {exe_path}")
            return None

        SetParent(hwnd, frame.winfo_id())

        def resize(event=None):
            MoveWindow(hwnd, 0, 0, frame.winfo_width(), frame.winfo_height(), True)

        frame.bind("<Configure>", resize)
        return hwnd
else:
    def embed_exe_into_frame(exe_path, frame):
        print("EXE embedding only supported on Windows.")
        return None

# =========================================================
#  SIMPLE SETTINGS / ACCOUNTS / MAIL
# =========================================================

def get_wifi_ip():
    try:
        output = subprocess.check_output("ipconfig", shell=True).decode(errors="ignore")
        match = re.search(r"IPv4 Address[^\:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", output)
        return match.group(1) if match else "127.0.0.1"
    except:
        return "127.0.0.1"

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {
            "theme": "dark",
            "account": {"logged_in": False, "username": "", "email": ""},
            "mail_server_ip": get_wifi_ip()
        }
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "theme": "dark",
            "account": {"logged_in": False, "username": "", "email": ""},
            "mail_server_ip": get_wifi_ip()
        }

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

settings = load_settings()

def load_accounts():
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=4)

def signup(email, password):
    accounts = load_accounts()
    if email in accounts:
        return False, "Account already exists."
    accounts[email] = {
        "password": password,
        "device": socket.gethostname(),
        "ip": socket.gethostbyname(socket.gethostname())
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

def load_mail():
    mails = []
    for file in os.listdir(MAIL_DIR):
        if file.endswith(".txt"):
            with open(os.path.join(MAIL_DIR, file), "r", encoding="utf-8") as f:
                mails.append((file[:-4], f.read()))
    return mails

def apply_theme(theme):
    global BG, FG, CARD, ACCENT
    if theme == "light":
        BG, FG, CARD, ACCENT = "#ffffff", "#000000", "#f0f0f0", "#3a86ff"
    elif theme == "hacker":
        BG, FG, CARD, ACCENT = "#000000", "#00ff00", "#001100", "#00ff00"
    else:
        BG, FG, CARD, ACCENT = "#1e1e1e", "#ffffff", "#2b2b2b", "#3a86ff"

apply_theme(settings["theme"])

# =========================================================
#  LAUNCHER UI
# =========================================================

class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LeModCraft Launcher")
        self.geometry("900x600")
        self.configure(bg=BG)

        # Sidebar + main page frame
        self.sidebar = tk.Frame(self, width=200, bg=CARD)
        self.sidebar.pack(side="left", fill="y")

        self.page_frame = tk.Frame(self, bg=BG)
        self.page_frame.pack(side="right", fill="both", expand=True)

        # Build UI
        self.pages = {}
        self.build_sidebar()
        self.build_pages()

        # AUTO‑LOGIN FIX (Minecraft account)
        homepage.auto_login_if_exists(self)

        # Show homepage
        self.show_page("Home")

    # -----------------------------------------------------
    # Sidebar buttons
    # -----------------------------------------------------
    def build_sidebar(self):
        for name in ["Home", "Versions", "Mail", "Settings"]:
            tk.Button(
                self.sidebar,
                text=name,
                bg=CARD,
                fg=FG,
                font=("Arial", 14),
                relief="flat",
                command=lambda n=name: self.show_page(n)
            ).pack(fill="x", pady=5)

    # -----------------------------------------------------
    # Page registry
    # -----------------------------------------------------
    def build_pages(self):
        self.pages["Home"] = lambda: self.build_home_page()
        self.pages["Versions"] = lambda: self.build_versions_page()
        self.pages["Mail"] = lambda: self.build_mail_page()
        self.pages["Settings"] = lambda: self.build_settings_page()

    # -----------------------------------------------------
    # Page switching
    # -----------------------------------------------------
    def show_page(self, name):
        for w in self.page_frame.winfo_children():
            w.destroy()
        page = self.pages[name]()
        page.pack(fill="both", expand=True)

    # -----------------------------------------------------
    # HOME PAGE (AUTO‑LOGIN + MODPACKS)
    # -----------------------------------------------------
    def build_home_page(self):
        # auto_login_if_exists() already validated the saved Minecraft token.
        return homepage.build_home_page(self, BG, FG, CARD, ACCENT)

    # -----------------------------------------------------
    # VERSIONS PAGE
    # -----------------------------------------------------
    def build_versions_page(self):
        return view_edit.create_Versions_tab(self.page_frame)

    # -----------------------------------------------------
    # MAIL PAGE
    # -----------------------------------------------------
    def build_mail_page(self):
        frame = tk.Frame(self.page_frame, bg=BG)
        tk.Label(frame, text="Mail", font=("Arial", 24), bg=BG, fg=FG).pack(pady=20)

        tk.Button(frame, text="New Mail", bg=ACCENT, fg="white",
                  command=lambda: open_mail_editor(self)).pack(pady=10)

        self.mail_list = tk.Frame(frame, bg=BG)
        self.mail_list.pack(fill="both", expand=True)

        self.refresh_mail()
        return frame

    def refresh_mail(self):
        for w in self.mail_list.winfo_children():
            w.destroy()

        if not settings["account"]["logged_in"]:
            tk.Label(self.mail_list, text="Log in to view mail.", bg=BG, fg=FG).pack()
            return

        mails = load_mail()
        if not mails:
            tk.Label(self.mail_list, text="No mail.", bg=BG, fg=FG).pack()
            return

        for subject, body in mails:
            item = tk.Frame(self.mail_list, bg=CARD)
            item.pack(fill="x", pady=5)
            tk.Label(item, text=subject, font=("Arial", 16), bg=CARD, fg=FG).pack(anchor="w")
            tk.Label(item, text=body, bg=CARD, fg=FG, wraplength=600, justify="left").pack(anchor="w")

    # -----------------------------------------------------
    # SETTINGS PAGE
    # -----------------------------------------------------
    def build_settings_page(self):
        frame = tk.Frame(self.page_frame, bg=BG)

        tk.Label(frame, text="Theme", font=("Arial", 20), bg=BG, fg=FG).pack(anchor="w", padx=20, pady=10)
        theme_var = tk.StringVar(value=settings["theme"])

        def save_theme():
            settings["theme"] = theme_var.get()
            save_settings()
            apply_theme(settings["theme"])
            self.configure(bg=BG)
            self.sidebar.configure(bg=CARD)
            self.page_frame.configure(bg=BG)

        for t in ["dark", "light", "hacker"]:
            tk.Radiobutton(frame, text=t, variable=theme_var, value=t,
                           bg=BG, fg=FG, selectcolor=BG,
                           command=save_theme).pack(anchor="w", padx=20)

        tk.Label(frame, text="Account", font=("Arial", 20), bg=BG, fg=FG).pack(anchor="w", padx=20, pady=10)

        self.acc_label = tk.Label(frame, text="", bg=BG, fg=FG)
        self.acc_label.pack(anchor="w", padx=20)

        self.acc_button = tk.Button(frame, text="", bg=ACCENT, fg="white")
        self.acc_button.pack(anchor="w", padx=20, pady=5)

        update_account_ui(self)

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

        safe = re.sub(r'[<>:"/\\|?*]', "_", subject)
        with open(os.path.join(MAIL_DIR, safe + ".txt"), "w", encoding="utf-8") as f:
            f.write(body)

        win.destroy()
        app.refresh_mail()

    tk.Button(win, text="Save", bg=ACCENT, fg="white", command=save_mail).pack(pady=10)

# =========================================================
#  ACCOUNT UI
# =========================================================

def update_account_ui(app):
    acc = settings["account"]
    if acc["logged_in"]:
        app.acc_label.config(text=f"Logged in as: {acc['username']}")
        app.acc_button.config(text="Log Out", command=lambda: logout(app))
    else:
        app.acc_label.config(text="Not logged in")
        app.acc_button.config(text="Sign Up / Log In", command=lambda: open_login_window(app))

def logout(app):
    settings["account"] = {"logged_in": False, "username": "", "email": ""}
    save_settings()
    update_account_ui(app)
    app.refresh_mail()

def open_login_window(app):
    win = tk.Toplevel(app)
    win.title("Login")
    win.geometry("350x300")
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

# =========================================================
#  RUN
# =========================================================

if __name__ == "__main__":
    app = Launcher()
    app.mainloop()
