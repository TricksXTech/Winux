# TricksXTech Core - Configuration, Theme Loader, and Environment Detection

$script:TxSessionCache = @{}

function Get-TxRootPath {
    if ($script:TxRoot -and (Test-Path $script:TxRoot)) {
        return $script:TxRoot
    }
    return (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
}

function Read-TxJsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    return ($raw | ConvertFrom-Json)
}

function Write-TxUtf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        [void](New-Item -ItemType Directory -Path $dir -Force)
    }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

function ConvertTo-TxHashtable {
    param([Parameter(ValueFromPipeline = $true)]$InputObject)
    if ($null -eq $InputObject) { return $null }
    if ($InputObject -is [System.Collections.IDictionary]) {
        $ht = @{}
        foreach ($k in $InputObject.Keys) {
            $ht[$k] = ConvertTo-TxHashtable $InputObject[$k]
        }
        return $ht
    }
    if ($InputObject -is [PSCustomObject]) {
        $ht = @{}
        foreach ($prop in $InputObject.PSObject.Properties) {
            $ht[$prop.Name] = ConvertTo-TxHashtable $prop.Value
        }
        return $ht
    }
    if ($InputObject -is [System.Collections.IEnumerable] -and -not ($InputObject -is [string])) {
        $arr = @()
        foreach ($item in $InputObject) {
            $arr += ,(ConvertTo-TxHashtable $item)
        }
        return $arr
    }
    return $InputObject
}

function Merge-TxHashtables {
    param(
        [hashtable]$Base,
        [hashtable]$Override
    )
    $result = @{}
    foreach ($k in $Base.Keys) {
        $result[$k] = $Base[$k]
    }
    if ($null -eq $Override) { return $result }
    foreach ($k in $Override.Keys) {
        if ($result.ContainsKey($k) -and ($result[$k] -is [hashtable]) -and ($Override[$k] -is [hashtable])) {
            $result[$k] = Merge-TxHashtables $result[$k] $Override[$k]
        } else {
            $result[$k] = $Override[$k]
        }
    }
    return $result
}

function Get-TxThemes {
    $root = Get-TxRootPath
    $themesFile = Join-Path $root "themes\themes.json"
    $data = Read-TxJsonFile $themesFile
    return (ConvertTo-TxHashtable $data.themes)
}

function Get-TxThemeOrder {
    $root = Get-TxRootPath
    $themesFile = Join-Path $root "themes\themes.json"
    $data = Read-TxJsonFile $themesFile
    if ($data.order) {
        return @($data.order | ForEach-Object { [string]$_ })
    }
    $themes = ConvertTo-TxHashtable $data.themes
    return @($themes.Keys | Sort-Object)
}

function Resolve-TxThemeId {
    param([string]$InputName)
    if ([string]::IsNullOrWhiteSpace($InputName)) { return $null }
    $needle = $InputName.ToLowerInvariant().Trim()
    $themes = Get-TxThemes
    $order = Get-TxThemeOrder

    if ($themes.ContainsKey($needle)) { return $needle }

    $idx = 0
    if ([int]::TryParse($needle, [ref]$idx) -and $idx -ge 1 -and $idx -le $order.Count) {
        return $order[$idx - 1]
    }

    $builtinAliases = @{
        "tokyo"     = "tokyo-night"
        "midnight"  = "tokyo-night"
        "mocha"     = "catppuccin"
        "cat"       = "catppuccin"
        "pastel"    = "catppuccin"
        "cyber"     = "cyberpunk"
        "synthwave" = "cyberpunk"
        "neon"      = "cyberpunk"
        "retro"     = "retro-crt"
        "crt"       = "retro-crt"
        "matrix"    = "retro-crt"
    }
    if ($builtinAliases.ContainsKey($needle)) { return $builtinAliases[$needle] }

    foreach ($id in $order) {
        $t = $themes[$id]
        if ($t -and $t.aliases) {
            foreach ($a in @($t.aliases)) {
                if ([string]$a -eq $needle) { return $id }
            }
        }
    }

    foreach ($id in $order) {
        if ($id.StartsWith($needle) -or $themes[$id].name.ToLowerInvariant().StartsWith($needle)) {
            return $id
        }
    }
    return $null
}

