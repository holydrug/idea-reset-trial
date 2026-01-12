#!/usr/bin/env python3
"""
JetBrains IntelliJ IDEA Trial Reset Script
Works on macOS, Windows, and Linux

Removes:
- Config directories (IntelliJIdea*)
- Cache directories
- License files (bl, crl)
- Toolbox trial data (Toolbox itself is preserved!)
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
from dataclasses import dataclass
from typing import List, Optional, Callable

# ============================================================================
# Result types for structured error handling
# ============================================================================

@dataclass
class CommandResult:
    """Result of a command execution."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error: Optional[Exception] = None


@dataclass
class DeleteResult:
    """Result of a delete operation."""
    success: bool
    path: Path
    message: str
    error: Optional[Exception] = None


# ============================================================================
# Output abstraction (replaces direct print calls)
# ============================================================================

class Output:
    """Abstraction for output handling - enables testing and logging switch."""
    
    def __init__(self, printer: Callable[[str], None] = print):
        self._print = printer
    
    def info(self, msg: str):
        self._print(msg)
    
    def ok(self, msg: str):
        self._print(f"  [OK] {msg}")
    
    def skip(self, msg: str):
        self._print(f"  [--] {msg}")
    
    def error(self, msg: str):
        self._print(f"  [!!] {msg}")
    
    def dry(self, msg: str):
        self._print(f"  [DRY] {msg}")
    
    def section(self, title: str):
        self._print(f"\n[{title}]")


# Default output instance
output = Output()


# ============================================================================
# Command execution
# ============================================================================

def run_cmd(cmd: List[str], shell: bool = False) -> CommandResult:
    """
    Run command and return structured result.
    
    Args:
        cmd: Command as list of arguments (preferred) or string if shell=True
        shell: Whether to run through shell (avoid when possible)
    
    Returns:
        CommandResult with success status, output, and error details
    """
    try:
        result = subprocess.run(
            cmd, 
            shell=shell, 
            check=True, 
            capture_output=True,
            text=True
        )
        return CommandResult(
            success=True,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=0
        )
    except subprocess.CalledProcessError as e:
        return CommandResult(
            success=False,
            stdout=e.stdout or "",
            stderr=e.stderr or "",
            exit_code=e.returncode,
            error=e
        )
    except FileNotFoundError as e:
        return CommandResult(
            success=False,
            error=e,
            exit_code=-1
        )


# ============================================================================
# Windows-specific paths and environment
# ============================================================================

@dataclass
class WindowsEnv:
    """Windows environment paths with validation."""
    appdata: Optional[Path]
    localappdata: Optional[Path]
    is_valid: bool
    errors: List[str]
    
    @classmethod
    def detect(cls) -> "WindowsEnv":
        """Detect and validate Windows environment variables."""
        errors = []
        
        # APPDATA
        appdata_str = os.environ.get("APPDATA")
        appdata = None
        if appdata_str:
            appdata = Path(appdata_str)
            if not appdata.exists():
                errors.append(f"APPDATA path does not exist: {appdata}")
                appdata = None
        else:
            errors.append("APPDATA environment variable not set")
        
        # LOCALAPPDATA
        localappdata_str = os.environ.get("LOCALAPPDATA")
        localappdata = None
        if localappdata_str:
            localappdata = Path(localappdata_str)
            if not localappdata.exists():
                errors.append(f"LOCALAPPDATA path does not exist: {localappdata}")
                localappdata = None
        else:
            errors.append("LOCALAPPDATA environment variable not set")
        
        # Fallback to standard paths if env vars missing
        if appdata is None:
            fallback = Path.home() / "AppData" / "Roaming"
            if fallback.exists():
                appdata = fallback
                errors = [e for e in errors if "APPDATA" not in e]
        
        if localappdata is None:
            fallback = Path.home() / "AppData" / "Local"
            if fallback.exists():
                localappdata = fallback
                errors = [e for e in errors if "LOCALAPPDATA" not in e]
        
        return cls(
            appdata=appdata,
            localappdata=localappdata,
            is_valid=appdata is not None or localappdata is not None,
            errors=errors
        )


