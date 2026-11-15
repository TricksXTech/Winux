#!/usr/bin/env python3
"""TricksXTech - HackingTool & Tools/New Cross-Shell Launcher for Windows CMD & PowerShell."""

import os
import sys
import subprocess

CATEGORY_MAP = {
    "anonsurf": "anonsurf.py",
    "anon": "anonsurf.py",
    "info": "information_gathering.py",
    "recon": "information_gathering.py",
    "infogather": "information_gathering.py",
    "wordlist": "wordlist_generator.py",
    "words": "wordlist_generator.py",
    "wireless": "wireless_attack.py",
    "wifi": "wireless_attack.py",
    "sql": "sql_injection.py",
    "sqli": "sql_injection.py",
    "phishing": "phishing_attack.py",
    "web": "web_attack.py",
    "webattack": "web_attack.py",
    "post": "post_exploitation.py",
    "postexploit": "post_exploitation.py",
    "forensics": "forensics.py",
    "payload": "payload_creator.py",
    "exploit": "exploit_frameworks.py",
    "reverse": "reverse_engineering.py",
    "rev": "reverse_engineering.py",
    "re": "reverse_engineering.py",
    "ddos": "ddos.py",
    "rat": "remote_administration.py",
    "remote": "remote_administration.py",
    "xss": "xss_attack.py",
    "stego": "steganography.py",
    "steganography": "steganography.py",
    "ad": "active_directory.py",
    "activedirectory": "active_directory.py",
    "cloud": "cloud_security.py",
    "mobile": "mobile_security.py",
    "android": "others/android_attack.py",
    "other": "other_tools.py",
    "others": "other_tools.py",
    "mix": "others/mix_tools.py",
    "social": "others/socialmedia_finder.py",
    "socialmedia": "others/socialmedia.py",
    "email": "others/email_verifier.py",
    "hashcrack": "others/hash_crack.py",
    "homograph": "others/homograph_attacks.py",
    "crawl": "others/web_crawling.py",
    "manager": "tool_manager.py",
}

GUIDE_SECTIONS = {
    "info": """  [ Information Gathering & Reconnaissance ]
  Overview: Tools for network discovery, DNS enumeration, OSINT footprinting, and target reconnaissance.
  Top Tools: Nmap, Shodan, Holehe, Maigret, SpiderFoot, TheHarvester, Subfinder, Masscan.
  Windows Native Setup:
    • Nmap:        winget install Insecure.Nmap
    • OSINT/Email: pip install holehe maigret
  TricksXTech Built-in Commands (Ready now without installing):
    • osint <target>           -> DoH DNS, RDAP, ASN/Geo, TLS cert & HTTP security headers
    • subdomains <domain>      -> Passive crt.sh Certificate Transparency enumeration
    • webtech <url>            -> Passive web technology, WAF & CDN fingerprinter
    • portcheck <host> [ports] -> Multi-port TCP connectivity & latency probe
    • lan                      -> Read-only ARP table, gateway cache & MAC vendor check
""",
    "forensics": """  [ Digital Forensics & Binary Analysis ]
  Overview: Tools for forensic investigation, packet inspection, file carvers, and memory analysis.
  Top Tools: Wireshark, Autopsy, Bulk Extractor.
  Windows Native Setup:
    • Wireshark:       winget install WiresharkFoundation.Wireshark
    • Autopsy:         Download Windows installer from https://www.autopsy.com/
  TricksXTech Built-in Commands (Ready now without installing):
    • peinspect <file> -> Static PE/ELF binary header, entropy & strings analyzer
    • exifinfo <image> -> File magic verifier, EXIF metadata, GPS & PNG chunks
    • hexview <file>   -> Canonical hex dump + ASCII representation
    • hashid <hash>    -> Offline hash, JWT & UUID type identifier
    • secretaudit <dir>-> Scan directory for leaked API keys and sensitive tokens
""",
    "stego": """  [ Steganography & Data Hiding ]
  Overview: Tools for inspecting hidden information in image, audio, and carrier files.
  Top Tools: Steghide, Stegseek, Zsteg.
  Windows Native Setup:
    • Stegseek / Stegsolve: Available via GitHub Windows releases.
  TricksXTech Built-in Commands (Ready now without installing):
    • stego audit <file>       -> Check for EOF trailing payload bytes & PNG metadata
    • stego hide <bmp> <txt>   -> Lossless BMP LSB steganographic text encoder
    • stego extract <bmp>      -> Lossless BMP LSB steganographic text decoder
    • exifinfo <file>          -> Extract hidden comment tags and GPS metadata
""",
    "wordlist": """  [ Wordlist Generation & Password Dictionaries ]
  Overview: Utilities to generate custom target dictionaries and pattern-based wordlists.
  Top Tools: Crunch, Cupp, Cewl.
  Windows Native Setup:
    • Cupp: pip install cupp
  TricksXTech Built-in Commands (Ready now without installing):
    • wordgen <base> --leet    -> Generate leetspeak mutations (P@ssw0rd)
    • wordgen --pin 4          -> Generate numeric PIN lists
    • pwgen [length]           -> Cryptographically secure random passwords
    • tokengen [bytes]         -> URL-safe random session tokens
""",
    "reverse": """  [ Reverse Engineering & Disassembly ]
  Overview: Disassemblers, decompilers, and binary analysis frameworks.
  Top Tools: Ghidra, Radare2, GDB, APKTool.
  Windows Native Setup:
    • Ghidra:  winget install NSA.Ghidra
    • Radare2: winget install radare2
  TricksXTech Built-in Commands (Ready now without installing):
    • peinspect <file> -> Inspect PE sections, imports, exports, and compiler markers
    • hexview <file>   -> Detailed binary hex inspector with offset navigation
""",
    "anonsurf": """  [ Anonymous Routing & Privacy ]
  Overview: Route system traffic through encrypted tunnels or anonymity relays.
  Top Tools: Tor, Anonsurf, Multitor.
  Windows Native Setup:
    • Tor: Download Tor Browser or Tor Expert Bundle for Windows.
  TricksXTech Built-in Commands (Ready now without installing):
    • vpn status               -> Exit IP, ASN/ISP, and DNS leak detector
    • vpn rotate 5m            -> Automatic 5-minute background VPN IP rotation
    • vpn sync                 -> Sync verified public academic VPNGate relays
"""
}

