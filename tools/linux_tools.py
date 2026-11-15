#!/usr/bin/env python3
"""TricksXTech Safe Linux-Style CLI Utilities (grep, head, tail, wc, df, du, udiff, b64/jwt, ss)."""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import ctypes
import datetime
import difflib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.parse

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, fmt_bytes, header, load_theme

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "dist", "build"}
LINK_TAGS = (
    getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003),
    getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C),
)
CLOUD_ATTRS = 0x1000 | 0x40000 | 0x400000


def _read_stdin_text() -> str:
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    return sys.stdin.read()


def _is_binary_chunk(data: bytes) -> bool:
    return b"\x00" in data[:2048]


def cmd_grep(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="grep", description="Search pattern in files or stdin")
    p.add_argument("-i", "--ignore-case", action="store_true", help="Case-insensitive match")
    p.add_argument("-r", "--recursive", action="store_true", help="Recurse into directories")
    p.add_argument("-n", "--line-number", action="store_true", default=True, help="Show line numbers")
    p.add_argument("-v", "--invert-match", action="store_true", help="Select non-matching lines")
    p.add_argument("-c", "--count", action="store_true", help="Print only match counts per file")
    p.add_argument("pattern", help="Regex or text pattern")
    p.add_argument("paths", nargs="*", help="Files or directories (or pipe stdin)")
    args = p.parse_args(argv)

    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        rx = re.compile(args.pattern, flags)
    except re.error:
        rx = re.compile(re.escape(args.pattern), flags)

    def highlight_line(line: str) -> str:
        if args.invert_match:
            return fmt(line, ui["text"])
        out: list[str] = []
        last = 0
        for m in rx.finditer(line):
            if m.start() > last:
                out.append(fmt(line[last:m.start()], ui["text"]))
            out.append(fmt(line[m.start():m.end()], ui["error"], bold=True))
            last = m.end()
        if last < len(line):
            out.append(fmt(line[last:], ui["text"]))
        return "".join(out)

    def scan_lines(label: str | None, lines_iter) -> int:
        matches = 0
        for idx, raw in enumerate(lines_iter, 1):
            line = raw.rstrip("\r\n")
            hit = bool(rx.search(line))
            if args.invert_match:
                hit = not hit
            if hit:
                matches += 1
                if not args.count:
                    prefix = (fmt(label, ui["secondary"]) + fmt(":", ui["muted"])) if label else ""
                    num_s = fmt(str(idx), ui["accent"]) + fmt(":", ui["muted"])
                    print(f"{prefix}{num_s}{highlight_line(line)}")
        if args.count and matches > 0:
            prefix = (fmt(label, ui["secondary"]) + fmt(":", ui["muted"])) if label else ""
            print(f"{prefix}{fmt(str(matches), ui['accent'], True)}")
        return matches

    if not args.paths:
        if sys.stdin is not None and not sys.stdin.isatty():
            scan_lines(None, sys.stdin)
            return
        args.paths = ["."]
        args.recursive = True

    targets: list[str] = []
    for path in args.paths:
        if os.path.isfile(path):
            targets.append(path)
        elif os.path.isdir(path):
            if args.recursive or len(args.paths) == 1:
                for root, dirs, files in os.walk(path):
                    dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                    for fn in sorted(files):
                        targets.append(os.path.join(root, fn))
        else:
            print(fmt(f"grep: {path}: No such file or directory", ui["warning"]), file=sys.stderr)

    multi = len(targets) > 1
    total_hits = 0
    for fp in targets:
        try:
            with open(fp, "rb") as bf:
                head_chunk = bf.read(2048)
                if _is_binary_chunk(head_chunk):
                    continue
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                total_hits += scan_lines(fp if multi else None, f)
        except OSError:
            continue

    if total_hits == 0 and not args.count:
        print(fmt("  No matches found.", ui["muted"]))


def cmd_head(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="head", description="Output first N lines of files or stdin")
    p.add_argument("-n", "--lines", type=int, default=10, help="Number of lines (default 10)")
    p.add_argument("files", nargs="*", help="Files to inspect (or pipe stdin)")
    args = p.parse_args(argv)
    limit = max(0, args.lines)

    if not args.files:
        text = _read_stdin_text()
        if not text:
            print(fmt("  Usage: head [-n 10] <file> (or pipe stdin)", ui["muted"]))
            return
        for line in text.splitlines()[:limit]:
            print(line)
        return

    multi = len(args.files) > 1
    for i, fp in enumerate(args.files):
        if multi:
            if i > 0:
                print()
            print(fmt(f"==> {fp} <==", ui["accent"], True))
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f):
                    if idx >= limit:
                        break
                    print(line.rstrip("\r\n"))
        except OSError as exc:
            print(fmt(f"head: {fp}: {exc}", ui["error"]), file=sys.stderr)