# ============================================================================
# Windows Registry operations
# ============================================================================

class WindowsRegistry:
    """Windows registry operations with proper error handling."""
    
    # Registry key paths for JetBrains
    JETBRAINS_KEYS = [
        r"SOFTWARE\JavaSoft\Prefs\jetbrains",
        r"SOFTWARE\JavaSoft\Prefs\jetbrains\idea",
        r"SOFTWARE\JetBrains",
        r"SOFTWARE\JetBrains\IntelliJ IDEA",
    ]
    
    def __init__(self):
        self._winreg = None
        self._available = False
        self._import_error: Optional[str] = None
        
        try:
            import winreg
            self._winreg = winreg
            self._available = True
        except ImportError as e:
            self._import_error = str(e)
    
    @property
    def available(self) -> bool:
        return self._available
    
    @property
    def import_error(self) -> Optional[str]:
        return self._import_error
    
    def delete_key_recursive(self, hkey, key_path: str) -> DeleteResult:
        """
        Recursively delete a registry key and all its subkeys.
        
        Args:
            hkey: Registry hive (e.g., HKEY_CURRENT_USER)
            key_path: Path to the key to delete
        
        Returns:
            DeleteResult with operation status
        """
        if not self._available:
            return DeleteResult(
                success=False,
                path=Path(key_path),
                message="winreg module not available",
                error=ImportError(self._import_error)
            )
        
        winreg = self._winreg
        
        try:
            # Open key with full access
            key = winreg.OpenKey(hkey, key_path, 0, winreg.KEY_ALL_ACCESS)
        except FileNotFoundError:
            return DeleteResult(
                success=False,
                path=Path(key_path),
                message="Key not found"
            )
        except PermissionError as e:
            return DeleteResult(
                success=False,
                path=Path(key_path),
                message=f"Permission denied: {e}",
                error=e
            )
        except OSError as e:
            return DeleteResult(
                success=False,
                path=Path(key_path),
                message=f"Cannot open key: {e}",
                error=e
            )
        
        try:
            # Delete all subkeys first (required by Windows)
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, 0)
                    subkey_path = f"{key_path}\\{subkey_name}"
                    sub_result = self.delete_key_recursive(hkey, subkey_path)
                    if not sub_result.success and sub_result.error:
                        # Propagate errors from subkey deletion
                        winreg.CloseKey(key)
                        return sub_result
                except OSError:
                    # No more subkeys
                    break
            
            winreg.CloseKey(key)
            
            # Now delete the key itself
            winreg.DeleteKey(hkey, key_path)
            
            return DeleteResult(
                success=True,
                path=Path(key_path),
                message="Deleted successfully"
            )
            
        except PermissionError as e:
            return DeleteResult(
                success=False,
                path=Path(key_path),
                message=f"Permission denied during deletion: {e}",
                error=e
            )
        except OSError as e:
            return DeleteResult(
                success=False,
                path=Path(key_path),
                message=f"Error during deletion: {e}",
                error=e
            )
    
    def delete_jetbrains_keys(self, dry_run: bool = False) -> List[DeleteResult]:
        """Delete all JetBrains-related registry keys."""
        results = []
        
        if not self._available:
            return [DeleteResult(
                success=False,
                path=Path("REGISTRY"),
                message=f"winreg module not available: {self._import_error}"
            )]
        
        winreg = self._winreg
        
        for key_path in self.JETBRAINS_KEYS:
            if dry_run:
                # Check if key exists for dry run
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
                    winreg.CloseKey(key)
                    results.append(DeleteResult(
                        success=True,
                        path=Path(f"HKCU\\{key_path}"),
                        message="Would delete"
                    ))
                except FileNotFoundError:
                    results.append(DeleteResult(
                        success=False,
                        path=Path(f"HKCU\\{key_path}"),
                        message="Not found"
                    ))
                except OSError as e:
                    results.append(DeleteResult(
                        success=False,
                        path=Path(f"HKCU\\{key_path}"),
                        message=f"Cannot access: {e}",
                        error=e
                    ))
            else:
                result = self.delete_key_recursive(winreg.HKEY_CURRENT_USER, key_path)
                # Update path to include hive name for display
                result.path = Path(f"HKCU\\{key_path}")
                results.append(result)
        
        return results


