import tkinter as tk
import os
import sys
import subprocess

# ---------------------------------------------------------
# PATH HANDLING (WORKS FOR .py, .pyw, AND .exe)
# ---------------------------------------------------------

def get_base_path():
    # homepage.pyw is in: BASE/recources/homepage/
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.dirname(os.path.dirname(here))  # go up twice

BASE = get_base_path()
MODPACKS_DIR = os.path.join(BASE, "modpacks")
ENGINE_DIR = os.path.join(BASE, "Engine")

os.makedirs(MODPACKS_DIR, exist_ok=True)


# ---------------------------------------------------------
# UNIVERSAL EXECUTOR (RUN .exe / .py / .pyw)
# ---------------------------------------------------------

def run_any(path, args=None):
    args = args or []
    path = os.path.normpath(path)

    if path.endswith(".exe"):
        subprocess.Popen([path] + args)

    elif path.endswith(".py") or path.endswith(".pyw"):
        subprocess.Popen([sys.executable, path] + args)

    else:
        print("[ERROR] Unknown executable:", path)


# ---------------------------------------------------------
# CUSTOM VS NORMAL DETECTION
# ---------------------------------------------------------

def folder_has_main_lmc(folder):
    try:
        for f in os.listdir(folder):
            if f.endswith(".main.lmc"):
                return True
    except FileNotFoundError:
        return False
    return False


def get_custom_phaser():
    candidates = [
        os.path.join(BASE, "custom_phaser.exe"),
        os.path.join(BASE, "custom_phaser.py"),
        os.path.join(BASE, "custom_phaser.pyw"),

        # Correct location inside recources/Engine/
        os.path.join(BASE, "recources", "Engine", "custom_phaser.exe"),
        os.path.join(BASE, "recources", "Engine", "custom_phaser.py"),
        os.path.join(BASE, "recources", "Engine", "custom_phaser.pyw")
    ]

    for c in candidates:
        if os.path.exists(c):
            return c

    return None

# ---------------------------------------------------------
# ENGINE LAUNCHERS
# ---------------------------------------------------------

def launch_modern_engine(pack_name):
    version = "1.20.1"  # TODO: dynamic version later
    username = "Player"
    uuid = "00000000-0000-0000-0000-000000000000"
    token = "dummy"

    jar_path = os.path.join(ENGINE_DIR, "lemc-loader.jar")

    cmd = [
        "java",
        "--add-opens", "java.base/java.lang=ALL-UNNAMED",
        "--add-opens", "java.base/java.io=ALL-UNNAMED",
        "--add-opens", "java.base/java.util=ALL-UNNAMED",
        "--add-opens", "java.base/java.nio=ALL-UNNAMED",
        "--add-opens", "java.base/sun.nio.ch=ALL-UNNAMED",
        "-jar", jar_path,
        "--base", ENGINE_DIR,
        "--version", version,
        "--username", username,
        "--uuid", uuid,
        "--access-token", token
    ]

    print("[Modern Engine] Launching:", " ".join(cmd))
    subprocess.Popen(cmd, cwd=ENGINE_DIR)


def launch_legacy_engine(pack_name):
    jar_path = os.path.join(ENGINE_DIR, "legacy-loader.jar")
    print("[Legacy Engine] Launching:", jar_path)
    subprocess.Popen(["java", "-jar", jar_path], cwd=ENGINE_DIR)


# ---------------------------------------------------------
# NORMAL PACK ENGINE DETECTION
# ---------------------------------------------------------

def detect_normal_engine(folder):
    try:
        mod_count = len([f for f in os.listdir(folder) if f.endswith(".jar")])
    except FileNotFoundError:
        mod_count = 0

    if mod_count < 20:
        return "modern"
    else:
        return "legacy"


# ---------------------------------------------------------
# PACK LAUNCHER (NORMAL OR CUSTOM)
# ---------------------------------------------------------

