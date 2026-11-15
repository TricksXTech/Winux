#!/usr/bin/env python3
"""TricksXTech Additional System & File Diagnostics (envfind, organize, dupes, extrename, replace, perms, cleantemp, watchdir, symlinks, zipmgr, targz, clip)."""

from __future__ import annotations

import argparse
from collections import defaultdict
import ctypes
import fnmatch
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import zipfile

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, fmt_bytes, header, load_theme

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "dist", "build"}
CLOUD_ATTRS = 0x1000 | 0x40000 | 0x400000
LINK_TAGS = (
    getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003),
    getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C),
)
SECRET_KEY_HINTS = ("KEY", "TOKEN", "SECRET", "PASS", "PWD", "CREDENTIAL", "AUTH", "API_KEY", "PRIVATE")

ORGANIZE_MAP: dict[str, set[str]] = {
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".rtf"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz"},
    "Code": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".c", ".cpp", ".h", ".java", ".cs", ".ps1", ".cmd", ".sh", ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css"},
    "Installers": {".exe", ".msi", ".msix", ".iso"},
}


def _safe_walk_files(root: str):
    stack = [os.path.abspath(root)]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for ent in it:
                    try:
                        if ent.is_symlink():
                            continue
                        st = ent.stat(follow_symlinks=False)
                        if os.name == "nt":
                            if getattr(st, "st_reparse_tag", 0) in LINK_TAGS:
                                continue
                            if getattr(st, "st_file_attributes", 0) & CLOUD_ATTRS:
                                continue
                        if ent.is_dir(follow_symlinks=False):
                            if ent.name not in SKIP_DIRS:
                                stack.append(ent.path)
                        elif ent.is_file(follow_symlinks=False):
                            yield ent.path, st.st_size
                    except OSError:
                        continue
        except OSError:
            continue


def cmd_envfind(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="envfind", description="Search & display environment variables (secrets masked by default)")
    p.add_argument("pattern", nargs="?", default="", help="Substring filter for variable name or value")
    p.add_argument("--reveal", action="store_true", help="Do not mask secret-like variable values")
    args = p.parse_args(argv)

    filt = args.pattern.lower().strip()
    header(f"Environment Variables" + (f" // filter '{args.pattern}'" if filt else ""), theme)
    items = sorted(os.environ.items(), key=lambda kv: kv[0].lower())
    shown = 0
    for k, v in items:
        if filt and filt not in k.lower() and filt not in v.lower():
            continue
        is_secret = any(h in k.upper() for h in SECRET_KEY_HINTS)
        disp = (v[:4] + "..." + f"[{len(v)} chars masked]") if (is_secret and not args.reveal and len(v) > 6) else v
        if len(disp) > 84:
            disp = disp[:81] + "..."
        print(f"  {fmt(k.ljust(28), ui['primary'], True)} {fmt(disp, ui['warning'] if is_secret and not args.reveal else ui['text'])}")
        shown += 1
    if not shown:
        print("  " + fmt("No matching environment variables found.", ui["muted"]))
    print()


def cmd_organize(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="organize", description="Sort immediate files in a folder into category subfolders")
    p.add_argument("path", nargs="?", default=".", help="Target directory (default .)")
    p.add_argument("--apply", action="store_true", help="Actually move files (defaults to dry-run preview)")
    args = p.parse_args(argv)

    target = os.path.abspath(args.path)
    if not os.path.isdir(target):
        print(fmt(f"  Directory not found: {target}", ui["error"]))
        return

    header(f"Directory File Organizer // {target}", theme)
    mode_lbl = "APPLY MODE (moving files)" if args.apply else "DRY-RUN PREVIEW (pass --apply to move)"
    print(f"  {fmt('Mode:', ui['muted'])} {fmt(mode_lbl, ui['warning'] if not args.apply else ui['success'], True)}")
    print(fmt("  " + "─" * 70, ui["border"]))

    counts: dict[str, int] = defaultdict(int)
    moved = 0
    for ent in sorted(os.scandir(target), key=lambda e: e.name.lower()):
        if not ent.is_file(follow_symlinks=False):
            continue
        ext = os.path.splitext(ent.name)[1].lower()
        bucket = "Other"
        for cat, exts in ORGANIZE_MAP.items():
            if ext in exts:
                bucket = cat
                break
        counts[bucket] += 1
        dest_dir = os.path.join(target, bucket)
        dest_path = os.path.join(dest_dir, ent.name)
        if args.apply:
            os.makedirs(dest_dir, exist_ok=True)
            if os.path.exists(dest_path):
                stem, suf = os.path.splitext(ent.name)
                n = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(dest_dir, f"{stem}_{n}{suf}")
                    n += 1
            shutil.move(ent.path, dest_path)
            moved += 1
        else:
            if moved < 25:
                print(f"  {fmt(ent.name.ljust(34), ui['text'])} -> {fmt(bucket + os.sep, ui['accent'], True)}")
            moved += 1

    print()
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    print(f"  {fmt('Total Files:', ui['muted'])} {fmt(str(moved), ui['primary'], True)}  ({summary or 'none'})")
    print()