def print_help():
    print("""TricksXTech // HackingTool Suite Launcher & Windows Guide
Usage:
  ht                         Launch main interactive HackingTool menu
  ht <category>              Launch a specific tool category menu
  ht guide [category]        Show Windows guide & native alternatives
  ht list                    Show all available categories
  ht --help                  Show this help screen

Available category shortcuts:
  info, recon        -> Information Gathering
  forensics          -> Cyber Forensics (Autopsy, Wireshark, etc.)
  stego              -> Steganography tools
  wordlist           -> Wordlist generation utilities
  reverse, rev       -> Reverse engineering tools
  social, email      -> Social media & email verification tools
  cloud, ad          -> Cloud & Active Directory tools
  web, xss, sql      -> Web application assessment tools
  anonsurf           -> Anonymous routing tools
  manager            -> Tool update / manager
""")

def print_guide(cat=None):
    if cat:
        key = cat.lower().lstrip("-")
        for k, text in GUIDE_SECTIONS.items():
            if k in key or key in k:
                print("\n" + text)
                return
    print("\n--- TricksXTech // Windows Security & Tools Guide ---")
    for text in GUIDE_SECTIONS.values():
        print(text)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    new_dir = os.path.join(base_dir, "new")
    
    args = sys.argv[1:]
    if not args:
        # Launch main hackingtool interactive menu
        try:
            from hackingtool import cli
            cli.main(["--classic"])
        except Exception:
            subprocess.run([sys.executable, "-m", "hackingtool.cli", "--classic"])
        return

    cmd = args[0].lower().lstrip("-")
    if cmd in ("h", "help"):
        print_help()
        return

    if cmd == "guide":
        target = args[1] if len(args) > 1 else None
        print_guide(target)
        return

    if cmd == "list":
        print("Available tool categories in D:\\Terminal\\tools\\new:")
        for alias, script in sorted(CATEGORY_MAP.items()):
            print(f"  {alias.ljust(15)} -> {script}")
        return

    # Check if category shortcut exists
    target_script = CATEGORY_MAP.get(cmd)
    if target_script:
        # Print a brief category guide if available
        if cmd in GUIDE_SECTIONS:
            print("\n" + GUIDE_SECTIONS[cmd])
        script_path = os.path.join(new_dir, target_script.replace("/", os.sep))
        if os.path.isfile(script_path):
            subprocess.run([sys.executable, script_path] + args[1:])
            return

    # Direct filename check in new\
    direct_file = os.path.join(new_dir, cmd if cmd.endswith(".py") else f"{cmd}.py")
    if os.path.isfile(direct_file):
        subprocess.run([sys.executable, direct_file] + args[1:])
        return

    # Pass through to upstream hackingtool cli
    try:
        from hackingtool import cli
        cli.main(args)
    except Exception as e:
        print(f"Error running hackingtool: {e}")

if __name__ == "__main__":
    main()
