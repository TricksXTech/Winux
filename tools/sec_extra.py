#!/usr/bin/env python3
"""
TricksXTech Defensive Security Auditing, Digital Forensics & Static Analysis Tools
(Safe, local-first subset inspired by auditing/forensic categories; zero offensive/exploit/listener code)
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import re
import stat
import struct
import subprocess
import sys
import unicodedata
import urllib.parse
import zlib
from pathlib import Path

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from free_tools import enable_vt, load_theme, fmt, fmt_bytes, header


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    ent = 0.0
    for c in counts:
        if c:
            p = c / n
            ent -= p * math.log2(p)
    return ent


def _detect_magic(head: bytes) -> str:
    if head.startswith(b"MZ"):
        return "PE/DOS Executable (MZ)"
    if head.startswith(b"\x7fELF"):
        return "ELF Unix/Linux Executable"
    if head.startswith(b"%PDF-"):
        return "PDF Document"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG Image"
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG Image"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "GIF Image"
    if head.startswith(b"BM"):
        return "BMP Image"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return "ZIP / Office OOXML / JAR Archive"
    if head.startswith(b"\x1f\x8b"):
        return "GZIP Compressed Archive"
    if head.startswith(b"7z\xbc\xaf'\x1c"):
        return "7-Zip Archive"
    if head.startswith(b"Rar!\x1a\x07"):
        return "RAR Archive"
    if head.startswith(b"SQLite format 3\x00"):
        return "SQLite 3 Database"
    return "Unknown / Plaintext"


# ── 1. Local Windows Security Exposure Audit (secaudit) ───────────────────────

def cmd_secaudit(argv: list[str], theme: dict) -> int:
    ap = argparse.ArgumentParser(prog="secaudit", description="Read-only Windows hardening, firewall, Defender & open-port exposure audit")
    ap.parse_args(argv)

    ui = theme["ui"]
    header("Windows Local Security Posture Audit (Read-Only)", theme)

    if os.name != "nt":
        print("  " + fmt("Windows-specific audit requires Windows OS.", ui["warning"]))
        return 1

    ps_script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$fw = @(Get-NetFirewallProfile | Select-Object Name, @{N='Enabled';E={[bool]$_.Enabled}})
$def = Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled, AntispywareEnabled
$rdp = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections).fDenyTSConnections
$smb1 = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters' -Name SMB1).SMB1
$guest = (Get-LocalUser -Name 'Guest').Enabled
$exposed = @(Get-NetTCPConnection -State Listen | Where-Object { $_.LocalAddress -in @('0.0.0.0','::','*') } | ForEach-Object {
    $pname = (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    [PSCustomObject]@{ Port=$_.LocalPort; Addr=$_.LocalAddress; PID=$_.OwningProcess; Proc=$pname }
} | Sort-Object Port, Addr -Unique)
$loopbackCount = @(Get-NetTCPConnection -State Listen | Where-Object { $_.LocalAddress -in @('127.0.0.1','::1') }).Count
[PSCustomObject]@{
    Firewall = $fw
    Defender = $def
    RdpDenied = $rdp
    Smb1 = $smb1
    GuestEnabled = $guest
    Exposed = $exposed
    LoopbackCount = $loopbackCount
} | ConvertTo-Json -Depth 4
"""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25,
        )
        data = json.loads(res.stdout or "{}")
    except Exception as ex:
        print("  " + fmt(f"Audit query failed: {ex}", ui["error"], True))
        return 1

    print("  " + fmt("DEFENSIVE PROTECTIONS", ui["secondary"], True))
    fw_list = data.get("Firewall") or []
    if isinstance(fw_list, dict):
        fw_list = [fw_list]
    for f in fw_list:
        on = bool(f.get("Enabled"))
        badge = fmt("ON ", ui["success"], True) if on else fmt("OFF", ui["error"], True)
        print(f"    Firewall ({f.get('Name', '?').ljust(7)}): {badge}")

    ddef = data.get("Defender") or {}
    if ddef:
        av_on = bool(ddef.get("AntivirusEnabled"))
        rtp_on = bool(ddef.get("RealTimeProtectionEnabled"))
        print(f"    Windows Defender AV:   {fmt('ENABLED', ui['success'], True) if av_on else fmt('DISABLED', ui['warning'], True)}")
        print(f"    Real-Time Protection:  {fmt('ENABLED', ui['success'], True) if rtp_on else fmt('DISABLED', ui['warning'], True)}")

    rdp_denied = data.get("RdpDenied")
    if rdp_denied is not None:
        rdp_off = int(rdp_denied) == 1
        print(f"    Remote Desktop (RDP):  {fmt('DISABLED (safer)', ui['success'], True) if rdp_off else fmt('ENABLED (ensure NLA & strong password)', ui['warning'], True)}")

    smb1 = data.get("Smb1")
    smb1_off = (smb1 is None) or (int(smb1) == 0)
    print(f"    Legacy SMBv1 Protocol: {fmt('DISABLED', ui['success'], True) if smb1_off else fmt('ENABLED (disable SMBv1!)', ui['error'], True)}")

    guest_on = data.get("GuestEnabled")
    if guest_on is not None:
        print(f"    Built-in Guest Acct:   {fmt('DISABLED', ui['success'], True) if not guest_on else fmt('ENABLED (risk!)', ui['error'], True)}")

    print()
    print("  " + fmt("EXPOSED NETWORK LISTENERS (0.0.0.0 / ::)", ui["secondary"], True))
    exposed = data.get("Exposed") or []
    if isinstance(exposed, dict):
        exposed = [exposed]
    print(f"    {fmt('Localhost-only listeners (127.0.0.1 / ::1):', ui['muted'])} {data.get('LoopbackCount', 0)}")
    if not exposed:
        print("    " + fmt("✓ Zero ports exposed on wildcard addresses (0.0.0.0 / ::).", ui["success"], True))
    else:
        for item in exposed[:25]:
            proc = item.get("Proc") or "?"
            addr = item.get("Addr") or "*"
            port = item.get("Port") or "?"
            pid = item.get("PID") or "?"
            print(f"    {fmt(':', ui['muted'])}{fmt(str(port).ljust(6), ui['accent'], True)}  {fmt(addr.ljust(8), ui['muted'])}  PID {str(pid).ljust(6)}  {fmt(str(proc), ui['text'])}")
        if len(exposed) > 25:
            print("    " + fmt(f"... and {len(exposed) - 25} more.", ui["muted"]))
    print()
    print("  " + fmt("TricksXTech Tool Suite Policy: 0 listening services, 0 remote shells, 100% local execution.", ui["muted"]))
    print()
    return 0


