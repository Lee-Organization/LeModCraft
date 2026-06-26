import os
import time
import subprocess
import requests
import shutil
import threading
import glob
import zipfile
import json
import concurrent.futures

# ---------------------------------------------------------
# BASIC PATHS
# ---------------------------------------------------------
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MC_ROOT = os.path.join(BASE_PATH, "data", "Minecraft")
VERSIONS_ROOT = os.path.join(MC_ROOT, "versions")

os.makedirs(VERSIONS_ROOT, exist_ok=True)

# ---------------------------------------------------------
# AUTO-DETECT MINECRAFT LAUNCHER (BEDROCK ONLY)
# ---------------------------------------------------------
def find_minecraft_launcher():
    local_appdata = os.getenv("LOCALAPPDATA") or ""
    program_files = os.getenv("ProgramFiles") or r"C:\Program Files"
    program_files_x86 = os.getenv("ProgramFiles(x86)") or r"C:\Program Files (x86)"

    candidates = [
        os.path.join(local_appdata, "MinecraftLauncher", "MinecraftLauncher.exe"),
        os.path.join(
            local_appdata,
            "Packages",
            "Microsoft.4297127D64EC6_8wekyb3d8bbwe",
            "LocalCache",
            "Local",
            "MinecraftLauncher",
            "MinecraftLauncher.exe"
        ),
        os.path.join(program_files_x86, "Minecraft Launcher", "MinecraftLauncher.exe"),
        os.path.join(program_files, "Minecraft Launcher", "MinecraftLauncher.exe"),
    ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    shallow_root = local_appdata
    if shallow_root and os.path.isdir(shallow_root):
        for root, dirs, files in os.walk(shallow_root):
            if "MinecraftLauncher.exe" in files:
                return os.path.join(root, "MinecraftLauncher.exe")
            if root.count(os.sep) - shallow_root.count(os.sep) > 4:
                dirs[:] = []
    return None

# ---------------------------------------------------------
# FETCH MOJANG VERSION LIST
# ---------------------------------------------------------
def get_mojang_versions():
    url = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("versions", [])

def find_version_entry(version_id, versions):
    for v in versions:
        if v.get("id") == version_id:
            return v
    return None

# ---------------------------------------------------------
# SIMPLE DOWNLOAD
# ---------------------------------------------------------
def download_file(url, dest, progress_callback=lambda x: None):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        return
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("Content-Length", "0") or 0)
    downloaded = 0

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = int(downloaded * 100 / total)
                progress_callback(min(99, pct))

# ---------------------------------------------------------
# FAST ASSETS (PER-VERSION, PARALLEL, SIMPLIFIED)
# ---------------------------------------------------------
def fast_download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        return
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open(dest, "wb") as f:
                f.write(r.content)
    except:
        pass

def download_assets_fast(data, version_folder, progress_callback=lambda x: None):
    assets_info = data.get("assetIndex")
    if not assets_info:
        return

    index_url = assets_info["url"]
    index_id = assets_info.get("id", "assets")

    assets_root = os.path.join(version_folder, "assets")
    indexes_dir = os.path.join(assets_root, "indexes")
    objects_dir = os.path.join(assets_root, "objects")

    os.makedirs(indexes_dir, exist_ok=True)
    os.makedirs(objects_dir, exist_ok=True)

    index_path = os.path.join(indexes_dir, index_id + ".json")

    r = requests.get(index_url, timeout=15)
    r.raise_for_status()
    with open(index_path, "wb") as f:
        f.write(r.content)

    index_data = json.loads(r.content)
    objects = index_data.get("objects", {})

    total = len(objects)
    if total == 0:
        progress_callback(100)
        return

    base_url = "https://resources.download.minecraft.net"
    done = 0

    def task(obj_hash):
        nonlocal done
        url = f"{base_url}/{obj_hash[:2]}/{obj_hash}"
        dest = os.path.join(objects_dir, obj_hash)
        fast_download(url, dest)
        done += 1
        progress_callback(50 + int((done / total) * 50))

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        for name, obj in objects.items():
            h = obj.get("hash")
            if not h:
                continue
            ex.submit(task, h)

# ---------------------------------------------------------
# LIBRARIES + NATIVES (PER-VERSION, SIMPLIFIED)
# ---------------------------------------------------------
def download_libraries_local(data, version_folder, progress_callback=lambda x: None):
    libs = data.get("libraries", [])
    libs_dir = os.path.join(version_folder, "libraries")
    os.makedirs(libs_dir, exist_ok=True)

    total = len(libs)
    done = 0

    def dl_artifact(lib):
        nonlocal done
        downloads = lib.get("downloads", {})
        artifact = downloads.get("artifact")
        if artifact:
            url = artifact.get("url")
            path = artifact.get("path", "")
            if url:
                filename = os.path.basename(path) or os.path.basename(url)
                dest = os.path.join(libs_dir, filename)
                try:
                    fast_download(url, dest)
                except:
                    pass
        done += 1
        if total > 0:
            pct = int(done * 100 / total)
            progress_callback(min(99, pct))

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for lib in libs:
            ex.submit(dl_artifact, lib)

