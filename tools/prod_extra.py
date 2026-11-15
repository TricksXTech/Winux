#!/usr/bin/env python3
"""
TricksXTech Productivity, Utility & Developer Workflow CLI Tools (20 tools)
"""

import argparse
import ast
import csv
import datetime as dt
import io
import json
import math
import operator
import os
import re
import secrets
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from free_tools import enable_vt, load_theme, fmt, gradient, fmt_bytes, header, get_root
from vpn_tool import ensure_vpn_for_tool


# ── Shared Helpers ────────────────────────────────────────────────────────────

def get_data_dir() -> Path:
    override = os.environ.get("TX_DATA_DIR", "").strip()
    base = Path(override) if override else Path(get_root()) / "config" / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def parse_duration(spec: str) -> float:
    raw = (spec or "").strip().lower()
    if not raw:
        raise ValueError("Empty duration.")
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        val = float(raw)
        if val <= 0:
            raise ValueError("Duration must be > 0.")
        return val
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|m|min|mins|s|sec|secs)", raw)
    if not matches:
        raise ValueError(f"Invalid duration '{spec}'. Examples: 90, 45s, 5m, 1h30m.")
    rebuilt = "".join(a + b for a, b in matches)
    if rebuilt != re.sub(r"\s+", "", raw):
        raise ValueError(f"Invalid duration '{spec}'. Examples: 90, 45s, 5m, 1h30m.")
    total = 0.0
    for num_str, unit in matches:
        num = float(num_str)
        if unit.startswith("h"):
            total += num * 3600.0
        elif unit.startswith("m"):
            total += num * 60.0
        else:
            total += num
    if total <= 0:
        raise ValueError("Duration must be > 0.")
    return total


def format_hms(seconds: float, show_ms: bool = False) -> str:
    seconds = max(0.0, seconds)
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 100)
    if hrs > 0:
        base = f"{hrs:02d}:{mins:02d}:{secs:02d}"
    else:
        base = f"{mins:02d}:{secs:02d}"
    return f"{base}.{ms:02d}" if show_ms else base


def _fetch_json_url(url: str, timeout: int = 12) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "TricksXTech-CLI/2.0 (curl-compatible)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


# ── 1. Stopwatch ──────────────────────────────────────────────────────────────

def cmd_stopwatch(argv, theme):
    ap = argparse.ArgumentParser(prog="stopwatch", description="Interactive terminal stopwatch with lap tracking")
    ap.add_argument("--seconds", type=float, default=0.0, help="Auto-stop after N seconds (optional)")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    header("TricksXTech // Stopwatch", theme)
    has_msvcrt = os.name == "nt" and sys.stdin.isatty()
    if has_msvcrt:
        import msvcrt
        print("  " + fmt("Controls: [Space] Pause/Resume   [L] Record Lap   [Q / Ctrl+C] Stop", ui["muted"]))
    else:
        print("  " + fmt("Press Ctrl+C to stop stopwatch.", ui["muted"]))
    print()

    start = time.monotonic()
    paused_total = 0.0
    pause_started = None
    laps = []
    last_lap_elapsed = 0.0

    try:
        while True:
            now = time.monotonic()
            elapsed = (pause_started if pause_started is not None else now) - start - paused_total
            if args.seconds > 0 and elapsed >= args.seconds:
                elapsed = args.seconds
                status = fmt("DONE", ui["success"], True)
                print(f"\r  ⏱  {fmt(format_hms(elapsed, True), ui['primary'], True)}   [{status}]   ", end="", flush=True)
                break

            state_tag = fmt("PAUSED", ui["warning"], True) if pause_started is not None else fmt("RUNNING", ui["success"], True)
            print(f"\r  ⏱  {fmt(format_hms(elapsed, True), ui['primary'], True)}   [{state_tag}]   Laps: {len(laps)}   ", end="", flush=True)

            if has_msvcrt and msvcrt.kbhit():
                ch = msvcrt.getwch().lower()
                if ch == " ":
                    if pause_started is None:
                        pause_started = time.monotonic()
                    else:
                        paused_total += time.monotonic() - pause_started
                        pause_started = None
                elif ch == "l":
                    split = elapsed - last_lap_elapsed
                    last_lap_elapsed = elapsed
                    laps.append((len(laps) + 1, elapsed, split))
                    print()
                    print(f"    {fmt('Lap #' + str(len(laps)), ui['accent'], True)}  Total: {fmt(format_hms(elapsed, True), ui['text'])}  Split: {fmt('+' + format_hms(split, True), ui['secondary'])}")
                elif ch in ("q", "\x03"):
                    break
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass

    final_elapsed = ((pause_started if pause_started is not None else time.monotonic()) - start - paused_total)
    print()
    print()
    print(f"  {fmt('Final Elapsed:', ui['secondary'], True)} {fmt(format_hms(final_elapsed, True), ui['primary'], True)}")
    if laps:
        print(f"  {fmt('Recorded Laps:', ui['muted'])} {len(laps)}")
    print()
    return 0


# ── 2. Countdown ──────────────────────────────────────────────────────────────

def _run_timer_bar(total_secs: float, label: str, theme: dict, no_beep: bool = False) -> bool:
    ui = theme["ui"]
    stops = [ui.get("gradientStart", ui["primary"]), ui.get("gradientMid", ui["secondary"]), ui.get("gradientEnd", ui["accent"])]
    t0 = time.monotonic()
    width = 30
    try:
        while True:
            elapsed = time.monotonic() - t0
            rem = max(0.0, total_secs - elapsed)
            pct = min(1.0, elapsed / total_secs) if total_secs > 0 else 1.0
            filled = int(round(pct * width))
            bar = gradient("█" * filled, stops, False) + fmt("░" * (width - filled), ui["border"])
            print(f"\r  {fmt(label, ui['secondary'], True)}  [{bar}]  {fmt(f'{pct*100:5.1f}%', ui['accent'])}  Rem: {fmt(format_hms(rem), ui['primary'], True)}  ", end="", flush=True)
            if elapsed >= total_secs:
                break
            time.sleep(min(0.1, rem))
        print()
        if not no_beep:
            sys.stdout.write("\a")
            sys.stdout.flush()
        return True
    except KeyboardInterrupt:
        print()
        print("  " + fmt("Timer cancelled.", ui["warning"]))
        return False


def cmd_countdown(argv, theme):
    ap = argparse.ArgumentParser(prog="countdown", description="Live terminal countdown timer")
    ap.add_argument("duration", help="Duration (e.g. 90, 45s, 5m, 1h30m)")
    ap.add_argument("--msg", default="Time is up!", help="Completion message")
    ap.add_argument("--no-beep", action="store_true", help="Do not ring terminal bell when finished")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    try:
        total = parse_duration(args.duration)
    except ValueError as ex:
        print("  " + fmt(str(ex), ui["error"], True))
        return 1

    header(f"TricksXTech // Countdown ({format_hms(total)})", theme)
    ok = _run_timer_bar(total, "Timer", theme, no_beep=args.no_beep)
    if ok:
        print("  " + fmt(f"✓ {args.msg}", ui["success"], True))
        print()
        return 0
    return 1


# ── 3. Todo ───────────────────────────────────────────────────────────────────

