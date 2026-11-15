#!/usr/bin/env python3
"""TricksXTech Additional Cryptography, Encoding & Hashing Utilities."""

from __future__ import annotations

import argparse
import base64
import codecs
import getpass
import hashlib
import hmac
import math
import os
import secrets
import sys
import zlib

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, fmt_bytes, header, load_theme

BCRYPT_ALPHA = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
BCRYPT_INDEX = {ch: idx for idx, ch in enumerate(BCRYPT_ALPHA)}


def _read_stdin_if_piped() -> str:
    if sys.stdin is not None and not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _pi_frac_hex_words(count: int = 18 + 1024) -> tuple[list[int], list[list[int]]]:
    """Generate exact Blowfish initial P-array and S-boxes from binary fractional bits of pi - 3."""
    extra_bits = 128
    shift = count * 32 + extra_bits

    def arccot_fixed(x: int) -> int:
        x2 = x * x
        term = (1 << shift) // x
        total = term
        n = 3
        sign = -1
        while term:
            term //= x2
            delta = term // n
            if not delta:
                break
            total += sign * delta
            sign = -sign
            n += 2
        return total

    pi_fixed = (16 * arccot_fixed(5) - 4 * arccot_fixed(239)) - (3 << shift)
    frac = (pi_fixed >> extra_bits) & ((1 << (count * 32)) - 1)
    words = [(frac >> (32 * (count - 1 - i))) & 0xFFFFFFFF for i in range(count)]
    p = words[:18]
    s = [
        words[18:274],
        words[274:530],
        words[530:786],
        words[786:1042],
    ]
    return p, s


def _bcrypt_encode(data: bytes) -> str:
    out: list[str] = []
    i = 0
    n = len(data)
    while i < n:
        c1 = data[i]
        i += 1
        out.append(BCRYPT_ALPHA[(c1 >> 2) & 0x3F])
        c1 = (c1 & 0x03) << 4
        if i >= n:
            out.append(BCRYPT_ALPHA[c1])
            break
        c2 = data[i]
        i += 1
        c1 |= (c2 >> 4) & 0x0F
        out.append(BCRYPT_ALPHA[c1])
        c1 = (c2 & 0x0F) << 2
        if i >= n:
            out.append(BCRYPT_ALPHA[c1])
            break
        c2 = data[i]
        i += 1
        c1 |= (c2 >> 6) & 0x03
        out.append(BCRYPT_ALPHA[c1])
        out.append(BCRYPT_ALPHA[c2 & 0x3F])
    return "".join(out)


def _bcrypt_decode(text: str, length: int) -> bytes:
    res = bytearray()
    chars = text
    idx = 0
    while idx < len(chars) and len(res) < length:
        c1 = BCRYPT_INDEX[chars[idx]]
        c2 = BCRYPT_INDEX[chars[idx + 1]]
        idx += 2
        res.append(((c1 << 2) | (c2 >> 4)) & 0xFF)
        if len(res) >= length or idx >= len(chars):
            break
        c3 = BCRYPT_INDEX[chars[idx]]
        idx += 1
        res.append((((c2 & 0x0F) << 4) | (c3 >> 2)) & 0xFF)
        if len(res) >= length or idx >= len(chars):
            break
        c4 = BCRYPT_INDEX[chars[idx]]
        idx += 1
        res.append((((c3 & 0x03) << 6) | c4) & 0xFF)
    return bytes(res)


_PI_CACHE: tuple[list[int], list[list[int]]] | None = None


