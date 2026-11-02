#!/bin/sh
# Flashes one image on one nRF52840DK and records its serial output.
# Run on the Saclay SSH frontend, inside a running experiment.
# Usage: run_iotlab.sh <exp_id> <node_id> <firmware.elf> <log> [seconds] [boots]
set -eu

exp=$1
node=$2
fw=$3
log=$4
secs=${5:-60}
boots=${6:-3}
list="saclay,nrf52840dk,$node"

iotlab-node -i "$exp" --flash "$fw" -l "$list" > /dev/null
: > "$log"

i=0
while [ "$i" -lt "$boots" ]; do
    timeout "$secs" nc "nrf52840dk-$node" 20000 >> "$log" &
    capture=$!
    sleep 2
    iotlab-node -i "$exp" --reset -l "$list" > /dev/null
    wait "$capture" || true
    i=$((i + 1))
done
