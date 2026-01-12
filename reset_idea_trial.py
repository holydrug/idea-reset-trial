#!/usr/bin/env python3
"""
JetBrains IntelliJ IDEA Trial Reset Script
Works on macOS, Windows, and Linux

Removes:
- Config directories (IntelliJIdea*)
- Cache directories
- License files (bl, crl)
- Toolbox data
- Machine ID (UserIdOnMachine, device_id, etc.)
- Java preferences
- Windows registry keys
"""

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path


def run_cmd(cmd, shell=True):
    """Run command and return success status."""
    try:
        subprocess.run(cmd, shell=shell, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def get_jetbrains_paths():
    """Returns paths to JetBrains config/cache directories based on OS."""
    system = platform.system()
    home = Path.home()

    paths = {
        "config_dirs": [],
        "cache_dirs": [],
        "license_files": [],
        "preferences": [],
        "toolbox_data": [],
        "registry_keys": []
    }

    if system == "Darwin":  # macOS
        app_support = home / "Library" / "Application Support" / "JetBrains"
        caches = home / "Library" / "Caches" / "JetBrains"
        preferences = home / "Library" / "Preferences"

        if app_support.exists():
            paths["config_dirs"] = list(app_support.glob("IntelliJIdea*"))
            paths["license_files"] = [
                app_support / "bl",
                app_support / "crl",
                app_support / "consentOptions",
            ]

            toolbox = app_support / "Toolbox"
            if toolbox.exists():
                paths["toolbox_data"] = [toolbox]

        if caches.exists():
            paths["cache_dirs"] = list(caches.glob("IntelliJIdea*"))
            paths["cache_dirs"].extend(caches.glob("Toolbox*"))

        if preferences.exists():
            paths["preferences"] = list(preferences.glob("jetbrains*.plist"))
            paths["preferences"].extend(preferences.glob("com.jetbrains*.plist"))
            # Java prefs with machine ID
            java_prefs = preferences / "com.apple.java.util.prefs.plist"
            if java_prefs.exists():
                paths["preferences"].append(java_prefs)

    elif system == "Windows":
        appdata = Path(os.environ.get("APPDATA", ""))
        localappdata = Path(os.environ.get("LOCALAPPDATA", ""))

        jb_roaming = appdata / "JetBrains"
        if jb_roaming.exists():
            paths["config_dirs"] = list(jb_roaming.glob("IntelliJIdea*"))
            paths["license_files"] = [
                jb_roaming / "bl",
                jb_roaming / "crl",
                jb_roaming / "consentOptions",
            ]

            toolbox = jb_roaming / "Toolbox"
            if toolbox.exists():
                paths["toolbox_data"] = [toolbox]

        jb_local = localappdata / "JetBrains"
        if jb_local.exists():
            paths["cache_dirs"] = list(jb_local.glob("IntelliJIdea*"))
            paths["cache_dirs"].extend(jb_local.glob("Toolbox*"))

        # Windows registry keys for machine ID
        paths["registry_keys"] = [
            r"SOFTWARE\JavaSoft\Prefs\jetbrains",
            r"SOFTWARE\JetBrains",
        ]

    else:  # Linux
        config = home / ".config" / "JetBrains"
        cache = home / ".cache" / "JetBrains"
        local = home / ".local" / "share" / "JetBrains"

        if config.exists():
            paths["config_dirs"] = list(config.glob("IntelliJIdea*"))
        if cache.exists():
            paths["cache_dirs"] = list(cache.glob("IntelliJIdea*"))
        if local.exists():
            paths["license_files"] = [
                local / "bl",
                local / "crl",
                local / "consentOptions",
            ]

            toolbox = local / "Toolbox"
            if toolbox.exists():
                paths["toolbox_data"] = [toolbox]

        # Java preferences
        java_prefs = home / ".java" / ".userPrefs" / "jetbrains"
        if java_prefs.exists():
            paths["preferences"].append(java_prefs)

        # Prefs root
        prefs_root = home / ".java" / ".userPrefs"
        if prefs_root.exists():
            paths["preferences"].append(prefs_root)

    return paths


def delete_macos_java_prefs():
    """Delete macOS Java preferences containing machine ID."""
    if platform.system() != "Darwin":
        return

    print("\n[Machine ID (Java Prefs)]")

    # Delete entire java.util.prefs domain (contains JetBrains.UserIdOnMachine)
    if run_cmd('defaults delete com.apple.java.util.prefs "/" 2>/dev/null'):
        print("  [OK] Deleted com.apple.java.util.prefs")
    else:
        print("  [--] com.apple.java.util.prefs not found or already empty")


def delete_windows_registry_keys(keys):
    """Delete Windows registry keys related to JetBrains."""
    if platform.system() != "Windows":
        return

    print("\n[Windows Registry]")

    try:
        import winreg

        def delete_key_recursive(hkey, key_path):
            try:
                key = winreg.OpenKey(hkey, key_path, 0, winreg.KEY_ALL_ACCESS)
                # Delete subkeys first
                while True:
                    try:
                        subkey = winreg.EnumKey(key, 0)
                        delete_key_recursive(hkey, f"{key_path}\\{subkey}")
                    except OSError:
                        break
                winreg.CloseKey(key)
                winreg.DeleteKey(hkey, key_path)
                return True
            except FileNotFoundError:
                return False
            except Exception:
                return False

        for key_path in keys:
            if delete_key_recursive(winreg.HKEY_CURRENT_USER, key_path):
                print(f"  [OK] Deleted HKCU\\{key_path}")
            else:
                print(f"  [--] Not found: HKCU\\{key_path}")

    except ImportError:
        print("  [!!] winreg module not available")


def safe_delete(path: Path, dry_run: bool = False):
    """Safely delete a file or directory."""
    if not path.exists():
        print(f"  [--] Not found: {path}")
        return False

    try:
        if dry_run:
            print(f"  [DRY] Would delete: {path}")
            return True

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"  [OK] Deleted: {path}")
        return True
    except PermissionError:
        print(f"  [!!] Permission denied: {path}")
        return False
    except Exception as e:
        print(f"  [!!] Error deleting {path}: {e}")
        return False