def _bcrypt_hash_raw(password: bytes, salt: bytes, cost: int) -> str:
    global _PI_CACHE
    if _PI_CACHE is None:
        _PI_CACHE = _pi_frac_hex_words()
    p_init, s_init = _PI_CACHE
    p = list(p_init)
    s0 = list(s_init[0])
    s1 = list(s_init[1])
    s2 = list(s_init[2])
    s3 = list(s_init[3])

    pw = (password[:72] if len(password) > 72 else password) + b"\x00"
    if len(pw) > 72:
        pw = pw[:72]
    pw_len = len(pw)
    salt_len = len(salt)

    def enc_block(xl: int, xr: int) -> tuple[int, int]:
        for r in range(16):
            xl ^= p[r]
            a = (xl >> 24) & 0xFF
            b = (xl >> 16) & 0xFF
            c = (xl >> 8) & 0xFF
            d = xl & 0xFF
            xr ^= (((s0[a] + s1[b]) & 0xFFFFFFFF) ^ s2[c]) + s3[d] & 0xFFFFFFFF
            xl, xr = xr, xl
        xl, xr = xr, xl
        xr ^= p[16]
        xl ^= p[17]
        return xl, xr

    def key_stream(key_bytes: bytes, klen: int) -> None:
        pos = 0
        for i in range(18):
            w = 0
            for _ in range(4):
                w = ((w << 8) | key_bytes[pos]) & 0xFFFFFFFF
                pos = (pos + 1) % klen
            p[i] ^= w

    def eks_round(data: bytes, dlen: int, key: bytes, klen: int) -> None:
        key_stream(key, klen)
        dl = dr = 0
        dpos = 0

        def next_word() -> int:
            nonlocal dpos
            w = 0
            for _ in range(4):
                w = ((w << 8) | data[dpos]) & 0xFFFFFFFF
                dpos = (dpos + 1) % dlen
            return w

        for i in range(0, 18, 2):
            dl ^= next_word()
            dr ^= next_word()
            dl, dr = enc_block(dl, dr)
            p[i], p[i + 1] = dl, dr
        for box in (s0, s1, s2, s3):
            for i in range(0, 256, 2):
                dl ^= next_word()
                dr ^= next_word()
                dl, dr = enc_block(dl, dr)
                box[i], box[i + 1] = dl, dr

    # EksBlowfishSetup
    eks_round(salt, salt_len, pw, pw_len)
    rounds = 1 << cost
    for _ in range(rounds):
        key_stream(pw, pw_len)
        dl = dr = 0
        for i in range(0, 18, 2):
            dl, dr = enc_block(dl, dr)
            p[i], p[i + 1] = dl, dr
        for box in (s0, s1, s2, s3):
            for i in range(0, 256, 2):
                dl, dr = enc_block(dl, dr)
                box[i], box[i + 1] = dl, dr

        key_stream(salt, salt_len)
        dl = dr = 0
        for i in range(0, 18, 2):
            dl, dr = enc_block(dl, dr)
            p[i], p[i + 1] = dl, dr
        for box in (s0, s1, s2, s3):
            for i in range(0, 256, 2):
                dl, dr = enc_block(dl, dr)
                box[i], box[i + 1] = dl, dr

    ctext = bytearray(b"OrpheanBeholderScryDoubt")
    cwords = [int.from_bytes(ctext[i : i + 4], "big") for i in range(0, 24, 4)]
    for _ in range(64):
        for j in range(0, 6, 2):
            cwords[j], cwords[j + 1] = enc_block(cwords[j], cwords[j + 1])
    out_bytes = b"".join(w.to_bytes(4, "big") for w in cwords)[:23]
    return _bcrypt_encode(out_bytes)


def verify_bcrypt(password: str, full_hash: str) -> bool:
    if not full_hash or len(full_hash) < 59 or not full_hash.startswith(("$2a$", "$2b$", "$2y$")):
        raise ValueError("Expected OpenBSD bcrypt hash starting with $2a$, $2b$, or $2y$")
    parts = full_hash.split("$")
    if len(parts) != 4 or len(parts[3]) < 53:
        raise ValueError("Invalid bcrypt hash format")
    cost = int(parts[2])
    if cost < 4 or cost > 16:
        raise ValueError(f"Unsupported bcrypt cost factor: {cost}")
    salt_b64 = parts[3][:22]
    salt_raw = _bcrypt_decode(salt_b64, 16)
    digest = _bcrypt_hash_raw(password.encode("utf-8"), salt_raw, cost)
    expected_digest = parts[3][22:53]
    return hmac.compare_digest(digest, expected_digest)


