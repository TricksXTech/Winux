#!/usr/bin/env python3
"""TricksXTech Passive Public OSINT Inspector (DNS, RDAP, IP/ASN, TLS, HTTP Headers)."""

from __future__ import annotations

import argparse
import datetime
import ipaddress
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, header, load_theme
from vpn_tool import ensure_vpn_for_tool

USER_AGENT = "TricksXTech-OSINT/1.0 (+passive-public-lookup)"


def _http_json(url: str, timeout: float = 5.5) -> tuple[dict | None, str | None]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/rdap+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:
        return None, str(exc)


def _normalize_target(raw: str) -> tuple[str, bool]:
    s = raw.strip()
    if "://" in s:
        parsed = urllib.parse.urlparse(s)
        host = parsed.hostname or s
    else:
        host = s.split("/")[0].strip()
        if ":" in host and not host.startswith("["):
            # Could be host:port or IPv6
            try:
                ipaddress.ip_address(host)
            except ValueError:
                host = host.split(":")[0]
        host = host.strip("[]")
    try:
        ipaddress.ip_address(host)
        return host, True
    except ValueError:
        return host.lower().rstrip("."), False


def _query_doh(name: str, rtype: str) -> list[str]:
    q = urllib.parse.urlencode({"name": name, "type": rtype})
    data, err = _http_json(f"https://dns.google/resolve?{q}", timeout=4.5)
    if err or not data:
        return []
    answers = data.get("Answer") or []
    out: list[str] = []
    for ans in answers:
        val = str(ans.get("data", "")).strip()
        if val:
            out.append(val)
    return out


def _inspect_ip(ip_str: str, ui: dict) -> None:
    print("  " + fmt("IP / ASN / GEOLOCATION", ui["secondary"], True))
    try:
        ptr, _, _ = socket.gethostbyaddr(ip_str)
    except Exception:
        ptr = None
    if ptr:
        print(f"  {fmt('Reverse PTR:', ui['muted']):<20} {fmt(ptr, ui['accent'])}")

    data, err = _http_json(f"https://ipinfo.io/{urllib.parse.quote(ip_str)}/json", timeout=4.5)
    if data and not data.get("bogon") and ("org" in data or "country" in data):
        org = data.get("org", "?")
        city = data.get("city", "")
        region = data.get("region", "")
        country = data.get("country", "")
        loc = ", ".join(p for p in (city, region, country) if p) or "?"
        tz = data.get("timezone", "?")
        print(f"  {fmt('ASN / Org:', ui['muted']):<20} {fmt(org, ui['text'], True)}")
        print(f"  {fmt('Location:', ui['muted']):<20} {fmt(loc, ui['text'])}   {fmt('TZ:', ui['muted'])} {fmt(tz, ui['muted'])}")
    else:
        data2, err2 = _http_json(
            f"http://ip-api.com/json/{urllib.parse.quote(ip_str)}?fields=status,country,regionName,city,isp,org,as,message",
            timeout=4.5,
        )
        if data2 and data2.get("status") == "success":
            loc = ", ".join(p for p in (data2.get("city", ""), data2.get("regionName", ""), data2.get("country", "")) if p)
            asn = data2.get("as", "?")
            isp = data2.get("isp", "?")
            print(f"  {fmt('ASN:', ui['muted']):<20} {fmt(asn, ui['text'], True)}   {fmt('ISP:', ui['muted'])} {fmt(isp, ui['text'])}")
            print(f"  {fmt('Location:', ui['muted']):<20} {fmt(loc or '?', ui['text'])}")
        else:
            msg = err or err2 or "Lookup unavailable (rate-limited or offline)"
            print(f"  {fmt('IP Metadata:', ui['muted']):<20} {fmt(msg, ui['warning'])}")
    print()


def _extract_rdap_vcard_name(entity: dict) -> str:
    vc = entity.get("vcardArray")
    if isinstance(vc, list) and len(vc) > 1 and isinstance(vc[1], list):
        for item in vc[1]:
            if isinstance(item, list) and len(item) >= 4 and item[0] == "fn":
                return str(item[3])
    return str(entity.get("handle", ""))