def main():
    print("=" * 60)
    print("JetBrains IntelliJ IDEA Trial Reset")
    print(f"OS: {platform.system()} {platform.release()}")
    print("=" * 60)

    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    if dry_run:
        print("\n[DRY RUN MODE - no files will be deleted]\n")

    paths = get_jetbrains_paths()
    deleted_count = 0

    print("\n[Config directories]")
    for path in paths["config_dirs"]:
        if safe_delete(path, dry_run):
            deleted_count += 1
    if not paths["config_dirs"]:
        print("  No config directories found")

    print("\n[Cache directories]")
    for path in paths["cache_dirs"]:
        if safe_delete(path, dry_run):
            deleted_count += 1
    if not paths["cache_dirs"]:
        print("  No cache directories found")

    print("\n[License files]")
    for path in paths["license_files"]:
        if safe_delete(path, dry_run):
            deleted_count += 1
    if not paths["license_files"]:
        print("  No license files found")

    print("\n[Toolbox data]")
    for path in paths["toolbox_data"]:
        if safe_delete(path, dry_run):
            deleted_count += 1
    if not paths["toolbox_data"]:
        print("  No Toolbox data found")

    print("\n[Preferences]")
    for path in paths["preferences"]:
        if safe_delete(path, dry_run):
            deleted_count += 1
    if not paths["preferences"]:
        print("  No preference files found")

    # Platform-specific cleanup
    if not dry_run:
        if platform.system() == "Darwin":
            delete_macos_java_prefs()
        elif platform.system() == "Windows":
            delete_windows_registry_keys(paths["registry_keys"])

    print("\n" + "=" * 60)
    print(f"Done! Trial reset complete.")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Restart your computer (recommended) or log out/in")
    print("2. Launch IntelliJ IDEA")
    print("3. You should get a fresh 30-day trial")


if __name__ == "__main__":
    main()
