@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "BACKEND_DIR=%%~fI"
for %%I in ("%SCRIPT_DIR%..\..") do set "SAAS_DIR=%%~fI"

set "PYTHON_EXE=%SAAS_DIR%\venv_saas\Scripts\python.exe"
set "RESTORE_SCRIPT=%SCRIPT_DIR%restore_saas_db_backup.py"
set "BACKUP_DIR=%BACKEND_DIR%\backups"
set "BACKUP_FILE=%~1"

if not exist "%PYTHON_EXE%" (
    echo ERRO: Python do ambiente virtual nao encontrado em:
    echo %PYTHON_EXE%
    exit /b 1
)

if not exist "%RESTORE_SCRIPT%" (
    echo ERRO: Script de restauracao nao encontrado em:
    echo %RESTORE_SCRIPT%
    exit /b 1
)

if not defined BACKUP_FILE (
    for /f "delims=" %%F in ('dir /b /a:-d /o-d "%BACKUP_DIR%\*.zip" 2^>nul') do (
        set "BACKUP_FILE=%BACKUP_DIR%\%%F"
        goto :backup_found
    )
)

:backup_found
if not defined BACKUP_FILE (
    echo ERRO: Nenhum backup .zip encontrado em:
    echo %BACKUP_DIR%
    echo.
    echo Use assim, informando o arquivo manualmente:
    echo %~nx0 "C:\caminho\brana_saas_full_YYYYMMDD_HHMMSS.zip"
    exit /b 1
)

if not exist "%BACKUP_FILE%" (
    echo ERRO: Arquivo de backup nao encontrado:
    echo %BACKUP_FILE%
    exit /b 1
)

echo.
echo Backup selecionado:
echo %BACKUP_FILE%
echo.
echo ATENCAO: esta restauracao substitui os dados atuais do banco do SaaS.
set /p CONFIRMA=Digite SIM para continuar: 

if /I not "%CONFIRMA%"=="SIM" (
    echo Operacao cancelada.
    exit /b 1
)

echo.
echo Restaurando backup...
"%PYTHON_EXE%" "%RESTORE_SCRIPT%" "%BACKUP_FILE%" --yes
if errorlevel 1 (
    echo.
    echo ERRO: a restauracao falhou.
    exit /b 1
)

echo.
echo Restauracao concluida com sucesso.
exit /b 0