# ── 2. Static Binary / PE / ELF Inspector (peinspect) ─────────────────────────

def _extract_ascii_strings(data: bytes, min_len: int = 6, max_items: int = 25) -> list[str]:
    pat = re.compile(rb"[\x20-\x7e]{" + str(min_len).encode("ascii") + rb",}")
    found = []
    seen = set()
    for m in pat.finditer(data[:2 * 1024 * 1024]):
        s = m.group(0).decode("ascii", errors="replace").strip()
        if s and s not in seen:
            seen.add(s)
            found.append(s)
            if len(found) >= max_items:
                break
    return found


def cmd_peinspect(argv: list[str], theme: dict) -> int:
    ap = argparse.ArgumentParser(prog="peinspect", description="Safe static PE/ELF binary header, section entropy & strings analyzer (never executes files)")
    ap.add_argument("file", help="Path to executable, DLL, ELF, or binary")
    ap.add_argument("--strings", type=int, default=20, help="Number of extracted ASCII strings to show (default 20, 0 to skip)")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    if not os.path.isfile(args.file):
        print("  " + fmt(f"File not found: {args.file}", ui["error"], True))
        return 1

    with open(args.file, "rb") as f:
        data = f.read()

    header(f"Static Binary Inspector ({os.path.basename(args.file)})", theme)
    ent = _shannon_entropy(data)
    ent_tag = fmt(f"{ent:.2f} bits/byte (HIGH/PACKED?)", ui["warning"], True) if ent >= 7.2 else fmt(f"{ent:.2f} bits/byte", ui["accent"], True)
    print(f"  {fmt('File Size:', ui['secondary'], True)}   {fmt_bytes(len(data))} ({len(data):,} bytes)")
    print(f"  {fmt('Format:', ui['secondary'], True)}      {fmt(_detect_magic(data[:16]), ui['primary'], True)}")
    print(f"  {fmt('SHA-256:', ui['secondary'], True)}     {hashlib.sha256(data).hexdigest()}")
    print(f"  {fmt('Entropy:', ui['secondary'], True)}     {ent_tag}")

    if data.startswith(b"MZ") and len(data) >= 64:
        pe_off = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_off + 24 <= len(data) and data[pe_off:pe_off + 4] == b"PE\x00\x00":
            machine, num_sec, ts, _, _, opt_sz, chars = struct.unpack_from("<HHIIIHH", data, pe_off + 4)
            arch_map = {0x014C: "x86 (32-bit)", 0x8664: "x86-64 (64-bit)", 0xAA64: "ARM64", 0x01C0: "ARM"}
            arch = arch_map.get(machine, f"0x{machine:04X}")
            kind = "DLL" if (chars & 0x2000) else "EXE"
            import datetime as _dt
            t_str = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"  {fmt('PE Arch:', ui['secondary'], True)}     {arch} [{kind}]   Built: {t_str}")

            opt_off = pe_off + 24
            sec_off = opt_off + opt_sz
            print()
            print("  " + fmt("PE SECTIONS", ui["secondary"], True))
            print(f"    {'NAME'.ljust(10)} {'VIRT_SZ'.rjust(10)} {'RAW_SZ'.rjust(10)} {'ENTROPY'.rjust(9)}  NOTE")
            for i in range(min(num_sec, 24)):
                s_pos = sec_off + i * 40
                if s_pos + 40 > len(data):
                    break
                raw_name, vsz, _va, rsz, rptr, _, _, _, _sc = struct.unpack_from("<8sIIIIIIHI", data, s_pos)
                sname = raw_name.split(b"\x00", 1)[0].decode("ascii", errors="replace")
                chunk = data[rptr:rptr + rsz] if rsz and rptr + rsz <= len(data) else b""
                sent = _shannon_entropy(chunk)
                note = fmt("PACKED/OBFUSCATED?", ui["warning"]) if sent >= 7.2 else fmt("normal", ui["muted"])
                print(f"    {fmt(sname.ljust(10), ui['primary'], True)} {fmt(fmt_bytes(vsz).rjust(10), ui['text'])} {fmt(fmt_bytes(rsz).rjust(10), ui['text'])} {fmt(f'{sent:6.2f}'.rjust(9), ui['accent'])}  {note}")

    elif data.startswith(b"\x7fELF") and len(data) >= 24:
        cls = "64-bit" if data[4] == 2 else ("32-bit" if data[4] == 1 else "?")
        end = "Little-Endian" if data[5] == 1 else "Big-Endian"
        print(f"  {fmt('ELF Header:', ui['secondary'], True)}  {cls}, {end}")

    if args.strings > 0:
        strs = _extract_ascii_strings(data, min_len=6, max_items=args.strings)
        print()
        print(f"  {fmt('SAMPLE ASCII STRINGS', ui['secondary'], True)} (showing up to {args.strings})")
        for s in strs:
            print("    " + fmt(s[:88], ui["text"]))
    print()
    return 0


