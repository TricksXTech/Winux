#!/usr/bin/env python3
"""TricksXTech Additional Developer & Data Processing Tools."""

from __future__ import annotations

import argparse
from collections import Counter
import colorsys
import csv
import datetime
import html as html_mod
import io
import json
import os
import re
import sys
import unicodedata
import xml.dom.minidom

try:
    import defusedxml.ElementTree as SafeET
except ImportError:
    import xml.etree.ElementTree as SafeET

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, header, load_theme


def _read_stdin_text() -> str:
    if sys.stdin is not None and not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _flatten_dict(obj: dict, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    for k, v in obj.items():
        nk = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten_dict(v, nk))
        elif isinstance(v, list):
            out[nk] = json.dumps(v, ensure_ascii=False)
        else:
            out[nk] = v
    return out


def cmd_jsonmin(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="jsonmin", description="Validate & minify JSON file or piped stdin")
    p.add_argument("file", nargs="?", default="", help="JSON file (omit for stdin)")
    p.add_argument("-o", "--out", help="Write minified output to file")
    args = p.parse_args(argv)

    raw = open(args.file, "r", encoding="utf-8-sig").read() if args.file else _read_stdin_text()
    data = json.loads(raw)
    mini = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(mini)
        print(f"  {fmt('Minified JSON written:', ui['success'], True)} {args.out} ({len(mini):,} bytes)")
    else:
        print(mini)


