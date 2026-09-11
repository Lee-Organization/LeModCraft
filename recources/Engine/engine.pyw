import os
import sys
import json
import platform
import subprocess
import base64
import re
import shutil
import zipfile
from collections import Counter

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
#  ACCOUNT LOADING (NEW)
# =========================================================

def load_mc_account():
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    account_file = os.path.join(base, "data", "Account.json")

    if not os.path.exists(account_file):
        raise Exception("No Account.json found!")

    with open(account_file, "r") as f:
        data = json.load(f)

    if len(data["accounts"]) == 0:
        raise Exception("No Minecraft accounts stored!")

    return data["accounts"][0]

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

def get_mod_jars(version_id: str, modpack_dir: str = None) -> list:
    """Return the JARs belonging to the selected modpack.

    Older builds looked in ``LeModCraft/mods/<version>``.  Modpacks are
    actually stored under ``modpacks/<name>`` and may keep their JARs either
    at the pack root or in a conventional ``mods`` folder.
    """
    if not modpack_dir:
        legacy_dir = os.path.join(BASE, "mods", version_id)
        if not os.path.isdir(legacy_dir):
            return []
        modpack_dir = legacy_dir

    jars = []
    search_roots = [modpack_dir]
    mods_dir = os.path.join(modpack_dir, "mods")
    if os.path.isdir(mods_dir):
        search_roots.append(mods_dir)

    seen = set()
    for root in search_roots:
        for current_root, _, names in os.walk(root):
            for name in names:
                if not name.lower().endswith(".jar"):
                    continue
                path = os.path.normpath(os.path.join(current_root, name))
                if path not in seen:
                    seen.add(path)
                    jars.append(path)

    return sorted(jars)

# =========================================================
#  VERSION FOLDER / JAR AUTO-DETECTION
# =========================================================

def find_version_folder(version_id: str) -> str:
    versions_dir = os.path.join(MC_ROOT, "versions")
    if not os.path.exists(versions_dir):
        raise FileNotFoundError(f"Minecraft versions folder not found: {versions_dir}")

    # 1) Exact match
    exact = os.path.join(versions_dir, version_id)
    if os.path.isdir(exact):
        return exact

    # 2) Match version_id-* ONLY
    for folder in os.listdir(versions_dir):
        if folder.startswith(version_id + "-"):
            full = os.path.join(versions_dir, folder)
            if os.path.isdir(full):
                return full

    raise FileNotFoundError(f"No matching version folder found for {version_id}")

def find_version_json(version_folder: str) -> str:
    folder_name = os.path.basename(version_folder)
    json_path = os.path.join(version_folder, folder_name + ".json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Version JSON missing: {json_path}")
    return json_path

def find_version_jar(version_folder: str) -> str:
    folder_name = os.path.basename(version_folder)
    jar_path = os.path.join(version_folder, folder_name + ".jar")

    if not os.path.exists(jar_path):
        # Try ANY .jar in the folder
        for f in os.listdir(version_folder):
            if f.lower().endswith(".jar"):
                return os.path.join(version_folder, f)

        raise FileNotFoundError(f"Version JAR missing: {jar_path}")

    return jar_path

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


def argument_allowed_by_rules(item: dict, features: dict = None) -> bool:
    """Apply Mojang's OS and feature rules to a JVM/game argument."""
    rules = item.get("rules")
    if not rules:
        return True

    features = features or {}
    allowed = False
    os_name = get_os_name()

    for rule in rules:
        os_rule = rule.get("os")
        if os_rule:
            rule_os = os_rule.get("name")
            if rule_os and rule_os != os_name:
                continue

        rule_features = rule.get("features", {})
        if any(features.get(name, False) != expected
               for name, expected in rule_features.items()):
            continue

        action = rule.get("action", "allow")
        if action == "allow":
            allowed = True
        elif action == "disallow":
            allowed = False

    return allowed

# =========================================================
#  MODERN / LEGACY-JSON CLASSPATH
# =========================================================