# ── 3. Forensic File Magic & EXIF Inspector (exifinfo) ────────────────────────

_EXIF_TAGS = {
    0x010F: "Make",
    0x0110: "Model",
    0x0112: "Orientation",
    0x0131: "Software",
    0x0132: "DateTime",
    0x013B: "Artist",
    0x8298: "Copyright",
    0x8769: "ExifIFDPtr",
    0x8825: "GPSInfoIFDPtr",
    0x9003: "DateTimeOriginal",
    0xA431: "BodySerialNumber",
}


def _parse_jpeg_exif(data: bytes) -> dict:
    info = {}
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            break
        marker = data[pos + 1]
        pos += 2
        if marker in (0xD9, 0xDA):
            break
        if marker == 0xD8 or (0xD0 <= marker <= 0xD7):
            continue
        if pos + 2 > len(data):
            break
        seg_len = struct.unpack_from(">H", data, pos)[0]
        seg = data[pos + 2:pos + seg_len]
        pos += seg_len
        if marker == 0xE1 and seg.startswith(b"Exif\x00\x00"):
            tiff = seg[6:]
            if len(tiff) < 8:
                continue
            endian = "<" if tiff[:2] == b"II" else (">" if tiff[:2] == b"MM" else "")
            if not endian:
                continue
            ifd0_off = struct.unpack_from(endian + "I", tiff, 4)[0]

            def read_ifd(offset: int):
                out = {}
                if offset + 2 > len(tiff):
                    return out
                count = struct.unpack_from(endian + "H", tiff, offset)[0]
                for i in range(count):
                    eo = offset + 2 + i * 12
                    if eo + 12 > len(tiff):
                        break
                    tag, typ, cnt, val_off = struct.unpack_from(endian + "HHII", tiff, eo)
                    name = _EXIF_TAGS.get(tag)
                    if not name:
                        continue
                    if typ == 2:  # ASCII
                        raw = tiff[eo + 8:eo + 12] if cnt <= 4 else tiff[val_off:val_off + cnt]
                        out[name] = raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()
                    elif typ in (3, 4):
                        out[name] = val_off
                return out

            tags = read_ifd(ifd0_off)
            if "ExifIFDPtr" in tags:
                tags.update(read_ifd(int(tags.pop("ExifIFDPtr"))))
            if "GPSInfoIFDPtr" in tags:
                tags.pop("GPSInfoIFDPtr")
                tags["GPS_Geotag"] = "PRESENT (image may reveal location!)"
            info.update(tags)
            break
    return info


