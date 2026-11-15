#!/usr/bin/env python3
"""TricksXTech Additional Network & HTTP Utilities (dns, rdns, cidr, unshorten, robots, sitemap, httpcode, uaparse, serve, lanspeed, pingcheck, ftpget, titlemeta)."""

from __future__ import annotations

import argparse
import ftplib
import functools
from html.parser import HTMLParser
import http.server
import ipaddress
import json
import os
import re
import socket
import socketserver
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, fmt_bytes, header, load_theme
from vpn_tool import ensure_vpn_for_tool

USER_AGENT = "TricksXTech-NetUtil/1.0"


def _is_local_target(host: str) -> bool:
    h = (host or "").strip().lower().rstrip(".")
    if not h or h in ("localhost", "::1") or h.endswith(".local"):
        return True
    try:
        ip_obj = ipaddress.ip_address(h)
        return bool(ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local)
    except ValueError:
        return False


def _clean_host(raw: str) -> str:
    s = (raw or "").strip()
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


def cmd_dns(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="dns", description="Fast DNS lookup (socket + DoH record query)")
    p.add_argument("host", nargs="?", help="Domain or hostname")
    p.add_argument("rtype", nargs="?", default="A", help="Record type: A | AAAA | MX | NS | TXT | CNAME | SOA")
    args = p.parse_args(argv)

    raw = args.host or input("  Enter hostname: ").strip()
    host = _clean_host(raw)
    if not host:
        return
    rtype = args.rtype.upper().strip() or "A"

    header(f"DNS Lookup // {host} ({rtype})", theme)
    try:
        q = urllib.parse.urlencode({"name": host, "type": rtype})
        req = urllib.request.Request(f"https://dns.google/resolve?{q}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=4.5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        answers = data.get("Answer") or []
        if answers:
            for ans in answers:
                ttl = ans.get("TTL", "-")
                val = ans.get("data", "")
                print(f"  {fmt(rtype.ljust(6), ui['primary'], True)} {fmt(('TTL ' + str(ttl)).ljust(11), ui['muted'])} {fmt(val, ui['accent'], True)}")
            print()
            return
    except Exception:
        pass

    # Local socket fallback
    try:
        infos = socket.getaddrinfo(host, None)
        ips = sorted({i[4][0] for i in infos})
        for ip in ips:
            fam = "IPv6" if ":" in ip else "IPv4"
            print(f"  {fmt(fam.ljust(6), ui['primary'], True)} {fmt(ip, ui['accent'], True)}")
    except Exception as exc:
        print(fmt(f"  DNS resolution failed: {exc}", ui["error"]))
    print()


def cmd_rdns(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="rdns", description="Reverse DNS lookup (IP -> hostname)")
    p.add_argument("ip", nargs="?", help="IPv4 or IPv6 address")
    args = p.parse_args(argv)

    ip_s = (args.ip or input("  Enter IP address: ").strip()).strip()
    if not ip_s:
        return
    header(f"Reverse DNS (PTR) // {ip_s}", theme)
    try:
        host, aliases, addrs = socket.gethostbyaddr(ip_s)
        print(f"  {fmt('PTR Host:'.ljust(14), ui['muted'])} {fmt(host, ui['primary'], True)}")
        if aliases:
            print(f"  {fmt('Aliases:'.ljust(14), ui['muted'])} {fmt(', '.join(aliases), ui['text'])}")
        print(f"  {fmt('Addresses:'.ljust(14), ui['muted'])} {fmt(', '.join(addrs), ui['accent'])}")
    except Exception as exc:
        print(f"  {fmt('PTR Lookup:', ui['muted'])} {fmt(f'No PTR record ({exc})', ui['warning'])}")
    print()


def cmd_cidr(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="cidr", description="Subnet & CIDR range calculator")
    p.add_argument("cidr", nargs="?", help="CIDR notation (e.g., 192.168.1.0/24 or 10.0.5.42/20)")
    args = p.parse_args(argv)

    raw = (args.cidr or input("  Enter IP/CIDR (e.g. 192.168.1.0/24): ").strip()).strip()
    if not raw:
        return
    try:
        net = ipaddress.ip_network(raw, strict=False)
        iface = ipaddress.ip_interface(raw)
    except ValueError as exc:
        print(fmt(f"  Invalid CIDR '{raw}': {exc}", ui["error"]))
        return

    header(f"Subnet & CIDR Calculator // {net}", theme)
    rows = [
        ("Input IP", str(iface.ip)),
        ("Network Address", str(net.network_address)),
        ("Prefix / Netmask", f"/{net.prefixlen}  ({net.netmask})"),
        ("Wildcard Mask", str(net.hostmask) if net.version == 4 else "-"),
        ("Broadcast", str(net.broadcast_address) if net.version == 4 else "-"),
        ("Total Addresses", f"{net.num_addresses:,}"),
    ]
    if net.version == 4:
        if net.prefixlen == 32:
            usable = 1
            first_h = last_h = str(net.network_address)
        elif net.prefixlen == 31:
            usable = 2
            first_h = str(net.network_address)
            last_h = str(net.broadcast_address)
        else:
            usable = max(0, net.num_addresses - 2)
            first_h = str(net.network_address + 1)
            last_h = str(net.broadcast_address - 1)
        rows.append(("Usable Hosts", f"{usable:,}"))
        rows.append(("Usable Range", f"{first_h}  ->  {last_h}"))
    rows.append(("Scope", "Private / RFC1918" if net.is_private else ("Loopback" if net.is_loopback else "Public Routable")))

    for k, v in rows:
        print(f"  {fmt((k + ':').ljust(19), ui['muted'])} {fmt(v, ui['accent'] if 'Range' in k or 'Network' in k else ui['text'], 'Network' in k)}")
    print()


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def cmd_unshorten(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="unshorten", description="Follow HTTP 3xx redirects to reveal final destination")
    p.add_argument("url", nargs="?", help="Shortened or redirecting URL")
    p.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN")
    args = p.parse_args(argv)

    raw = (args.url or input("  Enter URL: ").strip()).strip()
    if not raw:
        return
    url = raw if "://" in raw else f"https://{raw}"
    host = _clean_host(url)

    header(f"Redirect Unshortener // {url}", theme)
    if not _is_local_target(host):
        ensure_vpn_for_tool("unshorten", theme, skip_vpn=args.no_vpn)

    opener = urllib.request.build_opener(_NoRedirectHandler())
    cur = url
    visited: set[str] = set()
    for hop in range(1, 16):
        if cur in visited:
            print(fmt("  [Loop detected]", ui["warning"]))
            break
        visited.add(cur)
        req = urllib.request.Request(cur, method="HEAD", headers={"User-Agent": USER_AGENT})
        code = 0
        loc = None
        try:
            with opener.open(req, timeout=6.0) as resp:
                code = resp.status
                print(f"  {fmt(f'[{hop}]', ui['accent'], True)} {fmt(str(code), ui['success'], True)}  {fmt(cur, ui['primary'], True)}")
                break
        except urllib.error.HTTPError as exc:
            code = exc.code
            loc = exc.headers.get("Location") if exc.headers else None
            if code in (301, 302, 303, 307, 308) and loc:
                next_url = urllib.parse.urljoin(cur, loc)
                print(f"  {fmt(f'[{hop}]', ui['muted'])} {fmt(str(code), ui['warning'], True)}  {fmt(cur, ui['text'])} -> {fmt(next_url, ui['accent'])}")
                cur = next_url
                continue
            if code in (405, 403):
                # Retry with GET cleanly once
                try:
                    with opener.open(urllib.request.Request(cur, headers={"User-Agent": USER_AGENT}), timeout=6.0) as resp2:
                        print(f"  {fmt(f'[{hop}]', ui['accent'], True)} {fmt(str(resp2.status), ui['success'], True)}  {fmt(cur, ui['primary'], True)}")
                        break
                except urllib.error.HTTPError as exc2:
                    loc2 = exc2.headers.get("Location") if exc2.headers else None
                    if exc2.code in (301, 302, 303, 307, 308) and loc2:
                        next_url = urllib.parse.urljoin(cur, loc2)
                        print(f"  {fmt(f'[{hop}]', ui['muted'])} {fmt(str(exc2.code), ui['warning'], True)}  {fmt(cur, ui['text'])} -> {fmt(next_url, ui['accent'])}")
                        cur = next_url
                        continue
            print(f"  {fmt(f'[{hop}]', ui['muted'])} {fmt(str(code), ui['error'], True)}  {fmt(cur, ui['text'])}")
            break
        except Exception as exc:
            print(fmt(f"  Error on hop {hop}: {exc}", ui["error"]))
            break
    print()


def cmd_robots(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="robots", description="Fetch & parse robots.txt crawler directives")
    p.add_argument("target", nargs="?", help="Domain or URL")
    p.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN")
    args = p.parse_args(argv)

    raw = (args.target or input("  Enter domain or URL: ").strip()).strip()
    if not raw:
        return
    base = raw if "://" in raw else f"https://{raw}"
    parsed = urllib.parse.urlparse(base)
    rurl = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    header(f"robots.txt Parser // {parsed.netloc}", theme)
    if not _is_local_target(parsed.hostname or ""):
        ensure_vpn_for_tool("robots", theme, skip_vpn=args.no_vpn)

    req = urllib.request.Request(rurl, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=7.0) as resp:
            txt = resp.read(262144).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        print(fmt(f"  robots.txt returned HTTP {exc.code} ({exc.reason}).", ui["warning"]))
        print()
        return
    except Exception as exc:
        print(fmt(f"  Failed fetching robots.txt: {exc}", ui["error"]))
        print()
        return

    sitemaps: list[str] = []
    agents = 0
    allows = 0
    disallows = 0
    for line in txt.splitlines():
        clean = line.split("#", 1)[0].strip()
        if not clean or ":" not in clean:
            continue
        k, v = [x.strip() for x in clean.split(":", 1)]
        kl = k.lower()
        if kl == "user-agent":
            agents += 1
            print(f"\n  {fmt('User-Agent:', ui['primary'], True)} {fmt(v, ui['accent'], True)}")
        elif kl == "disallow":
            disallows += 1
            print(f"    {fmt('Disallow:', ui['error'])} {fmt(v or '(none)', ui['text'])}")
        elif kl == "allow":
            allows += 1
            print(f"    {fmt('Allow:   ', ui['success'])} {fmt(v, ui['text'])}")
        elif kl == "sitemap":
            sitemaps.append(v)
        else:
            print(f"    {fmt(k + ':', ui['muted'])} {fmt(v, ui['text'])}")

    if sitemaps:
        print("\n  " + fmt("SITEMAPS:", ui["secondary"], True))
        for sm in sitemaps:
            print(f"    {fmt('*', ui['accent'])} {fmt(sm, ui['accent'])}")
    print(f"\n  {fmt(f'Agents: {agents}  |  Allow: {allows}  |  Disallow: {disallows}  |  Sitemaps: {len(sitemaps)}', ui['muted'])}\n")


def cmd_sitemap(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="sitemap", description="Download & extract URLs from sitemap.xml")
    p.add_argument("target", nargs="?", help="Domain or direct sitemap.xml URL")
    p.add_argument("-n", "--limit", type=int, default=40, help="Max URLs to display (default 40)")
    p.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN")
    args = p.parse_args(argv)

    raw = (args.target or input("  Enter domain or sitemap URL: ").strip()).strip()
    if not raw:
        return
    url = raw if "://" in raw else f"https://{raw}"
    parsed = urllib.parse.urlparse(url)
    if not parsed.path or parsed.path == "/":
        url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"

    header(f"Sitemap XML Extractor // {url}", theme)
    if not _is_local_target(parsed.hostname or ""):
        ensure_vpn_for_tool("sitemap", theme, skip_vpn=args.no_vpn)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=9.0) as resp:
            xml_bytes = resp.read(2 * 1024 * 1024)
        root = ET.fromstring(xml_bytes)
    except Exception as exc:
        print(fmt(f"  Sitemap fetch/parse error: {exc}", ui["error"]))
        print()
        return

    locs: list[tuple[str, str]] = []
    for elem in root.iter():
        tag = elem.tag.split("}")[-1].lower()
        if tag in ("url", "sitemap"):
            loc = ""
            mod = ""
            for child in elem:
                ctag = child.tag.split("}")[-1].lower()
                if ctag == "loc" and child.text:
                    loc = child.text.strip()
                elif ctag == "lastmod" and child.text:
                    mod = child.text.strip()[:10]
            if loc:
                locs.append((loc, mod))

    print(f"  {fmt('Entries Extracted:', ui['muted'])} {fmt(str(len(locs)), ui['primary'], True)}")
    print(fmt("  " + "─" * 74, ui["border"]))
    for loc, mod in locs[: max(1, args.limit)]:
        mod_s = fmt(mod.ljust(12), ui["muted"]) if mod else fmt("-".ljust(12), ui["muted"])
        print(f"  {mod_s} {fmt(loc, ui['accent'])}")
    if len(locs) > args.limit:
        print(fmt(f"  ... and {len(locs) - args.limit} more URLs (increase with -n).", ui["muted"]))
    print()