def cmd_todo(argv, theme):
    ap = argparse.ArgumentParser(prog="todo", description="Persistent JSON task & to-do manager")
    sub = ap.add_subparsers(dest="action")

    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("text", nargs="+", help="Task description")
    p_add.add_argument("-p", "--priority", choices=["high", "med", "low"], default="med")

    p_done = sub.add_parser("done", help="Mark task ID completed")
    p_done.add_argument("id", type=int)

    p_rm = sub.add_parser("rm", help="Remove task ID")
    p_rm.add_argument("id", type=int)

    sub.add_parser("clear", help="Remove completed tasks")
    sub.add_parser("list", help="List tasks")

    args = ap.parse_args(argv)
    ui = theme["ui"]
    db_path = get_data_dir() / "todos.json"
    tasks = _load_json(db_path, [])

    action = args.action or "list"
    if action == "add":
        next_id = max([int(t.get("id", 0)) for t in tasks], default=0) + 1
        item = {
            "id": next_id,
            "text": " ".join(args.text).strip(),
            "priority": args.priority,
            "done": False,
            "created": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        tasks.append(item)
        _save_json(db_path, tasks)
        header("TricksXTech // Todo", theme)
        print(f"  {fmt('Added', ui['success'], True)} #{next_id} [{args.priority}]: {fmt(item['text'], ui['text'])}\n")
        return 0

    if action == "done":
        for t in tasks:
            if t.get("id") == args.id:
                t["done"] = True
                t["completed"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
                _save_json(db_path, tasks)
                print(f"  {fmt('Completed', ui['success'], True)} #{args.id}: {t['text']}")
                return 0
        print(f"  {fmt(f'Task #{args.id} not found.', ui['error'], True)}")
        return 1

    if action == "rm":
        new_tasks = [t for t in tasks if t.get("id") != args.id]
        if len(new_tasks) == len(tasks):
            print(f"  {fmt(f'Task #{args.id} not found.', ui['error'], True)}")
            return 1
        _save_json(db_path, new_tasks)
        print(f"  {fmt(f'Removed task #{args.id}.', ui['warning'])}")
        return 0

    if action == "clear":
        kept = [t for t in tasks if not t.get("done")]
        removed = len(tasks) - len(kept)
        _save_json(db_path, kept)
        print(f"  {fmt(f'Cleared {removed} completed task(s).', ui['success'])}")
        return 0

    header("TricksXTech // Todo List", theme)
    if not tasks:
        print("  " + fmt("No tasks yet. Use: todo add <task description> [-p high|med|low]", ui["muted"]))
        print()
        return 0
    prio_rank = {"high": 0, "med": 1, "low": 2}
    tasks_sorted = sorted(tasks, key=lambda x: (bool(x.get("done")), prio_rank.get(x.get("priority", "med"), 1), x.get("id", 0)))
    for t in tasks_sorted:
        done = bool(t.get("done"))
        mark = fmt("[✓]", ui["success"], True) if done else fmt("[ ]", ui["accent"])
        prio = t.get("priority", "med").upper().ljust(4)
        p_col = ui["error"] if prio.startswith("HIGH") else (ui["warning"] if prio.startswith("MED") else ui["muted"])
        txt_col = ui["muted"] if done else ui["text"]
        print(f"  {fmt('#' + str(t['id']).rjust(2), ui['primary'], True)}  {mark}  {fmt(prio, p_col)}  {fmt(t['text'], txt_col)}")
    print()
    return 0


# ── 4. Notes ──────────────────────────────────────────────────────────────────

def cmd_notes(argv, theme):
    ap = argparse.ArgumentParser(prog="notes", description="Markdown/text quick notes manager")
    sub = ap.add_subparsers(dest="action")

    p_add = sub.add_parser("add", help="Add a note")
    p_add.add_argument("title", help="Note title")
    p_add.add_argument("--body", default="", help="Note body text (or omit to read stdin)")
    p_add.add_argument("--tag", default="general", help="Tag label")

    p_view = sub.add_parser("view", help="View a note by ID or title")
    p_view.add_argument("target")

    p_search = sub.add_parser("search", help="Search notes by keyword")
    p_search.add_argument("query")

    p_rm = sub.add_parser("rm", help="Delete note by ID")
    p_rm.add_argument("id", type=int)

    sub.add_parser("list", help="List all notes")

    args = ap.parse_args(argv)
    ui = theme["ui"]
    db_path = get_data_dir() / "notes.json"
    notes = _load_json(db_path, [])
    action = args.action or "list"

    if action == "add":
        body = args.body
        if not body:
            if not sys.stdin.isatty():
                body = sys.stdin.read().strip()
            else:
                print("  " + fmt("Enter note body (single line):", ui["muted"]))
                body = input("  > ").strip()
        next_id = max([int(n.get("id", 0)) for n in notes], default=0) + 1
        item = {
            "id": next_id,
            "title": args.title.strip(),
            "tag": args.tag.strip(),
            "body": body,
            "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        notes.append(item)
        _save_json(db_path, notes)
        print(f"  {fmt('Saved note', ui['success'], True)} #{next_id} [{item['tag']}]: {item['title']}")
        return 0

    if action == "view":
        target = args.target.strip()
        found = None
        for n in notes:
            if str(n.get("id")) == target or n.get("title", "").lower() == target.lower():
                found = n
                break
        if not found:
            print("  " + fmt(f"Note '{target}' not found.", ui["error"], True))
            return 1
        header(f"TricksXTech // Note #{found['id']}: {found['title']}", theme)
        print(f"  {fmt('Tag:', ui['muted'])} {fmt(found.get('tag', 'general'), ui['accent'])}   {fmt('Updated:', ui['muted'])} {found.get('updated', '')}")
        print(fmt("  " + "─" * 60, ui["border"]))
        for line in (found.get("body") or "(empty)").splitlines():
            print("  " + fmt(line, ui["text"]))
        print()
        return 0

    if action == "search":
        q = args.query.lower()
        hits = [n for n in notes if q in n.get("title", "").lower() or q in n.get("body", "").lower() or q in n.get("tag", "").lower()]
        header(f"TricksXTech // Notes Search: '{args.query}'", theme)
        if not hits:
            print("  " + fmt("No matching notes.", ui["muted"]))
            print()
            return 0
        for n in hits:
            print(f"  {fmt('#' + str(n['id']).rjust(2), ui['primary'], True)}  [{fmt(n.get('tag', ''), ui['accent'])}]  {fmt(n['title'], ui['text'], True)}")
        print()
        return 0

    if action == "rm":
        kept = [n for n in notes if n.get("id") != args.id]
        if len(kept) == len(notes):
            print("  " + fmt(f"Note #{args.id} not found.", ui["error"], True))
            return 1
        _save_json(db_path, kept)
        print("  " + fmt(f"Deleted note #{args.id}.", ui["warning"]))
        return 0

    header("TricksXTech // Notes", theme)
    if not notes:
        print("  " + fmt("No notes saved. Use: notes add \"Title\" --body \"...\" --tag work", ui["muted"]))
        print()
        return 0
    for n in notes:
        preview = (n.get("body") or "").replace("\n", " ")[:48]
        print(f"  {fmt('#' + str(n['id']).rjust(2), ui['primary'], True)}  [{fmt(n.get('tag', 'general').ljust(8), ui['accent'])}]  {fmt(n['title'].ljust(22), ui['text'], True)}  {fmt(preview, ui['muted'])}")
    print()
    return 0


# ── 5. Banner ─────────────────────────────────────────────────────────────────

_PIXEL_FONT = {
    "A": [" ▄█▄ ", "█   █", "█████", "█   █", "█   █"],
    "B": ["████ ", "█   █", "████ ", "█   █", "████ "],
    "C": [" ████", "█    ", "█    ", "█    ", " ████"],
    "D": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "F": ["█████", "█    ", "████ ", "█    ", "█    "],
    "G": [" ████", "█    ", "█  ██", "█   █", " ████"],
    "H": ["█   █", "█   █", "█████", "█   █", "█   █"],
    "I": ["█████", "  █  ", "  █  ", "  █  ", "█████"],
    "J": ["█████", "   █ ", "   █ ", "█  █ ", " ██  "],
    "K": ["█   █", "█  █ ", "███  ", "█  █ ", "█   █"],
    "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "O": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "P": ["████ ", "█   █", "████ ", "█    ", "█    "],
    "Q": [" ███ ", "█   █", "█ █ █", "█  █ ", " ██ █"],
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "S": [" ████", "█    ", " ███ ", "    █", "████ "],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "U": ["█   █", "█   █", "█   █", "█   █", " ███ "],
    "V": ["█   █", "█   █", "█   █", " █ █ ", "  █  "],
    "W": ["█   █", "█   █", "█ █ █", "██ ██", "█   █"],
    "X": ["█   █", " █ █ ", "  █  ", " █ █ ", "█   █"],
    "Y": ["█   █", " █ █ ", "  █  ", "  █  ", "  █  "],
    "Z": ["█████", "   █ ", "  █  ", " █   ", "█████"],
    "0": [" ███ ", "█  ██", "█ █ █", "██  █", " ███ "],
    "1": ["  █  ", " ██  ", "  █  ", "  █  ", "█████"],
    "2": ["████ ", "    █", " ███ ", "█    ", "█████"],
    "3": ["████ ", "    █", " ███ ", "    █", "████ "],
    "4": ["█   █", "█   █", "█████", "    █", "    █"],
    "5": ["█████", "█    ", "████ ", "    █", "████ "],
    "6": [" ████", "█    ", "████ ", "█   █", " ███ "],
    "7": ["█████", "    █", "   █ ", "  █  ", "  █  "],
    "8": [" ███ ", "█   █", " ███ ", "█   █", " ███ "],
    "9": [" ███ ", "█   █", " ████", "    █", "████ "],
    "-": ["     ", "     ", "████ ", "     ", "     "],
    "_": ["     ", "     ", "     ", "     ", "█████"],
    "!": ["  █  ", "  █  ", "  █  ", "     ", "  █  "],
    "?": [" ███ ", "    █", "  ██ ", "     ", "  █  "],
    ".": ["     ", "     ", "     ", "     ", "  █  "],
    ":": ["     ", "  █  ", "     ", "  █  ", "     "],
    "+": ["     ", "  █  ", "█████", "  █  ", "     "],
    "=": ["     ", "█████", "     ", "█████", "     "],
    "/": ["    █", "   █ ", "  █  ", " █   ", "█    "],
    " ": ["   ", "   ", "   ", "   ", "   "],
}


def cmd_banner(argv, theme):
    ap = argparse.ArgumentParser(prog="banner", description="Render themed ASCII/Unicode gradient text banners")
    ap.add_argument("text", nargs="+", help="Banner text")
    ap.add_argument("--font", choices=["block", "ascii"], default="block", help="Glyph fill style")
    ap.add_argument("--plain", action="store_true", help="Disable ANSI color gradient")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    stops = [ui.get("gradientStart", ui["primary"]), ui.get("gradientMid", ui["secondary"]), ui.get("gradientEnd", ui["accent"])]
    text = " ".join(args.text).upper()
    rows = [""] * 5
    for idx, ch in enumerate(text):
        glyph = _PIXEL_FONT.get(ch, _PIXEL_FONT["?"])
        for r in range(5):
            seg = glyph[r].replace("█", "#").replace("▄", "#") if args.font == "ascii" else glyph[r]
            rows[r] += (seg + ("  " if idx < len(text) - 1 else ""))

    print()
    for line in rows:
        if args.plain:
            print("  " + line)
        else:
            print("  " + gradient(line, stops, bold=True))
    print()
    return 0


# ── 6. Expense ────────────────────────────────────────────────────────────────

def cmd_expense(argv, theme):
    ap = argparse.ArgumentParser(prog="expense", description="Personal expense logger & category summary")
    sub = ap.add_subparsers(dest="action")

    p_add = sub.add_parser("add", help="Record an expense")
    p_add.add_argument("amount", type=float)
    p_add.add_argument("category")
    p_add.add_argument("note", nargs="*")

    p_sum = sub.add_parser("summary", help="Show category breakdown")
    p_sum.add_argument("--month", default="", help="Filter YYYY-MM")

    p_list = sub.add_parser("list", help="List recent expenses")
    p_list.add_argument("--limit", type=int, default=15)

    p_rm = sub.add_parser("rm", help="Delete expense by ID")
    p_rm.add_argument("id", type=int)

    p_exp = sub.add_parser("export", help="Export expenses to CSV file")
    p_exp.add_argument("path")

    args = ap.parse_args(argv)
    ui = theme["ui"]
    db_path = get_data_dir() / "expenses.json"
    entries = _load_json(db_path, [])
    action = args.action or "summary"

    if action == "add":
        if args.amount <= 0:
            print("  " + fmt("Amount must be positive.", ui["error"], True))
            return 1
        next_id = max([int(e.get("id", 0)) for e in entries], default=0) + 1
        rec = {
            "id": next_id,
            "date": dt.datetime.now().strftime("%Y-%m-%d"),
            "amount": round(float(args.amount), 2),
            "category": args.category.strip().lower(),
            "note": " ".join(args.note).strip(),
        }
        entries.append(rec)
        _save_json(db_path, entries)
        print(f"  {fmt('Recorded expense', ui['success'], True)} #{next_id}: {rec['amount']:.2f} [{rec['category']}] {rec['note']}")
        return 0

    if action == "rm":
        kept = [e for e in entries if e.get("id") != args.id]
        if len(kept) == len(entries):
            print("  " + fmt(f"Expense #{args.id} not found.", ui["error"], True))
            return 1
        _save_json(db_path, kept)
        print("  " + fmt(f"Removed expense #{args.id}.", ui["warning"]))
        return 0

    if action == "export":
        out = Path(args.path).expanduser().resolve()
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "date", "amount", "category", "note"])
            w.writeheader()
            w.writerows(entries)
        print(f"  {fmt('Exported', ui['success'], True)} {len(entries)} records -> {out}")
        return 0

    if action == "list":
        header("TricksXTech // Recent Expenses", theme)
        for e in entries[-args.limit:]:
            amt_str = f"{e['amount']:>9.2f}"
            print(f"  {fmt('#' + str(e['id']).rjust(2), ui['primary'], True)}  {fmt(e['date'], ui['muted'])}  {fmt(amt_str, ui['accent'], True)}  [{fmt(e['category'].ljust(10), ui['secondary'])}]  {fmt(e.get('note', ''), ui['text'])}")
        print()
        return 0

    month_filter = getattr(args, "month", "")
    filtered = [e for e in entries if not month_filter or e.get("date", "").startswith(month_filter)]
    header("TricksXTech // Expense Summary" + (f" ({month_filter})" if month_filter else ""), theme)
    if not filtered:
        print("  " + fmt("No expenses logged yet. Use: expense add 250 food \"Lunch\"", ui["muted"]))
        print()
        return 0
    by_cat = {}
    total = 0.0
    for e in filtered:
        amt = float(e.get("amount", 0))
        cat = e.get("category", "other")
        by_cat[cat] = by_cat.get(cat, 0.0) + amt
        total += amt
    for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
        pct = (amt / total * 100.0) if total else 0.0
        bar = "█" * max(1, int(pct / 5))
        print(f"  {fmt(cat.ljust(14), ui['secondary'], True)}  {fmt(f'{amt:10.2f}', ui['text'])}  {fmt(f'{pct:5.1f}%', ui['accent'])}  {fmt(bar, ui['primary'])}")
    print(fmt("  " + "─" * 52, ui["border"]))
    print(f"  {fmt('TOTAL'.ljust(14), ui['primary'], True)}  {fmt(f'{total:10.2f}', ui['success'], True)}  ({len(filtered)} item(s))\n")
    return 0


# ── 7. Weather ────────────────────────────────────────────────────────────────

def cmd_weather(argv, theme):
    ap = argparse.ArgumentParser(prog="weather", description="Fetch live weather & 3-day forecast via wttr.in")
    ap.add_argument("city", nargs="*", help="City name (omit for IP geolocation)")
    ap.add_argument("--fahrenheit", "-f", action="store_true", help="Show Fahrenheit primary")
    ap.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN connection")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    header("TricksXTech // Live Weather", theme)
    ensure_vpn_for_tool("weather", theme, skip_vpn=args.no_vpn)

    city_q = " ".join(args.city).strip()
    url = f"https://wttr.in/{urllib.parse.quote(city_q)}?format=j1"
    try:
        data = _fetch_json_url(url, timeout=12)
    except Exception as ex:
        print("  " + fmt(f"Weather fetch failed: {ex}", ui["error"], True))
        return 1

    cur = (data.get("current_condition") or [{}])[0]
    area = (data.get("nearest_area") or [{}])[0]
    area_name = ((area.get("areaName") or [{}])[0]).get("value", city_q or "Unknown")
    country = ((area.get("country") or [{}])[0]).get("value", "")
    desc = ((cur.get("weatherDesc") or [{}])[0]).get("value", "N/A")

    temp_str = f"{cur.get('temp_F', '?')}°F ({cur.get('temp_C', '?')}°C)" if args.fahrenheit else f"{cur.get('temp_C', '?')}°C ({cur.get('temp_F', '?')}°F)"
    feels = f"{cur.get('FeelsLikeF', '?')}°F" if args.fahrenheit else f"{cur.get('FeelsLikeC', '?')}°C"

    print(f"  {fmt('Location:', ui['secondary'], True)}  {fmt(f'{area_name}, {country}'.strip(', '), ui['primary'], True)}")
    print(f"  {fmt('Condition:', ui['secondary'], True)} {fmt(desc, ui['accent'], True)}")
    print(f"  {fmt('Temp:', ui['secondary'], True)}      {fmt(temp_str, ui['text'], True)}   Feels like {feels}")
    print(f"  {fmt('Humidity:', ui['secondary'], True)}  {cur.get('humidity', '?')}%   Wind: {cur.get('windspeedKmph', '?')} km/h ({cur.get('winddir16Point', '')})   UV: {cur.get('uvIndex', '?')}")

    days = data.get("weather") or []
    if days:
        print()
        print("  " + fmt("3-DAY FORECAST", ui["secondary"], True))
        for d in days[:3]:
            date_s = d.get("date", "")
            lo = f"{d.get('mintempF')}°F" if args.fahrenheit else f"{d.get('mintempC')}°C"
            hi = f"{d.get('maxtempF')}°F" if args.fahrenheit else f"{d.get('maxtempC')}°C"
            print(f"    {fmt(date_s, ui['accent'])}   Low {fmt(lo, ui['muted'])}  →  High {fmt(hi, ui['primary'], True)}   Sunrise {d.get('astronomy', [{}])[0].get('sunrise', '')}")
    print()
    return 0


# ── 8. Habit ──────────────────────────────────────────────────────────────────

def _calc_streak(dates: list) -> tuple:
    if not dates:
        return 0, 0
    day_set = sorted({dt.date.fromisoformat(d) for d in dates})
    today = dt.date.today()
    cur = 0
    probe = today if today in day_set else (today - dt.timedelta(days=1))
    day_lookup = set(day_set)
    while probe in day_lookup:
        cur += 1
        probe -= dt.timedelta(days=1)

    best = 0
    run = 0
    prev = None
    for d in day_set:
        if prev is not None and (d - prev).days == 1:
            run += 1
        else:
            run = 1
        best = max(best, run)
        prev = d
    return cur, best


def cmd_habit(argv, theme):
    ap = argparse.ArgumentParser(prog="habit", description="Daily habit & streak tracker")
    sub = ap.add_subparsers(dest="action")

    p_add = sub.add_parser("add", help="Create a tracked habit")
    p_add.add_argument("name", nargs="+")

    p_chk = sub.add_parser("check", help="Mark habit complete for today (or --date)")
    p_chk.add_argument("target")
    p_chk.add_argument("--date", default=dt.date.today().isoformat())

    p_rm = sub.add_parser("rm", help="Remove a habit")
    p_rm.add_argument("target")

    sub.add_parser("list", help="List habits & 7-day streaks")

    args = ap.parse_args(argv)
    ui = theme["ui"]
    db_path = get_data_dir() / "habits.json"
    habits = _load_json(db_path, [])
    action = args.action or "list"

    if action == "add":
        name = " ".join(args.name).strip()
        if any(h["name"].lower() == name.lower() for h in habits):
            print("  " + fmt(f"Habit '{name}' already exists.", ui["warning"]))
            return 1
        hid = max([int(h.get("id", 0)) for h in habits], default=0) + 1
        habits.append({"id": hid, "name": name, "dates": []})
        _save_json(db_path, habits)
        print(f"  {fmt('Added habit', ui['success'], True)} #{hid}: {name}")
        return 0

    if action == "check":
        try:
            dt.date.fromisoformat(args.date)
        except ValueError:
            print("  " + fmt("Invalid date format. Use YYYY-MM-DD.", ui["error"], True))
            return 1
        tgt = args.target.strip()
        for h in habits:
            if str(h.get("id")) == tgt or h.get("name", "").lower() == tgt.lower():
                if args.date not in h["dates"]:
                    h["dates"].append(args.date)
                    _save_json(db_path, habits)
                cur, best = _calc_streak(h["dates"])
                print(f"  {fmt('Checked', ui['success'], True)} '{h['name']}' for {args.date}  |  Streak: {cur}d (Best: {best}d)")
                return 0
        print("  " + fmt(f"Habit '{tgt}' not found.", ui["error"], True))
        return 1

    if action == "rm":
        tgt = args.target.strip()
        kept = [h for h in habits if str(h.get("id")) != tgt and h.get("name", "").lower() != tgt.lower()]
        if len(kept) == len(habits):
            print("  " + fmt(f"Habit '{tgt}' not found.", ui["error"], True))
            return 1
        _save_json(db_path, kept)
        print("  " + fmt(f"Removed habit '{tgt}'.", ui["warning"]))
        return 0

    header("TricksXTech // Habit Tracker (7-Day View)", theme)
    if not habits:
        print("  " + fmt("No habits tracked yet. Use: habit add \"Workout\"", ui["muted"]))
        print()
        return 0
    today = dt.date.today()
    last7 = [(today - dt.timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    for h in habits:
        cur, best = _calc_streak(h.get("dates", []))
        dset = set(h.get("dates", []))
        grid = " ".join(fmt("■", ui["success"], True) if d in dset else fmt("□", ui["muted"]) for d in last7)
        print(f"  {fmt('#' + str(h['id']).rjust(2), ui['primary'], True)}  {fmt(h['name'].ljust(20), ui['text'], True)}  {grid}   Streak: {fmt(str(cur) + 'd', ui['accent'], True)} (Best {best}d)")
    print()
    return 0


# ── 9. Unit Converter ─────────────────────────────────────────────────────────

_UNIT_TABLES = {
    "length": ({"m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001, "mi": 1609.344, "yd": 0.9144, "ft": 0.3048, "in": 0.0254, "nm": 1852.0}),
    "mass": ({"kg": 1.0, "g": 0.001, "mg": 1e-6, "lb": 0.45359237, "lbs": 0.45359237, "oz": 0.028349523125, "t": 1000.0, "ton": 1000.0}),
    "data": ({"b": 1.0, "kb": 1000.0, "mb": 1e6, "gb": 1e9, "tb": 1e12, "kib": 1024.0, "mib": 1024.0 ** 2, "gib": 1024.0 ** 3, "tib": 1024.0 ** 4}),
    "speed": ({"mps": 1.0, "m/s": 1.0, "kmh": 1 / 3.6, "km/h": 1 / 3.6, "kph": 1 / 3.6, "mph": 0.44704, "kn": 0.514444444, "kt": 0.514444444}),
    "time": ({"s": 1.0, "sec": 1.0, "ms": 0.001, "min": 60.0, "m": 60.0, "h": 3600.0, "hr": 3600.0, "d": 86400.0, "day": 86400.0, "wk": 604800.0}),
    "area": ({"sqm": 1.0, "m2": 1.0, "sqkm": 1e6, "km2": 1e6, "sqft": 0.09290304, "ft2": 0.09290304, "acre": 4046.8564224, "ha": 10000.0}),
    "volume": ({"l": 1.0, "ml": 0.001, "gal": 3.785411784, "qt": 0.946352946, "cup": 0.2365882365}),
}


def _convert_temp(val: float, u1: str, u2: str) -> float:
    aliases = {"c": "c", "celsius": "c", "f": "f", "fahrenheit": "f", "k": "k", "kelvin": "k"}
    a, b = aliases.get(u1), aliases.get(u2)
    if not a or not b:
        raise KeyError("not temp")
    c_val = val if a == "c" else ((val - 32.0) * 5.0 / 9.0 if a == "f" else val - 273.15)
    if b == "c":
        return c_val
    if b == "f":
        return c_val * 9.0 / 5.0 + 32.0
    return c_val + 273.15


def cmd_unitconv(argv, theme):
    ap = argparse.ArgumentParser(prog="unitconv", description="Convert length, mass, temp, data, speed, time, area, volume")
    ap.add_argument("value", type=float)
    ap.add_argument("args", nargs="+", help="<from_unit> [to] <to_unit>")
    ns = ap.parse_args(argv)

    ui = theme["ui"]
    parts = [p.lower() for p in ns.args if p.lower() != "to"]
    if len(parts) != 2:
        print("  " + fmt("Usage: unitconv <value> <from_unit> [to] <to_unit>", ui["error"], True))
        return 1
    u1, u2 = parts

    header("TricksXTech // Unit Converter", theme)
    try:
        res = _convert_temp(ns.value, u1, u2)
        cat = "temperature"
    except KeyError:
        cat = None
        res = None
        for cname, tbl in _UNIT_TABLES.items():
            if u1 in tbl and u2 in tbl:
                cat = cname
                res = ns.value * tbl[u1] / tbl[u2]
                break
        if cat is None:
            print("  " + fmt(f"Unsupported or incompatible units: '{u1}' -> '{u2}'.", ui["error"], True))
            print("  " + fmt("Supported categories: length(m,km,mi,ft,in), mass(kg,g,lb,oz), temp(c,f,k), data(b,kb,mb,gb,kib,mib,gib), speed(mps,kmh,mph,kn), time(s,min,h,d), area(sqm,sqft,acre,ha), volume(l,ml,gal)", ui["muted"]))
            return 1

    print(f"  {fmt('Category:', ui['muted'])} {fmt(cat.upper(), ui['accent'])}")
    print(f"  {fmt(f'{ns.value:g} {u1}', ui['secondary'], True)}  =  {fmt(f'{res:.6g} {u2}', ui['primary'], True)}")
    print()
    return 0


# ── 10. Timezone Converter ────────────────────────────────────────────────────

_TZ_ALIASES = {
    "UTC": "UTC",
    "GMT": "GMT",
    "IST": "Asia/Kolkata",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "MST": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "BST": "Europe/London",
    "CET": "Europe/Berlin",
    "JST": "Asia/Tokyo",
    "SGT": "Asia/Singapore",
    "AEST": "Australia/Sydney",
}


def _resolve_tz(name: str) -> ZoneInfo:
    key = _TZ_ALIASES.get(name.strip().upper(), name.strip())
    return ZoneInfo(key)


def cmd_tzconv(argv, theme):
    ap = argparse.ArgumentParser(prog="tzconv", description="World clock & timezone converter")
    ap.add_argument("time", nargs="?", default="", help="Time like 14:30 or 2026-11-12T14:30 (default: now)")
    ap.add_argument("--from", dest="src_tz", default="", help="Source TZ (default: local)")
    ap.add_argument("--to", dest="dst_tzs", default="UTC,America/New_York,Europe/London,Asia/Kolkata,Asia/Tokyo", help="Comma-separated target timezones")
    ap.add_argument("--list", action="store_true", help="List matching IANA timezone names")
    ap.add_argument("--filter", default="", help="Filter substring for --list")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    header("TricksXTech // Timezone Converter", theme)

    if args.list:
        f = args.filter.lower()
        zones = sorted(z for z in available_timezones() if not f or f in z.lower())
        for z in zones[:60]:
            print("  " + fmt(z, ui["text"]))
        if len(zones) > 60:
            print("  " + fmt(f"... ({len(zones) - 60} more; pass --filter to narrow)", ui["muted"]))
        print()
        return 0

    try:
        if args.time:
            raw = args.time.strip()
            if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", raw):
                fmt_str = "%H:%M:%S" if len(raw.split(":")) == 3 else "%H:%M"
                t_only = dt.datetime.strptime(raw, fmt_str).time()
                base_dt = dt.datetime.combine(dt.date.today(), t_only)
            else:
                base_dt = dt.datetime.fromisoformat(raw)
        else:
            base_dt = dt.datetime.now()

        if args.src_tz:
            src = _resolve_tz(args.src_tz)
            base_dt = base_dt.replace(tzinfo=src) if base_dt.tzinfo is None else base_dt.astimezone(src)
        elif base_dt.tzinfo is None:
            base_dt = base_dt.astimezone()
    except Exception as ex:
        print("  " + fmt(f"Invalid time or source timezone: {ex}", ui["error"], True))
        return 1

    print(f"  {fmt('Source:', ui['secondary'], True)}  {fmt(base_dt.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)'), ui['primary'], True)}")
    print(fmt("  " + "─" * 64, ui["border"]))
    for tgt in [t.strip() for t in args.dst_tzs.split(",") if t.strip()]:
        try:
            conv = base_dt.astimezone(_resolve_tz(tgt))
            print(f"  {fmt(tgt.ljust(22), ui['accent'])}  {fmt(conv.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)'), ui['text'])}")
        except Exception as ex:
            print(f"  {fmt(tgt.ljust(22), ui['error'])}  Invalid TZ ({ex})")
    print()
    return 0


# ── 11. Git Clean (Merged Branches) ───────────────────────────────────────────

def cmd_gitclean(argv, theme):
    ap = argparse.ArgumentParser(prog="gitclean", description="Safely list/prune merged local Git branches (--dry-run default)")
    ap.add_argument("--path", default=".", help="Git repo path")
    ap.add_argument("--apply", action="store_true", help="Actually delete merged branches (otherwise preview only)")
    ap.add_argument("--include-unmerged", action="store_true", help="Also delete unmerged branches when --apply is set (dangerous)")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    header("TricksXTech // Git Branch Cleaner", theme)
    cwd = os.path.abspath(args.path)

    def _git(cmd_args):
        return subprocess.run(["git"] + cmd_args, cwd=cwd, capture_output=True, text=True)

    if _git(["rev-parse", "--is-inside-work-tree"]).returncode != 0:
        print("  " + fmt("Not inside a Git repository.", ui["error"], True))
        return 1

    cur = _git(["branch", "--show-current"]).stdout.strip()
    protected = {"main", "master", "dev", "develop", "staging", "release", cur}
    flag = "--list" if args.include_unmerged else "--merged"
    res = _git(["branch", flag])
    candidates = []
    for line in res.stdout.splitlines():
        name = line.lstrip("* ").strip()
        if name and name not in protected:
            candidates.append(name)

    print(f"  {fmt('Current branch:', ui['muted'])} {fmt(cur or '(detached)', ui['accent'], True)}")
    print(f"  {fmt('Protected:', ui['muted'])}      main, master, dev, develop, staging, release")
    print()
    if not candidates:
        print("  " + fmt("✓ No stale/merged local branches to clean.", ui["success"], True))
        print()
        return 0

    for b in candidates:
        tag = fmt("DELETE" if args.apply else "DRY-RUN", ui["warning"] if not args.apply else ui["error"], True)
        print(f"  [{tag}]  {fmt(b, ui['text'])}")

    if not args.apply:
        print()
        print("  " + fmt("Dry-run only — nothing deleted. Re-run with --apply to remove these branches.", ui["muted"]))
        print()
        return 0

    del_flag = "-D" if args.include_unmerged else "-d"
    deleted = 0
    for b in candidates:
        r = _git(["branch", del_flag, b])
        if r.returncode == 0:
            deleted += 1
        else:
            print("  " + fmt(f"Skipped '{b}': {r.stderr.strip()}", ui["error"]))
    print()
    print("  " + fmt(f"Deleted {deleted}/{len(candidates)} branch(es).", ui["success"], True))
    print()
    return 0


# ── 12. Git Stats ─────────────────────────────────────────────────────────────

def cmd_gitstats(argv, theme):
    ap = argparse.ArgumentParser(prog="gitstats", description="Repository commit, contributor & activity analytics")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args(argv)

    ui = theme["ui"]
    cwd = os.path.abspath(args.path)

    def _git(cmd_args):
        return subprocess.run(["git"] + cmd_args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    if _git(["rev-parse", "--is-inside-work-tree"]).returncode != 0:
        print("  " + fmt(f"Not a Git repository: {cwd}", ui["error"], True))
        return 1

    header(f"TricksXTech // Git Analytics ({os.path.basename(cwd)})", theme)
    branch = _git(["branch", "--show-current"]).stdout.strip() or "(detached)"
    total_commits = _git(["rev-list", "--count", "HEAD"]).stdout.strip() or "0"
    tracked_files = len(_git(["ls-files"]).stdout.splitlines())
    first_dt = _git(["log", "--reverse", "--format=%cs", "-n", "1"]).stdout.strip() or "-"
    last_dt = _git(["log", "--format=%cs (%ar)", "-n", "1"]).stdout.strip() or "-"
    tags = len(_git(["tag"]).stdout.splitlines())

    print(f"  {fmt('Branch:', ui['secondary'], True)}        {fmt(branch, ui['primary'], True)}     {fmt('Tags:', ui['secondary'], True)} {tags}")
    print(f"  {fmt('Total Commits:', ui['secondary'], True)} {fmt(total_commits, ui['accent'], True)}     {fmt('Tracked Files:', ui['secondary'], True)} {tracked_files}")
    print(f"  {fmt('First Commit:', ui['secondary'], True)}  {first_dt}     {fmt('Latest:', ui['secondary'], True)} {last_dt}")

    authors_out = _git(["shortlog", "-sn", "HEAD"]).stdout.splitlines()
    if authors_out:
        print()
        print("  " + fmt("TOP CONTRIBUTORS", ui["secondary"], True))
        max_c = max(int(line.strip().split()[0]) for line in authors_out[:args.top]) or 1
        for line in authors_out[:args.top]:
            parts = line.strip().split(None, 1)
            cnt = int(parts[0])
            name = parts[1] if len(parts) > 1 else "?"
            bar = "█" * max(1, int(cnt / max_c * 24))
            print(f"    {fmt(name[:24].ljust(24), ui['text'])}  {fmt(str(cnt).rjust(6), ui['accent'], True)}  {fmt(bar, ui['primary'])}")

    dates = _git(["log", "--format=%ad", "--date=format:%a", "HEAD"]).stdout.splitlines()
    if dates:
        counts = {d: 0 for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
        for d in dates:
            if d in counts:
                counts[d] += 1
        peak = max(counts.values()) or 1
        print()
        print("  " + fmt("COMMITS BY WEEKDAY", ui["secondary"], True))
        for day, cnt in counts.items():
            bar = "█" * int(cnt / peak * 20)
            print(f"    {fmt(day, ui['accent'])}  {fmt(str(cnt).rjust(5), ui['muted'])}  {fmt(bar, ui['secondary'])}")
    print()
    return 0


# ── 13. Bookmarks ─────────────────────────────────────────────────────────────

def cmd_bookmarks(argv, theme):
    ap = argparse.ArgumentParser(prog="bookmarks", description="CLI URL bookmark manager")
    sub = ap.add_subparsers(dest="action")

    p_add = sub.add_parser("add")
    p_add.add_argument("url")
    p_add.add_argument("--title", default="")
    p_add.add_argument("--tag", default="web")

    p_open = sub.add_parser("open")
    p_open.add_argument("id", type=int)

    p_search = sub.add_parser("search")
    p_search.add_argument("query")

    p_rm = sub.add_parser("rm")
    p_rm.add_argument("id", type=int)

    p_list = sub.add_parser("list")
    p_list.add_argument("--tag", default="")

    args = ap.parse_args(argv)
    ui = theme["ui"]
    db_path = get_data_dir() / "bookmarks.json"
    bms = _load_json(db_path, [])
    action = args.action or "list"

    if action == "add":
        url = args.url.strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            print("  " + fmt("URL must start with http:// or https://", ui["error"], True))
            return 1
        bid = max([int(b.get("id", 0)) for b in bms], default=0) + 1
        title = args.title.strip() or parsed.netloc
        bms.append({"id": bid, "url": url, "title": title, "tag": args.tag.strip()})
        _save_json(db_path, bms)
        print(f"  {fmt('Bookmarked', ui['success'], True)} #{bid} [{args.tag}]: {title} -> {url}")
        return 0

    if action == "open":
        for b in bms:
            if b.get("id") == args.id:
                url = b.get("url", "")
                if urllib.parse.urlparse(url).scheme not in ("http", "https"):
                    print("  " + fmt("Refusing non-HTTP bookmark URL.", ui["error"], True))
                    return 1
                webbrowser.open(url)
                print(f"  {fmt('Opened', ui['success'], True)} {url}")
                return 0
        print("  " + fmt(f"Bookmark #{args.id} not found.", ui["error"], True))
        return 1

    if action == "rm":
        kept = [b for b in bms if b.get("id") != args.id]
        if len(kept) == len(bms):
            print("  " + fmt(f"Bookmark #{args.id} not found.", ui["error"], True))
            return 1
        _save_json(db_path, kept)
        print("  " + fmt(f"Removed bookmark #{args.id}.", ui["warning"]))
        return 0

    tag_f = getattr(args, "tag", "").lower()
    q_f = getattr(args, "query", "").lower()
    shown = [
        b for b in bms
        if (not tag_f or b.get("tag", "").lower() == tag_f)
        and (not q_f or q_f in b.get("title", "").lower() or q_f in b.get("url", "").lower() or q_f in b.get("tag", "").lower())
    ]
    header("TricksXTech // Bookmarks", theme)
    if not shown:
        print("  " + fmt("No bookmarks found. Use: bookmarks add https://example.com --tag dev", ui["muted"]))
        print()
        return 0
    for b in shown:
        print(f"  {fmt('#' + str(b['id']).rjust(2), ui['primary'], True)}  [{fmt(b.get('tag', 'web').ljust(8), ui['accent'])}]  {fmt(b['title'].ljust(24), ui['text'], True)}  {fmt(b['url'], ui['muted'])}")
    print()
    return 0


# ── 14. Pick (Random Selector) ────────────────────────────────────────────────

def cmd_pick(argv, theme):
    ap = argparse.ArgumentParser(prog="pick", description="Cryptographically fair random selector, dice roller & coin flip")
    ap.add_argument("items", nargs="*", help="Items to choose from")
    ap.add_argument("-n", "--count", type=int, default=1, help="Number of items to pick")
    ap.add_argument("--range", dest="num_range", default="", help="Pick from integer range A..B (e.g. 1..100)")
    ap.add_argument("--file", default="", help="Pick random line(s) from file")
    ap.add_argument("--coin", action="store_true", help="Flip a coin")
    ap.add_argument("--dice", nargs="?", const=6, type=int, help="Roll an N-sided die (default 6)")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    rng = secrets.SystemRandom()

    if args.coin:
        print(f"  {fmt('Coin Flip:', ui['secondary'], True)} {fmt(rng.choice(['HEADS', 'TAILS']), ui['primary'], True)}")
        return 0
    if args.dice is not None:
        sides = max(2, args.dice)
        print(f"  {fmt(f'd{sides} Roll:', ui['secondary'], True)} {fmt(str(rng.randint(1, sides)), ui['primary'], True)}")
        return 0

    pool = list(args.items)
    if args.num_range:
        m = re.fullmatch(r"(-?\d+)\.\.(-?\d+)", args.num_range.strip())
        if not m:
            print("  " + fmt("Invalid --range. Use A..B, e.g. 1..100", ui["error"], True))
            return 1
        a, b = int(m.group(1)), int(m.group(2))
        lo, hi = min(a, b), max(a, b)
        count = max(1, min(args.count, hi - lo + 1))
        picks = [str(x) for x in rng.sample(range(lo, hi + 1), count)]
        print(f"  {fmt('Picked:', ui['secondary'], True)} {fmt(', '.join(picks), ui['primary'], True)}")
        return 0

    if args.file:
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            pool = [line.strip() for line in f if line.strip()]
    elif not pool and not sys.stdin.isatty():
        pool = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

    if not pool:
        print("  " + fmt("Provide items, --range A..B, --file PATH, --coin, or --dice.", ui["error"], True))
        return 1

    k = max(1, min(args.count, len(pool)))
    chosen = rng.sample(pool, k)
    for item in chosen:
        print(f"  {fmt('→', ui['accent'], True)} {fmt(item, ui['primary'], True)}")
    return 0


# ── 15. Pomodoro ──────────────────────────────────────────────────────────────

def cmd_pomodoro(argv, theme):
    ap = argparse.ArgumentParser(prog="pomodoro", description="Focus work/break interval Pomodoro timer")
    ap.add_argument("--work", default="25m", help="Work interval duration (default 25m)")
    ap.add_argument("--break", dest="brk", default="5m", help="Break interval duration (default 5m)")
    ap.add_argument("--cycles", type=int, default=1, help="Number of work+break cycles")
    ap.add_argument("--no-beep", action="store_true", help="Disable terminal bell")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    try:
        work_s = parse_duration(args.work)
        brk_s = parse_duration(args.brk)
    except ValueError as ex:
        print("  " + fmt(str(ex), ui["error"], True))
        return 1

    cycles = max(1, args.cycles)
    header(f"TricksXTech // Pomodoro ({cycles} cycle(s))", theme)
    for c in range(1, cycles + 1):
        print(f"  {fmt(f'Cycle {c}/{cycles} — FOCUS', ui['primary'], True)}")
        if not _run_timer_bar(work_s, "Work ", theme, no_beep=args.no_beep):
            return 1
        print(f"  {fmt(f'Cycle {c}/{cycles} — BREAK', ui['accent'], True)}")
        if not _run_timer_bar(brk_s, "Break", theme, no_beep=args.no_beep):
            return 1
    print("  " + fmt("✓ Pomodoro session complete!", ui["success"], True))
    print()
    return 0


# ── 16. Safe AST Calculator ───────────────────────────────────────────────────

_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.BitXor: operator.xor,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}
_SAFE_UNOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Invert: operator.invert}
_SAFE_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10, "log2": math.log2,
    "exp": math.exp, "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil,
    "pow": pow, "min": min, "max": max, "factorial": lambda n: math.factorial(int(n)) if 0 <= int(n) <= 500 else (_ for _ in ()).throw(ValueError("factorial range 0..500")),
    "deg": math.degrees, "rad": math.radians,
}
_SAFE_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _eval_ast(node):
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in _SAFE_CONSTS:
            return _SAFE_CONSTS[node.id]
        raise ValueError(f"Unknown symbol '{node.id}'")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNOPS:
        return _SAFE_UNOPS[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.BinOp):
        left, right = _eval_ast(node.left), _eval_ast(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > 1000:
                raise ValueError("Exponent magnitude limited to 1000.")
            return left ** right
        if type(node.op) in _SAFE_BINOPS:
            return _SAFE_BINOPS[type(node.op)](left, right)
        raise ValueError(f"Unsupported operator {type(node.op).__name__}")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        fn = _SAFE_FUNCS.get(node.func.id)
        if not fn:
            raise ValueError(f"Function '{node.func.id}' not allowed.")
        return fn(*[_eval_ast(a) for a in node.args])
    raise ValueError("Unsupported syntax in expression.")


def cmd_calc(argv, theme):
    ap = argparse.ArgumentParser(prog="calc", description="Safe AST scientific terminal calculator")
    ap.add_argument("expression", nargs="+", help="Math expression, e.g. 'sqrt(144) + 2**8'")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    expr = " ".join(args.expression).strip()
    try:
        tree = ast.parse(expr, mode="eval")
        res = _eval_ast(tree)
    except Exception as ex:
        print("  " + fmt(f"Error: {ex}", ui["error"], True))
        return 1

    print(f"  {fmt(expr, ui['muted'])}  =  {fmt(repr(res), ui['primary'], True)}")
    if isinstance(res, int) and abs(res) < 10 ** 12:
        print(f"  {fmt('Hex:', ui['muted'])} {hex(res)}   {fmt('Bin:', ui['muted'])} {bin(res)}")
    return 0


# ── 17. Currency Exchange (FX) ────────────────────────────────────────────────

def cmd_fx(argv, theme):
    ap = argparse.ArgumentParser(prog="fx", description="Live currency exchange rate converter")
    ap.add_argument("amount", type=float)
    ap.add_argument("currencies", nargs="+", help="<FROM> [to] <TO>")
    ap.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN connection")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    currs = [c.upper() for c in args.currencies if c.lower() != "to"]
    if len(currs) != 2:
        print("  " + fmt("Usage: fx <amount> <FROM> [to] <TO>  (e.g. fx 100 USD INR)", ui["error"], True))
        return 1
    src, dst = currs

    header("TricksXTech // Live Currency Converter (FX)", theme)
    ensure_vpn_for_tool("fx", theme, skip_vpn=args.no_vpn)

    try:
        data = _fetch_json_url(f"https://open.er-api.com/v6/latest/{urllib.parse.quote(src)}", timeout=12)
        if data.get("result") != "success":
            raise RuntimeError(data.get("error-type", "API error"))
        rate = data["rates"].get(dst)
        if rate is None:
            print("  " + fmt(f"Unknown target currency code '{dst}'.", ui["error"], True))
            return 1
        converted = args.amount * float(rate)
        print(f"  {fmt(f'{args.amount:,.2f} {src}', ui['secondary'], True)}  =  {fmt(f'{converted:,.4f} {dst}', ui['primary'], True)}")
        print(f"  {fmt('Rate:', ui['muted'])} 1 {src} = {rate} {dst}   ({data.get('time_last_update_utc', '')})")
        print()
        return 0
    except Exception as ex:
        print("  " + fmt(f"FX lookup failed: {ex}", ui["error"], True))
        return 1


# ── 18. Progress Bar Utility ──────────────────────────────────────────────────

def cmd_pbar(argv, theme):
    ap = argparse.ArgumentParser(prog="pbar", description="Themed CLI progress bar for pipelines or demos")
    ap.add_argument("--total", type=int, default=0, help="Expected total lines/steps")
    ap.add_argument("--label", default="Progress", help="Prefix label")
    ap.add_argument("--demo", action="store_true", help="Run a smooth animated progress demo")
    ap.add_argument("--steps", type=int, default=25, help="Demo step count")
    ap.add_argument("--delay", type=float, default=0.04, help="Demo delay seconds per step")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    stops = [ui.get("gradientStart", ui["primary"]), ui.get("gradientMid", ui["secondary"]), ui.get("gradientEnd", ui["accent"])]
    width = 32
    t0 = time.monotonic()

    def _draw(done: int, total: int):
        elapsed = max(0.001, time.monotonic() - t0)
        rate = done / elapsed
        if total > 0:
            pct = min(1.0, done / total)
            filled = int(round(pct * width))
            bar = gradient("█" * filled, stops, False) + fmt("░" * (width - filled), ui["border"])
            eta = (total - done) / rate if rate > 0 and done < total else 0.0
            print(f"\r  {fmt(args.label, ui['secondary'], True)}  [{bar}]  {fmt(f'{pct*100:5.1f}%', ui['accent'])}  ({done}/{total})  ETA {format_hms(eta)}  ", end="", flush=True)
        else:
            spin = "|/-\\"[done % 4]
            print(f"\r  {fmt(args.label, ui['secondary'], True)}  [{fmt(spin, ui['primary'], True)}]  {done} items  ({rate:.1f}/s)  ", end="", flush=True)

    if args.demo or sys.stdin.isatty():
        steps = max(1, args.steps)
        for i in range(1, steps + 1):
            _draw(i, steps)
            time.sleep(max(0.0, args.delay))
        print()
        print("  " + fmt("✓ Complete.", ui["success"], True))
        return 0

    count = 0
    for _ in sys.stdin:
        count += 1
        _draw(count, args.total)
    print()
    return 0


# ── 19. Custom Aliases Manager ────────────────────────────────────────────────

_RESERVED_ALIASES = {
    "cd", "exit", "cls", "clear", "dir", "ls", "cat", "sort", "compare", "sc",
    "type", "start", "sleep", "diff", "ps", "kill", "pwd", "echo", "copy", "mv",
    "rm", "cp", "ping", "ftp", "tar", "tree", "tx", "vpn", "tools", "aliases",
}


def _sync_aliases_files(aliases: dict) -> tuple:
    json_path = get_data_dir() / "custom_aliases.json"
    doskey_path = get_data_dir() / "custom_aliases.doskey"
    _save_json(json_path, aliases)
    lines = [f"{name}={target} $*" for name, target in sorted(aliases.items())]
    with open(doskey_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\r\n".join(lines) + ("\r\n" if lines else ""))
    return json_path, doskey_path


def cmd_aliases(argv, theme):
    ap = argparse.ArgumentParser(prog="aliases", description="Create & sync custom PS + CMD shell shortcuts")
    sub = ap.add_subparsers(dest="action")

    p_add = sub.add_parser("add", help="Add or update a shell alias")
    p_add.add_argument("name")
    p_add.add_argument("target", nargs="+")

    p_rm = sub.add_parser("rm", help="Remove a shell alias")
    p_rm.add_argument("name")

    sub.add_parser("sync", help="Regenerate custom_aliases.doskey from JSON")
    sub.add_parser("list", help="List custom aliases")

    args = ap.parse_args(argv)
    ui = theme["ui"]
    json_path = get_data_dir() / "custom_aliases.json"
    aliases = _load_json(json_path, {})
    action = args.action or "list"

    if action == "add":
        name = args.name.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", name):
            print("  " + fmt("Alias name must be 1-32 chars [A-Za-z0-9_-], starting with a letter.", ui["error"], True))
            return 1
        if name.lower() in _RESERVED_ALIASES:
            print("  " + fmt(f"Refusing to shadow reserved/built-in command '{name}'.", ui["error"], True))
            return 1
        target = " ".join(args.target).strip()
        if not target or any(ch in target for ch in ("\r", "\n", ";", "`", "$(")):
            print("  " + fmt("Invalid target command (multiline or shell injection chars blocked).", ui["error"], True))
            return 1
        aliases[name] = target
        _sync_aliases_files(aliases)
        print(f"  {fmt('Saved alias:', ui['success'], True)} {fmt(name, ui['primary'], True)} -> {fmt(target, ui['text'])}")
        print("  " + fmt("Run 'reload' in PowerShell (or open a new CMD session) to activate.", ui["muted"]))
        return 0

    if action == "rm":
        if args.name not in aliases:
            print("  " + fmt(f"Alias '{args.name}' not found.", ui["error"], True))
            return 1
        del aliases[args.name]
        _sync_aliases_files(aliases)
        print("  " + fmt(f"Removed alias '{args.name}'. Run 'reload' in PS to refresh.", ui["warning"]))
        return 0

    if action == "sync":
        jp, dp = _sync_aliases_files(aliases)
        print(f"  {fmt('Synced', ui['success'], True)} {len(aliases)} alias(es) -> {dp}")
        return 0

    header("TricksXTech // Custom Shell Aliases", theme)
    if not aliases:
        print("  " + fmt("No custom aliases yet. Example: aliases add gl \"git log --oneline -n 10\"", ui["muted"]))
        print()
        return 0
    for k, v in sorted(aliases.items()):
        print(f"  {fmt(k.ljust(16), ui['primary'], True)} ->  {fmt(v, ui['text'])}")
    print()
    return 0


# ── 20. Contacts (SQLite Address Book) ────────────────────────────────────────

def _contacts_conn() -> sqlite3.Connection:
    db = get_data_dir() / "contacts.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            org TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created TEXT NOT NULL
        )"""
    )
    conn.commit()
    return conn


def cmd_contacts(argv, theme):
    ap = argparse.ArgumentParser(prog="contacts", description="Local SQLite address book")
    sub = ap.add_subparsers(dest="action")

    p_add = sub.add_parser("add", help="Add a contact")
    p_add.add_argument("name")
    p_add.add_argument("--phone", default="")
    p_add.add_argument("--email", default="")
    p_add.add_argument("--org", default="")
    p_add.add_argument("--note", default="")

    p_s = sub.add_parser("search", help="Search contacts")
    p_s.add_argument("query")

    p_rm = sub.add_parser("rm", help="Delete contact by ID")
    p_rm.add_argument("id", type=int)

    p_exp = sub.add_parser("export", help="Export contacts to CSV")
    p_exp.add_argument("path")

    sub.add_parser("list", help="List contacts")

    args = ap.parse_args(argv)
    ui = theme["ui"]
    action = args.action or "list"
    conn = _contacts_conn()
    try:
        if action == "add":
            cur = conn.execute(
                "INSERT INTO contacts(name, phone, email, org, note, created) VALUES (?, ?, ?, ?, ?, ?)",
                (args.name.strip(), args.phone.strip(), args.email.strip(), args.org.strip(), args.note.strip(), dt.datetime.now().strftime("%Y-%m-%d %H:%M")),
            )
            conn.commit()
            print(f"  {fmt('Added contact', ui['success'], True)} #{cur.lastrowid}: {args.name}")
            return 0

        if action == "rm":
            cur = conn.execute("DELETE FROM contacts WHERE id = ?", (args.id,))
            conn.commit()
            if cur.rowcount == 0:
                print("  " + fmt(f"Contact #{args.id} not found.", ui["error"], True))
                return 1
            print("  " + fmt(f"Removed contact #{args.id}.", ui["warning"]))
            return 0

        if action == "export":
            rows = conn.execute("SELECT id, name, phone, email, org, note, created FROM contacts ORDER BY id").fetchall()
            out = Path(args.path).expanduser().resolve()
            with open(out, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "name", "phone", "email", "org", "note", "created"])
                w.writerows(rows)
            print(f"  {fmt('Exported', ui['success'], True)} {len(rows)} contact(s) -> {out}")
            return 0

        if action == "search":
            q = f"%{args.query.strip()}%"
            rows = conn.execute(
                "SELECT id, name, phone, email, org, note FROM contacts WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? OR org LIKE ? OR note LIKE ? ORDER BY name",
                (q, q, q, q, q),
            ).fetchall()
        else:
            rows = conn.execute("SELECT id, name, phone, email, org, note FROM contacts ORDER BY name").fetchall()

        header("TricksXTech // Contacts Book", theme)
        if not rows:
            print("  " + fmt("No contacts found. Use: contacts add \"Name\" --phone 123 --email a@b.com", ui["muted"]))
            print()
            return 0
        for cid, name, phone, email, org, note in rows:
            print(f"  {fmt('#' + str(cid).rjust(2), ui['primary'], True)}  {fmt(name.ljust(20), ui['text'], True)}  {fmt(phone.ljust(15), ui['accent'])}  {fmt(email.ljust(24), ui['secondary'])}  {fmt(org, ui['muted'])}")
        print()
        return 0
    finally:
        conn.close()


# ── Dispatcher ────────────────────────────────────────────────────────────────

COMMANDS = {
    "stopwatch": cmd_stopwatch,
    "countdown": cmd_countdown,
    "todo": cmd_todo,
    "notes": cmd_notes,
    "banner": cmd_banner,
    "expense": cmd_expense,
    "weather": cmd_weather,
    "habit": cmd_habit,
    "unitconv": cmd_unitconv,
    "tzconv": cmd_tzconv,
    "gitclean": cmd_gitclean,
    "gitstats": cmd_gitstats,
    "bookmarks": cmd_bookmarks,
    "pick": cmd_pick,
    "pomodoro": cmd_pomodoro,
    "calc": cmd_calc,
    "fx": cmd_fx,
    "pbar": cmd_pbar,
    "aliases": cmd_aliases,
    "contacts": cmd_contacts,
}


def main():
    enable_vt()
    theme = load_theme()
    argv = sys.argv[1:]
    if not argv:
        print("  Available prod_extra commands: " + ", ".join(sorted(COMMANDS)))
        return 1
    cmd = argv[0].lstrip("-").lower()
    fn = COMMANDS.get(cmd)
    if not fn:
        print(f"  Unknown command '{argv[0]}'. Available: {', '.join(sorted(COMMANDS))}")
        return 1
    return fn(argv[1:], theme) or 0


if __name__ == "__main__":
    sys.exit(main())
