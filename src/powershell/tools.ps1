# TricksXTech PowerShell - Free Built-In Tools Launcher

function Invoke-TricksToolPython {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptRelPath,
        [string[]]$ToolArgs = @(),
        [object[]]$PipeInput = $null
    )
    $root = Get-TxRootPath
    $scriptPath = Join-Path $root $ScriptRelPath
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Warning "Python 3 is required for $ScriptRelPath. Install Python or run via 'tx upgrade'."
        return
    }
    if ($null -ne $PipeInput) {
        $PipeInput | & $py.Source $scriptPath @ToolArgs
    } else {
        & $py.Source $scriptPath @ToolArgs
    }
}

function global:disk     { Invoke-TricksToolPython -ScriptRelPath "tools\disk_analyzer.py" }
function global:storage  { Invoke-TricksToolPython -ScriptRelPath "tools\disk_analyzer.py" }
function global:diskanalyzer { Invoke-TricksToolPython -ScriptRelPath "tools\disk_analyzer.py" }

function global:tools {
    param([switch]$Interactive, [switch]$i)
    if ($Interactive -or $i) {
        Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs @("--menu", "-i")
    } else {
        Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs @("--menu")
    }
}

function global:bigfiles {
    param([string]$Path = ".", [int]$Count = 20)
    Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs @("--bigfiles", $Path, [string]$Count)
}

function global:procs {
    param([int]$Count = 12)
    Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs @("--procs", [string]$Count)
}

function global:syshealth {
    param([int]$Count = 12)
    Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs @("--procs", [string]$Count)
}

function global:netinfo {
    Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs (@("--netinfo") + $args)
}

function global:netcheck {
    Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs (@("--netinfo") + $args)
}

function global:hashfile {
    param([Parameter(Mandatory = $true)][string]$Path, [string]$Expected = "")
    if ($Expected) {
        Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs @("--hash", $Path, $Expected)
    } else {
        Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs @("--hash", $Path)
    }
}

function global:loc {
    param([string]$Path = ".")
    Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs @("--loc", $Path)
}

function global:jsonfmt {
    param([Parameter(Mandatory = $true)][string]$Path)
    Invoke-TricksToolPython -ScriptRelPath "tools\free_tools.py" -ToolArgs @("--jsonfmt", $Path)
}

function global:wifi {
    Invoke-TricksToolPython -ScriptRelPath "tools\wifi_checker.py" -ToolArgs $args
}

function global:wificheck {
    Invoke-TricksToolPython -ScriptRelPath "tools\wifi_checker.py" -ToolArgs $args
}

function global:osint {
    Invoke-TricksToolPython -ScriptRelPath "tools\osint_tool.py" -ToolArgs $args
}

function global:grep {
    $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--grep") + $args) -PipeInput $pipe
}

function global:head {
    $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--head") + $args) -PipeInput $pipe
}

function global:tail {
    $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--tail") + $args) -PipeInput $pipe
}

function global:wc {
    $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--wc") + $args) -PipeInput $pipe
}

function global:df {
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--df") + $args)
}

function global:du {
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--du") + $args)
}

function global:udiff {
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--diff") + $args)
}

function global:b64 {
    $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--b64") + $args) -PipeInput $pipe
}

function global:jwt {
    $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--b64", "--jwt") + $args) -PipeInput $pipe
}

function global:ss {
    Invoke-TricksToolPython -ScriptRelPath "tools\linux_tools.py" -ToolArgs (@("--ss") + $args)
}

function global:subdomains {
    Invoke-TricksToolPython -ScriptRelPath "tools\recon_safe.py" -ToolArgs (@("--subdomains") + $args)
}

function global:webtech {
    Invoke-TricksToolPython -ScriptRelPath "tools\recon_safe.py" -ToolArgs (@("--webtech") + $args)
}

function global:lan {
    Invoke-TricksToolPython -ScriptRelPath "tools\recon_safe.py" -ToolArgs (@("--lan") + $args)
}

function global:portcheck {
    Invoke-TricksToolPython -ScriptRelPath "tools\recon_safe.py" -ToolArgs (@("--portcheck") + $args)
}

function global:vpn {
    Invoke-TricksToolPython -ScriptRelPath "tools\vpn_tool.py" -ToolArgs $args
}

function global:pwgen {
    Invoke-TricksToolPython -ScriptRelPath "tools\dev_tools.py" -ToolArgs (@("--pwgen") + $args)
}