def _parse_png_meta(data: bytes) -> dict:
    meta = {}
    pos = 8
    texts = []
    while pos + 8 <= len(data):
        clen, ctype = struct.unpack_from(">I4s", data, pos)
        cdata = data[pos + 8:pos + 8 + clen]
        pos += 12 + clen
        if ctype == b"IHDR" and len(cdata) >= 9:
            w, h, bd, ct = struct.unpack_from(">IIBB", cdata, 0)
            meta["Dimensions"] = f"{w}x{h} ({bd}-bit)"
        elif ctype == b"tEXt" and b"\x00" in cdata:
            k, v = cdata.split(b"\x00", 1)
            texts.append(f"{k.decode('latin1', 'replace')}={v.decode('latin1', 'replace')[:60]}")
        elif ctype == b"IEND":
            break
    if texts:
        meta["TextChunks"] = "; ".join(texts[:8])
    return meta


def cmd_exifinfo(argv: list[str], theme: dict) -> int:
    ap = argparse.ArgumentParser(prog="exifinfo", description="Forensic file magic verifier & JPEG EXIF / PNG / hash metadata reader")
    ap.add_argument("file", help="Target image, PDF, or file")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    if not os.path.isfile(args.file):
        print("  " + fmt(f"File not found: {args.file}", ui["error"], True))
        return 1

    with open(args.file, "rb") as f:
        data = f.read()

    magic = _detect_magic(data[:16])
    ext = Path(args.file).suffix.lower()
    mismatch = (
        (magic.startswith("PE/") and ext not in (".exe", ".dll", ".sys", ".scr"))
        or (magic.startswith("JPEG") and ext not in (".jpg", ".jpeg"))
        or (magic.startswith("PNG") and ext != ".png")
        or (magic.startswith("PDF") and ext != ".pdf")
    )

    header(f"Forensics & EXIF Inspector ({os.path.basename(args.file)})", theme)
    print(f"  {fmt('Size:', ui['secondary'], True)}        {fmt_bytes(len(data))} ({len(data):,} bytes)")
    print(f"  {fmt('Extension:', ui['secondary'], True)}   {ext or '(none)'}")
    print(f"  {fmt('Magic Type:', ui['secondary'], True)}  {fmt(magic, ui['error'] if mismatch else ui['primary'], True)}")
    if mismatch:
        print("  " + fmt("[!] ALERT: File extension does NOT match binary magic signature!", ui["error"], True))
    print(f"  {fmt('MD5:', ui['secondary'], True)}         {hashlib.md5(data).hexdigest()}")
    print(f"  {fmt('SHA-256:', ui['secondary'], True)}     {hashlib.sha256(data).hexdigest()}")

    meta = {}
    if data.startswith(b"\xff\xd8\xff"):
        meta = _parse_jpeg_exif(data)
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        meta = _parse_png_meta(data)

    if meta:
        print()
        print("  " + fmt("EMBEDDED METADATA / EXIF", ui["secondary"], True))
        for k, v in meta.items():
            col = ui["warning"] if "GPS" in k else ui["text"]
            print(f"    {fmt(str(k).ljust(18), ui['accent'])} {fmt(str(v), col)}")
    else:
        print()
        print("  " + fmt("No embedded EXIF/PNG metadata tags detected.", ui["muted"]))
    print()
    return 0


# ── 4. Hex Dump Viewer (hexview) ──────────────────────────────────────────────

def cmd_hexview(argv: list[str], theme: dict) -> int:
    ap = argparse.ArgumentParser(prog="hexview", description="Canonical hexadecimal + ASCII binary file viewer")
    ap.add_argument("file")
    ap.add_argument("--offset", type=int, default=0, help="Start byte offset (default 0)")
    ap.add_argument("-n", "--bytes", dest="nbytes", type=int, default=256, help="Bytes to display (default 256)")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    if not os.path.isfile(args.file):
        print("  " + fmt(f"File not found: {args.file}", ui["error"], True))
        return 1

    off = max(0, args.offset)
    count = max(1, min(4096, args.nbytes))
    with open(args.file, "rb") as f:
        f.seek(off)
        chunk = f.read(count)

    header(f"HexView ({os.path.basename(args.file)} @ 0x{off:X})", theme)
    print(f"  {fmt('Magic:', ui['muted'])} {_detect_magic(chunk[:16])}   Showing {len(chunk)} byte(s)")
    print()
    for i in range(0, len(chunk), 16):
        row = chunk[i:i + 16]
        left = " ".join(f"{b:02x}" for b in row[:8]).ljust(23)
        right = " ".join(f"{b:02x}" for b in row[8:]).ljust(23)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        addr_s = f"{off + i:08x}"
        print(f"  {fmt(addr_s, ui['accent'])}: {fmt(left, ui['text'])}  {fmt(right, ui['text'])}  |{fmt(asc, ui['primary'])}|")
    print()
    return 0