function Get-TxConfig {
    $root = Get-TxRootPath
    $defaultsFile = Join-Path $root "config\defaults.json"
    $userFile = Join-Path $root "config\user.json"

    $defaults = ConvertTo-TxHashtable (Read-TxJsonFile $defaultsFile)
    if (Test-Path $userFile) {
        try {
            $user = ConvertTo-TxHashtable (Read-TxJsonFile $userFile)
            return (Merge-TxHashtables $defaults $user)
        } catch {
            return $defaults
        }
    }
    return $defaults
}

function Save-TxConfig {
    param([Parameter(Mandatory = $true)][hashtable]$Config)
    $root = Get-TxRootPath
    $userFile = Join-Path $root "config\user.json"
    $json = $Config | ConvertTo-Json -Depth 10
    Write-TxUtf8NoBom -Path $userFile -Content $json
    Update-TxCmdThemeFile -Config $Config
}

function Get-TxActiveTheme {
    param([hashtable]$Config)
    if (-not $Config) { $Config = Get-TxConfig }
    $themes = Get-TxThemes
    $id = $Config.theme
    if ($id -and $themes.ContainsKey($id)) {
        return $themes[$id]
    }
    return $themes["tokyo-night"]
}

function Find-TxNerdFont {
    if ($script:TxSessionCache.ContainsKey("NerdFont")) {
        return $script:TxSessionCache["NerdFont"]
    }
    $found = $null
    $regPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
        "HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    )
    $preferredPatterns = @(
        "CaskaydiaCove Nerd Font Mono",
        "CaskaydiaCove Nerd Font",
        "JetBrainsMono Nerd Font Mono",
        "JetBrainsMono Nerd Font",
        "MesloLGS NF",
        "FiraCode Nerd Font",
        "Hack Nerd Font"
    )
    $allFontNames = New-Object System.Collections.Generic.List[string]
    foreach ($rp in $regPaths) {
        if (Test-Path $rp) {
            $props = Get-ItemProperty -Path $rp -ErrorAction SilentlyContinue
            if ($props) {
                foreach ($p in $props.PSObject.Properties) {
                    if ($p.Name -notmatch '^PS') {
                        [void]$allFontNames.Add($p.Name)
                    }
                }
            }
        }
    }
    foreach ($pat in $preferredPatterns) {
        foreach ($fn in $allFontNames) {
            if ($fn -like "*$pat*") {
                $found = $pat
                break
            }
        }
        if ($found) { break }
    }
    if (-not $found) {
        foreach ($fn in $allFontNames) {
            if ($fn -match 'Nerd Font|NFM|NFP|\bNF\b') {
                $found = ($fn -replace '\s*\(.*\)\s*$', '' -replace '\s+(Regular|Bold|Italic|Medium|Light).*$', '').Trim()
                break
            }
        }
    }
    $script:TxSessionCache["NerdFont"] = $found
    return $found
}

function Resolve-TxGlyphMode {
    param([hashtable]$Config)
    if (-not $Config) { $Config = Get-TxConfig }
    $mode = $Config.icons
    if ($mode -eq "nerd") { return "nerd" }
    if ($mode -eq "unicode") { return "unicode" }
    $nf = Find-TxNerdFont
    if ($nf) { return "nerd" }
    return "unicode"
}

function Resolve-TxFontFace {
    param([hashtable]$Config)
    if (-not $Config) { $Config = Get-TxConfig }
    if ($Config.wt.fontFace -and $Config.wt.fontFace -ne "auto") {
        return $Config.wt.fontFace
    }
    $nf = Find-TxNerdFont
    if ($nf) { return $nf }
    return "Cascadia Code"
}

