# TricksXTech CLI & Interactive Theme Control Center

param(
    [Parameter(Position = 0)][string]$Command = "",
    [Parameter(Position = 1)][string]$Arg1 = "",
    [Parameter(Position = 2)][string]$Arg2 = "",
    [switch]$Yes,
    [Alias('h', 'guide')][switch]$Help
)

$script:TxRoot = $PSScriptRoot
. (Join-Path $script:TxRoot "src\core\ansi.ps1")
. (Join-Path $script:TxRoot "src\core\config.ps1")
. (Join-Path $script:TxRoot "src\core\sysinfo.ps1")
. (Join-Path $script:TxRoot "src\core\hud.ps1")
. (Join-Path $script:TxRoot "src\powershell\prompt.ps1")
. (Join-Path $script:TxRoot "src\powershell\productivity.ps1")
. (Join-Path $script:TxRoot "src\wt\wt_manager.ps1")

Initialize-TxEncoding

function Commit-TxConfig {
    param([hashtable]$Config)
    Save-TxConfig -Config $Config
    $wtUpdated = Sync-TxWTSettings -Config $Config -OnlyIfHooked
    if (Get-Command Sync-TxRuntimeCache -ErrorAction SilentlyContinue) {
        Sync-TxRuntimeCache
        Apply-TxPSReadLineTheme -Config $script:TxRuntimeConfig -Theme $script:TxRuntimeTheme
    }
    return $wtUpdated
}

function Show-TxThemeCatalog {
    param([hashtable]$Config)
    if (-not $Config) { $Config = Get-TxConfig }
    $themes = Get-TxThemes
    $order = Get-TxThemeOrder
    $active = Get-TxActiveTheme $Config
    $ui = $active.ui

    Write-Host ""
    Write-Host (Format-TxGradient "  $($Config.brand) Themes ($($order.Count) Available)" -Stops @($ui.gradientStart, $ui.gradientMid, $ui.gradientEnd) -Bold)
    Write-Host (Format-TxText ("  " + ([string][char]0x2500 * 72)) -Fg $ui.border)

    $num = 1
    foreach ($id in $order) {
        $t = $themes[$id]
        $p = $t.palette
        $u = $t.ui
        $isAct = ($id -eq $Config.theme)
        $marker = if ($isAct) { Format-TxText ([string][char]0x2605 + " ACTIVE") -Fg $u.success -Bold } else { Format-TxText ("  [" + $num.ToString().PadLeft(2) + "]  ") -Fg $ui.muted }
        $blk = [string][char]0x2588 + [string][char]0x2588
        $swatches = @(
            $p.background, $u.primary, $u.secondary, $u.accent, $p.green, $p.yellow, $p.red, $p.purple
        ) | ForEach-Object { Format-TxText $blk -Fg $_ }

        $title = Format-TxText ($t.name.PadRight(20)) -Fg $u.primary -Bold
        $idTag = Format-TxText ("($id)".PadRight(17)) -Fg $ui.muted
        Write-Host "  $marker  $title $idTag $($swatches -join ' ')"
        Write-Host "            $(Format-TxText $t.tagline -Fg $ui.muted)"
        $num++
    }
    Write-Host (Format-TxText "  Switch anytime: tx theme <name|#>   (example: tx theme dracula or tx theme 8)" -Fg $ui.muted)
    Write-Host ""
}

function Show-TxPreview {
    param([string]$TargetTheme = "")
    $cfg = Get-TxConfig
    $themes = Get-TxThemes
    $order = Get-TxThemeOrder
    $glyphs = Get-TxGlyphs -Mode (Resolve-TxGlyphMode $cfg)

    $listIds = if ($TargetTheme) {
        $resolved = Resolve-TxThemeId $TargetTheme
        if (-not $resolved) {
            Write-Host "Unknown theme '$TargetTheme'. Try: $($order -join ', ')" -ForegroundColor Red
            return
        }
        @($resolved)
    } else {
        $order
    }

    Write-Host ""
    foreach ($id in $listIds) {
        $t = $themes[$id]
        $u = $t.ui
        $p = $t.palette
        $bgBand = Get-TxBg $p.background
        $rst = Get-TxReset
        $bar = ([string][char]0x2500 * 66)

        Write-Host (Format-TxText $bar -Fg $u.border)
        $hdr = Format-TxGradient " $($t.name)  [$id]" -Stops @($u.gradientStart, $u.gradientMid, $u.gradientEnd) -Bold
        Write-Host "$hdr  $(Format-TxText $t.tagline -Fg $u.muted)"

        # Simulated prompt samples in active style
        $sampleCfg = Merge-TxHashtables $cfg @{}
        $sampleCfg.theme = $id
        $samplePrompt = Invoke-TxRenderPrompt -Config $sampleCfg -Theme $t -Glyphs $glyphs `
            -LastOk $true -LastCode 0 -DurationMs 840 -HasNewCmd $true
        $sampleErr = Invoke-TxRenderPrompt -Config $sampleCfg -Theme $t -Glyphs $glyphs `
            -LastOk $false -LastCode 1 -DurationMs 2310 -HasNewCmd $true

        Write-Host "  Success prompt:"
        $okLines = @($samplePrompt -split "`n")
        for ($li = 0; $li -lt $okLines.Count; $li++) {
            $suffix = if ($li -eq ($okLines.Count - 1)) { Format-TxText 'git commit -m "feat: theme"' -Fg $u.text } else { "" }
            Write-Host "    $($okLines[$li])$suffix"
        }
        Write-Host "  Error + duration prompt:"
        $errLines = @($sampleErr -split "`n")
        for ($li = 0; $li -lt $errLines.Count; $li++) {
            $suffix = if ($li -eq ($errLines.Count - 1)) { Format-TxText 'npm run build' -Fg $u.error } else { "" }
            Write-Host "    $($errLines[$li])$suffix"
        }

        # Color strip inside theme background
        $strip = "$bgBand  $(Format-TxText 'bg' -Fg $u.muted -Bg $p.background) " +
            "$(Format-TxText 'Command' -Fg $u.primary -Bg $p.background -Bold) " +
            "$(Format-TxText '--flag' -Fg $u.accent -Bg $p.background) " +
            "$(Format-TxText '"string"' -Fg $p.green -Bg $p.background) " +
            "$(Format-TxText '$var' -Fg $p.purple -Bg $p.background) " +
            "$(Format-TxText '123' -Fg $p.yellow -Bg $p.background) " +
            "$(Format-TxText '# comment' -Fg $u.muted -Bg $p.background)  $rst"
        Write-Host "  Syntax preview: $strip"
    }
    Write-Host (Format-TxText ([string][char]0x2500 * 66) -Fg (Get-TxActiveTheme $cfg).ui.border)
    Write-Host ""
}