# ── 5. Local Hash Identifier (hashid) ─────────────────────────────────────────

def cmd_hashid(argv: list[str], theme: dict) -> int:
    ap = argparse.ArgumentParser(prog="hashid", description="Identify hash or token format locally (read-only pattern classifier)")
    ap.add_argument("value", nargs="+")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    val = " ".join(args.value).strip()
    header("Hash & Token Classifier", theme)

    matches = []
    if re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", val):
        matches.append("JWT (JSON Web Token) — inspect claims with: jwt <token>")
    if val.startswith(("$2a$", "$2b$", "$2y$", "$2x$")) and len(val) == 60:
        matches.append("OpenBSD bcrypt ($2a/$2b/$2y) — verify locally with: bcryptcheck <hash> <pw>")
    elif val.startswith("$argon2"):
        matches.append("Argon2 (argon2id / argon2i / argon2d)")
    elif val.startswith("$apr1$"):
        matches.append("Apache APR1-MD5 htpasswd hash")
    elif val.startswith("$6$"):
        matches.append("Unix crypt SHA-512 ($6$)")
    elif val.startswith("$5$"):
        matches.append("Unix crypt SHA-256 ($5$)")
    elif val.startswith("$1$"):
        matches.append("Unix crypt MD5 ($1$)")
    elif re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", val):
        matches.append("UUID (RFC 4122)")
    elif re.fullmatch(r"[0-9a-fA-F]+", val):
        ln = len(val)
        by_len = {
            8: ["CRC32 / Adler-32 (32-bit hex)"],
            32: ["MD5 (128-bit)", "MD4 (128-bit)", "NTLM (Windows 128-bit)"],
            40: ["SHA-1 (160-bit)", "RIPEMD-160", "MySQL5 SHA1(SHA1)"],
            56: ["SHA-224 (224-bit)", "SHA3-224"],
            64: ["SHA-256 (256-bit)", "SHA3-256", "BLAKE2s-256"],
            96: ["SHA-384 (384-bit)", "SHA3-384"],
            128: ["SHA-512 (512-bit)", "SHA3-512", "BLAKE2b-512", "Whirlpool"],
        }
        matches.extend(by_len.get(ln, [f"Hex string ({ln * 4} bits / {ln} hex chars)"]))

    print(f"  {fmt('Length:', ui['secondary'], True)}  {len(val)} chars")
    if not matches:
        print(f"  {fmt('Matches:', ui['warning'], True)} Unrecognized format")
    else:
        print(f"  {fmt('Likely:', ui['secondary'], True)}")
        for m in matches:
            print(f"    • {fmt(m, ui['primary'], True)}")
    print()
    return 0


# ── 6. Offline Secret & Config Risk Scanner (secretaudit) ─────────────────────