def cmd_httpcode(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="httpcode", description="Check HTTP status codes & latency for URLs")
    p.add_argument("urls", nargs="*", help="One or more URLs/domains")
    p.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN")
    args = p.parse_args(argv)

    targets = args.urls or [input("  Enter URL or domain: ").strip()]
    targets = [t for t in targets if t]
    if not targets:
        return

    header("HTTP Status Code Tester", theme)
    if any(not _is_local_target(_clean_host(u if "://" in u else f"https://{u}")) for u in targets):
        ensure_vpn_for_tool("httpcode", theme, skip_vpn=args.no_vpn)

    print(fmt(f"  {'CODE':<7} {'TTFB':>8}  {'URL'}", ui["muted"], True))
    print(fmt("  " + "─" * 74, ui["border"]))
    for raw in targets:
        u = raw if "://" in raw else f"https://{raw}"
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=7.0) as resp:
                ms = (time.perf_counter() - t0) * 1000.0
                c = ui["success"] if resp.status < 300 else ui["accent"]
                print(f"  {fmt(str(resp.status).ljust(7), c, True)} {fmt(f'{ms:6.0f}ms', ui['muted'])}  {fmt(resp.geturl(), ui['text'])}")
        except urllib.error.HTTPError as exc:
            ms = (time.perf_counter() - t0) * 1000.0
            c = ui["warning"] if 300 <= exc.code < 500 else ui["error"]
            print(f"  {fmt(str(exc.code).ljust(7), c, True)} {fmt(f'{ms:6.0f}ms', ui['muted'])}  {fmt(u + ' (' + exc.reason + ')', ui['text'])}")
        except Exception as exc:
            print(f"  {fmt('ERR'.ljust(7), ui['error'], True)} {fmt('      -', ui['muted'])}  {fmt(f'{u} ({exc})', ui['warning'])}")
    print()


