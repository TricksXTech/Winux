# TricksXTech Windows Terminal - Safe Settings Manager

function Get-TxWTSettingsPath {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"),
        (Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe\LocalState\settings.json"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\Windows Terminal\settings.json")
    )
    $found = @()
    foreach ($p in $candidates) {
        if (Test-Path $p) { $found += $p }
    }
    return ,$found
}

function Set-TxObjectProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        $Value
    )
    if ($Object -is [System.Collections.IDictionary]) {
        $Object[$Name] = $Value
        return
    }
    $existing = $Object.PSObject.Properties[$Name]
    if ($existing) {
        $existing.Value = $Value
    } else {
        $Object | Add-Member -MemberType NoteProperty -Name $Name -Value $Value -Force
    }
}

function Remove-TxObjectProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) { $Object.Remove($Name) }
        return
    }
    if ($Object.PSObject.Properties[$Name]) {
        $Object.PSObject.Properties.Remove($Name)
    }
}

function Build-TxWTSchemeObject {
    param([hashtable]$Theme)
    $p = $Theme.palette
    return [ordered]@{
        name                = $Theme.wtSchemeName
        background          = $p.background
        foreground          = $p.foreground
        cursorColor         = $p.cursor
        selectionBackground = $p.selection
        black               = $p.black
        red                 = $p.red
        green               = $p.green
        yellow              = $p.yellow
        blue                = $p.blue
        purple              = $p.purple
        cyan                = $p.cyan
        white               = $p.white
        brightBlack         = $p.brightBlack
        brightRed           = $p.brightRed
        brightGreen         = $p.brightGreen
        brightYellow        = $p.brightYellow
        brightBlue          = $p.brightBlue
        brightPurple        = $p.brightPurple
        brightCyan          = $p.brightCyan
        brightWhite         = $p.brightWhite
    }
}

function Build-TxWTThemeObject {
    param([hashtable]$Theme)
    $c = $Theme.wtChrome
    return [ordered]@{
        name = $Theme.wtThemeName
        window = [ordered]@{
            applicationTheme = $c.applicationTheme
        }
        tabRow = [ordered]@{
            background          = $c.tabRowBg
            unfocusedBackground = $c.tabRowUnfocusedBg
        }
        tab = [ordered]@{
            background          = "terminalBackground"
            unfocusedBackground = $c.tabUnfocusedBg
            showCloseButton     = "hover"
        }
    }
}

