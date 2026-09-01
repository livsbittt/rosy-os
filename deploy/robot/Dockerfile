# syntax=docker/dockerfile:1.7
ARG ROS_IMAGE=ros:jazzy-ros-base

FROM ${ROS_IMAGE} AS runtime-common

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROS_LOG_DIR=/tmp/ros-logs

RUN apt-get -o Acquire::Retries=5 update \
    && apt-get install -y --no-install-recommends \
        ros-jazzy-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

COPY src/rosy_bringup/config/cyclonedds_localhost.xml /etc/rosy/cyclonedds.xml

FROM runtime-common AS core-runtime

COPY deploy/robot/requirements-core.txt /tmp/requirements-core.txt
RUN apt-get -o Acquire::Retries=5 update \
    && apt-get install -y --no-install-recommends \
        python3-pip \
        ros-jazzy-nav2-msgs \
    && python3 -m pip install --break-system-packages --no-cache-dir \
        -r /tmp/requirements-core.txt \
    && mkdir -p /var/lib/rosy/.rosy \
    && mkdir -p /host/proc/net /host/etc /host/sys/class/thermal /host/sys/devices/virtual/thermal \
    && chown -R 1000:1000 /var/lib/rosy \
    && rm -rf /var/lib/apt/lists/* /tmp/requirements-core.txt

FROM core-runtime AS core-build

WORKDIR /opt/rosy_ws
COPY src/rosy_interfaces ./src/rosy_interfaces
COPY src/rosy_core ./src/rosy_core
RUN source /opt/ros/jazzy/setup.bash \
    && colcon build --merge-install --packages-up-to rosy_core

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
    && apt-get install -y --no-install-recommends \
        python3-pip \
        ros-jazzy-joint-state-publisher \
        ros-jazzy-robot-state-publisher \
        ros-jazzy-tf-transformations \
        ros-jazzy-xacro \
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
RUN mkdir -p src/rosy_description/meshes
RUN source /opt/ros/jazzy/setup.bash \
    && colcon build --merge-install \
        --packages-select sllidar_ros2 rosy_interfaces rosy_description rosy_bringup

FROM io-runtime AS io

COPY --from=io-build /opt/rosy_ws/install /opt/rosy_ws/install
COPY deploy/robot/entrypoint.sh /usr/local/bin/rosy-entrypoint
RUN chmod 0755 /usr/local/bin/rosy-entrypoint
ENV HOME=/var/lib/rosy \
    CYCLONEDDS_URI=file:///etc/rosy/cyclonedds.xml
ENTRYPOINT ["/usr/local/bin/rosy-entrypoint"]
CMD ["ros2", "launch", "rosy_bringup", "bringup_robot.launch.py", \
     "cmd_vel_timeout_s:=0.5", "enable_battery:=false"]
