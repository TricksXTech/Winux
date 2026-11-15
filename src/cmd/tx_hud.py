#!/usr/bin/env python3
"""TricksXTech CMD Companion - Fast TrueColor HUD and Directory Listings."""

import ctypes
import json
import os
import subprocess
import sys
import time
import winreg
from datetime import datetime


def enable_vt_mode():
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


def get_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def deep_merge(base, override):
    res = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(res.get(k), dict):
            res[k] = deep_merge(res[k], v)
        else:
            res[k] = v
    return res


def load_config_and_theme():
    root = get_root()
    with open(os.path.join(root, "config", "defaults.json"), "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    user_path = os.path.join(root, "config", "user.json")
    if os.path.isfile(user_path):
        try:
            with open(user_path, "r", encoding="utf-8-sig") as f:
                cfg = deep_merge(cfg, json.load(f))
        except Exception:
            pass
    with open(os.path.join(root, "themes", "themes.json"), "r", encoding="utf-8-sig") as f:
        themes = json.load(f)["themes"]
    theme = themes.get(cfg.get("theme"), themes["tokyo-night"])
    return cfg, theme


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def fg(h):
    r, g, b = hex_to_rgb(h)
    return f"\x1b[38;2;{r};{g};{b}m"


def fmt(text, color=None, bold=False):
    seq = ""
    if bold:
        seq += "\x1b[1m"
    if color:
        seq += fg(color)
    return f"{seq}{text}\x1b[0m" if seq else text


def gradient(text, stops, bold=True):
    if not text:
        return ""
    n = len(text)
    if n == 1 or len(stops) < 2:
        return fmt(text, stops[0], bold=bold)
    out = ["\x1b[1m"] if bold else []
    segs = len(stops) - 1
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(" ")
            continue
        t = i / (n - 1)
        scaled = t * segs
        idx = min(int(scaled), segs - 1)
        lt = scaled - idx
        c1 = hex_to_rgb(stops[idx])
        c2 = hex_to_rgb(stops[idx + 1])
        r = round(c1[0] + (c2[0] - c1[0]) * lt)
        g = round(c1[1] + (c2[1] - c1[1]) * lt)
        b = round(c1[2] + (c2[2] - c1[2]) * lt)
        out.append(f"\x1b[38;2;{r};{g};{b}m{ch}")
    out.append("\x1b[0m")
    return "".join(out)


def visible_len(s):
    import re
    return len(re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s))


def pad_vis(s, width):
    v = visible_len(s)
    return s if v >= width else s + (" " * (width - v))


def detect_nerd_font():
    patterns = ("nerd font", "caskaydiacove", "meslolgs", "nfm", "nfp")
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as k:
                i = 0
                while True:
                    try:
                        name, _, _ = winreg.EnumValue(k, i)
                        low = name.lower()
                        if any(p in low for p in patterns):
                            return True
                        i += 1
                    except OSError:
                        break
        except OSError:
            pass
    return False


