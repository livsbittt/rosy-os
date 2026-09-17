from setuptools import find_packages, setup

package_name = "rosy_games"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", ["config/match.yaml"]),
    ],
    install_requires=["setuptools", "httpx", "PyYAML"],
    zip_safe=True,
    description="Laptop game host. Not a CORE RobotMode.",
    license="Apache-2.0",
    entry_points={"console_scripts": ["rosy_games=rosy_games.cli:main"]},
)