# ============================================================================
# Path collection
# ============================================================================

def get_jetbrains_paths():
    """Returns paths to JetBrains config/cache directories based on OS."""
    system = platform.system()
    home = Path.home()

    paths = {
        "config_dirs": [],
        "cache_dirs": [],
        "license_files": [],
        "preferences": [],
        "toolbox_data": [],           # Legacy - not used anymore
        "toolbox_trial_files": [],    # Trial-related files inside Toolbox (keeps Toolbox itself)
        "eval_dirs": [],              # Trial evaluation data
        "eval_files": [],             # Trial-related files (other.xml)
        "hidden_dirs": [],            # Hidden .JetBrains directories
        "registry_keys": [],          # Kept for compatibility, but handled by WindowsRegistry
        "env_errors": []              # For reporting environment issues
    }

    if system == "Darwin":  # macOS
        app_support = home / "Library" / "Application Support" / "JetBrains"
        caches = home / "Library" / "Caches" / "JetBrains"
        preferences = home / "Library" / "Preferences"

        if app_support.exists():
            paths["config_dirs"] = list(app_support.glob("IntelliJIdea*"))
            
            # Eval folders inside config dirs (trial tracking)
            for config_dir in paths["config_dirs"]:
                eval_dir = config_dir / "eval"
                if eval_dir.exists():
                    paths["eval_dirs"].append(eval_dir)
                # options/other.xml contains evlsprt data
                other_xml = config_dir / "options" / "other.xml"
                if other_xml.exists():
                    paths["eval_files"].append(other_xml)
            
            paths["license_files"] = [
                app_support / "bl",
                app_support / "crl",
                app_support / "consentOptions",
                app_support / "PermanentDeviceId",
                app_support / "PermanentUserId",
            ]

            # Toolbox trial files (preserve Toolbox itself, only delete trial data)
            toolbox = app_support / "Toolbox"
            if toolbox.exists():
                toolbox_trial_patterns = [
                    ".uid", "state.json", ".state.json", "device_id", ".device_id",
                ]
                for pattern in toolbox_trial_patterns:
                    trial_file = toolbox / pattern
                    if trial_file.exists():
                        paths["toolbox_trial_files"].append(trial_file)

                toolbox_cache = toolbox / "cache"
                if toolbox_cache.exists():
                    paths["toolbox_trial_files"].append(toolbox_cache)

                toolbox_apps = toolbox / "apps"
                if toolbox_apps.exists():
                    for app_dir in toolbox_apps.iterdir():
                        if app_dir.is_dir():
                            for channel in app_dir.iterdir():
                                if channel.is_dir():
                                    eval_dir = channel / "eval"
                                    if eval_dir.exists():
                                        paths["toolbox_trial_files"].append(eval_dir)

        if caches.exists():
            paths["cache_dirs"] = list(caches.glob("IntelliJIdea*"))
            # Note: Toolbox cache preserved

        if preferences.exists():
            paths["preferences"] = list(preferences.glob("jetbrains*.plist"))
            paths["preferences"].extend(preferences.glob("com.jetbrains*.plist"))
            java_prefs = preferences / "com.apple.java.util.prefs.plist"
            if java_prefs.exists():
                paths["preferences"].append(java_prefs)
        
        # Hidden .JetBrains in home
        hidden_jb = home / ".JetBrains"
        if hidden_jb.exists():
            paths["hidden_dirs"].append(hidden_jb)

    elif system == "Windows":
        # Use validated Windows environment
        win_env = WindowsEnv.detect()
        paths["env_errors"] = win_env.errors
        
        if win_env.appdata:
            jb_roaming = win_env.appdata / "JetBrains"
            if jb_roaming.exists():
                paths["config_dirs"] = list(jb_roaming.glob("IntelliJIdea*"))
                
                # Eval folders inside config dirs (trial tracking)
                for config_dir in paths["config_dirs"]:
                    eval_dir = config_dir / "eval"
                    if eval_dir.exists():
                        paths["eval_dirs"].append(eval_dir)
                    # options/other.xml contains evlsprt data
                    other_xml = config_dir / "options" / "other.xml"
                    if other_xml.exists():
                        paths["eval_files"].append(other_xml)
                
                paths["license_files"] = [
                    jb_roaming / "bl",
                    jb_roaming / "crl",
                    jb_roaming / "consentOptions",
                    jb_roaming / "PermanentDeviceId",
                    jb_roaming / "PermanentUserId",
                ]

                # Toolbox trial files (preserve Toolbox itself, only delete trial data)
                toolbox = jb_roaming / "Toolbox"
                if toolbox.exists():
                    # Files to delete inside Toolbox for trial reset
                    toolbox_trial_patterns = [
                        ".uid",                    # User ID
                        "state.json",              # State with trial info
                        ".state.json",
                        "device_id",
                        ".device_id",
                    ]
                    for pattern in toolbox_trial_patterns:
                        trial_file = toolbox / pattern
                        if trial_file.exists():
                            paths["toolbox_trial_files"].append(trial_file)

                    # Cache inside Toolbox
                    toolbox_cache = toolbox / "cache"
                    if toolbox_cache.exists():
                        paths["toolbox_trial_files"].append(toolbox_cache)

                    # Eval dirs inside Toolbox apps
                    toolbox_apps = toolbox / "apps"
                    if toolbox_apps.exists():
                        for app_dir in toolbox_apps.iterdir():
                            if app_dir.is_dir():
                                for channel in app_dir.iterdir():
                                    if channel.is_dir():
                                        eval_dir = channel / "eval"
                                        if eval_dir.exists():
                                            paths["toolbox_trial_files"].append(eval_dir)

        if win_env.localappdata:
            jb_local = win_env.localappdata / "JetBrains"
            if jb_local.exists():
                paths["cache_dirs"] = list(jb_local.glob("IntelliJIdea*"))
                # Note: Toolbox cache in LOCALAPPDATA is preserved
        
        # Hidden .JetBrains in user profile
        hidden_jb = home / ".JetBrains"
        if hidden_jb.exists():
            paths["hidden_dirs"].append(hidden_jb)

    else:  # Linux
        # Support XDG Base Directory Specification
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        xdg_data = os.environ.get("XDG_DATA_HOME")
        
        config = Path(xdg_config) / "JetBrains" if xdg_config else home / ".config" / "JetBrains"
        cache = Path(xdg_cache) / "JetBrains" if xdg_cache else home / ".cache" / "JetBrains"
        local = Path(xdg_data) / "JetBrains" if xdg_data else home / ".local" / "share" / "JetBrains"

        if config.exists():
            paths["config_dirs"] = list(config.glob("IntelliJIdea*"))
            
            # Eval folders inside config dirs (trial tracking)
            for config_dir in paths["config_dirs"]:
                eval_dir = config_dir / "eval"
                if eval_dir.exists():
                    paths["eval_dirs"].append(eval_dir)
                # options/other.xml contains evlsprt data
                other_xml = config_dir / "options" / "other.xml"
                if other_xml.exists():
                    paths["eval_files"].append(other_xml)
                    
        if cache.exists():
            paths["cache_dirs"] = list(cache.glob("IntelliJIdea*"))
        if local.exists():
            paths["license_files"] = [
                local / "bl",
                local / "crl",
                local / "consentOptions",
                local / "PermanentDeviceId",
                local / "PermanentUserId",
            ]

            # Toolbox trial files (preserve Toolbox itself, only delete trial data)
            toolbox = local / "Toolbox"
            if toolbox.exists():
                toolbox_trial_patterns = [
                    ".uid", "state.json", ".state.json", "device_id", ".device_id",
                ]
                for pattern in toolbox_trial_patterns:
                    trial_file = toolbox / pattern
                    if trial_file.exists():
                        paths["toolbox_trial_files"].append(trial_file)

                toolbox_cache = toolbox / "cache"
                if toolbox_cache.exists():
                    paths["toolbox_trial_files"].append(toolbox_cache)

                toolbox_apps = toolbox / "apps"
                if toolbox_apps.exists():
                    for app_dir in toolbox_apps.iterdir():
                        if app_dir.is_dir():
                            for channel in app_dir.iterdir():
                                if channel.is_dir():
                                    eval_dir = channel / "eval"
                                    if eval_dir.exists():
                                        paths["toolbox_trial_files"].append(eval_dir)

        java_prefs = home / ".java" / ".userPrefs" / "jetbrains"
        if java_prefs.exists():
            paths["preferences"].append(java_prefs)

        prefs_root = home / ".java" / ".userPrefs"
        if prefs_root.exists():
            paths["preferences"].append(prefs_root)
        
        # Hidden .JetBrains in home
        hidden_jb = home / ".JetBrains"
        if hidden_jb.exists():
            paths["hidden_dirs"].append(hidden_jb)

    return paths