_SECRET_RULES = [
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub Token", re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{30,}\b|github_pat_[A-Za-z0-9_]{30,}")),
    ("Private Key Header", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("Google API Key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("Stripe Live Secret", re.compile(r"\bsk_live_[0-9A-Za-z]{20,}\b")),
    ("Slack Token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("Hardcoded Secret Assign", re.compile(r"(?i)\b(?:api_key|secret_key|private_key|db_pass|password)\b\s*[:=]\s*['\"][^'\"\n]{8,}['\"]")),
    ("Wildcard Bind 0.0.0.0", re.compile(r"""['"]0\.0\.0\.0['"]""")),
]


def _mask_secret(s: str) -> str:
    if len(s) <= 10:
        return "****"
    return s[:4] + "*" * (len(s) - 8) + s[-4:]


def cmd_secretaudit(argv: list[str], theme: dict) -> int:
    ap = argparse.ArgumentParser(prog="secretaudit", description="Offline static scanner for leaked secrets, private keys & 0.0.0.0 binds")
    ap.add_argument("path", nargs="?", default=".", help="Directory or file to scan")
    ap.add_argument("--max-kb", type=int, default=512)
    args = ap.parse_args(argv)

    ui = theme["ui"]
    root = os.path.abspath(args.path)
    if not os.path.exists(root):
        print("  " + fmt(f"Path not found: {root}", ui["error"], True))
        return 1

    header(f"Offline Secret & Misconfig Scanner ({root})", theme)
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    max_b = max(1, args.max_kb) * 1024
    findings = []
    scanned = 0

    def scan_file(fp: str):
        nonlocal scanned
        try:
            st = os.stat(fp)
            if st.st_size > max_b or st.st_size == 0:
                return
            with open(fp, "rb") as f:
                raw = f.read()
            if b"\x00" in raw[:4096]:
                return
            scanned += 1
            text = raw.decode("utf-8", errors="replace")
            for ln_no, line in enumerate(text.splitlines(), 1):
                for label, rx in _SECRET_RULES:
                    m = rx.search(line)
                    if m:
                        findings.append((fp, ln_no, label, _mask_secret(m.group(0))))
        except OSError:
            return

    if os.path.isfile(root):
        scan_file(root)
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs and not os.path.islink(os.path.join(dirpath, d))]
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                if not os.path.islink(fp):
                    scan_file(fp)

    print(f"  {fmt('Files Scanned:', ui['muted'])} {scanned}   {fmt('Findings:', ui['muted'])} {len(findings)}")
    print()
    if not findings:
        print("  " + fmt("✓ Zero leaked secrets, private keys, or wildcard binds detected.", ui["success"], True))
    else:
        for fp, ln_no, label, sample in findings[:40]:
            rel = os.path.relpath(fp, root) if os.path.isdir(root) else os.path.basename(fp)
            print(f"  {fmt('[!]', ui['warning'], True)} {fmt(label.ljust(23), ui['accent'])} {fmt(f'{rel}:{ln_no}', ui['text'])}  ({fmt(sample, ui['muted'])})")
        if len(findings) > 40:
            print("  " + fmt(f"... and {len(findings) - 40} more findings.", ui["muted"]))
    print()
    return 0


# ── 7. IDN Homograph Spoof Detector (idncheck) ────────────────────────────────

def cmd_idncheck(argv: list[str], theme: dict) -> int:
    ap = argparse.ArgumentParser(prog="idncheck", description="Defensive IDN / Punycode mixed-script phishing spoof detector")
    ap.add_argument("target", help="Domain name or URL to analyze")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    raw = args.target.strip()
    if "://" in raw:
        host = urllib.parse.urlparse(raw).hostname or raw
    else:
        host = raw.split("/")[0].split(":")[0]

    header(f"IDN Homograph Spoof Detector ({host})", theme)
    try:
        puny = host.encode("idna").decode("ascii")
        uni = puny.encode("ascii").decode("idna")
    except Exception as ex:
        print("  " + fmt(f"Invalid IDN domain '{host}': {ex}", ui["error"], True))
        return 1

    scripts = set()
    non_ascii = []
    for ch in uni:
        if ord(ch) > 127:
            uname = unicodedata.name(ch, f"U+{ord(ch):04X}")
            script = uname.split(" ")[0]
            scripts.add(script)
            non_ascii.append((ch, f"U+{ord(ch):04X}", uname))
        elif ch.isalpha():
            scripts.add("LATIN")

    is_mixed = len(scripts) > 1 or bool(non_ascii and puny.startswith("xn--"))
    print(f"  {fmt('Unicode Form:', ui['secondary'], True)}  {uni}")
    print(f"  {fmt('Punycode:', ui['secondary'], True)}      {fmt(puny, ui['accent'], True)}")
    print(f"  {fmt('Scripts:', ui['secondary'], True)}       {', '.join(sorted(scripts)) or 'ASCII'}")
    if is_mixed:
        print()
        print("  " + fmt("[!] WARNING: Non-ASCII / Mixed-Script IDN detected (potential lookalike phishing spoof!)", ui["error"], True))
        for ch, code, uname in non_ascii[:12]:
            print(f"      Char '{ch}'  ({code}) -> {uname}")
    else:
        print()
        print("  " + fmt("✓ Pure ASCII/single-script domain; no IDN homograph mix detected.", ui["success"], True))
    print()
    return 0


# ── 8. Local Steganography Inspector & BMP LSB Tool (stego) ───────────────────