def cmd_bcryptcheck(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="bcryptcheck", description="Verify a plaintext password against a $2a$/$2b$/$2y$ bcrypt hash")
    p.add_argument("arg1", help="Bcrypt hash ($2a$/$2b$/$2y$...) OR plaintext candidate")
    p.add_argument("arg2", nargs="?", default="", help="Plaintext candidate OR bcrypt hash")
    args = p.parse_args(argv)

    if args.arg2 and args.arg2.startswith("$2") and not args.arg1.startswith("$2"):
        hash_str, pw = args.arg2, args.arg1
    else:
        hash_str = args.arg1
        pw = args.arg2 if args.arg2 else getpass.getpass("  Enter candidate password: ")

    header("Bcrypt Hash Verifier (OpenBSD EksBlowfish)", theme)
    try:
        matched = verify_bcrypt(pw, hash_str)
        if matched:
            print(f"  {fmt('[MATCH]', ui['success'], True)} {fmt('Password matches the bcrypt hash.', ui['text'])}")
        else:
            print(f"  {fmt('[NO MATCH]', ui['error'], True)} {fmt('Password does NOT match this bcrypt hash.', ui['text'])}")
            print()
            sys.exit(1)
    except Exception as exc:
        print(fmt(f"  Verification error: {exc}", ui["warning"]))
        print()
        sys.exit(1)
    print()


def cmd_hmac256(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="hmac256", description="Compute HMAC-SHA256 signature for text or file")
    p.add_argument("key", help="Secret key string")
    p.add_argument("target", nargs="?", default="", help="Message text or --file <path>")
    p.add_argument("-f", "--file", help="Read payload bytes from file instead of string")
    args = p.parse_args(argv)

    if args.file:
        with open(args.file, "rb") as f:
            data = f.read()
        src = args.file
    else:
        msg = args.target or _read_stdin_if_piped().rstrip("\r\n") or input("  Enter message: ")
        data = msg.encode("utf-8")
        src = f"{len(data)} UTF-8 bytes"

    mac = hmac.new(args.key.encode("utf-8"), data, hashlib.sha256)
    header("HMAC-SHA256 Signature Calculator", theme)
    print(f"  {fmt('Input:'.ljust(12), ui['muted'])} {fmt(src, ui['text'])}")
    print(f"  {fmt('Hex:'.ljust(12), ui['muted'])} {fmt(mac.hexdigest(), ui['primary'], True)}")
    print(f"  {fmt('Base64:'.ljust(12), ui['muted'])} {fmt(base64.b64encode(mac.digest()).decode('ascii'), ui['accent'])}")
    print()


def cmd_rot13(argv: list[str], theme: dict) -> None:
    p = argparse.ArgumentParser(prog="rot13", description="ROT13 Caesar cipher encoder/decoder")
    p.add_argument("text", nargs="*", help="Input string (or pipe stdin)")
    args = p.parse_args(argv)
    txt = " ".join(args.text) if args.text else (_read_stdin_if_piped() or input("  Enter text: "))
    print(codecs.encode(txt, "rot_13"))


def cmd_bin2txt(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="bin2txt", description="Convert binary bitstrings (01000001...) <-> UTF-8 text")
    p.add_argument("-e", "--encode", action="store_true", help="Encode text to binary bits (auto-detects by default)")
    p.add_argument("data", nargs="*", help="Binary bits or text")
    args = p.parse_args(argv)

    raw = " ".join(args.data).strip() if args.data else (_read_stdin_if_piped().strip() or input("  Enter binary or text: ").strip())
    if not raw:
        return
    clean_bits = "".join(ch for ch in raw if ch in "01")
    looks_binary = (not args.encode) and clean_bits and all(ch in "01 \t\r\n" for ch in raw) and len(clean_bits) % 8 == 0
    if looks_binary:
        b = bytes(int(clean_bits[i : i + 8], 2) for i in range(0, len(clean_bits), 8))
        print(fmt(b.decode("utf-8", errors="replace"), ui["primary"], True))
    else:
        bits = " ".join(f"{byte:08b}" for byte in raw.encode("utf-8"))
        print(fmt(bits, ui["accent"], True))


