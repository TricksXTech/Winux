# TricksXTech Safe Installer (with Automatic Backup, -DryRun, and -Scope)

param(
    [ValidateSet("All", "WT", "PowerShell", "CMD")]
    [string]$Scope = "All",
    [string]$Theme = "",
    [switch]$DryRun,
    [switch]$NoBackup
)

$script:TxRoot = $PSScriptRoot
. (Join-Path $script:TxRoot "src\core\ansi.ps1")
. (Join-Path $script:TxRoot "src\core\config.ps1")
. (Join-Path $script:TxRoot "src\wt\wt_manager.ps1")

Initialize-TxEncoding

$cfg = Get-TxConfig
if ($Theme) {
    $resolvedTheme = Resolve-TxThemeId $Theme
    if (-not $resolvedTheme) {
        $validList = (Get-TxThemeOrder) -join ", "
        Write-Error "Unknown theme '$Theme'. Valid: $validList"
        exit 1
    }
    $cfg.theme = $resolvedTheme
    if (-not $DryRun) { Save-TxConfig -Config $cfg }
} else {
    if (-not $DryRun) { Update-TxCmdThemeFile -Config $cfg }
}

$activeTheme = Get-TxActiveTheme $cfg
$ui = $activeTheme.ui

Write-Host ""
Write-Host (Format-TxGradient "  $($cfg.brand) Terminal Installer" -Stops @($ui.gradientStart, $ui.gradientMid, $ui.gradientEnd) -Bold)
Write-Host (Format-TxText "  Root: $($script:TxRoot)  |  Theme: $($activeTheme.name)  |  Scope: $Scope$(if ($DryRun) { '  [DRY RUN]' })" -Fg $ui.muted)
Write-Host (Format-TxText ("  " + ([string][char]0x2500 * 66)) -Fg $ui.border)

# Prepare Backup Directory
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $script:TxRoot "backups\$stamp"
$manifest = [ordered]@{
    timestamp = $stamp
    root      = $script:TxRoot
    wtFiles   = @()
    profiles  = @()
    registry  = [ordered]@{}
}

if (-not $DryRun -and -not $NoBackup) {
    [void](New-Item -ItemType Directory -Path $backupDir -Force)
}

function Add-OrUpdateFencedBlock {
    param([string]$Existing, [string]$Block)
    $pattern = '(?s)# >>> TricksXTech >>>.*?# <<< TricksXTech <<<\r?\n?'
    $cleaned = [regex]::Replace($Existing, $pattern, "").TrimEnd()
    if ([string]::IsNullOrWhiteSpace($cleaned)) {
        return ($Block.TrimEnd() + "`r`n")
    }
    return ($cleaned + "`r`n`r`n" + $Block.TrimEnd() + "`r`n")
}

# 1. Windows Terminal
if ($Scope -in @("All", "WT")) {
    $wtPaths = @(Get-TxWTSettingsPath)
    if ($wtPaths.Count -eq 0) {
        Write-Host "  $(Format-TxText '[SKIP]' -Fg $ui.warning) Windows Terminal settings.json not found."
    } else {
        foreach ($wtPath in $wtPaths) {
            if (-not $DryRun -and -not $NoBackup) {
                $idx = $manifest.wtFiles.Count
                $bFile = Join-Path $backupDir "wt_settings_$idx.json"
                Copy-Item -LiteralPath $wtPath -Destination $bFile -Force
                $manifest.wtFiles += [ordered]@{ original = $wtPath; backup = $bFile }
            }
        }
        $synced = Sync-TxWTSettings -Config $cfg -DryRun:$DryRun
        foreach ($p in $synced) {
            Write-Host "  $(Format-TxText '[WT]' -Fg $ui.success -Bold) $(if ($DryRun) { 'Would update' } else { 'Updated' }) $p"
        }
    }
}

# 2. PowerShell Profile(s)
if ($Scope -in @("All", "PowerShell")) {
    $docsRoot = Split-Path -Parent (Split-Path -Parent $PROFILE.CurrentUserCurrentHost)
    $profileTargets = @($PROFILE.CurrentUserCurrentHost)
    $ps7ProfileDir = Join-Path $docsRoot "PowerShell"
    if ((Get-Command pwsh -ErrorAction SilentlyContinue) -or (Test-Path $ps7ProfileDir)) {
        $profileTargets += (Join-Path $ps7ProfileDir "Microsoft.PowerShell_profile.ps1")
    }

    $initPsPath = Join-Path $script:TxRoot "src\powershell\init.ps1"
    $block = @"
# >>> TricksXTech >>>
if (Test-Path '$initPsPath') {
    . '$initPsPath'
}
# <<< TricksXTech <<<
"@

    $pIdx = 0
    foreach ($prof in ($profileTargets | Select-Object -Unique)) {
        $existed = Test-Path $prof
        $existingText = if ($existed) { [System.IO.File]::ReadAllText($prof, [System.Text.Encoding]::UTF8) } else { "" }
        if (-not $DryRun -and -not $NoBackup) {
            $bName = "ps_profile_$pIdx.ps1"
            $bPath = Join-Path $backupDir $bName
            if ($existed) { Copy-Item -LiteralPath $prof -Destination $bPath -Force }
            $manifest.profiles += [ordered]@{ original = $prof; existed = $existed; backup = if ($existed) { $bPath } else { $null } }
        }
        if (-not $DryRun) {
            $newText = Add-OrUpdateFencedBlock -Existing $existingText -Block $block
            Write-TxUtf8NoBom -Path $prof -Content $newText
        }
        Write-Host "  $(Format-TxText '[PS]' -Fg $ui.success -Bold) $(if ($DryRun) { 'Would hook' } else { 'Hooked' }) $prof"
        $pIdx++
    }
}

