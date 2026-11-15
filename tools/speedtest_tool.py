#!/usr/bin/env python3
"""TricksXTech Live Speedometer Internet Speed Checker (Ping, Jitter, Live Download & Upload)."""

from __future__ import annotations

import argparse
import http.client
import math
import os
import socket
import ssl
import sys
import time
import urllib.request

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, fmt_bytes, gradient, header, load_theme

USER_AGENT = "TricksXTech-SpeedTest/1.0"
DOWNLOAD_ENDPOINTS = (
    ("speed.cloudflare.com", "/__down?bytes=25000000"),
    ("speed.cloudflare.com", "/__down?bytes=10000000"),
)


def _auto_scale(peak_mbps: float) -> float:
    for cap in (25.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2500.0):
        if peak_mbps <= cap * 0.92:
            return cap
    return max(2500.0, math.ceil(peak_mbps / 500.0) * 500.0)


def _render_speedometer_lines(
    phase: str,
    live_mbps: float,
    avg_mbps: float,
    peak_mbps: float,
    progress: float,
    transferred: int,
    ping_ms: float | None,
    jitter_ms: float | None,
    ui: dict,
) -> list[str]:
    """Build a crisp, fixed-height (12 lines) TrueColor ASCII/Unicode speedometer dial."""
    scale_max = _auto_scale(max(peak_mbps, live_mbps, 20.0))
    ratio = max(0.0, min(1.0, live_mbps / scale_max))

    # 19x9 semi-circular gauge grid mapped onto polar angle pi -> 0
    rows = 9
    cols = 35
    cx = cols // 2
    cy = rows - 1
    rx = 15.5
    ry = 7.4

    canvas: list[list[tuple[str, str, bool]]] = [
        [(" ", "", False) for _ in range(cols)] for _ in range(rows)
    ]

    # Plot arc segments (25 steps across 180 deg -> 0 deg)
    lit_threshold_angle = math.pi * (1.0 - ratio)
    for step in range(49):
        ang = math.pi * (1.0 - step / 48.0)
        x = round(cx + rx * math.cos(ang))
        y = round(cy - ry * math.sin(ang))
        if 0 <= y < rows and 0 <= x < cols:
            frac = step / 48.0
            is_lit = frac <= ratio + 1e-6
            if not is_lit:
                ch, clr, bld = "░", ui["muted"], False
            else:
                if frac < 0.35:
                    clr = ui["success"]
                elif frac < 0.70:
                    clr = ui["accent"]
                else:
                    clr = ui["primary"]
                ch, bld = "█", True
            canvas[y][x] = (ch, clr, bld)

    # Plot live needle pointing toward current Mbps ratio
    needle_ang = lit_threshold_angle
    for r_frac in (0.20, 0.35, 0.50, 0.65, 0.78):
        nx = round(cx + (rx * r_frac) * math.cos(needle_ang))
        ny = round(cy - (ry * r_frac) * math.sin(needle_ang))
        if 0 <= ny < rows and 0 <= nx < cols:
            if abs(math.cos(needle_ang)) < 0.3:
                nch = "|"
            elif math.cos(needle_ang) < 0:
                nch = "\\"
            else:
                nch = "/"
            canvas[ny][nx] = (nch, ui["warning"], True)

    canvas[cy][cx] = ("●", ui["primary"], True)

    # Digital live readout placed cleanly inside lower center
    readout = f"{live_mbps:6.1f} Mbps"
    rx0 = cx - len(readout) // 2
    for idx, ch in enumerate(readout):
        if 0 <= rx0 + idx < cols and canvas[cy - 1][rx0 + idx][0] == " ":
            canvas[cy - 1][rx0 + idx] = (ch, ui["accent"] if idx < 6 else ui["muted"], idx < 6)

    phase_lbl = fmt(f" {phase.upper()} ", ui["darkText"] if "darkText" in ui else ui["primary"], False)
    if "darkText" in ui:
        phase_badge = fmt(f"[{phase.upper()}]", ui["primary"], True)
    else:
        phase_badge = phase_lbl

    lines: list[str] = []
    ping_txt = f"{ping_ms:.1f} ms" if ping_ms is not None else "..."
    jit_txt = f"{jitter_ms:.1f} ms" if jitter_ms is not None else "..."
    lines.append(
        f"  {phase_badge}  Ping: {fmt(ping_txt, ui['accent'], True)}   "
        f"Jitter: {fmt(jit_txt, ui['secondary'], True)}   "
        f"Scale: 0-{int(scale_max)} Mbps"
    )

    for r in range(rows):
        row_chunks: list[str] = ["  "]
        for c in range(cols):
            ch, clr, bld = canvas[r][c]
            row_chunks.append(fmt(ch, clr, bld) if clr else ch)
        lines.append("".join(row_chunks))

    lines.append(
        f"  {fmt('0', ui['muted'])}" + (" " * 14)
        + fmt(f"{int(scale_max // 2)} Mbps", ui["muted"]) + (" " * 10)
        + fmt(f"{int(scale_max)}", ui["muted"])
    )

    p_clamped = max(0.0, min(1.0, progress))
    bar_w = 24
    filled = round(p_clamped * bar_w)
    pbar = fmt("━" * filled, ui["success"], True) + fmt("─" * (bar_w - filled), ui["muted"])
    lines.append(
        f"  {pbar} {fmt(f'{p_clamped * 100:3.0f}%', ui['text'], True)}  "
        f"Avg: {fmt(f'{avg_mbps:.1f}', ui['accent'], True)}  "
        f"Peak: {fmt(f'{peak_mbps:.1f}', ui['primary'], True)} Mbps  "
        f"({fmt_bytes(transferred)})"
    )
    return lines