function Show-TxStatus {
    $cfg = Get-TxConfig
    $thm = Get-TxActiveTheme $cfg
    $ui = $thm.ui
    $envStat = Get-TxEnvironmentStatus
    $glyphMode = Resolve-TxGlyphMode $cfg

    Write-Host ""
    Write-Host (Format-TxGradient "  $($cfg.brand) Status & Diagnostics" -Stops @($ui.gradientStart, $ui.gradientMid, $ui.gradientEnd) -Bold)
    Write-Host (Format-TxText ("  " + ([string][char]0x2500 * 60)) -Fg $ui.border)

    function Write-StatRow([string]$Label, [string]$Val, [string]$Color = $ui.text) {
        Write-Host ("  " + (Format-TxText $Label.PadRight(22) -Fg $ui.secondary -Bold) + (Format-TxText $Val -Fg $Color))
    }

    Write-StatRow "Active Theme" "$($thm.name) ($($thm.id))" $ui.primary
    Write-StatRow "Prompt Style" "$($cfg.style) (icons: $($cfg.icons) -> $glyphMode)" $ui.accent
    Write-StatRow "Startup HUD" $cfg.hud $ui.text
    Write-StatRow "WT Appearance" "opacity=$($cfg.wt.opacity)% acrylic=$($cfg.wt.useAcrylic) cursor=$($cfg.wt.cursorShape) crt=$($cfg.wt.retroEffect)" $ui.text
    Write-Host ""
    Write-StatRow "PowerShell" "$($envStat.PSVersion) (PS7 installed: $($envStat.Pwsh7Installed))" $(if ($envStat.Pwsh7Installed) { $ui.success } else { $ui.text })
    Write-StatRow "PSReadLine" "$($envStat.PSReadLineVer) (Inline predictions: $($envStat.PSReadLinePred))" $(if ($envStat.PSReadLinePred) { $ui.success } else { $ui.warning })
    Write-StatRow "Nerd Font" $envStat.NerdFont $(if ($envStat.HasNerdFont) { $ui.success } else { $ui.warning })
    Write-StatRow "Clink (CMD)" $(if ($envStat.HasClink) { $envStat.ClinkPath } else { "Not installed (using native VT100 CMD mode)" }) $(if ($envStat.HasClink) { $ui.success } else { $ui.warning })
    Write-StatRow "Windows Terminal" $(if ($envStat.HasWT) { "Detected (Hooked: $($envStat.WTHooked))" } else { "Not detected" }) $(if ($envStat.WTHooked) { $ui.success } else { $ui.accent })
    Write-StatRow "PowerShell Profile" $(if ($envStat.PSHooked) { "Installed" } else { "Not installed yet (run install.ps1)" }) $(if ($envStat.PSHooked) { $ui.success } else { $ui.accent })
    Write-StatRow "CMD AutoRun" $(if ($envStat.CMDHooked) { "Installed" } else { "Not installed yet (run install.ps1)" }) $(if ($envStat.CMDHooked) { $ui.success } else { $ui.accent })
    Write-Host ""
    if (-not $envStat.HasNerdFont -or -not $envStat.HasClink -or -not $envStat.PSReadLinePred) {
        Write-Host (Format-TxText "  Optional upgrades available! Run 'tx upgrade' to unlock Nerd Fonts, Clink & inline predictions." -Fg $ui.muted)
        Write-Host ""
    }
}

