# TricksXTech PowerShell - Rich Themed Directory Listings (l, ll, la, lt)

function Format-TxFileSize {
    param([long]$Bytes)
    if ($Bytes -lt 1024) { return "$Bytes B" }
    if ($Bytes -lt 1MB) { return ("{0:N1} KB" -f ($Bytes / 1KB)) }
    if ($Bytes -lt 1GB) { return ("{0:N1} MB" -f ($Bytes / 1MB)) }
    return ("{0:N2} GB" -f ($Bytes / 1GB))
}

function Get-TxFileStyle {
    param(
        [System.IO.FileSystemInfo]$Item,
        [hashtable]$Theme,
        [hashtable]$Glyphs
    )
    $ui = $Theme.ui
    $pal = $Theme.palette

    if ($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        return @{ Icon = $Glyphs.Link; Color = $ui.accent; Bold = $true }
    }
    if ($Item.PSIsContainer) {
        return @{ Icon = $Glyphs.Dir; Color = $ui.primary; Bold = $true }
    }

    $ext = $Item.Extension.ToLowerInvariant()
    switch -Regex ($ext) {
        '^\.(exe|msi|bat|cmd|ps1|psm1|sh)$' {
            return @{ Icon = $Glyphs.Gear; Color = $ui.success; Bold = $true }
        }
        '^\.(py|js|jsx|ts|tsx|cs|rs|go|c|cpp|h|hpp|java|lua|rb|php|html|css|scss|sql)$' {
            return @{ Icon = $Glyphs.Code; Color = $ui.accent; Bold = $false }
        }
        '^\.(json|yaml|yml|toml|xml|ini|conf|config|env|psd1)$' {
            return @{ Icon = $Glyphs.Gear; Color = $ui.warning; Bold = $false }
        }
        '^\.(zip|tar|gz|7z|rar|bz2|xz)$' {
            return @{ Icon = $Glyphs.Archive; Color = $ui.secondary; Bold = $false }
        }
        '^\.(png|jpg|jpeg|gif|svg|webp|ico|bmp|mp4|mkv|mp3|wav)$' {
            return @{ Icon = $Glyphs.Image; Color = $pal.purple; Bold = $false }
        }
        '^\.(md|txt|log|pdf|doc|docx|csv)$' {
            return @{ Icon = $Glyphs.Doc; Color = $ui.text; Bold = $false }
        }
        default {
            if ($Item.Name.StartsWith(".")) {
                return @{ Icon = $Glyphs.File; Color = $ui.muted; Bold = $false }
            }
            return @{ Icon = $Glyphs.File; Color = $ui.text; Bold = $false }
        }
    }
}

function Get-TxGitFileMap {
    param([string]$TargetDir)
    $map = @{}
    $root = Find-TxGitRoot -StartPath $TargetDir
    if (-not $root) { return $map }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return $map }
    try {
        $lines = & git -C $TargetDir status --porcelain 2>$null
        if ($LASTEXITCODE -ne 0) { return $map }
        foreach ($l in $lines) {
            if ($l.Length -ge 4) {
                $code = $l.Substring(0, 2).Trim()
                $rel = $l.Substring(3).Trim('"')
                if ($rel -match ' -> (.+)$') { $rel = $Matches[1] }
                $full = Join-Path $root ($rel -replace '/', '\')
                $map[$full.ToLowerInvariant()] = $code
            }
        }
    } catch { }
    return $map
}