def cmd_ascii(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="ascii", description="Display Decimal, Hex, Octal, Binary & Unicode values for characters")
    p.add_argument("text", nargs="*", help="Input string")
    args = p.parse_args(argv)
    txt = " ".join(args.text) if args.text else (_read_stdin_if_piped().rstrip("\r\n") or input("  Enter text: "))

    header("ASCII & Character Inspector", theme)
    print(fmt(f"  {'CHAR':<7} {'DEC':>6} {'HEX':>7} {'OCT':>7} {'BINARY'}", ui["muted"], True))
    print(fmt("  " + "─" * 44, ui["border"]))
    for ch in txt[:64]:
        code = ord(ch)
        glyph = repr(ch) if code < 32 or code == 127 else f"'{ch}'"
        print(f"  {fmt(glyph.ljust(7), ui['primary'], True)} {fmt(str(code).rjust(6), ui['text'])} {fmt(f'0x{code:02x}'.rjust(7), ui['accent'])} {fmt(f'0o{code:03o}'.rjust(7), ui['muted'])} {fmt(f'{code:08b}', ui['secondary'])}")
    print()


def cmd_tokengen(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="tokengen", description="Generate cryptographic Hex or URL-safe session/API tokens")
    p.add_argument("nbytes", nargs="?", type=int, default=32, help="Random entropy bytes (default 32 -> 64 hex chars)")
    p.add_argument("-n", "--count", type=int, default=3, help="Number of tokens (default 3)")
    p.add_argument("--urlsafe", "--url", action="store_true", help="Output URL-safe Base64 instead of Hex")
    args = p.parse_args(argv)

    nb = max(8, min(128, args.nbytes))
    cnt = max(1, min(30, args.count))
    header(f"Cryptographic Token Generator ({nb * 8}-bit)", theme)
    for _ in range(cnt):
        tok = secrets.token_urlsafe(nb) if args.urlsafe else secrets.token_hex(nb)
        print(f"  {fmt(tok, ui['accent'], True)}")
    print()


def cmd_fencrypt(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="fencrypt", description="AES-256-GCM authenticated file encryptor/decryptor (PBKDF2 600k)")
    p.add_argument("mode", choices=("enc", "dec"), help="enc (encrypt) | dec (decrypt)")
    p.add_argument("file", help="Input file path")
    p.add_argument("-o", "--out", help="Output path (defaults to <file>.txenc or stripped .txenc)")
    p.add_argument("-p", "--password", default="", help="Password (omit to prompt interactively)")
    args = p.parse_args(argv)

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    if not os.path.isfile(args.file):
        print(fmt(f"  File not found: {args.file}", ui["error"]))
        sys.exit(1)

    header(f"AES-256-GCM File {'Encryptor' if args.mode == 'enc' else 'Decryptor'}", theme)
    pw = args.password or getpass.getpass("  Enter password: ")
    if args.mode == "enc":
        if not args.password:
            pw2 = getpass.getpass("  Confirm password: ")
            if pw != pw2:
                print(fmt("  Passwords do not match.", ui["error"]))
                sys.exit(1)
        salt = os.urandom(16)
        nonce = os.urandom(12)
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
        key = kdf.derive(pw.encode("utf-8"))
        with open(args.file, "rb") as f:
            pt = f.read()
        ct = AESGCM(key).encrypt(nonce, pt, b"TX-AESGCM-v1")
        out_path = args.out or (args.file + ".txenc")
        with open(out_path, "wb") as f:
            f.write(b"TXE1" + salt + nonce + ct)
        print(f"  {fmt('Encrypted:', ui['success'], True)} {out_path} ({fmt_bytes(os.path.getsize(out_path))})")
    else:
        with open(args.file, "rb") as f:
            blob = f.read()
        if len(blob) < 32 or blob[:4] != b"TXE1":
            print(fmt("  Invalid or unsupported encrypted file header.", ui["error"]))
            return
        salt, nonce, ct = blob[4:20], blob[20:32], blob[32:]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
        key = kdf.derive(pw.encode("utf-8"))
        try:
            pt = AESGCM(key).decrypt(nonce, ct, b"TX-AESGCM-v1")
        except Exception:
            print(fmt("  Decryption failed (wrong password or corrupted file).", ui["error"], True))
            return
        out_path = args.out or (args.file[:-6] if args.file.endswith(".txenc") else args.file + ".dec")
        with open(out_path, "wb") as f:
            f.write(pt)
        print(f"  {fmt('Decrypted:', ui['success'], True)} {out_path} ({fmt_bytes(len(pt))})")
    print()