def cmd_tail(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="tail", description="Output last N lines (supports -f follow)")
    p.add_argument("-n", "--lines", type=int, default=10, help="Number of trailing lines (default 10)")
    p.add_argument("-f", "--follow", action="store_true", help="Follow file growth in real time")
    p.add_argument("files", nargs="*", help="Files to inspect (or pipe stdin)")
    args = p.parse_args(argv)
    limit = max(0, args.lines)

    if not args.files:
        text = _read_stdin_text()
        if not text:
            print(fmt("  Usage: tail [-n 10] [-f] <file> (or pipe stdin)", ui["muted"]))
            return
        lines = text.splitlines()
        for line in (lines[-limit:] if limit > 0 else []):
            print(line)
        return

    multi = len(args.files) > 1
    for i, fp in enumerate(args.files):
        if multi:
            if i > 0:
                print()
            print(fmt(f"==> {fp} <==", ui["accent"], True))
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.read().splitlines()
                for line in (all_lines[-limit:] if limit > 0 else []):
                    print(line)
        except OSError as exc:
            print(fmt(f"tail: {fp}: {exc}", ui["error"]), file=sys.stderr)
            continue

    if args.follow and args.files:
        target = args.files[0]
        print(fmt(f"--- following {target} (Ctrl+C to stop) ---", ui["muted"]))
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if line:
                        print(line.rstrip("\r\n"), flush=True)
                    else:
                        time.sleep(0.35)
        except KeyboardInterrupt:
            print()
        except OSError as exc:
            print(fmt(f"tail -f error: {exc}", ui["error"]), file=sys.stderr)


def cmd_wc(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="wc", description="Count lines, words, and bytes")
    p.add_argument("-l", "--lines", action="store_true", help="Show line count")
    p.add_argument("-w", "--words", action="store_true", help="Show word count")
    p.add_argument("-c", "--bytes", action="store_true", help="Show byte count")
    p.add_argument("files", nargs="*", help="Files (or pipe stdin)")
    args = p.parse_args(argv)
    show_all = not (args.lines or args.words or args.bytes)

    def render_row(lc: int, wc: int, bc: int, label: str, bold: bool = False) -> None:
        parts: list[str] = []
        if show_all or args.lines:
            parts.append(fmt(f"{lc:>8,}", ui["accent"], bold))
        if show_all or args.words:
            parts.append(fmt(f"{wc:>8,}", ui["primary"], bold))
        if show_all or args.bytes:
            parts.append(fmt(f"{bc:>10,}", ui["text"], bold))
        parts.append(fmt(" " + label, ui["secondary"] if bold else ui["muted"], bold))
        print(" ".join(parts))

    header_parts: list[str] = []
    if show_all or args.lines:
        header_parts.append(f"{'LINES':>8}")
    if show_all or args.words:
        header_parts.append(f"{'WORDS':>8}")
    if show_all or args.bytes:
        header_parts.append(f"{'BYTES':>10}")
    header_parts.append(" TARGET")
    print(fmt(" ".join(header_parts), ui["muted"], True))

    if not args.files:
        text = _read_stdin_text()
        if not text:
            print(fmt("  Usage: wc [-lwc] <file...> (or pipe stdin)", ui["muted"]))
            return
        b = text.encode("utf-8", errors="replace")
        render_row(len(text.splitlines()), len(text.split()), len(b), "<stdin>")
        return

    tot_l = tot_w = tot_b = 0
    ok_count = 0
    for fp in args.files:
        try:
            with open(fp, "rb") as f:
                raw = f.read()
            txt = raw.decode("utf-8", errors="replace")
            lc = raw.count(b"\n")
            if raw and not raw.endswith(b"\n"):
                lc += 1
            wc = len(txt.split())
            bc = len(raw)
            tot_l += lc
            tot_w += wc
            tot_b += bc
            ok_count += 1
            render_row(lc, wc, bc, fp)
        except OSError as exc:
            print(fmt(f"wc: {fp}: {exc}", ui["error"]), file=sys.stderr)

    if ok_count > 1:
        print(fmt("─" * 44, ui["border"]))
        render_row(tot_l, tot_w, tot_b, "total", bold=True)


