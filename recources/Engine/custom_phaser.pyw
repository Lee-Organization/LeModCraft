import os
import json
import subprocess
import sys

# ============================================================
#  FORCE ABSOLUTE PATH ENGINE RESOLUTION
# ============================================================

def resolve_engine(name):
    script_dir = os.path.dirname(os.path.abspath(__file__))

    exe = os.path.join(script_dir, name + ".exe")
    pyw = os.path.join(script_dir, name + ".pyw")

    print("DEBUG: script_dir =", script_dir)
    print("DEBUG: checking:", exe)
    print("DEBUG: checking:", pyw)

    if os.path.exists(exe):
        print("DEBUG: FOUND:", exe)
        return exe

    if os.path.exists(pyw):
        print("DEBUG: FOUND:", pyw)
        return pyw

    raise Exception(f"Engine not found in {script_dir}: {name}.exe or {name}.pyw")


# ============================================================
#  UTILITIES
# ============================================================

def abs_path(base, rel):
    return os.path.normpath(os.path.join(base, rel))

def run_engine(engine_path, args):
    engine_path = os.path.normpath(engine_path)

    if engine_path.endswith(".exe"):
        subprocess.Popen([engine_path] + args)
        return

    if engine_path.endswith(".py") or engine_path.endswith(".pyw"):
        subprocess.Popen([sys.executable, engine_path] + args)
        return

    if os.path.exists(engine_path):
        subprocess.Popen([engine_path] + args)
        return

    raise Exception(f"Unknown engine type or missing engine: {engine_path}")


# ============================================================
#  CUSTOM PACK DETECTION
# ============================================================

def is_custom_module(base_dir):
    for f in os.listdir(base_dir):
        # Skip the mod folder entirely
        if f.lower() == "mod" or f.lower() == "mods":
            continue

        # Check only top-level files
        if f.endswith(".main.lmc"):
            return True

    return False


# ============================================================
#  NORMAL MODE (ONLY IF CUSTOM FAILS)
# ============================================================

def detect_normal_engine(base_dir):
    mod_count = len([f for f in os.listdir(base_dir) if f.endswith(".jar")])

    if mod_count < 20:
        return "regular"
    elif mod_count < 80:
        return "heavy"
    else:
        return "super"

def launch_normal_mods(base_dir):
    engine = detect_normal_engine(base_dir)

    if engine == "regular":
        engine_path = resolve_engine("engine")
    elif engine == "heavy":
        engine_path = resolve_engine("heavy_engine")
    else:
        engine_path = resolve_engine("super_engine")

    print(f"[NORMAL MODE] Launching {engine} engine...")
    run_engine(engine_path, [base_dir])


# ============================================================
#  CUSTOM MODE CONTEXT
# ============================================================

class Context:
    def __init__(self, base):
        self.base = base
        self.loaded_lmc = set()
        self.loaded_jars = set()
        self.config = {}
        self.thumbnail = None
        self.mods = []

    def path(self, rel):
        return abs_path(self.base, rel)


# ------------------------------------------------------------
#  LOAD .main.lmc (MINIMAL FORMAT SUPPORTED)
# ------------------------------------------------------------

REQUIRED_MAIN = [
    "name",
    "version",
    "type",
    "startup",
    "info",
    "config",
    "resources",
    "helpers",
    "thumbnail",
    "mods",
    "arguments"
]

def load_main_lmc(path):
    with open(path, "r") as f:
        data = json.load(f)

    for key in REQUIRED_MAIN:
        if key not in data:
            raise Exception(f"Missing required field in .main.lmc: {key}")

    return data


# ------------------------------------------------------------
#  LOAD .lmc
# ------------------------------------------------------------

def load_lmc(path, ctx):
    path = os.path.normpath(path)
    if not path or not os.path.exists(path):
        print("[WARNING] Missing LMC:", path)
        return {}

    if path in ctx.loaded_lmc:
        return {}

    ctx.loaded_lmc.add(path)

    with open(path, "r") as f:
        return json.load(f)


# ------------------------------------------------------------
#  HANDLE .lmc
# ------------------------------------------------------------

