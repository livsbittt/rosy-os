<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# srv

## Purpose

rosidl service definitions for on-robot UI/hardware.

## Key Files

| File | Description |
|------|-------------|
| `Emotion.srv` | `string emotion` → `string response` |
| `SetLed.srv` | LED command + RGB + pixel list |
| `SetBrightness.srv` | Brightness set |
| `SetLamp.srv` | Lamp set |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

Changing a `.srv` is a break for every C++/Python client. Rebuild `rosy_interfaces` first.

### Testing Requirements

Compile.

### Common Patterns

Plain rosidl `.srv` files.

## Dependencies

### Internal

- Generated into `rosy_interfaces.srv`

### External

- rosidl, std_msgs

<!-- MANUAL: -->
