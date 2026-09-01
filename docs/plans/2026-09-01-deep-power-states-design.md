# Rosy Deep Power States Design

## Objective

Decide how far Rosy can push power saving below the `ACTIVE/IDLE/STANDBY` duty
cycle defined in the [proximity wake and sensor standby
design](2026-09-01-proximity-wake-standby-design.md), and answer a specific
question: can Rosy itself implement or drive a Raspberry Pi hibernate or sleep
state?

The short answer is no, and the reason is worth recording because it is a
platform limitation, not an implementation gap. The useful power savings sit
somewhere else entirely, and this document routes the work there.

## Platform findings

### Raspberry Pi 5 has no sleep and no hibernate

As of mid-2026 the Raspberry Pi 5 supports neither suspend-to-RAM (`mem`, ACPI
S3 equivalent) nor suspend-to-disk (`disk`, hibernate). The BCM2712 has the
hardware domain for it — in suspend the whole application processor apart from
a small always-on block powers down, and a power-down state machine can resume
on always-on GPIO — but the firmware path is blocked on Broadcom SDRAM PHY
self-refresh sequences that have not shipped. Raspberry Pi engineers were still
answering "turn the device off and reboot it, there is no low power sleep" in
July 2026.

The only deep state that actually exists is `halt` with the PMIC placed in
STANDBY:

```bash
sudo rpi-eeprom-config --edit     # POWER_OFF_ON_HALT=1, WAKE_ON_GPIO=0
echo +600 | sudo tee /sys/class/rtc/rtc0/wakealarm
sudo halt
```

This draws approximately 3 mA. `WAKE_ON_GPIO` is not relevant on Pi 5 — the
dedicated power button replaces the GPIO3 wake of earlier models — so the only
wake sources are the power button and the on-board RTC alarm.

| State | Supported on Pi 5 | Draw | Wake sources |
|---|---|---|---|
| suspend-to-RAM (`mem`) | no | — | — |
| hibernate (`disk`) | no | — | — |
| `halt` + `POWER_OFF_ON_HALT=1` | yes | ~3 mA | power button, RTC alarm |
| idle, powered on | — | ~2.7 W | — |

The consequence for design is that the Pi 5 offers no middle ground. It is
either fully powered at roughly 2.7 W or effectively off at 3 mA. Every
intermediate saving must come from the peripherals, not from the SoC.

### Why the deep state does not fit proximity wake

Even if the 3 mA state were reachable on demand, four properties of the
proximity wake design rule it out as the next step below `STANDBY`.

The wake sensor dies with the host. Proximity wake is triggered by the
ultrasonic channel sampled by `rosy_sensor_adc`. A halted Pi samples nothing, so
the only surviving wake sources are a scheduled RTC alarm and a physical button
press. The defining feature of the current design — a person walks up and Rosy
notices — cannot exist in this state without an always-on sidecar.

Recovery is a boot, not a resume. Returning from `halt` means restarting the
Docker Compose stack and the ROS 2 Jazzy graph. That is tens of seconds against
a design target of reacting to an approaching hand inside 500 ms.

It breaks the safety boundary the standby design deliberately drew. Standby is
documented as a display and sampling policy with no authority over motion:
E-Stop, the 50 Hz `cmd_vel` publisher, the teleop watchdog and the SAF-005
battery policy run unchanged in every mode. A `halt` stops all of them. Whatever
that state is, it is not another rung on the same ladder, and it must never be
reachable from the same idle timer.

State is lost. DDS discovery, odometry accumulation, the SLAM session and any
in-flight navigation goal do not survive.

### Where the power actually goes

Ranked by what a parked Rosy is burning, the SoC is not the top of the list.
The 6.8 V low-battery threshold in
[`bringup.py`](../../src/rosy_bringup/rosy_bringup/bringup.py) indicates a 2S
pack, and against that budget the order is:

1. **DYNAMIXEL holding torque.** Continuous while parked. Largest remaining
   saving, and the only one that touches the motion safety boundary.
2. **RPLIDAR C1 motor.** Spins continuously. `sllidar_ros2` already exposes
   `start_motor` and `stop_motor` services, so this is reachable today with no
   driver changes. The driver's own auto-standby only stops the motor when the
   `scan` topic has no subscribers, which never happens while Nav2 or SLAM is
   up, so an explicit service call is required.
3. **LCD backlight.** Already identified as the single largest display draw and
   already handled by `STANDBY`.
4. **Pi 5 SoC at ~2.7 W.** Not reducible short of `halt`.

This ranking is the whole argument: the next meaningful step is the LiDAR
motor, not the host power state.

## Design

### Power tiers

`ACTIVE/IDLE/STANDBY` keep their existing meaning and their existing single
owner, `rosy_core.power.manager`. The LiDAR motor becomes one more device
behavior mapped from `STANDBY`, alongside the ADC rate and the LCD backlight.

| Tier | Mechanism | Status |
|---|---|---|
| `ACTIVE` | full ADC rate, LCD on | implemented |
| `IDLE` | reduced ADC rate, LCD dimmed | implemented |
| `STANDBY` | lowest ADC rate, LCD off | implemented |
| `STANDBY` + LiDAR stop | `stop_motor` / `start_motor` service | this document |
| motor torque off | DYNAMIXEL torque disable | **not adopted** — see below |
| deep halt | `halt` + `POWER_OFF_ON_HALT` | **not adopted** — see below |

