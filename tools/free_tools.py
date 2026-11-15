#!/usr/bin/env python3
"""TricksXTech Free Tools Suite - Theme-synced local system & developer utilities."""

from __future__ import annotations

import csv
import ctypes
import hashlib
import io
import json
import os
import socket
import stat
import subprocess
import sys
import time
from collections import defaultdict


def enable_vt() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if os.name == "nt":
        try:
            k32 = ctypes.windll.kernel32
            h = k32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if k32.GetConsoleMode(h, ctypes.byref(mode)):
                k32.SetConsoleMode(h, mode.value | 0x0004)
        except Exception:
            pass


def get_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_theme() -> dict:
    root = get_root()
    try:
        with open(os.path.join(root, "config", "defaults.json"), "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
        u_path = os.path.join(root, "config", "user.json")
        if os.path.isfile(u_path):
            with open(u_path, "r", encoding="utf-8-sig") as f:
                cfg.update(json.load(f))
        with open(os.path.join(root, "themes", "themes.json"), "r", encoding="utf-8-sig") as f:
            themes = json.load(f)["themes"]
        return themes.get(cfg.get("theme"), themes["tokyo-night"])
    except Exception:
        return {
            "name": "Tokyo Night",
            "palette": {"green": "#9ECE6A", "yellow": "#E0AF68", "purple": "#BB9AF7", "cyan": "#7DCFFF"},
            "ui": {
                "primary": "#7AA2F7", "secondary": "#BB9AF7", "accent": "#7DCFFF",
                "success": "#9ECE6A", "warning": "#E0AF68", "error": "#F7768E",
                "muted": "#565F89", "text": "#C0CAF5", "border": "#3B4261",
                "gradientStart": "#7AA2F7", "gradientMid": "#BB9AF7", "gradientEnd": "#7DCFFF",
            },
        }


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def fmt(text: str, color: str | None = None, bold: bool = False) -> str:
    seq = "\x1b[1m" if bold else ""
    if color:
        r, g, b = hex_rgb(color)
        seq += f"\x1b[38;2;{r};{g};{b}m"
    return f"{seq}{text}\x1b[0m" if seq else text


def gradient(text: str, stops: list[str], bold: bool = True) -> str:
    if not text or len(stops) < 2:
        return fmt(text, stops[0] if stops else None, bold=bold)
    out = ["\x1b[1m"] if bold else []
    n = len(text)
    segs = len(stops) - 1
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(" ")
            continue
        t = i / max(1, n - 1)
        sc = t * segs
        idx = min(int(sc), segs - 1)
        lt = sc - idx
        c1, c2 = hex_rgb(stops[idx]), hex_rgb(stops[idx + 1])
        r = round(c1[0] + (c2[0] - c1[0]) * lt)
        g = round(c1[1] + (c2[1] - c1[1]) * lt)
        b = round(c1[2] + (c2[2] - c1[2]) * lt)
        out.append(f"\x1b[38;2;{r};{g};{b}m{ch}")
    out.append("\x1b[0m")
    return "".join(out)


def fmt_bytes(n: int) -> str:
    val = float(max(0, n))
    for u in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024.0 or u == "TB":
            return f"{int(val)} B" if u == "B" else f"{val:.2f} {u}"
        val /= 1024.0
    return f"{val:.2f} TB"


def header(title: str, theme: dict) -> None:
    ui = theme["ui"]
    stops = [ui["gradientStart"], ui["gradientMid"], ui["gradientEnd"]]
    print()
    print("  " + gradient(f"TricksXTech // {title}", stops, bold=True))
    print(fmt("  " + "─" * 68, ui["border"]))


def cmd_tools_hub(theme: dict, interactive: bool = False) -> None:
    ui = theme["ui"]
    header("Free Built-In Tools", theme)
    items = [
        ("1",  "disk",     "Disk Storage Analyzer & Cleanup Advisor (drives, folders, read-only junk advisor)"),
        ("2",  "bigfiles", "Top N Largest Files Finder           (usage: bigfiles [path] [topN])"),
        ("3",  "procs",    "Top Memory & Process Monitor         (usage: procs [count])"),
        ("4",  "netinfo",  "Network, Interfaces & Latency Check  (usage: netinfo)"),
        ("5",  "hashfile", "MD5 / SHA-1 / SHA-256 / SHA-512 Tool (usage: hashfile <file> [expected])"),
        ("6",  "loc",      "Project Code Line Counter            (usage: loc [path])"),
        ("7",  "jsonfmt",  "Colorized JSON Validator & Formatter (usage: jsonfmt <file>)"),
        ("8",  "sysinfo",  "TricksXTech System Telemetry HUD     (usage: sysinfo)"),
        ("9",  "wifi",     "Wi-Fi Signal, Channel & Security     (usage: wifi [--profiles])"),
        ("10", "osint",    "Passive Public OSINT Inspector       (usage: osint <domain|ip>)"),
        ("11", "df",        "Linux-style Drive Capacity Bars      (usage: df [path])"),
        ("12", "du",        "Linux-style Directory Usage Summary  (usage: du [path])"),
        ("13", "ss",        "Socket & Port Process Inspector      (usage: ss [-l] [-p filter])"),
        ("14", "subdomains","Passive CT-Log Subdomain Lookup      (usage: subdomains <domain> [--resolve])"),
        ("15", "webtech",   "Passive Web Tech & Stack Fingerprint (usage: webtech <url|domain>)"),
        ("16", "lan",       "Local ARP Neighbors & Gateway Cache  (usage: lan)"),
        ("17", "portcheck", "Dev Single-Host TCP Port Check       (usage: portcheck <host> [p1,p2...])"),
        ("18", "vpn",       "Auto-VPN & 5-min IP Rotator      (usage: vpn [start|stop|next|sync|auto|status])"),
        ("19", "pwgen",     "Strong Password/Passphrase Generator (usage: pwgen [len] [--words 4])"),
        ("20", "epoch",     "Unix Epoch <-> ISO-8601 Converter    (usage: epoch [timestamp_or_date])"),
        ("21", "uuid",      "UUID v4 Identifier Generator         (usage: uuid [-n count])"),
        ("22", "speedtest", "Live Speedometer Internet Speed Test (usage: speedtest [--quick] [--down-only])"),
    ]
    for num, cmd, desc in items:
        print(f"  {fmt('[' + num.rjust(2) + ']', ui['accent'], True)} {fmt(cmd.ljust(11), ui['primary'], True)} {fmt(desc, ui['text'])}")

    print()
    print("  " + fmt("LINUX-STYLE CLI COMMANDS", ui["secondary"], True))
    linux_cli = [
        ("grep",  "Search text/regex in files or stdin  (grep [-i] [-r] <pattern> [path...])"),
        ("head",  "Show first N lines                   (head [-n 10] <file...>)"),
        ("tail",  "Show last N lines or live follow     (tail [-n 10] [-f] <file>)"),
        ("wc",    "Count lines, words, and bytes        (wc [-lwc] <file...>)"),
        ("udiff", "Colorized unified file diff          (udiff <file1> <file2>)"),
        ("b64",   "Base64 / Hex / URL encode & decode   (b64 [-d] [--hex|--url] <text>)"),
        ("jwt",   "Decode JWT header & payload claims   (jwt <token>)"),
    ]
    for cmd, desc in linux_cli:
        print(f"  {fmt('  •', ui['accent'])}   {fmt(cmd.ljust(11), ui['primary'], True)} {fmt(desc, ui['text'])}")

    extra_sections = [
        ("NETWORK & LIVE SPEEDOMETER", [
            ("speedtest",   "Live speedometer UI for Ping, Jitter, Download & Upload (or: netspeed)"),
            ("dns / rdns",  "Forward & reverse DNS lookup         (dns example.com | rdns 8.8.8.8)"),
            ("cidr",        "Subnet / CIDR range & host calc      (cidr 192.168.1.0/24)"),
            ("httpcode",    "Check HTTP status & response time    (httpcode https://example.com)"),
            ("unshorten",   "Trace 301/302 redirect chains        (unshorten <short_url>)"),
            ("robots",      "Parse website robots.txt directives  (robots <domain_or_url>)"),
            ("sitemap",     "Extract URLs from sitemap.xml        (sitemap <domain_or_url>)"),
            ("titlemeta",   "Extract HTML <title> & <meta> tags   (titlemeta <url>)"),
            ("uaparse",     "Parse User-Agent OS/browser/device   (uaparse \"<ua_string>\")"),
            ("serve",       "Local HTTP file server (127.0.0.1)   (serve [port] [--lan])"),
            ("lanspeed",    "Measure LAN/share disk copy speed    (lanspeed <target_dir>)"),
            ("pingcheck",   "Ping latency summary (min/avg/max)   (pingcheck <host> [-n 4])"),
            ("ftpget",      "Download files over public FTP       (ftpget <ftp://...>)"),
        ]),
        ("SYSTEM & FILE DIAGNOSTICS", [
            ("envfind",     "Search environment variables         (envfind [pattern])"),
            ("organize",    "Sort folder by file type (--dry-run) (organize [dir] [--apply])"),
            ("dupes",       "Find duplicate files by SHA-256      (dupes [dir])"),
            ("extrename",   "Bulk rename extensions  (--dry-run)  (extrename <dir> <from> <to>)"),
            ("replace",     "Batch find & replace    (--dry-run)  (replace <dir> <old> <new>)"),
            ("perms",       "Audit file/dir ACL & mode bits       (perms [path])"),
            ("cleantemp",   "Clean empty/.tmp/.log   (--dry-run)  (cleantemp [dir] [--apply])"),
            ("watchdir",    "Watch folder for file changes        (watchdir [dir])"),
            ("symlinks",    "Audit symlinks & broken targets      (symlinks [dir])"),
            ("zipmgr",      "Create, extract or list .zip         (zipmgr create|extract|list ...)"),
            ("targz",       "Create, extract or list .tar.gz/.bz2 (targz create|extract|list ...)"),
            ("clip",        "Read/write Windows clipboard         (clip get | echo hi | clip)"),
        ]),
        ("CRYPTOGRAPHY & HASHING", [
            ("hmac256",     "Calculate HMAC-SHA256 signature      (hmac256 <key> <text>)"),
            ("rot13",       "ROT13 / Caesar text encoder          (rot13 <text>)"),
            ("bin2txt",     "Binary bits <-> ASCII text           (bin2txt 01001000... | --encode)"),
            ("ascii",       "Inspect decimal/hex/binary codes     (ascii \"Hello\")"),
            ("tokengen",    "Cryptographic hex/URL-safe tokens    (tokengen [bytes] [-n cnt] [--url])"),
            ("entropy",     "Password randomness & crack-time est (entropy \"<text>\")"),
            ("crc32",       "CRC32 checksum for text or files     (crc32 <file_or_text>)"),
            ("bcryptcheck", "Verify password vs $2a$/$2b$/$2y$    (bcryptcheck <pw> <hash>)"),
            ("htpasswd",    "Generate Apache/Nginx htpasswd line  (htpasswd <user> <pw>)"),
            ("fencrypt",    "AES-256-GCM + PBKDF2 file encryptor  (fencrypt enc|dec <file>)"),
            ("rsagen",      "Generate RSA 2048/4096 PEM keypairs  (rsagen [-b 2048] [-o prefix])"),
        ]),
        ("DEVELOPER & DATA UTILITIES", [
            ("jsonmin",     "Minify JSON files or stdin           (jsonmin <file_or_json>)"),
            ("csv2json",    "Convert CSV table -> JSON array      (csv2json <file.csv>)"),
            ("json2csv",    "Flatten JSON array -> CSV            (json2csv <file.json>)"),
            ("yaml2json",   "Convert YAML <-> JSON (--reverse)    (yaml2json <file.yaml>)"),
            ("xmlfmt",      "Validate & pretty-print XML safely   (xmlfmt <file.xml>)"),
            ("tomlcheck",   "Validate TOML & export JSON          (tomlcheck <file.toml>)"),
            ("logparse",    "Extract IPs/HTTP codes from logs     (logparse <access.log>)"),
            ("cronparse",   "Explain cron schedules & next runs   (cronparse \"*/15 * * * *\")"),
            ("md2html",     "Render Markdown -> HTML              (md2html <README.md>)"),
            ("htmlent",     "Escape / unescape HTML entities      (htmlent [-d] <text>)"),
            ("sqlfmt",      "Format SQL queries & keywords        (sqlfmt \"select * from users\")"),
            ("colorconv",   "Convert HEX / RGB / HSL swatches     (colorconv \"#7aa2f7\")"),
            ("lorem",       "Generate placeholder paragraphs/words(lorem [paras] [--words 50])"),
            ("slugify",     "Convert titles -> URL slugs          (slugify \"Hello World!\")"),
            ("caseconv",    "camel/snake/kebab/Pascal/CONST case  (caseconv -m snake \"myVar\")"),
            ("uniqsort",    "Sort, deduplicate & count frequency  (uniqsort [-c] <file>)"),
        ]),
        ("PRODUCTIVITY & WORKFLOW", [
            ("stopwatch",   "Interactive stopwatch with laps      (stopwatch)"),
            ("countdown",   "Live themed countdown timer          (countdown 5m --msg Done)"),
            ("pomodoro",    "Work/break focus intervals           (pomodoro --work 25m --break 5m)"),
            ("pbar",        "Progress bar for pipes or demos      (pbar --demo | cmd | pbar)"),
            ("todo",        "Persistent JSON to-do manager        (todo add \"Task\" -p high)"),
            ("notes",       "Tagged Markdown quick notes          (notes add \"Title\" --tag dev)"),
            ("expense",     "Expense logger & CSV summary         (expense add 250 food \"Lunch\")"),
            ("habit",       "Daily habit & 7-day streak tracker   (habit add|check|list)"),
            ("bookmarks",   "Saved URL bookmarks manager          (bookmarks add|list|open)"),
            ("contacts",    "SQLite local address book            (contacts add|search|export)"),
            ("aliases",     "Sync custom PS + CMD aliases         (aliases add gl \"git log -n 5\")"),
            ("banner",      "Themed gradient ASCII/block banners  (banner \"TRICKSXTECH\")"),
            ("calc",        "Safe AST scientific calculator       (calc \"sqrt(144) + 2**8\")"),
            ("unitconv",    "Unit converter (len/mass/data/temp)  (unitconv 100 km mi)"),
            ("tzconv",      "World clock & timezone converter     (tzconv 14:30 --from IST --to UTC)"),
            ("fx",          "Live currency exchange rates         (fx 100 USD INR)"),
            ("weather",     "Live weather & 3-day forecast        (weather Tokyo)"),
            ("pick",        "Random picker, dice & coin flip      (pick --range 1..50 | --coin)"),
            ("gitclean",    "Prune merged branches  (--dry-run)   (gitclean [--apply])"),
            ("gitstats",    "Commit & contributor analytics       (gitstats [repo_dir])"),
        ]),
        ("DEFENSE, FORENSICS & HARDENING", [
            ("secaudit",    "Windows Firewall/Defender/0.0.0.0 exposure audit (read-only)"),
            ("peinspect",   "Static PE/ELF binary header, entropy & strings analyzer (no exec)"),
            ("exifinfo",    "File magic verifier, EXIF/GPS & PNG metadata forensics"),
            ("hexview",     "Canonical hexadecimal + ASCII dump viewer (hexview <file>)"),
            ("hashid",      "Identify hash / JWT / UUID formats locally (hashid <value>)"),
            ("secretaudit", "Offline scan for leaked API keys, private keys & 0.0.0.0 binds"),
            ("idncheck",    "Detect Punycode & mixed-script homograph phishing domains"),
            ("stego",       "Audit EOF trailing image bytes & lossless BMP LSB inspector"),
            ("wordgen",     "Generate capped local QA/policy wordlists  (wordgen words --leet)"),
            ("hackingtool", "Multi-category security & forensics suite (or: ht, ht <category>)"),
            ("crypto",      "Crypto CLI launcher: TRX & BNB/ETH utilities  (crypto)"),
        ]),
    ]
    for sec_title, rows in extra_sections:
        print()
        print("  " + fmt(sec_title, ui["secondary"], True))
        for cmd, desc in rows:
            print(f"  {fmt('  •', ui['accent'])}   {fmt(cmd.ljust(13), ui['primary'], True)} {fmt(desc, ui['text'])}")

    print(fmt("  " + "─" * 74, ui["border"]))
    print(fmt("  Works in both PowerShell & CMD. Mutating tools default to --dry-run preview.", ui["muted"]))
    print()

    if not interactive:
        return
    try:
        pick = input("  Launch tool # (1-22, or Enter to exit): ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    this_dir = os.path.dirname(os.path.abspath(__file__))
    if this_dir not in sys.path:
        sys.path.insert(0, this_dir)

    if pick == "1":
        from disk_analyzer import main as disk_main
        disk_main()
    elif pick == "2":
        cmd_bigfiles(["."], theme)
    elif pick == "3":
        cmd_procs([], theme)
    elif pick == "4":
        cmd_netinfo(theme)
    elif pick == "5":
        fp = input("  File path to hash: ").strip().strip('"')
        if fp:
            cmd_hashfile([fp], theme)
    elif pick == "6":
        cmd_loc(["."], theme)
    elif pick == "7":
        fp = input("  JSON file path: ").strip().strip('"')
        if fp:
            cmd_jsonfmt([fp], theme)
    elif pick == "8":
        root = get_root()
        subprocess.run([sys.executable, os.path.join(root, "src", "cmd", "tx_hud.py"), "--sysinfo"])
    elif pick == "9":
        from wifi_checker import run_wifi_check
        run_wifi_check(theme)
    elif pick == "10":
        tgt = input("  Domain or public IP: ").strip()
        if tgt:
            from osint_tool import run_osint
            run_osint(tgt, theme)
    elif pick == "11":
        from linux_tools import cmd_df
        cmd_df([], theme)
    elif pick == "12":
        from linux_tools import cmd_du
        cmd_du(["."], theme)
    elif pick == "13":
        from linux_tools import cmd_ss
        cmd_ss([], theme)
    elif pick == "14":
        dom = input("  Domain for CT subdomain lookup: ").strip()
        if dom:
            from recon_safe import cmd_subdomains
            cmd_subdomains([dom], theme)
    elif pick == "15":
        tgt = input("  URL or domain: ").strip()
        if tgt:
            from recon_safe import cmd_webtech
            cmd_webtech([tgt], theme)
    elif pick == "16":
        from recon_safe import cmd_lan
        cmd_lan([], theme)
    elif pick == "17":
        host = input("  Host to check (default localhost): ").strip() or "localhost"
        from recon_safe import cmd_portcheck
        cmd_portcheck([host], theme)
    elif pick == "18":
        import vpn_tool
        act = (input("  VPN action [start / stop / next / sync / status] (Enter=status): ").strip() or "status").lower()
        if act == "start":
            res = vpn_tool.start_background_rotator(ui=ui, wait_connected=True)
            if res and res.get("status") == "connected":
                print(vpn_tool.vpn_badge_line(res, ui))
        elif act in ("stop", "down"):
            vpn_tool._cmd_stop(ui)
        elif act in ("next", "switch"):
            vpn_tool._cmd_next(ui)
        elif act == "sync":
            vpn_tool.sync_vpngate_pool(ui=ui)
        else:
            vpn_tool._cmd_status(theme)
    elif pick == "19":
        from dev_tools import cmd_pwgen
        cmd_pwgen([], theme)
    elif pick == "20":
        from dev_tools import cmd_epoch
        cmd_epoch([], theme)
    elif pick == "21":
        from dev_tools import cmd_uuid
        cmd_uuid(["-n", "5"], theme)
    elif pick.lower() in ("22", "s", "speedtest"):
        from speedtest_tool import run_speedtest
        run_speedtest([], theme)


def cmd_bigfiles(args: list[str], theme: dict) -> None:
    ui = theme["ui"]
    path = "."
    limit = 20
    for a in args:
        if a.isdigit():
            limit = max(1, min(100, int(a)))
        else:
            path = a
    target = os.path.abspath(path)
    if not os.path.exists(target):
        print(fmt(f"  Path not found: {path}", ui["error"], True))
        return

    header(f"Largest Files in {target}", theme)
    cloud_mask = 0x1000 | 0x40000 | 0x400000
    reparse_tags = (
        getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003),
        getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C),
    )
    results: list[tuple[int, str]] = []
    scanned_files = 0
    t0 = time.perf_counter()

    stack = [target]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        st = entry.stat(follow_symlinks=False)
                        if getattr(st, "st_reparse_tag", 0) in reparse_tags:
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            scanned_files += 1
                            if getattr(st, "st_file_attributes", 0) & cloud_mask:
                                continue
                            results.append((st.st_size, entry.path))
                    except OSError:
                        continue
        except OSError:
            continue

    results.sort(key=lambda x: x[0], reverse=True)
    top = results[:limit]
    dt = time.perf_counter() - t0
    if not top:
        print(fmt("  No local files found.", ui["muted"]))
        return

    max_sz = max(1, top[0][0])
    for idx, (sz, fp) in enumerate(top, start=1):
        bar_len = max(1, round((sz / max_sz) * 12))
        bar = fmt("━" * bar_len, ui["primary"], True) + fmt("─" * (12 - bar_len), ui["muted"])
        rel = os.path.relpath(fp, target) if fp.lower().startswith(target.lower()) else fp
        if len(rel) > 46:
            rel = "..." + rel[-43:]
        print(f"  {fmt(f'{idx:>2}.', ui['muted'])} {bar} {fmt(fmt_bytes(sz).rjust(10), ui['accent'], True)}  {fmt(rel, ui['text'])}")
    print(fmt(f"\n  Scanned {scanned_files:,} files in {dt:.2f}s.", ui["muted"]))
    print()


