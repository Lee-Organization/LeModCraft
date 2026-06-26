import os
import json
import time
import shutil
import tkinter as tk
from tkinter import ttk, messagebox
import requests
import re

bedrock_enabled = False  # toggle this to True if you ever support Bedrock

# NEW IMPORT — this is now responsible for installing versions
from recources.Versions.add_version import install_version

# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VERSIONS_PATH = os.path.join(BASE_PATH, "data", "Minecraft", "versions")

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def get_age(timestamp):
    diff = time.time() - timestamp
    days = diff // 86400
    hours = diff // 3600

    if diff < 60:
        return "Just now"
    if diff < 3600:
        return f"{int(diff//60)} minutes ago"
    if diff < 86400:
        return f"{int(hours)} hours ago"
    return f"{int(days)} days ago"


# ---------------------------------------------------------
# PARSE INSTALLED VERSION FOLDER
# ---------------------------------------------------------
def parse_installed(folder):
    display = folder.replace("update-", "").replace("-", " ")

    num = None
    for part in folder.split("-"):
        if part.isdigit():
            num = int(part)
            break
    if num is None:
        num = 0

    lower = folder.lower()
    is_java = "java" in lower
    is_bedrock = "bedrock" in lower
    is_snapshot = "snapshot" in lower
    is_release = "release" in lower

    path = os.path.join(VERSIONS_PATH, folder)
    age = get_age(os.path.getmtime(path))

    return {
        "folder": folder,
        "num": num,
        "java": is_java,
        "bedrock": is_bedrock,
        "snapshot": is_snapshot,
        "release": is_release,
        "display": display,
        "age": age
    }


# ---------------------------------------------------------
# SORTING ORDER
# ---------------------------------------------------------
def determine_types(versions):
    versions.sort(key=lambda v: v["num"], reverse=True)
    return versions


# ---------------------------------------------------------
# FETCH MOJANG MANIFEST
# ---------------------------------------------------------
def fetch_mojang_versions():
    url = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
    try:
        data = requests.get(url).json()
        return data["versions"]
    except:
        messagebox.showerror("Error", "Failed to fetch Mojang version list.")
        return []


# ---------------------------------------------------------
# SPLIT JAVA VS BEDROCK
# ---------------------------------------------------------
def split_versions(versions):
    java = []
    bedrock = []

    # Bedrock: 2–4 numeric segments
    bedrock_pattern = re.compile(r"^\d+(\.\d+){1,3}$")

    for v in versions:
        vid = v["id"]
        vtype = v["type"]

        # Bedrock detection
        if bedrock_pattern.match(vid):
            bedrock.append(vid)
            continue

        # Java detection
        if vtype in ["release", "snapshot", "old_beta", "old_alpha"]:
            java.append((vid, vtype))

    return java, bedrock