def find_git_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def get_git_status(cwd):
    root = find_git_root(cwd)
    if not root:
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain=v2", "--branch"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if proc.returncode != 0:
            return None
        branch = ""
        ahead = behind = staged = modified = untracked = conflicts = 0
        for line in proc.stdout.splitlines():
            if line.startswith("# branch.head "):
                branch = line[14:].strip()
            elif line.startswith("# branch.ab "):
                parts = line[12:].split()
                for p in parts:
                    if p.startswith("+"):
                        ahead = int(p[1:])
                    elif p.startswith("-"):
                        behind = int(p[1:])
            elif line.startswith(("1 ", "2 ")):
                xy = line[2:4]
                if xy[0] != ".":
                    staged += 1
                if xy[1] != ".":
                    modified += 1
            elif line.startswith("u "):
                conflicts += 1
            elif line.startswith("? "):
                untracked += 1
        return {
            "repo": os.path.basename(root),
            "branch": branch or "detached",
            "ahead": ahead,
            "behind": behind,
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
            "conflicts": conflicts,
            "dirty": (staged + modified + untracked + conflicts) > 0,
        }
    except Exception:
        return None


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("SystemStatusFlag", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def get_sys_info():
    # OS
    os_name = "Windows"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as k:
            prod, _ = winreg.QueryValueEx(k, "ProductName")
            build, _ = winreg.QueryValueEx(k, "CurrentBuildNumber")
            try:
                disp, _ = winreg.QueryValueEx(k, "DisplayVersion")
            except OSError:
                disp = ""
            bnum = int(build)
            title = "Windows 11" if bnum >= 22000 else "Windows 10"
            edition = prod.replace("Windows 10", "").replace("Windows 11", "").strip()
            os_name = f"{title} {edition} {disp} (Build {bnum})".replace("  ", " ").strip()
    except Exception:
        pass

    # CPU
    cpu = os.environ.get("PROCESSOR_ARCHITECTURE", "x64")
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            raw_cpu, _ = winreg.QueryValueEx(k, "ProcessorNameString")
            cpu = " ".join(raw_cpu.replace("(R)", "").replace("(TM)", "").replace("CPU", "").split())
    except Exception:
        pass
    cpu = f"{cpu} ({os.cpu_count() or 1} threads)"

    # RAM
    mem = MEMORYSTATUSEX()
    mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ram_used = ram_total = ram_pct = 0
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
        tot = mem.ullTotalPhys
        avail = mem.ullAvailPhys
        ram_total = round(tot / (1024**3), 1)
        ram_used = round((tot - avail) / (1024**3), 1)
        ram_pct = round(((tot - avail) / tot) * 100) if tot else 0

    # Disk
    drive = os.path.splitdrive(os.getcwd())[0] or "C:"
    free_b = ctypes.c_ulonglong()
    tot_b = ctypes.c_ulonglong()
    disk_used = disk_total = disk_pct = 0
    if ctypes.windll.kernel32.GetDiskFreeSpaceExW(drive + "\\", None, ctypes.byref(tot_b), ctypes.byref(free_b)):
        t = tot_b.value
        u = t - free_b.value
        disk_total = round(t / (1024**3))
        disk_used = round(u / (1024**3))
        disk_pct = round((u / t) * 100) if t else 0

    # Uptime
    ms = ctypes.windll.kernel32.GetTickCount64()
    secs = int(ms // 1000)
    days, rem = divmod(secs, 86400)
    hrs, rem = divmod(rem, 3600)
    mins, s = divmod(rem, 60)
    if days > 0:
        uptime = f"{days}d {hrs}h {mins}m"
    elif hrs > 0:
        uptime = f"{hrs}h {mins}m"
    else:
        uptime = f"{mins}m {s}s"

    # Power
    pwr = "AC Power"
    ps = SYSTEM_POWER_STATUS()
    if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(ps)):
        if ps.BatteryFlag != 128 and ps.BatteryLifePercent <= 100:
            chg = "Charging" if ps.ACLineStatus == 1 else "Battery"
            pwr = f"{ps.BatteryLifePercent}% ({chg})"

    is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())

    return {
        "user": os.environ.get("USERNAME", "user"),
        "host": os.environ.get("COMPUTERNAME", "PC"),
        "admin": is_admin,
        "os": os_name,
        "cpu": cpu,
        "ram_used": ram_used,
        "ram_total": ram_total,
        "ram_pct": ram_pct,
        "drive": drive,
        "disk_used": disk_used,
        "disk_total": disk_total,
        "disk_pct": disk_pct,
        "uptime": uptime,
        "power": pwr,
    }


def get_vpn_hud_summary():
    p = os.path.join(get_root(), "config", "vpn_state.json")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            st = json.load(f)
        if not isinstance(st, dict) or not st.get("running") or st.get("status") != "connected":
            return None
        if time.time() - float(st.get("heartbeat") or 0.0) > 20.0:
            return None
        rem = max(0, int(float(st.get("next_rotate_at") or 0.0) - time.time()))
        m, s = divmod(rem, 60)
        return f"ACTIVE  {st.get('exit_ip', '?')} ({st.get('target_name', '?')})  swap {m:02d}m {s:02d}s"
    except Exception:
        return None


