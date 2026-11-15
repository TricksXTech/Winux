# TricksXTech PowerShell - Smart Prompt Engine

$script:TxLastHistId = -1
$script:TxLastCwd = ""
$script:TxCachedNodeVer = $null
$script:TxCachedPyVer = $null
$script:TxIsAdminCached = $null

function Test-TxIsAdmin {
    if ($null -ne $script:TxIsAdminCached) { return $script:TxIsAdminCached }
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $pr = New-Object Security.Principal.WindowsPrincipal($id)
        $script:TxIsAdminCached = $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        $script:TxIsAdminCached = $false
    }
    return $script:TxIsAdminCached
}

function Format-TxShortPath {
    param([string]$Path)
    if ([string]::IsNullOrEmpty($Path)) { return "~" }
    $homeDir = $HOME.TrimEnd('\', '/')
    $display = $Path
    if ($display.StartsWith($homeDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        $rest = $display.Substring($homeDir.Length)
        $display = "~" + $rest
    }
    $display = $display -replace '\\', '/'
    $parts = $display.Split('/', [System.StringSplitOptions]::RemoveEmptyEntries)
    if ($parts.Length -gt 4) {
        $ellipsis = [string][char]0x2026 # …
        return "$($parts[0])/$ellipsis/$($parts[-2])/$($parts[-1])"
    }
    return $display
}

function Format-TxDuration {
    param([double]$Ms)
    if ($Ms -lt 1000) {
        return "$([int][Math]::Round($Ms))ms"
    }
    $sec = $Ms / 1000.0
    if ($sec -lt 60) {
        return "{0:N2}s" -f $sec
    }
    $ts = [TimeSpan]::FromMilliseconds($Ms)
    if ($ts.TotalHours -ge 1) {
        return "{0}h {1}m" -f [int]$ts.TotalHours, $ts.Minutes
    }
    return "{0}m {1}s" -f $ts.Minutes, $ts.Seconds
}

function Get-TxEnvTags {
    param(
        [string]$Cwd,
        [hashtable]$Glyphs
    )
    $tags = New-Object System.Collections.Generic.List[hashtable]

    # Python virtualenv / conda / local .venv
    $pyEnv = $null
    if ($env:VIRTUAL_ENV) {
        $pyEnv = Split-Path -Leaf $env:VIRTUAL_ENV
    } elseif ($env:CONDA_DEFAULT_ENV) {
        $pyEnv = $env:CONDA_DEFAULT_ENV
    } elseif ([System.IO.Directory]::Exists((Join-Path $Cwd ".venv"))) {
        $pyEnv = ".venv"
    }
    if ($pyEnv) {
        [void]$tags.Add(@{ Icon = $Glyphs.Python; Text = $pyEnv; Kind = "python" })
    }

    # Node project
    if ([System.IO.File]::Exists((Join-Path $Cwd "package.json"))) {
        if ($null -eq $script:TxCachedNodeVer) {
            $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
            if ($nodeCmd) {
                $nv = (& node -v 2>$null)
                $script:TxCachedNodeVer = if ($nv) { $nv.Trim() } else { "node" }
            } else {
                $script:TxCachedNodeVer = ""
            }
        }
        if ($script:TxCachedNodeVer) {
            [void]$tags.Add(@{ Icon = $Glyphs.Node; Text = $script:TxCachedNodeVer; Kind = "node" })
        }
    }

    # Rust / Go / Docker markers
    if ([System.IO.File]::Exists((Join-Path $Cwd "Cargo.toml"))) {
        [void]$tags.Add(@{ Icon = $Glyphs.Rust; Text = "rust"; Kind = "rust" })
    }
    if ([System.IO.File]::Exists((Join-Path $Cwd "go.mod"))) {
        [void]$tags.Add(@{ Icon = $Glyphs.Go; Text = "go"; Kind = "go" })
    }

    return $tags
}

function Build-TxPromptSegments {
    param(
        [hashtable]$Config,
        [hashtable]$Theme,
        [hashtable]$Glyphs,
        [bool]$LastOk,
        [int]$LastCode,
        [double]$DurationMs,
        [bool]$HasNewCmd
    )

    $ui = $Theme.ui
    $segs = $Config.segments
    $cwdLoc = Get-Location
    $cwd = $cwdLoc.ProviderPath
    $shortPath = Format-TxShortPath $cwdLoc.Path
    $isAdmin = Test-TxIsAdmin
    $git = if ($segs.git) { Get-TxGitStatus -Path $cwd } else { $null }
    $envs = if ($segs.env) { Get-TxEnvTags -Cwd $cwd -Glyphs $Glyphs } else { @() }

    $list = New-Object System.Collections.Generic.List[hashtable]

    # Shell / OS badge
    $psBadge = if ($PSVersionTable.PSVersion.Major -ge 7) { "PS7" } else { "PS" }
    if ($segs.admin -and $isAdmin) {
        [void]$list.Add(@{
            Text = "$($Glyphs.Admin) ADMIN"
            Fg   = $ui.darkText
            Bg   = $ui.warning
            Accent = $ui.warning
            Bold = $true
        })
    } else {
        $psLabel = if ($Glyphs.Shell) { "$($Glyphs.Shell) $psBadge" } else { $psBadge }
        [void]$list.Add(@{
            Text = $psLabel
            Fg   = $ui.darkText
            Bg   = $ui.primary
            Accent = $ui.primary
            Bold = $true
        })
    }

    if ($segs.userHost) {
        [void]$list.Add(@{
            Text = "$($Glyphs.User) $($env:USERNAME)@$($env:COMPUTERNAME)"
            Fg   = $ui.text
            Bg   = $ui.surfaceAlt
            Accent = $ui.secondary
            Bold = $false
        })
    }

    if ($segs.path) {
        [void]$list.Add(@{
            Text = "$($Glyphs.Folder) $shortPath"
            Fg   = $ui.accent
            Bg   = $ui.surface
            Accent = $ui.accent
            Bold = $true
        })
    }

    if ($git) {
        $gitParts = New-Object System.Collections.Generic.List[string]
        [void]$gitParts.Add("$($Glyphs.GitBranch) $($git.Branch)")
        if ($git.Ahead -gt 0) { [void]$gitParts.Add("$($Glyphs.Up)$($git.Ahead)") }
        if ($git.Behind -gt 0) { [void]$gitParts.Add("$($Glyphs.Down)$($git.Behind)") }
        if ($git.IsDirty) {
            $d = @()
            if ($git.Staged -gt 0) { $d += "+$($git.Staged)" }
            if ($git.Modified -gt 0) { $d += "~$($git.Modified)" }
            if ($git.Untracked -gt 0) { $d += "?$($git.Untracked)" }
            if ($git.Conflicts -gt 0) { $d += "!$($git.Conflicts)" }
            [void]$gitParts.Add(($d -join " "))
        } else {
            [void]$gitParts.Add($Glyphs.GitClean)
        }
        $gitColor = if ($git.Conflicts -gt 0) { $ui.error } elseif ($git.IsDirty) { $ui.warning } else { $ui.success }
        [void]$list.Add(@{
            Text = ($gitParts -join " ")
            Fg   = $ui.darkText
            Bg   = $gitColor
            Accent = $gitColor
            Bold = $true
        })
    }

    foreach ($e in $envs) {
        $eColor = switch ($e.Kind) {
            "python" { $ui.warning }
            "node"   { $ui.success }
            "rust"   { $ui.error }
            "go"     { $ui.accent }
            default  { $ui.secondary }
        }
        [void]$list.Add(@{
            Text = "$($e.Icon) $($e.Text)"
            Fg   = $eColor
            Bg   = $ui.surfaceAlt
            Accent = $eColor
            Bold = $false
        })
    }

    if ($segs.duration -and $HasNewCmd -and $DurationMs -ge 150) {
        $durStr = Format-TxDuration $DurationMs
        [void]$list.Add(@{
            Text = "$($Glyphs.Timer) $durStr"
            Fg   = $ui.warning
            Bg   = $ui.surfaceAlt
            Accent = $ui.warning
            Bold = $false
        })
    }

    if ($segs.exitCode -and $HasNewCmd -and (-not $LastOk)) {
        $errLabel = if ($LastCode -ne 0) { "$($Glyphs.Cross) $LastCode" } else { "$($Glyphs.Cross) ERR" }
        [void]$list.Add(@{
            Text = $errLabel
            Fg   = $ui.darkText
            Bg   = $ui.error
            Accent = $ui.error
            Bold = $true
        })
    }

    return @{
        Segments  = $list
        Git       = $git
        ShortPath = $shortPath
        Cwd       = $cwd
    }
}

function Invoke-TxRenderPrompt {
    param(
        [hashtable]$Config,
        [hashtable]$Theme,
        [hashtable]$Glyphs,
        [bool]$LastOk,
        [int]$LastCode,
        [double]$DurationMs,
        [bool]$HasNewCmd
    )

    $ui = $Theme.ui
    $style = if ($Config.style) { $Config.style } else { "capsule" }
    $built = Build-TxPromptSegments -Config $Config -Theme $Theme -Glyphs $Glyphs `
        -LastOk $LastOk -LastCode $LastCode -DurationMs $DurationMs -HasNewCmd $HasNewCmd

    $segs = $built.Segments
    $git = $built.Git
    $cwd = $built.Cwd
    $shortPath = $built.ShortPath
    $esc = $script:TxEsc
    $rst = "$esc[0m"
    $chevColor = if ($HasNewCmd -and (-not $LastOk)) { $ui.error } else { $ui.primary }

    # Update tab title and emit OSC 9;9 CWD for Windows Terminal split/duplicate tab
    $leaf = Split-Path -Leaf $cwd
    if (-not $leaf) { $leaf = $cwd }
    $tabTitle = if ($git) { "PS $([char]0x2022) $leaf ($($git.Branch))" } else { "PS $([char]0x2022) $leaf" }
    try { $Host.UI.RawUI.WindowTitle = $tabTitle } catch { }
    $oscCwd = "$esc]9;9;`"$cwd`"$esc\"

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append($oscCwd)

    if ($style -eq "minimal") {
        [void]$sb.Append((Format-TxText $shortPath -Fg $ui.accent -Bold))
        if ($git) {
            $gClr = if ($git.IsDirty) { $ui.warning } else { $ui.success }
            $mark = if ($git.IsDirty) { "*" } else { "" }
            [void]$sb.Append(" ")
            [void]$sb.Append((Format-TxText "($($git.Branch)$mark)" -Fg $gClr))
        }
        if ($HasNewCmd -and $Config.segments.duration -and $DurationMs -ge 250) {
            [void]$sb.Append(" ")
            [void]$sb.Append((Format-TxText (Format-TxDuration $DurationMs) -Fg $ui.muted))
        }
        if ($HasNewCmd -and $Config.segments.exitCode -and (-not $LastOk)) {
            $ec = if ($LastCode -ne 0) { $LastCode } else { "!" }
            [void]$sb.Append(" ")
            [void]$sb.Append((Format-TxText "[$ec]" -Fg $ui.error -Bold))
        }
        [void]$sb.Append(" ")
        [void]$sb.Append((Format-TxText $Glyphs.Chevron -Fg $chevColor -Bold))
        [void]$sb.Append(" ")
        return $sb.ToString()
    }

    if ($style -eq "classic") {
        if ($Config.segments.clock) {
            [void]$sb.Append((Format-TxText "[$(Get-Date -Format 'HH:mm:ss')] " -Fg $ui.muted))
        }
        [void]$sb.Append((Format-TxText "$($env:USERNAME)@$($env:COMPUTERNAME) " -Fg $ui.primary -Bold))
        [void]$sb.Append((Format-TxText $shortPath -Fg $ui.accent -Bold))
        if ($git) {
            $gClr = if ($git.IsDirty) { $ui.warning } else { $ui.success }
            $dirtyTag = if ($git.IsDirty) { " *" } else { "" }
            [void]$sb.Append((Format-TxText " [$($git.Branch)$dirtyTag]" -Fg $gClr))
        }
        if ($HasNewCmd -and $Config.segments.duration -and $DurationMs -ge 150) {
            [void]$sb.Append((Format-TxText " ($(Format-TxDuration $DurationMs))" -Fg $ui.muted))
        }
        if ($HasNewCmd -and $Config.segments.exitCode -and (-not $LastOk)) {
            $ec = if ($LastCode -ne 0) { $LastCode } else { "ERR" }
            [void]$sb.Append((Format-TxText " [exit:$ec]" -Fg $ui.error -Bold))
        }
        [void]$sb.Append("`n")
        [void]$sb.Append((Format-TxText "$($Glyphs.SubArrow)$($Glyphs.Chevron) " -Fg $chevColor -Bold))
        return $sb.ToString()
    }

    if ($style -eq "powerline") {
        for ($i = 0; $i -lt $segs.Count; $i++) {
            $s = $segs[$i]
            $fg = Get-TxFg $s.Fg
            $bg = Get-TxBg $s.Bg
            $b = if ($s.Bold) { "$esc[1m" } else { "" }
            if ($i -eq 0 -and $Glyphs.Mode -eq "nerd") {
                [void]$sb.Append((Get-TxFg $s.Bg))
                [void]$sb.Append($Glyphs.CapLeft)
            }
            [void]$sb.Append("$bg$fg$b $($s.Text) $rst")
            if ($i -lt ($segs.Count - 1)) {
                $nextBg = $segs[$i + 1].Bg
                [void]$sb.Append((Get-TxFg $s.Bg))
                [void]$sb.Append((Get-TxBg $nextBg))
                [void]$sb.Append("$($Glyphs.PlRight)$rst")
            } else {
                [void]$sb.Append((Get-TxFg $s.Bg))
                [void]$sb.Append("$($Glyphs.PlRight)$rst")
            }
        }
        if ($Config.segments.clock) {
            [void]$sb.Append(" ")
            [void]$sb.Append((Format-TxText "$($Glyphs.Clock) $(Get-Date -Format 'HH:mm:ss')" -Fg $ui.muted))
        }
        [void]$sb.Append("`n")
        [void]$sb.Append((Format-TxText "$($Glyphs.SubArrow)$($Glyphs.Chevron) " -Fg $chevColor -Bold))
        return $sb.ToString()
    }

    # Default: capsule style (works cleanly in both Unicode & Nerd Font modes)
    for ($i = 0; $i -lt $segs.Count; $i++) {
        $s = $segs[$i]
        if ($i -gt 0) { [void]$sb.Append(" ") }
        if ($Glyphs.Mode -eq "nerd") {
            [void]$sb.Append((Get-TxFg $s.Bg))
            [void]$sb.Append($Glyphs.CapLeft)
            [void]$sb.Append((Format-TxText " $($s.Text) " -Fg $s.Fg -Bg $s.Bg -Bold:$s.Bold))
            [void]$sb.Append((Get-TxFg $s.Bg))
            [void]$sb.Append($Glyphs.CapRight)
            [void]$sb.Append($rst)
        } else {
            [void]$sb.Append((Format-TxText "[" -Fg $ui.border))
            [void]$sb.Append((Format-TxText $s.Text -Fg $s.Accent -Bold:$s.Bold))
            [void]$sb.Append((Format-TxText "]" -Fg $ui.border))
        }
    }
    if ($Config.segments.clock) {
        [void]$sb.Append(" ")
        [void]$sb.Append((Format-TxText "$($Glyphs.Clock) $(Get-Date -Format 'HH:mm:ss')" -Fg $ui.muted))
    }
    [void]$sb.Append("`n")
    [void]$sb.Append((Format-TxText "$($Glyphs.SubArrow)$($Glyphs.Chevron) " -Fg $chevColor -Bold))
    return $sb.ToString()
}

function Install-TxPrompt {
    function global:prompt {
        $origOk = $?
        $origExit = if ($null -ne $global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }

        $hasNewCmd = $false
        $durMs = 0.0
        try {
            $hist = Get-History -Count 1 -ErrorAction SilentlyContinue
            if ($hist -and ($hist.Id -ne $script:TxLastHistId)) {
                $script:TxLastHistId = $hist.Id
                $hasNewCmd = $true
                if ($hist.EndExecutionTime -and $hist.StartExecutionTime) {
                    $durMs = ($hist.EndExecutionTime - $hist.StartExecutionTime).TotalMilliseconds
                }
            }
        } catch { }

        # Record directory visit for smart jump (`z`)
        try {
            $curPath = (Get-Location).ProviderPath
            if ($curPath -and ($curPath -ne $script:TxLastCwd)) {
                $script:TxLastCwd = $curPath
                if (Get-Command Register-TxJumpVisit -ErrorAction SilentlyContinue) {
                    Register-TxJumpVisit -Path $curPath
                }
            }
        } catch { }

        $cfg = if ($script:TxRuntimeConfig) { $script:TxRuntimeConfig } else { Get-TxConfig }
        $thm = if ($script:TxRuntimeTheme) { $script:TxRuntimeTheme } else { Get-TxActiveTheme $cfg }
        $g   = if ($script:TxRuntimeGlyphs) { $script:TxRuntimeGlyphs } else { Get-TxGlyphs -Mode (Resolve-TxGlyphMode $cfg) }

        $out = Invoke-TxRenderPrompt -Config $cfg -Theme $thm -Glyphs $g `
            -LastOk $origOk -LastCode $origExit -DurationMs $durMs -HasNewCmd $hasNewCmd

        $global:LASTEXITCODE = $origExit
        return $out
    }
}
