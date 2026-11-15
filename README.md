# Winux

> **Bringing the Power, Speed & Elegance of Linux Command Line to Windows.**
> A unified, hybrid terminal environment & tools suite for **Windows Terminal**, **PowerShell (5.1 & 7+)**, and **Command Prompt (CMD)**.

[![License: Custom (T-WOSEL)](https://img.shields.io/badge/License-Custom%20Security%20%26%20Edu-purple.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg)](https://microsoft.com/windows)
[![Shells: PowerShell & CMD](https://img.shields.io/badge/Shells-PowerShell%20%7C%20CMD%20%7C%20WT-green.svg)](#)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-yellow.svg)](https://python.org)

---

## 🌟 Overview

**Winux** bridges the gap between Windows and Linux terminal workflows. It transforms your default Windows terminal experience with:
- **Linux-Style Commands**: Native, high-performance implementations of `grep`, `head`, `tail`, `wc`, `df`, `du`, `udiff`, `b64`, `jwt`, `ss`, and directory navigation (`..`, `...`, `mkcd`).
- **10 Curated TrueColor Themes**: Complete 16-color schemes synced seamlessly across Windows Terminal, PowerShell, and Command Prompt.
- **Hardware Telemetry HUD**: Instant startup diagnostics (CPU, RAM, Disk, Battery, Uptime, Git status, and network info).
- **Built-In Developer & Diagnostic Tools**: Live animated Internet speedometer, passive OSINT analyzer, subdomains finder, secret scanner, port connectivity checker, steganography engine, file organizers, cryptography utilities, and productivity trackers.
- **Zero-Dependency Core**: Runs out of the box using built-in Windows APIs and Python 3.10+. No WSL required.

---

## 🎨 Included Themes

| ID | Name | Palette & Style |
| :--- | :--- | :--- |
| `tokyo-night` | **Tokyo Night** | Midnight slate, electric cyan, and soft violet neon |
| `catppuccin` | **Catppuccin Mocha** | Warm dark espresso with soothing pastel accents |
| `cyberpunk` | **Cyberpunk Synthwave** | High-voltage neon magenta, electric cyan, and obsidian |
| `retro-crt` | **Retro CRT Matrix** | Phosphor emerald glow, amber alerts, and optional CRT scanlines |
| `dracula` | **Dracula Neon** | Gothic obsidian velvet with electric purple, orchid, and mint |
| `nord` | **Nordic Frost** | Arctic polar night paired with crisp glacier cyan and sage |
| `gruvbox` | **Gruvbox Ember** | Warm charcoal retro palette with burnt orange and antique gold |
| `crimson-hack` | **Crimson Hacker** | Stealth tactical charcoal with crimson laser red and steel cyan |
| `solar-gold` | **Solar Obsidian** | Luxury deep basalt black accented with brushed 24k amber gold |
| `emerald-forest` | **Emerald Deepwood** | Midnight pine slate illuminated by vivid jade and ocean teal |

Each theme configures:
- Windows Terminal 16-color palette + matching tab/title-bar chrome theme
- 24-bit TrueColor ANSI capsule/powerline prompts in PowerShell & CMD
- Theme-matched syntax highlighting and autocompletion
- Gradient System Telemetry HUD

---

## 🚀 Quick Start (Zero System Changes Preview)

Try Winux in an isolated session without modifying your system profiles:

```powershell
# 1. Clone the repository
git clone https://github.com/TricksXTech/Winux.git
cd Winux

# 2. Preview themes and prompts in your current window
.\preview.ps1

# 3. Launch an isolated sandbox tab to test commands
.\preview.ps1 -Mode ps      # Isolated PowerShell tab
.\preview.ps1 -Mode cmd     # Isolated CMD tab
.\preview.ps1 -Mode split   # Side-by-side comparison pane
```

---

## 📦 Installation & Uninstallation

Winux automatically creates timestamped backups before applying any settings.

```powershell
# Preview exact system changes without writing anything (Dry-Run)
.\install.ps1 -DryRun

# Install for Windows Terminal, PowerShell, and Command Prompt
.\install.ps1

# Clean uninstall (or restore exact pre-installation snapshot)
.\uninstall.ps1
.\uninstall.ps1 -RestoreBackup
```

---

## 🎮 `tx` Control Center & CLI

Run `tx` with no arguments to launch the interactive TUI Control Center, or use direct commands:

```text
tx list                         List all 10 themes with live TrueColor swatches
tx theme <name|#>               Switch theme (tokyo-night, dracula, nord, ...)
tx brand <text>                 Customize the HUD banner title
tx style <style>                Prompt layout: capsule | powerline | minimal | classic
tx hud <full|compact|off>       Configure startup System HUD
tx icons <auto|unicode|nerd>    Switch glyph mode (Unicode or Nerd Font icons)
tx opacity <30-100>             Adjust Windows Terminal background opacity (%)
tx acrylic <on|off>             Toggle Windows Terminal acrylic glass blur
tx crt <auto|on|off>            Toggle Retro CRT scanline shader in Windows Terminal
tx cursor <shape>               Cursor style: bar | vintage | underscore | filledBox
tx segment <name> <on|off>      Toggle segments: admin, userHost, path, git, duration...
tx tools [-i]                   Open the Free Tools Hub
tx preview [theme]              Preview theme prompts and colors safely
tx status                       Inspect environment, fonts, Clink, PSReadLine state
tx upgrade [target]             Install optional upgrades (nerd-font, clink, psreadline, pwsh)
tx reset                        Reset user configuration back to defaults
tx -help                        Show the interactive command guide
```

---

## 🛠️ Linux-Style CLI Utilities (PowerShell & CMD)

Winux provides native, cross-shell Linux command alternatives built directly into CMD and PowerShell:

| Command | Usage | Description |
| :--- | :--- | :--- |
| `grep` | `grep [-i] [-r] <pattern> [path...]` | Regex search with highlighted matches across files or stdin |
| `head` | `head [-n N] <file...>` | View the first N lines of files or stdin (default: 10) |
| `tail` | `tail [-n N] [-f] <file...>` | View the last N lines or follow log growth live with `-f` |
| `wc` | `wc [-lwc] <file...>` | Fast line, word, and byte counter |
| `df` | `df [path]` | Linux-style mounted drive capacity bars and free space |
| `du` | `du [path] [-n N]` | Recursive folder and file disk usage sorted by size |
| `udiff` | `udiff <file1> <file2>` | Colorized unified diff (leaves PowerShell's `diff` intact) |
| `b64` | `b64 [-d] [--hex\|--url] <text>` | Base64, Hex, and URL encoder/decoder |
| `jwt` | `jwt <token>` | Offline JWT header and payload claim inspector |
| `ss` | `ss [-l] [-t\|-u] [-p filter]` | Active & listening TCP/UDP sockets mapped to process names |

---

## 🧰 Built-in Free Tools Suite

All utilities run in both **PowerShell** and **Command Prompt** without third-party installations:

- **Speedometer (`speedtest` / `netspeed`)**: Live animated gauge measuring ping latency, jitter, download, and upload Mbps (`--quick`, `--down-only`).
- **Disk Storage Analyzer (`disk` / `storage`)**: Interactive folder storage tree, virtual file handling, and read-only junk advisor.
- **Wi-Fi Diagnostics (`wifi` / `wificheck`)**: Read-only adapter diagnostics, signal meter, channel congestion advice, and AP security audit.
- **Passive OSINT Inspector (`osint <target>`)**: DoH DNS records (SPF/DMARC), RDAP metadata, ASN/Geo, and SSL certificate expiry.
- **Subdomain Finder (`subdomains <domain>`)**: Passive Certificate Transparency log queries (`crt.sh`) with optional DNS resolution.
- **Web Stack Fingerprinter (`webtech <url>`)**: Passive HTTP header, CDN/WAF, and server technology detector.
- **Local Network Auditor (`lan`)**: Local ARP neighbor cache, default gateway, and MAC vendor inspection.
- **Port Reachability (`portcheck <host> [ports]`)**: Single-host TCP connectivity and latency probe (capped at 25 ports).
- **Security & Forensics (`sec_extra.py`)**: `secaudit` (Firewall/Defender read-only audit), `peinspect` (PE binary static analysis), `exifinfo` (image metadata), `hexview` (canonical hex dump), `hashid` (hash identifier), `secretaudit` (leaked credential scanner), `stego` (lossless LSB stego), `wordgen` (custom QA dictionaries).
- **HackingTool Integration (`ht` / `hackingtool`)**: Multi-category security and forensic launcher (`ht list`, `ht guide <category>`), sanitized and optimized for Windows.
- **Developer Utilities**: `jsonmin`, `csv2json`, `json2csv`, `yaml2json`, `xmlfmt`, `tomlcheck`, `logparse`, `cronparse`, `md2html`, `sqlfmt`, `colorconv`, `slugify`.
- **Productivity Utilities**: `stopwatch`, `countdown`, `pomodoro`, `pbar`, `todo`, `notes`, `expense`, `habit`, `bookmarks`, `contacts`, `calc`, `weather`, `unitconv`, `tzconv`.

---

## 🔒 Security, Governance & Open Source Contributing

Winux is an open-source project welcoming community contributions to improve Linux CLI emulation and tools on Windows.

To protect users against malicious code, supply chain attacks, and backdoors, Winux enforces strict repository governance:

1. **Branch Protection**: Direct commits to the `main` branch are blocked.
2. **Mandatory Code Review**: Every Pull Request must be reviewed and explicitly approved by the repository owner (`@TricksXTech` via `.github/CODEOWNERS`) before merging.
3. **Zero Malicious Code Policy**: Submissions containing backdoors, unauthorized telemetry, credential scrapers, or exploit payloads will be immediately rejected and reported.
4. **No Hardcoded Machine Paths**: All code must use relative paths (`%~dp0`, `$PSScriptRoot`, `os.path.dirname`) to remain portable for every user.

For guidelines on submitting changes, please read [CONTRIBUTING.md](CONTRIBUTING.md) and our [Security Policy](SECURITY.md).

---

## ⚖️ Legal Disclaimer & License

This project is licensed under the **Winux Custom Open Security & Educational License (T-WOSEL)** — see the [LICENSE](LICENSE) file for complete terms.

> [!WARNING]
> **IMPORTANT SECURITY & LEGAL NOTICE**:
> Winux provides system diagnostics, network analysis, and security auditing frameworks intended **strictly for lawful system administration, academic research, and authorized educational purposes**.
>
> **The user assumes full, sole, and exclusive responsibility for all actions, outcomes, and legal liabilities** resulting from the use or misuse of this software. Under no circumstances shall **TricksXTech**, its creator, maintainers, or contributors be held liable for any damages, unauthorized access, service disruptions, or legal actions resulting from the execution or deployment of this software.

Copyright (c) 2026 TricksXTech.
