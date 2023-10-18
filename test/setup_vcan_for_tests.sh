#!/bin/bash
set -euo pipefail

sudo modprobe can vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0

