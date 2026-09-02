<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_emotion (Python package)

## Purpose

LCD node, GIF playback, and ROS-free info-card drawing.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `rosy_emotion.py` | `RosyEmotion` node; `set_emotion` → GIF |
| `emotion_server.py` | Alternate/entry service wrapper |
| `rosy_lcd.py` | Hardware LCD helper |
| `info_screen.py` | PIL renderer for `display/info` JSON (320×240) |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

Known emotions: hello, basic, angry, bored, fun, happy, interest, sad. Unknown names should fail closed.

### Testing Requirements

`../test/test_info_screen.py`

### Common Patterns

GIF play on a thread so the service callback does not block forever.

## Dependencies

### Internal

- `../emotion/*.gif`
- `rosy_interfaces/Emotion`

### External

- PIL, hardware LCD

<!-- MANUAL: -->
