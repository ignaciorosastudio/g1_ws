#!/bin/bash

# Local development environment — no robot ethernet required.
# Use this for RViz, simulation, and CLI debugging without the G1 connected.

deactivate 2>/dev/null || true

source /opt/ros/humble/setup.bash

if [ -f ~/g1_ws/cyclone_ws/install/setup.bash ]; then
    source ~/g1_ws/cyclone_ws/install/setup.bash
fi

source ~/g1_ws/install/setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://${HOME}/g1_ws/config/cyclonedds_local.xml
export ROS_DOMAIN_ID=0

echo "Local env ready (loopback only, no robot required)."
echo "  Python:       $(which python3)"
echo "  RMW:          $RMW_IMPLEMENTATION"
echo "  CycloneDDS:   $CYCLONEDDS_URI"
echo "  Domain:       $ROS_DOMAIN_ID"
