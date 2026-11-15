#!/usr/bin/env python3
"""TricksXTech VPN Manager, VPNGate Sync & Background 5-Minute IP Rotator."""

from __future__ import annotations

import argparse
import base64
import csv
import ctypes
import glob
import io
import json
import os
import random
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, get_root, header, load_theme

DEFAULT_ROTATE_SECONDS = 300  # 5 minutes
MIN_ROTATE_SECONDS = 30
VPNGATE_API_URL = "https://www.vpngate.net/api/iphone/"
VPNGATE_TARGET_COUNT = 16
VPNGATE_MAX_PER_COUNTRY = 3
ROTATION_HEARTBEAT_STALE_SEC = 18.0

_UNSAFE_OVPN_DIRECTIVES = {
    "script-security",
    "up",
    "down",
    "route-up",
    "route-pre-down",
    "tls-verify",
    "ipchange",
    "client-connect",
    "client-disconnect",
    "learn-address",
    "plugin",
    "management",
    "setenv",
    "askpass",
    "auth-user-pass",
}


def _config_dir() -> str:
    return os.path.join(get_root(), "config")


def _vpn_state_path() -> str:
    return os.path.join(_config_dir(), "vpn_state.json")


def _vpn_settings_path() -> str:
    return os.path.join(_config_dir(), "vpn_settings.json")


def _vpn_log_path() -> str:
    return os.path.join(_config_dir(), "vpn_rotator.log")


def _ovpn_log_path() -> str:
    return os.path.join(_config_dir(), "vpn_ovpn.log")


def _mgmt_pw_path() -> str:
    return os.path.join(_config_dir(), ".vpn_mgmt.pw")


def _stop_flag_path() -> str:
    return os.path.join(_config_dir(), "vpn_stop.flag")


def _next_flag_path() -> str:
    return os.path.join(_config_dir(), "vpn_next.flag")


def _ovpn_root_dir() -> str:
    return os.path.join(_config_dir(), "ovpn")


def _ovpn_vpngate_dir() -> str:
    return os.path.join(_ovpn_root_dir(), "vpngate")


def _is_admin() -> bool:
    if os.name != "nt":
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _is_pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        err = ctypes.GetLastError()
        # ERROR_ACCESS_DENIED (5) means the PID exists at a higher integrity level (e.g. elevated UAC).
        return err == 5
    try:
        code = ctypes.c_uint32()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return code.value == STILL_ACTIVE
        return False
    finally:
        kernel32.CloseHandle(handle)


def load_vpn_settings() -> dict:
    defaults = {
        "auto_vpn": True,
        "interval_seconds": DEFAULT_ROTATE_SECONDS,
        "random_order": True,
        "vpngate_auto_sync": True,
    }
    path = _vpn_settings_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                defaults.update(raw)
        except Exception:
            pass
    return defaults


def save_vpn_settings(settings: dict) -> None:
    os.makedirs(_config_dir(), exist_ok=True)
    tmp = _vpn_settings_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, _vpn_settings_path())


def _write_state(state: dict) -> None:
    os.makedirs(_config_dir(), exist_ok=True)
    state["heartbeat"] = time.time()
    tmp = _vpn_state_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, _vpn_state_path())


def _read_raw_state() -> dict | None:
    p = _vpn_state_path()
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def read_active_vpn_state() -> dict | None:
    """Return active daemon state if alive, else None."""
    st = _read_raw_state()
    if not st or not st.get("running"):
        return None
    pid = st.get("pid")
    hb = float(st.get("heartbeat") or 0.0)
    age = time.time() - hb if hb else 9999.0
    if _is_pid_alive(pid) and (age <= ROTATION_HEARTBEAT_STALE_SEC or st.get("status") in ("starting", "connecting", "rotating")):
        return st
    return None


