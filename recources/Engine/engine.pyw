import os
import sys
import json
import platform
import subprocess

# =========================================================
#  BASE PATHS
# =========================================================

def get_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE = get_base()

# Engine folder: ...\LeModCraft\recources\Engine
# Minecraft root: ...\LeModCraft\data\Minecraft
MC_ROOT = os.path.normpath(os.path.join(BASE, "..", "..", "data", "Minecraft"))

# =========================================================
#  OS / HELPERS
# =========================================================

def get_os_name():
    sysname = platform.system().lower()
    if "windows" in sysname:
        return "windows"
    if "linux" in sysname:
        return "linux"
    if "darwin" in sysname or "mac" in sysname:
        return "osx"
    return sysname

def get_mod_jars(version_id: str) -> list:
    mods_dir = os.path.join(BASE, "mods", version_id)
    if not os.path.exists(mods_dir):
        return []
    jars = []
    for name in os.listdir(mods_dir):
        if name.lower().endswith(".jar"):
            jars.append(os.path.join(mods_dir, name))
    return jars

# =========================================================
#  VERSION FOLDER / JAR AUTO-DETECTION
# =========================================================

def find_version_folder(version_id: str) -> str:
    versions_dir = os.path.join(MC_ROOT, "versions")
    if not os.path.exists(versions_dir):
        raise FileNotFoundError(f"Minecraft versions folder not found: {versions_dir}")

    for folder in os.listdir(versions_dir):
        if folder.startswith(version_id):
            full = os.path.join(versions_dir, folder)
            if os.path.isdir(full):
                return full

    raise FileNotFoundError(f"No matching version folder found for {version_id}")

def find_version_jar(version_folder: str) -> str:
    folder_name = os.path.basename(version_folder)
    jar_path = os.path.join(version_folder, folder_name + ".jar")
    if not os.path.exists(jar_path):
        raise FileNotFoundError(f"Version JAR missing: {jar_path}")
    return jar_path

def find_version_json(version_folder: str) -> str:
    folder_name = os.path.basename(version_folder)
    json_path = os.path.join(version_folder, folder_name + ".json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Version JSON missing: {json_path}")
    return json_path

# =========================================================
#  LWJGL2 (OLD VERSIONS)
# =========================================================