function Find-TxClinkPath {
    $cmd = Get-Command clink -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\clink\clink.bat"),
        (Join-Path ${env:ProgramFiles(x86)} "clink\clink.bat"),
        (Join-Path $env:ProgramFiles "clink\clink.bat"),
        (Join-Path $env:LOCALAPPDATA "clink\clink.bat")
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
}

function Get-TxEnvironmentStatus {
    $psrl = Get-Module -ListAvailable PSReadLine | Sort-Object Version -Descending | Select-Object -First 1
    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    $wt = Get-Command wt -ErrorAction SilentlyContinue
    $wtSettings = Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"
    $nf = Find-TxNerdFont
    $clink = Find-TxClinkPath
    $eza = Get-Command eza -ErrorAction SilentlyContinue
    $zoxide = Get-Command zoxide -ErrorAction SilentlyContinue
    $fzf = Get-Command fzf -ErrorAction SilentlyContinue
    $git = Get-Command git -ErrorAction SilentlyContinue
    $python = Get-Command python -ErrorAction SilentlyContinue

    $psHooked = $false
    if (Test-Path $PROFILE.CurrentUserCurrentHost) {
        $pRaw = Get-Content $PROFILE.CurrentUserCurrentHost -Raw -ErrorAction SilentlyContinue
        if ($pRaw -match 'TricksXTech') { $psHooked = $true }
    }

    $cmdHooked = $false
    $cmdReg = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Command Processor" -ErrorAction SilentlyContinue
    if ($cmdReg -and $cmdReg.AutoRun -match 'TricksXTech|init\.cmd') {
        $cmdHooked = $true
    }

    $wtHooked = $false
    if (Test-Path $wtSettings) {
        $wtRaw = Get-Content $wtSettings -Raw -ErrorAction SilentlyContinue
        if ($wtRaw -match 'TricksXTech ') { $wtHooked = $true }
    }

    return [ordered]@{
        PSVersion       = $PSVersionTable.PSVersion.ToString()
        Pwsh7Installed  = [bool]$pwsh
        PSReadLineVer   = if ($psrl) { $psrl.Version.ToString() } else { "None" }
        PSReadLinePred  = ($psrl -and ($psrl.Version -ge [version]"2.1.0"))
        NerdFont        = if ($nf) { $nf } else { "Not detected (using Unicode mode)" }
        HasNerdFont     = [bool]$nf
        ClinkPath       = $clink
        HasClink        = [bool]$clink
        HasWT           = [bool]$wt -and (Test-Path $wtSettings)
        WTSettingsPath  = $wtSettings
        WTHooked        = $wtHooked
        PSHooked        = $psHooked
        CMDHooked       = $cmdHooked
        HasGit          = [bool]$git
        HasPython       = [bool]$python
        HasEza          = [bool]$eza
        HasZoxide       = [bool]$zoxide
        HasFzf          = [bool]$fzf
    }
}

function ConvertTo-TxCmdRgb {
    param(
        [string]$Hex,
        [ValidateSet("38", "48")][string]$Layer = "38"
    )
    $rgb = ConvertFrom-TxHex $Hex
    return "`$E[$Layer;2;$($rgb[0]);$($rgb[1]);$($rgb[2])m"
}