# 3. Command Prompt (CMD) AutoRun + Console VT/History + Clink Script
if ($Scope -in @("All", "CMD")) {
    $cmdProcPath = "HKCU:\Software\Microsoft\Command Processor"
    $consolePath = "HKCU:\Console"

    $oldProc = Get-ItemProperty -Path $cmdProcPath -ErrorAction SilentlyContinue
    $oldAutoRun = if ($oldProc -and $oldProc.PSObject.Properties["AutoRun"]) { [string]$oldProc.AutoRun } else { $null }
    $oldCompChar = if ($oldProc -and $oldProc.PSObject.Properties["CompletionChar"]) { $oldProc.CompletionChar } else { $null }
    $oldPathComp = if ($oldProc -and $oldProc.PSObject.Properties["PathCompletionChar"]) { $oldProc.PathCompletionChar } else { $null }

    $oldCon = Get-ItemProperty -Path $consolePath -ErrorAction SilentlyContinue
    $conSnap = [ordered]@{}
    foreach ($k in @("VirtualTerminalLevel", "HistoryBufferSize", "NumberOfHistoryBuffers", "HistoryNoDup", "QuickEdit")) {
        $conSnap[$k] = if ($oldCon -and $oldCon.PSObject.Properties[$k]) { $oldCon.$k } else { $null }
    }

    $manifest.registry = [ordered]@{
        AutoRun            = $oldAutoRun
        CompletionChar     = $oldCompChar
        PathCompletionChar = $oldPathComp
        Console            = $conSnap
    }

    $initCmd = Join-Path $script:TxRoot "src\cmd\init.cmd"
    $callStmt = "call `"$initCmd`""

    # Strip any prior TricksXTech hook first, then chain cleanly if user had another AutoRun
    $cleanedAuto = if ($oldAutoRun) {
        ($oldAutoRun -replace '(?i)\s*&\s*call\s+"?[^"]*init\.cmd"?', '' -replace '(?i)call\s+"?[^"]*init\.cmd"?\s*&\s*', '' -replace '(?i)call\s+"?[^"]*init\.cmd"?', '').Trim()
    } else { "" }

    $newAutoRun = if ([string]::IsNullOrWhiteSpace($cleanedAuto)) {
        $callStmt
    } else {
        "$cleanedAuto & $callStmt"
    }

    if (-not $DryRun) {
        if (-not (Test-Path $cmdProcPath)) { [void](New-Item -Path $cmdProcPath -Force) }
        Set-ItemProperty -Path $cmdProcPath -Name "AutoRun" -Value $newAutoRun -Type String
        Set-ItemProperty -Path $cmdProcPath -Name "CompletionChar" -Value 9 -Type DWord
        Set-ItemProperty -Path $cmdProcPath -Name "PathCompletionChar" -Value 9 -Type DWord

        if (-not (Test-Path $consolePath)) { [void](New-Item -Path $consolePath -Force) }
        Set-ItemProperty -Path $consolePath -Name "VirtualTerminalLevel" -Value 1 -Type DWord
        Set-ItemProperty -Path $consolePath -Name "HistoryBufferSize" -Value 999 -Type DWord
        Set-ItemProperty -Path $consolePath -Name "NumberOfHistoryBuffers" -Value 16 -Type DWord
        Set-ItemProperty -Path $consolePath -Name "HistoryNoDup" -Value 1 -Type DWord
        Set-ItemProperty -Path $consolePath -Name "QuickEdit" -Value 1 -Type DWord
    }
    Write-Host "  $(Format-TxText '[CMD]' -Fg $ui.success -Bold) $(if ($DryRun) { 'Would configure' } else { 'Configured' }) CMD AutoRun, Tab completion, VT100 & 999-line history"

    # Clink integration if Clink is present
    $clink = Find-TxClinkPath
    if ($clink) {
        $clinkUserDir = Join-Path $env:LOCALAPPDATA "clink"
        $luaSrc = Join-Path $script:TxRoot "src\cmd\tx.lua"
        $luaDst = Join-Path $clinkUserDir "tx.lua"
        if (-not $DryRun) {
            if (-not (Test-Path $clinkUserDir)) { [void](New-Item -ItemType Directory -Path $clinkUserDir -Force) }
            Copy-Item -LiteralPath $luaSrc -Destination $luaDst -Force
        }
        Write-Host "  $(Format-TxText '[CLINK]' -Fg $ui.success -Bold) $(if ($DryRun) { 'Would install' } else { 'Installed' }) Clink Lua script -> $luaDst"
    }
}

if (-not $DryRun -and -not $NoBackup) {
    Write-TxUtf8NoBom -Path (Join-Path $backupDir "manifest.json") -Content ($manifest | ConvertTo-Json -Depth 10)
    Write-Host "  $(Format-TxText '[BACKUP]' -Fg $ui.accent -Bold) Saved rollback snapshot to $backupDir"
}

Write-Host ""
if ($DryRun) {
    Write-Host (Format-TxText "  Dry run finished. No changes were written." -Fg $ui.warning -Bold)
} else {
    Write-Host (Format-TxText "  TricksXTech installed! Open a new Windows Terminal tab (PowerShell or CMD) to enjoy." -Fg $ui.success -Bold)
    Write-Host (Format-TxText "  Run 'tx' anytime to customize themes, opacity, styles, or optional upgrades." -Fg $ui.muted)
}
Write-Host ""