def cmd_procs(args: list[str], theme: dict) -> None:
    ui = theme["ui"]
    limit = int(args[0]) if (args and args[0].isdigit()) else 12
    header(f"Top {limit} Processes by Memory", theme)
    try:
        out = subprocess.check_output(
            ["tasklist", "/fo", "csv", "/nh"],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except Exception as exc:
        print(fmt(f"  Failed to query processes: {exc}", ui["error"]))
        return

    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [kb, count]
    reader = csv.reader(io.StringIO(out))
    for row in reader:
        if len(row) < 5:
            continue
        name = row[0]
        mem_str = "".join(ch for ch in row[4] if ch.isdigit())
        kb = int(mem_str) if mem_str else 0
        agg[name][0] += kb
        agg[name][1] += 1

    ranked = sorted(agg.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    if not ranked:
        print(fmt("  No process entries found.", ui["muted"]))
        return

    max_kb = max(1, ranked[0][1][0])
    for idx, (name, (kb, cnt)) in enumerate(ranked, start=1):
        mb = kb / 1024.0
        bar_len = max(1, round((kb / max_kb) * 14))
        clr = ui["error"] if mb > 1024 else (ui["warning"] if mb > 350 else ui["success"])
        bar = fmt("━" * bar_len, clr, True) + fmt("─" * (14 - bar_len), ui["muted"])
        cnt_lbl = f" ({cnt}x)" if cnt > 1 else ""
        disp = (name + cnt_lbl)[:28].ljust(28)
        print(f"  {fmt(f'{idx:>2}.', ui['muted'])} {fmt(disp, ui['text'], True)} {bar} {fmt(f'{mb:>8.1f} MB', ui['accent'])}")
    print()


def cmd_netinfo(theme: dict, args: list[str] | None = None) -> None:
    ui = theme["ui"]
    skip_vpn = "--no-vpn" in (args or [])
    header("Network & Latency Inspector", theme)
    from vpn_tool import ensure_vpn_for_tool
    ensure_vpn_for_tool("netinfo", theme, skip_vpn=skip_vpn)
    host = socket.gethostname()
    print(f"  {fmt('Hostname'.ljust(16), ui['secondary'], True)} {fmt(host, ui['text'])}")

    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET)
        ips = sorted({info[4][0] for info in infos if info[4][0] != "127.0.0.1"})
        print(f"  {fmt('Local IPv4'.ljust(16), ui['secondary'], True)} {fmt(', '.join(ips) if ips else 'None', ui['accent'], True)}")
    except OSError:
        print(f"  {fmt('Local IPv4'.ljust(16), ui['secondary'], True)} {fmt('Unavailable', ui['muted'])}")

    print()
    print(f"  {fmt('TCP Reachability Check:', ui['primary'], True)}")
    targets = [("Cloudflare DNS", "1.1.1.1", 53), ("Google DNS", "8.8.8.8", 53)]
    for label, ip, port in targets:
        t0 = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=1.0):
                ms = (time.perf_counter() - t0) * 1000.0
                print(f"    {fmt('✓', ui['success'], True)} {fmt(label.ljust(18), ui['text'])} {fmt(f'{ip}:{port}'.ljust(14), ui['muted'])} {fmt(f'{ms:.1f} ms', ui['success'], True)}")
        except OSError:
            print(f"    {fmt('✘', ui['error'], True)} {fmt(label.ljust(18), ui['text'])} {fmt(f'{ip}:{port}'.ljust(14), ui['muted'])} {fmt('offline / timed out', ui['warning'])}")

    try:
        ns = subprocess.check_output(["netstat", "-ano", "-p", "TCP"], text=True, errors="replace", timeout=4)
        ports = sorted({
            line.split()[1].rsplit(":", 1)[-1]
            for line in ns.splitlines()
            if "LISTENING" in line and ":" in line.split()[1]
        }, key=lambda x: int(x) if x.isdigit() else 99999)
        if ports:
            print()
            print(f"  {fmt('Listening TCP Ports:', ui['primary'], True)} {fmt(', '.join(ports[:24]), ui['accent'])}")
    except Exception:
        pass
    print()


