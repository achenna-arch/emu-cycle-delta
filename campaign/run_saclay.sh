#!/bin/sh
# Waits for the experiment, then runs the series of protocol section 14 and releases the nodes.
# Run on the Saclay SSH frontend under nohup, from the folder that holds elf/ and lists/.
# Usage: run_saclay.sh <exp_id>
exp=$1

iotlab-experiment wait -i "$exp" --step 60 --timeout 60000 || exit 1
sh series_campaign.sh "$exp" 1 lists/all.txt logs/n1 > n1.out 2>&1 &
a=$!
sh series_campaign.sh "$exp" 2 lists/repeated.txt logs/n2 > n2.out 2>&1 &
b=$!
sh series_campaign.sh "$exp" 3 lists/repeated.txt logs/n3 > n3.out 2>&1 &
c=$!
wait $a
wait $b
wait $c
iotlab-experiment stop -i "$exp"
touch "done.$exp"
