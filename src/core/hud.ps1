# TricksXTech Core - Welcome Dashboard & System HUD

function Format-TxMeterBar {
    param(
        [int]$Percent,
        [int]$Width = 14,
        [hashtable]$Theme
    )
    $ui = $Theme.ui
    $clamped = [Math]::Max(0, [Math]::Min(100, $Percent))
    $filled = [int][Math]::Round(($clamped / 100.0) * $Width)
    $empty = $Width - $filled
    $fillColor = if ($clamped -ge 85) { $ui.error } elseif ($clamped -ge 65) { $ui.warning } else { $ui.success }
    $fillChar = [string][char]0x2501  # ━
    $emptyChar = [string][char]0x2500 # ─
    $fStr = if ($filled -gt 0) { Format-TxText ($fillChar * $filled) -Fg $fillColor -Bold } else { "" }
    $eStr = if ($empty -gt 0) { Format-TxText ($emptyChar * $empty) -Fg $ui.muted } else { "" }
    return "$fStr$eStr"
}

function Show-TxHud {
    param(
        [hashtable]$Config,
        [hashtable]$Theme,
        [switch]$Force,
        [switch]$IncludeNetwork
    )
    if (-not $Config) { $Config = Get-TxConfig }
    if (-not $Theme) { $Theme = Get-TxActiveTheme $Config }

    $mode = if ($Force) { "full" } else { $Config.hud }
    if ($mode -eq "off") { return }

    $ui = $Theme.ui
    $pal = $Theme.palette
    $glyphMode = Resolve-TxGlyphMode $Config
    $g = Get-TxGlyphs -Mode $glyphMode
    $box = $g.Box
    $stops = @($ui.gradientStart, $ui.gradientMid, $ui.gradientEnd)

    $brandName = if ($Config.brand) { [string]$Config.brand } else { "TricksXTech" }

    if ($mode -eq "compact") {
        $git = Get-TxGitStatus
        $userBadge = Format-TxText "$($env:USERNAME)@$($env:COMPUTERNAME)" -Fg $ui.accent -Bold
        $themeBadge = Format-TxText $Theme.name -Fg $ui.primary -Bold
        $styleBadge = Format-TxText "$($Config.style)/$glyphMode" -Fg $ui.secondary
        $title = Format-TxGradient $brandName -Stops $stops -Bold
        $line = " $title $(Format-TxText $box.V -Fg $ui.border) $userBadge $(Format-TxText $box.V -Fg $ui.border) $themeBadge ($styleBadge)"
        if ($git) {
            $gStat = if ($git.IsDirty) { Format-TxText "*$($git.Branch)" -Fg $ui.warning } else { Format-TxText $git.Branch -Fg $ui.success }
            $line += " $(Format-TxText $box.V -Fg $ui.border) git:$gStat"
        }
        Write-Host ""
        Write-Host $line
        Write-Host (Format-TxText "   tx (themes)  |  tools (tools hub)  |  ht (suite)  |  disk (analyzer)  |  ll (files)  |  sysinfo (HUD)" -Fg $ui.muted)
        Write-Host ""
        return
    }

    $info = Get-TxSystemInfo -IncludeNetwork:$IncludeNetwork
    $git = Get-TxGitStatus

    # Determine responsive inner box width (keep neat 72 chars unless console is narrower)
    $consoleWidth = 80
    try {
        if ($Host.UI.RawUI.WindowSize.Width -gt 40) {
            $consoleWidth = $Host.UI.RawUI.WindowSize.Width
        }
    } catch { }
    $innerWidth = [Math]::Min(74, [Math]::Max(58, $consoleWidth - 4))

    $borderFg = $ui.border
    $topBar = (Format-TxText "$($box.TL)$($box.H * $innerWidth)$($box.TR)" -Fg $borderFg)
    $midBar = (Format-TxText "$($box.LT)$($box.H * $innerWidth)$($box.RT)" -Fg $borderFg)
    $botBar = (Format-TxText "$($box.BL)$($box.H * $innerWidth)$($box.BR)" -Fg $borderFg)
    $vL = Format-TxText "$($box.V) " -Fg $borderFg
    $vR = Format-TxText " $($box.V)" -Fg $borderFg
    $contentWidth = $innerWidth - 2

    function Write-HudRow([string]$Content) {
        $padded = Format-TxPadRight -Text $Content -Width $contentWidth
        Write-Host "$vL$padded$vR"
    }

    # Swatch bar of theme colors
    $dot = $g.Dot
    $swatches = @(
        $pal.red, $pal.yellow, $pal.green, $pal.cyan, $pal.blue, $pal.purple
    ) | ForEach-Object { Format-TxText $dot -Fg $_ }
    $swatchStr = $swatches -join " "

    $logoText = "  $brandName"
    $headerLeft = Format-TxGradient $logoText -Stops $stops -Bold
    $themePill = Format-TxText "[$($Theme.name)]" -Fg $ui.primary -Bold
    $adminPill = if ($info.IsAdmin) { " " + (Format-TxText "ADMIN" -Fg $ui.darkText -Bg $ui.warning -Bold) } else { "" }

    $leftVis = Get-TxVisibleLength $headerLeft
    $rightPart = "$themePill$adminPill  $swatchStr"
    $rightVis = Get-TxVisibleLength $rightPart
    $gap = [Math]::Max(1, $contentWidth - $leftVis - $rightVis)
    $headerRow = "$headerLeft$(' ' * $gap)$rightPart"

    function Format-Kv([string]$Label, [string]$Value, [string]$ValColor = $ui.text) {
        $lbl = Format-TxText ($Label.PadRight(9)) -Fg $ui.secondary -Bold
        $val = Format-TxText $Value -Fg $ValColor
        return " $lbl $val"
    }

    # Build info rows
    $userHost = "$($info.User)@$($info.Host)"
    $cpuShort = $info.CPU
    if ($cpuShort.Length -gt ($contentWidth - 12)) {
        $cpuShort = $cpuShort.Substring(0, $contentWidth - 15) + "..."
    }

    $ramBar = Format-TxMeterBar -Percent $info.RAMPct -Width 14 -Theme $Theme
    $ramText = if ($info.RAMTotalGB -gt 0) {
        "$ramBar $(Format-TxText "$($info.RAMUsedGB)/$($info.RAMTotalGB) GB ($($info.RAMPct)%)" -Fg $ui.text)"
    } else {
        Format-TxText "Unavailable" -Fg $ui.muted
    }

    $diskBar = Format-TxMeterBar -Percent $info.DiskPct -Width 14 -Theme $Theme
    $diskText = if ($info.DiskTotalGB -gt 0) {
        "$diskBar $(Format-TxText "$($info.Drive) $($info.DiskUsedGB)/$($info.DiskTotalGB) GB ($($info.DiskPct)%)" -Fg $ui.text)"
    } else {
        Format-TxText "Unavailable" -Fg $ui.muted
    }

    $shellLine = "$($info.Shell)  $(Format-TxText $g.Diamond -Fg $ui.muted)  style:$(Format-TxText $Config.style -Fg $ui.accent)  icons:$(Format-TxText $glyphMode -Fg $ui.accent)"
    $upPower = "$($info.Uptime)  $(Format-TxText $g.Diamond -Fg $ui.muted)  Power: $($info.Power)"
    if ($info.IP) {
        $upPower += "  $(Format-TxText $g.Diamond -Fg $ui.muted)  IP: $($info.IP)"
    }

    Write-Host ""
    Write-Host $topBar
    Write-HudRow $headerRow
    Write-Host $midBar
    Write-HudRow (Format-Kv "Host" $userHost $ui.accent)
    Write-HudRow (Format-Kv "OS" $info.OS $ui.text)
    Write-HudRow (" $(Format-TxText ('Shell'.PadRight(9)) -Fg $ui.secondary -Bold) $shellLine")
    Write-HudRow (Format-Kv "CPU" $cpuShort $ui.text)
    Write-HudRow (" $(Format-TxText ('Memory'.PadRight(9)) -Fg $ui.secondary -Bold) $ramText")
    Write-HudRow (" $(Format-TxText ('Disk'.PadRight(9)) -Fg $ui.secondary -Bold) $diskText")
    Write-HudRow (Format-Kv "Uptime" $upPower $ui.text)

    if ($git) {
        $gitBadge = Format-TxText "$($git.RepoName) [$($git.Branch)]" -Fg $ui.primary -Bold
        $gitState = if ($git.IsDirty) {
            $parts = @()
            if ($git.Staged -gt 0) { $parts += "+$($git.Staged)" }
            if ($git.Modified -gt 0) { $parts += "~$($git.Modified)" }
            if ($git.Untracked -gt 0) { $parts += "?$($git.Untracked)" }
            if ($git.Conflicts -gt 0) { $parts += "!$($git.Conflicts)" }
            Format-TxText ($parts -join " ") -Fg $ui.warning
        } else {
            Format-TxText "$($g.Check) clean" -Fg $ui.success
        }
        $ab = ""
        if ($git.Ahead -gt 0) { $ab += " $($g.Up)$($git.Ahead)" }
        if ($git.Behind -gt 0) { $ab += " $($g.Down)$($git.Behind)" }
        $abStr = if ($ab) { Format-TxText $ab -Fg $ui.accent } else { "" }
        Write-HudRow (" $(Format-TxText ('Git'.PadRight(9)) -Fg $ui.secondary -Bold) $gitBadge  $gitState$abStr")
    }

    $vpnStatePath = Join-Path (Get-TxRootPath) "config\vpn_state.json"
    if (Test-Path $vpnStatePath) {
        try {
            $vst = Get-Content -Path $vpnStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($vst -and $vst.running -and ($vst.status -eq "connected") -and $vst.heartbeat) {
                $nowEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
                if (($nowEpoch - [double]$vst.heartbeat) -le 20) {
                    $rem = [Math]::Max(0, [int]([double]$vst.next_rotate_at - $nowEpoch))
                    $mins = [int][Math]::Floor($rem / 60)
                    $secs = $rem % 60
                    $vpnTxt = "ACTIVE  $($vst.exit_ip) ($($vst.target_name))  swap {0:D2}m {1:D2}s" -f $mins, $secs
                    Write-HudRow (Format-Kv "VPN" $vpnTxt $ui.success)
                }
            }
        } catch { }
    }

    Write-Host $midBar
    $tips = " " +
        (Format-TxText "tx" -Fg $ui.primary -Bold) + (Format-TxText " themes " -Fg $ui.muted) +
        (Format-TxText "tools" -Fg $ui.accent -Bold) + (Format-TxText " hub " -Fg $ui.muted) +
        (Format-TxText "ht" -Fg $ui.accent -Bold) + (Format-TxText " suite " -Fg $ui.muted) +
        (Format-TxText "disk" -Fg $ui.accent -Bold) + (Format-TxText " analyzer " -Fg $ui.muted) +
        (Format-TxText "ll" -Fg $ui.accent -Bold) + (Format-TxText " files " -Fg $ui.muted) +
        (Format-TxText "z" -Fg $ui.accent -Bold) + (Format-TxText " jump " -Fg $ui.muted) +
        (Format-TxText "sysinfo" -Fg $ui.accent -Bold) + (Format-TxText " HUD" -Fg $ui.muted)
    Write-HudRow $tips
    Write-Host $botBar
    Write-Host ""
}
