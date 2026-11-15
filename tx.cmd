@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tx.ps1" %*
if exist "%~dp0config\cmd_theme.cmd" (
    call "%~dp0config\cmd_theme.cmd"
    if not defined CLINK_DIR (
        if defined TX_PROMPT_BASE set "PROMPT=%TX_PROMPT_BASE%"
    )
)
