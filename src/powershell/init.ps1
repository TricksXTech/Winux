# TricksXTech PowerShell - Main Profile Loader

param(
    [switch]$NoHud,
    [switch]$Quiet
)

$script:TxRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

. (Join-Path $script:TxRoot "src\core\ansi.ps1")
. (Join-Path $script:TxRoot "src\core\config.ps1")
. (Join-Path $script:TxRoot "src\core\sysinfo.ps1")
. (Join-Path $script:TxRoot "src\core\hud.ps1")
. (Join-Path $script:TxRoot "src\powershell\jump.ps1")
. (Join-Path $script:TxRoot "src\powershell\ls_colors.ps1")
. (Join-Path $script:TxRoot "src\powershell\prompt.ps1")
. (Join-Path $script:TxRoot "src\powershell\productivity.ps1")
. (Join-Path $script:TxRoot "src\powershell\tools.ps1")
. (Join-Path $script:TxRoot "src\wt\wt_manager.ps1")

Initialize-TxEncoding

function Sync-TxRuntimeCache {
    $script:TxRuntimeConfig = Get-TxConfig
    $script:TxRuntimeTheme  = Get-TxActiveTheme $script:TxRuntimeConfig
    $script:TxRuntimeGlyphs = Get-TxGlyphs -Mode (Resolve-TxGlyphMode $script:TxRuntimeConfig)
}

Sync-TxRuntimeCache
Install-TxPrompt
Initialize-TxProductivity -Config $script:TxRuntimeConfig -Theme $script:TxRuntimeTheme

function global:tx {
    $cli = Join-Path $script:TxRoot "tx.ps1"
    & $cli @args
    Sync-TxRuntimeCache
    Apply-TxPSReadLineTheme -Config $script:TxRuntimeConfig -Theme $script:TxRuntimeTheme
}

$isInteractiveShell = $true
try {
    if ([Console]::IsOutputRedirected) { $isInteractiveShell = $false }
    $cliArgs = [Environment]::GetCommandLineArgs()
    $joinedArgs = ($cliArgs -join " ")
    if (($joinedArgs -match '(?i)\s-(c|command|e|encodedcommand|f|file)\b') -and ($joinedArgs -notmatch '(?i)\s-noexit\b')) {
        $isInteractiveShell = $false
    }
} catch { }

if (-not $NoHud -and -not $Quiet -and $isInteractiveShell) {
    Show-TxHud -Config $script:TxRuntimeConfig -Theme $script:TxRuntimeTheme
}