def cmd_uaparse(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="uaparse", description="Parse User-Agent strings (OS, Browser, Engine, Device)")
    p.add_argument("ua", nargs="*", help="User-Agent string")
    args = p.parse_args(argv)

    ua = " ".join(args.ua).strip() if args.ua else input("  Paste User-Agent string: ").strip()
    if not ua:
        return

    os_name = "Unknown"
    for pat, label in (
        (r"Windows NT 10\.0", "Windows 10/11"),
        (r"Windows NT 6\.3", "Windows 8.1"),
        (r"Windows NT 6\.1", "Windows 7"),
        (r"iPhone OS ([0-9_]+)", "iOS"),
        (r"iPad.*OS ([0-9_]+)", "iPadOS"),
        (r"Android ([0-9.]+)", "Android"),
        (r"Mac OS X ([0-9_]+)", "macOS"),
        (r"CrOS", "ChromeOS"),
        (r"Linux", "Linux"),
    ):
        m = re.search(pat, ua)
        if m:
            ver = f" {m.group(1).replace('_', '.')}" if m.lastindex else ""
            os_name = label + ver
            break

    browser = "Unknown"
    for pat, label in (
        (r"EdgA?/([0-9.]+)", "Microsoft Edge"),
        (r"OPR/([0-9.]+)", "Opera"),
        (r"Firefox/([0-9.]+)", "Firefox"),
        (r"Chrome/([0-9.]+)", "Chrome"),
        (r"Version/([0-9.]+).*Safari/", "Safari"),
        (r"curl/([0-9.]+)", "curl"),
        (r"python-requests/([0-9.]+)", "python-requests"),
        (r"Googlebot/([0-9.]+)", "Googlebot"),
    ):
        m = re.search(pat, ua)
        if m:
            browser = f"{label} {m.group(1)}"
            break

    engine = "Unknown"
    if "AppleWebKit" in ua:
        engine = "Blink" if ("Chrome" in ua or "Edg" in ua or "OPR" in ua) else "WebKit"
    elif "Gecko/" in ua and "Firefox" in ua:
        engine = "Gecko"

    low = ua.lower()
    if any(b in low for b in ("bot", "crawler", "spider", "curl/", "wget", "python-")):
        device = "Bot / CLI Client"
    elif "ipad" in low or "tablet" in low:
        device = "Tablet"
    elif "mobile" in low or "iphone" in low or ("android" in low and "mobile" in low):
        device = "Mobile"
    else:
        device = "Desktop"

    header("User-Agent String Parser", theme)
    print(f"  {fmt('Device Type:'.ljust(16), ui['muted'])} {fmt(device, ui['primary'], True)}")
    print(f"  {fmt('OS / Platform:'.ljust(16), ui['muted'])} {fmt(os_name, ui['accent'], True)}")
    print(f"  {fmt('Browser/App:'.ljust(16), ui['muted'])} {fmt(browser, ui['success'], True)}")
    print(f"  {fmt('Layout Engine:'.ljust(16), ui['muted'])} {fmt(engine, ui['text'])}")
    print()


