#!/bin/bash

# Deactivate any active venv
deactivate 2>/dev/null || true

source /opt/ros/humble/setup.bash

if [ -f ~/g1_ws/cyclone_ws/install/setup.bash ]; then
    source ~/g1_ws/cyclone_ws/install/setup.bash
fi

source ~/g1_ws/install/setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://${HOME}/g1_ws/config/cyclonedds.xml
export ROS_DOMAIN_ID=0
export UNITREE_DDS_PEER=192.168.123.164

echo "Robot env ready."
echo "  Python:       $(which python3)"
echo "  RMW:          $RMW_IMPLEMENTATION"
echo "  CycloneDDS:   $CYCLONEDDS_URI"
echo "  Domain:       $ROS_DOMAIN_ID"
echo "  DDS peer:     $UNITREE_DDS_PEER"
