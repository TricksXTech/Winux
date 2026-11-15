@echo off
rem TricksXTech CMD Initializer
if defined TX_CMD_LOADED goto :eof

rem Guard: do not alter output or run HUD for non-interactive cmd /c calls
set "_tx_cl=%CMDCMDLINE:"=%"
if /i not "%_tx_cl:/c =%"=="%_tx_cl%" (
    set "_tx_cl="
    goto :eof
)
set "_tx_cl="
set "TX_CMD_LOADED=1"

for %%I in ("%~dp0..\..") do set "TX_ROOT=%%~fI"

rem Enable UTF-8 cleanly
chcp 65001 >nul 2>&1

rem Add TricksXTech root to session PATH so 'tx' works everywhere
echo ;%PATH%; | findstr /i /c:";%TX_ROOT%;" >nul 2>&1
if errorlevel 1 set "PATH=%TX_ROOT%;%PATH%"

rem Ensure cmd_theme.cmd exists, then load themed prompt
if not exist "%TX_ROOT%\config\cmd_theme.cmd" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ". '%TX_ROOT%\src\core\ansi.ps1'; . '%TX_ROOT%\src\core\config.ps1'; $script:TxRoot='%TX_ROOT%'; Update-TxCmdThemeFile" >nul 2>&1
)
if exist "%TX_ROOT%\config\cmd_theme.cmd" (
    call "%TX_ROOT%\config\cmd_theme.cmd"
)

rem Apply static ANSI prompt unless Clink is active
if not defined CLINK_DIR (
    if defined TX_PROMPT_BASE set "PROMPT=%TX_PROMPT_BASE%"
)

rem Load CMD aliases and macros
if exist "%TX_ROOT%\src\cmd\macros.doskey" (
    doskey /macrofile="%TX_ROOT%\src\cmd\macros.doskey" >nul 2>&1
)
doskey tx="%TX_ROOT%\tx.cmd" $* >nul 2>&1
doskey reload=call "%TX_ROOT%\src\cmd\reload.cmd" >nul 2>&1