def extract_natives_local(version_folder, data):
    natives_dir = os.path.join(version_folder, "natives")
    os.makedirs(natives_dir, exist_ok=True)

    libs_dir = os.path.join(version_folder, "libraries")
    tmp_dir = os.path.join(version_folder, "natives_zips")
    os.makedirs(tmp_dir, exist_ok=True)

    libs = data.get("libraries", [])
    for lib in libs:
        downloads = lib.get("downloads", {})
        classifiers = downloads.get("classifiers", {})
        for key, info in classifiers.items():
            url = info.get("url")
            path = info.get("path", "")
            if not url:
                continue
            filename = os.path.basename(path) or os.path.basename(url)
            zip_path = os.path.join(tmp_dir, filename)
            try:
                fast_download(url, zip_path)
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(natives_dir)
            except:
                continue

# ---------------------------------------------------------
# GET REAL BEDROCK INSTALL PATH
# ---------------------------------------------------------
def get_bedrock_install_path():
    base = os.path.join(os.getenv("LOCALAPPDATA") or "", "Packages")
    if not os.path.isdir(base):
        return None

    for folder in os.listdir(base):
        if folder.startswith("Microsoft.MinecraftUWP"):
            return os.path.join(
                base,
                folder,
                "LocalState",
                "games",
                "com.mojang"
            )
    return None

# ---------------------------------------------------------
# FOLDER SIZE / PROGRESS (BEDROCK ONLY)
# ---------------------------------------------------------
def get_folder_size(path):
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total

def track_progress(folder, progress_callback):
    last_size = 0
    stable_ticks = 0
    progress = 1
    progress_callback(progress)

    while True:
        size = get_folder_size(folder)
        growth = size - last_size
        last_size = size

        if growth > 0:
            progress = min(99, progress + (growth / 50000))
            progress_callback(progress)
            stable_ticks = 0
        else:
            stable_ticks += 1

        if stable_ticks >= 5:
            progress_callback(100)
            break

        time.sleep(0.2)

def wait_for_install(folder, timeout=120):
    last = get_folder_size(folder)
    stable = 0
    start = time.time()

    while True:
        size = get_folder_size(folder)

        if size != last:
            last = size
            stable = 0
        else:
            stable += 1

        if stable >= 5:
            return folder

        if time.time() - start > timeout:
            raise TimeoutError("Install timed out")

        time.sleep(0.2)

# ---------------------------------------------------------
# BEDROCK HEADLESS INSTALL
# ---------------------------------------------------------
def run_headless_install(launcher_path, workdir, mojang_version):
    cmd = [
        launcher_path,
        "--workDir", workdir,
        "--install", mojang_version
    ]
    subprocess.Popen(cmd, shell=False)

# ---------------------------------------------------------
# MAIN INSTALL FUNCTION
# ---------------------------------------------------------
def install_version(version_id, edition, progress_callback=lambda x: None):
    """
    Install a Minecraft version (Java or Bedrock) into LeModCraft's
    internal structure.

    version_id: Mojang version ID (e.g. '1.20.4')
    edition: 'java' or 'bedrock'
    progress_callback: function(percent:int)
    """
    internal_name = f"{version_id}-{edition}"
    final_folder = os.path.join(VERSIONS_ROOT, internal_name)
    os.makedirs(final_folder, exist_ok=True)

    # -------------------------
    # BEDROCK INSTALL LOGIC
    # -------------------------
    if edition.lower() == "bedrock":
        launcher = find_minecraft_launcher()
        if not launcher:
            return "ERROR: Could not find MinecraftLauncher.exe"

        bedrock_path = get_bedrock_install_path()
        if not bedrock_path:
            return "ERROR: Could not locate Bedrock install directory."

        run_headless_install(launcher, bedrock_path, version_id)

        threading.Thread(
            target=track_progress,
            args=(bedrock_path, progress_callback),
            daemon=True
        ).start()

        try:
            wait_for_install(bedrock_path)
        except TimeoutError as e:
            return f"ERROR: Bedrock install timed out: {e}"

        if os.path.exists(final_folder):
            shutil.rmtree(final_folder)
        shutil.copytree(bedrock_path, final_folder)

        progress_callback(100)
        return f"SUCCESS: Installed Bedrock {version_id} into {internal_name}"

    # -------------------------
    # JAVA INSTALL LOGIC (NO LAUNCHER, SELF-CONTAINED)
    # -------------------------
    try:
        versions = get_mojang_versions()
    except Exception as e:
        return f"ERROR: Failed to fetch Mojang versions: {e}"

    entry = find_version_entry(version_id, versions)
    if not entry:
        return f"ERROR: Mojang version '{version_id}' not found."

    try:
        resp = requests.get(entry["url"], timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"ERROR: Failed to fetch version JSON: {e}"

    # Save JSON under internal name
    json_path = os.path.join(final_folder, internal_name + ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Download client jar
    client = data.get("downloads", {}).get("client")
    if not client:
        return "ERROR: Version JSON missing client download info."

    jar_url = client.get("url")
    jar_path = os.path.join(final_folder, internal_name + ".jar")
    try:
        download_file(jar_url, jar_path, lambda p: progress_callback(min(40, p)))
    except Exception as e:
        return f"ERROR: Failed to download client jar: {e}"

    # Download libraries (per-version, simplified)
    try:
        download_libraries_local(data, final_folder, lambda p: progress_callback(40 + int(p * 0.3)))
    except Exception:
        pass

    # Download assets (per-version, parallel, simplified)
    try:
        download_assets_fast(data, final_folder, lambda p: progress_callback(70 + int(p * 0.3)))
    except Exception:
        pass

    # Extract natives (per-version)
    try:
        extract_natives_local(final_folder, data)
    except Exception:
        pass

    progress_callback(100)
    return f"SUCCESS: Installed Java {version_id} into {internal_name}"
