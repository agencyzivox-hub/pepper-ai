import os
import re
import subprocess
import importlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("\n🔍 PEPPER AI ADVANCED DEEP DEBUG STARTED...\n")


# ==============================
# 1. FILE STRUCTURE CHECK
# ==============================
print("📁 Checking project structure...\n")

required_paths = [
    "app.py",
    "processor",
    "static",
    "static/thumbnails",
    "templates",
]

for path in required_paths:
    full = os.path.join(BASE_DIR, path)
    if os.path.exists(full):
        print("✔ OK:", path)
    else:
        print("❌ MISSING:", path)


# ==============================
# 2. PYTHON IMPORT CHECK
# ==============================
print("\n📦 Checking imports...\n")

modules = [
    "flask",
    "flask_login",
    "sqlalchemy",
    "googleapiclient",
    "PIL",
]

for m in modules:
    try:
        importlib.import_module(m)
        print("✔ OK module:", m)
    except Exception as e:
        print("❌ ERROR module:", m, "=>", e)


# ==============================
# 3. THUMBNAIL FILE CHECK
# ==============================
print("\n🖼 Checking thumbnails...\n")

thumb_dir = os.path.join(BASE_DIR, "static", "thumbnails")

if os.path.exists(thumb_dir):
    files = os.listdir(thumb_dir)
    print("✔ Total thumbnails:", len(files))

    broken = [f for f in files if "thumb_" not in f]
    if broken:
        print("⚠ Suspicious files:", broken)
else:
    print("❌ Thumbnail folder missing")


# ==============================
# 4. BAD PATH DETECTION (IMPORTANT)
# ==============================
print("\n🚨 Checking broken Windows URL paths...\n")

bad_pattern = r"C:\\|C:/"

bad_files = []

for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if file.endswith(".py") or file.endswith(".js"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                    if re.search(bad_pattern, content):
                        bad_files.append(path)
            except:
                pass

if bad_files:
    print("❌ Found hardcoded Windows paths:")
    for b in bad_files:
        print("   →", b)
else:
    print("✔ No hardcoded Windows paths found")


# ==============================
# 5. TAG ERROR SIMULATION CHECK
# ==============================
print("\n🏷 Checking unsafe tag patterns...\n")

tag_issues = []

for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                    if "tags =" in content and ("[" in content or "json" in content):
                        if "len(" not in content:
                            tag_issues.append(path)
            except:
                pass

if tag_issues:
    print("⚠ Possible unsafe tag handling files:")
    for t in tag_issues:
        print("   →", t)
else:
    print("✔ Tag handling looks safe")


# ==============================
# 6. FLASK APP IMPORT TEST
# ==============================
print("\n⚙ Testing Flask app import...\n")

try:
    import app
    print("✔ Flask app imported successfully")
except Exception as e:
    print("❌ Flask app import error:", e)


# ==============================
# 7. FFmpeg CHECK
# ==============================
print("\n🎬 Checking FFmpeg...\n")

try:
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    if result.returncode == 0:
        print("✔ FFmpeg installed")
    else:
        print("❌ FFmpeg not working")
except:
    print("❌ FFmpeg not installed")


# ==============================
# FINAL REPORT
# ==============================
print("\n==============================")
print("📊 PEPPER AI FULL DEBUG REPORT")
print("==============================\n")

print("👉 If you see ❌ = fix required")
print("👉 If you see ✔ = OK system safe\n")

print("🚀 Debug Complete!\n")