function Invoke-TxUpgrade {
    param([string]$Target = "check")
    $cfg = Get-TxConfig
    $thm = Get-TxActiveTheme $cfg
    $ui = $thm.ui
    $envStat = Get-TxEnvironmentStatus

    $items = @(
        [ordered]@{
            Id = "nerd-font"
            Name = "CaskaydiaCove Nerd Font"
            Installed = $envStat.HasNerdFont
            Benefit = "Unlocks sleek powerline curves and file/git icons"
            Run = { & winget install --id DEVCOM.NerdFonts.CascadiaCode --source winget --accept-package-agreements --accept-source-agreements }
            CmdText = "winget install DEVCOM.NerdFonts.CascadiaCode"
        },
        [ordered]@{
            Id = "clink"
            Name = "Clink for CMD"
            Installed = $envStat.HasClink
            Benefit = "Unlocks dynamic git/timer prompt, autosuggestions & fuzzy history in CMD"
            Run = {
                & winget install --id chrisant996.Clink --source winget --accept-package-agreements --accept-source-agreements
                $clinkScripts = Join-Path $env:LOCALAPPDATA "clink"
                if (-not (Test-Path $clinkScripts)) { New-Item -ItemType Directory -Path $clinkScripts -Force | Out-Null }
                Copy-Item -Path (Join-Path $script:TxRoot "src\cmd\tx.lua") -Destination (Join-Path $clinkScripts "tx.lua") -Force
            }
            CmdText = "winget install chrisant996.Clink (+ install tx.lua)"
        },
        [ordered]@{
            Id = "psreadline"
            Name = "PSReadLine 2.3+"
            Installed = $envStat.PSReadLinePred
            Benefit = "Unlocks Fish-style inline command predictions in PowerShell"
            Run = { Install-Module PSReadLine -Scope CurrentUser -Force -AllowClobber -SkipPublisherCheck }
            CmdText = "Install-Module PSReadLine -Scope CurrentUser -Force"
        },
        [ordered]@{
            Id = "pwsh"
            Name = "PowerShell 7"
            Installed = $envStat.Pwsh7Installed
            Benefit = "Modern cross-platform PowerShell with faster startup & PSReadLine predictions"
            Run = { & winget install --id Microsoft.PowerShell --source winget --accept-package-agreements --accept-source-agreements }
            CmdText = "winget install Microsoft.PowerShell"
        }
    )

    if ($Target -eq "check" -or [string]::IsNullOrWhiteSpace($Target)) {
        Write-Host ""
        Write-Host (Format-TxGradient "  $($cfg.brand) Optional Enhancements" -Stops @($ui.gradientStart, $ui.gradientMid, $ui.gradientEnd) -Bold)
        Write-Host (Format-TxText ("  " + ([string][char]0x2500 * 64)) -Fg $ui.border)
        foreach ($it in $items) {
            $stat = if ($it.Installed) { Format-TxText "[INSTALLED]" -Fg $ui.success -Bold } else { Format-TxText "[AVAILABLE]" -Fg $ui.warning -Bold }
            Write-Host "  $stat  $(Format-TxText $it.Name.PadRight(26) -Fg $ui.primary -Bold)  $(Format-TxText $it.Id -Fg $ui.accent)"
            Write-Host "               $(Format-TxText $it.Benefit -Fg $ui.muted)"
            Write-Host "               $(Format-TxText "Command: $($it.CmdText)" -Fg $ui.muted)"
        }
        Write-Host ""
        Write-Host (Format-TxText "  Run 'tx upgrade <nerd-font|clink|psreadline|pwsh>' to install one." -Fg $ui.text)
        Write-Host ""
        return
    }

    $chosen = $items | Where-Object { $_.Id -eq $Target.ToLowerInvariant() }
    if (-not $chosen) {
        Write-Host (Format-TxText "Unknown upgrade target '$Target'. Valid: check, nerd-font, clink, psreadline, pwsh" -Fg $ui.error)
        return
    }

    Write-Host (Format-TxText "About to run: $($chosen.CmdText)" -Fg $ui.accent -Bold)
    if (-not $Yes) {
        $ans = Read-Host "Proceed? [y/N]"
        if ($ans -notmatch '^(y|yes)$') {
            Write-Host (Format-TxText "Cancelled." -Fg $ui.muted)
            return
        }
    }
    & $chosen.Run
    $script:TxSessionCache.Clear()
    $wt = Commit-TxConfig $cfg
    Write-Host (Format-TxText "Done! Restart your terminal window if a new font or Clink was installed." -Fg $ui.success -Bold)
}

