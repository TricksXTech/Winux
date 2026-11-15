# TricksXTech Core - ANSI TrueColor, UTF-8, and Glyph Utilities
# Pure ASCII source for 100% compatibility with Windows PowerShell 5.1 and PowerShell 7+.

$script:TxEsc = [char]27
$script:TxRgbCache = @{}

function Initialize-TxEncoding {
    try {
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [Console]::OutputEncoding = $utf8NoBom
        [Console]::InputEncoding = $utf8NoBom
        $global:OutputEncoding = $utf8NoBom
    } catch {
        # Ignore when host lacks interactive console stream
    }
}

function ConvertFrom-TxHex {
    param([Parameter(Mandatory = $true)][string]$Hex)
    $clean = $Hex.TrimStart('#').ToUpperInvariant()
    if ($script:TxRgbCache.ContainsKey($clean)) {
        return $script:TxRgbCache[$clean]
    }
    if ($clean.Length -eq 3) {
        $clean = "$($clean[0])$($clean[0])$($clean[1])$($clean[1])$($clean[2])$($clean[2])"
    }
    if ($clean.Length -ne 6) {
        $rgb = @(255, 255, 255)
    } else {
        $rgb = @(
            [Convert]::ToInt32($clean.Substring(0, 2), 16),
            [Convert]::ToInt32($clean.Substring(2, 2), 16),
            [Convert]::ToInt32($clean.Substring(4, 2), 16)
        )
    }
    $script:TxRgbCache[$clean] = $rgb
    return $rgb
}

function Get-TxFg {
    param([string]$Hex)
    if ([string]::IsNullOrWhiteSpace($Hex)) { return "" }
    $c = ConvertFrom-TxHex $Hex
    return "$($script:TxEsc)[38;2;$($c[0]);$($c[1]);$($c[2])m"
}

function Get-TxBg {
    param([string]$Hex)
    if ([string]::IsNullOrWhiteSpace($Hex)) { return "" }
    $c = ConvertFrom-TxHex $Hex
    return "$($script:TxEsc)[48;2;$($c[0]);$($c[1]);$($c[2])m"
}

function Get-TxReset {
    return "$($script:TxEsc)[0m"
}

function Format-TxText {
    param(
        [AllowEmptyString()][string]$Text,
        [string]$Fg = "",
        [string]$Bg = "",
        [switch]$Bold,
        [switch]$Dim,
        [switch]$Italic,
        [switch]$Underline
    )
    $seq = ""
    if ($Bold) { $seq += "$($script:TxEsc)[1m" }
    if ($Dim) { $seq += "$($script:TxEsc)[2m" }
    if ($Italic) { $seq += "$($script:TxEsc)[3m" }
    if ($Underline) { $seq += "$($script:TxEsc)[4m" }
    if ($Fg) { $seq += (Get-TxFg $Fg) }
    if ($Bg) { $seq += (Get-TxBg $Bg) }
    if (-not $seq) { return $Text }
    return "$seq$Text$($script:TxEsc)[0m"
}

function Format-TxGradient {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string[]]$Stops,
        [switch]$Bold
    )
    if ([string]::IsNullOrEmpty($Text)) { return "" }
    if ($Stops.Count -lt 2) {
        return (Format-TxText $Text -Fg $Stops[0] -Bold:$Bold)
    }
    $chars = $Text.ToCharArray()
    $len = $chars.Length
    if ($len -eq 1) {
        return (Format-TxText $Text -Fg $Stops[0] -Bold:$Bold)
    }
    $sb = New-Object System.Text.StringBuilder
    if ($Bold) { [void]$sb.Append("$($script:TxEsc)[1m") }
    $segments = $Stops.Count - 1
    for ($i = 0; $i -lt $len; $i++) {
        $ch = $chars[$i]
        if ($ch -eq ' ') {
            [void]$sb.Append(' ')
            continue
        }
        $t = $i / [double]($len - 1)
        $scaled = $t * $segments
        $idx = [Math]::Min([int][Math]::Floor($scaled), $segments - 1)
        $localT = $scaled - $idx
        $c1 = ConvertFrom-TxHex $Stops[$idx]
        $c2 = ConvertFrom-TxHex $Stops[$idx + 1]
        $r = [int][Math]::Round($c1[0] + ($c2[0] - $c1[0]) * $localT)
        $g = [int][Math]::Round($c1[1] + ($c2[1] - $c1[1]) * $localT)
        $b = [int][Math]::Round($c1[2] + ($c2[2] - $c1[2]) * $localT)
        [void]$sb.Append("$($script:TxEsc)[38;2;$r;$g;$b`m$ch")
    }
    [void]$sb.Append("$($script:TxEsc)[0m")
    return $sb.ToString()
}

function Strip-TxAnsi {
    param([AllowEmptyString()][string]$Text)
    if ([string]::IsNullOrEmpty($Text)) { return "" }
    $esc = [string]$script:TxEsc
    $stripped = [regex]::Replace($Text, "$esc\[[0-9;?]*[A-Za-z]", "")
    $stripped = [regex]::Replace($stripped, "$esc\][^\a\x1b]*(\a|$esc\\)", "")
    return $stripped
}

function Get-TxVisibleLength {
    param([AllowEmptyString()][string]$Text)
    return (Strip-TxAnsi $Text).Length
}