function global:epoch {
    Invoke-TricksToolPython -ScriptRelPath "tools\dev_tools.py" -ToolArgs (@("--epoch") + $args)
}

function global:uuid {
    Invoke-TricksToolPython -ScriptRelPath "tools\dev_tools.py" -ToolArgs (@("--uuid") + $args)
}

function global:speedtest {
    Invoke-TricksToolPython -ScriptRelPath "tools\speedtest_tool.py" -ToolArgs $args
}

function global:netspeed {
    Invoke-TricksToolPython -ScriptRelPath "tools\speedtest_tool.py" -ToolArgs $args
}

# -- Network & HTTP Utilities --------------------------------------------------
function global:dns       { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--dns") + $args) }
function global:rdns      { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--rdns") + $args) }
function global:cidr      { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--cidr") + $args) }
function global:unshorten { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--unshorten") + $args) }
function global:robots    { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--robots") + $args) }
function global:sitemap   { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--sitemap") + $args) }
function global:httpcode  { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--httpcode") + $args) }
function global:uaparse   { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--uaparse") + $args) }
function global:serve     { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--serve") + $args) }
function global:lanspeed  { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--lanspeed") + $args) }
function global:pingcheck { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--pingcheck") + $args) }
function global:ftpget    { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--ftpget") + $args) }
function global:titlemeta { Invoke-TricksToolPython -ScriptRelPath "tools\net_extra.py" -ToolArgs (@("--titlemeta") + $args) }

# -- System & File Diagnostics -------------------------------------------------
function global:envfind   { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--envfind") + $args) }
function global:organize  { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--organize") + $args) }
function global:dupes     { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--dupes") + $args) }
function global:extrename { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--extrename") + $args) }
function global:replace   { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--replace") + $args) }
function global:perms     { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--perms") + $args) }
function global:cleantemp { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--cleantemp") + $args) }
function global:watchdir  { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--watchdir") + $args) }
function global:symlinks  { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--symlinks") + $args) }
function global:zipmgr    { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--zipmgr") + $args) }
function global:targz     { Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--targz") + $args) }
function global:clip      { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\sys_extra.py" -ToolArgs (@("--clip") + $args) -PipeInput $pipe }

# -- Cryptography & Hashing ----------------------------------------------------
function global:bcryptcheck { Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--bcryptcheck") + $args) }
function global:hmac256     { Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--hmac256") + $args) }
function global:rot13       { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--rot13") + $args) -PipeInput $pipe }
function global:bin2txt     { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--bin2txt") + $args) -PipeInput $pipe }
function global:ascii       { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--ascii") + $args) -PipeInput $pipe }
function global:tokengen    { Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--tokengen") + $args) }
function global:fencrypt    { Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--fencrypt") + $args) }
function global:htpasswd    { Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--htpasswd") + $args) }
function global:entropy     { Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--entropy") + $args) }
function global:crc32       { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--crc32") + $args) -PipeInput $pipe }
function global:rsagen      { Invoke-TricksToolPython -ScriptRelPath "tools\crypto_extra.py" -ToolArgs (@("--rsagen") + $args) }

# -- Developer & Data Processing -----------------------------------------------
function global:jsonmin   { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--jsonmin") + $args) -PipeInput $pipe }
function global:csv2json  { Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--csv2json") + $args) }
function global:json2csv  { Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--json2csv") + $args) }
function global:yaml2json { Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--yaml2json") + $args) }
function global:xmlfmt    { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--xmlfmt") + $args) -PipeInput $pipe }
function global:logparse  { Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--logparse") + $args) }
function global:cronparse { Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--cronparse") + $args) }
function global:md2html   { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--md2html") + $args) -PipeInput $pipe }
function global:htmlent   { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--htmlent") + $args) -PipeInput $pipe }
function global:sqlfmt    { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--sqlfmt") + $args) -PipeInput $pipe }
function global:colorconv { Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--colorconv") + $args) }
function global:lorem     { Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--lorem") + $args) }
function global:slugify   { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--slugify") + $args) -PipeInput $pipe }
function global:caseconv  { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--caseconv") + $args) -PipeInput $pipe }
function global:uniqsort  { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--uniqsort") + $args) -PipeInput $pipe }
function global:tomlcheck { Invoke-TricksToolPython -ScriptRelPath "tools\dev_extra.py" -ToolArgs (@("--tomlcheck") + $args) }

# -- Productivity & Workflow Utilities -----------------------------------------
function global:stopwatch { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--stopwatch") + $args) }
function global:countdown { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--countdown") + $args) }
function global:todo      { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--todo") + $args) }
function global:notes     { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--notes") + $args) }
function global:banner    { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--banner") + $args) }
function global:expense   { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--expense") + $args) }
function global:weather   { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--weather") + $args) }
function global:habit     { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--habit") + $args) }
function global:unitconv  { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--unitconv") + $args) }
function global:tzconv    { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--tzconv") + $args) }
function global:gitclean  { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--gitclean") + $args) }
function global:gitstats  { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--gitstats") + $args) }
function global:bookmarks { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--bookmarks") + $args) }
function global:pick      { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--pick") + $args) -PipeInput $pipe }
function global:pomodoro  { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--pomodoro") + $args) }
function global:calc      { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--calc") + $args) }
function global:fx        { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--fx") + $args) }
function global:pbar      { $pipe = if ($MyInvocation.ExpectingInput) { @($input) } else { $null }; Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--pbar") + $args) -PipeInput $pipe }
function global:aliases   { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--aliases") + $args) }
function global:contacts  { Invoke-TricksToolPython -ScriptRelPath "tools\prod_extra.py" -ToolArgs (@("--contacts") + $args) }

# -- Defensive Security, Forensics & Hardening --------------------------------
function global:secaudit    { Invoke-TricksToolPython -ScriptRelPath "tools\sec_extra.py" -ToolArgs (@("--secaudit") + $args) }
function global:peinspect   { Invoke-TricksToolPython -ScriptRelPath "tools\sec_extra.py" -ToolArgs (@("--peinspect") + $args) }
function global:exifinfo    { Invoke-TricksToolPython -ScriptRelPath "tools\sec_extra.py" -ToolArgs (@("--exifinfo") + $args) }
function global:hexview     { Invoke-TricksToolPython -ScriptRelPath "tools\sec_extra.py" -ToolArgs (@("--hexview") + $args) }
function global:hashid      { Invoke-TricksToolPython -ScriptRelPath "tools\sec_extra.py" -ToolArgs (@("--hashid") + $args) }
function global:secretaudit { Invoke-TricksToolPython -ScriptRelPath "tools\sec_extra.py" -ToolArgs (@("--secretaudit") + $args) }
function global:idncheck    { Invoke-TricksToolPython -ScriptRelPath "tools\sec_extra.py" -ToolArgs (@("--idncheck") + $args) }
function global:stego       { Invoke-TricksToolPython -ScriptRelPath "tools\sec_extra.py" -ToolArgs (@("--stego") + $args) }
function global:wordgen     { Invoke-TricksToolPython -ScriptRelPath "tools\sec_extra.py" -ToolArgs (@("--wordgen") + $args) }
function global:hackingtool { Invoke-TricksToolPython -ScriptRelPath "tools\hackingtool_tool.py" -ToolArgs $args }
function global:ht          { Invoke-TricksToolPython -ScriptRelPath "tools\hackingtool_tool.py" -ToolArgs $args }
function global:crypto      { Invoke-TricksToolPython -ScriptRelPath "tools\crypto.py" -ToolArgs $args }

# Load user-defined custom aliases safely (managed by the 'aliases' tool)
try {
    $txAliasFile = Join-Path (Get-TxRootPath) "config\data\custom_aliases.json"
    if (Test-Path $txAliasFile) {
        $aliasObj = Get-Content -Path $txAliasFile -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($prop in $aliasObj.PSObject.Properties) {
            $aName = [string]$prop.Name
            $aTarget = [string]$prop.Value
            if ($aName -match '^[A-Za-z][A-Za-z0-9_-]{0,31}$' -and $aTarget -and ($aTarget -notmatch '[\r\n;`]|\$\(')) {
                $toks = @()
                foreach ($m in [regex]::Matches($aTarget, '(?:[^\s"\x27]+|"[^"]*"|\x27[^\x27]*\x27)+')) {
                    $toks += $m.Value.Trim('"').Trim("'")
                }
                if ($toks.Count -gt 0) {
                    $exe = $toks[0]
                    $fixedArgs = if ($toks.Count -gt 1) { @($toks[1..($toks.Count - 1)]) } else { @() }
                    $sb = {
                        & $exe @fixedArgs @args
                    }.GetNewClosure()
                    Set-Item -Path "Function:global:$aName" -Value $sb -ErrorAction SilentlyContinue
                }
            }
        }
    }
} catch { }