function Sync-TxWTSettings {
    param(
        [hashtable]$Config,
        [switch]$OnlyIfHooked,
        [switch]$DryRun
    )
    if (-not $Config) { $Config = Get-TxConfig }
    $paths = Get-TxWTSettingsPath
    if (-not $paths -or $paths.Count -eq 0) { return @() }

    $themes = Get-TxThemes
    $active = Get-TxActiveTheme $Config
    $updated = @()

    foreach ($wtPath in $paths) {
        $raw = [System.IO.File]::ReadAllText($wtPath, [System.Text.Encoding]::UTF8)
        if ($OnlyIfHooked -and ($raw -notmatch 'TricksXTech ')) {
            continue
        }
        $json = $raw | ConvertFrom-Json

        # 1. Upsert all 4 color schemes
        $existingSchemes = @()
        if ($json.schemes) {
            foreach ($s in $json.schemes) {
                if ($s.name -notlike 'TricksXTech *') {
                    $existingSchemes += $s
                }
            }
        }
        $themeOrder = Get-TxThemeOrder
        $txSchemes = @()
        foreach ($key in $themeOrder) {
            if ($themes.ContainsKey($key)) {
                $txSchemes += (Build-TxWTSchemeObject $themes[$key])
            }
        }
        Set-TxObjectProperty -Object $json -Name "schemes" -Value @($existingSchemes + $txSchemes)

        # 2. Upsert all TricksXTech WT Chrome themes
        $existingThemes = @()
        if ($json.themes) {
            foreach ($t in $json.themes) {
                if ($t.name -notlike 'TricksXTech *') {
                    $existingThemes += $t
                }
            }
        }
        $txThemes = @()
        foreach ($key in $themeOrder) {
            if ($themes.ContainsKey($key)) {
                $txThemes += (Build-TxWTThemeObject $themes[$key])
            }
        }
        Set-TxObjectProperty -Object $json -Name "themes" -Value @($existingThemes + $txThemes)

        # 3. Set active chrome theme
        Set-TxObjectProperty -Object $json -Name "theme" -Value $active.wtThemeName

        # 4. Update profiles.defaults safely
        if (-not $json.profiles) {
            Set-TxObjectProperty -Object $json -Name "profiles" -Value ([ordered]@{ defaults = [ordered]@{}; list = @() })
        }
        if (-not $json.profiles.defaults) {
            Set-TxObjectProperty -Object $json.profiles -Name "defaults" -Value ([ordered]@{})
        }
        $defs = $json.profiles.defaults

        $fontFace = Resolve-TxFontFace $Config
        $fontSize = if ($Config.wt.fontSize) { [int]$Config.wt.fontSize } else { 11 }
        $opacity = if ($null -ne $Config.wt.opacity) { [int]$Config.wt.opacity } else { [int]$active.recommendedOpacity }
        $useAcrylic = if ($null -ne $Config.wt.useAcrylic) { [bool]$Config.wt.useAcrylic } else { [bool]$active.recommendedAcrylic }
        $cursorShape = if ($Config.wt.cursorShape) { [string]$Config.wt.cursorShape } else { "bar" }
        $padding = if ($Config.wt.padding) { [string]$Config.wt.padding } else { "10, 12, 10, 12" }

        $retroBool = $false
        if ($Config.wt.retroEffect -eq "auto") {
            $retroBool = [bool]$active.retroEffect
        } else {
            $retroBool = [bool]$Config.wt.retroEffect
        }

        Set-TxObjectProperty -Object $defs -Name "colorScheme" -Value $active.wtSchemeName
        Set-TxObjectProperty -Object $defs -Name "font" -Value ([ordered]@{ face = $fontFace; size = $fontSize })
        Set-TxObjectProperty -Object $defs -Name "cursorShape" -Value $cursorShape
        Set-TxObjectProperty -Object $defs -Name "opacity" -Value $opacity
        Set-TxObjectProperty -Object $defs -Name "useAcrylic" -Value $useAcrylic
        Set-TxObjectProperty -Object $defs -Name "padding" -Value $padding
        Set-TxObjectProperty -Object $defs -Name "experimental.retroTerminalEffect" -Value $retroBool

        if (-not $DryRun) {
            $outJson = $json | ConvertTo-Json -Depth 12
            Write-TxUtf8NoBom -Path $wtPath -Content $outJson
        }
        $updated += $wtPath
    }
    return $updated
}

function Remove-TxWTSettings {
    param([switch]$DryRun)
    $paths = Get-TxWTSettingsPath
    $cleaned = @()
    foreach ($wtPath in $paths) {
        $raw = [System.IO.File]::ReadAllText($wtPath, [System.Text.Encoding]::UTF8)
        $json = $raw | ConvertFrom-Json

        if ($json.schemes) {
            $kept = @($json.schemes | Where-Object { $_.name -notlike 'TricksXTech *' })
            Set-TxObjectProperty -Object $json -Name "schemes" -Value $kept
        }
        if ($json.themes) {
            $keptT = @($json.themes | Where-Object { $_.name -notlike 'TricksXTech *' })
            Set-TxObjectProperty -Object $json -Name "themes" -Value $keptT
        }
        if ($json.theme -like 'TricksXTech *') {
            Remove-TxObjectProperty -Object $json -Name "theme"
        }
        if ($json.profiles -and $json.profiles.defaults) {
            $defs = $json.profiles.defaults
            if ($defs.colorScheme -like 'TricksXTech *') {
                Remove-TxObjectProperty -Object $defs -Name "colorScheme"
            }
            foreach ($prop in @("font", "cursorShape", "opacity", "useAcrylic", "padding", "experimental.retroTerminalEffect")) {
                Remove-TxObjectProperty -Object $defs -Name $prop
            }
        }
        if (-not $DryRun) {
            $outJson = $json | ConvertTo-Json -Depth 12
            Write-TxUtf8NoBom -Path $wtPath -Content $outJson
        }
        $cleaned += $wtPath
    }
    return $cleaned
}
