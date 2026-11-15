@echo off
if not defined TX_ROOT (
    for %%I in ("%~dp0..\..") do set "TX_ROOT=%%~fI"
)
if exist "%TX_ROOT%\config\cmd_theme.cmd" (
    call "%TX_ROOT%\config\cmd_theme.cmd"
)
if not defined CLINK_DIR (
    if defined TX_PROMPT_BASE set "PROMPT=%TX_PROMPT_BASE%"
)
if defined TX_THEME_NAME (
    echo TricksXTech CMD reloaded [%TX_THEME_NAME%]
) else (
    echo TricksXTech CMD reloaded
)