def _sha256_file(fp: str) -> str:
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        while True:
            b = f.read(262144)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def cmd_dupes(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="dupes", description="Read-only duplicate file finder (size + SHA-256)")
    p.add_argument("path", nargs="?", default=".", help="Directory to scan (default .)")
    p.add_argument("--min-kb", type=int, default=1, help="Ignore tiny files below N KB (default 1)")
    args = p.parse_args(argv)

    target = os.path.abspath(args.path)
    min_bytes = max(0, args.min_kb) * 1024
    header(f"Duplicate File Finder // {target}", theme)

    by_size: dict[int, list[str]] = defaultdict(list)
    for fp, sz in _safe_walk_files(target):
        if sz >= min_bytes:
            by_size[sz].append(fp)

    by_hash: dict[tuple[int, str], list[str]] = defaultdict(list)
    for sz, paths in by_size.items():
        if len(paths) < 2:
            continue
        for fp in paths:
            try:
                digest = _sha256_file(fp)
                by_hash[(sz, digest)].append(fp)
            except OSError:
                continue

    groups = [(sz, dig, ps) for (sz, dig), ps in by_hash.items() if len(ps) > 1]
    groups.sort(key=lambda g: g[0] * (len(g[2]) - 1), reverse=True)

    if not groups:
        print("  " + fmt("No duplicate files found.", ui["success"]))
        print()
        return

    reclaimable = sum(sz * (len(ps) - 1) for sz, _, ps in groups)
    for idx, (sz, dig, ps) in enumerate(groups[:20], 1):
        print(f"  {fmt(f'Group #{idx}', ui['primary'], True)}  Size: {fmt(fmt_bytes(sz), ui['accent'])}  Copies: {len(ps)}  SHA256: {fmt(dig[:16] + '...', ui['muted'])}")
        for fp in ps:
            print(f"    {fmt('-', ui['muted'])} {fmt(fp, ui['text'])}")
    if len(groups) > 20:
        print(fmt(f"  ... and {len(groups) - 20} more duplicate groups.", ui["muted"]))
    print(f"\n  {fmt('Potential Reclaimable Space:', ui['muted'])} {fmt(fmt_bytes(reclaimable), ui['warning'], True)} (read-only report)\n")


def cmd_extrename(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="extrename", description="Bulk rename file extensions in a folder")
    p.add_argument("path", help="Target directory")
    p.add_argument("from_ext", help="Source extension (e.g. .jpeg or jpeg)")
    p.add_argument("to_ext", help="New extension (e.g. .jpg or jpg)")
    p.add_argument("-r", "--recursive", action="store_true", help="Include subdirectories")
    p.add_argument("--apply", action="store_true", help="Perform actual rename (dry-run by default)")
    args = p.parse_args(argv)

    src_ext = args.from_ext if args.from_ext.startswith(".") else "." + args.from_ext
    dst_ext = args.to_ext if args.to_ext.startswith(".") else "." + args.to_ext
    target = os.path.abspath(args.path)
    if not os.path.isdir(target):
        print(fmt(f"  Directory not found: {target}", ui["error"]))
        return

    header(f"Batch Extension Converter // {src_ext} -> {dst_ext}", theme)
    print(f"  {fmt('Mode:', ui['muted'])} {fmt('APPLY' if args.apply else 'DRY-RUN (pass --apply to rename)', ui['success'] if args.apply else ui['warning'], True)}")

    candidates: list[str] = []
    if args.recursive:
        for fp, _ in _safe_walk_files(target):
            if os.path.splitext(fp)[1].lower() == src_ext.lower():
                candidates.append(fp)
    else:
        for ent in os.scandir(target):
            if ent.is_file(follow_symlinks=False) and os.path.splitext(ent.name)[1].lower() == src_ext.lower():
                candidates.append(ent.path)

    changed = 0
    for fp in candidates:
        new_fp = os.path.splitext(fp)[0] + dst_ext
        if os.path.exists(new_fp):
            print(f"  {fmt('[SKIP exists]', ui['warning'])} {new_fp}")
            continue
        if args.apply:
            os.rename(fp, new_fp)
        if changed < 30:
            print(f"  {fmt(os.path.basename(fp), ui['text'])} -> {fmt(os.path.basename(new_fp), ui['accent'], True)}")
        changed += 1
    print(f"\n  {fmt('Matched:', ui['muted'])} {fmt(str(changed), ui['primary'], True)} file(s).\n")