def meter_bar(pct, width, ui):
    pct = max(0, min(100, pct))
    filled = round((pct / 100.0) * width)
    empty = width - filled
    clr = ui["error"] if pct >= 85 else (ui["warning"] if pct >= 65 else ui["success"])
    return fmt("━" * filled, clr, bold=True) + fmt("─" * empty, ui["muted"])


def show_hud(force=False):
    cfg, theme = load_config_and_theme()
    mode = "full" if force else cfg.get("hud", "full")
    if mode == "off":
        return

    ui = theme["ui"]
    pal = theme["palette"]
    icons_cfg = cfg.get("icons", "auto")
    glyph_mode = ("nerd" if detect_nerd_font() else "unicode") if icons_cfg == "auto" else icons_cfg
    stops = [ui["gradientStart"], ui["gradientMid"], ui["gradientEnd"]]
    brand_name = cfg.get("brand", "TricksXTech")
    git = get_git_status(os.getcwd())

    if mode == "compact":
        title = gradient(brand_name, stops, bold=True)
        u = fmt(f"{os.environ.get('USERNAME','user')}@{os.environ.get('COMPUTERNAME','PC')}", ui["accent"], bold=True)
        t = fmt(theme["name"], ui["primary"], bold=True)
        s = fmt(f"{cfg.get('style','capsule')}/{glyph_mode}", ui["secondary"])
        sep = fmt("│", ui["border"])
        line = f" {title} {sep} {u} {sep} {t} ({s})"
        if git:
            gc = fmt("*" + git["branch"], ui["warning"]) if git["dirty"] else fmt(git["branch"], ui["success"])
            line += f" {sep} git:{gc}"
        print()
        print(line)
        print(fmt("   tx (themes)  |  tools (tools hub)  |  crypto (suite)  |  ht (suite)  |  disk (analyzer)  |  ll (files)  |  sysinfo (HUD)", ui["muted"]))
        print()
        return

    info = get_sys_info()
    try:
        cols = os.get_terminal_size().columns
    except OSError:
        cols = 80
    inner = min(74, max(58, cols - 4))
    cw = inner - 2

    top = fmt("╭" + ("─" * inner) + "╮", ui["border"])
    mid = fmt("├" + ("─" * inner) + "┤", ui["border"])
    bot = fmt("╰" + ("─" * inner) + "╯", ui["border"])
    vl = fmt("│ ", ui["border"])
    vr = fmt(" │", ui["border"])

    def row(txt):
        print(f"{vl}{pad_vis(txt, cw)}{vr}")

    swatches = " ".join(fmt("●", pal[c]) for c in ("red", "yellow", "green", "cyan", "blue", "purple"))
    logo = gradient(f"  {brand_name}", stops, bold=True)
    pill = fmt(f"[{theme['name']}]", ui["primary"], bold=True)
    adm = (" " + f"\x1b[1m{fg(ui['darkText'])}\x1b[48;2;{';'.join(map(str, hex_to_rgb(ui['warning'])))}m ADMIN \x1b[0m") if info["admin"] else ""
    right = f"{pill}{adm}  {swatches}"
    gap = max(1, cw - visible_len(logo) - visible_len(right))

    def kv(k, v, vc=ui["text"]):
        return f" {fmt(k.ljust(9), ui['secondary'], bold=True)} {fmt(v, vc)}"

    cpu = info["cpu"]
    if len(cpu) > cw - 12:
        cpu = cpu[: cw - 15] + "..."

    ram_lbl = f"{info['ram_used']}/{info['ram_total']} GB ({info['ram_pct']}%)"
    dsk_lbl = f"{info['drive']} {info['disk_used']}/{info['disk_total']} GB ({info['disk_pct']}%)"
    ram_s = f"{meter_bar(info['ram_pct'], 14, ui)} {fmt(ram_lbl, ui['text'])}"
    dsk_s = f"{meter_bar(info['disk_pct'], 14, ui)} {fmt(dsk_lbl, ui['text'])}"
    sh_s = f"Command Prompt (CMD)  {fmt('◆', ui['muted'])}  style:{fmt(cfg.get('style','capsule'), ui['accent'])}  icons:{fmt(glyph_mode, ui['accent'])}"
    up_s = f"{info['uptime']}  {fmt('◆', ui['muted'])}  Power: {info['power']}"

    print()
    print(top)
    row(f"{logo}{' ' * gap}{right}")
    print(mid)
    row(kv("Host", f"{info['user']}@{info['host']}", ui["accent"]))
    row(kv("OS", info["os"]))
    row(f" {fmt('Shell'.ljust(9), ui['secondary'], bold=True)} {sh_s}")
    row(kv("CPU", cpu))
    row(f" {fmt('Memory'.ljust(9), ui['secondary'], bold=True)} {ram_s}")
    row(f" {fmt('Disk'.ljust(9), ui['secondary'], bold=True)} {dsk_s}")
    row(kv("Uptime", up_s))

    if git:
        gb = fmt(f"{git['repo']} [{git['branch']}]", ui["primary"], bold=True)
        if git["dirty"]:
            parts = []
            if git["staged"]:
                parts.append(f"+{git['staged']}")
            if git["modified"]:
                parts.append(f"~{git['modified']}")
            if git["untracked"]:
                parts.append(f"?{git['untracked']}")
            if git["conflicts"]:
                parts.append(f"!{git['conflicts']}")
            gs = fmt(" ".join(parts), ui["warning"])
        else:
            gs = fmt("✓ clean", ui["success"])
        ab = ""
        if git["ahead"]:
            ab += f" ↑{git['ahead']}"
        if git["behind"]:
            ab += f" ↓{git['behind']}"
        row(f" {fmt('Git'.ljust(9), ui['secondary'], bold=True)} {gb}  {gs}{fmt(ab, ui['accent'])}")

    vpn_line = get_vpn_hud_summary()
    if vpn_line:
        row(kv("VPN", vpn_line, ui["success"]))

    print(mid)
    tips = (
        " "
        + fmt("tx", ui["primary"], bold=True) + fmt(" themes ", ui["muted"])
        + fmt("tools", ui["accent"], bold=True) + fmt(" hub ", ui["muted"])
        + fmt("crypto", ui["accent"], bold=True) + fmt(" ", ui["muted"])
        + fmt("ht", ui["accent"], bold=True) + fmt(" suite ", ui["muted"])
        + fmt("disk", ui["accent"], bold=True) + fmt(" analyzer ", ui["muted"])
        + fmt("ll", ui["accent"], bold=True) + fmt(" files ", ui["muted"])
        + fmt("sysinfo", ui["accent"], bold=True) + fmt(" HUD", ui["muted"])
    )
    row(tips)
    print(bot)
    print()


