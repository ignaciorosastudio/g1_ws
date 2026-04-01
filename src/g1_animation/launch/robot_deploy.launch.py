import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('network_interface', default_value='enp3s0',
                              description='Ethernet interface connected to G1'),
        DeclareLaunchArgument('dry_run', default_value='true',
                              description='Print commands only, do not send to robot'),
        DeclareLaunchArgument('loop', default_value='true',
                              description='Loop the animation when playing'),
        DeclareLaunchArgument('mode', default_value='damping',
                              description='Control mode: damping (rt/lowcmd, robot static) or walking (rt/arm_sdk, loco controller active)'),

        Node(
            package='g1_animation',
            executable='robot_publisher',
            name='robot_publisher',
            parameters=[{
                'network_interface': LaunchConfiguration('network_interface'),
                'dry_run':           LaunchConfiguration('dry_run'),
                'loop':              LaunchConfiguration('loop'),
                'mode':              LaunchConfiguration('mode'),
            }],
            output='screen',
        ),
    ])