def _draw_frame(lines: list[str], is_tty: bool, prev_count: int) -> int:
    if is_tty and prev_count > 0:
        sys.stdout.write(f"\x1b[{prev_count}A")
    for ln in lines:
        if is_tty:
            sys.stdout.write("\x1b[2K" + ln + "\n")
        else:
            sys.stdout.write(ln + "\n")
    sys.stdout.flush()
    return len(lines)


def _measure_ping(host: str = "speed.cloudflare.com", port: int = 443, samples: int = 6) -> tuple[float | None, float | None]:
    rtts: list[float] = []
    ctx = ssl.create_default_context()
    for i in range(samples):
        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=3.5) as sock:
                if i == 0:
                    with ctx.wrap_socket(sock, server_hostname=host):
                        pass
                dt = (time.perf_counter() - t0) * 1000.0
                if i > 0:  # discard cold TLS handshake warmup
                    rtts.append(dt)
        except OSError:
            continue
    if not rtts:
        return None, None
    avg = sum(rtts) / len(rtts)
    jitter = (
        sum(abs(rtts[k] - rtts[k - 1]) for k in range(1, len(rtts))) / max(1, len(rtts) - 1)
        if len(rtts) > 1
        else 0.0
    )
    return avg, jitter


def _measure_download(
    duration_sec: float,
    ping_ms: float | None,
    jitter_ms: float | None,
    ui: dict,
    is_tty: bool,
) -> tuple[float, float, int]:
    total_bytes = 0
    avg_mbps = 0.0
    peak_mbps = 0.0
    samples_window: list[tuple[float, int]] = []
    prev_lines = 0
    t_start = time.perf_counter()
    last_draw = 0.0

    ctx = ssl.create_default_context()
    for host, path in DOWNLOAD_ENDPOINTS:
        req = urllib.request.Request(f"https://{host}{path}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=8.0, context=ctx) as resp:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    now = time.perf_counter()
                    total_bytes += len(chunk)
                    samples_window.append((now, len(chunk)))
                    while samples_window and now - samples_window[0][0] > 0.65:
                        samples_window.pop(0)
                    elapsed = max(0.05, now - t_start)
                    avg_mbps = (total_bytes * 8.0) / elapsed / 1_000_000.0
                    win_dt = max(0.08, now - samples_window[0][0]) if len(samples_window) > 1 else elapsed
                    win_bytes = sum(b for _, b in samples_window)
                    live_mbps = (win_bytes * 8.0) / win_dt / 1_000_000.0
                    if elapsed > 0.35 and live_mbps > peak_mbps:
                        peak_mbps = live_mbps

                    if is_tty and (now - last_draw >= 0.12):
                        prog = min(1.0, elapsed / duration_sec)
                        frame = _render_speedometer_lines(
                            "DOWNLOAD", live_mbps, avg_mbps, max(peak_mbps, avg_mbps), prog, total_bytes, ping_ms, jitter_ms, ui
                        )
                        prev_lines = _draw_frame(frame, True, prev_lines)
                        last_draw = now

                    if elapsed >= duration_sec:
                        break
            break
        except Exception:
            continue

    elapsed = max(0.05, time.perf_counter() - t_start)
    avg_mbps = (total_bytes * 8.0) / elapsed / 1_000_000.0
    peak_mbps = max(peak_mbps, avg_mbps)
    final_frame = _render_speedometer_lines(
        "DOWNLOAD", avg_mbps, avg_mbps, peak_mbps, 1.0, total_bytes, ping_ms, jitter_ms, ui
    )
    _draw_frame(final_frame, is_tty, prev_lines)
    return avg_mbps, peak_mbps, total_bytes


def _measure_upload(
    duration_sec: float,
    ping_ms: float | None,
    jitter_ms: float | None,
    ui: dict,
    is_tty: bool,
) -> tuple[float, float, int]:
    total_bytes = 0
    avg_mbps = 0.0
    peak_mbps = 0.0
    prev_lines = 0
    t_start = time.perf_counter()
    last_draw = 0.0
    chunk_size = 512 * 1024  # 512 KB per POST burst
    payload = b"T" * chunk_size
    ctx = ssl.create_default_context()

    conn: http.client.HTTPSConnection | None = None
    try:
        conn = http.client.HTTPSConnection("speed.cloudflare.com", 443, timeout=8.0, context=ctx)
        while True:
            t_req0 = time.perf_counter()
            if t_req0 - t_start >= duration_sec:
                break
            try:
                conn.request(
                    "POST",
                    "/__up",
                    body=payload,
                    headers={"User-Agent": USER_AGENT, "Content-Type": "application/octet-stream"},
                )
                resp = conn.getresponse()
                resp.read()
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = http.client.HTTPSConnection("speed.cloudflare.com", 443, timeout=8.0, context=ctx)
                break

            now = time.perf_counter()
            total_bytes += chunk_size
            req_dt = max(0.03, now - t_req0)
            elapsed = max(0.05, now - t_start)
            live_mbps = (chunk_size * 8.0) / req_dt / 1_000_000.0
            avg_mbps = (total_bytes * 8.0) / elapsed / 1_000_000.0
            if live_mbps > peak_mbps:
                peak_mbps = live_mbps

            if is_tty and (now - last_draw >= 0.12):
                prog = min(1.0, elapsed / duration_sec)
                frame = _render_speedometer_lines(
                    "UPLOAD", live_mbps, avg_mbps, peak_mbps, prog, total_bytes, ping_ms, jitter_ms, ui
                )
                prev_lines = _draw_frame(frame, True, prev_lines)
                last_draw = now
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    elapsed = max(0.05, time.perf_counter() - t_start)
    avg_mbps = (total_bytes * 8.0) / elapsed / 1_000_000.0
    peak_mbps = max(peak_mbps, avg_mbps)
    final_frame = _render_speedometer_lines(
        "UPLOAD", avg_mbps, avg_mbps, peak_mbps, 1.0, total_bytes, ping_ms, jitter_ms, ui
    )
    _draw_frame(final_frame, is_tty, prev_lines)
    return avg_mbps, peak_mbps, total_bytes


def run_speedtest(argv: list[str] | None = None, theme: dict | None = None) -> None:
    if theme is None:
        theme = load_theme()
    ui = theme["ui"]

    p = argparse.ArgumentParser(
        prog="speedtest",
        description="Live terminal speedometer internet speed test (Ping, Jitter, Download & Upload)",
    )
    p.add_argument("--quick", action="store_true", help="Short 3s burst per phase instead of 7s/5s")
    p.add_argument("--down-only", action="store_true", help="Test download speed only (skip upload)")
    p.add_argument("--with-vpn", action="store_true", help="Start TricksXTech VPN rotator before testing if inactive")
    args = p.parse_args(argv or [])

    dl_secs = 3.5 if args.quick else 7.5
    ul_secs = 3.0 if args.quick else 5.5
    is_tty = bool(sys.stdout.isatty())

    header("Live Internet Speedometer (Cloudflare Edge)", theme)

    from vpn_tool import ensure_vpn_for_tool, read_active_vpn_state, vpn_badge_line
    if args.with_vpn:
        ensure_vpn_for_tool("speedtest", theme, skip_vpn=False)
    else:
        active_vpn = read_active_vpn_state()
        if active_vpn and active_vpn.get("status") == "connected":
            print(vpn_badge_line(active_vpn, ui))
        else:
            print(f"  {fmt('[DIRECT LINK]', ui['muted'], True)} {fmt('Testing raw ISP speed (pass --with-vpn to measure active VPN route).', ui['muted'])}")
    print()

    if is_tty:
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

    dl_avg = dl_peak = 0.0
    ul_avg = ul_peak = 0.0
    dl_bytes = ul_bytes = 0
    ping_ms: float | None = None
    jitter_ms: float | None = None

    try:
        ping_ms, jitter_ms = _measure_ping()
        dl_avg, dl_peak, dl_bytes = _measure_download(dl_secs, ping_ms, jitter_ms, ui, is_tty)
        print()
        if not args.down_only:
            ul_avg, ul_peak, ul_bytes = _measure_upload(ul_secs, ping_ms, jitter_ms, ui, is_tty)
            print()
    except KeyboardInterrupt:
        print()
        print("  " + fmt("Speed test cancelled.", ui["warning"]))
        return
    finally:
        if is_tty:
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()

    # Final Scorecard
    tier = (
        ("GIGABIT / FIBER TIER", ui["success"]) if dl_avg >= 250 else
        ("FAST BROADBAND", ui["primary"]) if dl_avg >= 50 else
        ("STANDARD BROADBAND", ui["accent"]) if dl_avg >= 15 else
        ("CONSTRAINED / SLOW", ui["warning"])
    )
    print(fmt("  " + "─" * 68, ui["border"]))
    p_str = f"{ping_ms:.1f} ms" if ping_ms is not None else "Offline"
    j_str = f"{jitter_ms:.1f} ms" if jitter_ms is not None else "-"
    print(f"  {fmt('Ping / Latency:'.ljust(18), ui['muted'])} {fmt(p_str, ui['accent'], True)}   {fmt('Jitter:', ui['muted'])} {fmt(j_str, ui['text'])}")
    print(f"  {fmt('Download Avg:'.ljust(18), ui['muted'])} {fmt(f'{dl_avg:.2f} Mbps', ui['success'], True)} ({dl_avg / 8.0:.2f} MB/s)   {fmt('Peak:', ui['muted'])} {fmt(f'{dl_peak:.2f} Mbps', ui['primary'])}   [{fmt_bytes(dl_bytes)}]")
    if not args.down_only:
        print(f"  {fmt('Upload Avg:'.ljust(18), ui['muted'])} {fmt(f'{ul_avg:.2f} Mbps', ui['secondary'], True)} ({ul_avg / 8.0:.2f} MB/s)   {fmt('Peak:', ui['muted'])} {fmt(f'{ul_peak:.2f} Mbps', ui['primary'])}   [{fmt_bytes(ul_bytes)}]")
    print(f"  {fmt('Link Rating:'.ljust(18), ui['muted'])} {gradient(tier[0], [ui['gradientStart'], ui['gradientEnd']], bold=True)}")
    print()


def main() -> None:
    enable_vt()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    run_speedtest(sys.argv[1:])


if __name__ == "__main__":
    main()
