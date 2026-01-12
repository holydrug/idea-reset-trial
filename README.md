# JetBrains IntelliJ IDEA Trial Reset Script

A script to reset the trial period of JetBrains IntelliJ IDEA. Works on macOS, Windows, and Linux.

## ⚠️ Disclaimer

This script is provided for educational purposes only. Use at your own risk. It is recommended to purchase a license to support JetBrains developers.

## 🔧 What the Script Removes

- **Configuration directories** (IntelliJIdea*)
- **Cache directories**
- **License files** (bl, crl, consentOptions)
- **Toolbox data**
- **Machine ID** (UserIdOnMachine, device_id, etc.)
- **Java preferences**
- **Windows registry keys** (Windows only)

## 📋 Requirements

- Python 3.6 or higher
- Administrator privileges may be required for some operations

## 🚀 Usage

### Basic Execution

```bash
python reset_idea_trial.py
```

### Dry Run Mode

Shows what will be deleted without actually removing any files:

```bash
python reset_idea_trial.py --dry-run
```

or

```bash
python reset_idea_trial.py -n
```

## 💻 Supported Platforms

| Platform  | Status |
|-----------|--------|
| macOS     | ✅     |
| Windows   | ✅     |
| Linux     | ✅     |

## 📁 Paths Being Removed

### macOS
- `~/Library/Application Support/JetBrains/IntelliJIdea*`
- `~/Library/Caches/JetBrains/IntelliJIdea*`
- `~/Library/Preferences/jetbrains*.plist`
- `~/Library/Preferences/com.jetbrains*.plist`

### Windows
- `%APPDATA%/JetBrains/IntelliJIdea*`
- `%LOCALAPPDATA%/JetBrains/IntelliJIdea*`
- Registry keys: `HKCU\SOFTWARE\JavaSoft\Prefs\jetbrains`, `HKCU\SOFTWARE\JetBrains`

### Linux
- `~/.config/JetBrains/IntelliJIdea*`
- `~/.cache/JetBrains/IntelliJIdea*`
- `~/.local/share/JetBrains/bl`, `crl`, `consentOptions`
- `~/.java/.userPrefs/jetbrains`

## 📝 After Running

1. **Restart your computer** (recommended) or log out/in
2. Launch IntelliJ IDEA
3. You should get a fresh 30-day trial

## 🔍 Example Output

```
============================================================
JetBrains IntelliJ IDEA Trial Reset
OS: Windows 10
============================================================

[Config directories]
  [OK] Deleted: C:\Users\User\AppData\Roaming\JetBrains\IntelliJIdea2024.1

[Cache directories]
  [OK] Deleted: C:\Users\User\AppData\Local\JetBrains\IntelliJIdea2024.1

[License files]
  [OK] Deleted: C:\Users\User\AppData\Roaming\JetBrains\bl

[Toolbox data]
  No Toolbox data found

[Preferences]
  No preference files found

[Windows Registry]
  [OK] Deleted HKCU\SOFTWARE\JavaSoft\Prefs\jetbrains

============================================================
Done! Trial reset complete.
============================================================

Next steps:
1. Restart your computer (recommended) or log out/in
2. Launch IntelliJ IDEA
3. You should get a fresh 30-day trial
```

## 📄 License

MIT License