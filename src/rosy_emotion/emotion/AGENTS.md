<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-14 | Updated: 2026-09-14 -->

# emotion

## Purpose

LCD emotion GIFs installed to the `rosy_emotion` share directory. Looked up at runtime via `get_package_share_directory('rosy_emotion')/emotion`.

## Key Files

| File | Description |
|------|-------------|
| `hello.gif` | Greeting |
| `basic.gif` | Idle / default |
| `angry.gif` | Angry |
| `bored.gif` | Bored |
| `fun.gif` | Fun |
| `happy.gif` | Happy |
| `interest.gif` | Interest |
| `sad.gif` | Sad |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Filenames are the `set_emotion` names. Renaming a GIF without updating the service contract breaks the LCD.
- Info-screen cards are drawn in PIL (`../rosy_emotion/info_screen.py`), not as GIFs here.

### Testing Requirements

None. Binary assets.

### Common Patterns

One GIF per named emotion. Share-dir install via `setup.py`.

## Dependencies

### Internal

- `../rosy_emotion/` LCD / emotion server

### External

None.

<!-- MANUAL: -->
