from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'g1_animation'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='you',
    maintainer_email='you@example.com',
    description='G1 EDU+ animation pipeline',
    license='MIT',
    entry_points={
        'console_scripts': [
            'animation_publisher = g1_animation.animation_publisher:main',
            'animation_cli       = g1_animation.animation_cli:main',
            'robot_publisher     = g1_animation.robot_publisher:main',
            'wifi_publisher      = g1_animation.wifi_publisher:main',
            'pose_capture = g1_animation.pose_capture:main',
        ],
    },
)