function Show-TxHelp {
    $cfg = Get-TxConfig
    $ui = (Get-TxActiveTheme $cfg).ui
    $order = Get-TxThemeOrder
    $div = [string][char]0x2500 * 74

    Write-Host ""
    Write-Host (Format-TxGradient "  $($cfg.brand) Complete Guide & Command Reference" -Stops @($ui.gradientStart, $ui.gradientMid, $ui.gradientEnd) -Bold)
    Write-Host (Format-TxText "  Beautifies Windows Terminal, PowerShell (5.1/7+), and Command Prompt (CMD)" -Fg $ui.muted)
    Write-Host (Format-TxText "  $div" -Fg $ui.border)

    function Write-HelpSection {
        param([string]$Heading, [object[]]$Rows, [int]$ColW = 34)
        Write-Host ""
        Write-Host "  $(Format-TxText $Heading -Fg $ui.secondary -Bold)"
        foreach ($r in $Rows) {
            Write-Host "    $(Format-TxText $r[0].PadRight($ColW) -Fg $ui.primary -Bold) $(Format-TxText $r[1] -Fg $ui.text)"
        }
    }

    Write-HelpSection "1. THEME & CONTROL CENTER COMMANDS" @(
        @("tx",                            "Open interactive theme, HUD, appearance & tools control center"),
        @("tx list",                       "List all $($order.Count) themes with live TrueColor swatches"),
        @("tx theme <name|#>",             "Switch theme ($($order -join ' | '))"),
        @("tx brand <text>",               "Customize banner title shown in HUD & Control Center (default: TricksXTech)"),
        @("tx style <style>",              "Prompt layout: capsule | powerline | minimal | classic"),
        @("tx hud <mode>",                 "Startup System HUD: full | compact | off"),
        @("tx icons <mode>",               "Glyph icons mode: auto | unicode | nerd"),
        @("tx opacity <30-100>",           "Adjust Windows Terminal background opacity (%)"),
        @("tx acrylic <on|off>",           "Toggle Windows Terminal acrylic glass blur"),
        @("tx crt <auto|on|off>",          "Toggle Retro CRT scanline shader in Windows Terminal"),
        @("tx cursor <shape>",             "Cursor: bar | vintage | underscore | filledBox | doubleUnderscore"),
        @("tx font <name|auto> [size]",    "Set custom font family & point size in Windows Terminal"),
        @("tx segment <name> <on|off>",    "Toggle segment: admin, userHost, path, git, env, duration, exitCode, clock"),
        @("tx preview [theme]",            "Showcase live prompts & syntax colors without changing config"),
        @("tx status | tx doctor",         "Inspect active hooks, Nerd Font, Clink, PSReadLine & WT state"),
        @("tx upgrade [target]",           "Install upgrades: nerd-font | clink | psreadline | pwsh"),
        @("tx reset",                      "Reset user configuration back to defaults"),
        @("tx -help | tx help",            "Show this complete guide of themes, commands & built-in tools")
    )

    Write-HelpSection "2. BUILT-IN FREE TOOLS (PowerShell & CMD)" @(
        @("tools  (tools -i in PS)",       "Open the Free Tools Hub menu & interactive launcher"),
        @("disk | storage | diskanalyzer", "Interactive Drive/Folder Storage Analyzer & read-only cleanup advisor"),
        @("wifi | wificheck [--profiles]", "Wi-Fi signal meter, 2.4/5/6 GHz channel check & WPA3/WPA2/WEP audit"),
        @("osint <domain|ip>",             "Passive public OSINT: DoH DNS/SPF/DMARC, ASN/Geo, RDAP, TLS & headers"),
        @("subdomains <domain> [--resolve]","Passive CT-log subdomain discovery (crt.sh / certspotter)"),
        @("webtech <url|domain>",          "Passive single-request HTTP header, CDN & stack fingerprinter"),
        @("lan",                           "Read-only local ARP neighbor table, gateway & MAC OUI/LAA info"),
        @("portcheck <host> [p1,p2...]",   "Dev single-host TCP connectivity & latency check (max 25 ports)"),
        @("vpn [start|stop|next|sync|auto]","Auto-VPN + background 5-min IP rotation across synced & custom servers"),
        @("pwgen [len] [--words N]",       "Cryptographic password, API token & passphrase generator"),
        @("epoch [timestamp_or_iso]",      "Convert between Unix epoch (s/ms), UTC ISO-8601 & local time"),
        @("uuid [-n count] [--upper]",     "Generate random UUID v4 identifiers"),
        @("bigfiles [path] [topN]",        "Find top N largest files under a directory (default: . 20)"),
        @("procs [count] | syshealth",     "Top processes ranked by memory usage with resource bars"),
        @("netinfo | netcheck",            "Local IPv4 interfaces, DNS latency check & listening TCP ports"),
        @("hashfile <file> [expected]",    "Compute & verify MD5, SHA-1, SHA-256 & SHA-512 checksums"),
        @("loc [path]",                    "Count source code lines grouped by programming language"),
        @("jsonfmt <file>",                "Validate & pretty-print JSON with theme colors"),
        @("sysinfo | fetch",               "Render the full TricksXTech System Telemetry HUD on demand")
    )

    Write-HelpSection "3. LINUX-STYLE CLI UTILITIES (PowerShell & CMD)" @(
        @("grep [-i] [-r] [-v] [-c] <pat>", "Highlighted regex/text search across files, dirs, or piped stdin"),
        @("head [-n N] <file...>",         "Display the first N lines of files or piped stdin (default: 10)"),
        @("tail [-n N] [-f] <file...>",    "Display last N lines or follow log growth live with -f"),
        @("wc [-lwc] <file...>",           "Count lines, words, and bytes across files or stdin"),
        @("df [path]",                     "Mounted drive capacity, free space & usage bars"),
        @("du [path] [-n N]",              "Summarize immediate folder & file disk usage sorted by size"),
        @("udiff <file1> <file2>",         "Colorized unified diff (keeps PS built-in diff = Compare-Object)"),
        @("b64 [-d] [--hex|--url] <txt>",  "Base64, Hex, or URL encode/decode text or piped input"),
        @("jwt <token>",                   "Decode JWT header, claims & UTC timestamps (read-only)"),
        @("ss [-l] [-t|-u] [-p filter]",   "List listening/active TCP & UDP sockets mapped to PID & process")
    )

    Write-HelpSection "4. NAVIGATION, FILE & GIT SHORTCUTS" @(
        @("l | ll | la | lt [path]",       "Compact grid, rich Git-aware listing, hidden files, & tree view"),
        @("z <query>  (PowerShell)",       "Smart frecency directory jump to previously visited folders"),
        @(".. | ... | ....",               "Go up 1, 2, or 3 parent directories quickly"),
        @("mkcd <dir> | touch <file>",     "Create & enter directory; create or update file timestamp"),
        @("which <cmd> | ports | myip",    "Locate executable, list open ports (PS), or check public IP (PS)"),
        @("extract <zip/tar>  (PS)",       "Extract zip/archive cleanly into folder"),
        @("reload",                        "Reload theme, prompt & aliases in current shell"),
        @("gs | gst | ga | gaa | gd | gds","Git status, add, diff & staged diff shortcuts"),
        @("gc | gcm | glog | gbr | gp | gl","Git commit, graph log, branches, push & pull shortcuts")
    )

    Write-HelpSection "5. LIVE SPEEDOMETER & NETWORK UTILITIES" @(
        @("speedtest | netspeed",          "Live animated speedometer for Ping, Jitter, Download & Upload (--quick)"),
        @("dns <host> | rdns <ip>",        "Forward DNS and reverse PTR lookups"),
        @("cidr <subnet>",                 "Calculate network, broadcast, mask, and usable host count"),
        @("httpcode <url> | unshorten",    "Check HTTP status/latency or trace 301/302 redirect chains"),
        @("robots <url> | sitemap <url>",  "Parse robots.txt directives or extract sitemap.xml URLs"),
        @("titlemeta <url> | uaparse",     "Extract HTML title/meta tags or parse User-Agent strings"),
        @("serve [port] | lanspeed <dir>", "Quick local HTTP file server (127.0.0.1) & LAN write benchmark"),
        @("pingcheck <host> | ftpget",     "Min/avg/max ping stats or public FTP file downloader")
    )

    Write-HelpSection "6. SYSTEM & FILE DIAGNOSTICS" @(
        @("envfind [pat] | perms [path]",  "Filter active env vars or inspect file permissions & modes"),
        @("organize [dir] [--apply]",      "Sort files by extension into folders (--dry-run default)"),
        @("dupes [dir] | symlinks [dir]",  "Find duplicate files by SHA-256 or audit broken symlinks"),
        @("extrename | replace [--apply]", "Bulk rename extensions or search/replace text (--dry-run default)"),
        @("cleantemp [dir] [--apply]",     "Remove empty/.tmp/.log files safely (--dry-run default)"),
        @("watchdir [dir] | clip",         "Live folder change monitor; read/write Windows clipboard"),
        @("zipmgr | targz",                "Inspect, pack, or unpack .zip, .tar.gz & .tar.bz2 archives")
    )

    Write-HelpSection "7. CRYPTOGRAPHY & HASHING" @(
        @("hmac256 <key> <txt> | crc32",   "Compute HMAC-SHA256 signatures or CRC32 checksums"),
        @("rot13 | bin2txt | ascii",       "ROT13 cipher, binary-ASCII decoder, and char code inspector"),
        @("tokengen | entropy <pw>",       "Generate crypto hex/URL tokens & estimate password entropy"),
        @("bcryptcheck | htpasswd",        "Verify $2a$/$2b$/$2y$ hashes & generate Apache htpasswd lines"),
        @("fencrypt enc|dec <file>",       "AES-256-GCM + PBKDF2-SHA256 local file encryption"),
        @("rsagen [-b 2048] [-o prefix]",  "Generate local RSA PEM public/private key pairs")
    )

    Write-HelpSection "8. DEVELOPER & DATA UTILITIES" @(
        @("jsonmin | csv2json | json2csv", "Minify JSON and convert cleanly between CSV and JSON"),
        @("yaml2json | xmlfmt | tomlcheck","YAML<->JSON, XML formatter/validator, & TOML checker"),
        @("logparse <file> | cronparse",   "Extract IP/status stats from logs & explain cron expressions"),
        @("md2html | htmlent | sqlfmt",    "Markdown->HTML, HTML entity encode/decode, & SQL formatter"),
        @("colorconv | lorem | slugify",   "HEX/RGB/HSL swatch converter, placeholder text, & URL slugs"),
        @("caseconv | uniqsort",           "camel/snake/kebab/Pascal converter & unique line sorter")
    )

    Write-HelpSection "9. PRODUCTIVITY & WORKFLOW UTILITIES" @(
        @("stopwatch | countdown | pomodoro","Live lap stopwatch, progress countdown & work/break timer"),
        @("todo | notes | expense | habit","Local JSON task, note, expense & 7-day habit trackers"),
        @("bookmarks | contacts | aliases","URL bookmarks, SQLite contacts book & PS/CMD alias sync"),
        @("banner <text> | pbar [--demo]", "Gradient block banners & themed CLI pipeline progress bar"),
        @("calc <expr> | unitconv | tzconv","Safe AST math calculator, unit converter & world timezones"),
        @("weather [city] | fx <amt> A B", "Live wttr.in weather/forecast & live FX currency converter"),
        @("pick [items|--range|--coin]",   "Cryptographic random choice, dice roller & coin flip"),
        @("gitclean [--apply] | gitstats", "Dry-run merged branch pruner & Git contributor analytics")
    )

    Write-HelpSection "10. DEFENSIVE SECURITY, FORENSICS & HARDENING" @(
        @("secaudit",                      "Read-only Windows Firewall, Defender, SMBv1/RDP & 0.0.0.0 audit"),
        @("peinspect <file> | hexview",    "Static PE/ELF binary header, entropy & strings + canonical hex dump"),
        @("exifinfo <file> | stego",       "File magic verification, JPEG EXIF/GPS, PNG & trailer stego audit"),
        @("hashid <hash> | secretaudit",   "Offline hash/token identifier & local secret/misconfig scanner"),
        @("idncheck <domain> | wordgen",   "Homograph phishing Punycode detector & capped local wordlist gen"),
        @("hackingtool | ht [category]",   "Interactive security & forensic suite (or: ht list, ht info)"),
        @("crypto [trx|bnb|eth]",          "Cryptocurrency CLI utility launcher (TRX, BNB, ETH)")
    )

    Write-Host ""
    Write-Host (Format-TxText "  $div" -Fg $ui.border)
    Write-Host (Format-TxText "  Tip: Run 'tools' to see all utilities, 'tx preview <theme>' to test themes." -Fg $ui.muted)
    Write-Host ""
}