def fmt_size(b):
    if b < 1024:
        return f"{b} B"
    if b < 1024**2:
        return f"{b / 1024:.1f} KB"
    if b < 1024**3:
        return f"{b / (1024**2):.1f} MB"
    return f"{b / (1024**3):.2f} GB"


def style_entry(name, is_dir, ui, pal):
    if is_dir:
        return "▸", ui["primary"], True
    ext = os.path.splitext(name)[1].lower()
    if ext in (".exe", ".msi", ".bat", ".cmd", ".ps1", ".sh"):
        return "⚙", ui["success"], True
    if ext in (".py", ".js", ".ts", ".rs", ".go", ".c", ".cpp", ".lua", ".html", ".css", ".sql"):
        return "⟨⟩", ui["accent"], False
    if ext in (".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".env"):
        return "⚙", ui["warning"], False
    if ext in (".zip", ".tar", ".gz", ".7z", ".rar"):
        return "▤", ui["secondary"], False
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
        return "▣", pal["purple"], False
    if name.startswith("."):
        return "▫", ui["muted"], False
    return "≡" if ext in (".md", ".txt", ".log", ".pdf") else "▫", ui["text"], False


def show_ls(path=".", show_all=False):
    _, theme = load_config_and_theme()
    ui, pal = theme["ui"], theme["palette"]
    target = os.path.abspath(path)
    if not os.path.isdir(target):
        print(fmt(f"Path not found: {path}", ui["error"]))
        return
    entries = []
    with os.scandir(target) as it:
        for e in it:
            if not show_all and e.name.startswith("."):
                continue
            try:
                is_dir = e.is_dir()
                st = e.stat()
                entries.append((not is_dir, e.name.lower(), e.name, is_dir, st.st_size, st.st_mtime))
            except OSError:
                continue
    entries.sort()
    if not entries:
        print(fmt("  (empty directory)", ui["muted"]))
        return

    print(
        " "
        + fmt("Type".ljust(6), ui["muted"], bold=True)
        + fmt("Size".rjust(10), ui["muted"], bold=True)
        + "  "
        + fmt("Modified".ljust(18), ui["muted"], bold=True)
        + fmt("Name", ui["muted"], bold=True)
    )
    print(fmt(" " + "─" * 58, ui["border"]))
    dirs = files = total_b = 0
    for _, _, name, is_dir, sz, mt in entries:
        icon, clr, bld = style_entry(name, is_dir, ui, pal)
        if is_dir:
            dirs += 1
            t_col = fmt("DIR   ", ui["secondary"])
            s_col = fmt("<DIR>".rjust(10), ui["secondary"])
            disp = name + "/"
        else:
            files += 1
            total_b += sz
            t_col = fmt("FILE  ", ui["muted"])
            s_col = fmt(fmt_size(sz).rjust(10), ui["muted"])
            disp = name
        dt = datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M").ljust(18)
        print(f" {t_col}{s_col}  {fmt(dt, ui['muted'])}{fmt(icon + ' ', clr)}{fmt(disp, clr, bold=bld)}")
    print(fmt(f" {dirs} dirs, {files} files ({fmt_size(total_b)})", ui["muted"]))


def show_tree(path=".", depth=2):
    _, theme = load_config_and_theme()
    ui, pal = theme["ui"], theme["palette"]
    root = os.path.abspath(path)
    if not os.path.isdir(root):
        print(fmt(f"Path not found: {path}", ui["error"]))
        return
    print(fmt(f"▸ {root}", ui["primary"], bold=True))

    def walk(d, prefix, lvl):
        if lvl > depth:
            return
        items = []
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.name in (".git", "node_modules", "__pycache__"):
                        continue
                    items.append((not e.is_dir(), e.name.lower(), e.name, e.is_dir(), e.path))
        except OSError:
            return
        items.sort()
        for idx, (_, _, name, is_dir, full) in enumerate(items):
            last = idx == len(items) - 1
            branch = "└── " if last else "├── "
            icon, clr, bld = style_entry(name, is_dir, ui, pal)
            disp = name + ("/" if is_dir else "")
            print(f"{prefix}{fmt(branch, ui['border'])}{fmt(icon + ' ' + disp, clr, bold=bld)}")
            if is_dir and lvl < depth:
                nxt = prefix + ("    " if last else fmt("│   ", ui["border"]))
                walk(full, nxt, lvl + 1)

    walk(root, "", 1)


def main():
    enable_vt_mode()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = sys.argv[1:]
    if "--sysinfo" in args or "--force" in args:
        show_hud(force=True)
    elif "--ls" in args:
        p = next((a for a in args if not a.startswith("-")), ".")
        show_ls(p, show_all=False)
    elif "--la" in args:
        p = next((a for a in args if not a.startswith("-")), ".")
        show_ls(p, show_all=True)
    elif "--tree" in args:
        p = next((a for a in args if not a.startswith("-")), ".")
        show_tree(p)
    else:
        show_hud(force=False)


if __name__ == "__main__":
    main()
