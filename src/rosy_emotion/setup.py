from setuptools import find_packages, setup
import os, glob

package_name = 'rosy_emotion'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/emotion', glob.glob(os.path.join('emotion', '*.gif'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pl3',
    maintainer_email='kyung133851@pinklab.art',
    description='ROSY emotion display server',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            "rosy_emotion=rosy_emotion.rosy_emotion:main",
            "emotion_server=rosy_emotion.emotion_server:main"
        ],
    },
)