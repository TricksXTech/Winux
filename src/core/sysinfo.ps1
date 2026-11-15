# TricksXTech Core - Fast System Telemetry & Git Repo Detection

function Find-TxGitRoot {
    param([string]$StartPath = (Get-Location).ProviderPath)
    if ([string]::IsNullOrEmpty($StartPath)) { return $null }
    try {
        $dir = New-Object System.IO.DirectoryInfo($StartPath)
        while ($null -ne $dir) {
            $gitPath = Join-Path $dir.FullName ".git"
            if ([System.IO.Directory]::Exists($gitPath) -or [System.IO.File]::Exists($gitPath)) {
                return $dir.FullName
            }
            $dir = $dir.Parent
        }
    } catch { }
    return $null
}

function Get-TxGitStatus {
    param([string]$Path = (Get-Location).ProviderPath)
    $root = Find-TxGitRoot -StartPath $Path
    if (-not $root) { return $null }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return $null }

    try {
        $lines = & git -C $Path status --porcelain=v2 --branch 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }

        $branch = ""
        $oid = ""
        $ahead = 0
        $behind = 0
        $staged = 0
        $modified = 0
        $untracked = 0
        $conflicts = 0

        foreach ($line in $lines) {
            if ($line -match '^# branch\.head (.+)$') {
                $branch = $Matches[1].Trim()
            } elseif ($line -match '^# branch\.oid ([0-9a-f]+)') {
                $oid = $Matches[1].Substring(0, [Math]::Min(7, $Matches[1].Length))
            } elseif ($line -match '^# branch\.ab \+(\d+) -(\d+)') {
                $ahead = [int]$Matches[1]
                $behind = [int]$Matches[2]
            } elseif ($line.StartsWith("1 ") -or $line.StartsWith("2 ")) {
                $xy = $line.Substring(2, 2)
                if ($xy[0] -ne '.') { $staged++ }
                if ($xy[1] -ne '.') { $modified++ }
            } elseif ($line.StartsWith("u ")) {
                $conflicts++
            } elseif ($line.StartsWith("? ")) {
                $untracked++
            }
        }

        if ($branch -eq "(detached)" -or [string]::IsNullOrEmpty($branch)) {
            $branch = if ($oid) { "@$oid" } else { "detached" }
        }

        return [ordered]@{
            Root      = $root
            RepoName  = Split-Path -Leaf $root
            Branch    = $branch
            Ahead     = $ahead
            Behind    = $behind
            Staged    = $staged
            Modified  = $modified
            Untracked = $untracked
            Conflicts = $conflicts
            IsDirty   = (($staged + $modified + $untracked + $conflicts) -gt 0)
        }
    } catch {
        return $null
    }
}