def _apr1_md5(password: str, salt: str) -> str:
    """Standard Apache APR1 MD5 crypt implementation."""
    pw = password.encode("utf-8")
    slt = salt[:8].encode("ascii")
    itoa64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    ctx = hashlib.md5(pw + b"$apr1$" + slt)
    alt = hashlib.md5(pw + slt + pw).digest()
    i = len(pw)
    while i > 0:
        ctx.update(alt[: min(16, i)])
        i -= 16
    i = len(pw)
    while i > 0:
        ctx.update(b"\x00" if (i & 1) else pw[:1])
        i >>= 1
    dig = ctx.digest()
    for r in range(1000):
        c2 = hashlib.md5()
        c2.update(pw if (r & 1) else dig)
        if r % 3:
            c2.update(slt)
        if r % 7:
            c2.update(pw)
        c2.update(dig if (r & 1) else pw)
        dig = c2.digest()

    def enc24(b0: int, b1: int, b2: int, n: int) -> str:
        v = (b0 << 16) | (b1 << 8) | b2
        s = []
        for _ in range(n):
            s.append(itoa64[v & 0x3F])
            v >>= 6
        return "".join(s)

    out = (
        enc24(dig[0], dig[6], dig[12], 4)
        + enc24(dig[1], dig[7], dig[13], 4)
        + enc24(dig[2], dig[8], dig[14], 4)
        + enc24(dig[3], dig[9], dig[15], 4)
        + enc24(dig[4], dig[10], dig[5], 4)
        + enc24(0, 0, dig[11], 2)
    )
    return f"$apr1${salt[:8]}${out}"


def cmd_htpasswd(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="htpasswd", description="Generate Apache .htpasswd entries ($apr1$ MD5 / {SHA})")
    p.add_argument("username", help="Username")
    p.add_argument("password", nargs="?", default="", help="Password (omit to prompt hidden)")
    p.add_argument("--sha", action="store_true", help="Output {SHA} format instead of $apr1$")
    args = p.parse_args(argv)

    pw = args.password if args.password else getpass.getpass("  Enter password: ")
    if args.sha:
        entry = f"{args.username}:{{SHA}}{base64.b64encode(hashlib.sha1(pw.encode('utf-8')).digest()).decode('ascii')}"
    else:
        salt = "".join(secrets.choice("./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz") for _ in range(8))
        entry = f"{args.username}:{_apr1_md5(pw, salt)}"
    print(fmt(entry, ui["primary"], True))