def launch_pack(pack_name):
    pack_path = os.path.join(MODPACKS_DIR, pack_name)

    # CUSTOM PACK?
    if folder_has_main_lmc(pack_path):
        print(f"[CUSTOM PACK] {pack_name} → running custom phaser...")
        phaser = get_custom_phaser()

        if phaser is None:
            print("[ERROR] custom_phaser not found in launcher root!")
            return

        run_any(phaser, [pack_path])
        return

    # NORMAL PACK → detect engine
    engine = detect_normal_engine(pack_path)

    if engine == "modern":
        print(f"[NORMAL PACK] {pack_name} → modern engine")
        launch_modern_engine(pack_name)
    else:
        print(f"[NORMAL PACK] {pack_name} → legacy engine")
        launch_legacy_engine(pack_name)


# ---------------------------------------------------------
# LOAD MODPACKS
# ---------------------------------------------------------

def load_modpacks():
    packs = []
    if not os.path.exists(MODPACKS_DIR):
        return packs

    for folder in os.listdir(MODPACKS_DIR):
        path = os.path.join(MODPACKS_DIR, folder)
        if os.path.isdir(path):
            packs.append(folder)
    return packs


# ---------------------------------------------------------
# BUILD HOME PAGE
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

    # SEARCH BAR
    search_frame = tk.Frame(frame, bg=BG)
    search_frame.pack(pady=10)

    search_entry = tk.Entry(search_frame, width=50, font=("Arial", 14))
    search_entry.pack(side="left", padx=10)

    tk.Button(
        search_frame,
        text="Search",
        bg=ACCENT,
        fg="white",
        command=lambda: print("# TODO: search feature")
    ).pack(side="left")

    # SCROLLABLE CANVAS
    canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")

    canvas.configure(yscrollcommand=scrollbar.set)

    inner = tk.Frame(canvas, bg=BG)
    inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")

    packs = load_modpacks() or []

    CARD_WIDTH = 180
    CARD_HEIGHT = 260
    CARD_PAD = 40  # horizontal padding

    def rebuild_cards():
        # Make inner frame match canvas width
        try:
            canvas.itemconfig(inner_window, width=canvas.winfo_width())
        except tk.TclError:
            return  # canvas not ready yet

        # Clear old cards
        for widget in inner.winfo_children():
            widget.destroy()

        window_width = max(1, canvas.winfo_width())
        columns = max(1, window_width // (CARD_WIDTH + CARD_PAD))

        row = 0
        col = 0

        for pack in packs:
            card = tk.Frame(inner, bg=CARD, padx=10, pady=10)
            card.grid(row=row, column=col, padx=20, pady=20)

            # Thumbnail
            thumb = tk.Frame(card, bg="#555555", width=150, height=150)
            thumb.pack()
            thumb.pack_propagate(False)

            tk.Label(
                thumb,
                text="IMG",
                bg="#555555",
                fg="white"
            ).pack(expand=True)

            # Name
            tk.Label(
                card,
                text=pack,
                font=("Arial", 14, "bold"),
                bg=CARD,
                fg=FG,
                wraplength=150,
                justify="center"
            ).pack(pady=5)

            # Play button
            tk.Button(
                card,
                text="Play",
                bg=ACCENT,
                fg="white",
                width=12,
                command=lambda p=pack: launch_pack(p)
            ).pack(pady=2)

            # Menu button
            tk.Button(
                card,
                text="⋮",
                bg=CARD,
                fg=FG,
                width=3,
                command=lambda p=pack: launch_legacy_engine(p)
            ).pack(pady=2)

            col += 1
            if col >= columns:
                col = 0
                row += 1

        canvas.configure(scrollregion=canvas.bbox("all"))

    # Rebuild when the canvas itself resizes (safer than binding whole app)
    def on_canvas_configure(event):
        if event.width > 1:
            rebuild_cards()

    canvas.bind("<Configure>", on_canvas_configure)

    # Build once after Tk has laid things out
    frame.after(50, rebuild_cards)

    return frame