def get_lwjgl2_jars() -> list:
    lw_dir = os.path.join(BASE, "runtime", "lwjgl2")
    jars = [
        os.path.join(lw_dir, "lwjgl.jar"),
        os.path.join(lw_dir, "lwjgl_util.jar"),
        os.path.join(lw_dir, "jinput.jar"),
    ]
    missing = [p for p in jars if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError("Missing LWJGL2 jars:\n" + "\n".join(missing))
    return jars

def get_lwjgl2_natives() -> str:
    lw_dir = os.path.join(BASE, "runtime", "lwjgl2")
    os_name = get_os_name()
    natives_dir = os.path.join(lw_dir, "natives", os_name)
    if not os.path.exists(natives_dir):
        raise FileNotFoundError(f"LWJGL2 natives folder missing: {natives_dir}")
    return natives_dir

# =========================================================
#  RULES (MODERN/LEGACY JSON)
# =========================================================

def lib_allowed_by_rules(lib: dict) -> bool:
    rules = lib.get("rules")
    if not rules:
        return True

    os_name = get_os_name()
    allowed = False

    for rule in rules:
        action = rule.get("action", "allow")
        os_rule = rule.get("os")

        if os_rule:
            name = os_rule.get("name")
            if name and name != os_name:
                continue

        if action == "allow":
            allowed = True
        elif action == "disallow":
            allowed = False

    return allowed

# =========================================================
#  MODERN / LEGACY-JSON CLASSPATH
# =========================================================

def build_json_classpath(version_id: str, data: dict) -> str:
    version_folder = find_version_folder(version_id)
    jar_path = find_version_jar(version_folder)

    libs = []
    missing = []
    lib_root = os.path.join(MC_ROOT, "libraries")

    for lib in data.get("libraries", []):
        if not lib_allowed_by_rules(lib):
            continue

        downloads = lib.get("downloads", {})
        artifact = downloads.get("artifact")
        if not artifact:
            continue

        path = artifact.get("path")
        if not path:
            continue

        full_path = os.path.join(lib_root, path)
        if os.path.exists(full_path):
            libs.append(full_path)
        else:
            missing.append(full_path)

    if missing:
        raise FileNotFoundError("Missing library files:\n" + "\n".join(missing))

    libs.append(jar_path)
    libs.extend(get_mod_jars(version_id))

    sep = ";" if os.name == "nt" else ":"
    return sep.join(libs)

def get_natives_folder(version_id: str) -> str:
    version_folder = find_version_folder(version_id)
    natives_dir = os.path.join(version_folder, "natives")
    os.makedirs(natives_dir, exist_ok=True)
    return natives_dir

def build_jvm_args(data: dict, natives_dir: str, classpath: str) -> list:
    jvm_args = []

    jvm_section = data.get("arguments", {}).get("jvm", [])
    for item in jvm_section:
        if isinstance(item, str):
            jvm_args.append(item)
        elif isinstance(item, dict) and "value" in item:
            val = item["value"]
            if isinstance(val, list):
                jvm_args.extend(val)
            else:
                jvm_args.append(val)

    if not any("java.library.path" in a for a in jvm_args):
        jvm_args.append(f"-Djava.library.path={natives_dir}")

    replaced = []
    for arg in jvm_args:
        arg = arg.replace("${natives_directory}", natives_dir)
        arg = arg.replace("${classpath}", classpath)
        replaced.append(arg)

    return replaced

def build_game_args(data: dict, username: str, uuid: str, access_token: str) -> list:
    args = []

    if "arguments" in data and "game" in data["arguments"]:
        game_section = data["arguments"]["game"]
        for item in game_section:
            if isinstance(item, str):
                args.append(item)
            elif isinstance(item, dict) and "value" in item:
                val = item["value"]
                if isinstance(val, list):
                    args.extend(val)
                else:
                    args.append(val)
    elif "minecraftArguments" in data:
        args = data["minecraftArguments"].split(" ")

    replacements = {
        "${auth_player_name}": username,
        "${auth_uuid}": uuid,
        "${auth_access_token}": access_token,
        "${version_name}": data.get("id", ""),
        "${assets_index_name}": data.get("assets", ""),
        "${game_directory}": os.path.join(MC_ROOT, "game"),
        "${user_type}": "mojang",
        "${version_type}": data.get("type", "release"),
    }

    final = []
    for arg in args:
        for key, val in replacements.items():
            arg = arg.replace(key, val)
        final.append(arg)

    return final

# =========================================================
#  OLD (NO JSON) CLASSPATH
# =========================================================

def build_old_classpath(version_id: str) -> str:
    version_folder = find_version_folder(version_id)
    jar_path = find_version_jar(version_folder)

    cp_list = get_lwjgl2_jars() + [jar_path]
    cp_list.extend(get_mod_jars(version_id))

    sep = ";" if os.name == "nt" else ":"
    return sep.join(cp_list)

# =========================================================
#  MAIN DISPATCH
# =========================================================

def build_launch_command(version_id: str, username: str, uuid: str, access_token: str) -> list:
    version_folder = find_version_folder(version_id)
    json_path = find_version_json(version_folder)

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cp = build_json_classpath(version_id, data)
        natives = get_natives_folder(version_id)

        jvm_args = build_jvm_args(data, natives, cp)
        game_args = build_game_args(data, username, uuid, access_token)

        main_class = data.get("mainClass")
        if not main_class:
            raise ValueError("mainClass missing in version JSON")

        cmd = ["java"] + jvm_args + ["-cp", cp, main_class] + game_args
        return cmd

    else:
        cp = build_old_classpath(version_id)
        natives = get_lwjgl2_natives()
        main_class = "net.minecraft.client.Minecraft"

        cmd = [
            "java",
            f"-Djava.library.path={natives}",
            "-cp", cp,
            main_class,
            username
        ]
        return cmd

# =========================================================
#  OPTIONAL: TEST
# =========================================================

if __name__ == "__main__":
    version = "1.20.1"  # base ID; will match 1.20.1-rc1-java etc.
    username = "Player"
    uuid = "00000000-0000-0000-0000-000000000000"
    token = "dummy-token"

    try:
        print("BASE:", BASE)
        print("MC_ROOT:", MC_ROOT)
        cmd = build_launch_command(version, username, uuid, token)
        print("Launch command:")
        print(" ".join(cmd))
        # subprocess.Popen(cmd)
    except Exception as e:
        print("Error:", e)