# ---------------------------------------------------------
# ADD VERSION WINDOW (PAGE 2)
# ---------------------------------------------------------
def open_edit_versions_window(parent):
    import tkinter as tk
    from tkinter import ttk, messagebox
    import threading

    global bedrock_enabled

    # -----------------------------
    # WINDOW SETUP
    # -----------------------------
    win = tk.Toplevel(parent)
    win.title("Add Minecraft Version")
    win.geometry("900x550")
    win.resizable(False, False)

    # -----------------------------
    # FETCH MOJANG VERSIONS
    # -----------------------------
    all_versions = fetch_mojang_versions()
    java_versions, bedrock_versions = split_versions(all_versions)

    # -----------------------------
    # SEARCH BARS
    # -----------------------------
    ttk.Label(win, text="Search Java:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
    java_search_var = tk.StringVar()
    ttk.Entry(win, textvariable=java_search_var, width=30).grid(row=0, column=1, sticky="w", padx=10)

    ttk.Label(win, text="Search Bedrock:").grid(row=0, column=2, sticky="w", padx=10, pady=5)
    bedrock_search_var = tk.StringVar()
    ttk.Entry(win, textvariable=bedrock_search_var, width=30).grid(row=0, column=3, sticky="w", padx=10)

    # -----------------------------
    # JAVA LIST
    # -----------------------------
    ttk.Label(win, text="Java Versions").grid(row=1, column=0, columnspan=2, pady=5)

    java_tree = ttk.Treeview(win, columns=("Version", "Type"), show="headings", height=18)
    java_tree.heading("Version", text="Version")
    java_tree.heading("Type", text="Type")
    java_tree.column("Version", width=200)
    java_tree.column("Type", width=100)
    java_tree.grid(row=2, column=0, columnspan=2, padx=10, sticky="nsew")

    # -----------------------------
    # BEDROCK LIST
    # -----------------------------
    ttk.Label(win, text="Bedrock Versions").grid(row=1, column=2, columnspan=2, pady=5)

    bedrock_tree = ttk.Treeview(win, columns=("Version",), show="headings", height=18)
    bedrock_tree.heading("Version", text="Version")
    bedrock_tree.column("Version", width=200)
    bedrock_tree.grid(row=2, column=2, columnspan=2, padx=10, sticky="nsew")

    # -----------------------------
    # POPULATE LISTS
    # -----------------------------
    for vid, vtype in java_versions:
        java_tree.insert("", "end", values=(vid, vtype))

    for vid in bedrock_versions:
        bedrock_tree.insert("", "end", values=(vid,))

    # -----------------------------
    # MUTUAL EXCLUSIVE SELECTION
    # -----------------------------
    def on_java_select(event):
        bedrock_tree.selection_remove(*bedrock_tree.selection())

    def on_bedrock_select(event):
        java_tree.selection_remove(*java_tree.selection())

    java_tree.bind("<<TreeviewSelect>>", on_java_select)
    bedrock_tree.bind("<<TreeviewSelect>>", on_bedrock_select)

    # -----------------------------
    # SEARCH FILTERS
    # -----------------------------
    def filter_java(*_):
        search = java_search_var.get().lower()
        java_tree.delete(*java_tree.get_children())
        for vid, vtype in java_versions:
            if search in vid.lower():
                java_tree.insert("", "end", values=(vid, vtype))

    def filter_bedrock(*_):
        search = bedrock_search_var.get().lower()
        bedrock_tree.delete(*bedrock_tree.get_children())
        for vid in bedrock_versions:
            if search in vid.lower():
                bedrock_tree.insert("", "end", values=(vid,))

    java_search_var.trace_add("write", filter_java)
    bedrock_search_var.trace_add("write", filter_bedrock)

    # -----------------------------
    # PROGRESS BAR
    # -----------------------------
    progress = ttk.Progressbar(win, length=400, mode="determinate")
    progress.grid(row=3, column=0, columnspan=4, pady=15)

    def update_progress(value):
        progress["value"] = value
        progress.update_idletasks()

    # -----------------------------
    # INSTALL BUTTON
    # -----------------------------
    def install_selected():
        java_sel = java_tree.selection()
        bedrock_sel = bedrock_tree.selection()

        # Java selected
        if java_sel:
            version = java_tree.item(java_sel[0])["values"][0]
            edition = "java"

        # Bedrock selected
        elif bedrock_sel:
            version = bedrock_tree.item(bedrock_sel[0])["values"][0]
            edition = "bedrock"

            if not bedrock_enabled:
                messagebox.showwarning(
                    "Bedrock Not Supported",
                    "Bedrock installation is not supported at the moment.\n\n"
                    "Please install a Java version instead."
                )
                return

        else:
            messagebox.showerror("Error", "No version selected.")
            return

        # Run installer in thread
        def run_install():
            result = install_version(version, edition, update_progress)
            messagebox.showinfo("Install Complete", result)

        threading.Thread(target=run_install, daemon=True).start()

    ttk.Button(win, text="Install Selected Version", command=install_selected).grid(
        row=4, column=0, columnspan=4, pady=10
    )

    win.transient(parent)
    win.grab_set()
    win.focus()

# ---------------------------------------------------------
# DELETE INSTALLED VERSION (FIRST PAGE)
# ---------------------------------------------------------
def delete_installed_version(tree):
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "No version selected.")
        return

    folder = selection[0]
    full_path = os.path.join(VERSIONS_PATH, folder)

    if not os.path.exists(full_path):
        messagebox.showerror("Error", "Folder not found.")
        return

    if not messagebox.askyesno("Delete Version", f"Delete installed version '{folder}'?"):
        return

    try:
        shutil.rmtree(full_path)
        tree.delete(folder)
        messagebox.showinfo("Deleted", f"Version '{folder}' removed.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to delete:\n{e}")


# ---------------------------------------------------------
# INSTALLED VERSIONS TAB (PAGE 1)
# ---------------------------------------------------------
def create_Versions_tab(root):
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    tree = ttk.Treeview(
        frame,
        columns=("Version", "Type", "Age"),
        show="headings",
        height=15
    )

    tree.heading("Version", text="Version")
    tree.heading("Type", text="Type")
    tree.heading("Age", text="Age")

    tree.column("Version", width=200)
    tree.column("Type", width=150)
    tree.column("Age", width=150)

    tree.grid(row=0, column=0, sticky="nsew")

    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    # LOAD INSTALLED VERSIONS
    versions = []
    if os.path.isdir(VERSIONS_PATH):
        for folder in os.listdir(VERSIONS_PATH):
            if os.path.isdir(os.path.join(VERSIONS_PATH, folder)):
                versions.append(parse_installed(folder))

    ordered = determine_types(versions)

    for v in ordered:
        tree.insert("", "end", iid=v["folder"],
                    values=(v["display"], "", v["age"]))

    # BUTTON BAR
    button_frame = ttk.Frame(frame)
    button_frame.grid(row=1, column=0, pady=10)

    ttk.Button(
        button_frame,
        text="Add Version",
        width=15,
        command=lambda: open_edit_versions_window(root)
    ).grid(row=0, column=0, padx=5)

    ttk.Button(
        button_frame,
        text="Delete",
        width=15,
        command=lambda: delete_installed_version(tree)
    ).grid(row=0, column=1, padx=5)

    return frame