def _get_logical_drives() -> list[str]:
    if os.name != "nt":
        return ["/"]
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    drives: list[str] = []
    for idx in range(26):
        if mask & (1 << idx):
            letter = chr(ord("A") + idx)
            root = f"{letter}:\\"
            if ctypes.windll.kernel32.GetDriveTypeW(root) in (2, 3, 4, 6):
                drives.append(root)
    return drives


def cmd_df(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="df", description="Display disk filesystem usage")
    p.add_argument("path", nargs="?", help="Optional specific drive or folder path")
    args = p.parse_args(argv)

    header("Filesystem Disk Usage (df)", theme)
    roots = [os.path.abspath(args.path)] if args.path else _get_logical_drives()
    print(fmt(f"  {'MOUNT':<10} {'SIZE':>10} {'USED':>10} {'AVAIL':>10} {'USE%':>7}  {'USAGE BAR'}", ui["muted"], True))
    print(fmt("  " + "─" * 68, ui["border"]))

    for root in roots:
        try:
            usage = shutil.disk_usage(root)
        except OSError:
            continue
        pct = (usage.used / usage.total * 100.0) if usage.total > 0 else 0.0
        filled = round((pct / 100.0) * 18)
        bar = "█" * filled + "░" * (18 - filled)
        c = ui["error"] if pct >= 90 else (ui["warning"] if pct >= 75 else ui["success"])
        label = root[:9]
        print(
            f"  {fmt(label.ljust(10), ui['primary'], True)}"
            f" {fmt(fmt_bytes(usage.total).rjust(10), ui['text'])}"
            f" {fmt(fmt_bytes(usage.used).rjust(10), ui['text'])}"
            f" {fmt(fmt_bytes(usage.free).rjust(10), ui['accent'])}"
            f" {fmt(f'{pct:5.1f}%', c, True)}  {fmt(bar, c)}"
        )
    print()


