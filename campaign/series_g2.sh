#!/bin/sh
# Measures the images of gate G2 on one node. Logs go to g2_n<node>/.
# Run on the Saclay SSH frontend, inside a running experiment.
# Usage: series_g2.sh <exp_id> <node_id>
exp=$1
node=$2
dir=g2_n$node
mkdir -p "$dir"

images="smoke_p0 smoke_p4 smoke_p8 smoke_p12"
images="$images smoke_g1 smoke_g2 smoke_g3 smoke_g4 smoke_g5 smoke_g6 smoke_g7 smoke_g8"
for tag in mut_alu32 mut_load32 A000_parent A000_child A001_parent A001_child; do
    images="$images ${tag}_p0 ${tag}_p4 ${tag}_p8 ${tag}_p12"
done

for i in $images; do
    sh run_iotlab.sh "$exp" "$node" "$i.elf" "$dir/$i.log" 15 3
    echo "$i exit=$? lines=$(wc -l < "$dir/$i.log") starts=$(grep -c BENCH,START "$dir/$i.log") done=$(grep -c BENCH,DONE "$dir/$i.log")"
done
date -u