def _append_log(msg: str) -> None:
    os.makedirs(_config_dir(), exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        if os.path.isfile(_vpn_log_path()) and os.path.getsize(_vpn_log_path()) > 512 * 1024:
            with open(_vpn_log_path(), "r", encoding="utf-8", errors="replace") as f:
                tail = f.readlines()[-200:]
            with open(_vpn_log_path(), "w", encoding="utf-8") as f:
                f.writelines(tail)
        with open(_vpn_log_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def _fetch_public_ip(timeout: float = 4.5) -> dict:
    endpoints = (
        ("https://ipinfo.io/json", "ipinfo"),
        ("http://ip-api.com/json/?fields=status,country,regionName,city,isp,org,as,query", "ipapi"),
        ("https://api.ipify.org?format=json", "ipify"),
    )
    for url, kind in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TricksXTech-VPN/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if kind == "ipinfo" and data.get("ip"):
                return {
                    "ip": data.get("ip", "?"),
                    "org": data.get("org", "?"),
                    "loc": ", ".join(p for p in (data.get("city", ""), data.get("region", ""), data.get("country", "")) if p) or "?",
                }
            if kind == "ipapi" and data.get("status") == "success":
                return {
                    "ip": data.get("query", "?"),
                    "org": data.get("as") or data.get("org") or data.get("isp") or "?",
                    "loc": ", ".join(p for p in (data.get("city", ""), data.get("regionName", ""), data.get("country", "")) if p) or "?",
                }
            if kind == "ipify" and data.get("ip"):
                return {"ip": data.get("ip", "?"), "org": "?", "loc": "?"}
        except Exception:
            continue
    return {"ip": "Unavailable", "org": "-", "loc": "-"}


def _get_windows_vpn_profiles() -> list[dict]:
    ps_cmd = (
        "Get-VpnConnection -ErrorAction SilentlyContinue | "
        "Select-Object Name, ServerAddress, TunnelType, ConnectionStatus | "
        "ConvertTo-Json -Compress"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=6,
        )
        raw = (res.stdout or "").strip()
        if not raw:
            return []
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = [parsed]
        return [
            {
                "kind": "winvpn",
                "source": "winvpn",
                "id": f"winvpn:{x.get('Name')}",
                "name": str(x.get("Name", "")),
                "server": str(x.get("ServerAddress", "")),
                "country": "Windows Profile",
                "tunnel": str(x.get("TunnelType", "")),
                "status": str(x.get("ConnectionStatus", "Disconnected")),
            }
            for x in parsed
            if isinstance(x, dict) and x.get("Name")
        ]
    except Exception:
        return []


def _find_openvpn_exe() -> str | None:
    on_path = shutil.which("openvpn")
    if on_path:
        return on_path
    candidates = [
        r"C:\Program Files\OpenVPN\bin\openvpn.exe",
        r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _get_ovpn_configs() -> list[dict]:
    user_home = os.path.expanduser("~")
    vg_dir = os.path.normcase(os.path.abspath(_ovpn_vpngate_dir()))
    search_dirs = [
        _ovpn_root_dir(),
        os.path.join(user_home, "OpenVPN", "config"),
        r"C:\Program Files\OpenVPN\config",
    ]
    found: list[dict] = []
    seen: set[str] = set()
    for base in search_dirs:
        if not os.path.isdir(base):
            continue
        for pat in (os.path.join(base, "*.ovpn"), os.path.join(base, "*", "*.ovpn")):
            for fp in sorted(glob.glob(pat)):
                norm = os.path.abspath(fp)
                key = os.path.normcase(norm)
                if key in seen:
                    continue
                seen.add(key)
                remote = "-"
                country = "-"
                try:
                    with open(norm, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            s = line.strip()
                            low = s.lower()
                            if low.startswith("remote ") and remote == "-":
                                parts = s.split()
                                if len(parts) >= 2:
                                    remote = ":".join(parts[1:3])
                            elif s.startswith("# TX-COUNTRY:"):
                                country = s.split(":", 1)[1].strip()
                except OSError:
                    pass
                src = "vpngate" if os.path.normcase(norm).startswith(vg_dir + os.sep) else "custom"
                found.append(
                    {
                        "kind": "ovpn",
                        "source": src,
                        "id": f"ovpn:{key}",
                        "name": os.path.splitext(os.path.basename(norm))[0],
                        "path": norm,
                        "server": remote,
                        "country": country,
                    }
                )
    # Prefer custom user configs before synced vpngate pool
    found.sort(key=lambda item: (0 if item["source"] == "custom" else 1, item["name"].lower()))
    return found


def _get_dns_summary() -> list[tuple[str, str]]:
    ps_cmd = (
        "Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
        "Where-Object { $_.ServerAddresses.Count -gt 0 } | "
        "ForEach-Object { '{0}|{1}' -f $_.InterfaceAlias, ($_.ServerAddresses -join ', ') }"
    )
    out: list[tuple[str, str]] = []
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=6)
        for line in res.stdout.splitlines():
            if "|" in line:
                iface, servers = line.split("|", 1)
                out.append((iface.strip(), servers.strip()))
    except Exception:
        pass
    return out


def _get_active_vpn_adapters() -> list[str]:
    ps_cmd = (
        "Get-NetAdapter -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Status -eq 'Up' -and ($_.InterfaceDescription -match 'TAP|Wintun|WireGuard|OpenVPN|VPN|PPP|WAN Miniport' -or $_.Name -match 'VPN|WireGuard|OpenVPN') } | "
        "ForEach-Object { '{0} ({1})' -f $_.Name, $_.InterfaceDescription }"
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=6)
        return [l.strip() for l in res.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def _parse_interval(raw: str | None) -> int:
    if not raw:
        return DEFAULT_ROTATE_SECONDS
    s = raw.strip().lower()
    m = re.match(r"^(\d+)\s*([smh]?)$", s)
    if not m:
        return DEFAULT_ROTATE_SECONDS
    val = int(m.group(1))
    unit = m.group(2)
    if unit == "m":
        secs = val * 60
    elif unit == "h":
        secs = val * 3600
    else:
        secs = val
    return max(MIN_ROTATE_SECONDS, secs)


def _list_all_targets() -> tuple[list[dict], str | None]:
    ovpns = _get_ovpn_configs()
    win_vpns = _get_windows_vpn_profiles()
    ovpn_exe = _find_openvpn_exe()
    targets: list[dict] = []
    if ovpn_exe:
        targets.extend(ovpns)
    targets.extend(win_vpns)
    return targets, ovpn_exe


def _sanitize_ovpn_text(raw_text: str) -> str | None:
    out_lines: list[str] = []
    has_remote = False
    has_cert_or_ca = False
    has_cipher = False
    has_data_ciphers = False
    in_pem_block = False

    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<") and stripped.endswith(">"):
            low_tag = stripped.lower()
            if low_tag in ("<ca>", "<cert>", "<key>", "<tls-auth>", "<tls-crypt>"):
                in_pem_block = True
                has_cert_or_ca = True
            elif low_tag.startswith("</"):
                in_pem_block = False
            out_lines.append(line)
            continue

        if in_pem_block:
            out_lines.append(line)
            continue

        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue

        directive = stripped.split(None, 1)[0].lower().lstrip("-")
        if directive in _UNSAFE_OVPN_DIRECTIVES:
            continue

        if directive == "resolv-retry":
            out_lines.append("resolv-retry 8")
            continue

        if directive == "remote":
            has_remote = True
        elif directive == "cipher":
            has_cipher = True
        elif directive == "data-ciphers":
            has_data_ciphers = True

        out_lines.append(stripped)

    if not (has_remote and has_cert_or_ca):
        return None
    if has_cipher and not has_data_ciphers:
        out_lines.append("data-ciphers AES-256-GCM:AES-128-GCM:AES-128-CBC")
    return "\n".join(out_lines) + "\n"


def sync_vpngate_pool(limit: int = VPNGATE_TARGET_COUNT, ui: dict | None = None, quiet: bool = False) -> tuple[int, str | None]:
    """Fetch and sanitize active public academic OpenVPN configs from VPNGate."""
    if ui and not quiet:
        print(f"  {fmt('[VPN]', ui['accent'], True)} {fmt('Syncing live OpenVPN relay pool from University of Tsukuba VPNGate...', ui['text'])}")

    req = urllib.request.Request(VPNGATE_API_URL, headers={"User-Agent": "TricksXTech-VPN/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=14.0) as resp:
            raw_csv = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return 0, f"VPNGate download failed: {exc}"

    lines = [ln for ln in raw_csv.splitlines() if ln and not ln.startswith("*")]
    if not lines:
        return 0, "Empty response from VPNGate feed."
    if lines[0].startswith("#"):
        lines[0] = lines[0][1:]

    candidates: list[dict] = []
    seen_ips: set[str] = set()
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    for row in reader:
        ip = (row.get("IP") or "").strip()
        b64_cfg = (row.get("OpenVPN_ConfigData_Base64") or "").strip()
        if not ip or not b64_cfg or ip in seen_ips:
            continue
        try:
            score = int(row.get("Score") or 0)
        except ValueError:
            score = 0
        try:
            ping = int(row.get("Ping") or 999)
        except ValueError:
            ping = 999
        if score <= 0:
            continue
        try:
            decoded = base64.b64decode(b64_cfg).decode("utf-8", errors="replace")
        except Exception:
            continue
        sanitized = _sanitize_ovpn_text(decoded)
        if not sanitized:
            continue
        cc = re.sub(r"[^A-Za-z0-9]", "", (row.get("CountryShort") or "XX").upper()) or "XX"
        clong = (row.get("CountryLong") or cc).strip()
        # Prefer lower ping + high score
        rank_score = score - (max(0, ping) * 1500)
        seen_ips.add(ip)
        candidates.append(
            {
                "ip": ip,
                "cc": cc,
                "country_long": clong,
                "rank_score": rank_score,
                "score": score,
                "ping": ping,
                "ovpn_text": sanitized,
            }
        )

    if not candidates:
        return 0, "No valid OpenVPN relay configs returned by VPNGate."

    candidates.sort(key=lambda c: c["rank_score"], reverse=True)

    # Select diverse servers across countries
    selected: list[dict] = []
    country_counts: dict[str, int] = {}
    for cand in candidates:
        cnt = country_counts.get(cand["cc"], 0)
        if cnt < VPNGATE_MAX_PER_COUNTRY:
            selected.append(cand)
            country_counts[cand["cc"]] = cnt + 1
            if len(selected) >= limit:
                break
    if len(selected) < limit:
        picked_ips = {c["ip"] for c in selected}
        for cand in candidates:
            if cand["ip"] not in picked_ips:
                selected.append(cand)
                if len(selected) >= limit:
                    break

    vg_dir = _ovpn_vpngate_dir()
    os.makedirs(vg_dir, exist_ok=True)
    for old in glob.glob(os.path.join(vg_dir, "*.ovpn")):
        try:
            os.remove(old)
        except OSError:
            pass

    written = 0
    for cand in selected:
        safe_ip = re.sub(r"[^0-9A-Za-z_-]", "_", cand["ip"])
        fname = f"vg-{cand['cc']}-{safe_ip}.ovpn"
        fpath = os.path.join(vg_dir, fname)
        header_notes = (
            f"# Source: VPNGate Academic Relay (vpngate.net)\n"
            f"# TX-COUNTRY: {cand['country_long']} ({cand['cc']})\n"
            f"# TX-IP: {cand['ip']}\n"
            f"# TX-SCORE: {cand['score']}  PING: {cand['ping']}ms\n"
        )
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(header_notes + cand["ovpn_text"])
            written += 1
        except OSError:
            continue

    _append_log(f"Synced {written} VPNGate OpenVPN configs across {len({c['cc'] for c in selected})} countries.")
    if ui and not quiet:
        countries_str = ", ".join(sorted({c["cc"] for c in selected})[:8])
        print(f"  {fmt('[VPN]', ui['success'], True)} {fmt(f'Synced {written} verified OpenVPN servers ({countries_str}).', ui['text'])}")
    return written, None


def _reserve_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _stop_ovpn_clean(proc: subprocess.Popen | None, mgmt_port: int | None = None, mgmt_pw: str | None = None) -> None:
    if proc is None:
        return
    if proc.poll() is None and mgmt_port and mgmt_pw:
        try:
            with socket.create_connection(("127.0.0.1", int(mgmt_port)), timeout=2.0) as msock:
                msock.settimeout(2.0)
                time.sleep(0.15)
                try:
                    msock.recv(512)
                except OSError:
                    pass
                msock.sendall((mgmt_pw + "\r\n").encode("ascii"))
                time.sleep(0.15)
                try:
                    msock.recv(512)
                except OSError:
                    pass
                msock.sendall(b"signal SIGTERM\r\n")
                time.sleep(0.2)
            proc.wait(timeout=6.0)
            return
        except Exception:
            pass
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5.0)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _disconnect_win_vpns(profiles: list[dict] | None = None) -> None:
    for v in (profiles or []):
        if v.get("status", "").lower() == "connected":
            try:
                subprocess.run(["rasdial", v["name"], "/disconnect"], capture_output=True, text=True, timeout=10)
            except Exception:
                pass
    try:
        subprocess.run(["rasdial", "/disconnect"], capture_output=True, text=True, timeout=8)
    except Exception:
        pass


def _connect_and_verify_target(
    target: dict,
    ovpn_exe: str | None,
    real_ip: str | None,
    prev_vpn_ip: str | None,
) -> tuple[bool, subprocess.Popen | None, int | None, str | None, dict, str]:
    """Connect target endpoint and wait until tunnel handshake + exit IP are verified."""
    if target["kind"] == "winvpn":
        try:
            res = subprocess.run(
                ["rasdial", target["name"]],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=18,
            )
        except Exception as exc:
            return False, None, None, None, {}, f"WinVPN error: {exc}"
        if res.returncode != 0:
            msg = ((res.stdout or "") + " " + (res.stderr or "")).strip().splitlines()
            return False, None, None, None, {}, (msg[-1] if msg else "rasdial failed")
        time.sleep(2.0)
        pub = _fetch_public_ip(timeout=5.0)
        return True, None, None, None, pub, ""

    if not ovpn_exe:
        return False, None, None, None, {}, "OpenVPN executable not found"
    if not _is_admin():
        return False, None, None, None, {}, "OpenVPN requires Administrator privileges"

    mgmt_port = _reserve_free_port()
    mgmt_pw = secrets.token_hex(12)
    os.makedirs(_config_dir(), exist_ok=True)
    with open(_mgmt_pw_path(), "w", encoding="ascii") as f:
        f.write(mgmt_pw + "\n")

    log_path = _ovpn_log_path()
    try:
        with open(log_path, "w", encoding="utf-8") as lf:
            lf.write("")
    except OSError:
        pass

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    cmd = [
        ovpn_exe,
        "--config", target["path"],
        "--verb", "3",
        "--connect-retry-max", "1",
        "--connect-timeout", "10",
        "--resolv-retry", "8",
        "--management", "127.0.0.1", str(mgmt_port), _mgmt_pw_path(),
        "--log", log_path,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )

    deadline = time.monotonic() + 20.0
    connected_ok = False
    fail_reason = "Handshake timeout (20s)"
    while time.monotonic() < deadline:
        if _stop_requested():
            _stop_ovpn_clean(proc, mgmt_port, mgmt_pw)
            return False, None, None, None, {}, "Stopped by user"

        log_txt = ""
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
                log_txt = lf.read()
        except OSError:
            pass

        if "Initialization Sequence Completed" in log_txt:
            connected_ok = True
            break

        for err_marker in (
            "AUTH_FAILED",
            "TLS Error:",
            "TLS key negotiation failed",
            "route addition failed",
            "Cannot open TUN/TAP",
            "Exiting due to fatal error",
            "All TAP-Windows adapters on this system are currently in use",
        ):
            if err_marker in log_txt:
                fail_reason = err_marker
                break
        if fail_reason != "Handshake timeout (20s)":
            break

        if proc.poll() is not None:
            fail_reason = f"OpenVPN exited (code {proc.returncode})"
            break

        time.sleep(0.4)

    if not connected_ok:
        _stop_ovpn_clean(proc, mgmt_port, mgmt_pw)
        return False, None, None, None, {}, fail_reason

    time.sleep(1.5)
    pub = _fetch_public_ip(timeout=6.0)
    new_ip = pub.get("ip", "Unavailable")
    if real_ip and new_ip != "Unavailable" and new_ip == real_ip:
        time.sleep(2.0)
        pub = _fetch_public_ip(timeout=6.0)
        new_ip = pub.get("ip", "Unavailable")
        if new_ip == real_ip:
            _stop_ovpn_clean(proc, mgmt_port, mgmt_pw)
            return False, None, None, None, {}, "Tunnel came up without changing public exit IP"

    if prev_vpn_ip and new_ip != "Unavailable" and new_ip == prev_vpn_ip:
        _stop_ovpn_clean(proc, mgmt_port, mgmt_pw)
        return False, None, None, None, {}, "Endpoint kept identical exit IP"

    return True, proc, mgmt_port, mgmt_pw, pub, ""


def _pick_next_candidates(
    targets: list[dict],
    current_id: str | None,
    current_country: str | None,
    cooldowns: dict[str, float],
    random_order: bool,
) -> list[dict]:
    now = time.time()
    usable = [t for t in targets if t["id"] != current_id and cooldowns.get(t["id"], 0.0) <= now]
    if not usable:
        usable = [t for t in targets if t["id"] != current_id] or list(targets)

    ovpn_diff_country = [
        t for t in usable
        if t["kind"] == "ovpn" and (not current_country or t.get("country") != current_country)
    ]
    ovpn_same_country = [
        t for t in usable
        if t["kind"] == "ovpn" and t not in ovpn_diff_country
    ]
    win_targets = [t for t in usable if t["kind"] != "ovpn"]

    if random_order:
        random.shuffle(ovpn_diff_country)
        random.shuffle(ovpn_same_country)
        random.shuffle(win_targets)

    return ovpn_diff_country + ovpn_same_country + win_targets


def _stop_requested() -> bool:
    return os.path.isfile(_stop_flag_path())


def _clear_control_flags() -> None:
    for p in (_stop_flag_path(), _next_flag_path()):
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass


def _run_daemon_loop(interval_secs: int, random_order: bool) -> None:
    _clear_control_flags()
    _append_log(f"VPN daemon started (PID {os.getpid()}, interval={interval_secs}s, admin={_is_admin()}).")

    targets, ovpn_exe = _list_all_targets()
    ovpn_count = sum(1 for t in targets if t["kind"] == "ovpn")
    if ovpn_count < 2:
        sync_vpngate_pool(limit=VPNGATE_TARGET_COUNT, quiet=True)
        targets, ovpn_exe = _list_all_targets()

    if len(targets) < 2:
        _write_state(
            {
                "pid": os.getpid(),
                "running": False,
                "status": "error",
                "last_error": f"Need >= 2 endpoints, found {len(targets)}.",
            }
        )
        _append_log(f"Exiting: insufficient endpoints ({len(targets)}).")
        return

    real_info = _fetch_public_ip(timeout=4.0)
    real_ip = real_info.get("ip") if real_info.get("ip") != "Unavailable" else None

    cooldowns: dict[str, float] = {}
    current_id: str | None = None
    current_country: str | None = None
    prev_vpn_ip: str | None = None
    ovpn_proc: subprocess.Popen | None = None
    mgmt_port: int | None = None
    mgmt_pw: str | None = None
    rotations = 0
    started_at = time.time()

    try:
        while not _stop_requested():
            _write_state(
                {
                    "pid": os.getpid(),
                    "running": True,
                    "status": "rotating" if rotations > 0 else "connecting",
                    "mode": "daemon",
                    "interval_seconds": interval_secs,
                    "target_name": "-",
                    "target_kind": "-",
                    "target_server": "-",
                    "country": "-",
                    "real_ip": real_ip or "?",
                    "exit_ip": prev_vpn_ip or "-",
                    "exit_org": "-",
                    "exit_loc": "-",
                    "rotations": rotations,
                    "started_at": started_at,
                    "connected_at": None,
                    "next_rotate_at": None,
                    "last_error": "",
                }
            )

            # Tear down previous tunnel cleanly before switching to different server
            _stop_ovpn_clean(ovpn_proc, mgmt_port, mgmt_pw)
            ovpn_proc = None
            mgmt_port = None
            mgmt_pw = None
            _disconnect_win_vpns(_get_windows_vpn_profiles())
            time.sleep(1.0)

            targets, ovpn_exe = _list_all_targets()
            candidates = _pick_next_candidates(targets, current_id, current_country, cooldowns, random_order)
            connected_target = None
            connected_pub: dict = {}
            last_err = "No candidates succeeded"

            for cand in candidates[:6]:
                if _stop_requested():
                    break
                _append_log(f"Trying endpoint {cand['name']} ({cand['server']}, {cand.get('country', '-')})...")
                ok, proc, mport, mpw, pub, err = _connect_and_verify_target(cand, ovpn_exe, real_ip, prev_vpn_ip)
                if ok:
                    connected_target = cand
                    ovpn_proc = proc
                    mgmt_port = mport
                    mgmt_pw = mpw
                    connected_pub = pub
                    last_err = ""
                    break
                cooldowns[cand["id"]] = time.time() + 180.0
                last_err = f"{cand['name']}: {err}"
                _append_log(f"Skipped {last_err}")

            if _stop_requested():
                break

            if not connected_target:
                _append_log(f"All candidates failed this round ({last_err}); refreshing VPNGate pool...")
                sync_vpngate_pool(limit=VPNGATE_TARGET_COUNT, quiet=True)
                _write_state(
                    {
                        "pid": os.getpid(),
                        "running": True,
                        "status": "retrying",
                        "mode": "daemon",
                        "interval_seconds": interval_secs,
                        "real_ip": real_ip or "?",
                        "exit_ip": "Disconnected",
                        "rotations": rotations,
                        "started_at": started_at,
                        "last_error": last_err,
                    }
                )
                for _ in range(10):
                    if _stop_requested():
                        break
                    time.sleep(1.0)
                continue

            now = time.time()
            rotations += 1
            current_id = connected_target["id"]
            current_country = connected_target.get("country")
            prev_vpn_ip = connected_pub.get("ip", "Unavailable")
            next_rotate_at = now + interval_secs

            _append_log(
                f"Connected #{rotations}: {connected_target['name']} | Exit IP: {prev_vpn_ip} | Loc: {connected_pub.get('loc', '-')}"
            )

            end_at = time.monotonic() + interval_secs
            while time.monotonic() < end_at:
                if _stop_requested():
                    break
                if os.path.isfile(_next_flag_path()):
                    try:
                        os.remove(_next_flag_path())
                    except OSError:
                        pass
                    _append_log("Manual switch requested (vpn next); rotating to next server now.")
                    break
                if ovpn_proc is not None and ovpn_proc.poll() is not None:
                    _append_log(f"OpenVPN tunnel dropped early (code {ovpn_proc.returncode}); switching immediately.")
                    cooldowns[current_id] = time.time() + 120.0
                    break

                _write_state(
                    {
                        "pid": os.getpid(),
                        "running": True,
                        "status": "connected",
                        "mode": "daemon",
                        "interval_seconds": interval_secs,
                        "target_name": connected_target["name"],
                        "target_kind": connected_target["kind"],
                        "target_server": connected_target["server"],
                        "country": connected_target.get("country", "-"),
                        "real_ip": real_ip or "?",
                        "exit_ip": prev_vpn_ip,
                        "exit_org": connected_pub.get("org", "-"),
                        "exit_loc": connected_pub.get("loc", "-"),
                        "rotations": rotations,
                        "started_at": started_at,
                        "connected_at": now,
                        "next_rotate_at": next_rotate_at,
                        "last_error": "",
                    }
                )
                time.sleep(1.0)
    finally:
        _append_log("Shutting down VPN daemon cleanly and restoring direct routes...")
        _stop_ovpn_clean(ovpn_proc, mgmt_port, mgmt_pw)
        _disconnect_win_vpns(_get_windows_vpn_profiles())
        _clear_control_flags()
        try:
            if os.path.isfile(_mgmt_pw_path()):
                os.remove(_mgmt_pw_path())
        except OSError:
            pass
        _write_state(
            {
                "pid": None,
                "running": False,
                "status": "stopped",
                "rotations": rotations,
                "last_error": "",
            }
        )


def _find_pythonw() -> str:
    py_dir = os.path.dirname(os.path.abspath(sys.executable))
    pyw = os.path.join(py_dir, "pythonw.exe")
    if os.path.isfile(pyw):
        return pyw
    return sys.executable


def _spawn_daemon(interval_secs: int, random_order: bool) -> tuple[bool, str]:
    pyw = _find_pythonw()
    script_path = os.path.abspath(__file__)
    args = f'"{script_path}" --daemon --interval {interval_secs}' + (" --random" if random_order else "")

    _clear_control_flags()
    _write_state(
        {
            "pid": None,
            "running": True,
            "status": "starting",
            "mode": "daemon",
            "interval_seconds": interval_secs,
            "last_error": "",
        }
    )

    if _is_admin() or os.name != "nt":
        cmd = [pyw, script_path, "--daemon", "--interval", str(interval_secs)]
        if random_order:
            cmd.append("--random")
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        proc = subprocess.Popen(
            cmd,
            cwd=get_root(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        return True, f"Started background daemon (PID {proc.pid})."

    # Non-elevated terminal: request one-time Windows UAC consent so OpenVPN can manage TAP routes cleanly.
    shell32 = ctypes.windll.shell32
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    ret = shell32.ShellExecuteW(None, "runas", pyw, args, get_root(), 0)
    ret_val = int(ret or 0)
    if ret_val <= 32:
        _write_state({"pid": None, "running": False, "status": "stopped", "last_error": f"UAC declined or ShellExecute error {ret_val}"})
        return False, "Windows UAC consent declined or failed (OpenVPN requires Admin once for tunnel routing)."
    return True, "Launched elevated background VPN rotator daemon."


def start_background_rotator(interval_secs: int | None = None, random_order: bool | None = None, ui: dict | None = None, wait_connected: bool = True) -> dict | None:
    """Ensure the 5-minute VPN rotator daemon is running and connected."""
    existing = read_active_vpn_state()
    if existing and existing.get("status") == "connected":
        return existing

    settings = load_vpn_settings()
    iv = interval_secs if interval_secs is not None else int(settings.get("interval_seconds", DEFAULT_ROTATE_SECONDS))
    rnd = random_order if random_order is not None else bool(settings.get("random_order", True))

    ovpns = _get_ovpn_configs()
    if len(ovpns) < 2 and settings.get("vpngate_auto_sync", True):
        cnt, err = sync_vpngate_pool(limit=VPNGATE_TARGET_COUNT, ui=ui, quiet=(ui is None))
        if err and ui:
            print(f"  {fmt('[VPN Sync Warning]', ui['warning'], True)} {fmt(err, ui['muted'])}")

    targets, ovpn_exe = _list_all_targets()
    if len(targets) < 2:
        if ui:
            print(f"  {fmt('[VPN Error]', ui['error'], True)} {fmt('Fewer than 2 VPN profiles/.ovpn configs available.', ui['text'])}")
        return None

    if existing and existing.get("status") in ("starting", "connecting", "rotating"):
        if ui:
            print(f"  {fmt('[VPN]', ui['accent'], True)} {fmt('VPN rotator already handshaking; waiting for tunnel...', ui['text'])}")
    else:
        if ui and not _is_admin():
            print(f"  {fmt('[VPN]', ui['accent'], True)} {fmt('Starting 5-min VPN rotator (approve UAC prompt once if asked)...', ui['text'])}")
        elif ui:
            print(f"  {fmt('[VPN]', ui['accent'], True)} {fmt(f'Connecting VPN + starting {iv // 60}m background rotator...', ui['text'])}")

        ok, msg = _spawn_daemon(iv, rnd)
        if not ok:
            if ui:
                print(f"  {fmt('[VPN Warning]', ui['warning'], True)} {fmt(msg, ui['text'])}")
            return None

    if not wait_connected:
        return read_active_vpn_state()

    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        st = _read_raw_state()
        if st:
            status = st.get("status")
            if status == "connected" and _is_pid_alive(st.get("pid")):
                return st
            if status in ("error", "stopped") and not st.get("running"):
                if ui:
                    print(f"  {fmt('[VPN Warning]', ui['warning'], True)} {fmt(st.get('last_error') or 'Rotator stopped before connecting.', ui['text'])}")
                return None
        time.sleep(0.45)

    if ui:
        print(f"  {fmt('[VPN Warning]', ui['warning'], True)} {fmt('VPN still handshaking or blocked (run vpn log to inspect).', ui['text'])}")
    return _read_raw_state()


def _format_countdown(next_rotate_at: float | None) -> str:
    if not next_rotate_at:
        return "--:--"
    rem = max(0, int(next_rotate_at - time.time()))
    m, s = divmod(rem, 60)
    return f"{m:02d}m {s:02d}s"


def vpn_badge_line(state: dict, ui: dict) -> str:
    srv = state.get("target_name", "?")
    ip = state.get("exit_ip", "?")
    loc = state.get("exit_loc") or state.get("country") or "-"
    cnt = state.get("rotations", 1)
    cd = _format_countdown(state.get("next_rotate_at"))
    return (
        f"  {fmt('[VPN ACTIVE]', ui['success'], True)} "
        f"{fmt(srv, ui['primary'], True)} -> IP: {fmt(ip, ui['accent'], True)} ({loc}) "
        f"| Swap #{cnt + 1} in {fmt(cd, ui['secondary'], True)}"
    )


def ensure_vpn_for_tool(tool_name: str, theme: dict, skip_vpn: bool = False) -> dict | None:
    """Ensure active rotating VPN before running external network/OSINT tools when auto_vpn is ON."""
    if skip_vpn or os.environ.get("TX_NO_VPN") == "1":
        return None
    ui = theme["ui"]
    settings = load_vpn_settings()
    active = read_active_vpn_state()

    if active and active.get("status") == "connected":
        print(vpn_badge_line(active, ui))
        return active

    if active and active.get("status") in ("connecting", "rotating", "starting"):
        print(f"  {fmt('[VPN]', ui['accent'], True)} {fmt('Waiting for VPN IP rotation swap to complete...', ui['text'])}")
        st = start_background_rotator(ui=ui, wait_connected=True)
        if st and st.get("status") == "connected":
            print(vpn_badge_line(st, ui))
            return st
        print(f"  {fmt('[VPN Warning]', ui['warning'], True)} {fmt(f'{tool_name} continuing direct (VPN swap pending).', ui['muted'])}")
        return None

    if not settings.get("auto_vpn", True):
        return None

    st = start_background_rotator(ui=ui, wait_connected=True)
    if st and st.get("status") == "connected":
        print(vpn_badge_line(st, ui))
        return st

    msg = f'{tool_name} running direct (use "vpn start" in Admin terminal or "vpn auto off").'
    print(f"  {fmt('[DIRECT / NO VPN]', ui['warning'], True)} {fmt(msg, ui['muted'])}")
    return None


def _cmd_stop(ui: dict) -> None:
    st = read_active_vpn_state()
    if st:
        os.makedirs(_config_dir(), exist_ok=True)
        with open(_stop_flag_path(), "w", encoding="ascii") as f:
            f.write("stop\n")
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if not read_active_vpn_state():
                break
            time.sleep(0.3)
    _disconnect_win_vpns(_get_windows_vpn_profiles())
    _write_state({"pid": None, "running": False, "status": "stopped", "last_error": ""})
    print(f"  {fmt('[VPN]', ui['success'], True)} {fmt('Background VPN rotator stopped & tunnel disconnected cleanly.', ui['text'])}")


def _cmd_next(ui: dict) -> None:
    st = read_active_vpn_state()
    if not st:
        print(f"  {fmt('No running background rotator. Starting now...', ui['warning'])}")
        res = start_background_rotator(ui=ui, wait_connected=True)
        if res and res.get("status") == "connected":
            print(vpn_badge_line(res, ui))
        return
    prev_rot = int(st.get("rotations") or 0)
    os.makedirs(_config_dir(), exist_ok=True)
    with open(_next_flag_path(), "w", encoding="ascii") as f:
        f.write("next\n")
    print(f"  {fmt('[VPN]', ui['accent'], True)} {fmt('Switching to a different VPN server & new IP...', ui['text'])}")
    deadline = time.monotonic() + 28.0
    while time.monotonic() < deadline:
        cur = _read_raw_state()
        if cur and cur.get("status") == "connected" and int(cur.get("rotations") or 0) > prev_rot:
            print(vpn_badge_line(cur, ui))
            return
        time.sleep(0.45)
    print(f"  {fmt('[VPN Warning]', ui['warning'], True)} {fmt('Switch still in progress (check vpn or vpn log in a moment).', ui['text'])}")


def _cmd_status(theme: dict) -> None:
    ui = theme["ui"]
    header("VPN Status, Exit IP & 5-Min Auto-Rotator", theme)

    settings = load_vpn_settings()
    active_daemon = read_active_vpn_state()
    pub = _fetch_public_ip(timeout=4.5)
    adapters = _get_active_vpn_adapters()
    win_vpns = _get_windows_vpn_profiles()
    ovpns = _get_ovpn_configs()
    ovpn_exe = _find_openvpn_exe()
    connected_win = [v["name"] for v in win_vpns if v["status"].lower() == "connected"]

    tunnel_up = bool(adapters or connected_win or (active_daemon and active_daemon.get("status") == "connected"))
    st_label = "VPN TUNNEL ACTIVE" if tunnel_up else "DIRECT / NO ACTIVE VPN TUNNEL"
    st_color = ui["success"] if tunnel_up else ui["warning"]

    auto_lbl = "ON (tools auto-connect & rotate every 5m)" if settings.get("auto_vpn", True) else "OFF (manual vpn start / rotate)"
    auto_clr = ui["success"] if settings.get("auto_vpn", True) else ui["muted"]

    print(f"  {fmt('Tunnel State:'.ljust(17), ui['muted'])} {fmt('[' + st_label + ']', st_color, True)}")
    print(f"  {fmt('Public Exit IP:'.ljust(17), ui['muted'])} {fmt(pub['ip'], ui['primary'], True)}   {fmt('ASN/ISP:', ui['muted'])} {fmt(pub['org'], ui['text'])}")
    print(f"  {fmt('Geo Location:'.ljust(17), ui['muted'])} {fmt(pub['loc'], ui['accent'])}")
    print(f"  {fmt('Auto-VPN Mode:'.ljust(17), ui['muted'])} {fmt(auto_lbl, auto_clr, True)}")
    if adapters:
        print(f"  {fmt('Active Adapter:'.ljust(17), ui['muted'])} {fmt(', '.join(adapters[:3]), ui['success'])}")

    if active_daemon:
        cd = _format_countdown(active_daemon.get("next_rotate_at"))
        srv = active_daemon.get("target_name", "?")
        rot = active_daemon.get("rotations", 0)
        iv = int(active_daemon.get("interval_seconds") or DEFAULT_ROTATE_SECONDS)
        print(f"  {fmt('Daemon State:'.ljust(17), ui['muted'])} {fmt('RUNNING', ui['success'], True)} (PID {active_daemon.get('pid')})  Server: {fmt(srv, ui['accent'])}  Swaps: {rot}  Every: {iv // 60}m")
        print(f"  {fmt('Next Rotate In:'.ljust(17), ui['muted'])} {fmt(cd, ui['primary'], True)}   Real IP saved: {fmt(str(active_daemon.get('real_ip', '?')), ui['muted'])}")

    dns_rows = _get_dns_summary()
    if dns_rows:
        print()
        print("  " + fmt("ACTIVE DNS SERVERS (LEAK CHECK)", ui["secondary"], True))
        for iface, srvs in dns_rows[:5]:
            print(f"  {fmt(iface.ljust(22), ui['muted'])} {fmt(srvs, ui['text'])}")

    print()
    print("  " + fmt("CONFIGURED VPN PROFILES & .OVPN ENDPOINTS", ui["secondary"], True))
    total_count = len(win_vpns) + (len(ovpns) if ovpn_exe else 0)
    idx = 1
    for v in win_vpns:
        sc = ui["success"] if v["status"].lower() == "connected" else ui["muted"]
        print(f"  {fmt('[' + str(idx) + ']', ui['accent'], True)} {fmt('WinVPN'.ljust(8), ui['primary'])} {fmt(v['name'].ljust(20), ui['text'], True)} {fmt(v['server'].ljust(26), ui['muted'])} {fmt('[' + v['status'] + ']', sc)}")
        idx += 1
    shown_ovpns = ovpns[:18]
    for o in shown_ovpns:
        tag = ("OpenVPN" if ovpn_exe else "NoExe  ")
        src_col = ui["accent"] if o["source"] == "custom" else ui["secondary"]
        ctry = o.get("country") or o["source"]
        print(f"  {fmt('[' + str(idx) + ']', ui['accent'], True)} {fmt(tag.ljust(8), src_col)} {fmt(o['name'].ljust(20), ui['text'], True)} {fmt(o['server'].ljust(22), ui['muted'])} {fmt(ctry, ui['muted'])}")
        idx += 1
    if len(ovpns) > len(shown_ovpns):
        print(f"  {fmt(f'... and {len(ovpns) - len(shown_ovpns)} more .ovpn endpoints.', ui['muted'])}")
    if not win_vpns and not ovpns:
        print("  " + fmt("No VPN profiles or .ovpn configs found yet.", ui["muted"]))

    print()
    if total_count < 2:
        need_msg = f'{total_count} endpoint(s) ready. Run "vpn sync" or "vpn start" to fetch VPNGate servers!'
        print(f"  {fmt('Rotation Status:', ui['warning'], True)} {fmt(need_msg, ui['text'])}")
    else:
        print(f"  {fmt('Rotation Pool:', ui['success'], True)} {fmt(f'{total_count} endpoint(s) ready ({len(ovpns)} OpenVPN, {len(win_vpns)} WinVPN).', ui['text'])}")
    print(f"  {fmt('Commands:', ui['muted'])}  {fmt('vpn start', ui['primary'], True)} (bg 5m rotate) | {fmt('vpn next', ui['accent'])} | {fmt('vpn stop', ui['warning'])} | {fmt('vpn sync', ui['secondary'])} | {fmt('vpn auto on|off', ui['muted'])}")
    print()


def _resolve_target(spec: str, targets: list[dict]) -> dict | None:
    s = spec.strip().lower()
    if s.isdigit():
        i = int(s) - 1
        if 0 <= i < len(targets):
            return targets[i]
    for t in targets:
        if t["name"].lower() == s:
            return t
    return None


def _cmd_rotate_foreground(interval_secs: int, random_order: bool, theme: dict) -> None:
    ui = theme["ui"]
    header(f"Foreground VPN Exit IP Rotator (Every {interval_secs // 60}m {interval_secs % 60}s)", theme)

    ovpns = _get_ovpn_configs()
    if len(ovpns) < 2 and load_vpn_settings().get("vpngate_auto_sync", True):
        sync_vpngate_pool(limit=VPNGATE_TARGET_COUNT, ui=ui)

    targets, ovpn_exe = _list_all_targets()
    if len(targets) < 2:
        print(f"  {fmt('Cannot start IP rotation:', ui['warning'], True)} Found {len(targets)} usable endpoint(s).")
        return

    if any(t["kind"] == "ovpn" for t in targets) and not _is_admin():
        print(f"  {fmt('Admin Note:', ui['warning'], True)} Non-admin terminal cannot bind OpenVPN TUN routes; prefer 'vpn start' to elevate cleanly once.")

    real_info = _fetch_public_ip(timeout=4.0)
    real_ip = real_info.get("ip") if real_info.get("ip") != "Unavailable" else None
    cooldowns: dict[str, float] = {}
    current_id: str | None = None
    current_country: str | None = None
    prev_vpn_ip: str | None = None
    ovpn_proc: subprocess.Popen | None = None
    mgmt_port: int | None = None
    mgmt_pw: str | None = None

    print(f"  {fmt('Endpoints loaded:', ui['muted'])} {fmt(str(len(targets)), ui['primary'], True)}   {fmt('Interval:', ui['muted'])} {fmt(f'{interval_secs}s', ui['accent'], True)}   {fmt('Ctrl+C to stop & disconnect', ui['muted'])}")
    print(fmt("  " + "─" * 74, ui["border"]))

    try:
        while True:
            _stop_ovpn_clean(ovpn_proc, mgmt_port, mgmt_pw)
            ovpn_proc = None
            mgmt_port = None
            mgmt_pw = None
            _disconnect_win_vpns(_get_windows_vpn_profiles())
            time.sleep(1.0)

            candidates = _pick_next_candidates(targets, current_id, current_country, cooldowns, random_order)
            chosen = None
            pub: dict = {}
            for cand in candidates[:6]:
                print(f"  {fmt('Trying:', ui['muted'])} {fmt(cand['name'], ui['accent'])} ({cand.get('country', '-')})...")
                ok, proc, mport, mpw, pub_res, err = _connect_and_verify_target(cand, ovpn_exe, real_ip, prev_vpn_ip)
                if ok:
                    chosen = cand
                    ovpn_proc = proc
                    mgmt_port = mport
                    mgmt_pw = mpw
                    pub = pub_res
                    break
                cooldowns[cand["id"]] = time.time() + 180.0
                print(f"  {fmt('Skipped:', ui['warning'])} {cand['name']} ({err})")

            if not chosen:
                print(f"  {fmt('No endpoints connected this round. Retrying in 10s...', ui['error'])}")
                time.sleep(10.0)
                continue

            current_id = chosen["id"]
            current_country = chosen.get("country")
            prev_vpn_ip = pub.get("ip", "Unavailable")
            ts = time.strftime("%H:%M:%S")
            print(f"  {fmt('[' + ts + ']', ui['muted'])} {fmt(chosen['name'].ljust(22), ui['secondary'], True)} -> IP: {fmt(prev_vpn_ip, ui['success'], True)}  ({fmt(pub.get('loc', '-'), ui['text'])})")

            end_at = time.monotonic() + interval_secs
            while time.monotonic() < end_at:
                if ovpn_proc is not None and ovpn_proc.poll() is not None:
                    print(f"  {fmt('Tunnel dropped early; switching to different server...', ui['warning'])}")
                    break
                time.sleep(1.0)
    except KeyboardInterrupt:
        print()
        print("  " + fmt("Stopping rotation and disconnecting VPN tunnel...", ui["warning"], True))
    finally:
        _stop_ovpn_clean(ovpn_proc, mgmt_port, mgmt_pw)
        _disconnect_win_vpns(_get_windows_vpn_profiles())
        print("  " + fmt("VPN disconnected cleanly.", ui["success"]))
        print()


def _cmd_log(theme: dict) -> None:
    ui = theme["ui"]
    header("VPN Rotator History Log", theme)
    if not os.path.isfile(_vpn_log_path()):
        print("  " + fmt("No VPN rotation log yet. Start with 'vpn start'.", ui["muted"]))
        print()
        return
    with open(_vpn_log_path(), "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()[-30:]
    for ln in lines:
        s = ln.rstrip("\r\n")
        col = ui["success"] if "Connected #" in s else (ui["warning"] if ("Skipped" in s or "dropped" in s) else ui["text"])
        print("  " + fmt(s, col))
    print()


def main() -> None:
    enable_vt()
    p = argparse.ArgumentParser(
        prog="vpn",
        description="TricksXTech VPN Manager, VPNGate Sync & 5-Min Auto-Rotator",
    )
    p.add_argument("action", nargs="?", default="status", help="status | start | stop | down | next | sync | auto | list | up | rotate | log")
    p.add_argument("arg", nargs="?", default="", help="Interval (5m), on|off (for auto), or profile name/# (for up)")
    p.add_argument("--random", action="store_true", help="Shuffle endpoint rotation order")
    p.add_argument("--daemon", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--interval", type=int, default=0, help=argparse.SUPPRESS)
    args = p.parse_args()

    if args.daemon:
        iv = args.interval if args.interval >= MIN_ROTATE_SECONDS else int(load_vpn_settings().get("interval_seconds", DEFAULT_ROTATE_SECONDS))
        rnd = bool(args.random or load_vpn_settings().get("random_order", True))
        _run_daemon_loop(iv, rnd)
        return

    theme = load_theme()
    ui = theme["ui"]
    act = args.action.lower().strip()

    if act in ("status", "check", "ip", "list"):
        _cmd_status(theme)
    elif act == "sync":
        cnt, err = sync_vpngate_pool(limit=VPNGATE_TARGET_COUNT, ui=ui)
        if err:
            print(f"  {fmt('[VPN Sync Error]', ui['error'], True)} {fmt(err, ui['text'])}")
    elif act == "start":
        iv = _parse_interval(args.arg) if args.arg else None
        if iv is not None:
            st_cfg = load_vpn_settings()
            st_cfg["interval_seconds"] = iv
            save_vpn_settings(st_cfg)
        res = start_background_rotator(interval_secs=iv, random_order=(True if args.random else None), ui=ui, wait_connected=True)
        if res and res.get("status") == "connected":
            print(vpn_badge_line(res, ui))
    elif act in ("stop", "down"):
        _cmd_stop(ui)
    elif act in ("next", "switch"):
        _cmd_next(ui)
    elif act == "auto":
        st_cfg = load_vpn_settings()
        val = args.arg.lower().strip()
        if val in ("on", "true", "1", "enable"):
            st_cfg["auto_vpn"] = True
            save_vpn_settings(st_cfg)
            print(f"  {fmt('[VPN Auto]', ui['success'], True)} {fmt('Auto-VPN ENABLED — network tools will connect & rotate every 5m.', ui['text'])}")
        elif val in ("off", "false", "0", "disable"):
            st_cfg["auto_vpn"] = False
            save_vpn_settings(st_cfg)
            print(f"  {fmt('[VPN Auto]', ui['warning'], True)} {fmt('Auto-VPN DISABLED - tools run direct unless you run vpn start.', ui['text'])}")
        else:
            cur = "ON" if st_cfg.get("auto_vpn", True) else "OFF"
            print(f"  {fmt('Auto-VPN is currently:', ui['muted'])} {fmt(cur, ui['primary'], True)}  (toggle: vpn auto on | vpn auto off)")
    elif act == "log":
        _cmd_log(theme)
    elif act == "up":
        targets, ovpn_exe = _list_all_targets()
        if not args.arg:
            print(fmt("  Specify profile name or # (run 'vpn list' to view).", ui["warning"]))
            return
        t = _resolve_target(args.arg, targets)
        if not t:
            print(fmt(f"  Profile '{args.arg}' not found. Run 'vpn list'.", ui["error"]))
            return
        ok, proc, mport, mpw, pub, err = _connect_and_verify_target(t, ovpn_exe, None, None)
        if not ok:
            print(f"  {fmt('Failed:', ui['error'], True)} {fmt(err, ui['warning'])}")
            return
        print(f"  {fmt('Connected:', ui['success'], True)} {t['name']} -> Exit IP: {fmt(pub.get('ip', '?'), ui['accent'], True)} ({pub.get('loc', '-')})")
        if proc is not None:
            print("  " + fmt("OpenVPN running in foreground; press Ctrl+C to disconnect cleanly.", ui["muted"]))
            try:
                proc.wait()
            except KeyboardInterrupt:
                _stop_ovpn_clean(proc, mport, mpw)
    elif act == "rotate":
        secs = _parse_interval(args.arg)
        _cmd_rotate_foreground(secs, bool(args.random or load_vpn_settings().get("random_order", True)), theme)
    else:
        print(fmt(f"  Unknown action '{act}'. Try: vpn | vpn start | vpn stop | vpn next | vpn sync | vpn auto on|off | vpn log", ui["warning"]))


if __name__ == "__main__":
    main()
