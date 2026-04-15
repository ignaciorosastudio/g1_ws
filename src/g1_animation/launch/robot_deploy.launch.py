import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition


def generate_launch_description():
    g1pilot_share = get_package_share_directory('g1pilot')
    urdf_file = os.path.join(
        g1pilot_share, 'description_files', 'urdf', 'g1_29dof_upperbody.urdf'
    )
    with open(urdf_file, 'r') as f:
        robot_description = f.read()

    return LaunchDescription([
        DeclareLaunchArgument('network_interface', default_value='enp3s0',
                              description='Ethernet interface connected to G1'),
        DeclareLaunchArgument('dry_run', default_value='true',
                              description='Preview only — do not send commands to robot'),
        DeclareLaunchArgument('loop', default_value='false',
                              description='Loop the animation when playing'),
        DeclareLaunchArgument('mode', default_value='damping',
                              description='Control mode: damping or walking'),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='Launch RViz and robot_state_publisher'),
        DeclareLaunchArgument('use_gui', default_value='false',
                              description='Use joint_state_publisher_gui instead of robot_publisher'),

        # Animation / robot control node
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
            condition=UnlessCondition(LaunchConfiguration('use_gui')),
        ),

        # Robot state publisher — needed by RViz to visualise the URDF
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
            output='screen',
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),

        # Optional GUI slider control (replaces robot_publisher for manual posing)
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            output='screen',
            condition=IfCondition(LaunchConfiguration('use_gui')),
        ),

        # RViz
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', os.path.join(g1pilot_share, 'config', '29dof.rviz')],
            output='screen',
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])
