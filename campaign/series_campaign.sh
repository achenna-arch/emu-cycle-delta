#!/bin/sh
# Measures the images of a list on one node. An image with 3 complete boots is left alone, so a
# new slot resumes the list, and a shorter log is kept aside before the image is measured again.
# Run on the Saclay SSH frontend, inside a running experiment.
# Usage: series_campaign.sh <exp_id> <node_id> <list> <log_dir>
set -u

exp=$1
node=$2
list=$3
dir=$4
mkdir -p "$dir"

complete() {
    [ "$(grep -c 'BENCH,DONE' "$1" 2>/dev/null)" -ge 3 ] 2>/dev/null
}

for pass in 1 2 3; do
    # A for loop, because nc would read a list given on stdin.
    for image in $(cat "$list"); do
        log="$dir/$image.log"
        complete "$log" && continue
        [ -f "$log" ] && mv "$log" "$log.short$pass"
        sh run_iotlab.sh "$exp" "$node" "elf/$image.elf" "$log" 15 3 || exit 1
    done
done