def _inspect_rdap(target: str, is_ip: bool, ui: dict) -> None:
    print("  " + fmt("PUBLIC RDAP / REGISTRATION", ui["secondary"], True))
    endpoint = f"https://rdap.org/ip/{urllib.parse.quote(target)}" if is_ip else f"https://rdap.org/domain/{urllib.parse.quote(target)}"
    data, err = _http_json(endpoint, timeout=6.0)
    if err or not data:
        print(f"  {fmt('RDAP:', ui['muted']):<20} {fmt(err or 'No RDAP response', ui['warning'])}")
        print()
        return

    if is_ip:
        name = data.get("name", "?")
        handle = data.get("handle", "?")
        cidr_list = data.get("cidr0_cidrs") or []
        cidrs = ", ".join(
            f"{c.get('v4prefix') or c.get('v6prefix')}/{c.get('length')}"
            for c in cidr_list
            if isinstance(c, dict)
        )
        country = data.get("country", "?")
        print(f"  {fmt('Netname:', ui['muted']):<20} {fmt(name, ui['primary'], True)}   {fmt('Handle:', ui['muted'])} {fmt(handle, ui['text'])}")
        if cidrs:
            print(f"  {fmt('CIDR:', ui['muted']):<20} {fmt(cidrs, ui['accent'])}   {fmt('Country:', ui['muted'])} {fmt(country, ui['text'])}")
    else:
        ldh = data.get("ldhName", target)
        status = ", ".join(data.get("status", [])[:4]) or "?"
        events = {ev.get("eventAction"): ev.get("eventDate", "")[:10] for ev in (data.get("events") or []) if isinstance(ev, dict)}
        registrar = ""
        for ent in data.get("entities") or []:
            roles = ent.get("roles") or []
            if "registrar" in roles:
                registrar = _extract_rdap_vcard_name(ent)
                break
        ns_list = [ns.get("ldhName", "") for ns in (data.get("nameservers") or []) if isinstance(ns, dict) and ns.get("ldhName")]
        print(f"  {fmt('Domain:', ui['muted']):<20} {fmt(ldh, ui['primary'], True)}   {fmt('Registrar:', ui['muted'])} {fmt(registrar or '?', ui['text'])}")
        created = events.get("registration", "?")
        expires = events.get("expiration", "?")
        changed = events.get("last changed", "?")
        print(f"  {fmt('Dates:', ui['muted']):<20} {fmt(f'Created {created}  |  Updated {changed}  |  Expires {expires}', ui['text'])}")
        print(f"  {fmt('Status:', ui['muted']):<20} {fmt(status, ui['muted'])}")
        if ns_list:
            print(f"  {fmt('RDAP NS:', ui['muted']):<20} {fmt(', '.join(ns_list[:4]), ui['accent'])}")
    print()


def _inspect_dns(domain: str, ui: dict) -> list[str]:
    print("  " + fmt("PUBLIC DNS RECORDS (DNS-over-HTTPS)", ui["secondary"], True))
    ips: list[str] = []
    any_online = False
    for rtype in ("A", "AAAA", "MX", "NS", "TXT", "CAA"):
        vals = _query_doh(domain, rtype)
        if vals:
            any_online = True
            if rtype in ("A", "AAAA"):
                ips.extend(vals)
            shown = vals[:4]
            suffix = f" (+{len(vals) - 4} more)" if len(vals) > 4 else ""
            color = ui["accent"] if rtype in ("A", "AAAA") else ui["text"]
            for idx, v in enumerate(shown):
                raw_lbl = f"{rtype}:" if idx == 0 else ""
                extra = suffix if idx == len(shown) - 1 else ""
                line_val = (v[:82] + "...") if len(v) > 85 else v
                print(f"  {fmt(raw_lbl.ljust(14), ui['muted'])} {fmt(line_val + extra, color)}")
    # DMARC check
    dmarc = _query_doh(f"_dmarc.{domain}", "TXT")
    if dmarc:
        any_online = True
        print(f"  {fmt('DMARC:'.ljust(14), ui['muted'])} {fmt(dmarc[0][:85], ui['success'])}")
    else:
        print(f"  {fmt('DMARC:'.ljust(14), ui['muted'])} {fmt('No _dmarc TXT record published', ui['warning'])}")

    if not any_online:
        # Local socket fallback
        try:
            infos = socket.getaddrinfo(domain, None)
            local_ips = sorted({i[4][0] for i in infos})
            ips.extend(local_ips)
            print(f"  {fmt('Local Resolve:'.ljust(14), ui['muted'])} {fmt(', '.join(local_ips[:6]), ui['accent'])}")
        except Exception as exc:
            print(f"  {fmt('DNS Lookup:'.ljust(14), ui['muted'])} {fmt(f'Failed ({exc})', ui['error'])}")
    print()
    return ips


