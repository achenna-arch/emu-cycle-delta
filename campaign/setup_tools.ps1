# Fetches the free toolchain into _tools. Safe to rerun.
$ErrorActionPreference = "Continue"
$root  = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root "_tools"
$py    = Join-Path $tools "venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $tools | Out-Null
if (-not (Test-Path $py)) { python -m venv (Join-Path $tools "venv") }

& $py -m pip install --quiet --disable-pip-version-check west py7zr cmake ninja pyelftools
Write-Output "pip done: $LASTEXITCODE"

$sdk = Join-Path $tools "dl-sdk"
$ren = Join-Path $tools "dl-renode"
New-Item -ItemType Directory -Force -Path $sdk, $ren | Out-Null

gh release download v1.0.1 -R zephyrproject-rtos/sdk-ng -D $sdk --skip-existing `
    -p "zephyr-sdk-1.0.1_windows-x86_64_minimal.7z" `
    -p "toolchain_gnu_windows-x86_64_arm-zephyr-eabi.7z"
Write-Output "sdk download done: $LASTEXITCODE"

gh release download v1.17.0 -R renode/renode -D $ren --skip-existing `
    -p "renode-1.17.0.windows-portable.zip"
Write-Output "renode download done: $LASTEXITCODE"

Get-ChildItem $sdk, $ren -File | Select-Object Name, Length | Format-Table -AutoSize | Out-String | Write-Output
