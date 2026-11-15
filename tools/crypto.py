#!/usr/bin/env python3
"""Winux // Crypto Tool Suite - Cross-shell cryptocurrency utility launcher."""

from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, header, load_theme


def show_menu(theme: dict) -> None:
    ui = theme["ui"]
    while True:
        header("Crypto CLI Suite", theme)
        print(f"  {fmt('[ 1]', ui['primary'], True)}  {fmt('TRX', ui['text'], True)}        (Tron Network)")
        print(f"  {fmt('[ 2]', ui['primary'], True)}  {fmt('BNB, ETH', ui['text'], True)}   (Binance Smart Chain / Ethereum)")
        print(f"  {fmt('[99]', ui['muted'])}  {fmt('Exit', ui['muted'])}")
        print()
        try:
            choice = input(fmt("  Select an option [1-2, 99]: ", ui["accent"])).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if choice in ("1", "trx"):
            print("trx")
            break
        elif choice in ("2", "bnb", "eth", "bnb, eth"):
            print("ok")
            break
        elif choice in ("99", "q", "quit", "exit"):
            break
        else:
            print(f"  {fmt('Invalid selection. Choose 1 or 2.', ui['error'])}")
            print()


def main():
    enable_vt()
    theme = load_theme()
    args = sys.argv[1:]

    if not args:
        show_menu(theme)
        return

    arg = args[0].lower().strip("-")
    if arg in ("1", "trx"):
        print("trx")
    elif arg in ("2", "bnb", "eth"):
        print("ok")
    elif arg in ("h", "help"):
        print("Winux // Crypto CLI Suite")
        print("Usage:")
        print("  crypto           Open interactive menu")
        print("  crypto trx       Select TRX (prints 'trx')")
        print("  crypto bnb       Select BNB / ETH (prints 'ok')")
        print("  crypto eth       Select BNB / ETH (prints 'ok')")
    else:
        show_menu(theme)


if __name__ == "__main__":
    main()
