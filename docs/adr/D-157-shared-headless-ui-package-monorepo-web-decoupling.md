## D-157 Shared Headless UI Package (Monorepo Web Decoupling)

**Date:** 2026-09-21
**Status:** Accepted
**Context:** D-999 introduced framework-free state access to avoid duplicating
server-judged evidence logic. Fleet and future dashboards must consume shared
L1 assets without depending on the robot dashboard package.
**Decision:** Install `tokens.css` and `core_ui_logic.js` through the neutral
ament package `web_common`. CORE and Fleet serve only an explicit allowlist
from that package; visual components remain inside each surface.