function Format-TxPadRight {
    param(
        [AllowEmptyString()][string]$Text,
        [int]$Width
    )
    $vis = Get-TxVisibleLength $Text
    if ($vis -ge $Width) { return $Text }
    return $Text + (' ' * ($Width - $vis))
}

function Get-TxGlyphs {
    param([ValidateSet("unicode", "nerd")][string]$Mode = "unicode")

    $box = @{
        TL = [string][char]0x256D  # ╭
        TR = [string][char]0x256E  # ╮
        BL = [string][char]0x2570  # ╰
        BR = [string][char]0x256F  # ╯
        H  = [string][char]0x2500  # ─
        V  = [string][char]0x2502  # │
        LT = [string][char]0x251C  # ├
        RT = [string][char]0x2524  # ┤
        BlockFull = [string][char]0x2588 # █
        BlockMed  = [string][char]0x2593 # ▓
        BlockLight= [string][char]0x2591 # ░
        BarFill   = [string][char]0x2501 # ━
    }

    if ($Mode -eq "nerd") {
        return @{
            Mode       = "nerd"
            Box        = $box
            Chevron    = [string][char]0x276F     # ❯
            SubArrow   = [string][char]0x2570 + [string][char]0x2500 # ╰─
            Admin      = [string][char]0xF0E7     # nf-fa-bolt
            User       = [string][char]0xF007     # nf-fa-user
            Folder     = [string][char]0xF07C     # nf-fa-folder_open
            GitBranch  = [string][char]0xE0A0     # nf-pl-branch
            GitDirty   = [string][char]0xF06A     # nf-fa-exclamation_circle
            GitClean   = [string][char]0xF00C     # nf-fa-check
            Up         = [string][char]0x2191     # ↑
            Down       = [string][char]0x2193     # ↓
            Check      = [string][char]0xF00C     # nf-fa-check
            Cross      = [string][char]0xF00D     # nf-fa-times
            Timer      = [string][char]0xF017     # nf-fa-clock_o
            Clock      = [string][char]0xF017
            Python     = [string][char]0xE73C     # nf-dev-python
            Node       = [string][char]0xE718     # nf-dev-nodejs_small
            Rust       = [string][char]0xE7A8     # nf-dev-rust
            Go         = [string][char]0xE627     # nf-seti-go
            Docker     = [string][char]0xF308     # nf-linux-docker
            Shell      = [string][char]0xE795     # nf-dev-terminal
            CapLeft    = [string][char]0xE0B6     # 
            CapRight   = [string][char]0xE0B4     # 
            PlRight    = [string][char]0xE0B0     # 
            PlLeft     = [string][char]0xE0B2     # 
            PlThinR    = [string][char]0xE0B1     # 
            Diamond    = [string][char]0x25C6     # ◆
            Dot        = [string][char]0x25CF     # ●
            Star       = [string][char]0x2605     # ★
            File       = [string][char]0xF15B     # nf-fa-file
            Dir        = [string][char]0xF07B     # nf-fa-folder
            Link       = [string][char]0xF0C1     # nf-fa-link
            Gear       = [string][char]0xF013     # nf-fa-cog
            Code       = [string][char]0xF121     # nf-fa-code
            Image      = [string][char]0xF1C5     # nf-fa-file_image_o
            Archive    = [string][char]0xF1C6     # nf-fa-file_archive_o
            Doc        = [string][char]0xF15C     # nf-fa-file_text
        }
    }

    return @{
        Mode       = "unicode"
        Box        = $box
        Chevron    = [string][char]0x276F     # ❯
        SubArrow   = [string][char]0x2570 + [string][char]0x2500 # ╰─
        Admin      = [string][char]0x26A1     # ⚡
        User       = [string][char]0x25C8     # ◈
        Folder     = [string][char]0x25B8     # ▸
        GitBranch  = [string][char]0x2387     # ⎇
        GitDirty   = [string][char]0x00B1     # ±
        GitClean   = [string][char]0x2713     # ✓
        Up         = [string][char]0x2191     # ↑
        Down       = [string][char]0x2193     # ↓
        Check      = [string][char]0x2713     # ✓
        Cross      = [string][char]0x2718     # ✘
        Timer      = [string][char]0x23F1     # ⏱ (fallback safe)
        Clock      = [string][char]0x25F7     # ◷
        Python     = "py"
        Node       = "js"
        Rust       = "rs"
        Go         = "go"
        Docker     = "dk"
        Shell      = ""
        CapLeft    = [string][char]0x2590     # ▐
        CapRight   = [string][char]0x258C     # ▌
        PlRight    = [string][char]0x25B6     # ▶
        PlLeft     = [string][char]0x25C0     # ◀
        PlThinR    = [string][char]0x203A     # ›
        Diamond    = [string][char]0x25C6     # ◆
        Dot        = [string][char]0x25CF     # ●
        Star       = [string][char]0x2605     # ★
        File       = [string][char]0x25AB     # ▫
        Dir        = [string][char]0x25B8     # ▸
        Link       = [string][char]0x21AA     # ↪
        Gear       = [string][char]0x2699     # ⚙
        Code       = [string][char]0x27E8 + [string][char]0x27E9 # ⟨⟩
        Image      = [string][char]0x25A3     # ▣
        Archive    = [string][char]0x25A4     # ▤
        Doc        = [string][char]0x2261     # ≡
    }
}