def cmd_entropy(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="entropy", description="Calculate Shannon entropy & charset strength of a string")
    p.add_argument("text", nargs="*", help="String to measure (omit to prompt safely)")
    args = p.parse_args(argv)

    txt = " ".join(args.text) if args.text else getpass.getpass("  Enter secret/string (hidden): ")
    if not txt:
        return
    counts: dict[str, int] = {}
    for ch in txt:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(txt)
    shannon_per_char = -sum((c / n) * math.log2(c / n) for c in counts.values())
    shannon_total = shannon_per_char * n

    pool = 0
    if any(c.islower() for c in txt):
        pool += 26
    if any(c.isupper() for c in txt):
        pool += 26
    if any(c.isdigit() for c in txt):
        pool += 10
    if any(not c.isalnum() for c in txt):
        pool += 33
    charset_bits = n * math.log2(max(1, pool))

    tier = (
        ("STRONG (High Entropy)", ui["success"]) if charset_bits >= 80 else
        ("MODERATE", ui["accent"]) if charset_bits >= 50 else
        ("WEAK", ui["error"])
    )
    header("String Entropy Analyzer", theme)
    print(f"  {fmt('Length:'.ljust(18), ui['muted'])} {n} chars  (Unique: {len(counts)})")
    print(f"  {fmt('Shannon Bits:'.ljust(18), ui['muted'])} {fmt(f'{shannon_total:.1f} bits', ui['primary'], True)}  ({shannon_per_char:.2f} bits/char)")
    print(f"  {fmt('Charset Bits:'.ljust(18), ui['muted'])} {fmt(f'{charset_bits:.1f} bits', ui['accent'], True)}  (alphabet size ~{pool})")
    print(f"  {fmt('Rating:'.ljust(18), ui['muted'])} {fmt(tier[0], tier[1], True)}")
    print()


def cmd_crc32(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="crc32", description="Compute fast CRC32 checksum of a file or string")
    p.add_argument("target", help="File path or string (--text to force string)")
    p.add_argument("--text", action="store_true", help="Treat argument literally as text")
    args = p.parse_args(argv)

    crc = 0
    if not args.text and os.path.isfile(args.target):
        with open(args.target, "rb") as f:
            while True:
                b = f.read(262144)
                if not b:
                    break
                crc = zlib.crc32(b, crc)
        src = args.target
    else:
        crc = zlib.crc32(args.target.encode("utf-8"))
        src = "string"
    hx = f"{crc & 0xFFFFFFFF:08x}"
    print(f"  {fmt('CRC32', ui['secondary'], True)} ({src}): {fmt(hx, ui['primary'], True)}  ({crc & 0xFFFFFFFF})")


def cmd_rsagen(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="rsagen", description="Generate local RSA public/private PEM keypair")
    p.add_argument("-b", "--bits", type=int, default=2048, choices=(2048, 3072, 4096), help="Key size (default 2048)")
    p.add_argument("-o", "--prefix", default="id_rsa_local", help="Output filename prefix (creates <prefix>.pem & <prefix>.pub.pem)")
    args = p.parse_args(argv)

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    priv_path = os.path.abspath(args.prefix + ".pem")
    pub_path = os.path.abspath(args.prefix + ".pub.pem")
    if os.path.exists(priv_path) or os.path.exists(pub_path):
        print(fmt(f"  Refused: output key files already exist ({args.prefix}.*).", ui["warning"]))
        return

    header(f"RSA-{args.bits} Keypair Generator", theme)
    key = rsa.generate_private_key(public_exponent=65537, key_size=args.bits)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(priv_path, "wb") as f:
        f.write(priv_pem)
    with open(pub_path, "wb") as f:
        f.write(pub_pem)
    print(f"  {fmt('Private Key:', ui['warning'], True)} {priv_path}")
    print(f"  {fmt('Public Key: ', ui['success'], True)} {pub_path}")
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
        print("crypto_extra.py subcommands: --bcryptcheck, --hmac256, --rot13, --bin2txt, --ascii, --tokengen, --fencrypt, --htpasswd, --entropy, --crc32, --rsagen")
        return
    dispatch = {
        "--bcryptcheck": cmd_bcryptcheck,
        "--hmac256": cmd_hmac256,
        "--rot13": cmd_rot13,
        "--bin2txt": cmd_bin2txt,
        "--ascii": cmd_ascii,
        "--tokengen": cmd_tokengen,
        "--fencrypt": cmd_fencrypt,
        "--htpasswd": cmd_htpasswd,
        "--entropy": cmd_entropy,
        "--crc32": cmd_crc32,
        "--rsagen": cmd_rsagen,
    }
    fn = dispatch.get(args[0])
    if fn:
        fn(args[1:], theme)
    else:
        print(f"Unknown crypto_extra subcommand: {args[0]}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
