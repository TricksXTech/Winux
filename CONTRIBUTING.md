# Contributing to Winux

Thank you for your interest in contributing to **Winux**! Winux is an open-source project dedicated to bringing the speed, elegance, and utility of Linux command-line workflows natively to Windows (Windows Terminal, PowerShell, and Command Prompt).

---

## 🔒 Security & Code Integrity Policy (Strict Anti-Malware Rule)

To ensure the safety and trust of all users:

1. **No Direct Commits to `main`**:
   The default branch is protected. No contributor—regardless of permissions—may push code directly to the `main` branch. All changes must go through a Pull Request (PR).

2. **Mandatory Maintainer Code Review**:
   Every Pull Request must be reviewed and explicitly approved by repository owners (`@TricksXTech` as defined in `.github/CODEOWNERS`) before it can be merged.

3. **Zero Malicious Code Policy**:
   - Any pull request containing malicious code, remote command execution backdoors, unauthorized telemetry or data scraping, obfuscated binary payloads, or credential stealers will be **immediately rejected and reported**.
   - Submissions must be clean, readable, self-contained Python/PowerShell/Batch source code.
   - External network calls must be passive, documented, and strictly respect user privacy.

4. **Zero Hardcoded Personal/System Paths**:
   - Never hardcode user profiles or absolute drive letters (e.g. `C:\Users\...` or `D:\...`).
   - Use dynamic relative references (`%~dp0` in CMD, `$PSScriptRoot` in PowerShell, `os.path.dirname(__file__)` in Python).

---

## 🚀 How to Contribute

### 1. Fork and Clone
```bash
git clone https://github.com/<your-username>/Winux.git
cd Winux
```

### 2. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 3. Develop & Test Locally
Before submitting a PR, test your changes across all supported environments:
- **Windows Terminal**
- **PowerShell (5.1 & PowerShell 7+)**
- **Command Prompt (CMD)**

Ensure:
- Python scripts compile cleanly without syntax errors:
  ```powershell
  python -m py_compile tools/<your_script>.py
  ```
- PowerShell scripts are pure ASCII/UTF-8 encoded without BOM corruption.
- Batch scripts preserve standard CRLF line endings.

### 4. Commit and Push
```bash
git add .
git commit -m "feat: Add new Linux-style command or tool"
git push origin feature/your-feature-name
```

### 5. Submit a Pull Request
Open a Pull Request against the `main` branch on [GitHub](https://github.com/TricksXTech/Winux/pulls). Fill out the Pull Request template checklist thoroughly.

---

## 📜 Code of Conduct

- Be respectful and constructive in all discussions, issues, and pull requests.
- Help maintain clean, readable, and well-documented open-source code for the entire community.
