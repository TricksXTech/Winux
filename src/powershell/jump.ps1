# TricksXTech PowerShell - Smart Frecency Directory Jumper (z)

$script:TxJumpData = $null
$script:TxPrevDir = $null

function Get-TxJumpDbPath {
    $root = Get-TxRootPath
    return (Join-Path $root "config\jump_db.json")
}

function Import-TxJumpDb {
    if ($null -ne $script:TxJumpData) { return $script:TxJumpData }
    $dbPath = Get-TxJumpDbPath
    $script:TxJumpData = @{}
    if (Test-Path $dbPath) {
        try {
            $raw = [System.IO.File]::ReadAllText($dbPath, [System.Text.Encoding]::UTF8)
            $obj = $raw | ConvertFrom-Json
            foreach ($p in $obj.PSObject.Properties) {
                $script:TxJumpData[$p.Name] = @{
                    score = [double]$p.Value.score
                    ts    = [long]$p.Value.ts
                }
            }
        } catch {
            $script:TxJumpData = @{}
        }
    }
    return $script:TxJumpData
}

function Save-TxJumpDb {
    if ($null -eq $script:TxJumpData) { return }
    $dbPath = Get-TxJumpDbPath
    try {
        $json = $script:TxJumpData | ConvertTo-Json -Depth 5
        Write-TxUtf8NoBom -Path $dbPath -Content $json
    } catch { }
}

function Register-TxJumpVisit {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    if (-not [System.IO.Directory]::Exists($Path)) { return }
    $db = Import-TxJumpDb
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    if ($db.ContainsKey($Path)) {
        $db[$Path].score = [Math]::Round($db[$Path].score + 1.0, 2)
        $db[$Path].ts = $now
    } else {
        $db[$Path] = @{ score = 1.0; ts = $now }
    }
    # Cap database size to top 150 entries
    if ($db.Count -gt 160) {
        $keep = $db.GetEnumerator() | Sort-Object { $_.Value.score } -Descending | Select-Object -First 150
        $newDb = @{}
        foreach ($e in $keep) { $newDb[$e.Key] = $e.Value }
        $script:TxJumpData = $newDb
    }
    Save-TxJumpDb
}

function z {
    param(
        [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
        [string[]]$Query
    )
    $cfg = if ($script:TxRuntimeConfig) { $script:TxRuntimeConfig } else { Get-TxConfig }
    $theme = if ($script:TxRuntimeTheme) { $script:TxRuntimeTheme } else { Get-TxActiveTheme $cfg }
    $ui = $theme.ui

    if (-not $Query -or $Query.Count -eq 0) {
        Set-Location $HOME
        return
    }
    $joined = ($Query -join " ").Trim()
    if ($joined -eq "-") {
        if ($script:TxPrevDir -and (Test-Path $script:TxPrevDir)) {
            $cur = (Get-Location).ProviderPath
            Set-Location $script:TxPrevDir
            $script:TxPrevDir = $cur
        }
        return
    }
    if (Test-Path $joined -PathType Container) {
        $script:TxPrevDir = (Get-Location).ProviderPath
        Set-Location $joined
        return
    }

    $db = Import-TxJumpDb
    if ($joined -eq "-l" -or $joined -eq "--list") {
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $rows = $db.GetEnumerator() | Where-Object { Test-Path $_.Key } | Sort-Object {
            $ageHrs = [Math]::Max(1.0, ($now - $_.Value.ts) / 3600.0)
            $_.Value.score * (10.0 / (1.0 + [Math]::Log($ageHrs)))
        } -Descending | Select-Object -First 15
        Write-Host (Format-TxText " Frequent Directories" -Fg $ui.primary -Bold)
        foreach ($r in $rows) {
            $sc = ("{0:N1}" -f $r.Value.score).PadLeft(6)
            Write-Host "  $(Format-TxText $sc -Fg $ui.accent)  $(Format-TxText $r.Key -Fg $ui.text)"
        }
        return
    }

    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $terms = $Query | ForEach-Object { $_.ToLowerInvariant() }
    $bestPath = $null
    $bestRank = -1.0

    foreach ($entry in @($db.GetEnumerator())) {
        $p = $entry.Key
        if (-not [System.IO.Directory]::Exists($p)) { continue }
        $low = $p.ToLowerInvariant()
        $allMatch = $true
        foreach ($t in $terms) {
            if (-not $low.Contains($t)) { $allMatch = $false; break }
        }
        if (-not $allMatch) { continue }
        $leaf = (Split-Path -Leaf $p).ToLowerInvariant()
        $leafBonus = if ($leaf.Contains($terms[-1])) { 2.5 } else { 1.0 }
        $ageHrs = [Math]::Max(1.0, ($now - $entry.Value.ts) / 3600.0)
        $rank = $entry.Value.score * $leafBonus * (10.0 / (1.0 + [Math]::Log($ageHrs)))
        if ($rank -gt $bestRank) {
            $bestRank = $rank
            $bestPath = $p
        }
    }

    if ($bestPath) {
        $script:TxPrevDir = (Get-Location).ProviderPath
        Set-Location $bestPath
    } else {
        Write-Host (Format-TxText "z: no matching directory found for '$joined'" -Fg $ui.warning)
    }
}