function Get-TxSystemInfo {
    param([switch]$IncludeNetwork)

    # OS Name & Build from registry (instant)
    $cv = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -ErrorAction SilentlyContinue
    $buildNum = 0
    if ($cv.CurrentBuildNumber) { [void][int]::TryParse($cv.CurrentBuildNumber, [ref]$buildNum) }
    $osTitle = if ($buildNum -ge 22000) { "Windows 11" } else { "Windows 10" }
    $edition = ($cv.ProductName -replace '^Windows \d+\s*', '').Trim()
    $dispVer = $cv.DisplayVersion
    $osDisplay = "$osTitle $edition"
    if ($dispVer) { $osDisplay += " $dispVer" }
    if ($buildNum -gt 0) { $osDisplay += " (Build $buildNum)" }

    # CPU from registry
    $cpuName = (Get-ItemProperty "HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor\0" -ErrorAction SilentlyContinue).ProcessorNameString
    if ($cpuName) {
        $cpuName = ($cpuName -replace '\s+', ' ' -replace '\(R\)|\(TM\)|CPU\s*', '').Trim()
    } else {
        $cpuName = $env:PROCESSOR_ARCHITECTURE
    }
    $cores = [Environment]::ProcessorCount

    # Memory (fast .NET ComputerInfo with CIM fallback)
    $ramUsedGB = 0.0
    $ramTotalGB = 0.0
    $ramPct = 0
    try {
        Add-Type -AssemblyName Microsoft.VisualBasic -ErrorAction Stop
        $ci = New-Object Microsoft.VisualBasic.Devices.ComputerInfo
        $tot = [double]$ci.TotalPhysicalMemory
        $avail = [double]$ci.AvailablePhysicalMemory
        if ($tot -gt 0) {
            $ramTotalGB = [Math]::Round($tot / 1GB, 1)
            $ramUsedGB = [Math]::Round(($tot - $avail) / 1GB, 1)
            $ramPct = [int][Math]::Round((($tot - $avail) / $tot) * 100)
        }
    } catch {
        try {
            $osCim = Get-CimInstance Win32_OperatingSystem -Property TotalVisibleMemorySize, FreePhysicalMemory -ErrorAction Stop
            $totKB = [double]$osCim.TotalVisibleMemorySize
            $freeKB = [double]$osCim.FreePhysicalMemory
            if ($totKB -gt 0) {
                $ramTotalGB = [Math]::Round($totKB / 1MB, 1)
                $ramUsedGB = [Math]::Round(($totKB - $freeKB) / 1MB, 1)
                $ramPct = [int][Math]::Round((($totKB - $freeKB) / $totKB) * 100)
            }
        } catch { }
    }

    # Current/System Drive space
    $curDriveLetter = (Get-Location).Drive.Name
    if (-not $curDriveLetter) { $curDriveLetter = "C" }
    $diskUsedGB = 0.0
    $diskTotalGB = 0.0
    $diskPct = 0
    try {
        $drv = [System.IO.DriveInfo]::new($curDriveLetter)
        if ($drv.IsReady -and $drv.TotalSize -gt 0) {
            $diskTotalGB = [Math]::Round($drv.TotalSize / 1GB, 0)
            $diskUsedGB = [Math]::Round(($drv.TotalSize - $drv.AvailableFreeSpace) / 1GB, 0)
            $diskPct = [int][Math]::Round((($drv.TotalSize - $drv.AvailableFreeSpace) / [double]$drv.TotalSize) * 100)
        }
    } catch { }

    # Uptime via TickCount64 (available on .NET Core/.NET 5+, fallback unsigned TickCount on .NET 4.8)
    $uptimeMs = 0L
    if ([System.Environment].GetProperty("TickCount64")) {
        $uptimeMs = [int64][System.Environment]::TickCount64
    } else {
        $uptimeMs = ([int64][System.Environment]::TickCount -band 0xFFFFFFFFL)
    }
    $ts = [TimeSpan]::FromMilliseconds([Math]::Max(0, $uptimeMs))
    $uptimeStr = if ($ts.Days -gt 0) {
        "$($ts.Days)d $($ts.Hours)h $($ts.Minutes)m"
    } elseif ($ts.Hours -gt 0) {
        "$($ts.Hours)h $($ts.Minutes)m"
    } else {
        "$($ts.Minutes)m $($ts.Seconds)s"
    }

    # Battery / Power
    $powerStr = "AC Power"
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $ps = [System.Windows.Forms.SystemInformation]::PowerStatus
        if ($ps.BatteryChargeStatus -ne [System.Windows.Forms.BatteryChargeStatus]::NoSystemBattery) {
            $bp = [int][Math]::Round($ps.BatteryLifePercent * 100)
            $chg = if ($ps.PowerLineStatus -eq [System.Windows.Forms.PowerLineStatus]::Online) { "Charging" } else { "Battery" }
            $powerStr = "$bp% ($chg)"
        }
    } catch { }

    # Local IP (optional for full HUD / sysinfo)
    $ipStr = ""
    if ($IncludeNetwork) {
        try {
            $ips = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
                Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and $_.ToString() -ne '127.0.0.1' } |
                Select-Object -First 1
            if ($ips) { $ipStr = $ips.ToString() }
        } catch { }
    }

    # Admin status
    $isAdmin = $false
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $pr = New-Object Security.Principal.WindowsPrincipal($id)
        $isAdmin = $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { }

    return [ordered]@{
        User        = $env:USERNAME
        Host        = $env:COMPUTERNAME
        IsAdmin     = $isAdmin
        OS          = $osDisplay
        Shell       = "PowerShell $($PSVersionTable.PSVersion)"
        CPU         = "$cpuName ($cores threads)"
        RAMUsedGB   = $ramUsedGB
        RAMTotalGB  = $ramTotalGB
        RAMPct      = $ramPct
        Drive       = "${curDriveLetter}:"
        DiskUsedGB  = $diskUsedGB
        DiskTotalGB = $diskTotalGB
        DiskPct     = $diskPct
        Uptime      = $uptimeStr
        Power       = $powerStr
        IP          = $ipStr
    }
}