def cmd_replace(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="replace", description="Batch text search & replace across files")
    p.add_argument("path", help="Directory or file path")
    p.add_argument("find", help="Exact substring to find")
    p.add_argument("repl", help="Replacement string")
    p.add_argument("--glob", default="*", help="Filename glob filter (e.g. *.py)")
    p.add_argument("-r", "--recursive", action="store_true", help="Recurse subdirectories")
    p.add_argument("--apply", action="store_true", help="Write modifications (dry-run by default)")
    args = p.parse_args(argv)

    target = os.path.abspath(args.path)
    files: list[str] = []
    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        it = _safe_walk_files(target) if args.recursive else ((e.path, 0) for e in os.scandir(target) if e.is_file())
        for fp, _ in it:
            if fnmatch.fnmatch(os.path.basename(fp), args.glob):
                files.append(fp)
    else:
        print(fmt(f"  Path not found: {target}", ui["error"]))
        return

    header(f"Batch Search & Replace // '{args.find}' -> '{args.repl}'", theme)
    print(f"  {fmt('Mode:', ui['muted'])} {fmt('APPLY' if args.apply else 'DRY-RUN (pass --apply to modify files)', ui['success'] if args.apply else ui['warning'], True)}")

    mod_files = 0
    total_hits = 0
    for fp in files:
        try:
            with open(fp, "rb") as bf:
                head = bf.read(2048)
                if b"\x00" in head:
                    continue
            with open(fp, "r", encoding="utf-8") as f:
                txt = f.read()
        except Exception:
            continue
        cnt = txt.count(args.find)
        if cnt <= 0:
            continue
        mod_files += 1
        total_hits += cnt
        if args.apply:
            new_txt = txt.replace(args.find, args.repl)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(new_txt)
        print(f"  {fmt(f'[{cnt}x]', ui['accent'], True)} {fmt(fp, ui['primary'] if args.apply else ui['text'])}")

    print(f"\n  {fmt('Summary:', ui['muted'])} {total_hits} match(es) across {mod_files} file(s).\n")


def cmd_perms(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="perms", description="Inspect file/folder permissions, mode bits & Windows ACLs")
    p.add_argument("path", nargs="?", default=".", help="File or directory path")
    args = p.parse_args(argv)

    target = os.path.abspath(args.path)
    if not os.path.exists(target):
        print(fmt(f"  Path not found: {target}", ui["error"]))
        return

    st = os.stat(target)
    header(f"File Permissions Audit // {target}", theme)
    mode_s = stat.filemode(st.st_mode)
    rw = f"Readable={os.access(target, os.R_OK)}  Writable={os.access(target, os.W_OK)}  Exec={os.access(target, os.X_OK)}"
    print(f"  {fmt('POSIX Mode:'.ljust(14), ui['muted'])} {fmt(mode_s, ui['accent'], True)}  (octal {oct(stat.S_IMODE(st.st_mode))})")
    print(f"  {fmt('Access Test:'.ljust(14), ui['muted'])} {fmt(rw, ui['text'])}")
    if os.name == "nt":
        attrs = getattr(st, "st_file_attributes", 0)
        flags = []
        if attrs & 0x1:
            flags.append("READONLY")
        if attrs & 0x2:
            flags.append("HIDDEN")
        if attrs & 0x4:
            flags.append("SYSTEM")
        print(f"  {fmt('Win Attribs:'.ljust(14), ui['muted'])} {fmt(', '.join(flags) or 'Normal', ui['secondary'])}")
        try:
            ic = subprocess.run(["icacls", target], capture_output=True, text=True, timeout=5)
            print("\n  " + fmt("WINDOWS ACL (icacls)", ui["secondary"], True))
            for ln in ic.stdout.splitlines()[:-1]:
                if ln.strip():
                    print("  " + fmt(ln, ui["text"]))
        except Exception:
            pass
    print()