# ============================================================================
# macOS-specific operations
# ============================================================================

def delete_macos_java_prefs(dry_run: bool = False) -> Optional[CommandResult]:
    """Delete macOS Java preferences containing machine ID."""
    if platform.system() != "Darwin":
        return None

    output.section("Machine ID (Java Prefs)")

    if dry_run:
        output.dry("Would delete com.apple.java.util.prefs")
        return CommandResult(success=True)

    # Use list form instead of shell=True
    result = run_cmd(["defaults", "delete", "com.apple.java.util.prefs", "/"])
    
    if result.success:
        output.ok("Deleted com.apple.java.util.prefs")
    else:
        output.skip("com.apple.java.util.prefs not found or already empty")
    
    return result


def delete_windows_registry(dry_run: bool = False) -> List[DeleteResult]:
    """Delete Windows registry keys related to JetBrains."""
    if platform.system() != "Windows":
        return []

    output.section("Windows Registry")
    
    registry = WindowsRegistry()
    
    if not registry.available:
        output.error(f"winreg module not available: {registry.import_error}")
        return []
    
    results = registry.delete_jetbrains_keys(dry_run=dry_run)
    
    for result in results:
        if dry_run:
            if result.success:
                output.dry(f"Would delete: {result.path}")
            else:
                output.skip(f"Not found: {result.path}")
        else:
            if result.success:
                output.ok(f"Deleted: {result.path}")
            elif result.error:
                output.error(f"{result.message}: {result.path}")
            else:
                output.skip(f"Not found: {result.path}")
    
    return results