def cmd_csv2json(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="csv2json", description="Convert CSV file to structured JSON array")
    p.add_argument("file", help="Input .csv file")
    p.add_argument("-o", "--out", help="Optional output .json file")
    args = p.parse_args(argv)

    with open(args.file, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out_txt = json.dumps(rows, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as out:
            out.write(out_txt + "\n")
        print(f"  {fmt('Converted', ui['success'], True)} {len(rows)} rows -> {args.out}")
    else:
        print(out_txt)


def cmd_json2csv(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="json2csv", description="Flatten JSON array into CSV")
    p.add_argument("file", help="Input .json file (array of objects)")
    p.add_argument("-o", "--out", help="Optional output .csv file")
    args = p.parse_args(argv)

    with open(args.file, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        print(fmt("  Expected non-empty JSON array of objects.", ui["warning"]))
        return

    flat_rows = [_flatten_dict(r) if isinstance(r, dict) else {"value": r} for r in data]
    cols: list[str] = []
    seen: set[str] = set()
    for row in flat_rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                cols.append(k)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    writer.writerows(flat_rows)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as out:
            out.write(buf.getvalue())
        print(f"  {fmt('Converted', ui['success'], True)} {len(flat_rows)} rows -> {args.out}")
    else:
        print(buf.getvalue(), end="")


def cmd_yaml2json(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="yaml2json", description="Convert between YAML and JSON")
    p.add_argument("file", help="Input .yml/.yaml or .json file")
    p.add_argument("--reverse", action="store_true", help="Convert JSON -> YAML instead")
    p.add_argument("-o", "--out", help="Optional output path")
    args = p.parse_args(argv)

    import yaml

    with open(args.file, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    is_json_in = args.reverse or args.file.lower().endswith(".json")
    data = json.loads(raw) if is_json_in else yaml.safe_load(raw)
    out_txt = yaml.safe_dump(data, sort_keys=False, allow_unicode=True) if is_json_in else json.dumps(data, indent=2, ensure_ascii=False, default=str)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as out:
            out.write(out_txt + ("\n" if not out_txt.endswith("\n") else ""))
        print(f"  {fmt('Saved:', ui['success'], True)} {args.out}")
    else:
        print(out_txt)


def cmd_xmlfmt(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="xmlfmt", description="Validate & pretty-print XML safely")
    p.add_argument("file", help="Input XML file")
    args = p.parse_args(argv)

    with open(args.file, "rb") as f:
        raw = f.read()
    # Validate safely with defusedxml first
    SafeET.fromstring(raw)
    dom = xml.dom.minidom.parseString(raw)
    pretty = "\n".join(ln for ln in dom.toprettyxml(indent="  ").splitlines() if ln.strip())
    header(f"XML Valid & Formatted // {os.path.basename(args.file)}", theme)
    for ln in pretty.splitlines():
        print("  " + fmt(ln, ui["accent"] if ln.lstrip().startswith("<") else ui["text"]))
    print()


def cmd_logparse(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="logparse", description="Extract IPs, HTTP status tiers & error levels from server logs")
    p.add_argument("file", help="Path to log file")
    p.add_argument("--top", type=int, default=10, help="Show top N IPs/codes (default 10)")
    args = p.parse_args(argv)

    ip_rx = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
    status_rx = re.compile(r'"\s+([1-5]\d{2})\s+')
    lvl_rx = re.compile(r"\b(ERROR|CRITICAL|FATAL|WARN|WARNING|INFO|DEBUG)\b", re.IGNORECASE)

    ips: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    total_lines = 0
    sample_errors: list[str] = []

    with open(args.file, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            total_lines += 1
            for m in ip_rx.findall(ln):
                ips[m] += 1
            sm = status_rx.search(ln)
            if sm:
                statuses[sm.group(1)] += 1
            lm = lvl_rx.search(ln)
            if lm:
                lvl = lm.group(1).upper()
                levels[lvl] += 1
                if lvl in ("ERROR", "CRITICAL", "FATAL") and len(sample_errors) < 5:
                    sample_errors.append(ln.strip()[:100])

    header(f"Log Summary // {os.path.basename(args.file)}", theme)
    print(f"  {fmt('Lines Scanned:', ui['muted'])} {fmt(f'{total_lines:,}', ui['primary'], True)}")
    if levels:
        print("\n  " + fmt("LOG LEVELS:", ui["secondary"], True))
        for k, v in levels.most_common():
            clr = ui["error"] if k in ("ERROR", "CRITICAL", "FATAL") else (ui["warning"] if "WARN" in k else ui["accent"])
            print(f"    {fmt(k.ljust(12), clr, True)} {v:,}")
    if statuses:
        print("\n  " + fmt("HTTP STATUS CODES:", ui["secondary"], True))
        for k, v in statuses.most_common(args.top):
            clr = ui["success"] if k.startswith("2") else (ui["warning"] if k.startswith(("3", "4")) else ui["error"])
            print(f"    {fmt(k.ljust(12), clr, True)} {v:,}")
    if ips:
        print("\n  " + fmt(f"TOP {min(args.top, len(ips))} IP ADDRESSES:", ui["secondary"], True))
        for ip, v in ips.most_common(args.top):
            print(f"    {fmt(ip.ljust(18), ui['accent'])} {v:,}")
    if sample_errors:
        print("\n  " + fmt("SAMPLE ERRORS:", ui["error"], True))
        for e in sample_errors:
            print("    " + fmt(e, ui["text"]))
    print()


_CRON_MACROS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _expand_cron_field(expr: str, lo: int, hi: int) -> set[int]:
    vals: set[int] = set()
    for part in expr.split(","):
        step = 1
        if "/" in part:
            rng, st = part.split("/", 1)
            step = max(1, int(st))
        else:
            rng = part
        if rng == "*":
            a, b = lo, hi
        elif "-" in rng:
            s_a, s_b = rng.split("-", 1)
            a, b = int(s_a), int(s_b)
        else:
            v = int(rng)
            vals.add(v)
            continue
        for x in range(max(lo, a), min(hi, b) + 1, step):
            vals.add(x)
    return vals


def cmd_cronparse(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="cronparse", description="Explain a 5-field cron expression & list next 5 runs")
    p.add_argument("expr", nargs="*", help="5-field cron (e.g. '*/15 * * * *' or '@daily')")
    args = p.parse_args(argv)

    raw = " ".join(args.expr).strip() if args.expr else input("  Enter cron expression: ").strip()
    norm = _CRON_MACROS.get(raw.lower(), raw)
    fields = norm.split()
    if len(fields) != 5:
        print(fmt("  Expected standard 5-field cron: MIN HOUR DOM MON DOW (e.g. '*/5 * * * *').", ui["warning"]))
        return

    mins = _expand_cron_field(fields[0], 0, 59)
    hrs = _expand_cron_field(fields[1], 0, 23)
    doms = _expand_cron_field(fields[2], 1, 31)
    mons = _expand_cron_field(fields[3], 1, 12)
    dows = {x % 7 for x in _expand_cron_field(fields[4], 0, 7)}

    header(f"Cron Expression Inspector // '{raw}'", theme)
    labels = ("Minute (0-59)", "Hour (0-23)", "Day/Month", "Month (1-12)", "Day/Week")
    for lbl, fval in zip(labels, fields):
        print(f"  {fmt((lbl + ':').ljust(16), ui['muted'])} {fmt(fval, ui['accent'], True)}")

    # Find next 5 matching minutes from current local minute (capped scan 400 days)
    cur = datetime.datetime.now().replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    runs: list[datetime.datetime] = []
    for _ in range(366 * 24 * 60):
        # Convert Python weekday (Mon=0..Sun=6) to cron (Sun=0..Sat=6)
        cron_dow = (cur.weekday() + 1) % 7
        if (
            cur.minute in mins
            and cur.hour in hrs
            and cur.day in doms
            and cur.month in mons
            and cron_dow in dows
        ):
            runs.append(cur)
            if len(runs) >= 5:
                break
        cur += datetime.timedelta(minutes=1)

    print("\n  " + fmt("NEXT 5 SCHEDULED RUNS (Local):", ui["secondary"], True))
    for r in runs:
        print(f"    {fmt('->', ui['primary'])} {fmt(r.strftime('%Y-%m-%d %H:%M (%a)'), ui['text'], True)}")
    print()


def cmd_md2html(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="md2html", description="Convert Markdown file to clean HTML")
    p.add_argument("file", help="Input .md file")
    p.add_argument("-o", "--out", help="Optional .html output path")
    args = p.parse_args(argv)

    with open(args.file, "r", encoding="utf-8-sig") as f:
        md_text = f.read()

    try:
        from markdown_it import MarkdownIt
        body_html = MarkdownIt().render(md_text)
    except Exception:
        lines = []
        for ln in md_text.splitlines():
            s = html_mod.escape(ln)
            if s.startswith("### "):
                lines.append(f"<h3>{s[4:]}</h3>")
            elif s.startswith("## "):
                lines.append(f"<h2>{s[3:]}</h2>")
            elif s.startswith("# "):
                lines.append(f"<h1>{s[2:]}</h1>")
            elif s.strip():
                lines.append(f"<p>{s}</p>")
        body_html = "\n".join(lines)

    doc = f"<!doctype html>\n<html><head><meta charset='utf-8'><title>{html_mod.escape(os.path.basename(args.file))}</title></head><body>\n{body_html}\n</body></html>\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as out:
            out.write(doc)
        print(f"  {fmt('HTML generated:', ui['success'], True)} {args.out}")
    else:
        print(doc)


def cmd_htmlent(argv: list[str], theme: dict) -> None:
    p = argparse.ArgumentParser(prog="htmlent", description="Encode or decode HTML entities")
    p.add_argument("-d", "--decode", action="store_true", help="Unescape HTML entities back to text")
    p.add_argument("text", nargs="*", help="Input text")
    args = p.parse_args(argv)

    raw = " ".join(args.text) if args.text else (_read_stdin_text() or input("  Enter text: "))
    print(html_mod.unescape(raw) if args.decode else html_mod.escape(raw, quote=True))


def cmd_sqlfmt(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="sqlfmt", description="Clean SQL query formatter & clause indenter")
    p.add_argument("target", nargs="*", help="SQL string or path to .sql file")
    args = p.parse_args(argv)

    raw = " ".join(args.target) if args.target else (_read_stdin_text() or input("  Paste SQL query: "))
    if len(args.target) == 1 and os.path.isfile(args.target[0]):
        with open(args.target[0], "r", encoding="utf-8-sig") as f:
            raw = f.read()

    # Preserve string literals while formatting keywords outside quotes
    literals: list[str] = []

    def _stash(m: re.Match) -> str:
        literals.append(m.group(0))
        return f"__TX_SQL_LIT_{len(literals) - 1}__"

    masked = re.sub(r"'(?:''|[^'])*'", _stash, raw)
    collapsed = " ".join(masked.split())
    major_kw = (
        "SELECT", "FROM", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL JOIN", "JOIN",
        "WHERE", "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "OFFSET", "UNION ALL", "UNION",
        "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM",
    )
    for kw in sorted(major_kw, key=len, reverse=True):
        collapsed = re.sub(rf"\b{re.escape(kw)}\b", f"\n{kw}", collapsed, flags=re.IGNORECASE)
    for sub_kw in ("AND", "OR"):
        collapsed = re.sub(rf"\b{sub_kw}\b", f"\n  {sub_kw}", collapsed, flags=re.IGNORECASE)

    # Restore literals
    for idx, lit in enumerate(literals):
        collapsed = collapsed.replace(f"__TX_SQL_LIT_{idx}__", lit)

    header("SQL Formatter", theme)
    for ln in collapsed.strip().splitlines():
        print("  " + fmt(ln, ui["accent"] if any(ln.startswith(k) for k in ("SELECT", "FROM", "WHERE", "JOIN")) else ui["text"]))
    print()


def cmd_colorconv(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="colorconv", description="Convert between HEX, RGB & HSL with TrueColor swatch")
    p.add_argument("color", nargs="?", help="Color e.g. #7aa2f7, rgb(122,162,247), or hsl(220,89,72)")
    args = p.parse_args(argv)

    raw = (args.color or input("  Enter color (#HEX / r,g,b / hsl(...)): ").strip()).strip().lower()
    r = g = b = 0
    if raw.startswith("#") or re.fullmatch(r"[0-9a-f]{6}|[0-9a-f]{3}", raw):
        hx = raw.lstrip("#")
        if len(hx) == 3:
            hx = "".join(c * 2 for c in hx)
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    elif raw.startswith("hsl"):
        nums = [float(x) for x in re.findall(r"[0-9.]+", raw)]
        h, s, l = nums[0] / 360.0, nums[1] / 100.0, nums[2] / 100.0
        rf, gf, bf = colorsys.hls_to_rgb(h, l, s)
        r, g, b = round(rf * 255), round(gf * 255), round(bf * 255)
    else:
        nums = [int(float(x)) for x in re.findall(r"[0-9.]+", raw)]
        if len(nums) < 3:
            print(fmt("  Could not parse color. Try #7aa2f7 or 122,162,247.", ui["warning"]))
            return
        r, g, b = [max(0, min(255, n)) for n in nums[:3]]

    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    hex_str = f"#{r:02X}{g:02X}{b:02X}"
    swatch = f"\x1b[48;2;{r};{g};{b}m        \x1b[0m"
    header(f"Color Converter // {hex_str}", theme)
    print(f"  {fmt('Swatch:'.ljust(10), ui['muted'])} {swatch}")
    print(f"  {fmt('HEX:'.ljust(10), ui['muted'])} {fmt(hex_str, ui['primary'], True)}")
    print(f"  {fmt('RGB:'.ljust(10), ui['muted'])} {fmt(f'rgb({r}, {g}, {b})', ui['accent'], True)}")
    print(f"  {fmt('HSL:'.ljust(10), ui['muted'])} {fmt(f'hsl({round(h * 360)}, {round(s * 100)}%, {round(l * 100)}%)', ui['secondary'], True)}")
    print()


def cmd_lorem(argv: list[str], theme: dict) -> None:
    p = argparse.ArgumentParser(prog="lorem", description="Generate Lorem Ipsum placeholder text")
    p.add_argument("paragraphs", nargs="?", type=int, default=2, help="Number of paragraphs (default 2)")
    p.add_argument("--words", type=int, default=0, help="Output exact N words instead of full paragraphs")
    args = p.parse_args(argv)

    bank = (
        "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt "
        "ut labore et dolore magna aliqua ut enim ad minim veniam quis nostrud exercitation "
        "ullamco laboris nisi ut aliquip ex ea commodo consequat duis aute irure dolor in "
        "reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur "
        "sint occaecat cupidatat non proident sunt in culpa qui officia deserunt mollit anim id est laborum"
    ).split()
    if args.words > 0:
        w = [bank[i % len(bank)] for i in range(args.words)]
        w[0] = w[0].capitalize()
        print(" ".join(w) + ".")
        return
    base_para = " ".join(bank).capitalize() + "."
    for i in range(max(1, min(10, args.paragraphs))):
        print(base_para)
        if i + 1 < args.paragraphs:
            print()


def cmd_slugify(argv: list[str], theme: dict) -> None:
    p = argparse.ArgumentParser(prog="slugify", description="Convert string into URL-safe lowercase slug")
    p.add_argument("text", nargs="*", help="Input string")
    args = p.parse_args(argv)
    raw = " ".join(args.text) if args.text else (_read_stdin_text() or input("  Enter text: "))
    norm = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", norm.lower()).strip("-")
    print(slug)


def cmd_caseconv(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="caseconv", description="Convert text across camelCase, snake_case, kebab-case, PascalCase")
    p.add_argument("text", nargs="*", help="Input words or identifier")
    p.add_argument("-m", "--mode", choices=("all", "camel", "snake", "kebab", "pascal", "upper"), default="all", help="Output style")
    args = p.parse_args(argv)

    raw = " ".join(args.text) if args.text else (_read_stdin_text().strip() or input("  Enter text: ").strip())
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw)
    words = [w.lower() for w in re.split(r"[^a-zA-Z0-9]+", spaced) if w]
    if not words:
        return
    forms = {
        "camel": words[0] + "".join(w.capitalize() for w in words[1:]),
        "pascal": "".join(w.capitalize() for w in words),
        "snake": "_".join(words),
        "kebab": "-".join(words),
        "upper": "_".join(w.upper() for w in words),
    }
    if args.mode != "all":
        print(forms[args.mode])
        return
    header("Case Converter", theme)
    for k, v in forms.items():
        print(f"  {fmt(k.ljust(10), ui['muted'])} {fmt(v, ui['primary'], True)}")
    print()


def cmd_uniqsort(argv: list[str], theme: dict) -> None:
    p = argparse.ArgumentParser(prog="uniqsort", description="Sort text lines with optional dedupe (-u) & counts (-c)")
    p.add_argument("file", nargs="?", default="", help="Text file (or pipe stdin)")
    p.add_argument("-r", "--reverse", action="store_true", help="Reverse sort order")
    p.add_argument("-u", "--unique", action="store_true", help="Remove duplicate lines")
    p.add_argument("-c", "--count", action="store_true", help="Show occurrence counts per line")
    p.add_argument("-i", "--ignore-case", action="store_true", help="Case-insensitive sort")
    args = p.parse_args(argv)

    raw = open(args.file, "r", encoding="utf-8", errors="replace").read() if args.file else _read_stdin_text()
    lines = [ln.rstrip("\r\n") for ln in raw.splitlines()]
    key_fn = (lambda s: s.lower()) if args.ignore_case else None
    if args.count:
        cnt = Counter(lines)
        items = sorted(cnt.items(), key=(lambda kv: (kv[1], kv[0])), reverse=args.reverse)
        for line, n in items:
            print(f"{n:>6}  {line}")
        return
    if args.unique:
        lines = list(dict.fromkeys(lines))
    lines.sort(key=key_fn, reverse=args.reverse)
    for ln in lines:
        print(ln)


def _toml_parse_stdlib(text: str) -> dict:
    """Pure-stdlib TOML 1.0 subset parser for Python 3.10 when tomllib isn't present."""
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(text)
    except ImportError:
        pass

    root: dict = {}
    cur = root
    lines = text.splitlines()
    idx = 0

    def parse_val(raw_v: str):
        v = raw_v.strip()
        if v == "true":
            return True
        if v == "false":
            return False
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            return [parse_val(x) for x in inner.split(",") if x.strip()] if inner else []
        if v.startswith("{") and v.endswith("}"):
            d = {}
            inner = v[1:-1].strip()
            for part in (inner.split(",") if inner else []):
                if "=" in part:
                    pk, pv = part.split("=", 1)
                    d[pk.strip().strip('"')] = parse_val(pv)
            return d
        try:
            clean_n = v.replace("_", "")
            return float(clean_n) if ("." in clean_n or "e" in clean_n.lower()) else int(clean_n, 0)
        except ValueError:
            return v

    def strip_comment(line: str) -> str:
        in_sq = in_dq = False
        esc = False
        for j, ch in enumerate(line):
            if esc:
                esc = False
                continue
            if ch == "\\" and in_dq:
                esc = True
            elif ch == '"' and not in_sq:
                in_dq = not in_dq
            elif ch == "'" and not in_dq:
                in_sq = not in_sq
            elif ch == "#" and not in_sq and not in_dq:
                return line[:j]
        return line

    while idx < len(lines):
        ln = strip_comment(lines[idx]).strip()
        idx += 1
        if not ln:
            continue
        if ln.startswith("[[") and ln.endswith("]]"):
            path = [p.strip().strip('"') for p in ln[2:-2].split(".")]
            node = root
            for part in path[:-1]:
                node = node.setdefault(part, {})
            arr = node.setdefault(path[-1], [])
            new_tbl: dict = {}
            arr.append(new_tbl)
            cur = new_tbl
            continue
        if ln.startswith("[") and ln.endswith("]"):
            path = [p.strip().strip('"') for p in ln[1:-1].split(".")]
            node = root
            for part in path:
                node = node.setdefault(part, {})
            cur = node
            continue
        if "=" not in ln:
            raise ValueError(f"Invalid TOML syntax on line {idx}: {ln}")
        k_raw, v_raw = ln.split("=", 1)
        # Handle multiline [...] array cleanly
        while v_raw.count("[") > v_raw.count("]") and idx < len(lines):
            v_raw += " " + strip_comment(lines[idx]).strip()
            idx += 1
        key_parts = [kp.strip().strip('"') for kp in k_raw.split(".")]
        target = cur
        for kp in key_parts[:-1]:
            target = target.setdefault(kp, {})
        target[key_parts[-1]] = parse_val(v_raw)
    return root


def cmd_tomlcheck(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="tomlcheck", description="Parse & validate a .toml file natively")
    p.add_argument("file", help="Path to .toml file")
    args = p.parse_args(argv)

    with open(args.file, "r", encoding="utf-8-sig") as f:
        data = _toml_parse_stdlib(f.read())
    header(f"TOML Validated // {os.path.basename(args.file)}", theme)
    for ln in json.dumps(data, indent=2, ensure_ascii=False, default=str).splitlines():
        print("  " + fmt(ln, ui["accent"] if ":" in ln else ui["muted"]))
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
    if not args:
        print("dev_extra.py subcommands: --jsonmin, --csv2json, --json2csv, --yaml2json, --xmlfmt, --logparse, --cronparse, --md2html, --htmlent, --sqlfmt, --colorconv, --lorem, --slugify, --caseconv, --uniqsort, --tomlcheck")
        return
    dispatch = {
        "--jsonmin": cmd_jsonmin,
        "--csv2json": cmd_csv2json,
        "--json2csv": cmd_json2csv,
        "--yaml2json": cmd_yaml2json,
        "--xmlfmt": cmd_xmlfmt,
        "--logparse": cmd_logparse,
        "--cronparse": cmd_cronparse,
        "--md2html": cmd_md2html,
        "--htmlent": cmd_htmlent,
        "--sqlfmt": cmd_sqlfmt,
        "--colorconv": cmd_colorconv,
        "--lorem": cmd_lorem,
        "--slugify": cmd_slugify,
        "--caseconv": cmd_caseconv,
        "--uniqsort": cmd_uniqsort,
        "--tomlcheck": cmd_tomlcheck,
    }
    fn = dispatch.get(args[0])
    if fn:
        fn(args[1:], theme)
    else:
        print(f"Unknown dev_extra subcommand: {args[0]}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