def cmd_cleantemp(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="cleantemp", description="Safe temp/empty file cleaner (.tmp, .bak, .old, 0-byte)")
    p.add_argument("path", nargs="?", default=".", help="Directory to scan (default .)")
    p.add_argument("--include-logs", action="store_true", help="Also include *.log files")
    p.add_argument("--apply", action="store_true", help="Delete matched temp files (dry-run by default)")
    args = p.parse_args(argv)

    target = os.path.abspath(args.path)
    low_t = target.lower()
    if any(seg in low_t for seg in ("\\windows", "\\program files", "c:\\programdata")):
        print(fmt(f"  Refused: '{target}' is a protected OS directory.", ui["error"]))
        return

    exts = {".tmp", ".temp", ".bak", ".old"}
    if args.include_logs:
        exts.add(".log")

    header(f"Temporary File Cleaner // {target}", theme)
    print(f"  {fmt('Mode:', ui['muted'])} {fmt('DELETE' if args.apply else 'DRY-RUN PREVIEW (pass --apply to delete)', ui['error'] if args.apply else ui['warning'], True)}")

    hits: list[tuple[str, int, str]] = []
    for fp, sz in _safe_walk_files(target):
        ext = os.path.splitext(fp)[1].lower()
        if ext in exts:
            hits.append((fp, sz, f"temp ext ({ext})"))
        elif sz == 0:
            hits.append((fp, 0, "empty 0-byte"))

    total_b = sum(s for _, s, _ in hits)
    deleted = 0
    for fp, sz, why in hits[:35]:
        print(f"  {fmt(why.ljust(18), ui['muted'])} {fmt(fmt_bytes(sz).rjust(10), ui['accent'])}  {fmt(fp, ui['text'])}")
    if args.apply:
        for fp, _, _ in hits:
            try:
                os.remove(fp)
                deleted += 1
            except OSError:
                pass
    if len(hits) > 35:
        print(fmt(f"  ... and {len(hits) - 35} more candidate files.", ui["muted"]))
    print(f"\n  {fmt('Matched:', ui['muted'])} {len(hits)} file(s) ({fmt_bytes(total_b)})" + (f"   Deleted: {deleted}" if args.apply else "") + "\n")


def cmd_watchdir(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="watchdir", description="Watch a directory live for Created / Modified / Deleted files")
    p.add_argument("path", nargs="?", default=".", help="Directory to watch (default .)")
    p.add_argument("--interval", type=float, default=0.8, help="Polling interval in seconds (default 0.8)")
    args = p.parse_args(argv)

    target = os.path.abspath(args.path)
    if not os.path.isdir(target):
        print(fmt(f"  Directory not found: {target}", ui["error"]))
        return

    def snap() -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for fp, sz in _safe_walk_files(target):
            try:
                out[fp] = (os.stat(fp).st_mtime_ns, sz)
            except OSError:
                pass
        return out

    header(f"File Modification Monitor // {target}", theme)
    print(f"  {fmt('Watching for changes (Ctrl+C to stop)...', ui['muted'])}")
    prev = snap()
    try:
        while True:
            time.sleep(max(0.25, args.interval))
            cur = snap()
            ts = time.strftime("%H:%M:%S")
            for k in sorted(cur.keys() - prev.keys()):
                print(f"  {fmt('[' + ts + ']', ui['muted'])} {fmt('[CREATED] ', ui['success'], True)} {fmt(os.path.relpath(k, target), ui['text'])}")
            for k in sorted(prev.keys() - cur.keys()):
                print(f"  {fmt('[' + ts + ']', ui['muted'])} {fmt('[DELETED] ', ui['error'], True)} {fmt(os.path.relpath(k, target), ui['text'])}")
            for k in sorted(cur.keys() & prev.keys()):
                if cur[k] != prev[k]:
                    print(f"  {fmt('[' + ts + ']', ui['muted'])} {fmt('[MODIFIED]', ui['accent'], True)} {fmt(os.path.relpath(k, target), ui['text'])} ({fmt_bytes(cur[k][1])})")
            prev = cur
    except KeyboardInterrupt:
        print("\n  " + fmt("Watch stopped.", ui["warning"]))


