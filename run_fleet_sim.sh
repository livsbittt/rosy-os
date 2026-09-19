#!/bin/bash
# run_fleet_sim.sh
# One-click startup script for multi-robot simulation + sensor control + fleet orchestration

set -e

ROBOTS=${1:-2}
echo "Starting $ROBOTS-robot fleet simulation..."

# 1. Source ROS2 workspace
source /opt/ros/jazzy/setup.bash
source install/setup.bash

# 2. Cleanup previous processes
killall -9 ruby gz python3 parameter_bridge create 2>/dev/null || true

# 3. Start gz_multi.launch.py in the background
echo "[1/3] Starting Gazebo Multi-Robot Environment (core+nav2)..."
ros2 launch src/sim/gz_sim/launch/gz_multi.launch.py robots:=$ROBOTS world_name:=/tmp/map_260905.world mode:=nav core:=true headless:=true spawn_x:=-0.5 spawn_spacing:=1.0 > /tmp/rosy_gz.log 2>&1 &
GZ_PID=$!

echo "Waiting for robots.yaml to be generated..."
ROBOTS_YAML=""
for i in {1..30}; do
    # Find the newest robots.yaml in /tmp/rosy_gz_multi_*/
    YAML_PATH=$(ls -t /tmp/rosy_gz_multi_*/robots.yaml 2>/dev/null | head -n 1)
    if [ -n "$YAML_PATH" ] && [ -f "$YAML_PATH" ]; then
        ROBOTS_YAML=$YAML_PATH
        break
    fi
    sleep 1
done

if [ -z "$ROBOTS_YAML" ]; then
    echo "Error: Failed to find robots.yaml. Simulation might have crashed."
    cat /tmp/rosy_gz.log
    kill $GZ_PID 2>/dev/null || true
    exit 1
fi
echo "Found Fleet manifest: $ROBOTS_YAML"
sleep 5 # Wait a bit longer for Gazebo to fully settle

# 4. Start control/sensing nodes for each robot in the background
echo "[2/3] Starting Control/Sensing stack for each robot..."
for (( i=1; i<=$ROBOTS; i++ )); do
    NS=$(printf "rosy_%02d" $i)
    WEB_PORT=$(( 28151 + i * 10 ))
    BACKEND_PORT=$(( 28152 + i * 10 ))
    
    echo "  -> $NS (Web UI: http://localhost:$WEB_PORT)"
    
    export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
    export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
    export ROSY_NAMESPACE=$NS
    
    ros2 launch control robot.launch.py profile:=sensing localization_required:=false start_camera:=false web_port:=$WEB_PORT web_backend_port:=$BACKEND_PORT > /tmp/rosy_control_$NS.log 2>&1 &
done

# 5. Start Fleet Server
echo "[3/3] Starting Fleet Console..."
export PYTHONPATH="$PYTHONPATH:$(pwd)/src/site/fleet:$(pwd)/src/core/core_common:$(pwd)/src/core/core_features"

echo ""
echo "========================================================="
echo "✅ All Systems Running!"
echo ""
echo "📍 Fleet Console:  http://localhost:8090/console"
for (( i=1; i<=$ROBOTS; i++ )); do
    NS=$(printf "rosy_%02d" $i)
    WEB_PORT=$(( 28151 + i * 10 ))
    echo "📍 $NS Web:      http://localhost:$WEB_PORT"
done
echo "========================================================="
echo "Press Ctrl+C to stop all processes."

python3 src/site/fleet/fleet/cli.py console --robots "$ROBOTS_YAML" \
    --ui-tokens "$PWD/src/core/core_api_web/core_api_web/web/tokens.css"

# Cleanup on exit
kill $(jobs -p) 2>/dev/null || true
echo "Stopped."
