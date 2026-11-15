#!/usr/bin/env python3
"""Winux // Crypto Tool Suite - Cross-shell cryptocurrency utility launcher."""

from __future__ import annotations

import os
import sys
import random

import base58
import ecdsa
import requests
from Crypto.Hash import keccak
from rich import print as rprint

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from free_tools import enable_vt, fmt, header, load_theme


def keccak256(data):
    hasher = keccak.new(digest_bits=256)
    hasher.update(data)
    return hasher.digest()


def get_signing_key(raw_priv):
    return ecdsa.SigningKey.from_string(raw_priv, curve=ecdsa.SECP256k1)


def verifying_key_to_addr(key):
    pub_key = key.to_string()
    primitive_addr = b'\x41' + keccak256(pub_key)[-20:]
    addr = base58.b58encode_check(primitive_addr)
    return addr


def run_trx_scanner(theme: dict) -> None:
    """Runs the TRX address and balance scanner loop."""
    print(f"\n{fmt('[*] Starting TRX Scanner...', theme['ui']['accent'], True)}\n")
    z = 0
    w = 0
    
    while True:
        raw = bytes(random.sample(range(0, 256), 32))
        key = get_signing_key(raw)
        addr = verifying_key_to_addr(key.get_verifying_key()).decode()
        priv = raw.hex()
        
        try:
            block = requests.get(f"https://apilist.tronscan.org/api/account?address={addr}", timeout=10)
            res = block.json()
            
            # Safely parse balances (Tronscan returns empty lists for unused/empty addresses)
            balances_list = res.get("balances", [])
            if balances_list:
                bal = float(balances_list[0].get("amount", 0))
            else:
                bal = 0.0
                
        except Exception:
            # Skip API limits or temporary connection issues
            continue

        if bal > 0:
            w += 1
            with open("FileTRXWinner.txt", "a") as f:
                f.write(f"\nADDReSS: {addr}   bal: {bal}")
                f.write(f"\nPRIVATEKEY: {priv}")
                f.write("\n------------------------")
        else:
            rprint(f'[red1]Total Scan : [/][b blue]{z}[/]')
            rprint(f'[gold1]Address:     [/]{addr}          Balance: {bal}')
            rprint(f'[gold1]Address(hex):[/]{base58.b58decode_check(addr.encode()).hex()}')
            rprint(f'[gold1]Private Key: [/][red1]{raw.hex()}[/]')
            z += 1


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
            run_trx_scanner(theme)
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
        run_trx_scanner(theme)
    elif arg in ("2", "bnb", "eth"):
        print("ok")
    elif arg in ("h", "help"):
        print("Winux // Crypto CLI Suite")
        print("Usage:")
        print("  crypto             Open interactive menu")
        print("  crypto trx         Select TRX scanner")
        print("  crypto bnb         Select BNB / ETH (prints 'ok')")
        print("  crypto eth         Select BNB / ETH (prints 'ok')")
    else:
        show_menu(theme)


if __name__ == "__main__":
    main()