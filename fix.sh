#!/bin/bash
cd "/mnt/f/Dev/Control/Robot/ROS/Rosy/Rosy OS"
for d in src/apps/* src/core/* src/hardware/* src/navigation/* src/sim/* src/site/*; do
  if [ -f "$d/setup.py" ]; then
    pkg=$(basename "$d")
    mkdir -p "$d/resource"
    touch "$d/resource/$pkg"
  fi
done
