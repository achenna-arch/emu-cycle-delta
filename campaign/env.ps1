# Dot-source before building: . campaign\env.ps1
$root  = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root "_tools"
$sdk   = Join-Path $tools "sdk\zephyr-sdk-1.0.1"

$env:ZEPHYR_BASE = Join-Path $tools "zp\zephyr"
$env:ZEPHYR_SDK_INSTALL_DIR = $sdk
$env:ZEPHYR_TOOLCHAIN_VARIANT = "zephyr"
$env:PATH = (Join-Path $tools "venv\Scripts") + ";" + (Join-Path $sdk "hosttools\bin") + ";" + $env:PATH