def cmd_symlinks(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="symlinks", description="Inspect symlinks/junctions and detect broken targets")
    p.add_argument("path", nargs="?", default=".", help="Directory to audit (default .)")
    args = p.parse_args(argv)

    target = os.path.abspath(args.path)
    header(f"Symlink & Junction Inspector // {target}", theme)
    found = 0
    stack = [target]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for ent in it:
                    try:
                        st = ent.stat(follow_symlinks=False)
                        reparse = getattr(st, "st_reparse_tag", 0)
                        if ent.is_symlink() or reparse in LINK_TAGS:
                            found += 1
                            try:
                                link_tgt = os.readlink(ent.path)
                            except OSError:
                                link_tgt = "(unreadable target)"
                            resolved = os.path.join(os.path.dirname(ent.path), link_tgt) if not os.path.isabs(link_tgt) else link_tgt
                            ok = os.path.exists(resolved)
                            badge = fmt("[OK]    ", ui["success"], True) if ok else fmt("[BROKEN]", ui["error"], True)
                            print(f"  {badge} {fmt(ent.path, ui['primary'])} -> {fmt(link_tgt, ui['accent'] if ok else ui['warning'])}")
                        elif ent.is_dir(follow_symlinks=False) and ent.name not in SKIP_DIRS:
                            stack.append(ent.path)
                    except OSError:
                        continue
        except OSError:
            continue
    if not found:
        print("  " + fmt("No symlinks or directory junctions found.", ui["muted"]))
    print()


def cmd_zipmgr(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="zipmgr", description="Create, list, or safely extract ZIP archives")
    p.add_argument("action", choices=("create", "extract", "list", "pack", "unpack"), help="create | extract | list")
    p.add_argument("archive", help="Path to .zip file")
    p.add_argument("target", nargs="?", default=".", help="Source folder/file (for create) or output dir (for extract)")
    args = p.parse_args(argv)

    act = {"pack": "create", "unpack": "extract"}.get(args.action, args.action)
    header(f"ZIP Manager ({act}) // {args.archive}", theme)
    try:
        if act == "list":
            if not os.path.isfile(args.archive):
                print(fmt(f"  Archive not found: {args.archive}", ui["error"]))
                sys.exit(1)
            with zipfile.ZipFile(args.archive, "r") as zf:
                for info in zf.infolist()[:50]:
                    print(f"  {fmt(fmt_bytes(info.file_size).rjust(10), ui['accent'])}  {fmt(info.filename, ui['text'])}")
                if len(zf.infolist()) > 50:
                    print(fmt(f"  ... and {len(zf.infolist()) - 50} more entries.", ui["muted"]))
        elif act == "create":
            src = os.path.abspath(args.target)
            if not os.path.exists(src):
                print(fmt(f"  Source not found: {src}", ui["error"]))
                sys.exit(1)
            cnt = 0
            with zipfile.ZipFile(args.archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                if os.path.isfile(src):
                    zf.write(src, os.path.basename(src))
                    cnt = 1
                else:
                    for fp, _ in _safe_walk_files(src):
                        if os.path.abspath(fp) == os.path.abspath(args.archive):
                            continue
                        zf.write(fp, os.path.relpath(fp, src))
                        cnt += 1
            print(f"  {fmt('Created:', ui['success'], True)} {args.archive} ({cnt} files, {fmt_bytes(os.path.getsize(args.archive))})")
        elif act == "extract":
            if not os.path.isfile(args.archive):
                print(fmt(f"  Archive not found: {args.archive}", ui["error"]))
                sys.exit(1)
            dest = os.path.abspath(args.target)
            os.makedirs(dest, exist_ok=True)
            extracted = 0
            with zipfile.ZipFile(args.archive, "r") as zf:
                for member in zf.infolist():
                    out_p = os.path.abspath(os.path.join(dest, member.filename))
                    if not (out_p == dest or out_p.startswith(dest + os.sep)):
                        raise ValueError(f"Blocked unsafe zip path: {member.filename}")
                    zf.extract(member, dest)
                    extracted += 1
            print(f"  {fmt('Extracted:', ui['success'], True)} {extracted} entry(s) into {dest}")
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(fmt(f"  ZIP error: {exc}", ui["error"], True))
        sys.exit(1)
    print()


def cmd_targz(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="targz", description="Manage .tar / .tar.gz / .tar.bz2 archives cleanly")
    p.add_argument("action", choices=("create", "extract", "list", "pack", "unpack"), help="create | extract | list")
    p.add_argument("archive", help="Path to tarball (.tar.gz, .tar.bz2, .tar)")
    p.add_argument("target", nargs="?", default=".", help="Source path (create) or destination dir (extract)")
    args = p.parse_args(argv)

    act = {"pack": "create", "unpack": "extract"}.get(args.action, args.action)
    header(f"Tarball Manager ({act}) // {args.archive}", theme)
    low = args.archive.lower()
    wmode = "w:bz2" if low.endswith((".bz2", ".tbz2")) else ("w:gz" if low.endswith((".gz", ".tgz")) else "w")

    try:
        if act == "list":
            if not os.path.isfile(args.archive):
                print(fmt(f"  Archive not found: {args.archive}", ui["error"]))
                sys.exit(1)
            with tarfile.open(args.archive, "r:*") as tf:
                members = tf.getmembers()
                for m in members[:50]:
                    print(f"  {fmt(fmt_bytes(m.size).rjust(10), ui['accent'])}  {fmt(m.name, ui['text'])}")
        elif act == "create":
            src = os.path.abspath(args.target)
            if not os.path.exists(src):
                print(fmt(f"  Source not found: {src}", ui["error"]))
                sys.exit(1)
            with tarfile.open(args.archive, wmode) as tf:
                tf.add(src, arcname=os.path.basename(src))
            print(f"  {fmt('Created:', ui['success'], True)} {args.archive} ({fmt_bytes(os.path.getsize(args.archive))})")
        elif act == "extract":
            if not os.path.isfile(args.archive):
                print(fmt(f"  Archive not found: {args.archive}", ui["error"]))
                sys.exit(1)
            dest = os.path.abspath(args.target)
            os.makedirs(dest, exist_ok=True)
            with tarfile.open(args.archive, "r:*") as tf:
                for m in tf.getmembers():
                    out_p = os.path.abspath(os.path.join(dest, m.name))
                    if not (out_p == dest or out_p.startswith(dest + os.sep)):
                        raise ValueError(f"Blocked unsafe tar member: {m.name}")
                tf.extractall(dest)
            print(f"  {fmt('Extracted cleanly into:', ui['success'], True)} {dest}")
    except (OSError, tarfile.TarError, ValueError) as exc:
        print(fmt(f"  Tar error: {exc}", ui["error"], True))
        sys.exit(1)
    print()


def _win32_clipboard_get() -> str:
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

    if not user32.OpenClipboard(None):
        raise RuntimeError("Could not open system clipboard")
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _win32_clipboard_set(text: str) -> None:
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.EmptyClipboard.argtypes = []
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

    data = (text + "\x00").encode("utf-16-le")
    hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not hmem:
        raise MemoryError("GlobalAlloc failed")
    ptr = kernel32.GlobalLock(hmem)
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(hmem)

    if not user32.OpenClipboard(None):
        raise RuntimeError("Could not open clipboard")
    try:
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_UNICODETEXT, hmem)
    finally:
        user32.CloseClipboard()


