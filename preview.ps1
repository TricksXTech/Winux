# TricksXTech Sandbox Previewer (Zero system changes)

param(
    [ValidateSet("showcase", "ps", "cmd", "split")]
    [string]$Mode = "showcase",
    [string]$Theme = ""
)

$script:TxRoot = $PSScriptRoot
. (Join-Path $script:TxRoot "src\core\ansi.ps1")
. (Join-Path $script:TxRoot "src\core\config.ps1")
. (Join-Path $script:TxRoot "src\core\sysinfo.ps1")
. (Join-Path $script:TxRoot "src\core\hud.ps1")
. (Join-Path $script:TxRoot "src\powershell\jump.ps1")
. (Join-Path $script:TxRoot "src\powershell\ls_colors.ps1")
. (Join-Path $script:TxRoot "src\powershell\prompt.ps1")
. (Join-Path $script:TxRoot "src\powershell\productivity.ps1")

Initialize-TxEncoding

if ($Mode -eq "ps") {
    $initPs = Join-Path $script:TxRoot "src\powershell\init.ps1"
    $wt = Get-Command wt -ErrorAction SilentlyContinue
    if ($wt) {
        Start-Process wt -ArgumentList @("-w", "0", "new-tab", "--title", "TricksXTech PS Preview", "powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $initPs)
    } else {
        & powershell.exe -NoExit -ExecutionPolicy Bypass -File $initPs
    }
    return
}

if ($Mode -eq "cmd") {
    $initCmd = Join-Path $script:TxRoot "src\cmd\init.cmd"
    $wt = Get-Command wt -ErrorAction SilentlyContinue
    if ($wt) {
        Start-Process wt -ArgumentList @("-w", "0", "new-tab", "--title", "TricksXTech CMD Preview", "cmd.exe", "/k", $initCmd)
    } else {
        & cmd.exe /k $initCmd
    }
    return
}

if ($Mode -eq "split") {
    $initPs = Join-Path $script:TxRoot "src\powershell\init.ps1"
    $initCmd = Join-Path $script:TxRoot "src\cmd\init.cmd"
    $wt = Get-Command wt -ErrorAction SilentlyContinue
    if ($wt) {
        Start-Process wt -ArgumentList @(
            "-w", "0", "new-tab", "--title", "TricksXTech PowerShell", "powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $initPs,
            ";", "split-pane", "-V", "--title", "TricksXTech CMD", "cmd.exe", "/k", $initCmd
        )
        return
    }
}

# Default: Safe inline visual showcase (nothing written to system profiles)
$cfg = Get-TxConfig
if ($Theme) {
    $resolvedPrev = Resolve-TxThemeId $Theme
    if ($resolvedPrev) { $cfg.theme = $resolvedPrev }
}
$thm = Get-TxActiveTheme $cfg
$script:TxRuntimeConfig = $cfg
$script:TxRuntimeTheme = $thm
$script:TxRuntimeGlyphs = Get-TxGlyphs -Mode (Resolve-TxGlyphMode $cfg)

Show-TxHud -Config $cfg -Theme $thm -Force -IncludeNetwork
& (Join-Path $script:TxRoot "tx.ps1") preview
Write-Host (Format-TxText "  Sample Themed Directory Listing (ll) in $($script:TxRoot):" -Fg $thm.ui.primary -Bold)
Show-TxFileList -Path $script:TxRoot
Write-Host ""
Write-Host (Format-TxText "  Preview complete! No system files were modified." -Fg $thm.ui.success -Bold)
Write-Host (Format-TxText "  Try interactive sandbox: .\preview.ps1 -Mode ps | -Mode cmd | -Mode split" -Fg $thm.ui.muted)
Write-Host (Format-TxText "  Or launch the theme UI:  .\tx.ps1" -Fg $thm.ui.muted)
Write-Host (Format-TxText "  When ready to install:   .\install.ps1" -Fg $thm.ui.accent)
Write-Host ""
