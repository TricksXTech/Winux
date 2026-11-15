#!/usr/bin/env python3
"""TricksXTech Passive Infrastructure & Local LAN Diagnostics (CT Logs, Passive WebTech, ARP/LAN, Dev Port Check)."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
import ipaddress
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, header, load_theme
from vpn_tool import ensure_vpn_for_tool

USER_AGENT = "TricksXTech-Inspector/1.0 (+passive-diagnostics)"
MAX_PORTCHECK_PORTS = 25

COMMON_DEV_PORTS: list[tuple[int, str]] = [
    (22, "SSH"),
    (53, "DNS"),
    (80, "HTTP"),
    (443, "HTTPS"),
    (3000, "Dev HTTP"),
    (3306, "MySQL"),
    (5000, "Flask/Dev"),
    (5432, "PostgreSQL"),
    (6379, "Redis"),
    (8000, "HTTP Alt"),
    (8080, "HTTP Proxy"),
    (8443, "HTTPS Alt"),
    (27017, "MongoDB"),
]

COMMON_OUI_PREFIXES: dict[str, str] = {
    "00:50:56": "VMware",
    "00:0c:29": "VMware",
    "00:15:5d": "Microsoft Hyper-V",
    "08:00:27": "VirtualBox",
    "b8:27:eb": "Raspberry Pi",
    "dc:a6:32": "Raspberry Pi",
    "e4:5f:01": "Raspberry Pi",
    "00:1a:2b": "Cisco",
    "f4:ec:38": "TP-Link",
    "50:c7:bf": "TP-Link",
    "c0:25:e9": "TP-Link",
    "2c:f0:5d": "Micro-Star / MSI",
    "3c:7c:3f": "ASUSTek",
    "04:d4:c4": "ASUSTek",
    "a4:83:e7": "Apple",
    "f0:18:98": "Apple",
    "3c:22:fb": "Apple",
    "00:e0:4c": "Realtek",
    "d8:bb:c1": "Micro-Star / Realtek",
    "34:97:f6": "Intel",
    "a4:4c:c8": "Dell",
    "b4:2e:99": "Giga-Byte",
    "24:0a:c4": "Espressif IoT",
    "30:ae:a4": "Espressif IoT",
    "7c:9e:bd": "Espressif IoT",
}


def _http_get_json(url: str, timeout: float = 10.0) -> tuple[object | None, str | None]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:
        return None, str(exc)


def _clean_host(raw: str) -> str:
    s = raw.strip()
    if "://" in s:
        s = urllib.parse.urlparse(s).hostname or s
    else:
        s = s.split("/")[0].strip()
        if ":" in s and not s.startswith("["):
            try:
                ipaddress.ip_address(s)
            except ValueError:
                s = s.split(":")[0]
    return s.strip("[]").lower().rstrip(".")


def _is_local_or_private(host: str) -> bool:
    h = host.strip().lower().rstrip(".")
    if h in ("localhost", "::1") or h.endswith(".local"):
        return True
    try:
        ip_obj = ipaddress.ip_address(h)
        return bool(ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local)
    except ValueError:
        return False


def cmd_subdomains(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(
        prog="subdomains",
        description="Passive Certificate Transparency (CT Log) subdomain lookup",
    )
    p.add_argument("domain", nargs="?", help="Target domain (e.g., example.com)")
    p.add_argument("--resolve", action="store_true", help="Also resolve top 25 discovered hosts via DNS")
    p.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN connection")
    args = p.parse_args(argv)

    raw_dom = args.domain
    if not raw_dom:
        try:
            raw_dom = input("  Enter domain (e.g. github.com): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
    domain = _clean_host(raw_dom)
    if not domain or "." not in domain:
        print(fmt("  Please provide a valid domain name (e.g. subdomains github.com).", ui["warning"]))
        return

    header(f"Passive CT-Log Subdomains // {domain}", theme)
    ensure_vpn_for_tool("subdomains", theme, skip_vpn=args.no_vpn)
    print(f"  {fmt('Source:', ui['muted'])} {fmt('Certificate Transparency (crt.sh / certspotter, strictly passive)', ui['text'])}")

    found_names: set[str] = set()
    cert_count = 0
    src_used = "crt.sh"

    data, err = _http_get_json(f"https://crt.sh/?q=%25.{urllib.parse.quote(domain)}&output=json", timeout=12.0)
    if isinstance(data, list):
        cert_count = len(data)
        for row in data:
            if not isinstance(row, dict):
                continue
            nv = str(row.get("name_value", ""))
            for line in nv.splitlines():
                nm = line.strip().lower().rstrip(".")
                if nm == domain or nm.endswith("." + domain):
                    found_names.add(nm)
    else:
        src_used = "certspotter"
        q_url = f"https://api.certspotter.com/v1/issuances?domain={urllib.parse.quote(domain)}&include_subdomains=true&expand=dns_names"
        data2, err2 = _http_get_json(q_url, timeout=10.0)
        if isinstance(data2, list):
            cert_count = len(data2)
            for item in data2:
                for nm in (item.get("dns_names") or []):
                    nm_clean = str(nm).strip().lower().rstrip(".")
                    if nm_clean == domain or nm_clean.endswith("." + domain):
                        found_names.add(nm_clean)
        else:
            print(f"  {fmt('CT Query Error:', ui['warning'], True)} {fmt(f'crt.sh ({err}) | certspotter ({err2})', ui['muted'])}")
            print()
            return

    sorted_names = sorted(found_names, key=lambda n: (n.startswith("*."), len(n), n))
    print(f"  {fmt('Certificates Scanned:', ui['muted'])} {fmt(str(cert_count), ui['accent'], True)}   {fmt('Unique Names:', ui['muted'])} {fmt(str(len(sorted_names)), ui['primary'], True)}   {fmt('Provider:', ui['muted'])} {fmt(src_used, ui['muted'])}")
    print(fmt("  " + "─" * 74, ui["border"]))

    if not sorted_names:
        print("  " + fmt("No CT log entries found for this domain.", ui["muted"]))
        print()
        return

    resolved_ips: dict[str, str] = {}
    if args.resolve:
        concrete = [h for h in sorted_names if not h.startswith("*.")][:25]
        def _res(host: str) -> tuple[str, str]:
            try:
                infos = socket.getaddrinfo(host, None)
                ips = sorted({i[4][0] for i in infos})
                return host, ", ".join(ips[:2])
            except Exception:
                return host, "-"
        with ThreadPoolExecutor(max_workers=8) as ex:
            for host, ip_txt in ex.map(_res, concrete):
                resolved_ips[host] = ip_txt

    for nm in sorted_names[:50]:
        c = ui["warning"] if nm.startswith("*.") else ui["text"]
        if args.resolve and nm in resolved_ips:
            print(f"  {fmt(nm.ljust(42), c)}  {fmt(resolved_ips[nm], ui['accent'])}")
        else:
            print(f"  {fmt('•', ui['accent'])} {fmt(nm, c)}")

    if len(sorted_names) > 50:
        print(fmt(f"  ... and {len(sorted_names) - 50} more CT names.", ui["muted"]))
    print()


class _MetaHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.generator: str = ""
        self.script_srcs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        amap = {k.lower(): (v or "") for k, v in attrs}
        if t == "title":
            self.in_title = True
        elif t == "meta" and amap.get("name", "").lower() == "generator" and not self.generator:
            self.generator = amap.get("content", "").strip()
        elif t == "script" and amap.get("src"):
            self.script_srcs.append(amap["src"])

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def cmd_webtech(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(
        prog="webtech",
        description="Passive single-request HTTP header & HTML technology fingerprinter",
    )
    p.add_argument("target", nargs="?", help="URL or domain (e.g. https://github.com)")
    p.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN connection")
    args = p.parse_args(argv)

    raw = args.target
    if not raw:
        try:
            raw = input("  Enter URL or domain: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
    if not raw:
        return
    url = raw if "://" in raw else f"https://{raw}"
    host = _clean_host(url)

    header(f"Passive Web Tech Fingerprinter // {host}", theme)
    if not _is_local_or_private(host):
        ensure_vpn_for_tool("webtech", theme, skip_vpn=args.no_vpn)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    status_str = ""
    final_url = url
    hdrs: list[tuple[str, str]] = []
    body = ""
    tls_note = ""

    try:
        with urllib.request.urlopen(req, timeout=7.0) as resp:
            status_str = f"{resp.status} {resp.reason}"
            final_url = resp.geturl()
            hdrs = list(resp.headers.items())
            body = resp.read(131072).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_str = f"{exc.code} {exc.reason}"
        final_url = exc.geturl() or url
        hdrs = list(exc.headers.items()) if exc.headers else []
        try:
            body = exc.read(65536).decode("utf-8", errors="replace")
        except Exception:
            body = ""
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            print(f"  {fmt('TLS Verification:', ui['warning'], True)} {fmt(str(exc.reason), ui['warning'])}")
        else:
            print(f"  {fmt('Request Failed:', ui['error'], True)} {fmt(str(exc.reason), ui['warning'])}")
        print()
        return
    except Exception as exc:
        print(f"  {fmt('Request Failed:', ui['error'], True)} {fmt(str(exc), ui['warning'])}")
        print()
        return

    hmap = {k.lower(): v for k, v in hdrs}
    print(f"  {fmt('Final URL:'.ljust(17), ui['muted'])} {fmt(final_url, ui['accent'])}")
    print(f"  {fmt('HTTP Status:'.ljust(17), ui['muted'])} {fmt(status_str, ui['success'], True)}")
    if tls_note:
        print(f"  {fmt('TLS Note:'.ljust(17), ui['muted'])} {fmt(tls_note, ui['warning'])}")

    server_v = hmap.get("server", "hidden / not disclosed")
    powered_v = hmap.get("x-powered-by", "")
    print(f"  {fmt('Server Header:'.ljust(17), ui['muted'])} {fmt(server_v, ui['primary'], True)}")
    if powered_v:
        print(f"  {fmt('X-Powered-By:'.ljust(17), ui['muted'])} {fmt(powered_v, ui['secondary'], True)}")

    parser = _MetaHTMLParser()
    try:
        parser.feed(body)
    except Exception:
        pass
    title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip()
    if title:
        short_title = (title[:66] + "...") if len(title) > 69 else title
        print(f"  {fmt('Page Title:'.ljust(17), ui['muted'])} {fmt(short_title, ui['text'])}")

    tech_tags: list[str] = []
    if "cf-ray" in hmap or "cloudflare" in server_v.lower():
        tech_tags.append("Cloudflare CDN/WAF")
    if "x-vercel-id" in hmap or "vercel" in server_v.lower():
        tech_tags.append("Vercel Edge")
    if "x-amz-cf-id" in hmap or "cloudfront" in hmap.get("via", "").lower():
        tech_tags.append("AWS CloudFront")
    if "x-fastly-request-id" in hmap or "fastly" in hmap.get("x-served-by", "").lower():
        tech_tags.append("Fastly CDN")
    if "x-github-request-id" in hmap or "github.com" in server_v.lower():
        tech_tags.append("GitHub Pages / Edge")
    if "x-nf-request-id" in hmap or "netlify" in server_v.lower():
        tech_tags.append("Netlify")
    if parser.generator:
        tech_tags.append(f"Generator: {parser.generator}")
    if "__NEXT_DATA__" in body or "/_next/static/" in body:
        tech_tags.append("Next.js")
    if "wp-content/" in body or "wp-includes/" in body:
        tech_tags.append("WordPress")
    if "react" in " ".join(parser.script_srcs).lower():
        tech_tags.append("React")
    if "tailwind" in body.lower():
        tech_tags.append("Tailwind CSS hint")
    if "alt-svc" in hmap and "h3" in hmap["alt-svc"].lower():
        tech_tags.append("HTTP/3 (QUIC)")

    print()
    print("  " + fmt("DETECTED STACK & INFRASTRUCTURE HINTS", ui["secondary"], True))
    if tech_tags:
        for tag in tech_tags:
            print(f"  {fmt('•', ui['accent'])} {fmt(tag, ui['text'], True)}")
    else:
        print("  " + fmt("No overt framework/CDN fingerprint headers disclosed.", ui["muted"]))

    cookies = [v for k, v in hdrs if k.lower() == "set-cookie"]
    if cookies:
        print()
        print("  " + fmt(f"SET-COOKIE FLAGS ({len(cookies)})", ui["secondary"], True))
        for ck in cookies[:6]:
            cname = ck.split("=", 1)[0].strip()
            flags = [f for f in ("Secure", "HttpOnly", "SameSite") if f.lower() in ck.lower()]
            flag_str = ", ".join(flags) if flags else "No Secure/HttpOnly/SameSite flags"
            fc = ui["success"] if ("Secure" in flags and "HttpOnly" in flags) else ui["warning"]
            print(f"  {fmt(cname.ljust(22), ui['primary'])} {fmt(flag_str, fc)}")
    print()


def _mac_vendor_note(mac: str, ip_str: str, gateways: set[str]) -> tuple[str, str]:
    notes: list[str] = []
    if ip_str in gateways:
        notes.append("Default Gateway")
    if ip_str.startswith(("224.", "239.")) or ip_str.endswith(".255") or mac.lower().startswith(("01-00-5e", "ff-ff-ff")):
        return "Multicast / Broadcast", "muted"

    norm = mac.lower().replace("-", ":")
    parts = norm.split(":")
    if len(parts) == 6:
        try:
            first_byte = int(parts[0], 16)
            if first_byte & 0x02:
                notes.append("Randomized / LAA MAC")
        except ValueError:
            pass
        oui = ":".join(parts[:3])
        if oui in COMMON_OUI_PREFIXES:
            notes.append(COMMON_OUI_PREFIXES[oui])
    label = " | ".join(notes) if notes else "LAN Device"
    color_key = "accent" if ip_str in gateways else "text"
    return label, color_key


def cmd_lan(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    argparse.ArgumentParser(
        prog="lan",
        description="Read-only local ARP neighbor table & gateway viewer",
    ).parse_args(argv)

    header("Local Network Neighbors & Gateway (ARP Cache)", theme)

    gateways: set[str] = set()
    try:
        rt = subprocess.run(["route", "print", "-4"], capture_output=True, text=True, timeout=6)
        for line in rt.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                gateways.add(parts[2])
    except Exception:
        pass

    if gateways:
        print(f"  {fmt('Default Gateway(s):', ui['muted'])} {fmt(', '.join(sorted(gateways)), ui['success'], True)}")
        print()

    try:
        arp = subprocess.run(["arp", "-a"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=6)
    except Exception as exc:
        print(fmt(f"  Failed reading ARP table: {exc}", ui["error"]))
        return

    cur_iface = ""
    rows: list[tuple[str, str, str, str, str, str]] = []
    for raw in arp.stdout.splitlines():
        s = raw.strip()
        if not s:
            continue
        m_if = re.match(r"^Interface:\s+([0-9.]+)\s+---\s+(\S+)", s)
        if m_if:
            cur_iface = m_if.group(1)
            continue
        m_ent = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})\s+(\S+)", s)
        if m_ent:
            ip_a, mac, kind = m_ent.group(1), m_ent.group(2), m_ent.group(3)
            note, c_key = _mac_vendor_note(mac, ip_a, gateways)
            rows.append((cur_iface or "-", ip_a, mac.lower(), kind, note, c_key))

    if not rows:
        print("  " + fmt("ARP cache is empty.", ui["muted"]))
        print()
        return

    print(fmt(f"  {'INTERFACE':<16} {'IP ADDRESS':<16} {'MAC ADDRESS':<19} {'TYPE':<9} {'INFO'}", ui["muted"], True))
    print(fmt("  " + "─" * 82, ui["border"]))
    for iface, ip_a, mac, kind, note, c_key in rows:
        print(
            f"  {fmt(iface.ljust(16), ui['muted'])}"
            f" {fmt(ip_a.ljust(16), ui['primary'], ip_a in gateways)}"
            f" {fmt(mac.ljust(19), ui['text'])}"
            f" {fmt(kind.ljust(9), ui['muted'])}"
            f" {fmt(note, ui[c_key], ip_a in gateways)}"
        )
    print()


def cmd_portcheck(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(
        prog="portcheck",
        description="Developer TCP connectivity & latency check for a single host (max 25 ports)",
    )
    p.add_argument("host", nargs="?", default="localhost", help="Target host or IP (default: localhost)")
    p.add_argument("ports", nargs="?", default="", help="Comma-separated ports (e.g. 80,443,3000,5432)")
    p.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN connection")
    args = p.parse_args(argv)

    host = _clean_host(args.host) or "localhost"
    service_map = dict(COMMON_DEV_PORTS)
    ports_to_check: list[int] = []
    if args.ports.strip():
        for tok in args.ports.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                pn = int(tok)
                if 1 <= pn <= 65535 and pn not in ports_to_check:
                    ports_to_check.append(pn)
            except ValueError:
                print(fmt(f"  Skipping invalid port: {tok}", ui["warning"]))
        if len(ports_to_check) > MAX_PORTCHECK_PORTS:
            print(fmt(f"  Capped at {MAX_PORTCHECK_PORTS} ports per developer check.", ui["warning"]))
            ports_to_check = ports_to_check[:MAX_PORTCHECK_PORTS]
    else:
        ports_to_check = [pt for pt, _ in COMMON_DEV_PORTS]

    if not ports_to_check:
        print(fmt("  No valid ports provided.", ui["warning"]))
        return

    header(f"TCP Connectivity Check // {host}", theme)
    if not _is_local_or_private(host):
        ensure_vpn_for_tool("portcheck", theme, skip_vpn=args.no_vpn)
    try:
        target_ip = socket.gethostbyname(host)
    except Exception as exc:
        print(f"  {fmt('DNS Resolution Failed:', ui['error'], True)} {fmt(str(exc), ui['warning'])}")
        print()
        return

    print(f"  {fmt('Resolved IP:', ui['muted'])} {fmt(target_ip, ui['accent'], True)}   {fmt('Ports Checked:', ui['muted'])} {fmt(str(len(ports_to_check)), ui['text'])}")
    print(fmt("  " + "─" * 58, ui["border"]))

    def probe(port: int) -> tuple[int, bool, float]:
        t0 = time.perf_counter()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.2)
        try:
            rc = s.connect_ex((target_ip, port))
            ms = (time.perf_counter() - t0) * 1000.0
            return port, (rc == 0), ms
        except Exception:
            ms = (time.perf_counter() - t0) * 1000.0
            return port, False, ms
        finally:
            try:
                s.close()
            except Exception:
                pass

    results: list[tuple[int, bool, float]] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(probe, pt) for pt in ports_to_check]
        for f in as_completed(futs):
            results.append(f.result())

    results.sort(key=lambda r: r[0])
    print(fmt(f"  {'PORT':<8} {'SERVICE':<14} {'STATUS':<12} {'LATENCY'}", ui["muted"], True))
    open_cnt = 0
    for port, is_open, ms in results:
        svc = service_map.get(port, "custom")
        if is_open:
            open_cnt += 1
        st_txt = "OPEN" if is_open else "CLOSED"
        st_col = ui["success"] if is_open else ui["muted"]
        print(
            f"  {fmt(str(port).ljust(8), ui['primary'], is_open)}"
            f" {fmt(svc.ljust(14), ui['text'])}"
            f" {fmt(st_txt.ljust(12), st_col, is_open)}"
            f" {fmt(f'{ms:.1f} ms', ui['accent'] if is_open else ui['muted'])}"
        )
    print(fmt("  " + "─" * 58, ui["border"]))
    print(f"  {fmt(f'{open_cnt} open / {len(results) - open_cnt} closed', ui['text'])}")
    print()


def main() -> None:
    enable_vt()
    theme = load_theme()
    args = sys.argv[1:]
    if not args:
        print("recon_safe.py subcommands: --subdomains, --webtech, --lan, --portcheck")
        return
    cmd = args[0]
    rest = args[1:]
    dispatch = {
        "--subdomains": cmd_subdomains,
        "--webtech": cmd_webtech,
        "--lan": cmd_lan,
        "--portcheck": cmd_portcheck,
    }
    fn = dispatch.get(cmd)
    if fn:
        fn(rest, theme)
    else:
        print(f"Unknown recon_safe subcommand: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