function Start-TxInteractiveUI {
    $themes = Get-TxThemes
    $themeOrder = Get-TxThemeOrder
    $styleOrder = @("capsule", "powerline", "minimal", "classic")
    $hudOrder   = @("full", "compact", "off")
    $iconOrder  = @("auto", "unicode", "nerd")
    $cursorOrder = @("bar", "filledBox", "underscore", "vintage", "doubleUnderscore")

    while ($true) {
        $cfg = Get-TxConfig
        $thm = Get-TxActiveTheme $cfg
        $ui = $thm.ui
        $pal = $thm.palette

        $brandLabel = if ($cfg.brand) { [string]$cfg.brand } else { "TricksXTech" }
        try { Clear-Host } catch { }
        Write-Host ""
        Write-Host (Format-TxGradient "  $brandLabel   C O N T R O L   C E N T E R" -Stops @($ui.gradientStart, $ui.gradientMid, $ui.gradientEnd) -Bold)
        Write-Host (Format-TxText ("  " + ([string][char]0x2500 * 64)) -Fg $ui.border)

        # Mini live preview bar
        $glyphs = Get-TxGlyphs -Mode (Resolve-TxGlyphMode $cfg)
        $sample = Invoke-TxRenderPrompt -Config $cfg -Theme $thm -Glyphs $glyphs -LastOk $true -LastCode 0 -DurationMs 420 -HasNewCmd $true
        Write-Host "  $(Format-TxText 'LIVE PROMPT PREVIEW:' -Fg $ui.muted)"
        $sLines = @($sample -split "`n")
        for ($li = 0; $li -lt $sLines.Count; $li++) {
            $sfx = if ($li -eq ($sLines.Count - 1)) { Format-TxText 'tx theme cyberpunk' -Fg $ui.text } else { "" }
            Write-Host "    $($sLines[$li])$sfx"
        }
        Write-Host (Format-TxText ("  " + ([string][char]0x2500 * 64)) -Fg $ui.border)

        Write-Host "  $(Format-TxText '[1]' -Fg $ui.accent -Bold) Theme         : $(Format-TxText $thm.name -Fg $ui.primary -Bold) $(Format-TxText ('(cycles ' + $themeOrder.Count + ' themes; run tx list for all)') -Fg $ui.muted)"
        Write-Host "  $(Format-TxText '[2]' -Fg $ui.accent -Bold) Prompt Style  : $(Format-TxText $cfg.style -Fg $ui.primary -Bold) $(Format-TxText '(cycles: capsule / powerline / minimal / classic)' -Fg $ui.muted)"
        Write-Host "  $(Format-TxText '[3]' -Fg $ui.accent -Bold) Startup HUD   : $(Format-TxText $cfg.hud -Fg $ui.primary -Bold) $(Format-TxText '(cycles: full / compact / off)' -Fg $ui.muted)"
        Write-Host "  $(Format-TxText '[4]' -Fg $ui.accent -Bold) Icon Mode     : $(Format-TxText "$($cfg.icons) ($(Resolve-TxGlyphMode $cfg))" -Fg $ui.primary -Bold)"
        Write-Host "  $(Format-TxText '[5]' -Fg $ui.accent -Bold) Acrylic Blur  : $(Format-TxText ([string]$cfg.wt.useAcrylic) -Fg $ui.primary -Bold)  |  Opacity: $(Format-TxText "$($cfg.wt.opacity)%" -Fg $ui.accent -Bold)"
        Write-Host "  $(Format-TxText '[6]' -Fg $ui.accent -Bold) Opacity Step  : $(Format-TxText 'cycle 100% / 95% / 90% / 82%' -Fg $ui.muted)"
        Write-Host "  $(Format-TxText '[7]' -Fg $ui.accent -Bold) Cursor Shape  : $(Format-TxText $cfg.wt.cursorShape -Fg $ui.primary -Bold)"
        Write-Host "  $(Format-TxText '[8]' -Fg $ui.accent -Bold) Retro CRT FX  : $(Format-TxText ([string]$cfg.wt.retroEffect) -Fg $ui.primary -Bold)"
        Write-Host "  $(Format-TxText '[T]' -Fg $ui.secondary -Bold) Free Tools Hub (Disk, Wi-Fi, OSINT, Linux CLI, BigFiles...)"
        Write-Host "  $(Format-TxText '[P]' -Fg $ui.secondary -Bold) Showcase All $($themeOrder.Count) Themes"
        Write-Host "  $(Format-TxText '[H]' -Fg $ui.secondary -Bold) Full Guide (All Commands & Tools)"
        Write-Host "  $(Format-TxText '[S]' -Fg $ui.secondary -Bold) System Status & Optional Upgrades"
        Write-Host "  $(Format-TxText '[Q]' -Fg $ui.error -Bold) Done / Exit"
        Write-Host ""

        $choice = Read-Host "  Choose option"
        switch ($choice.ToLowerInvariant().Trim()) {
            "1" {
                $idx = [Array]::IndexOf($themeOrder, $cfg.theme)
                $cfg.theme = $themeOrder[($idx + 1) % $themeOrder.Count]
                [void](Commit-TxConfig $cfg)
            }
            "2" {
                $idx = [Array]::IndexOf($styleOrder, $cfg.style)
                $cfg.style = $styleOrder[($idx + 1) % $styleOrder.Count]
                [void](Commit-TxConfig $cfg)
            }
            "3" {
                $idx = [Array]::IndexOf($hudOrder, $cfg.hud)
                $cfg.hud = $hudOrder[($idx + 1) % $hudOrder.Count]
                [void](Commit-TxConfig $cfg)
            }
            "4" {
                $idx = [Array]::IndexOf($iconOrder, $cfg.icons)
                $cfg.icons = $iconOrder[($idx + 1) % $iconOrder.Count]
                [void](Commit-TxConfig $cfg)
            }
            "5" {
                $cfg.wt.useAcrylic = -not [bool]$cfg.wt.useAcrylic
                [void](Commit-TxConfig $cfg)
            }
            "6" {
                $steps = @(100, 95, 90, 82)
                $cur = [int]$cfg.wt.opacity
                $nxt = ($steps | Where-Object { $_ -lt $cur } | Select-Object -First 1)
                if (-not $nxt) { $nxt = $steps[0] }
                $cfg.wt.opacity = $nxt
                [void](Commit-TxConfig $cfg)
            }
            "7" {
                $idx = [Array]::IndexOf($cursorOrder, $cfg.wt.cursorShape)
                $cfg.wt.cursorShape = $cursorOrder[($idx + 1) % $cursorOrder.Count]
                [void](Commit-TxConfig $cfg)
            }
            "8" {
                $modes = @("auto", $true, $false)
                $curStr = ([string]$cfg.wt.retroEffect).ToLowerInvariant()
                $nxt = switch ($curStr) { "auto" { $true } "true" { $false } default { "auto" } }
                $cfg.wt.retroEffect = $nxt
                [void](Commit-TxConfig $cfg)
            }
            "t" {
                $py = Get-Command python -ErrorAction SilentlyContinue
                if ($py) {
                    & $py.Source (Join-Path $script:TxRoot "tools\free_tools.py") --menu -i
                } else {
                    Write-Host "Python 3 is required for the Free Tools Hub." -ForegroundColor Yellow
                }
                Read-Host "  Press Enter to continue"
            }
            "p" {
                Show-TxPreview
                Read-Host "  Press Enter to continue"
            }
            "h" {
                Show-TxHelp
                Read-Host "  Press Enter to continue"
            }
            "s" {
                Show-TxStatus
                Invoke-TxUpgrade -Target "check"
                Read-Host "  Press Enter to continue"
            }
            { $_ -in @("q", "exit", "") } {
                return
            }
        }
    }
}