def cmd_hashfile(args: list[str], theme: dict) -> None:
    ui = theme["ui"]
    if not args:
        print(fmt("  Usage: hashfile <file> [expected_hash]", ui["warning"]))
        return
    fp = args[0]
    expected = args[1].strip().lower() if len(args) > 1 else None
    if not os.path.isfile(fp):
        print(fmt(f"  File not found: {fp}", ui["error"], True))
        return

    header(f"File Checksums: {os.path.basename(fp)}", theme)
    algos = {
        "MD5": hashlib.md5(),
        "SHA1": hashlib.sha1(),
        "SHA256": hashlib.sha256(),
        "SHA512": hashlib.sha512(),
    }
    sz = os.path.getsize(fp)
    with open(fp, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            for h in algos.values():
                h.update(chunk)

    print(f"  {fmt('Size'.ljust(9), ui['secondary'], True)} {fmt(fmt_bytes(sz), ui['text'])}")
    matched = False
    for name, h in algos.items():
        digest = h.hexdigest()
        if expected and digest == expected:
            matched = True
            badge = " " + fmt("[MATCH]", ui["success"], True)
        else:
            badge = ""
        print(f"  {fmt(name.ljust(9), ui['secondary'], True)} {fmt(digest, ui['accent'])}{badge}")

    if expected and not matched:
        print(f"\n  {fmt('✘ MISMATCH against expected hash:', ui['error'], True)} {fmt(expected, ui['muted'])}")
    print()


def cmd_loc(args: list[str], theme: dict) -> None:
    ui = theme["ui"]
    target = os.path.abspath(args[0] if args else ".")
    if not os.path.isdir(target):
        print(fmt(f"  Directory not found: {target}", ui["error"], True))
        return

    header(f"Code Line Counter: {target}", theme)
    lang_map = {
        ".py": "Python", ".ps1": "PowerShell", ".psm1": "PowerShell",
        ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".html": "HTML", ".css": "CSS/SCSS", ".scss": "CSS/SCSS",
        ".json": "JSON", ".md": "Markdown", ".lua": "Lua",
        ".cmd": "Batch/CMD", ".bat": "Batch/CMD", ".sh": "Shell",
        ".go": "Go", ".rs": "Rust", ".c": "C/C++", ".cpp": "C/C++", ".h": "C/C++",
        ".java": "Java", ".cs": "C#", ".sql": "SQL", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    }
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}
    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # files, code, blank

    stack = [target]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.lower() not in skip_dirs:
                                stack.append(entry.path)
                        else:
                            ext = os.path.splitext(entry.name)[1].lower()
                            lang = lang_map.get(ext)
                            if not lang:
                                continue
                            code_l = blank_l = 0
                            with open(entry.path, "r", encoding="utf-8", errors="ignore") as f:
                                for line in f:
                                    if line.strip():
                                        code_l += 1
                                    else:
                                        blank_l += 1
                            stats[lang][0] += 1
                            stats[lang][1] += code_l
                            stats[lang][2] += blank_l
                    except OSError:
                        continue
        except OSError:
            continue

    if not stats:
        print(fmt("  No recognized source files found.", ui["muted"]))
        print()
        return

    ranked = sorted(stats.items(), key=lambda kv: kv[1][1], reverse=True)
    tot_f = sum(v[0] for _, v in ranked)
    tot_c = sum(v[1] for _, v in ranked)
    tot_b = sum(v[2] for _, v in ranked)
    max_c = max(1, ranked[0][1][1])

    print(f"  {fmt('Language'.ljust(14), ui['muted'], True)} {fmt('Files'.rjust(6), ui['muted'], True)} {fmt('Code'.rjust(8), ui['muted'], True)} {fmt('Blank'.rjust(8), ui['muted'], True)}  {fmt('Share', ui['muted'], True)}")
    print(fmt("  " + "─" * 58, ui["border"]))
    for lang, (f_cnt, c_cnt, b_cnt) in ranked:
        bar_len = max(1, round((c_cnt / max_c) * 14))
        bar = fmt("━" * bar_len, ui["primary"], True) + fmt("─" * (14 - bar_len), ui["muted"])
        pct = (c_cnt / tot_c * 100.0) if tot_c else 0.0
        print(f"  {fmt(lang.ljust(14), ui['accent'], True)} {fmt(f'{f_cnt:>6,}', ui['text'])} {fmt(f'{c_cnt:>8,}', ui['success'])} {fmt(f'{b_cnt:>8,}', ui['muted'])}  {bar} {fmt(f'{pct:4.1f}%', ui['muted'])}")
    print(fmt("  " + "─" * 58, ui["border"]))
    print(f"  {fmt('Total'.ljust(14), ui['primary'], True)} {fmt(f'{tot_f:>6,}', ui['text'], True)} {fmt(f'{tot_c:>8,}', ui['success'], True)} {fmt(f'{tot_b:>8,}', ui['muted'])}")
    print()