def _dir_size_fast(root_path: str) -> int:
    total = 0
    stack = [root_path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for ent in it:
                    try:
                        st = ent.stat(follow_symlinks=False)
                        if os.name == "nt":
                            reparse = getattr(st, "st_reparse_tag", 0)
                            attrs = getattr(st, "st_file_attributes", 0)
                            if stat.S_ISLNK(st.st_mode) or reparse in LINK_TAGS:
                                continue
                            if ent.is_dir(follow_symlinks=False):
                                stack.append(ent.path)
                                continue
                            if attrs & CLOUD_ATTRS:
                                continue
                            total += st.st_size
                        else:
                            if ent.is_dir(follow_symlinks=False):
                                stack.append(ent.path)
                            elif ent.is_file(follow_symlinks=False):
                                total += st.st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def cmd_du(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="du", description="Summarize directory & file sizes (depth 1)")
    p.add_argument("path", nargs="?", default=".", help="Directory to inspect (default: .)")
    p.add_argument("-n", "--limit", type=int, default=25, help="Max entries to show (default 25)")
    args = p.parse_args(argv)

    target = os.path.abspath(args.path)
    header(f"Directory Disk Usage (du) // {target}", theme)
    if not os.path.exists(target):
        print(fmt(f"  Path not found: {target}", ui["error"]))
        return
    if os.path.isfile(target):
        print(f"  {fmt(fmt_bytes(os.path.getsize(target)).rjust(12), ui['accent'], True)}  {fmt(target, ui['text'])}")
        print()
        return

    rows: list[tuple[int, str, bool]] = []
    grand = 0
    try:
        with os.scandir(target) as it:
            for ent in it:
                try:
                    is_d = ent.is_dir(follow_symlinks=False)
                    sz = _dir_size_fast(ent.path) if is_d else ent.stat(follow_symlinks=False).st_size
                    rows.append((sz, ent.name, is_d))
                    grand += sz
                except OSError:
                    continue
    except OSError as exc:
        print(fmt(f"  Cannot read directory: {exc}", ui["error"]))
        return

    rows.sort(key=lambda r: r[0], reverse=True)
    for sz, name, is_d in rows[: max(1, args.limit)]:
        pct = (sz / grand * 100.0) if grand > 0 else 0.0
        tag = "/" if is_d else ""
        c = ui["primary"] if is_d else ui["text"]
        print(f"  {fmt(fmt_bytes(sz).rjust(11), ui['accent'], True)}  {fmt(f'{pct:5.1f}%', ui['muted'])}  {fmt(name + tag, c, is_d)}")
    print(fmt("  " + "─" * 52, ui["border"]))
    print(f"  {fmt(fmt_bytes(grand).rjust(11), ui['success'], True)}  {fmt('100.0%', ui['muted'])}  {fmt('TOTAL (' + str(len(rows)) + ' items)', ui['text'], True)}")
    print()


def cmd_diff(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="udiff", description="Colorized unified diff between two text files")
    p.add_argument("file_a", help="Original file")
    p.add_argument("file_b", help="Modified file")
    p.add_argument("-U", "--context", type=int, default=3, help="Context lines (default 3)")
    args = p.parse_args(argv)

    try:
        with open(args.file_a, "r", encoding="utf-8", errors="replace") as fa:
            lines_a = fa.readlines()
        with open(args.file_b, "r", encoding="utf-8", errors="replace") as fb:
            lines_b = fb.readlines()
    except OSError as exc:
        print(fmt(f"udiff error: {exc}", ui["error"]), file=sys.stderr)
        return

    diff_lines = list(
        difflib.unified_diff(lines_a, lines_b, fromfile=args.file_a, tofile=args.file_b, n=args.context)
    )
    if not diff_lines:
        print(fmt(f"  No differences between {args.file_a} and {args.file_b}.", ui["success"], True))
        return

    for raw in diff_lines:
        line = raw.rstrip("\r\n")
        if line.startswith("+++") or line.startswith("---"):
            print(fmt(line, ui["primary"], True))
        elif line.startswith("@@"):
            print(fmt(line, ui["accent"], True))
        elif line.startswith("+"):
            print(fmt(line, ui["success"]))
        elif line.startswith("-"):
            print(fmt(line, ui["error"]))
        else:
            print(fmt(line, ui["muted"]))


def _b64_pad_decode(token: str) -> bytes:
    rem = len(token) % 4
    if rem:
        token += "=" * (4 - rem)
    return base64.urlsafe_b64decode(token.encode("ascii"))


def cmd_b64(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="b64", description="Base64 / URL / Hex encoder-decoder & JWT inspector")
    p.add_argument("-d", "--decode", action="store_true", help="Decode input")
    p.add_argument("--hex", action="store_true", help="Use Hex instead of Base64")
    p.add_argument("--url", action="store_true", help="Use URL percent encoding")
    p.add_argument("--jwt", action="store_true", help="Decode JWT header and payload (read-only)")
    p.add_argument("text", nargs="*", help="Input string (or pipe stdin)")
    args = p.parse_args(argv)

    raw_text = " ".join(args.text) if args.text else _read_stdin_text().strip()
    if not raw_text:
        print(fmt("  Usage: b64 [-d] [--hex|--url|--jwt] <text> (or pipe stdin)", ui["muted"]))
        return

    if args.jwt:
        parts = raw_text.strip().split(".")
        if len(parts) < 2:
            print(fmt("  Invalid JWT format (expected header.payload.signature).", ui["error"]))
            return
        header("JWT Token Inspector (Read-Only)", theme)
        for label, seg in (("HEADER", parts[0]), ("PAYLOAD", parts[1])):
            try:
                decoded = _b64_pad_decode(seg).decode("utf-8", errors="replace")
                parsed = json.loads(decoded)
                print("  " + fmt(label, ui["secondary"], True))
                for line in json.dumps(parsed, indent=2).splitlines():
                    print("  " + fmt(line, ui["accent"] if label == "HEADER" else ui["text"]))
                if label == "PAYLOAD" and isinstance(parsed, dict):
                    for ts_key in ("iat", "nbf", "exp"):
                        if isinstance(parsed.get(ts_key), (int, float)):
                            dt = datetime.datetime.fromtimestamp(parsed[ts_key], tz=datetime.timezone.utc)
                            print("  " + fmt(f"  -> {ts_key}: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}", ui["muted"]))
            except Exception as exc:
                print(fmt(f"  Failed decoding {label}: {exc}", ui["error"]))
        if len(parts) >= 3:
            print("  " + fmt(f"SIGNATURE: {len(parts[2])} chars (not verified locally)", ui["muted"]))
        print()
        return

    try:
        if args.url:
            out = urllib.parse.unquote(raw_text) if args.decode else urllib.parse.quote(raw_text, safe="")
        elif args.hex:
            if args.decode:
                out = bytes.fromhex(raw_text.replace(" ", "")).decode("utf-8", errors="replace")
            else:
                out = raw_text.encode("utf-8").hex()
        else:
            if args.decode:
                out = base64.b64decode(raw_text.encode("ascii"), validate=False).decode("utf-8", errors="replace")
            else:
                out = base64.b64encode(raw_text.encode("utf-8")).decode("ascii")
        print(out)
    except (binascii.Error, ValueError) as exc:
        print(fmt(f"Decode error: {exc}", ui["error"]), file=sys.stderr)


def cmd_ss(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="ss", description="Socket & port inspector with PID/process mapping")
    p.add_argument("-l", "--listening", action="store_true", help="Show LISTENING sockets only")
    p.add_argument("-t", "--tcp", action="store_true", help="Show TCP sockets only")
    p.add_argument("-u", "--udp", action="store_true", help="Show UDP sockets only")
    p.add_argument("-p", "--filter", default="", help="Filter by port or process name")
    args = p.parse_args(argv)

    header("Socket & Port Statistics (ss)", theme)
    pid_map: dict[str, str] = {}
    try:
        tl = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=6)
        for row in csv.reader(io.StringIO(tl.stdout)):
            if len(row) >= 2:
                pid_map[row[1].strip()] = row[0].strip()
    except Exception:
        pass

    try:
        ns = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=8)
    except Exception as exc:
        print(fmt(f"  netstat failed: {exc}", ui["error"]))
        return

    filt = args.filter.lower().strip()
    rows: list[tuple[str, str, str, str, str, str]] = []
    for raw in ns.stdout.splitlines():
        parts = raw.split()
        if not parts:
            continue
        proto = parts[0].upper()
        if proto not in ("TCP", "UDP"):
            continue
        if args.tcp and not args.udp and proto != "TCP":
            continue
        if args.udp and not args.tcp and proto != "UDP":
            continue

        if proto == "TCP" and len(parts) >= 5:
            local_a, remote_a, state, pid = parts[1], parts[2], parts[3], parts[4]
        elif proto == "UDP" and len(parts) >= 4:
            local_a, remote_a, state, pid = parts[1], parts[2], "UNCONN", parts[3]
        else:
            continue

        if args.listening and state not in ("LISTENING", "UNCONN"):
            continue
        pname = pid_map.get(pid, "System" if pid in ("0", "4") else "?")
        if filt and (filt not in local_a.lower() and filt not in pname.lower() and filt not in state.lower()):
            continue
        rows.append((proto, state, local_a, remote_a, pid, pname))

    # Sort LISTENING first, then ESTABLISHED
    order = {"LISTENING": 0, "ESTABLISHED": 1, "UNCONN": 2}
    rows.sort(key=lambda r: (order.get(r[1], 3), r[2]))

    print(fmt(f"  {'PROTO':<6} {'STATE':<13} {'LOCAL ADDRESS':<24} {'REMOTE ADDRESS':<22} {'PID':>6}  {'PROCESS'}", ui["muted"], True))
    print(fmt("  " + "─" * 92, ui["border"]))
    for proto, state, local_a, remote_a, pid, pname in rows[:45]:
        sc = ui["accent"] if state == "LISTENING" else (ui["success"] if state == "ESTABLISHED" else ui["muted"])
        la = (local_a[:21] + "...") if len(local_a) > 24 else local_a
        ra = (remote_a[:19] + "...") if len(remote_a) > 22 else remote_a
        print(
            f"  {fmt(proto.ljust(6), ui['primary'])}"
            f" {fmt(state.ljust(13), sc, state in ('LISTENING', 'ESTABLISHED'))}"
            f" {fmt(la.ljust(24), ui['text'])}"
            f" {fmt(ra.ljust(22), ui['muted'])}"
            f" {fmt(pid.rjust(6), ui['muted'])}  {fmt(pname, ui['secondary'])}"
        )
    if len(rows) > 45:
        print(fmt(f"  ... {len(rows) - 45} more sockets (filter with: ss -p <port_or_name>)", ui["muted"]))
    print()


def main() -> None:
    enable_vt()
    theme = load_theme()
    args = sys.argv[1:]
    if not args:
        print("linux_tools.py subcommands: --grep, --head, --tail, --wc, --df, --du, --diff, --b64, --ss")
        return

    cmd = args[0]
    rest = args[1:]
    dispatch = {
        "--grep": cmd_grep,
        "--head": cmd_head,
        "--tail": cmd_tail,
        "--wc": cmd_wc,
        "--df": cmd_df,
        "--du": cmd_du,
        "--diff": cmd_diff,
        "--b64": cmd_b64,
        "--ss": cmd_ss,
    }
    fn = dispatch.get(cmd)
    if fn:
        fn(rest, theme)
    else:
        print(f"Unknown linux_tools subcommand: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