def cmd_clip(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="clip", description="Read or write Windows clipboard text cleanly")
    p.add_argument("action", nargs="?", default="paste", help="paste (default) | copy")
    p.add_argument("text", nargs="*", help="Text to copy (or pipe stdin)")
    args = p.parse_args(argv)

    act = args.action.lower().strip()
    if act == "copy" or args.text or (sys.stdin is not None and not sys.stdin.isatty()):
        payload = " ".join(args.text) if args.text else ("" if sys.stdin.isatty() else sys.stdin.read())
        if not payload and act not in ("paste", "get"):
            payload = act
        _win32_clipboard_set(payload)
        print(f"  {fmt('[CLIPBOARD]', ui['success'], True)} Copied {len(payload)} char(s).")
        return

    txt = _win32_clipboard_get()
    print(txt)


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
        print("sys_extra.py subcommands: --envfind, --organize, --dupes, --extrename, --replace, --perms, --cleantemp, --watchdir, --symlinks, --zipmgr, --targz, --clip")
        return
    dispatch = {
        "--envfind": cmd_envfind,
        "--organize": cmd_organize,
        "--dupes": cmd_dupes,
        "--extrename": cmd_extrename,
        "--replace": cmd_replace,
        "--perms": cmd_perms,
        "--cleantemp": cmd_cleantemp,
        "--watchdir": cmd_watchdir,
        "--symlinks": cmd_symlinks,
        "--zipmgr": cmd_zipmgr,
        "--targz": cmd_targz,
        "--clip": cmd_clip,
    }
    fn = dispatch.get(args[0])
    if fn:
        fn(args[1:], theme)
    else:
        print(f"Unknown sys_extra subcommand: {args[0]}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