def cmd_serve(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="serve", description="Start local HTTP file-sharing server")
    p.add_argument("port", nargs="?", type=int, default=8000, help="Port number (default 8000)")
    p.add_argument("directory", nargs="?", default=".", help="Directory to serve (default .)")
    p.add_argument("--lan", action="store_true", help="Bind 0.0.0.0 so LAN devices can access (default localhost 127.0.0.1)")
    args = p.parse_args(argv)

    root_dir = os.path.abspath(args.directory)
    if not os.path.isdir(root_dir):
        print(fmt(f"  Directory not found: {root_dir}", ui["error"]))
        return

    bind_ip = "0.0.0.0" if args.lan else "127.0.0.1"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root_dir)

    class _ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    header("Local HTTP File Server", theme)
    print(f"  {fmt('Directory:'.ljust(14), ui['muted'])} {fmt(root_dir, ui['text'])}")
    print(f"  {fmt('Local URL:'.ljust(14), ui['muted'])} {fmt(f'http://127.0.0.1:{args.port}/', ui['primary'], True)}")
    if args.lan:
        try:
            lan_ips = [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET) if i[4][0] != "127.0.0.1"]
            for lip in sorted(set(lan_ips)):
                print(f"  {fmt('LAN URL:'.ljust(14), ui['muted'])} {fmt(f'http://{lip}:{args.port}/', ui['accent'], True)}")
        except Exception:
            pass
    print(f"  {fmt('Controls:'.ljust(14), ui['muted'])} {fmt('Press Ctrl+C to stop server', ui['warning'])}")
    print()
    try:
        with _ReusableTCPServer((bind_ip, args.port), handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  " + fmt("HTTP server stopped.", ui["success"]))
    except OSError as exc:
        print(fmt(f"  Failed binding port {args.port}: {exc}", ui["error"]))


def cmd_lanspeed(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(
        prog="lanspeed",
        description="Local folder / UNC share throughput test or TCP LAN receiver (--listen)",
    )
    p.add_argument("target", nargs="?", default=".", help="Folder/UNC path, host IP, or --listen")
    p.add_argument("arg2", nargs="?", default="", help="Size in MB (for path test, default 64) or TCP port (default 9753)")
    p.add_argument("--listen", action="store_true", help="Listen as TCP receiver on port 9753 (or arg2)")
    args = p.parse_args(argv)

    if args.listen or args.target == "--listen":
        port = int(args.arg2) if args.arg2.isdigit() else (int(args.target) if args.target.isdigit() else 9753)
        header(f"LAN Bandwidth Receiver // Port {port}", theme)
        print(f"  {fmt('Listening on:', ui['muted'])} {fmt(f'0.0.0.0:{port}', ui['primary'], True)}  (run `lanspeed <this_ip> {port}` on peer, Ctrl+C stops)")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", port))
            srv.listen(1)
            try:
                while True:
                    conn, addr = srv.accept()
                    t0 = time.perf_counter()
                    total = 0
                    with conn:
                        while True:
                            buf = conn.recv(65536)
                            if not buf:
                                break
                            total += len(buf)
                    dt = max(0.01, time.perf_counter() - t0)
                    mbps = (total * 8.0) / dt / 1_000_000.0
                    print(f"  {fmt(addr[0], ui['accent'])} sent {fmt_bytes(total)} in {dt:.2f}s -> {fmt(f'{mbps:.1f} Mbps', ui['success'], True)}")
            except KeyboardInterrupt:
                print("\n  " + fmt("Receiver stopped.", ui["warning"]))
        return

    # Check if target looks like an IP/hostname rather than an existing folder path
    if not os.path.exists(args.target):
        port = int(args.arg2) if args.arg2.isdigit() else 9753
        header(f"LAN TCP Bandwidth Test // {args.target}:{port}", theme)
        block = b"L" * (256 * 1024)
        total = 0
        t0 = time.perf_counter()
        try:
            with socket.create_connection((args.target, port), timeout=5.0) as sock:
                while time.perf_counter() - t0 < 4.0:
                    sock.sendall(block)
                    total += len(block)
            dt = max(0.01, time.perf_counter() - t0)
            mbps = (total * 8.0) / dt / 1_000_000.0
            print(f"  {fmt('Sent:'.ljust(14), ui['muted'])} {fmt_bytes(total)} in {dt:.2f}s")
            print(f"  {fmt('Throughput:'.ljust(14), ui['muted'])} {fmt(f'{mbps:.2f} Mbps ({mbps / 8.0:.2f} MB/s)', ui['success'], True)}")
        except Exception as exc:
            print(fmt(f"  TCP connect failed ({exc}). Start receiver on target with: lanspeed --listen {port}", ui["warning"]))
        print()
        return

    # Local or SMB/UNC share I/O benchmark
    size_mb = int(args.arg2) if args.arg2.isdigit() else 32
    size_mb = max(4, min(512, size_mb))
    target_dir = os.path.abspath(args.target)
    header(f"Share / Disk Bandwidth Test // {target_dir}", theme)
    tmp_path = os.path.join(target_dir, f".tx_speedtest_{os.getpid()}.tmp")
    chunk = os.urandom(1024 * 1024)
    try:
        t0 = time.perf_counter()
        with open(tmp_path, "wb") as f:
            for _ in range(size_mb):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        w_dt = max(0.005, time.perf_counter() - t0)

        t1 = time.perf_counter()
        with open(tmp_path, "rb") as f:
            while f.read(1024 * 1024):
                pass
        r_dt = max(0.005, time.perf_counter() - t1)

        w_mbs = size_mb / w_dt
        r_mbs = size_mb / r_dt
        print(f"  {fmt('Test Size:'.ljust(14), ui['muted'])} {size_mb} MB")
        print(f"  {fmt('Write Speed:'.ljust(14), ui['muted'])} {fmt(f'{w_mbs:.1f} MB/s', ui['accent'], True)}  ({w_mbs * 8.0:.0f} Mbps)")
        print(f"  {fmt('Read Speed:'.ljust(14), ui['muted'])} {fmt(f'{r_mbs:.1f} MB/s', ui['success'], True)}  ({r_mbs * 8.0:.0f} Mbps)")
    except OSError as exc:
        print(fmt(f"  Benchmark failed: {exc}", ui["error"]))
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
    print()


def cmd_pingcheck(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="pingcheck", description="System ping wrapper with latency visualization & jitter summary")
    p.add_argument("host", nargs="?", default="1.1.1.1", help="Target host or IP (default 1.1.1.1)")
    p.add_argument("-n", "--count", type=int, default=5, help="Packet count (default 5)")
    args = p.parse_args(argv)

    cnt = max(1, min(20, args.count))
    header(f"Ping & Latency Analyzer // {args.host}", theme)
    flag = "-n" if os.name == "nt" else "-c"
    res = subprocess.run(["ping", flag, str(cnt), args.host], capture_output=True, text=True, encoding="utf-8", errors="replace")
    rtts: list[float] = []
    for line in res.stdout.splitlines():
        m = re.search(r"time[=<]\s*([0-9.]+)\s*ms", line, re.IGNORECASE)
        if m:
            ms = float(m.group(1))
            rtts.append(ms)
            bar_n = max(1, min(28, round(ms / 6.0)))
            clr = ui["success"] if ms < 40 else (ui["accent"] if ms < 100 else ui["warning"])
            print(f"  {fmt(f'#{len(rtts):<2}', ui['muted'])} {fmt('█' * bar_n, clr, True)}  {fmt(f'{ms:.1f} ms', clr, True)}")
        elif "timed out" in line.lower() or "unreachable" in line.lower():
            print(f"  {fmt('!', ui['error'], True)}  {fmt(line.strip(), ui['warning'])}")

    print(fmt("  " + "─" * 58, ui["border"]))
    if rtts:
        avg = sum(rtts) / len(rtts)
        jit = sum(abs(rtts[i] - rtts[i - 1]) for i in range(1, len(rtts))) / max(1, len(rtts) - 1)
        loss = max(0, cnt - len(rtts))
        print(f"  {fmt('Min / Avg / Max:', ui['muted'])} {fmt(f'{min(rtts):.1f} / {avg:.1f} / {max(rtts):.1f} ms', ui['primary'], True)}   {fmt('Jitter:', ui['muted'])} {jit:.1f} ms   {fmt('Loss:', ui['muted'])} {loss}/{cnt}")
    else:
        print(fmt("  No ICMP replies received.", ui["error"]))
    print()


def cmd_ftpget(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="ftpget", description="Download or list public FTP files over ftplib")
    p.add_argument("target", help="FTP host or ftp://host/path")
    p.add_argument("remote_path", nargs="?", default="/", help="Remote file or folder path (default /)")
    p.add_argument("-o", "--outdir", default=".", help="Local output folder for downloaded file")
    p.add_argument("--list", action="store_true", help="List directory only")
    p.add_argument("--user", default="anonymous", help="FTP username (default anonymous)")
    p.add_argument("--password", default="anonymous@", help="FTP password")
    p.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN")
    args = p.parse_args(argv)

    if args.target.lower().startswith("ftp://"):
        parsed = urllib.parse.urlparse(args.target)
        host = parsed.hostname or ""
        port = parsed.port or 21
        rpath = parsed.path or args.remote_path or "/"
    else:
        host = _clean_host(args.target)
        port = 21
        rpath = args.remote_path

    if not host:
        print(fmt("  Invalid FTP host.", ui["error"]))
        return

    header(f"FTP Client // {host}:{port}", theme)
    if not _is_local_target(host):
        ensure_vpn_for_tool("ftpget", theme, skip_vpn=args.no_vpn)

    try:
        with ftplib.FTP() as ftp:
            ftp.connect(host, port, timeout=10.0)
            ftp.login(args.user, args.password)
            if args.list or rpath.endswith("/") or rpath in ("/", "."):
                print(f"  {fmt('Listing:', ui['muted'])} {fmt(rpath, ui['accent'])}")
                lines: list[str] = []
                ftp.dir(rpath, lines.append)
                for ln in lines[:40]:
                    print("  " + fmt(ln, ui["text"]))
                if len(lines) > 40:
                    print(fmt(f"  ... ({len(lines) - 40} more entries)", ui["muted"]))
            else:
                os.makedirs(args.outdir, exist_ok=True)
                fname = os.path.basename(rpath.rstrip("/")) or "ftp_download.bin"
                dest = os.path.abspath(os.path.join(args.outdir, fname))
                with open(dest, "wb") as out:
                    ftp.retrbinary(f"RETR {rpath}", out.write)
                sz = os.path.getsize(dest)
                print(f"  {fmt('Downloaded:', ui['success'], True)} {fmt(dest, ui['primary'])} ({fmt_bytes(sz)})")
    except Exception as exc:
        print(fmt(f"  FTP error: {exc}", ui["error"]))
    print()


class _TitleMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_chunks: list[str] = []
        self.metas: list[tuple[str, str]] = []
        self.canonical = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        amap = {k.lower(): (v or "") for k, v in attrs}
        if t == "title":
            self.in_title = True
        elif t == "meta":
            key = amap.get("name") or amap.get("property") or amap.get("http-equiv") or ""
            val = amap.get("content") or amap.get("charset") or ""
            if key and val:
                self.metas.append((key, val))
            elif amap.get("charset"):
                self.metas.append(("charset", amap["charset"]))
        elif t == "link" and "canonical" in amap.get("rel", "").lower() and amap.get("href"):
            self.canonical = amap["href"]

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_chunks.append(data)


def cmd_titlemeta(argv: list[str], theme: dict) -> None:
    ui = theme["ui"]
    p = argparse.ArgumentParser(prog="titlemeta", description="Extract webpage <title> and <meta>/OpenGraph tags")
    p.add_argument("target", nargs="?", help="URL or domain")
    p.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN")
    args = p.parse_args(argv)

    raw = (args.target or input("  Enter URL or domain: ").strip()).strip()
    if not raw:
        return
    url = raw if "://" in raw else f"https://{raw}"
    host = _clean_host(url)

    header(f"Page Title & Meta Extractor // {url}", theme)
    if not _is_local_target(host):
        ensure_vpn_for_tool("titlemeta", theme, skip_vpn=args.no_vpn)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            html = resp.read(262144).decode("utf-8", errors="replace")
    except Exception as exc:
        print(fmt(f"  Fetch failed: {exc}", ui["error"]))
        print()
        return

    parser = _TitleMetaParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    title = re.sub(r"\s+", " ", "".join(parser.title_chunks)).strip()
    print(f"  {fmt('Title:'.ljust(16), ui['muted'])} {fmt(title or '(none)', ui['primary'], True)}")
    if parser.canonical:
        print(f"  {fmt('Canonical:'.ljust(16), ui['muted'])} {fmt(parser.canonical, ui['accent'])}")
    print(fmt("  " + "─" * 74, ui["border"]))
    for k, v in parser.metas[:25]:
        short = (v[:68] + "...") if len(v) > 71 else v
        print(f"  {fmt(k.ljust(22), ui['secondary'])} {fmt(short, ui['text'])}")
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
        print("net_extra.py subcommands: --dns, --rdns, --cidr, --unshorten, --robots, --sitemap, --httpcode, --uaparse, --serve, --lanspeed, --pingcheck, --ftpget, --titlemeta")
        return
    dispatch = {
        "--dns": cmd_dns,
        "--rdns": cmd_rdns,
        "--cidr": cmd_cidr,
        "--unshorten": cmd_unshorten,
        "--robots": cmd_robots,
        "--sitemap": cmd_sitemap,
        "--httpcode": cmd_httpcode,
        "--uaparse": cmd_uaparse,
        "--serve": cmd_serve,
        "--lanspeed": cmd_lanspeed,
        "--pingcheck": cmd_pingcheck,
        "--ftpget": cmd_ftpget,
        "--titlemeta": cmd_titlemeta,
    }
    fn = dispatch.get(args[0])
    if fn:
        fn(args[1:], theme)
    else:
        print(f"Unknown net_extra subcommand: {args[0]}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