function Update-TxCmdThemeFile {
    param([hashtable]$Config)
    if (-not $Config) { $Config = Get-TxConfig }
    $root = Get-TxRootPath
    $theme = Get-TxActiveTheme $Config
    $ui = $theme.ui
    $glyphMode = Resolve-TxGlyphMode $Config
    $g = Get-TxGlyphs -Mode $glyphMode
    $style = if ($Config.style) { $Config.style } else { "capsule" }

    $fgPrim = ConvertTo-TxCmdRgb $ui.primary "38"
    $bgPrim = ConvertTo-TxCmdRgb $ui.primary "48"
    $fgSec  = ConvertTo-TxCmdRgb $ui.secondary "38"
    $bgSec  = ConvertTo-TxCmdRgb $ui.secondary "48"
    $fgAcc  = ConvertTo-TxCmdRgb $ui.accent "38"
    $fgMut  = ConvertTo-TxCmdRgb $ui.muted "38"
    $fgText = ConvertTo-TxCmdRgb $ui.text "38"
    $fgDark = ConvertTo-TxCmdRgb $ui.darkText "38"
    $bgSurf = ConvertTo-TxCmdRgb $ui.surface "48"
    $fgSurf = ConvertTo-TxCmdRgb $ui.surface "38"
    $fgErr  = ConvertTo-TxCmdRgb $ui.error "38"
    $bgErr  = ConvertTo-TxCmdRgb $ui.error "48"
    $rst    = "`$E[0m"
    $bold   = "`$E[1m"

    # Build themed PROMPT string using CMD prompt tokens ($E, $P, $T, $_)
    # Trim centiseconds from $T using 3 backspaces ($H$H$H)
    $timeToken = "`$T`$H`$H`$H"
    $titleSeq = "`$E]0;CMD - `$P`$E\"
    $chev = $g.Chevron
    $sub  = $g.SubArrow

    if ($style -eq "minimal") {
        $promptLine = "$titleSeq$fgSec$bold`$P$rst $fgPrim$chev$rst "
    } elseif ($style -eq "classic") {
        $promptLine = "$titleSeq$fgMut[$timeToken]$rst $fgPrim%USERNAME%@%COMPUTERNAME%$rst $fgAcc`$P$rst`$_$fgPrim$chev$rst "
    } elseif ($style -eq "powerline" -and $glyphMode -eq "nerd") {
        $plR = $g.PlRight
        $promptLine = "$titleSeq$bgPrim$fgDark$bold CMD $rst$fgPrim$bgSurf$plR$fgText `$P $rst$fgSurf$bgSec$plR$fgDark $timeToken $rst$fgSec$plR$rst`$_$fgPrim$bold$chev$rst "
    } else {
        $dot = $g.Dot
        $clock = $g.Clock
        $capL = if ($glyphMode -eq "nerd") { $g.CapLeft } else { "[" }
        $capR = if ($glyphMode -eq "nerd") { $g.CapRight } else { "]" }
        $seg1 = if ($glyphMode -eq "nerd") {
            "$fgPrim$capL$bgPrim$fgDark$bold CMD $rst$fgPrim$capR"
        } else {
            "$fgMut$capL$fgPrim$bold CMD $rst$fgMut$capR"
        }
        $seg2 = if ($glyphMode -eq "nerd") {
            "$fgSurf$capL$bgSurf$fgAcc$bold `$P $rst$fgSurf$capR"
        } else {
            "$fgMut$capL$fgAcc$bold `$P $rst$fgMut$capR"
        }
        $seg3 = if ($Config.segments.clock) {
            " $fgMut$clock $timeToken$rst"
        } else {
            ""
        }
        $promptLine = "$titleSeq$seg1 $seg2$seg3`$_$fgPrim$bold$sub$chev$rst "
    }

    $cmdContent = @"
@echo off
rem Auto-generated by TricksXTech - do not edit manually
set "TX_THEME_ID=$($theme.id)"
set "TX_THEME_NAME=$($theme.name)"
set "TX_STYLE=$style"
set "TX_GLYPHS=$glyphMode"
set "TX_PROMPT_BASE=$promptLine"
"@

    $outPath = Join-Path $root "config\cmd_theme.cmd"
    $crlfContent = ($cmdContent -replace "\r?\n", "`r`n").TrimEnd() + "`r`n"
    Write-TxUtf8NoBom -Path $outPath -Content $crlfContent
}
