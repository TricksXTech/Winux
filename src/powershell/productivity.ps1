# TricksXTech PowerShell - PSReadLine Theming, Keybindings, and Productivity Utilities

function Apply-TxPSReadLineTheme {
    param(
        [hashtable]$Config,
        [hashtable]$Theme
    )
    if (-not $Config) { $Config = Get-TxConfig }
    if (-not $Theme) { $Theme = Get-TxActiveTheme $Config }
    if (-not $Config.productivity.psReadLineTheme) { return }

    $psrl = Get-Module PSReadLine -ErrorAction SilentlyContinue
    if (-not $psrl) {
        try { Import-Module PSReadLine -ErrorAction Stop } catch { return }
        $psrl = Get-Module PSReadLine -ErrorAction SilentlyContinue
    }
    if (-not $psrl) { return }

    $ui = $Theme.ui
    $pal = $Theme.palette
    $ver = $psrl.Version

    $colors = @{
        Command            = $ui.primary
        Parameter          = $ui.accent
        String             = $pal.green
        Operator           = $ui.secondary
        Variable           = $pal.purple
        Comment            = $ui.muted
        Number             = $pal.yellow
        Type               = $pal.cyan
        Keyword            = $ui.secondary
        Member             = $ui.text
        Default            = $ui.text
        Emphasis           = $ui.warning
        Error              = $ui.error
        ContinuationPrompt = $ui.muted
        Selection          = (Get-TxBg $pal.selection)
    }

    if ($ver -ge [version]"2.1.0") {
        $colors["InlinePrediction"] = $ui.muted
    }

    try {
        Set-PSReadLineOption -Colors $colors -BellStyle None -HistoryNoDuplicates -ErrorAction SilentlyContinue
    } catch { }

    if ($ver -ge [version]"2.1.0") {
        try {
            $src = if ($ver -ge [version]"2.2.0") { "HistoryAndPlugin" } else { "History" }
            $view = if ($ver -ge [version]"2.2.0" -and $Config.productivity.predictionView) { $Config.productivity.predictionView } else { "InlineView" }
            Set-PSReadLineOption -PredictionSource $src -PredictionViewStyle $view -ErrorAction SilentlyContinue
        } catch { }
    }

    try {
        Set-PSReadLineKeyHandler -Key UpArrow -Function HistorySearchBackward -ErrorAction SilentlyContinue
        Set-PSReadLineKeyHandler -Key DownArrow -Function HistorySearchForward -ErrorAction SilentlyContinue
        Set-PSReadLineKeyHandler -Key Tab -Function MenuComplete -ErrorAction SilentlyContinue
        Set-PSReadLineKeyHandler -Chord "Ctrl+d" -Function DeleteCharOrExit -ErrorAction SilentlyContinue
    } catch { }
}

function Initialize-TxProductivity {
    param(
        [hashtable]$Config,
        [hashtable]$Theme
    )
    Apply-TxPSReadLineTheme -Config $Config -Theme $Theme

    # Fast directory navigation
    function global:..   { Set-Location .. }
    function global:...  { Set-Location ..\.. }
    function global:.... { Set-Location ..\..\.. }

    function global:mkcd {
        param([Parameter(Mandatory = $true)][string]$Path)
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        Set-Location $Path
    }

    function global:touch {
        param([Parameter(Mandatory = $true)][string]$Path)
        if (Test-Path $Path) {
            (Get-Item $Path).LastWriteTime = Get-Date
        } else {
            New-Item -ItemType File -Path $Path -Force | Out-Null
        }
    }

    function global:which {
        param([Parameter(Mandatory = $true)][string]$Name)
        Get-Command $Name -All -ErrorAction SilentlyContinue | Select-Object CommandType, Name, Source
    }

    function global:sysinfo {
        Show-TxHud -Force -IncludeNetwork
    }

    function global:fetch {
        Show-TxHud -Force -IncludeNetwork
    }

    function global:ports {
        $cfg = if ($script:TxRuntimeConfig) { $script:TxRuntimeConfig } else { Get-TxConfig }
        $thm = if ($script:TxRuntimeTheme) { $script:TxRuntimeTheme } else { Get-TxActiveTheme $cfg }
        $ui = $thm.ui
        $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
            Sort-Object LocalPort | Select-Object LocalAddress, LocalPort, OwningProcess -Unique
        Write-Host (Format-TxText " Listening TCP Ports" -Fg $ui.primary -Bold)
        foreach ($c in $conns) {
            $pname = (Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue).ProcessName
            if (-not $pname) { $pname = "pid:$($c.OwningProcess)" }
            $pStr = ([string]$c.LocalPort).PadLeft(6)
            Write-Host "  $(Format-TxText $pStr -Fg $ui.accent -Bold)  $(Format-TxText $c.LocalAddress.PadRight(18) -Fg $ui.muted)  $(Format-TxText $pname -Fg $ui.text)"
        }
    }

    function global:myip {
        $cfg = if ($script:TxRuntimeConfig) { $script:TxRuntimeConfig } else { Get-TxConfig }
        $thm = if ($script:TxRuntimeTheme) { $script:TxRuntimeTheme } else { Get-TxActiveTheme $cfg }
        $ui = $thm.ui
        $locals = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
            Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and $_.ToString() -ne '127.0.0.1' }
        foreach ($ip in $locals) {
            Write-Host "$(Format-TxText 'Local IPv4:' -Fg $ui.secondary -Bold) $(Format-TxText $ip.ToString() -Fg $ui.accent)"
        }
    }

    function global:extract {
        param(
            [Parameter(Mandatory = $true)][string]$Archive,
            [string]$Destination = "."
        )
        if (-not (Test-Path $Archive)) {
            Write-Error "Archive not found: $Archive"
            return
        }
        if ($Archive -match '\.zip$') {
            Expand-Archive -LiteralPath $Archive -DestinationPath $Destination -Force
        } elseif (Get-Command tar -ErrorAction SilentlyContinue) {
            & tar -xf $Archive -C $Destination
        } else {
            Write-Error "Unsupported archive format (no tar available): $Archive"
        }
    }

    function global:reload {
        $loader = Join-Path (Get-TxRootPath) "src\powershell\init.ps1"
        . $loader -Quiet
        $thm = Get-TxActiveTheme
        Write-Host (Format-TxText "TricksXTech reloaded [$($thm.name)]" -Fg $thm.ui.success -Bold)
    }

    # Safe Git shortcuts (never override built-in PS aliases like gc, gp, gl, gm)
    if ($Config.productivity.gitAliases) {
        function global:gs    { & git status -sb @args }
        function global:gst   { & git status @args }
        function global:ga    { & git add @args }
        function global:gaa   { & git add --all @args }
        function global:gd    { & git diff @args }
        function global:gds   { & git diff --staged @args }
        function global:gcm   { param([string]$Message) & git commit -m $Message }
        function global:glog  { & git log --oneline --graph --decorate -n 20 @args }
        function global:gbr   { & git branch -vv @args }
        function global:gpush { & git push @args }
        function global:gpull { & git pull @args }
    }
}