def build_json_classpath(
    version_id: str, data: dict, modpack_dir: str = None
) -> str:
    version_folder = find_version_folder(version_id)
    jar_path = find_version_jar(version_folder)

    libs = []
    missing = []

    # Libraries are stored per-version:
    lib_root = os.path.join(version_folder, "libraries")

    for lib in data.get("libraries", []):
        if not lib_allowed_by_rules(lib):
            continue

        downloads = lib.get("downloads", {})
        artifact = downloads.get("artifact")
        if not artifact:
            continue

        path = artifact.get("path", "")
        url = artifact.get("url", "")

        filename = os.path.basename(path) or os.path.basename(url)
        full_path = os.path.join(lib_root, filename)

        if os.path.exists(full_path):
            libs.append(full_path)
        else:
            missing.append(full_path)

    if missing:
        raise FileNotFoundError("Missing library files:\n" + "\n".join(missing))

    libs.append(jar_path)
    libs.extend(get_mod_jars(version_id, modpack_dir))

    sep = ";" if os.name == "nt" else ":"
    return sep.join(libs)

def get_natives_folder(version_id: str) -> str:
    version_folder = find_version_folder(version_id)
    natives_dir = os.path.join(version_folder, "natives")
    os.makedirs(natives_dir, exist_ok=True)
    return natives_dir


def repair_asset_object_layout(version_folder: str, data: dict):
    """Move assets from the old flat layout into Minecraft's hash folders."""
    asset_index = data.get("assetIndex", {})
    index_id = asset_index.get("id")
    if not index_id:
        return

    assets_root = os.path.join(version_folder, "assets")
    index_path = os.path.join(assets_root, "indexes", index_id + ".json")
    objects_dir = os.path.join(assets_root, "objects")
    if not os.path.exists(index_path) or not os.path.isdir(objects_dir):
        return

    try:
        with open(index_path, "r", encoding="utf-8") as file:
            objects = json.load(file).get("objects", {})
    except (OSError, ValueError, TypeError):
        return

    for asset in objects.values():
        asset_hash = asset.get("hash") if isinstance(asset, dict) else None
        if not asset_hash or len(asset_hash) < 2:
            continue

        old_path = os.path.join(objects_dir, asset_hash)
        new_dir = os.path.join(objects_dir, asset_hash[:2])
        new_path = os.path.join(new_dir, asset_hash)

        if os.path.isfile(old_path) and not os.path.exists(new_path):
            os.makedirs(new_dir, exist_ok=True)
            try:
                os.replace(old_path, new_path)
            except OSError:
                # A copy fallback handles filesystems where replace cannot
                # move across the selected storage boundary.
                try:
                    import shutil
                    shutil.copy2(old_path, new_path)
                    os.remove(old_path)
                except OSError:
                    pass