# ============================================================================
# File system operations
# ============================================================================

def safe_delete(path: Path, dry_run: bool = False) -> DeleteResult:
    """
    Safely delete a file or directory.
    
    Uses atomic check-and-delete pattern where possible.
    """
    if dry_run:
        if path.exists():
            output.dry(f"Would delete: {path}")
            return DeleteResult(success=True, path=path, message="Would delete")
        else:
            output.skip(f"Not found: {path}")
            return DeleteResult(success=False, path=path, message="Not found")
    
    try:
        # Attempt deletion directly - handles TOCTOU better than check-then-delete
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        
        output.ok(f"Deleted: {path}")
        return DeleteResult(success=True, path=path, message="Deleted")
        
    except FileNotFoundError:
        output.skip(f"Not found: {path}")
        return DeleteResult(success=False, path=path, message="Not found")
    except PermissionError as e:
        output.error(f"Permission denied: {path}")
        return DeleteResult(success=False, path=path, message="Permission denied", error=e)
    except OSError as e:
        output.error(f"Error deleting {path}: {e}")
        return DeleteResult(success=False, path=path, message=str(e), error=e)


# ============================================================================
# Argument parsing
# ============================================================================

def parse_args(argv: List[str]) -> dict:
    """Parse command line arguments."""
    args = {
        "dry_run": False,
        "help": False,
        "unknown": []
    }
    
    valid_flags = {
        "--dry-run": "dry_run",
        "-n": "dry_run",
        "--help": "help",
        "-h": "help",
    }
    
    for arg in argv[1:]:  # Skip script name
        if arg in valid_flags:
            args[valid_flags[arg]] = True
        elif arg.startswith("-"):
            args["unknown"].append(arg)
    
    return args