# Main Command Dispatch
if ($Help) {
    Show-TxHelp
    return
}

$cmd = $Command.ToLowerInvariant().Trim()
if ([string]::IsNullOrEmpty($cmd) -or $cmd -eq "ui") {
    Start-TxInteractiveUI
    return
}

$cfg = Get-TxConfig

switch ($cmd) {
    { $_ -in @("help", "guide", "-help", "-h", "--help", "/?") } {
        Show-TxHelp
    }
    "list" {
        Show-TxThemeCatalog -Config $cfg
    }
    "theme" {
        $resolved = Resolve-TxThemeId $Arg1
        if (-not $resolved) {
            Show-TxThemeCatalog -Config $cfg
            if ($Arg1) {
                $validIds = (Get-TxThemeOrder) -join ", "
                Write-Host (Format-TxText "Unknown theme '$Arg1'. Choose: $validIds" -Fg (Get-TxActiveTheme $cfg).ui.error)
            }
            return
        }
        $cfg.theme = $resolved
        $wt = Commit-TxConfig $cfg
        $thm = Get-TxActiveTheme $cfg
        $msg = "Switched theme to $($thm.name) [$($thm.id)]"
        if ($wt.Count -gt 0) { $msg += " (Windows Terminal updated live)" }
        Write-Host (Format-TxText $msg -Fg $thm.ui.success -Bold)
    }
    "style" {
        $valid = @("capsule", "powerline", "minimal", "classic")
        $val = $Arg1.ToLowerInvariant().Trim()
        if ($val -notin $valid) {
            Write-Host "Valid styles: $($valid -join ', ')" -ForegroundColor Yellow
            return
        }
        $cfg.style = $val
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Prompt style set to '$val'" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "hud" {
        $valid = @("full", "compact", "off")
        $val = $Arg1.ToLowerInvariant().Trim()
        if ($val -notin $valid) {
            Write-Host "Valid HUD modes: $($valid -join ', ')" -ForegroundColor Yellow
            return
        }
        $cfg.hud = $val
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Startup HUD set to '$val'" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "icons" {
        $valid = @("auto", "unicode", "nerd")
        $val = $Arg1.ToLowerInvariant().Trim()
        if ($val -notin $valid) {
            Write-Host "Valid icon modes: $($valid -join ', ')" -ForegroundColor Yellow
            return
        }
        $cfg.icons = $val
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Icon mode set to '$val' (effective: $(Resolve-TxGlyphMode $cfg))" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "opacity" {
        $op = 0
        if (-not [int]::TryParse($Arg1, [ref]$op) -or $op -lt 30 -or $op -gt 100) {
            Write-Host "Provide an opacity integer between 30 and 100." -ForegroundColor Yellow
            return
        }
        $cfg.wt.opacity = $op
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Windows Terminal opacity set to $op%" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "acrylic" {
        $on = $Arg1.ToLowerInvariant() -in @("on", "true", "1", "yes")
        $cfg.wt.useAcrylic = $on
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Windows Terminal acrylic set to $on" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "crt" {
        $val = $Arg1.ToLowerInvariant()
        $cfg.wt.retroEffect = switch ($val) { "on" { $true } "true" { $true } "off" { $false } "false" { $false } default { "auto" } }
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Retro CRT scanlines set to '$($cfg.wt.retroEffect)'" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "cursor" {
        $valid = @("bar", "vintage", "underscore", "filledBox", "doubleUnderscore")
        $match = $valid | Where-Object { $_.ToLowerInvariant() -eq $Arg1.ToLowerInvariant() } | Select-Object -First 1
        if (-not $match) {
            Write-Host "Valid cursor shapes: $($valid -join ', ')" -ForegroundColor Yellow
            return
        }
        $cfg.wt.cursorShape = $match
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Cursor shape set to '$match'" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "font" {
        if ([string]::IsNullOrWhiteSpace($Arg1)) {
            Write-Host "Usage: tx font <font-name|auto> [size]" -ForegroundColor Yellow
            return
        }
        $cfg.wt.fontFace = $Arg1
        $sz = 0
        if ($Arg2 -and [int]::TryParse($Arg2, [ref]$sz) -and $sz -ge 8 -and $sz -le 32) {
            $cfg.wt.fontSize = $sz
        }
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Font updated to '$($cfg.wt.fontFace)' (size $($cfg.wt.fontSize))" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "segment" {
        $valid = @("admin", "userHost", "path", "git", "env", "duration", "exitCode", "clock")
        $seg = $valid | Where-Object { $_.ToLowerInvariant() -eq $Arg1.ToLowerInvariant() } | Select-Object -First 1
        if (-not $seg) {
            Write-Host "Valid segments: $($valid -join ', ')" -ForegroundColor Yellow
            return
        }
        $on = if ($Arg2) { $Arg2.ToLowerInvariant() -in @("on", "true", "1", "yes") } else { -not [bool]$cfg.segments[$seg] }
        $cfg.segments[$seg] = $on
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Prompt segment '$seg' = $on" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "brand" {
        if ([string]::IsNullOrWhiteSpace($Arg1)) {
            Write-Host "Current brand: '$($cfg.brand)'. Usage: tx brand <name>" -ForegroundColor Yellow
            return
        }
        $cfg.brand = $Arg1.Trim()
        [void](Commit-TxConfig $cfg)
        Write-Host (Format-TxText "Banner brand updated to '$($cfg.brand)'" -Fg (Get-TxActiveTheme $cfg).ui.success -Bold)
    }
    "tools" {
        $py = Get-Command python -ErrorAction SilentlyContinue
        if ($py) {
            if ($Arg1 -eq "-i") {
                & $py.Source (Join-Path $script:TxRoot "tools\free_tools.py") --menu -i
            } else {
                & $py.Source (Join-Path $script:TxRoot "tools\free_tools.py") --menu
            }
        } else {
            Write-Host "Python 3 is required for the Free Tools Hub." -ForegroundColor Yellow
        }
    }
    "preview" {
        Show-TxPreview -TargetTheme $Arg1
    }
    { $_ -in @("status", "doctor") } {
        Show-TxStatus
    }
    "upgrade" {
        Invoke-TxUpgrade -Target $Arg1
    }
    "reset" {
        $userPath = Join-Path $script:TxRoot "config\user.json"
        if (Test-Path $userPath) { Remove-Item $userPath -Force }
        $fresh = Get-TxConfig
        [void](Commit-TxConfig $fresh)
        Write-Host (Format-TxText "TricksXTech config reset to defaults." -Fg (Get-TxActiveTheme $fresh).ui.success -Bold)
    }
    default {
        Write-Host "Unknown command '$Command'." -ForegroundColor Red
        Show-TxHelp
    }
}