def _inspect_tls(host: str, ui: dict) -> None:
    print("  " + fmt("TLS / SSL CERTIFICATE (PORT 443)", ui["secondary"], True))
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=5.0) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                ver = ssock.version() or "?"
    except Exception as exc:
        print(f"  {fmt('TLS Status:', ui['muted']):<20} {fmt(f'Unavailable ({exc})', ui['warning'])}")
        print()
        return

    subj = dict(x[0] for x in cert.get("subject", ()))
    iss = dict(x[0] for x in cert.get("issuer", ()))
    cn = subj.get("commonName", host)
    issuer_name = iss.get("organizationName") or iss.get("commonName") or "?"
    not_after_raw = cert.get("notAfter", "")
    days_left_str = "?"
    exp_color = ui["text"]
    if not_after_raw:
        try:
            exp_dt = datetime.datetime.strptime(not_after_raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=datetime.timezone.utc)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            days_left = (exp_dt - now_dt).days
            days_left_str = f"{days_left} days left ({exp_dt.strftime('%Y-%m-%d')})"
            exp_color = ui["success"] if days_left >= 21 else (ui["warning"] if days_left >= 0 else ui["error"])
        except Exception:
            days_left_str = not_after_raw

    sans = [val for typ, val in cert.get("subjectAltName", ()) if typ == "DNS"]
    san_preview = ", ".join(sans[:4]) + (f" (+{len(sans) - 4} more)" if len(sans) > 4 else "")
    print(f"  {fmt('Subject CN:', ui['muted']):<20} {fmt(cn, ui['primary'], True)}   {fmt('Protocol:', ui['muted'])} {fmt(ver, ui['accent'])}")
    print(f"  {fmt('Issuer:', ui['muted']):<20} {fmt(issuer_name, ui['text'])}")
    print(f"  {fmt('Expiry:', ui['muted']):<20} {fmt(days_left_str, exp_color, True)}")
    if san_preview:
        print(f"  {fmt('SANs:', ui['muted']):<20} {fmt(san_preview, ui['muted'])}")
    print()


def _inspect_http_headers(host: str, ui: dict) -> None:
    print("  " + fmt("HTTP SECURITY HEADERS AUDIT", ui["secondary"], True))
    url = f"https://{host}/"
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    headers_map: dict[str, str] = {}
    status_line = ""
    try:
        with urllib.request.urlopen(req, timeout=5.5) as resp:
            status_line = f"{resp.status} {resp.reason}"
            headers_map = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        status_line = f"{exc.code} {exc.reason}"
        headers_map = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
    except Exception as exc:
        print(f"  {fmt('HTTPS HEAD:', ui['muted']):<20} {fmt(f'Unavailable ({exc})', ui['warning'])}")
        print()
        return

    print(f"  {fmt('Status:', ui['muted']):<20} {fmt(status_line, ui['accent'], True)}   {fmt('Server:', ui['muted'])} {fmt(headers_map.get('server', 'hidden'), ui['text'])}")
    checks = [
        ("strict-transport-security", "HSTS"),
        ("content-security-policy", "CSP"),
        ("x-frame-options", "X-Frame-Options"),
        ("x-content-type-options", "X-Content-Type-Opt"),
        ("referrer-policy", "Referrer-Policy"),
        ("permissions-policy", "Permissions-Policy"),
    ]
    for h_key, label in checks:
        val = headers_map.get(h_key)
        if val:
            short = (val[:62] + "...") if len(val) > 65 else val
            print(f"  {fmt('[SET]  ', ui['success'], True)} {fmt(label.ljust(19), ui['text'])} {fmt(short, ui['muted'])}")
        else:
            print(f"  {fmt('[MISS] ', ui['warning'], True)} {fmt(label.ljust(19), ui['muted'])} {fmt('Not advertised', ui['muted'])}")
    print()


def _is_private_ip(target: str, is_ip: bool) -> bool:
    if not is_ip:
        return target in ("localhost",)
    try:
        ip_obj = ipaddress.ip_address(target)
        return bool(ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local)
    except ValueError:
        return False


def run_osint(raw_target: str, theme: dict, no_vpn: bool = False) -> None:
    ui = theme["ui"]
    target, is_ip = _normalize_target(raw_target)
    if not target:
        print(fmt("  Specify a domain or IP address. Example: osint example.com", ui["warning"]))
        return

    header(f"Passive OSINT Inspector // {target}", theme)
    if not _is_private_ip(target, is_ip):
        ensure_vpn_for_tool("osint", theme, skip_vpn=no_vpn)
    kind = "IP Address" if is_ip else "Domain / Host"
    print(f"  {fmt('Target Type:', ui['muted']):<20} {fmt(kind, ui['primary'], True)}")
    print()

    if is_ip:
        _inspect_ip(target, ui)
        _inspect_rdap(target, True, ui)
    else:
        ips = _inspect_dns(target, ui)
        if ips:
            _inspect_ip(ips[0], ui)
        _inspect_rdap(target, False, ui)
        _inspect_tls(target, ui)
        _inspect_http_headers(target, ui)


def main() -> None:
    enable_vt()
    parser = argparse.ArgumentParser(
        prog="osint",
        description="TricksXTech Passive Public OSINT Inspector (DNS, RDAP, IP/ASN, TLS, HTTP Headers)",
    )
    parser.add_argument("target", nargs="?", help="Domain, URL, or public IP address")
    parser.add_argument("--no-vpn", action="store_true", help="Skip automatic VPN connection for this lookup")
    args = parser.parse_args()
    theme = load_theme()
    target = args.target
    if not target:
        try:
            target = input("  Enter domain or IP to inspect: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
    if target:
        run_osint(target, theme, no_vpn=args.no_vpn)


if __name__ == "__main__":
    main()