where python >nul 2>&1
if not errorlevel 1 (
    doskey ll=python "%TX_ROOT%\src\cmd\tx_hud.py" --ls $* >nul 2>&1
    doskey la=python "%TX_ROOT%\src\cmd\tx_hud.py" --la $* >nul 2>&1
    doskey lt=python "%TX_ROOT%\src\cmd\tx_hud.py" --tree $* >nul 2>&1
    doskey sysinfo=python "%TX_ROOT%\src\cmd\tx_hud.py" --sysinfo >nul 2>&1
    doskey fetch=python "%TX_ROOT%\src\cmd\tx_hud.py" --sysinfo >nul 2>&1
    doskey disk=python "%TX_ROOT%\tools\disk_analyzer.py" >nul 2>&1
    doskey storage=python "%TX_ROOT%\tools\disk_analyzer.py" >nul 2>&1
    doskey diskanalyzer=python "%TX_ROOT%\tools\disk_analyzer.py" >nul 2>&1
    doskey tools=python "%TX_ROOT%\tools\free_tools.py" --menu $* >nul 2>&1
    doskey bigfiles=python "%TX_ROOT%\tools\free_tools.py" --bigfiles $* >nul 2>&1
    doskey procs=python "%TX_ROOT%\tools\free_tools.py" --procs $* >nul 2>&1
    doskey syshealth=python "%TX_ROOT%\tools\free_tools.py" --procs $* >nul 2>&1
    doskey netinfo=python "%TX_ROOT%\tools\free_tools.py" --netinfo $* >nul 2>&1
    doskey netcheck=python "%TX_ROOT%\tools\free_tools.py" --netinfo $* >nul 2>&1
    doskey hashfile=python "%TX_ROOT%\tools\free_tools.py" --hash $* >nul 2>&1
    doskey loc=python "%TX_ROOT%\tools\free_tools.py" --loc $* >nul 2>&1
    doskey jsonfmt=python "%TX_ROOT%\tools\free_tools.py" --jsonfmt $* >nul 2>&1
    doskey wifi=python "%TX_ROOT%\tools\wifi_checker.py" $* >nul 2>&1
    doskey wificheck=python "%TX_ROOT%\tools\wifi_checker.py" $* >nul 2>&1
    doskey osint=python "%TX_ROOT%\tools\osint_tool.py" $* >nul 2>&1
    doskey grep=python "%TX_ROOT%\tools\linux_tools.py" --grep $* >nul 2>&1
    doskey head=python "%TX_ROOT%\tools\linux_tools.py" --head $* >nul 2>&1
    doskey tail=python "%TX_ROOT%\tools\linux_tools.py" --tail $* >nul 2>&1
    doskey wc=python "%TX_ROOT%\tools\linux_tools.py" --wc $* >nul 2>&1
    doskey df=python "%TX_ROOT%\tools\linux_tools.py" --df $* >nul 2>&1
    doskey du=python "%TX_ROOT%\tools\linux_tools.py" --du $* >nul 2>&1
    doskey udiff=python "%TX_ROOT%\tools\linux_tools.py" --diff $* >nul 2>&1
    doskey b64=python "%TX_ROOT%\tools\linux_tools.py" --b64 $* >nul 2>&1
    doskey jwt=python "%TX_ROOT%\tools\linux_tools.py" --b64 --jwt $* >nul 2>&1
    doskey ss=python "%TX_ROOT%\tools\linux_tools.py" --ss $* >nul 2>&1
    doskey subdomains=python "%TX_ROOT%\tools\recon_safe.py" --subdomains $* >nul 2>&1
    doskey webtech=python "%TX_ROOT%\tools\recon_safe.py" --webtech $* >nul 2>&1
    doskey lan=python "%TX_ROOT%\tools\recon_safe.py" --lan $* >nul 2>&1
    doskey portcheck=python "%TX_ROOT%\tools\recon_safe.py" --portcheck $* >nul 2>&1
    doskey vpn=python "%TX_ROOT%\tools\vpn_tool.py" $* >nul 2>&1
    doskey pwgen=python "%TX_ROOT%\tools\dev_tools.py" --pwgen $* >nul 2>&1
    doskey epoch=python "%TX_ROOT%\tools\dev_tools.py" --epoch $* >nul 2>&1
    doskey uuid=python "%TX_ROOT%\tools\dev_tools.py" --uuid $* >nul 2>&1
    doskey speedtest=python "%TX_ROOT%\tools\speedtest_tool.py" $* >nul 2>&1
    doskey netspeed=python "%TX_ROOT%\tools\speedtest_tool.py" $* >nul 2>&1
    doskey dns=python "%TX_ROOT%\tools\net_extra.py" --dns $* >nul 2>&1
    doskey rdns=python "%TX_ROOT%\tools\net_extra.py" --rdns $* >nul 2>&1
    doskey cidr=python "%TX_ROOT%\tools\net_extra.py" --cidr $* >nul 2>&1
    doskey unshorten=python "%TX_ROOT%\tools\net_extra.py" --unshorten $* >nul 2>&1
    doskey robots=python "%TX_ROOT%\tools\net_extra.py" --robots $* >nul 2>&1
    doskey sitemap=python "%TX_ROOT%\tools\net_extra.py" --sitemap $* >nul 2>&1
    doskey httpcode=python "%TX_ROOT%\tools\net_extra.py" --httpcode $* >nul 2>&1
    doskey uaparse=python "%TX_ROOT%\tools\net_extra.py" --uaparse $* >nul 2>&1
    doskey serve=python "%TX_ROOT%\tools\net_extra.py" --serve $* >nul 2>&1
    doskey lanspeed=python "%TX_ROOT%\tools\net_extra.py" --lanspeed $* >nul 2>&1
    doskey pingcheck=python "%TX_ROOT%\tools\net_extra.py" --pingcheck $* >nul 2>&1
    doskey ftpget=python "%TX_ROOT%\tools\net_extra.py" --ftpget $* >nul 2>&1
    doskey titlemeta=python "%TX_ROOT%\tools\net_extra.py" --titlemeta $* >nul 2>&1
    doskey envfind=python "%TX_ROOT%\tools\sys_extra.py" --envfind $* >nul 2>&1
    doskey organize=python "%TX_ROOT%\tools\sys_extra.py" --organize $* >nul 2>&1
    doskey dupes=python "%TX_ROOT%\tools\sys_extra.py" --dupes $* >nul 2>&1
    doskey extrename=python "%TX_ROOT%\tools\sys_extra.py" --extrename $* >nul 2>&1
    doskey replace=python "%TX_ROOT%\tools\sys_extra.py" --replace $* >nul 2>&1
    doskey perms=python "%TX_ROOT%\tools\sys_extra.py" --perms $* >nul 2>&1
    doskey cleantemp=python "%TX_ROOT%\tools\sys_extra.py" --cleantemp $* >nul 2>&1
    doskey watchdir=python "%TX_ROOT%\tools\sys_extra.py" --watchdir $* >nul 2>&1
    doskey symlinks=python "%TX_ROOT%\tools\sys_extra.py" --symlinks $* >nul 2>&1
    doskey zipmgr=python "%TX_ROOT%\tools\sys_extra.py" --zipmgr $* >nul 2>&1
    doskey targz=python "%TX_ROOT%\tools\sys_extra.py" --targz $* >nul 2>&1
    doskey clip=python "%TX_ROOT%\tools\sys_extra.py" --clip $* >nul 2>&1
    doskey bcryptcheck=python "%TX_ROOT%\tools\crypto_extra.py" --bcryptcheck $* >nul 2>&1
    doskey hmac256=python "%TX_ROOT%\tools\crypto_extra.py" --hmac256 $* >nul 2>&1
    doskey rot13=python "%TX_ROOT%\tools\crypto_extra.py" --rot13 $* >nul 2>&1
    doskey bin2txt=python "%TX_ROOT%\tools\crypto_extra.py" --bin2txt $* >nul 2>&1
    doskey ascii=python "%TX_ROOT%\tools\crypto_extra.py" --ascii $* >nul 2>&1
    doskey tokengen=python "%TX_ROOT%\tools\crypto_extra.py" --tokengen $* >nul 2>&1
    doskey fencrypt=python "%TX_ROOT%\tools\crypto_extra.py" --fencrypt $* >nul 2>&1
    doskey htpasswd=python "%TX_ROOT%\tools\crypto_extra.py" --htpasswd $* >nul 2>&1
    doskey entropy=python "%TX_ROOT%\tools\crypto_extra.py" --entropy $* >nul 2>&1
    doskey crc32=python "%TX_ROOT%\tools\crypto_extra.py" --crc32 $* >nul 2>&1
    doskey rsagen=python "%TX_ROOT%\tools\crypto_extra.py" --rsagen $* >nul 2>&1
    doskey jsonmin=python "%TX_ROOT%\tools\dev_extra.py" --jsonmin $* >nul 2>&1
    doskey csv2json=python "%TX_ROOT%\tools\dev_extra.py" --csv2json $* >nul 2>&1
    doskey json2csv=python "%TX_ROOT%\tools\dev_extra.py" --json2csv $* >nul 2>&1
    doskey yaml2json=python "%TX_ROOT%\tools\dev_extra.py" --yaml2json $* >nul 2>&1
    doskey xmlfmt=python "%TX_ROOT%\tools\dev_extra.py" --xmlfmt $* >nul 2>&1
    doskey logparse=python "%TX_ROOT%\tools\dev_extra.py" --logparse $* >nul 2>&1
    doskey cronparse=python "%TX_ROOT%\tools\dev_extra.py" --cronparse $* >nul 2>&1
    doskey md2html=python "%TX_ROOT%\tools\dev_extra.py" --md2html $* >nul 2>&1
    doskey htmlent=python "%TX_ROOT%\tools\dev_extra.py" --htmlent $* >nul 2>&1
    doskey sqlfmt=python "%TX_ROOT%\tools\dev_extra.py" --sqlfmt $* >nul 2>&1
    doskey colorconv=python "%TX_ROOT%\tools\dev_extra.py" --colorconv $* >nul 2>&1
    doskey lorem=python "%TX_ROOT%\tools\dev_extra.py" --lorem $* >nul 2>&1
    doskey slugify=python "%TX_ROOT%\tools\dev_extra.py" --slugify $* >nul 2>&1
    doskey caseconv=python "%TX_ROOT%\tools\dev_extra.py" --caseconv $* >nul 2>&1
    doskey uniqsort=python "%TX_ROOT%\tools\dev_extra.py" --uniqsort $* >nul 2>&1
    doskey tomlcheck=python "%TX_ROOT%\tools\dev_extra.py" --tomlcheck $* >nul 2>&1
    doskey stopwatch=python "%TX_ROOT%\tools\prod_extra.py" --stopwatch $* >nul 2>&1
    doskey countdown=python "%TX_ROOT%\tools\prod_extra.py" --countdown $* >nul 2>&1
    doskey todo=python "%TX_ROOT%\tools\prod_extra.py" --todo $* >nul 2>&1
    doskey notes=python "%TX_ROOT%\tools\prod_extra.py" --notes $* >nul 2>&1
    doskey banner=python "%TX_ROOT%\tools\prod_extra.py" --banner $* >nul 2>&1
    doskey expense=python "%TX_ROOT%\tools\prod_extra.py" --expense $* >nul 2>&1
    doskey weather=python "%TX_ROOT%\tools\prod_extra.py" --weather $* >nul 2>&1
    doskey habit=python "%TX_ROOT%\tools\prod_extra.py" --habit $* >nul 2>&1
    doskey unitconv=python "%TX_ROOT%\tools\prod_extra.py" --unitconv $* >nul 2>&1
    doskey tzconv=python "%TX_ROOT%\tools\prod_extra.py" --tzconv $* >nul 2>&1
    doskey gitclean=python "%TX_ROOT%\tools\prod_extra.py" --gitclean $* >nul 2>&1
    doskey gitstats=python "%TX_ROOT%\tools\prod_extra.py" --gitstats $* >nul 2>&1
    doskey bookmarks=python "%TX_ROOT%\tools\prod_extra.py" --bookmarks $* >nul 2>&1
    doskey pick=python "%TX_ROOT%\tools\prod_extra.py" --pick $* >nul 2>&1
    doskey pomodoro=python "%TX_ROOT%\tools\prod_extra.py" --pomodoro $* >nul 2>&1
    doskey calc=python "%TX_ROOT%\tools\prod_extra.py" --calc $* >nul 2>&1
    doskey fx=python "%TX_ROOT%\tools\prod_extra.py" --fx $* >nul 2>&1
    doskey pbar=python "%TX_ROOT%\tools\prod_extra.py" --pbar $* >nul 2>&1
    doskey aliases=python "%TX_ROOT%\tools\prod_extra.py" --aliases $* >nul 2>&1
    doskey contacts=python "%TX_ROOT%\tools\prod_extra.py" --contacts $* >nul 2>&1
    doskey secaudit=python "%TX_ROOT%\tools\sec_extra.py" --secaudit $* >nul 2>&1
    doskey peinspect=python "%TX_ROOT%\tools\sec_extra.py" --peinspect $* >nul 2>&1
    doskey exifinfo=python "%TX_ROOT%\tools\sec_extra.py" --exifinfo $* >nul 2>&1
    doskey hexview=python "%TX_ROOT%\tools\sec_extra.py" --hexview $* >nul 2>&1
    doskey hashid=python "%TX_ROOT%\tools\sec_extra.py" --hashid $* >nul 2>&1
    doskey secretaudit=python "%TX_ROOT%\tools\sec_extra.py" --secretaudit $* >nul 2>&1
    doskey idncheck=python "%TX_ROOT%\tools\sec_extra.py" --idncheck $* >nul 2>&1
    doskey stego=python "%TX_ROOT%\tools\sec_extra.py" --stego $* >nul 2>&1
    doskey wordgen=python "%TX_ROOT%\tools\sec_extra.py" --wordgen $* >nul 2>&1
    doskey hackingtool=python "%TX_ROOT%\tools\hackingtool_tool.py" $* >nul 2>&1
    doskey ht=python "%TX_ROOT%\tools\hackingtool_tool.py" $* >nul 2>&1
    doskey crypto=python "%TX_ROOT%\tools\crypto_tool.py" $* >nul 2>&1
    if exist "%TX_ROOT%\config\data\custom_aliases.doskey" doskey /macrofile="%TX_ROOT%\config\data\custom_aliases.doskey" >nul 2>&1
    if not defined TX_NO_HUD (
        python "%TX_ROOT%\src\cmd\tx_hud.py"
    )
) else (
    doskey ll=dir /a:-h $* >nul 2>&1
    doskey la=dir /a $* >nul 2>&1
    doskey lt=tree /f $* >nul 2>&1
    doskey sysinfo=powershell -NoProfile -ExecutionPolicy Bypass -Command ". '%TX_ROOT%\src\core\ansi.ps1'; . '%TX_ROOT%\src\core\config.ps1'; . '%TX_ROOT%\src\core\sysinfo.ps1'; . '%TX_ROOT%\src\core\hud.ps1'; $script:TxRoot='%TX_ROOT%'; Show-TxHud -Force -IncludeNetwork" >nul 2>&1
    doskey fetch=powershell -NoProfile -ExecutionPolicy Bypass -Command ". '%TX_ROOT%\src\core\ansi.ps1'; . '%TX_ROOT%\src\core\config.ps1'; . '%TX_ROOT%\src\core\sysinfo.ps1'; . '%TX_ROOT%\src\core\hud.ps1'; $script:TxRoot='%TX_ROOT%'; Show-TxHud -Force -IncludeNetwork" >nul 2>&1
    if not defined TX_NO_HUD (
        powershell -NoProfile -ExecutionPolicy Bypass -Command ". '%TX_ROOT%\src\core\ansi.ps1'; . '%TX_ROOT%\src\core\config.ps1'; . '%TX_ROOT%\src\core\sysinfo.ps1'; . '%TX_ROOT%\src\core\hud.ps1'; $script:TxRoot='%TX_ROOT%'; Show-TxHud"
    )
)
