# syntax=docker/dockerfile:1.7
ARG ROS_IMAGE=ros:jazzy-ros-base

FROM ${ROS_IMAGE} AS runtime-common

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROS_LOG_DIR=/tmp/ros-logs

# Hub linux/arm64 ros:jazzy-ros-base from 2026-09-16 ships 0-byte CPython
# stdlib, debpython, and colcon sources. Reinstall from Ubuntu ports in
# this order: stdlib first (so python3 runs), then python3-minimal
# (debpython), then colcon plugins (otherwise `colcon build` exits 0 with
# no install/). Later stages --reinstall numpy/yaml/pip. No-op on a
# healthy amd64 or native Pi image of the same packages.
RUN apt-get -o Acquire::Retries=5 update \
    && apt-get install --reinstall -y --no-install-recommends \
        libpython3.12-minimal \
        libpython3.12-stdlib \
    && apt-get install --reinstall -y --no-install-recommends \
        python3-minimal \
        python3 \
    && apt-get install --reinstall -y --no-install-recommends \
        python3-colcon-argcomplete \
        python3-colcon-bash \
        python3-colcon-cd \
        python3-colcon-cmake \
        python3-colcon-common-extensions \
        python3-colcon-core \
        python3-colcon-defaults \
        python3-colcon-devtools \
        python3-colcon-library-path \
        python3-colcon-metadata \
        python3-colcon-mixin \
        python3-colcon-notification \
        python3-colcon-output \
        python3-colcon-package-information \
        python3-colcon-package-selection \
        python3-colcon-parallel-executor \
        python3-colcon-pkg-config \
        python3-colcon-powershell \
        python3-colcon-python-setup-py \
        python3-colcon-recursive-crawl \
        python3-colcon-ros \
        python3-colcon-test-result \
        python3-colcon-zsh \
        python3-vcstool \
        ros-jazzy-ament-package \
    && apt-get install -y --no-install-recommends \
        ros-jazzy-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

COPY src/rosy_bringup/config/cyclonedds_localhost.xml /etc/rosy/cyclonedds.xml

FROM runtime-common AS core-runtime

COPY deploy/robot/requirements-core.txt /tmp/requirements-core.txt
RUN apt-get -o Acquire::Retries=5 update \
    && apt-get install --reinstall -y --no-install-recommends \
        python3-pip \
        python3-numpy \
        python3-yaml \
    && apt-get install -y --no-install-recommends \
        ros-jazzy-nav2-msgs \
        ros-jazzy-rcl-interfaces \
        ros-jazzy-visualization-msgs \
        ros-jazzy-tf2-ros \
    && python3 -m pip install --break-system-packages --no-cache-dir \
        -r /tmp/requirements-core.txt \
    && mkdir -p /var/lib/rosy/.rosy \
    && mkdir -p /host/proc/net /host/etc /host/sys/class/thermal /host/sys/devices/virtual/thermal \
    && chown -R 1000:1000 /var/lib/rosy \
    && rm -rf /var/lib/apt/lists/* /tmp/requirements-core.txt

FROM core-runtime AS core-build

WORKDIR /opt/rosy_ws
# omx/imu/vision/control belong to optional slices, not this core image.
COPY src/rosy_interfaces ./src/rosy_interfaces
COPY src/rosy_core ./src/rosy_core
RUN set -eo pipefail \
    && source /opt/ros/jazzy/setup.bash \
    && colcon build --merge-install --packages-up-to rosy_core \
    && test -d /opt/rosy_ws/install

FROM core-runtime AS core

COPY --from=core-build /opt/rosy_ws/install /opt/rosy_ws/install
COPY deploy/robot/entrypoint.sh /usr/local/bin/rosy-entrypoint
RUN chmod 0755 /usr/local/bin/rosy-entrypoint
ENV HOME=/var/lib/rosy \
    ROSY_CONFIG=/etc/rosy/rosy.yaml \
    CYCLONEDDS_URI=file:///etc/rosy/cyclonedds.xml
ENTRYPOINT ["/usr/local/bin/rosy-entrypoint"]
CMD ["ros2", "run", "rosy_core", "rosy_core"]

FROM runtime-common AS io-runtime

COPY deploy/robot/requirements-io.txt /tmp/requirements-io.txt
RUN apt-get -o Acquire::Retries=5 update \
    && apt-get install --reinstall -y --no-install-recommends \
        python3-pip \
        python3-yaml \
    && apt-get install -y --no-install-recommends \
        ros-jazzy-joint-state-publisher \
        ros-jazzy-robot-state-publisher \
        ros-jazzy-tf-transformations \
        ros-jazzy-xacro \
        ros-jazzy-navigation2 \
        ros-jazzy-nav2-bringup \
    && python3 -m pip install --break-system-packages --no-cache-dir \
        -r /tmp/requirements-io.txt \
    && rm -rf /var/lib/apt/lists/* /tmp/requirements-io.txt

FROM io-runtime AS io-build

WORKDIR /opt/rosy_ws
ARG SLLIDAR_COMMIT=34300099fadfc772965962dec837bf436706188f
RUN git clone https://github.com/Slamtec/sllidar_ros2.git src/sllidar_ros2 \
    && cd src/sllidar_ros2 \
    && git checkout --detach ${SLLIDAR_COMMIT} \
    && rm -rf .git
COPY src/rosy_interfaces ./src/rosy_interfaces
COPY src/rosy_description ./src/rosy_description
COPY src/rosy_bringup ./src/rosy_bringup
COPY src/rosy_navigation ./src/rosy_navigation
RUN mkdir -p src/rosy_description/meshes
RUN set -eo pipefail \
    && source /opt/ros/jazzy/setup.bash \
    && colcon build --merge-install \
        --packages-select sllidar_ros2 rosy_interfaces rosy_description rosy_bringup rosy_navigation \
    && test -d /opt/rosy_ws/install

FROM io-runtime AS io

COPY --from=io-build /opt/rosy_ws/install /opt/rosy_ws/install
COPY deploy/robot/entrypoint.sh /usr/local/bin/rosy-entrypoint
RUN chmod 0755 /usr/local/bin/rosy-entrypoint
ENV HOME=/var/lib/rosy \
    CYCLONEDDS_URI=file:///etc/rosy/cyclonedds.xml
ENTRYPOINT ["/usr/local/bin/rosy-entrypoint"]
CMD ["ros2", "launch", "rosy_bringup", "bringup_robot.launch.py", \
     "cmd_vel_timeout_s:=0.5", "enable_battery:=false"]