### LiDAR motor policy

The policy layer stays ROS-independent and declares intent only. `PowerManager`
computes a desired spin state and the bridge reconciles the hardware to it, the
same shape as the existing `power/mode` and `set_led` paths.

```
PowerManager (policy, no ROS)          ros_bridge (reconciler)
  mode == STANDBY and lidar.standby_stop
      -> lidar_spinning = False   ──────>  stop_motor
  any wake / activity / non-idle mode
      -> lidar_spinning = True    ──────>  start_motor
```

A restart is not instantaneous, so the manager also tracks a spin-up window.
`lidar_ready` is false from the moment the spin request is issued until
`spinup_s` has elapsed, and it is published in `PowerStatus` so the dashboard,
the info screen and any future navigation gate can see that scans are not yet
trustworthy. The manager does not itself block anything on this signal; it
reports it.

Configuration lives under the existing `power` block:

```yaml
power:
  lidar:
    standby_stop: false     # STANDBY에서 LiDAR 모터 정지 — 벤치 검증 후 활성화
    spinup_s: 2.0           # start_motor 후 스캔을 신뢰하기까지의 시간
```

`standby_stop` ships **disabled**. The interlocks make this safe on paper —
`STANDBY` is only reachable when the robot mode is `IDLE`, and any accepted
motion command, navigation transition or non-idle mode forces `ACTIVE` before
the command is acted on, which reissues `start_motor` — but what a stopped scan
does to a running Nav2 lifecycle over a five minute idle window is an
integration behavior that has to be observed on the robot, not reasoned about.
The code path is complete and unit tested; enabling it is a configuration flip
behind the Raspberry Pi bench acceptance gate, consistent with how the rest of
the hardware-facing power work is staged.

LiDAR is a navigation sensor here, not a safety sensor — the standby design
explicitly leaves obstacle avoidance with Nav2 and routes presence only to the
UI — so stopping the motor removes no safety function that exists today. It
does remove navigation input, which is why the wake path restores it before any
motion is acted on.

Service calls follow the LED precedent: non-blocking `call_async`, skipped
silently when the service is not ready, never allowed to stall the 5 Hz power
timer. A missing LiDAR driver degrades to today's behavior.

### Deliberately not adopted

**Motor torque off in STANDBY.** This is the largest remaining saving and it is
also the first proposal that crosses the line the standby design drew: power
policy would be commanding actuator state. A robot parked on a slope rolls when
torque is released. This needs a hazard assessment, a defined re-engage
sequence, and an ADR of its own before any code.

**Deep halt as a power tier.** Not reachable from the idle timer, for the four
reasons above. It remains defensible as an explicitly operator-requested
storage or transport mode — `halt` with an RTC wake alarm, entered through a
deliberate API call with confirmation, never automatically — but that is a
different feature with a different contract, and it forfeits proximity wake.

**Waiting for Pi 5 sleep support.** Not a plan. If suspend-to-RAM ships it
still cannot sample the ultrasonic sensor, so it would face the same wake
source problem.

### Portability

Other controllers are not equally handicapped. Jetson supports SC7 suspend and
x86 controllers support S3/S0ix and hibernate properly; the Pi 5 is the
outlier. If Rosy ever needs real host suspend, the shape that fits the existing
architecture is a `PlatformPowerBackend` that declares its own capabilities —
`suspend_supported`, `hibernate_supported`, `deep_halt_supported` — in the same
spirit as [`capability.py`](../../src/rosy_core/rosy_core/capability.py), with
the Pi 5 backend reporting the first two as unsupported. `PowerManager` stays
the policy owner and never learns platform specifics. This is recorded as the
intended direction, not scheduled work.

Preserving proximity wake across a host power-down needs hardware regardless of
platform: an always-on microcontroller holding the ultrasonic sensor and
driving the Pi power button or `GLOBAL_EN`. That is a board change, not a
software task.

## Verification

Unit tests with the injected clock cover the desired spin state per mode, the
transition into and out of `STANDBY`, restoration on every wake source,
`lidar_ready` across the spin-up window, and `standby_stop: false` preserving
current behavior exactly. The bridge reconciliation is reviewed against the
skip-when-unavailable contract.

Bench measurements remain a separate acceptance gate and are the only source of
truth for the numbers this design is argued from: per-mode battery current with
the motors, LiDAR and LCD isolated; `cat /sys/power/state` on the actual image;
observed Nav2 behavior across a stopped-scan interval; and, if the storage mode
is ever built, the real `halt`-to-ROS-ready recovery time.

## Sources

- [RPi5 Bookworm Desktop: How to hibernate and sleep?](https://forums.raspberrypi.com/viewtopic.php?t=361542)
- [pi5 suspend to ram](https://forums.raspberrypi.com/viewtopic.php?t=357346)
- [raspberrypi/firmware issue #1635 — hibernation and sleep remain unsupported](https://github.com/raspberrypi/firmware/issues/1635)
- [Raspberry Pi documentation — RTC and wake alarm](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/raspberry-pi/rtc.adoc)
- [Raspberry Pi documentation — EEPROM bootloader configuration](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/raspberry-pi/eeprom-bootloader.adoc)
- [Tom's Hardware — Raspberry Pi 5 review, idle power](https://www.tomshardware.com/reviews/raspberry-pi-5)
- [Slamtec/sllidar_ros2 — start_motor / stop_motor services](https://github.com/Slamtec/sllidar_ros2)
