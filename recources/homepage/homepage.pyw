import os
import json
import base64
import binascii
import time
import threading
import requests
import urllib.parse
import tkinter as tk
import webbrowser
import subprocess

# ---------------------------------------------------------
# BASE PATH + DATA
# ---------------------------------------------------------

def get_base_path():
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.dirname(os.path.dirname(here))

BASE = get_base_path()
DATA_DIR = os.path.join(BASE, "data")
ACCOUNT_FILE = os.path.join(DATA_DIR, "Account.json")
MODPACK_DIR = os.path.join(BASE, "Modpacks")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODPACK_DIR, exist_ok=True)

# ---------------------------------------------------------
# GLOBAL LOGIN STATE
# ---------------------------------------------------------

SIGNED_IN = False
USER_NAME = None
USER_UUID = None
USER_TOKEN = None

# ---------------------------------------------------------
# ACCOUNT STORAGE
# ---------------------------------------------------------

def load_accounts():
    if not os.path.exists(ACCOUNT_FILE):
        with open(ACCOUNT_FILE, "w") as f:
            json.dump({"accounts": []}, f)
        return {"accounts": []}

    with open(ACCOUNT_FILE, "r") as f:
        return json.load(f)


def save_accounts(data):
    with open(ACCOUNT_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------------------------------------------------------
# AUTO LOGIN ON STARTUP
# ---------------------------------------------------------

def token_is_valid(token):
    """Check the local JWT expiry before attempting an automatic login."""
    if not isinstance(token, str) or not token:
        return False

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(
            base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        )
        expires_at = int(claims.get("exp", 0))
        return expires_at > int(time.time()) + 60
    except (
        IndexError,
        ValueError,
        TypeError,
        UnicodeDecodeError,
        binascii.Error,
    ):
        return False


def auto_login_if_exists(app):
    global SIGNED_IN, USER_NAME, USER_UUID, USER_TOKEN

    data = load_accounts()

    if len(data["accounts"]) == 0:
        SIGNED_IN = False
        return

    acc = data["accounts"][0]

    if not token_is_valid(acc.get("token")):
        SIGNED_IN = False
        USER_NAME = None
        USER_UUID = None
        USER_TOKEN = None
        print("[AUTO LOGIN] Saved Minecraft token expired; login required.")
        return

    USER_NAME = acc["username"]
    USER_UUID = acc["uuid"]
    USER_TOKEN = acc["token"]
    SIGNED_IN = True

    print(f"[AUTO LOGIN] Logged in automatically as {USER_NAME}")

# ---------------------------------------------------------
# MICROSOFT LOGIN (BROWSER + PASTE URL/CODE)
# ---------------------------------------------------------

def start_ms_login(app):
    CLIENT_ID = "00000000402b5328"
    REDIRECT_URI = "https://login.live.com/oauth20_desktop.srf"
    SCOPE = "XboxLive.signin offline_access"

    auth_url = (
        "https://login.live.com/oauth20_authorize.srf?"
        f"client_id={CLIENT_ID}&"
        f"response_type=code&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"scope={urllib.parse.quote(SCOPE)}"
    )

    webbrowser.open(auth_url)

    win = tk.Toplevel(app)
    win.title("Microsoft Login")
    win.geometry("520x200")
    win.configure(bg="#222222")

    tk.Label(
        win,
        text="After signing in, copy the URL immediately\nbefore it changes, and paste it here:",
        bg="#222222",
        fg="white",
        font=("Arial", 10),
        justify="center"
    ).pack(pady=10)

    entry = tk.Entry(win, width=65)
    entry.pack(pady=5)

    def submit():
        text = entry.get().strip()
        if not text:
            return

        if "http" in text:
            parsed = urllib.parse.urlparse(text)
            q = urllib.parse.parse_qs(parsed.query)
            if "code" in q:
                auth_code = q["code"][0]
            else:
                print("[LOGIN ERROR] No ?code= in URL.")
                return
        else:
            auth_code = text

        win.destroy()
        threading.Thread(target=lambda: finish_ms_login(app, auth_code), daemon=True).start()

    tk.Button(
        win,
        text="Continue",
        bg="#0077ff",
        fg="white",
        font=("Arial", 11, "bold"),
        command=submit
    ).pack(pady=10)

# ---------------------------------------------------------
# TOKEN EXCHANGE
# ---------------------------------------------------------

def finish_ms_login(app, auth_code):
    CLIENT_ID = "00000000402b5328"
    REDIRECT_URI = "https://login.live.com/oauth20_desktop.srf"

    token_resp = requests.post(
        "https://login.live.com/oauth20_token.srf",
        data={
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code": auth_code,
            "grant_type": "authorization_code"
        }
    ).json()

    if "access_token" not in token_resp:
        print("[LOGIN ERROR]", token_resp)
        return

    ms_access_token = token_resp["access_token"]

    xbl_resp = requests.post(
        "https://user.auth.xboxlive.com/user/authenticate",
        json={
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={ms_access_token}"
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
    ).json()

    if "Token" not in xbl_resp:
        print("[LOGIN ERROR]", xbl_resp)
        return

    xbl_token = xbl_resp["Token"]
    user_hash = xbl_resp["DisplayClaims"]["xui"][0]["uhs"]

    xsts_resp = requests.post(
        "https://xsts.auth.xboxlive.com/xsts/authorize",
        json={
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [xbl_token]
            },
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType": "JWT"
        }
    ).json()

    if "Token" not in xsts_resp:
        print("[LOGIN ERROR]", xsts_resp)
        return

    xsts_token = xsts_resp["Token"]

    identity_token = f"XBL3.0 x={user_hash};{xsts_token}"

    mc_resp = requests.post(
        "https://api.minecraftservices.com/authentication/login_with_xbox",
        json={"identityToken": identity_token}
    ).json()

    if "access_token" not in mc_resp:
        print("[LOGIN ERROR]", mc_resp)
        return

    mc_access_token = mc_resp["access_token"]

    profile = requests.get(
        "https://api.minecraftservices.com/minecraft/profile",
        headers={"Authorization": f"Bearer {mc_access_token}"}
    ).json()

    if "id" not in profile:
        print("[LOGIN ERROR]", profile)
        return

    uuid = profile["id"]
    username = profile["name"]

    data = load_accounts()
    found = False
    for acc in data["accounts"]:
        if acc["username"] == username:
            acc["uuid"] = uuid
            acc["token"] = mc_access_token
            found = True

    if not found:
        data["accounts"].append({
            "username": username,
            "password": None,
            "uuid": uuid,
            "token": mc_access_token
        })

    save_accounts(data)

    global SIGNED_IN, USER_NAME, USER_UUID, USER_TOKEN
    SIGNED_IN = True
    USER_NAME = username
    USER_UUID = uuid
    USER_TOKEN = mc_access_token

    rebuild_homepage_ui(app)

# ---------------------------------------------------------
# MODPACK SCAN
# ---------------------------------------------------------

def load_modpacks():
    packs = []
    for folder in os.listdir(MODPACK_DIR):
        full = os.path.join(MODPACK_DIR, folder)
        if os.path.isdir(full):
            packs.append({
                "id": folder,
                "name": folder,
                "path": full
            })
    return packs

# ---------------------------------------------------------
# ENGINE LAUNCH
# ---------------------------------------------------------
def launch_modpack(app, pack):
    engine_dir = os.path.join(BASE, "recources", "Engine")
    phaser_base = os.path.join(engine_dir, "custom_phaser")

    modpack_path = pack["path"]   # THIS IS THE FIX

    # Try .exe
    exe = phaser_base + ".exe"
    if os.path.exists(exe):
        os.startfile(exe)
        return

    # Try .pyw
    pyw = phaser_base + ".pyw"
    if os.path.exists(pyw):
        subprocess.Popen(["python", pyw, modpack_path])
        return

    # Try .py
    py = phaser_base + ".py"
    if os.path.exists(py):
        subprocess.Popen(["python", py, modpack_path])
        return

    print("custom_phaser not found!")

# ---------------------------------------------------------
# HOMEPAGE UI
# ---------------------------------------------------------

def build_home_page(app, BG, FG, CARD, ACCENT):
    frame = tk.Frame(app.page_frame, bg=BG)

    tk.Label(
        frame,
        text="Modpacks",
        font=("Arial", 28, "bold"),
        bg=BG,
        fg=FG
    ).pack(pady=20)

    if not SIGNED_IN:
        tk.Button(
            frame,
            text="Login with Microsoft",
            bg=ACCENT,
            fg="white",
            font=("Arial", 14, "bold"),
            command=lambda: start_ms_login(app)
        ).pack(pady=10)
        return frame

    tk.Label(
        frame,
        text=f"Signed in as {USER_NAME}",
        bg=BG,
        fg=FG,
        font=("Arial", 16, "bold")
    ).pack(pady=10)

    packs = load_modpacks()

    if not packs:
        tk.Label(
            frame,
            text="No modpacks found.",
            bg=BG,
            fg=FG,
            font=("Arial", 14)
        ).pack(pady=20)
        return frame

    for pack in packs:
        card = tk.Frame(frame, bg=CARD)
        card.pack(fill="x", padx=20, pady=10)

        tk.Label(card, text=pack["name"], font=("Arial", 18, "bold"), bg=CARD, fg=FG).pack(anchor="w")

        tk.Button(
            card,
            text="Play",
            bg=ACCENT,
            fg="white",
            font=("Arial", 12, "bold"),
            command=lambda p=pack: launch_modpack(app, p)
        ).pack(anchor="e", pady=5)

    return frame

# ---------------------------------------------------------
# HOMEPAGE REBUILD
# ---------------------------------------------------------

def rebuild_homepage_ui(app):
    for widget in app.page_frame.winfo_children():
        widget.destroy()
    build_home_page(app, "#222222", "white", "#333333", "#0077ff")