def cmd_jsonfmt(args: list[str], theme: dict) -> None:
    ui = theme["ui"]
    pal = theme["palette"]
    if not args:
        print(fmt("  Usage: jsonfmt <file.json>", ui["warning"]))
        return
    fp = args[0]
    if not os.path.isfile(fp):
        print(fmt(f"  File not found: {fp}", ui["error"], True))
        return
    try:
        with open(fp, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as exc:
        print(fmt(f"  Invalid JSON: {exc}", ui["error"], True))
        return

    header(f"JSON Valid & Formatted: {os.path.basename(fp)}", theme)
    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    for line in pretty.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            print(f"  {fmt(k, ui['primary'])}:{fmt(v, pal.get('green', ui['accent']))}")
        else:
            print(f"  {fmt(line, ui['muted'])}")
    print()


def main() -> None:
    enable_vt()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    theme = load_theme()
    args = sys.argv[1:]
    if not args or args[0] in ("--menu", "tools"):
        cmd_tools_hub(theme, interactive=("-i" in args or "--interactive" in args))
    elif args[0] == "--bigfiles":
        cmd_bigfiles(args[1:], theme)
    elif args[0] == "--procs":
        cmd_procs(args[1:], theme)
    elif args[0] == "--netinfo":
        cmd_netinfo(theme, args[1:])
    elif args[0] == "--hash":
        cmd_hashfile(args[1:], theme)
    elif args[0] == "--loc":
        cmd_loc(args[1:], theme)
    elif args[0] == "--jsonfmt":
        cmd_jsonfmt(args[1:], theme)
    else:
        cmd_tools_hub(theme, interactive=False)


if __name__ == "__main__":
    main()
