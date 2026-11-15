#!/usr/bin/env python3
"""TricksXTech Wi-Fi Diagnostics, Signal & Security Checker (read-only)."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, header, load_theme


def _run_netsh(args: list[str]) -> tuple[int, str]:
    try:
        res = subprocess.run(
            ["netsh", "wlan"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        out = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
        return res.returncode, out
    except FileNotFoundError:
        return 127, "netsh.exe not found (Windows WLAN diagnostic requires netsh)."
    except subprocess.TimeoutExpired:
        return 124, "Timed out querying Windows WLAN AutoConfig service."
    except Exception as exc:
        return 1, str(exc)


def _channel_band(ch_str: str, radio: str = "") -> tuple[int | None, str]:
    m = re.search(r"\d+", ch_str or "")
    if not m:
        return None, "?"
    ch = int(m.group(0))
    r_low = (radio or "").lower()
    if "be" in r_low and ch <= 233:
        # Channel numbers in netsh distinguish 2.4 / 5 / 6 partially; annotate carefully
        pass
    if 1 <= ch <= 14:
        return ch, "2.4 GHz"
    if 32 <= ch <= 177:
        return ch, "5 GHz"
    if ch > 177:
        return ch, "6 GHz"
    return ch, "Unknown"


def _signal_bar(pct: int, ui: dict, width: int = 12) -> str:
    pct = max(0, min(100, pct))
    filled = round((pct / 100.0) * width)
    bar = "█" * filled + "░" * (width - filled)
    if pct >= 70:
        c = ui["success"]
    elif pct >= 40:
        c = ui["warning"]
    else:
        c = ui["error"]
    return fmt(bar, c) + " " + fmt(f"{pct:>3}%", c, True)


def _security_grade(auth: str, cipher: str) -> tuple[str, str]:
    a = (auth or "").upper()
    c = (cipher or "").upper()
    if "WPA3" in a or "SAE" in a:
        return "STRONG", "success"
    if "WPA2" in a:
        if "TKIP" in c and "CCMP" not in c:
            return "WARN  ", "warning"
        return "GOOD  ", "success"
    if "OPEN" in a or "NONE" in c:
        return "OPEN  ", "error"
    if "WEP" in a or "WEP" in c:
        return "WEAK  ", "error"
    if "WPA" in a:
        return "LEGACY", "warning"
    return "INFO  ", "muted"


def _parse_kv_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if cur:
                blocks.append(cur)
                cur = {}
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k:
                # Start new block if 'Name' repeats cleanly
                if k == "Name" and cur:
                    blocks.append(cur)
                    cur = {}
                cur[k] = v
    if cur:
        blocks.append(cur)
    # Filter to blocks that look like interfaces (have Name or State)
    return [b for b in blocks if "State" in b or "Name" in b or "SSID" in b]


def _parse_networks(text: str) -> list[dict]:
    networks: list[dict] = []
    cur_net: dict | None = None
    cur_bssid: dict | None = None

    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        m_ssid = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", s)
        if m_ssid:
            if cur_net is not None:
                if cur_bssid:
                    cur_net["bssids"].append(cur_bssid)
                    cur_bssid = None
                networks.append(cur_net)
            ssid_name = m_ssid.group(1).strip() or "<Hidden SSID>"
            cur_net = {
                "ssid": ssid_name,
                "network_type": "",
                "auth": "",
                "cipher": "",
                "bssids": [],
            }
            continue

        if cur_net is None or ":" not in s:
            continue

        k, v = [p.strip() for p in s.split(":", 1)]
        if re.match(r"^BSSID\s+\d+$", k):
            if cur_bssid:
                cur_net["bssids"].append(cur_bssid)
            cur_bssid = {"bssid": v, "signal": 0, "radio": "", "channel": "", "band": ""}
        elif cur_bssid is not None:
            kl = k.lower()
            if kl == "signal":
                m_pct = re.search(r"(\d+)", v)
                cur_bssid["signal"] = int(m_pct.group(1)) if m_pct else 0
            elif kl == "radio type":
                cur_bssid["radio"] = v
            elif kl == "channel":
                cur_bssid["channel"] = v
            elif kl == "band":
                cur_bssid["band"] = v
        else:
            kl = k.lower()
            if kl == "network type":
                cur_net["network_type"] = v
            elif kl == "authentication":
                cur_net["auth"] = v
            elif kl == "encryption":
                cur_net["cipher"] = v

    if cur_net is not None:
        if cur_bssid:
            cur_net["bssids"].append(cur_bssid)
        networks.append(cur_net)
    return networks


def _parse_saved_profiles(text: str) -> list[str]:
    profiles: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^\s*All User Profile\s*:\s*(.+)$", line)
        if m:
            profiles.append(m.group(1).strip())
    return profiles


def run_wifi_check(theme: dict, show_profiles: bool = False) -> None:
    ui = theme["ui"]
    header("Wi-Fi Signal, Channel & Security Checker", theme)

    # 1. Active interface(s)
    rc_if, out_if = _run_netsh(["show", "interfaces"])
    if "no wireless interface" in out_if.lower() or "wlansvc" in out_if.lower() and rc_if != 0:
        print("  " + fmt("No active Windows wireless interface detected.", ui["warning"], True))
        print("  " + fmt(out_if.strip().splitlines()[0] if out_if.strip() else "Check adapter or WLAN AutoConfig service.", ui["muted"]))
        print()
        return

    ifaces = _parse_kv_blocks(out_if)
    print("  " + fmt("ACTIVE WI-FI INTERFACE", ui["secondary"], True))
    if not ifaces:
        print("  " + fmt("Could not parse interface state.", ui["muted"]))
    for iface in ifaces:
        name = iface.get("Name", "Wi-Fi")
        state = iface.get("State", "unknown")
        desc = iface.get("Description", "")
        st_color = ui["success"] if state.lower() == "connected" else ui["warning"]
        print(f"  {fmt('Adapter:', ui['muted'])} {fmt(name, ui['primary'], True)}  {fmt('[' + state.upper() + ']', st_color, True)}  {fmt(desc, ui['muted'])}")
        if state.lower() == "connected":
            ssid = iface.get("SSID", "?")
            bssid = iface.get("AP BSSID", iface.get("BSSID", "?"))
            radio = iface.get("Radio type", "?")
            auth = iface.get("Authentication", "?")
            cipher = iface.get("Cipher", "?")
            ch_raw = iface.get("Channel", "?")
            band_explicit = iface.get("Band", "")
            ch_num, band_guess = _channel_band(ch_raw, radio)
            band = band_explicit or band_guess
            rx = iface.get("Receive rate (Mbps)", "?")
            tx = iface.get("Transmit rate (Mbps)", "?")
            sig_m = re.search(r"(\d+)", iface.get("Signal", "0"))
            sig_pct = int(sig_m.group(1)) if sig_m else 0
            grade, g_key = _security_grade(auth, cipher)

            print(f"  {fmt('SSID:', ui['muted']):<19} {fmt(ssid, ui['text'], True)}   {fmt('BSSID:', ui['muted'])} {fmt(bssid, ui['muted'])}")
            print(f"  {fmt('Signal:', ui['muted']):<19} {_signal_bar(sig_pct, ui)}   {fmt('Band/Ch:', ui['muted'])} {fmt(f'{band} (Ch {ch_raw})', ui['accent'], True)}")
            print(f"  {fmt('Link Speed:', ui['muted']):<19} {fmt(f'Rx {rx} Mbps / Tx {tx} Mbps', ui['text'])}   {fmt('Radio:', ui['muted'])} {fmt(radio, ui['muted'])}")
            print(f"  {fmt('Security:', ui['muted']):<19} {fmt(f'{auth} / {cipher}', ui['text'])}   {fmt('[' + grade.strip() + ']', ui[g_key], True)}")

    print()

    # 2. Nearby BSSID scan
    rc_net, out_net = _run_netsh(["show", "networks", "mode=bssid"])
    print("  " + fmt("NEARBY NETWORKS & SECURITY AUDIT", ui["secondary"], True))
    if rc_net != 0:
        msg = out_net.strip().splitlines()[0] if out_net.strip() else "Scan failed."
        print("  " + fmt(msg, ui["warning"]))
        print("  " + fmt("Tip: Enable Windows Location access for Desktop apps if nearby scan returns blocked.", ui["muted"]))
        print()
        return

    networks = _parse_networks(out_net)
    if not networks:
        print("  " + fmt("No nearby Wi-Fi networks reported by adapter.", ui["muted"]))
    else:
        rows: list[tuple[int, str, int | None, str, str, str, str, str]] = []
        ch24_counts: dict[int, int] = {c: 0 for c in range(1, 15)}

        for net in networks:
            bssids = net["bssids"]
            if bssids:
                best = max(bssids, key=lambda b: b["signal"])
                sig = best["signal"]
                radio = best["radio"] or "-"
                ch_num, band_guess = _channel_band(best["channel"], radio)
                band = best["band"] or band_guess
                if ch_num and 1 <= ch_num <= 14:
                    ch24_counts[ch_num] = ch24_counts.get(ch_num, 0) + len(bssids)
            else:
                sig = 0
                ch_num = None
                band = "?"
                radio = "-"
            grade, g_key = _security_grade(net["auth"], net["cipher"])
            rows.append((sig, net["ssid"], ch_num, band, net["auth"], net["cipher"], grade, g_key))

        rows.sort(key=lambda r: r[0], reverse=True)
        print(
            fmt("  " + f"{'SSID':<24} {'SIGNAL':<16} {'BAND / CH':<13} {'SECURITY':<18} {'AUDIT'}", ui["muted"], True)
        )
        print(fmt("  " + "─" * 82, ui["border"]))
        open_or_weak = 0
        for sig, ssid, ch_num, band, auth, cipher, grade, g_key in rows[:20]:
            ssid_s = (ssid[:21] + "...") if len(ssid) > 24 else ssid
            ch_txt = f"{band} Ch{ch_num}" if ch_num is not None else band
            sec_txt = f"{auth}/{cipher}".replace("-Personal", "")
            sec_txt = (sec_txt[:15] + "...") if len(sec_txt) > 18 else sec_txt
            if g_key == "error":
                open_or_weak += 1
            print(
                f"  {fmt(ssid_s.ljust(24), ui['text'])}"
                f" {_signal_bar(sig, ui, width=10)}"
                f"  {fmt(ch_txt.ljust(13), ui['accent'])}"
                f" {fmt(sec_txt.ljust(18), ui['muted'])}"
                f" {fmt('[' + grade.strip() + ']', ui[g_key], True)}"
            )

        print()
        # 2.4 GHz congestion advice
        busy_24 = sum(ch24_counts.values())
        if busy_24 > 0:
            cleanest = min((1, 6, 11), key=lambda c: ch24_counts.get(c, 0))
            summary_24 = f"Ch1:{ch24_counts[1]}  Ch6:{ch24_counts[6]}  Ch11:{ch24_counts[11]}"
            print(f"  {fmt('2.4 GHz Congestion:', ui['muted'])} {fmt(summary_24, ui['text'])}   {fmt(f'Cleanest non-overlapping: Ch {cleanest}', ui['accent'], True)}")
        if open_or_weak:
            print(f"  {fmt('Security Note:', ui['warning'], True)} {fmt(f'{open_or_weak} nearby Open/WEP network(s) detected (unencrypted or weak).', ui['warning'])}")

    # 3. Saved profile inventory (names ONLY, read-only, never dumps credentials)
    rc_prof, out_prof = _run_netsh(["show", "profiles"])
    if rc_prof == 0:
        profiles = _parse_saved_profiles(out_prof)
        if show_profiles:
            print()
            print("  " + fmt(f"SAVED WI-FI PROFILES ({len(profiles)})", ui["secondary"], True))
            if profiles:
                for i in range(0, len(profiles), 4):
                    chunk = "   ".join(p.ljust(20) for p in profiles[i:i + 4])
                    print("  " + fmt(chunk, ui["text"]))
            else:
                print("  " + fmt("No saved user profiles.", ui["muted"]))
        else:
            print(f"  {fmt('Saved Profiles:', ui['muted'])} {fmt(str(len(profiles)), ui['primary'], True)}  {fmt('(run: wifi --profiles to list names)', ui['muted'])}")
    print()


def main() -> None:
    enable_vt()
    parser = argparse.ArgumentParser(
        prog="wifi",
        description="TricksXTech Read-Only Wi-Fi Signal, Channel & Security Checker",
    )
    parser.add_argument("--profiles", action="store_true", help="Also list saved profile names (never reads keys)")
    args = parser.parse_args()
    theme = load_theme()
    run_wifi_check(theme, show_profiles=args.profiles)


if __name__ == "__main__":
    main()