def cmd_stego(argv: list[str], theme: dict) -> int:
    ap = argparse.ArgumentParser(prog="stego", description="Forensic image anomaly inspector & lossless 24-bit BMP LSB demo")
    sub = ap.add_subparsers(dest="action")

    p_ins = sub.add_parser("inspect", help="Audit JPEG/PNG/BMP for trailing payloads or metadata anomalies")
    p_ins.add_argument("file")

    p_hide = sub.add_parser("hide", help="Embed UTF-8 text into 24-bit uncompressed BMP LSBs")
    p_hide.add_argument("src_bmp")
    p_hide.add_argument("dst_bmp")
    p_hide.add_argument("message", nargs="+")

    p_ext = sub.add_parser("extract", help="Extract hidden TXS1 message from 24-bit BMP LSBs")
    p_ext.add_argument("bmp_file")

    args = ap.parse_args(argv)
    ui = theme["ui"]
    action = args.action
    if not action:
        ap.print_help()
        return 1

    if action == "inspect":
        if not os.path.isfile(args.file):
            print("  " + fmt(f"File not found: {args.file}", ui["error"], True))
            return 1
        with open(args.file, "rb") as f:
            data = f.read()
        header(f"Stego & Trailer Forensic Audit ({os.path.basename(args.file)})", theme)
        magic = _detect_magic(data[:16])
        print(f"  {fmt('Format:', ui['secondary'], True)} {magic}   Size: {fmt_bytes(len(data))}")
        anomalies = []
        if data.startswith(b"\xff\xd8\xff"):
            eoi = data.rfind(b"\xff\xd9")
            if eoi != -1 and eoi + 2 < len(data):
                trailing = data[eoi + 2:]
                anomalies.append(f"Trailing {len(trailing)} byte(s) after JPEG EOI (FFD9)! Header: {_detect_magic(trailing[:16])}")
        elif data.startswith(b"\x89PNG\r\n\x1a\n"):
            iend = data.find(b"IEND")
            if iend != -1 and iend + 8 < len(data):
                trailing = data[iend + 8:]
                anomalies.append(f"Trailing {len(trailing)} byte(s) after PNG IEND chunk!")
        elif data.startswith(b"BM") and len(data) >= 30:
            pix_off = struct.unpack_from("<I", data, 10)[0]
            bpp = struct.unpack_from("<H", data, 28)[0]
            if bpp == 24 and pix_off < len(data):
                pix = data[pix_off:]
                bits = "".join(str(b & 1) for b in pix[:48])
                hdr_bytes = bytes(int(bits[i:i + 8], 2) for i in range(0, 48, 8))
                if hdr_bytes.startswith(b"TXS1"):
                    anomalies.append("Detected embedded TXS1 BMP LSB payload (run: stego extract <file>)")
        if not anomalies:
            print("  " + fmt("✓ No trailing EOF payload or TXS1 LSB marker detected.", ui["success"], True))
        else:
            for a in anomalies:
                print("  " + fmt(f"[!] {a}", ui["warning"], True))
        print()
        return 0

    if action == "hide":
        if not os.path.isfile(args.src_bmp):
            print("  " + fmt(f"BMP not found: {args.src_bmp}", ui["error"], True))
            return 1
        with open(args.src_bmp, "rb") as f:
            bmp = bytearray(f.read())
        if not bmp.startswith(b"BM") or len(bmp) < 54 or struct.unpack_from("<H", bmp, 28)[0] != 24:
            print("  " + fmt("Only 24-bit uncompressed BMP files are supported for safe lossless LSB.", ui["error"], True))
            return 1
        pix_off = struct.unpack_from("<I", bmp, 10)[0]
        msg_bytes = " ".join(args.message).encode("utf-8")
        payload = b"TXS1" + struct.pack(">I", len(msg_bytes)) + msg_bytes
        need_bits = len(payload) * 8
        if pix_off + need_bits > len(bmp):
            print("  " + fmt(f"BMP too small ({len(bmp) - pix_off} pixel bytes, need {need_bits}).", ui["error"], True))
            return 1
        bit_idx = 0
        for byte in payload:
            for shift in range(7, -1, -1):
                bit = (byte >> shift) & 1
                bmp[pix_off + bit_idx] = (bmp[pix_off + bit_idx] & 0xFE) | bit
                bit_idx += 1
        with open(args.dst_bmp, "wb") as f:
            f.write(bmp)
        print(f"  {fmt('Embedded', ui['success'], True)} {len(msg_bytes)} byte(s) into {args.dst_bmp}")
        return 0

    if action == "extract":
        if not os.path.isfile(args.bmp_file):
            print("  " + fmt(f"BMP not found: {args.bmp_file}", ui["error"], True))
            return 1
        with open(args.bmp_file, "rb") as f:
            bmp = f.read()
        if not bmp.startswith(b"BM") or len(bmp) < 54:
            print("  " + fmt("Not a valid BMP file.", ui["error"], True))
            return 1
        pix_off = struct.unpack_from("<I", bmp, 10)[0]
        if pix_off + 64 > len(bmp):
            print("  " + fmt("No LSB payload present.", ui["warning"]))
            return 1

        def read_bytes(start_idx: int, count: int) -> bytes:
            out = bytearray()
            for b_i in range(count):
                val = 0
                for k in range(8):
                    val = (val << 1) | (bmp[start_idx + b_i * 8 + k] & 1)
                out.append(val)
            return bytes(out)

        hdr = read_bytes(pix_off, 8)
        if not hdr.startswith(b"TXS1"):
            print("  " + fmt("No TXS1 LSB payload found in this BMP.", ui["warning"]))
            return 1
        msg_len = struct.unpack_from(">I", hdr, 4)[0]
        if pix_off + (8 + msg_len) * 8 > len(bmp):
            print("  " + fmt("Corrupted/truncated LSB length header.", ui["error"], True))
            return 1
        secret_msg = read_bytes(pix_off + 64, msg_len).decode("utf-8", errors="replace")
        print(f"  {fmt('Extracted:', ui['success'], True)} {secret_msg}")
        return 0
    return 1


