## D-160 Games Domain Strict Decoupling (AST Validation)

**Date:** 2026-09-21
**Status:** Accepted
**Context:** The `apps/games` package encapsulates game logic (`field`, `game`, `policy`) and host/infrastructure (`host`, `web`). The core game logic must be highly portable and completely isolated from the robot's physical constraints (`core`, `rclpy`), fleet context (`fleet`), and specific runtime IO dependencies (`cv2`, `httpx`). While this was established as a rule in `apps/games/AGENTS.md`, it lacked automated enforcement.
**Decision:** Implement `test_games_imports_isolation` (an AST validation guard) in `test_module_separation.py`. The `field`, `game`, and `policy` submodules within `apps/games` are now statically prohibited from importing `core`, `fleet`, `rclpy`, `httpx`, or `cv2`. The host logic remains allowed to interact with these as needed.
