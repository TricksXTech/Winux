# TricksXTech Clean Uninstaller & Backup Restorer

param(
    [switch]$RestoreBackup,
    [switch]$DryRun
)

$script:TxRoot = $PSScriptRoot
. (Join-Path $script:TxRoot "src\core\ansi.ps1")
. (Join-Path $script:TxRoot "src\core\config.ps1")
. (Join-Path $script:TxRoot "src\wt\wt_manager.ps1")

Initialize-TxEncoding
$cfg = Get-TxConfig
$ui = (Get-TxActiveTheme $cfg).ui

Write-Host ""
Write-Host (Format-TxGradient "  $($cfg.brand) Terminal Uninstaller" -Stops @($ui.gradientStart, $ui.gradientMid, $ui.gradientEnd) -Bold)
Write-Host (Format-TxText ("  " + ([string][char]0x2500 * 60)) -Fg $ui.border)

$backupsRoot = Join-Path $script:TxRoot "backups"
$latestBackup = $null
if (Test-Path $backupsRoot) {
    $latestBackup = Get-ChildItem -Path $backupsRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
}

if ($RestoreBackup -and $latestBackup) {
    $manifestPath = Join-Path $latestBackup.FullName "manifest.json"
    if (Test-Path $manifestPath) {
        $manifest = Read-TxJsonFile $manifestPath
        Write-Host "  $(Format-TxText '[RESTORE]' -Fg $ui.accent -Bold) Using snapshot $($latestBackup.Name)"

        foreach ($wt in $manifest.wtFiles) {
            if (Test-Path $wt.backup) {
                if (-not $DryRun) { Copy-Item -LiteralPath $wt.backup -Destination $wt.original -Force }
                Write-Host "  $(Format-TxText '[WT]' -Fg $ui.success) Restored $($wt.original)"
            }
        }
        foreach ($pr in $manifest.profiles) {
            if ($pr.existed -and $pr.backup -and (Test-Path $pr.backup)) {
                if (-not $DryRun) { Copy-Item -LiteralPath $pr.backup -Destination $pr.original -Force }
                Write-Host "  $(Format-TxText '[PS]' -Fg $ui.success) Restored $($pr.original)"
            } elseif (-not $pr.existed -and (Test-Path $pr.original)) {
                if (-not $DryRun) { Remove-Item -LiteralPath $pr.original -Force }
                Write-Host "  $(Format-TxText '[PS]' -Fg $ui.success) Removed newly created $($pr.original)"
            }
        }
        $cmdProc = "HKCU:\Software\Microsoft\Command Processor"
        if ($manifest.registry) {
            if (-not $DryRun) {
                if ($null -eq $manifest.registry.AutoRun) {
                    Remove-ItemProperty -Path $cmdProc -Name "AutoRun" -ErrorAction SilentlyContinue
                } else {
                    Set-ItemProperty -Path $cmdProc -Name "AutoRun" -Value $manifest.registry.AutoRun
                }
            }
            Write-Host "  $(Format-TxText '[CMD]' -Fg $ui.success) Restored CMD AutoRun registry setting"
        }
        $clinkLua = Join-Path $env:LOCALAPPDATA "clink\tx.lua"
        if (Test-Path $clinkLua) {
            if (-not $DryRun) { Remove-Item -LiteralPath $clinkLua -Force }
            Write-Host "  $(Format-TxText '[CLINK]' -Fg $ui.success) Removed $clinkLua"
        }
        Write-Host ""
        Write-Host (Format-TxText "  Backup restored cleanly." -Fg $ui.success -Bold)
        Write-Host ""
        return
    }
}

# Clean strip mode
$cleanedWT = Remove-TxWTSettings -DryRun:$DryRun
foreach ($p in $cleanedWT) {
    Write-Host "  $(Format-TxText '[WT]' -Fg $ui.success) $(if ($DryRun) { 'Would clean' } else { 'Cleaned' }) TricksXTech schemes/themes from $p"
}

$docsRoot = Split-Path -Parent (Split-Path -Parent $PROFILE.CurrentUserCurrentHost)
$profiles = @(
    $PROFILE.CurrentUserCurrentHost,
    (Join-Path $docsRoot "PowerShell\Microsoft.PowerShell_profile.ps1")
) | Select-Object -Unique

foreach ($prof in $profiles) {
    if (Test-Path $prof) {
        $raw = [System.IO.File]::ReadAllText($prof, [System.Text.Encoding]::UTF8)
        if ($raw -match '# >>> TricksXTech >>>') {
            $stripped = ([regex]::Replace($raw, '(?s)# >>> TricksXTech >>>.*?# <<< TricksXTech <<<\r?\n?', '')).Trim()
            if (-not $DryRun) {
                if ([string]::IsNullOrWhiteSpace($stripped)) {
                    Remove-Item -LiteralPath $prof -Force
                } else {
                    Write-TxUtf8NoBom -Path $prof -Content ($stripped + "`r`n")
                }
            }
            Write-Host "  $(Format-TxText '[PS]' -Fg $ui.success) $(if ($DryRun) { 'Would remove' } else { 'Removed' }) TricksXTech hook from $prof"
        }
    }
}

$cmdProc = "HKCU:\Software\Microsoft\Command Processor"
$procProps = Get-ItemProperty -Path $cmdProc -ErrorAction SilentlyContinue
if ($procProps -and $procProps.AutoRun) {
    $ar = [string]$procProps.AutoRun
    if ($ar -match 'TricksXTech|init\.cmd') {
        $cleaned = ($ar -replace '(?i)\s*&\s*call\s+"?[^"]*init\.cmd"?', '' -replace '(?i)call\s+"?[^"]*init\.cmd"?\s*&\s*', '' -replace '(?i)call\s+"?[^"]*init\.cmd"?', '').Trim()
        if (-not $DryRun) {
            if ([string]::IsNullOrWhiteSpace($cleaned)) {
                Remove-ItemProperty -Path $cmdProc -Name "AutoRun" -ErrorAction SilentlyContinue
            } else {
                Set-ItemProperty -Path $cmdProc -Name "AutoRun" -Value $cleaned
            }
        }
        Write-Host "  $(Format-TxText '[CMD]' -Fg $ui.success) $(if ($DryRun) { 'Would remove' } else { 'Removed' }) TricksXTech from CMD AutoRun"
    }
}

$clinkLua = Join-Path $env:LOCALAPPDATA "clink\tx.lua"
if (Test-Path $clinkLua) {
    if (-not $DryRun) { Remove-Item -LiteralPath $clinkLua -Force }
    Write-Host "  $(Format-TxText '[CLINK]' -Fg $ui.success) $(if ($DryRun) { 'Would remove' } else { 'Removed' }) $clinkLua"
}

Write-Host ""
Write-Host (Format-TxText "  TricksXTech uninstalled cleanly. Files inside $($script:TxRoot) were preserved." -Fg $ui.success -Bold)
Write-Host ""
