# rosy_games

Laptop game host (D-90). CORE does not import this package. Final `cmd_vel` stays in CORE.

`field` / `game` / `policy` are ROS-free and must not import `cv2`, `rclpy`, `rosy_core`, or `rosy_fleet`. OpenCV belongs only in a later `host` observation adapter.
