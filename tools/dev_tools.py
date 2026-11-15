#!/usr/bin/env python3
"""TricksXTech Everyday Developer Utilities (pwgen, epoch, uuid)."""

from __future__ import annotations

import argparse
import datetime
import os
import secrets
import string
import sys
import uuid

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, header, load_theme

WORDLIST = (
    "amber", "anchor", "atlas", "aurora", "beacon", "cipher", "cloud", "cobalt",
    "comet", "coral", "cosmos", "crimson", "crystal", "cyber", "delta", "drift",
    "echo", "ember", "emerald", "falcon", "fiber", "flint", "forest", "frost",
    "galaxy", "glacier", "granite", "harbor", "horizon", "indigo", "jade", "jasper",
    "kernel", "lagoon", "lantern", "laser", "lunar", "matrix", "meteor", "mirage",
    "nebula", "neon", "nexus", "nordic", "nova", "obsidian", "onyx", "orbit",
    "photon", "pioneer", "pixel", "plasma", "prism", "pulse", "quartz", "radar",
    "raven", "ripple", "rocket", "saffron", "saturn", "scalar", "shadow", "signal",
    "silver", "solar", "spark", "spectrum", "sphinx", "spiral", "summit", "synth",
    "thunder", "timber", "titan", "topaz", "vector", "velvet", "vertex", "vortex",
)


def cmd_pwgen(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="pwgen", description="Cryptographically strong password & passphrase generator")
    p.add_argument("length", nargs="?", type=int, default=20, help="Password length (default 20)")
    p.add_argument("-n", "--count", type=int, default=5, help="Number of passwords to generate (default 5)")
    p.add_argument("--no-sym", action="store_true", help="Alphanumeric only (exclude punctuation symbols)")
    p.add_argument("--words", type=int, default=0, help="Generate memorable dash-separated passphrase with N words")
    args = p.parse_args(argv)

    header("Secure Password & Token Generator (secrets)", theme)
    cnt = max(1, min(30, args.count))

    if args.words > 0:
        wcnt = max(3, min(12, args.words))
        for _ in range(cnt):
            phrase = "-".join(secrets.choice(WORDLIST) for _ in range(wcnt))
            num_suffix = secrets.randbelow(90) + 10
            print(f"  {fmt(f'{phrase}-{num_suffix}', ui['accent'], True)}")
        print()
        return

    length = max(8, min(128, args.length))
    alphabet = string.ascii_letters + string.digits + ("" if args.no_sym else "!@#$%^&*_-+=")
    for _ in range(cnt):
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        print(f"  {fmt(pw, ui['primary'], True)}")
    print(fmt(f"  Length: {length} chars  |  Charset: {len(alphabet)} symbols  |  Never logged or saved", ui["muted"]))
    print()


def cmd_epoch(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="epoch", description="Unix timestamp <-> UTC/local date converter")
    p.add_argument("value", nargs="?", default="", help="Unix seconds/ms or ISO date string (omit for current time)")
    args = p.parse_args(argv)

    header("Unix Epoch & ISO-8601 Time Converter", theme)
    raw = args.value.strip()
    dt_utc: datetime.datetime

    if not raw or raw.lower() == "now":
        dt_utc = datetime.datetime.now(datetime.timezone.utc)
    elif re_match_num(raw):
        num = float(raw)
        if abs(num) > 1e11:  # milliseconds
            num /= 1000.0
        try:
            dt_utc = datetime.datetime.fromtimestamp(num, tz=datetime.timezone.utc)
        except Exception as exc:
            print(fmt(f"  Timestamp out of range: {exc}", ui["error"]))
            return
    else:
        try:
            clean = raw.replace("Z", "+00:00")
            parsed = datetime.datetime.fromisoformat(clean)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
            dt_utc = parsed.astimezone(datetime.timezone.utc)
        except Exception as exc:
            print(fmt(f"  Could not parse '{raw}' as Unix epoch or ISO-8601 date: {exc}", ui["warning"]))
            return

    dt_local = dt_utc.astimezone()
    unix_s = int(dt_utc.timestamp())
    unix_ms = int(dt_utc.timestamp() * 1000)

    print(f"  {fmt('Unix (seconds):'.ljust(18), ui['muted'])} {fmt(str(unix_s), ui['primary'], True)}")
    print(f"  {fmt('Unix (millis):'.ljust(18), ui['muted'])} {fmt(str(unix_ms), ui['accent'])}")
    print(f"  {fmt('UTC ISO-8601:'.ljust(18), ui['muted'])} {fmt(dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ'), ui['text'], True)}")
    print(f"  {fmt('Local Time:'.ljust(18), ui['muted'])} {fmt(dt_local.strftime('%Y-%m-%d %H:%M:%S %Z (%z)'), ui['success'])}")
    print()


def re_match_num(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def cmd_uuid(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="uuid", description="Generate UUID v4 identifiers")
    p.add_argument("-n", "--count", type=int, default=1, help="How many UUIDs to generate")
    p.add_argument("--upper", action="store_true", help="Uppercase output")
    args = p.parse_args(argv)

    cnt = max(1, min(50, args.count))
    for _ in range(cnt):
        val = str(uuid.uuid4())
        if args.upper:
            val = val.upper()
        print(fmt(val, ui["accent"], True))


def main() -> None:
    enable_vt()
    theme = load_theme()
    args = sys.argv[1:]
    if not args:
        print("dev_tools.py subcommands: --pwgen, --epoch, --uuid")
        return
    cmd = args[0]
    rest = args[1:]
    dispatch = {
        "--pwgen": cmd_pwgen,
        "--epoch": cmd_epoch,
        "--uuid": cmd_uuid,
    }
    fn = dispatch.get(cmd)
    if fn:
        fn(rest, theme)
    else:
        print(f"Unknown dev_tools subcommand: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
