import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition
from launch.actions import SetEnvironmentVariable


def generate_launch_description():
    g1pilot_share = get_package_share_directory('g1pilot')

    urdf_file = os.path.join(
        g1pilot_share,
        'description_files',
        'urdf',
        'g1_29dof_upperbody.urdf'
    )

    with open(urdf_file, 'r') as f:
        robot_description = f.read()

    # Launch argument
    use_gui = LaunchConfiguration('use_gui')

    return LaunchDescription([
        SetEnvironmentVariable(
            'CYCLONEDDS_URI',
            'file://' + os.path.expanduser('~/g1_ws/config/cyclonedds_local.xml')
        ),

        # Declare argument
        DeclareLaunchArgument(
            'use_gui',
            default_value='false',
            description='Use joint_state_publisher_gui instead of animation node'
        ),

        # Robot state publisher (always needed)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
            output='screen',
        ),

        # Animation node (ONLY if GUI is false)
        Node(
            package='g1_animation',
            executable='animation_publisher',
            name='animation_publisher',
            parameters=[{'loop': True}],
            output='screen',
            condition=UnlessCondition(use_gui),
        ),

        # Joint state publisher GUI (ONLY if GUI is true)
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            parameters=[{'robot_description': robot_description}],
            output='screen',
            condition=IfCondition(use_gui),
        ),

        # RViz
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=[
                '-d',
                os.path.join(g1pilot_share, 'config', '29dof.rviz')
            ],
            output='screen',
        ),
    ])