def get_java_major_version(java_executable: str):
    """Return the major version reported by a Java executable."""
    try:
        result = subprocess.run(
            [java_executable, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    output = (result.stdout or "") + "\n" + (result.stderr or "")
    match = re.search(r'version\s+"([^"]+)"', output)
    if not match:
        return None

    version = match.group(1).split(".")
    if version[0] == "1" and len(version) > 1:
        return int(version[1])
    try:
        return int(re.match(r"\d+", version[0]).group())
    except (AttributeError, ValueError):
        return None


def _java_candidates():
    """Find Java executables without assuming PATH is the right runtime."""
    executable_name = "java.exe" if os.name == "nt" else "java"
    candidates = []

    def add_candidate(path):
        if not path:
            return
        if os.path.isdir(path):
            path = os.path.join(path, "bin", executable_name)
        candidates.append(path)

    explicit = os.environ.get("LEMODCRAFT_JAVA")
    if explicit:
        add_candidate(explicit)

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        add_candidate(java_home)

    path_java = shutil.which("java")
    if path_java:
        add_candidate(path_java)

    if os.name == "nt":
        program_roots = [
            (os.environ.get("ProgramFiles"), ""),
            (os.environ.get("ProgramFiles(x86)"), ""),
            (os.environ.get("LOCALAPPDATA"), ""),
            # Temurin's default per-user Windows install location.
            (os.environ.get("LOCALAPPDATA"), "Programs"),
        ]
        vendor_folders = (
            "Java",
            "Eclipse Adoptium",
            "Microsoft",
            "AdoptOpenJDK",
            "Temurin",
        )

        for program_root, prefix in program_roots:
            if not program_root:
                continue
            for vendor_folder in vendor_folders:
                root = os.path.join(program_root, prefix, vendor_folder)
                if not os.path.isdir(root):
                    continue

                for current_root, dirs, files in os.walk(root):
                    depth = os.path.relpath(current_root, root).count(os.sep)
                    if depth > 5:
                        dirs[:] = []
                        continue
                    for filename in files:
                        if filename.lower() == executable_name.lower():
                            add_candidate(os.path.join(current_root, filename))

    unique = []
    seen = set()
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if normalized not in seen and os.path.isfile(normalized):
            seen.add(normalized)
            unique.append(normalized)
    return unique


def find_java_executable(data: dict) -> str:
    """Select Java compatible with the version manifest."""
    required = data.get("javaVersion", {}).get("majorVersion")
    try:
        required = int(required) if required is not None else None
    except (TypeError, ValueError):
        required = None

    candidates = _java_candidates()
    if not candidates:
        raise FileNotFoundError(
            "Java was not found. Install the required Java runtime or set "
            "LEMODCRAFT_JAVA to its java executable."
        )

    checked_versions = []
    for candidate in candidates:
        detected = get_java_major_version(candidate)
        checked_versions.append((candidate, detected))
        if required is None or detected == required:
            return candidate

    if required is not None:
        found = ", ".join(
            f"{path} (Java {version or 'unknown'})"
            for path, version in checked_versions
        )
        raise RuntimeError(
            f"Minecraft {data.get('id', 'version')} requires Java {required}, "
            f"but no matching runtime was found. Checked: {found}. "
            "Install that Java version or set LEMODCRAFT_JAVA to its "
            "java executable."
        )

    return candidates[0]

def build_jvm_args(data: dict, natives_dir: str, classpath: str) -> list:
    jvm_args = []

    jvm_section = data.get("arguments", {}).get("jvm", [])
    for item in jvm_section:
        if isinstance(item, str):
            values = [item]
        elif isinstance(item, dict) and "value" in item:
            if not argument_allowed_by_rules(item):
                continue
            val = item["value"]
            if isinstance(val, list):
                values = val
            else:
                values = [val]
        else:
            continue

        # The launcher owns the final classpath argument below.  Some
        # version manifests also include -cp/${classpath} in their JVM list;
        # keeping both produces an invalid command.
        for value in values:
            if value in ("-cp", "${classpath}"):
                continue
            jvm_args.append(value)

    if not any("java.library.path" in a for a in jvm_args):
        jvm_args.append(f"-Djava.library.path={natives_dir}")

    replaced = []
    for arg in jvm_args:
        arg = arg.replace("${natives_directory}", natives_dir)
        arg = arg.replace("${classpath}", classpath)
        replaced.append(arg)

    return replaced

def get_xuid(access_token: str) -> str:
    """Read the Xbox user id from the JWT when it is available."""
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(
            base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        )
        return str(claims.get("xuid") or claims.get("xid") or "")
    except (IndexError, ValueError, TypeError, UnicodeDecodeError):
        return ""


def build_game_args(
    data: dict,
    username: str,
    uuid: str,
    access_token: str,
    version_folder: str = None,
) -> list:
    args = []
    features = {
        "is_demo_user": False,
        "has_custom_resolution": False,
        "is_quick_play": False,
    }

    if "arguments" in data and "game" in data["arguments"]:
        game_section = data["arguments"]["game"]
        for item in game_section:
            if isinstance(item, str):
                args.append(item)
            elif isinstance(item, dict) and "value" in item:
                if not argument_allowed_by_rules(item, features):
                    continue
                val = item["value"]
                if isinstance(val, list):
                    args.extend(val)
                else:
                    args.append(val)
    elif "minecraftArguments" in data:
        args = data["minecraftArguments"].split(" ")

    assets_root = os.path.join(version_folder, "assets") if version_folder else os.path.join(MC_ROOT, "assets")
    replacements = {
        "${auth_player_name}": username,
        "${auth_uuid}": uuid,
        "${auth_access_token}": access_token,
        "${version_name}": data.get("id", ""),
        "${assets_root}": assets_root,
        "${assets_index_name}": data.get("assets", ""),
        "${game_directory}": os.path.join(MC_ROOT, "game"),
        "${user_type}": "msa",
        "${version_type}": data.get("type", "release"),
        "${launcher_name}": "LeModCraft",
        "${launcher_version}": "1.0",
        "${clientid}": uuid,
        "${auth_xuid}": get_xuid(access_token),
        "${resolution_width}": "854",
        "${resolution_height}": "480",
        "${quickPlayPath}": "",
        "${quickPlaySingleplayer}": "",
        "${quickPlayMultiplayer}": "",
        "${quickPlayRealms}": "",
    }

    final = []
    for arg in args:
        for key, val in replacements.items():
            arg = arg.replace(key, val)
        # Do not pass unresolved template variables to Java.  A supported
        # manifest should normally replace every value above, but skipping an
        # optional argument is safer than making the JVM/game parse ${...}.
        if "${" not in arg:
            final.append(arg)

    return final

# =========================================================
#  OLD (NO JSON) CLASSPATH
# =========================================================

def build_old_classpath(version_id: str, modpack_dir: str = None) -> str:
    version_folder = find_version_folder(version_id)
    jar_path = find_version_jar(version_folder)

    cp_list = get_lwjgl2_jars() + [jar_path]
    cp_list.extend(get_mod_jars(version_id, modpack_dir))

    sep = ";" if os.name == "nt" else ":"
    return sep.join(cp_list)

# =========================================================
#  MAIN DISPATCH (MODIFIED)
# =========================================================

def _version_candidates(value):
    """Extract Minecraft-style versions from metadata values."""
    if isinstance(value, dict):
        values = []
        for nested in value.values():
            values.extend(_version_candidates(nested))
        return values

    if isinstance(value, (list, tuple)):
        values = []
        for nested in value:
            values.extend(_version_candidates(nested))
        return values

    if not isinstance(value, str):
        return []

    # This handles exact versions and ranges such as:
    #   [1.20.1,1.21), >=1.20.1, and 1.20.1
    matches = re.findall(r"(?<!\d)(\d+\.\d+(?:\.\d+)?)(?!\d)", value)
    # For a range such as [1.20.1,1.21), the lower bound is the useful
    # version to resolve against the installed version folders.
    return matches[:1]


def _metadata_versions_from_json(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError, TypeError):
        return []

    versions = []
    version_keys = {
        "minecraft",
        "minecraft_version",
        "minecraftversion",
        "game_version",
        "gameversion",
    }

    def visit(value, key=None):
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                normalized_key = str(nested_key).lower().replace("-", "_")
                if normalized_key == "minecraft" and isinstance(nested_value, dict):
                    versions.extend(
                        _version_candidates(nested_value.get("version", ""))
                    )
                elif normalized_key in version_keys:
                    versions.extend(_version_candidates(nested_value))
                visit(nested_value, normalized_key)
        elif isinstance(value, list):
            for nested_value in value:
                visit(nested_value, key)

    visit(data)
    return versions


def _metadata_versions_from_jar(path):
    versions = []

    try:
        with zipfile.ZipFile(path, "r") as jar:
            names = set(jar.namelist())

            if "fabric.mod.json" in names:
                try:
                    fabric_data = json.loads(
                        jar.read("fabric.mod.json").decode("utf-8")
                    )
                    versions.extend(
                        _version_candidates(
                            fabric_data.get("depends", {}).get("minecraft", "")
                        )
                    )
                except (ValueError, UnicodeDecodeError, AttributeError):
                    pass

            for metadata_name in (
                "META-INF/mods.toml",
                "META-INF/neoforge.mods.toml",
            ):
                if metadata_name not in names:
                    continue

                try:
                    text = jar.read(metadata_name).decode("utf-8", errors="ignore")
                except KeyError:
                    continue

                # Only inspect the Minecraft dependency block.  The other
                # version fields in these files are the mod's own version.
                dependency_blocks = re.findall(
                    r'modId\s*=\s*["\']minecraft["\'](.*?)(?=\n\s*\[\[|\Z)',
                    text,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                for block in dependency_blocks:
                    match = re.search(
                        r"(?:versionRange|version)\s*=\s*[\"']([^\"']+)",
                        block,
                        flags=re.IGNORECASE,
                    )
                    if match:
                        versions.extend(_version_candidates(match.group(1)))
    except (OSError, zipfile.BadZipFile):
        pass

    return versions


def _modpack_jars(modpack_dir):
    return get_mod_jars("", modpack_dir)


def _installed_version_folders():
    versions_dir = os.path.join(MC_ROOT, "versions")
    if not os.path.isdir(versions_dir):
        return []

    return sorted(
        folder
        for folder in os.listdir(versions_dir)
        if os.path.isdir(os.path.join(versions_dir, folder))
        and folder.lower() != "delete me"
    )


def _resolve_installed_version(version_hint):
    matches = []
    for folder in _installed_version_folders():
        if (
            folder == version_hint
            or folder.startswith(version_hint + "-")
            or folder.startswith(version_hint + ".")
        ):
            matches.append(folder)

    if not matches:
        raise FileNotFoundError(
            f"Modpack requires Minecraft {version_hint}, but it is not installed."
        )

    if len(matches) > 1:
        raise RuntimeError(
            "More than one installed version matches "
            f"Minecraft {version_hint}: {', '.join(matches)}"
        )

    return matches[0]


def detect_minecraft_version(modpack_dir):
    """Resolve the version declared by a modpack instead of using a constant."""
    if not modpack_dir or not os.path.isdir(modpack_dir):
        raise ValueError("A valid modpack folder is required to detect its version.")

    declared_versions = []

    # Common modpack manifests, including CurseForge-style nested metadata.
    for root, _, names in os.walk(modpack_dir):
        for name in names:
            lower_name = name.lower()
            if lower_name in {
                "manifest.json",
                "modpack.json",
                "pack.json",
                "instance.json",
            }:
                declared_versions.extend(
                    _metadata_versions_from_json(os.path.join(root, name))
                )

    for jar_path in _modpack_jars(modpack_dir):
        declared_versions.extend(_metadata_versions_from_jar(jar_path))

    if declared_versions:
        counts = Counter(declared_versions)
        most_common = counts.most_common()
        if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
            raise RuntimeError(
                "The modpack declares multiple Minecraft versions: "
                + ", ".join(sorted(set(declared_versions)))
            )
        return _resolve_installed_version(most_common[0][0])

    # A pack without readable metadata is only safe when there is no choice
    # to make.  This avoids silently forcing every pack onto one version.
    installed = _installed_version_folders()
    if len(installed) == 1:
        return installed[0]

    if not installed:
        raise FileNotFoundError(
            "No installed Minecraft versions were found, and the modpack "
            "does not declare one."
        )

    raise RuntimeError(
        "The modpack does not declare a Minecraft version. Add a supported "
        "manifest or mod metadata before launching it."
    )


def build_launch_command(version_id: str = None, modpack_dir: str = None) -> list:
    acc = load_mc_account()

    username = acc["username"]
    uuid = acc["uuid"]
    access_token = acc["token"]

    if not version_id:
        version_id = detect_minecraft_version(modpack_dir)

    version_folder = find_version_folder(version_id)
    json_path = find_version_json(version_folder)

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        repair_asset_object_layout(version_folder, data)
        cp = build_json_classpath(version_id, data, modpack_dir)
        natives = get_natives_folder(version_id)

        jvm_args = build_jvm_args(data, natives, cp)
        game_args = build_game_args(
            data, username, uuid, access_token, version_folder
        )

        main_class = data.get("mainClass")
        if not main_class:
            raise ValueError("mainClass missing in version JSON")

        java_executable = find_java_executable(data)
        cmd = [java_executable] + jvm_args + ["-cp", cp, main_class] + game_args
        return cmd

    else:
        cp = build_old_classpath(version_id, modpack_dir)
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
    try:
        if len(sys.argv) < 2:
            raise ValueError("Usage: engine.pyw <modpack_folder>")

        modpack = os.path.abspath(sys.argv[1])
        version_hint = sys.argv[2].strip() if len(sys.argv) >= 3 else None
        if version_hint:
            version = _resolve_installed_version(version_hint)
        else:
            version = detect_minecraft_version(modpack)
        print("BASE:", BASE)
        print("MC_ROOT:", MC_ROOT)
        print("MODPACK:", modpack)
        print("MINECRAFT VERSION:", version)
        cmd = build_launch_command(version, modpack)
        print("Launch command:")
        print(" ".join(cmd))
        os.makedirs(os.path.join(MC_ROOT, "game"), exist_ok=True)
        subprocess.Popen(cmd, cwd=os.path.join(MC_ROOT, "game"))
    except Exception as e:
        print("Error:", e)