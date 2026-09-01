from setuptools import find_packages, setup
import os, glob

package_name = 'rosy_bringup'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob.glob(os.path.join('launch', '*launch.*'))),
        ('share/' + package_name + '/config', glob.glob(os.path.join('config', '*.yaml')) + glob.glob(os.path.join('config', '*.xml'))),
        ('share/' + package_name + '/scripts', glob.glob(os.path.join('scripts', '*.sh'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pl3',
    maintainer_email='kyung133851@pinklab.art',
    description='ROSY bringup: motor/odometry/battery drivers for Pinky Pro',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bringup=rosy_bringup.bringup:main',
            'battery_publisher=rosy_bringup.battery_publisher:main',
            'dynamixel_probe=rosy_bringup.dynamixel_probe:main',
        ],
    },
)