def handle_lmc(data, ctx):
    if "jar" in data:
        jar_path = ctx.path(data["jar"])
        if os.path.exists(jar_path):
            run_jar(jar_path, ctx)
        else:
            print("[WARNING] Missing JAR:", jar_path)

    for jar in data.get("load_jars", []):
        jar_path = ctx.path(jar)
        if os.path.exists(jar_path):
            run_jar(jar_path, ctx)
        else:
            print("[WARNING] Missing JAR:", jar_path)

    for lmc in data.get("load_lmc", []):
        child = load_lmc(ctx.path(lmc), ctx)
        handle_lmc(child, ctx)

    if "load_config" in data:
        load_config(ctx.path(data["load_config"]), ctx)


# ------------------------------------------------------------
#  LOAD CONFIG.JSON (EMPTY ALLOWED)
# ------------------------------------------------------------

def load_config(path, ctx):
    if not path or not os.path.exists(path):
        print("[WARNING] Missing config:", path)
        return

    with open(path, "r") as f:
        try:
            cfg = json.load(f)
        except:
            cfg = {}

    ctx.config.update(cfg)

    if "thumbnail" in cfg:
        ctx.thumbnail = ctx.path(cfg["thumbnail"])

    for lmc in cfg.get("load_modules", []):
        child = load_lmc(ctx.path(lmc), ctx)
        handle_lmc(child, ctx)

    for mod in cfg.get("mods", []):
        if mod:
            ctx.mods.append(ctx.path(mod))


# ------------------------------------------------------------
#  RUN .jar
# ------------------------------------------------------------

def run_jar(path, ctx):
    path = os.path.normpath(path)
    if path in ctx.loaded_jars:
        return

    ctx.loaded_jars.add(path)
    # subprocess.Popen(["java", "-jar", path])


# ------------------------------------------------------------
#  CUSTOM ENGINE DETECTION (BY MOD COUNT)
# ------------------------------------------------------------

def detect_custom_engine(ctx):
    mod_count = len(ctx.mods)

    if mod_count < 20:
        return "regular"
    elif mod_count < 80:
        return "heavy"
    else:
        return "super"


# ------------------------------------------------------------
#  CUSTOM MODE ENTRY
# ------------------------------------------------------------

def run_custom(base_dir):
    ctx = Context(base_dir)

    # Find .main.lmc
    main_file = None
    for f in os.listdir(base_dir):
        if f.endswith(".main.lmc"):
            main_file = abs_path(base_dir, f)
            break

    if not main_file:
        raise Exception("No .main.lmc found in custom mode.")

    main_data = load_main_lmc(main_file)

    # STARTUP
    if main_data.get("startup"):
        startup = load_lmc(ctx.path(main_data["startup"]), ctx)
        handle_lmc(startup, ctx)
    else:
        print("[WARNING] No startup file defined.")

    # CONFIG
    if main_data.get("config"):
        load_config(ctx.path(main_data["config"]), ctx)
    else:
        print("[WARNING] No config file defined.")

    # MODS ROOT
    if main_data.get("mods"):
        ctx.mods.append(ctx.path(main_data["mods"]))

    # ENGINE TYPE (modern / heavy / super)
    engine = main_data.get("engine", None)
    if engine is None:
        raise Exception("Missing 'engine' field in .main.lmc")

    if engine == "modern":
        engine_path = resolve_engine("engine")      # your custom engine
    elif engine == "heavy":
        engine_path = resolve_engine("heavy_engine")
    elif engine == "super":
        engine_path = resolve_engine("super_engine")
    else:
        raise Exception(f"Unknown custom engine type: {engine}")

    print(f"[CUSTOM MODE] Launching {engine} engine...")
    # Pass base_dir to engine; engine itself will handle Minecraft version folders
    run_engine(engine_path, [base_dir])


# ============================================================
#  MAIN ENTRY
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: custom_phaser.pyw <module_folder>")
        return

    base_dir = sys.argv[1]

    if is_custom_module(base_dir):
        print(f"[CUSTOM PACK] {os.path.basename(base_dir)} → running custom phaser...")
        run_custom(base_dir)
    else:
        print(f"[NORMAL PACK] {os.path.basename(base_dir)} → running normal mode...")
        launch_normal_mods(base_dir)


if __name__ == "__main__":
    main()