function Show-TxFileList {
    param(
        [string]$Path = ".",
        [switch]$All,
        [switch]$Compact
    )
    $cfg = if ($script:TxRuntimeConfig) { $script:TxRuntimeConfig } else { Get-TxConfig }
    $theme = if ($script:TxRuntimeTheme) { $script:TxRuntimeTheme } else { Get-TxActiveTheme $cfg }
    $glyphs = if ($script:TxRuntimeGlyphs) { $script:TxRuntimeGlyphs } else { Get-TxGlyphs -Mode (Resolve-TxGlyphMode $cfg) }
    $ui = $theme.ui

    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $resolved) {
        Write-Host (Format-TxText "Path not found: $Path" -Fg $ui.error)
        return
    }
    $targetPath = $resolved.ProviderPath
    $items = Get-ChildItem -LiteralPath $targetPath -Force:$All -ErrorAction SilentlyContinue |
        Sort-Object @{Expression = { -not $_.PSIsContainer }}, Name

    if (-not $items -or $items.Count -eq 0) {
        Write-Host (Format-TxText "  (empty directory)" -Fg $ui.muted)
        return
    }

    if ($Compact) {
        $cols = @()
        $maxLen = 0
        foreach ($it in $items) {
            $len = $it.Name.Length + 4
            if ($len -gt $maxLen) { $maxLen = $len }
        }
        $colW = [Math]::Max(18, [Math]::Min(36, $maxLen + 2))
        $winW = 90
        try { if ($Host.UI.RawUI.WindowSize.Width -gt 30) { $winW = $Host.UI.RawUI.WindowSize.Width } } catch { }
        $numCols = [Math]::Max(1, [int][Math]::Floor($winW / $colW))
        $row = ""
        $idx = 0
        foreach ($it in $items) {
            $st = Get-TxFileStyle -Item $it -Theme $theme -Glyphs $glyphs
            $name = if ($it.PSIsContainer) { "$($it.Name)/" } else { $it.Name }
            if ($name.Length -gt ($colW - 4)) { $name = $name.Substring(0, $colW - 7) + "..." }
            $cell = (Format-TxText "$($st.Icon) " -Fg $st.Color) + (Format-TxText $name -Fg $st.Color -Bold:$st.Bold)
            $row += (Format-TxPadRight -Text $cell -Width $colW)
            $idx++
            if (($idx % $numCols) -eq 0) {
                Write-Host $row
                $row = ""
            }
        }
        if ($row) { Write-Host $row }
        return
    }

    $gitMap = Get-TxGitFileMap -TargetDir $targetPath
    $hdr = " " +
        (Format-TxText ("Mode".PadRight(8)) -Fg $ui.muted -Bold) +
        (Format-TxText ("Size".PadLeft(10)) -Fg $ui.muted -Bold) + "  " +
        (Format-TxText ("Modified".PadRight(18)) -Fg $ui.muted -Bold) +
        (Format-TxText "Git  " -Fg $ui.muted -Bold) +
        (Format-TxText "Name" -Fg $ui.muted -Bold)
    Write-Host $hdr
    Write-Host (Format-TxText (" " + ([string][char]0x2500 * 66)) -Fg $ui.border)

    $dirCount = 0
    $fileCount = 0
    $totalBytes = [long]0

    foreach ($it in $items) {
        $st = Get-TxFileStyle -Item $it -Theme $theme -Glyphs $glyphs
        $modeStr = $it.Mode.PadRight(8)
        if ($it.PSIsContainer) {
            $dirCount++
            $sizeStr = "<DIR>".PadLeft(10)
            $sizeColor = $ui.secondary
        } else {
            $fileCount++
            $totalBytes += $it.Length
            $sizeStr = (Format-TxFileSize $it.Length).PadLeft(10)
            $sizeColor = $ui.muted
        }
        $dateStr = $it.LastWriteTime.ToString("yyyy-MM-dd HH:mm").PadRight(18)

        $gCode = ""
        $fullKey = $it.FullName.ToLowerInvariant()
        if ($gitMap.ContainsKey($fullKey)) {
            $gCode = $gitMap[$fullKey]
        }
        $gBadge = if ($gCode) {
            $gClr = if ($gCode -match '\?') { $ui.accent } elseif ($gCode -match 'A') { $ui.success } else { $ui.warning }
            Format-TxText ($gCode.PadRight(5)) -Fg $gClr -Bold
        } else {
            "     "
        }

        $dispName = if ($it.PSIsContainer) { "$($it.Name)/" } else { $it.Name }
        $line = " " +
            (Format-TxText $modeStr -Fg $ui.muted) +
            (Format-TxText $sizeStr -Fg $sizeColor) + "  " +
            (Format-TxText $dateStr -Fg $ui.muted) +
            $gBadge +
            (Format-TxText "$($st.Icon) " -Fg $st.Color) +
            (Format-TxText $dispName -Fg $st.Color -Bold:$st.Bold)
        Write-Host $line
    }

    $summary = " $dirCount dirs, $fileCount files ($(Format-TxFileSize $totalBytes))"
    Write-Host (Format-TxText $summary -Fg $ui.muted)
}

function Show-TxTree {
    param(
        [string]$Path = ".",
        [int]$Depth = 2,
        [switch]$All
    )
    $cfg = if ($script:TxRuntimeConfig) { $script:TxRuntimeConfig } else { Get-TxConfig }
    $theme = if ($script:TxRuntimeTheme) { $script:TxRuntimeTheme } else { Get-TxActiveTheme $cfg }
    $glyphs = if ($script:TxRuntimeGlyphs) { $script:TxRuntimeGlyphs } else { Get-TxGlyphs -Mode (Resolve-TxGlyphMode $cfg) }
    $ui = $theme.ui

    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $resolved) {
        Write-Host (Format-TxText "Path not found: $Path" -Fg $ui.error)
        return
    }
    $rootItem = Get-Item -LiteralPath $resolved.ProviderPath
    Write-Host (Format-TxText "$($glyphs.Folder) $($rootItem.FullName)" -Fg $ui.primary -Bold)

    $tee = [string][char]0x251C + [string][char]0x2500 + [string][char]0x2500 + " "
    $end = [string][char]0x2514 + [string][char]0x2500 + [string][char]0x2500 + " "
    $bar = [string][char]0x2502 + "   "

    function Walk-Tree([string]$Dir, [string]$Prefix, [int]$Level) {
        if ($Level -gt $Depth) { return }
        $children = Get-ChildItem -LiteralPath $Dir -Force:$All -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notin @('.git', 'node_modules', '__pycache__') -or $All } |
            Sort-Object @{Expression = { -not $_.PSIsContainer }}, Name
        if (-not $children) { return }
        $count = $children.Count
        for ($i = 0; $i -lt $count; $i++) {
            $it = $children[$i]
            $isLast = ($i -eq ($count - 1))
            $branch = if ($isLast) { $end } else { $tee }
            $st = Get-TxFileStyle -Item $it -Theme $theme -Glyphs $glyphs
            $name = if ($it.PSIsContainer) { "$($it.Name)/" } else { $it.Name }
            Write-Host ("$Prefix$(Format-TxText $branch -Fg $ui.border)$(Format-TxText "$($st.Icon) $name" -Fg $st.Color -Bold:$st.Bold)")
            if ($it.PSIsContainer -and $Level -lt $Depth) {
                $nextPrefix = $Prefix + (if ($isLast) { "    " } else { Format-TxText $bar -Fg $ui.border })
                Walk-Tree -Dir $it.FullName -Prefix $nextPrefix -Level ($Level + 1)
            }
        }
    }

    Walk-Tree -Dir $rootItem.FullName -Prefix "" -Level 1
}

function l  { param([string]$Path = ".") Show-TxFileList -Path $Path -Compact }
function ll { param([string]$Path = ".") Show-TxFileList -Path $Path }
function la { param([string]$Path = ".") Show-TxFileList -Path $Path -All }
function lt { param([string]$Path = ".", [int]$Depth = 2, [switch]$All) Show-TxTree -Path $Path -Depth $Depth -All:$All }