# ── 9. Safe Local Wordlist & Permutation Generator (wordgen) ──────────────────

_LEET_MAP = str.maketrans({"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"})


def cmd_wordgen(argv: list[str], theme: dict) -> int:
    ap = argparse.ArgumentParser(prog="wordgen", description="Generate bounded local QA/policy wordlists (permutations or charset patterns)")
    ap.add_argument("words", nargs="*", help="Seed words to combine/mutate (omit to use --chars pattern)")
    ap.add_argument("--chars", default="abc123", help="Charset for length combinations (default abc123)")
    ap.add_argument("--min", dest="min_len", type=int, default=2)
    ap.add_argument("--max", dest="max_len", type=int, default=3)
    ap.add_argument("--leet", action="store_true", help="Include leetspeak & capitalized variants for seed words")
    ap.add_argument("-n", "--limit", type=int, default=200, help="Max output lines (hard cap 50000)")
    ap.add_argument("-o", "--out", default="", help="Optional output file path")
    args = ap.parse_args(argv)

    ui = theme["ui"]
    limit = max(1, min(50000, args.limit))
    results = []
    seen = set()

    def push(w: str):
        if w not in seen and len(results) < limit:
            seen.add(w)
            results.append(w)

    if args.words:
        variants = []
        for w in args.words:
            vs = [w, w.lower(), w.capitalize(), w.upper()]
            if args.leet:
                vs.append(w.lower().translate(_LEET_MAP))
                vs.append(w.capitalize().translate(_LEET_MAP))
            variants.append(list(dict.fromkeys(vs)))
        for vlist in variants:
            for item in vlist:
                push(item)
        for a, b in itertools.permutations(args.words, min(2, len(args.words))):
            for sep in ("", "_", "-", "@"):
                push(f"{a}{sep}{b}")
        for base in list(results):
            for sfx in ("1", "123", "2026", "!"):
                push(base + sfx)
    else:
        lo = max(1, min(8, args.min_len))
        hi = max(lo, min(8, args.max_len))
        charset = "".join(dict.fromkeys(args.chars))
        for length in range(lo, hi + 1):
            for tup in itertools.product(charset, repeat=length):
                push("".join(tup))
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break

    if args.out:
        out_p = Path(args.out).expanduser().resolve()
        out_p.write_text("\n".join(results) + "\n", encoding="utf-8")
        print(f"  {fmt('Generated', ui['success'], True)} {len(results)} word(s) -> {out_p}")
    else:
        for r in results:
            print(r)
    return 0


# ── Dispatcher ────────────────────────────────────────────────────────────────

COMMANDS = {
    "secaudit": cmd_secaudit,
    "peinspect": cmd_peinspect,
    "exifinfo": cmd_exifinfo,
    "hexview": cmd_hexview,
    "hashid": cmd_hashid,
    "secretaudit": cmd_secretaudit,
    "idncheck": cmd_idncheck,
    "stego": cmd_stego,
    "wordgen": cmd_wordgen,
}


def main():
    enable_vt()
    theme = load_theme()
    argv = sys.argv[1:]
    if not argv:
        print("  Available sec_extra commands: " + ", ".join(sorted(COMMANDS)))
        return 1
    cmd = argv[0].lstrip("-").lower()
    fn = COMMANDS.get(cmd)
    if not fn:
        print(f"  Unknown command '{argv[0]}'. Available: {', '.join(sorted(COMMANDS))}")
        return 1
    return fn(argv[1:], theme) or 0


if __name__ == "__main__":
    sys.exit(main())