def print_help():
    """Print usage information."""
    print("""
JetBrains IntelliJ IDEA Trial Reset Script

Usage: python reset_idea_trial.py [options]

Options:
    -n, --dry-run    Show what would be deleted without actually deleting
    -h, --help       Show this help message

This script removes JetBrains trial-related files and settings:
    - Config directories (IntelliJIdea*)
    - Cache directories
    - License files (bl, crl)
    - Toolbox trial data (Toolbox itself is preserved!)
    - Machine ID and Java preferences
    - Windows registry keys (on Windows)
""")


# ============================================================================
# Main
# ============================================================================

def main():
    args = parse_args(sys.argv)
    
    if args["help"]:
        print_help()
        return 0
    
    if args["unknown"]:
        output.error(f"Unknown arguments: {', '.join(args['unknown'])}")
        output.info("Use --help for usage information")
        return 1
    
    dry_run = args["dry_run"]
    
    output.info("=" * 60)
    output.info("JetBrains IntelliJ IDEA Trial Reset")
    output.info(f"OS: {platform.system()} {platform.release()}")
    output.info("=" * 60)

    if dry_run:
        output.info("\n[DRY RUN MODE - no files will be deleted]\n")

    paths = get_jetbrains_paths()
    
    # Report any environment issues
    if paths.get("env_errors"):
        output.section("Environment Warnings")
        for error in paths["env_errors"]:
            output.error(error)

    deleted_count = 0

    output.section("Config directories")
    for path in paths["config_dirs"]:
        if safe_delete(path, dry_run).success:
            deleted_count += 1
    if not paths["config_dirs"]:
        output.info("  No config directories found")

    output.section("Cache directories")
    for path in paths["cache_dirs"]:
        if safe_delete(path, dry_run).success:
            deleted_count += 1
    if not paths["cache_dirs"]:
        output.info("  No cache directories found")

    output.section("License files")
    for path in paths["license_files"]:
        if safe_delete(path, dry_run).success:
            deleted_count += 1
    if not paths["license_files"]:
        output.info("  No license files found")

    output.section("Toolbox trial data (Toolbox preserved)")
    for path in paths["toolbox_trial_files"]:
        if safe_delete(path, dry_run).success:
            deleted_count += 1
    if not paths["toolbox_trial_files"]:
        output.info("  No Toolbox trial files found")

    output.section("Preferences")
    for path in paths["preferences"]:
        if safe_delete(path, dry_run).success:
            deleted_count += 1
    if not paths["preferences"]:
        output.info("  No preference files found")

    output.section("Eval directories (trial data)")
    for path in paths["eval_dirs"]:
        if safe_delete(path, dry_run).success:
            deleted_count += 1
    if not paths["eval_dirs"]:
        output.info("  No eval directories found")

    output.section("Eval files (other.xml)")
    for path in paths["eval_files"]:
        if safe_delete(path, dry_run).success:
            deleted_count += 1
    if not paths["eval_files"]:
        output.info("  No eval files found")

    output.section("Hidden JetBrains directories")
    for path in paths["hidden_dirs"]:
        if safe_delete(path, dry_run).success:
            deleted_count += 1
    if not paths["hidden_dirs"]:
        output.info("  No hidden directories found")

    # Platform-specific cleanup
    if platform.system() == "Darwin":
        delete_macos_java_prefs(dry_run)
    elif platform.system() == "Windows":
        delete_windows_registry(dry_run)

    output.info("\n" + "=" * 60)
    output.info("Done! Trial reset complete.")
    output.info("=" * 60)
    output.info("\nNext steps:")
    output.info("1. Restart your computer (recommended) or log out/in")
    output.info("2. Launch IntelliJ IDEA")
    output.info("3. You should get a fresh 30-day trial")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
