# Unpacks the archives and fetches Zephyr with only the modules this project needs. Safe to rerun.
$ErrorActionPreference = "Continue"
$root  = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root "_tools"
$py    = Join-Path $tools "venv\Scripts\python.exe"
$west  = Join-Path $tools "venv\Scripts\west.exe"
$sdk   = Join-Path $tools "sdk"
$zp    = Join-Path $tools "zp"
$env:PATH = (Join-Path $tools "venv\Scripts") + ";" + $env:PATH

New-Item -ItemType Directory -Force -Path $sdk, $zp | Out-Null

foreach ($a in Get-ChildItem (Join-Path $tools "dl-sdk") -Filter *.7z) {
    & $py -I -c "import sys,py7zr; py7zr.SevenZipFile(sys.argv[1]).extractall(sys.argv[2])" $a.FullName $sdk
    Write-Output "extracted $($a.Name): $LASTEXITCODE"
}

$renode = Join-Path $tools "renode"
if (-not (Test-Path $renode)) {
    Expand-Archive -Path (Join-Path $tools "dl-renode\renode-1.17.0.windows-portable.zip") -DestinationPath $renode
    Write-Output "renode extracted"
}

$zephyr = Join-Path $zp "zephyr"
if (-not (Test-Path $zephyr)) {
    # Blobless: full history for pair selection, file contents on demand.
    git clone --quiet --filter=blob:none https://github.com/zephyrproject-rtos/zephyr $zephyr
    Write-Output "zephyr clone: $LASTEXITCODE"
}

Push-Location $zp
if (-not (Test-Path (Join-Path $zp ".west"))) { & $west init -l $zephyr }
& $west config manifest.project-filter -- "-.*,+cmsis,+cmsis_6,+hal_nordic"
& $west update --narrow -o=--depth=1
Write-Output "west update: $LASTEXITCODE"
Pop-Location

& $py -m pip install --quiet --disable-pip-version-check -r (Join-Path $zephyr "scripts\requirements-base.txt")
Write-Output "requirements: $LASTEXITCODE"

Get-ChildItem $sdk -Directory -Recurse -Depth 1 | Select-Object -ExpandProperty FullName
git -C $zephyr log -1 --format="zephyr HEAD %H %cs"
Get-ChildItem $tools -Directory | ForEach-Object {
    $mb = [math]::Round((Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB)
    Write-Output ("{0,8} MB  {1}" -f $mb, $_.Name)
}
