# Rosy Battery Integrity and Low-Battery Alert Design

## Objective

Make the battery reading on real hardware mean something, and make a low
battery visible to a person who is not standing in front of the robot.

Today neither holds. The state of charge is computed against a pack Rosy does
not have, so on the bench it reads zero forever. The red LED that already
exists is gated behind a 15-second proximity window, so a robot draining itself
overnight in an empty room shows nothing at all. Below both of those sits a
third problem: nothing stops the pack from running down to the protection
board's cutoff, and that cutoff is an unannounced power cut to a Raspberry Pi
with a mounted filesystem.

This document fixes the measurement, gives the alert its own display authority,
and adds one deliberate escalation below `critical` that shuts the host down
while there is still charge to do it cleanly. It does not add charging, docking,
or return-to-dock; those are the subject of the docking station design and
depend on this work landing first.

## The measurement is wrong

`rosy_sensor_adc` reads the pack through a divider and converts it in one line
([`main_node.cpp:146`](../../src/rosy_sensor_adc/src/main_node.cpp)):

```cpp
batt_result.voltage = (adc_result[CH_BATTERY] / 4096.0) * 4.096 / (13.0 / 28.0);
```

The `13.0 / 28.0` divider puts a hard ceiling on what the channel can express:
`4.096 * 28 / 13` = **8.82 V**. Nothing above that is representable, whatever
the pack actually is.

Three other facts in the tree agree on what the pack is. The node hardcodes
`POWER_SUPPLY_TECHNOLOGY_LION` and `design_capacity = 5.0` Ah. `bringup.py`
warns below **6.8 V** ([`bringup.py:46`](../../src/rosy_bringup/rosy_bringup/bringup.py)).
A 2S lithium-ion pack is 8.4 V full and 7.4 V nominal, which sits inside the
8.82 V ceiling with headroom and puts 6.8 V exactly where a low warning belongs.
The hardware is 2S, and this has been confirmed against the physical pack.

`rosy_core` disagrees with all of it
([`rosy_default.yaml`](../../src/rosy_core/config/rosy_default.yaml)):

```yaml
battery_full_voltage: 12.6      # 3S
battery_empty_voltage: 10.0
```

and maps voltage to percent linearly against those constants
([`ros_bridge.py:147-148`](../../src/rosy_core/rosy_core/bridge/ros_bridge.py)):

```python
span = max(self._battery_full - self._battery_empty, 1e-6)
percent = max(0.0, min(100.0, (voltage - self._battery_empty) / span * 100.0))
```

A 2S pack cannot reach 10.0 V, so `voltage - self._battery_empty` is always
negative and `percent` is always clamped to **0.0**. Every consequence follows
from that single number:

- `SafetyManager.on_battery_percent(0.0)` returns `critical` on the first
  sample after boot.
- `_apply_voltage` then calls `nav.home()` or trips E-Stop
  ([`ros_bridge.py:151-158`](../../src/rosy_core/rosy_core/bridge/ros_bridge.py)).
- `PowerManager.on_battery_alert("critical")` wakes the robot and keeps waking
  it.
- `/metrics` reports `rosy_battery_percent 0` forever.

This is the reason the fix has to land before any docking work. Return-to-dock
is triggered by state of charge, and there is currently no state of charge to
trigger on.

### Linear interpolation is the wrong curve

Fixing the two constants to 8.4 and 6.4 removes the clamp but leaves a second,
quieter error. Lithium-ion does not discharge linearly. A 2S cell pair sits
between roughly 7.8 V and 7.5 V for well over half its usable capacity, then
falls off sharply. Interpolated linearly against an 8.4/6.4 span, 7.5 V reports
**55%** when the pack is closer to a third full, and the robot then falls from
"half full" to the critical threshold in a few minutes.

Thresholds expressed in percent are only meaningful if percent tracks remaining
energy. SAF-005 is written in percent (20% / 10%), the operator dashboard shows
percent, and the docking policy will budget against percent. So the mapping
becomes a piecewise-linear open-circuit-voltage table rather than a two-point
span:

| Pack V | 8.40 | 8.12 | 7.96 | 7.84 | 7.74 | 7.64 | 7.58 | 7.50 | 7.42 | 7.32 | 6.60 | 6.40 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| % | 100 | 90 | 80 | 70 | 60 | 50 | 40 | 30 | 20 | 10 | 5 | 0 |

The table is configuration, not code, so a different pack is a config change.
The existing `battery_full_voltage` / `battery_empty_voltage` keys stay
supported as the fallback when no curve is given, which keeps the simulator and
any 3S variant working unchanged.

The table is an open-circuit curve and the pack is rarely at rest, which is the
subject of the next section.

## Nothing filters the reading

The path from an ADC sample to E-Stop has no filter, no debounce, and no
hysteresis anywhere along it. `_on_battery` calls `_apply_voltage`, which calls
`on_battery_percent`, which can return `STOP`, which trips E-Stop — all inside
one callback on one sample
([`ros_bridge.py:140-158`](../../src/rosy_core/rosy_core/bridge/ros_bridge.py)).

That matters because the robot pulls its own supply down. Two DYNAMIXEL servos
accelerating from rest sag a small 2S pack by several hundred millivolts for the
duration of the transient. On the OCV table above, a 400 mV sag near 7.6 V moves
the reported charge by roughly 30 points. A robot at a genuine 45% can therefore
read below the 10% critical threshold during a single hard start, and trip a
policy that stops it or sends it home.

This is a live defect independent of the 3S constants, and correcting the curve
makes it *more* reachable, not less, because percent will no longer be pinned at
zero.

The fix is the pattern `PresenceDetector` already uses for the ultrasonic
channel: filter the signal, then require agreement across consecutive samples
before changing state, with different thresholds in each direction.

- A first-order low-pass on voltage with a time constant of a few seconds. The
  battery is a slow signal; nothing is lost by smoothing it and the motor
  transient is rejected.
- Entering an alert level requires `enter_samples` consecutive filtered samples
  past the threshold. Leaving it requires `exit_samples` past the threshold plus
  a hysteresis margin. A pack hovering on 20% does not emit paired
  `battery.low` events forever.
- The escalation to shutdown additionally requires the level to be held for a
  configured dwell in seconds, not just in samples, so no filter tuning can make
  it fire on a transient.

Note what this does *not* fix. Without current sensing there is no way to
compensate the sag, only to reject it. A robot that drives continuously will
read lower than one at rest, and the reported charge is an estimate with a real
error bar. That is acceptable for a threshold policy and is not acceptable as a
fuel gauge; the API and dashboard should keep presenting it as an estimate.

## The alert is invisible when it matters

The LED already turns red below 30%
([`ros_bridge.py:58`](../../src/rosy_core/rosy_core/bridge/ros_bridge.py)):

```python
_LED_STEPS = ((60.0, 0, 60, 0), (30.0, 60, 40, 0), (0.0, 60, 0, 0))
```

but it is only ever called from inside the proximity information window
([`ros_bridge.py:266-270`](../../src/rosy_core/rosy_core/bridge/ros_bridge.py)):

```python
if status.info_visible:
    if not self._info_was_visible:
        self._set_led_gauge(self._svc.state.snapshot().battery.percent)
elif self._info_was_visible:
    self._clear_led()
```

`info_visible` is true for `info_hold_s` (default 15) seconds after a wake. So
the battery colour is shown to somebody who has already walked up to the robot
and is looking at it. The case the requirement is actually about — nobody is
near, the robot is parked, the pack is draining — clears the LED and leaves it
cleared.

The LED has one caller and no notion of who owns it. Adding a second caller
without an owner produces a race between the gauge and the alert.

### Display authority

`BatteryMonitor` declares an alert intent and `ros_bridge` reconciles the
hardware to it, which is the same shape as `power/mode` and the PWR-005 LiDAR
intent — the policy layer stays ROS-independent and never calls a service.

Arbitration is a fixed priority, highest first:

| Priority | Owner | Pattern |
|---|---|---|
| 1 | `deep` | red, 2 Hz blink |
| 2 | `critical` | red, 1 Hz blink |
| 3 | `warning` | amber, solid, reduced brightness |
| 4 | info window | existing `_LED_STEPS` gauge |
| 5 | nothing | off |

Blinking rather than holding solid is deliberate on three counts: a changing
light is far more noticeable in peripheral vision than a static one, a 50% duty
cycle halves the draw of the thing complaining about draw, and it distinguishes
an active alert from the steady gauge colour, which is red below 30% too.

The alert must survive `STANDBY`, which is the entire point — the robot is
parked and unattended precisely when this matters. `_tick_power` already runs at
5 Hz in every power mode, which is enough to drive a 2 Hz blink, so the alert
needs no timer of its own and no exception to the power policy.

The alert deliberately does not extend the information window or force `ACTIVE`.
`PowerManager.on_battery_alert` already wakes the robot when a threshold is
crossed ([`manager.py:294`](../../src/rosy_core/rosy_core/power/manager.py)); a
persistent alert that also pinned the mode to `ACTIVE` would hold the LCD
backlight and the full ADC rate on for the whole drain, which is the opposite of
what a low battery calls for. The LED alert is a display layer with no authority
over power mode, exactly as the power manager has no authority over motion.

## Deep discharge

Below `critical` the pack is heading for the protection board's cutoff. That
cutoff is real and it will save the cells, but from the Raspberry Pi's point of
view it is an unannounced power removal with the root filesystem mounted and
Docker writing. The risk being managed here is filesystem corruption, not cell
damage — the protection board already has the cells covered.

So one level is added below `critical`, at 5%: stop the motors, hold the alert,
wait out a grace period, then shut the host down cleanly.

Stopping the motors first is not incidental. Motion is the dominant draw, and
removing it both extends the remaining time and lets the sagged voltage recover
toward the resting curve, which makes the reading the shutdown decision is based
on more trustworthy than the one that triggered it.

### Why a sentinel and not the Host Agent

`rosy-core` cannot halt the host. It runs as uid 1000 with no privileged
capability and read-only `/proc` and `/sys` bind mounts
([`compose.yaml:36-63`](../../deploy/robot/compose.yaml)). ADR D-22 put host
privilege behind a separate minimal process for good reason and this design does
not relitigate it.

The Host Agent is that process and it is further along than
[its contract document](../reference/rosy-host-agent-contract.md) claims — the
status line still reads `implementation pending (WP-4)` but both
[`host_agent.py`](../../deploy/release/host_agent.py) and
[`host_agent_server.py`](../../deploy/release/host_agent_server.py) exist and are
covered by [`test/test_host_agent.py`](../../test/test_host_agent.py). That
document is stale and should be corrected.

It is still the wrong vehicle here, for three reasons that compound:

- No systemd unit starts it. Neither `rosy-runtime.service` nor `install-pi.sh`
  references it, so on a real Pi the socket does not exist.
- No client connects to it. `rosy_core` contains no reference to
  `/run/rosy/host-agent.sock` at all.
- Its command set has `system.reboot` and no shutdown
  ([`host_agent.py:80`](../../deploy/release/host_agent.py)), and every
  privileged command is specified as `administrator` role with confirmation
  required.

That last point is the disqualifying one. A battery policy fires with nobody
present; there is no administrator to authenticate and no operator to confirm.
Routing it through the Host Agent means adding an unattended, unconfirmed
execution path to the process whose entire justification is that it refuses
exactly that. The security model would be weakened to carry one message.

The sentinel inverts the direction and avoids the question. `rosy-core` writes a
file stating an observation; a host-side unit reads it, applies its own policy,
and decides. There is no command, no socket, no authentication, and no
capability CORE gains — a compromised CORE can assert "the battery is low" and
the worst outcome is a shutdown, which is the safe direction. This is narrower
than the Host Agent, not a duplicate of it.

Wiring the Host Agent into the deployment remains necessary work. It is not this
work.

### Sentinel contract

CORE writes `${ROSY_DATA_PATH}/battery-shutdown-request.json` — already a
read-write bind mount at `/var/lib/rosy`
([`compose.yaml`](../../deploy/robot/compose.yaml)), so no new mount is needed:

```json
{
  "requested_at": "2026-09-02T04:31:07Z",
  "reason": "battery_deep_discharge",
  "percent": 4.6,
  "voltage": 6.58,
  "grace_seconds": 120
}
```

Written atomically (temp file plus rename) so the host never reads a partial
document. Removed by CORE if the level recovers, which is what makes charging
mid-grace cancel the shutdown without any dedicated signalling.

`rosy-lowbatt-shutdown.service`, a host unit driven by a `systemd.path` watch on
that file, re-reads it after the grace period and halts only if it is still
present and still recent. It applies its own freshness bound rather than
trusting `requested_at`, so a stale file surviving an unclean shutdown cannot
halt the next boot. `/var/lib/rosy` is persistent, so this guard is required,
not optional.

The unit is the only new privileged component and it takes no parameters,
accepts no connections, and can do exactly one thing.

### This needs an ADR

[D-25](../reference/ROSY%20ADR%20Log.md) records that the power ladder ends at
`STANDBY` and that Pi 5 `halt` is **not adopted**. This design halts the Pi.

The distinction is real — D-25 rejected `halt` as a power-saving rung below
`STANDBY`, reachable from an idle timer, and that document itself says such a
state "must never be reachable from the same idle timer". A battery safety
escalation is a different trigger with a different purpose and no wake
expectation. But D-25 states plainly that `halt` is not adopted, and a design
that halts the machine cannot rest on a reading of its rationale. A new decision
records the exception and its interlocks explicitly, and D-25 gains a pointer to
it.

The interlocks the ADR fixes: reachable only from the battery policy, never from
a dwell timer; requires the deep level held for a dwell in seconds; cancelled by
recovery; and never entered while the robot is in a non-`IDLE` mode without the
motors having been stopped first.

## Design summary

A new ROS-independent `rosy_core.power.battery` module owns the whole chain:
filter, OCV mapping, level machine with hysteresis, LED intent, and the shutdown
request. It takes an injected clock and is tested without ROS, matching
`PowerManager`.

`ros_bridge` keeps its existing role of feeding it samples and reconciling
hardware to its declared intent. `SafetyManager` keeps ownership of SAF-005
thresholds and events; the new module feeds it filtered percent instead of raw,
and adds the `deep` level beneath.

```
batt_state / battery/voltage
        │
        ▼
  BatteryMonitor ──► percent (filtered) ──► SafetyManager  (SAF-005, unchanged)
        │                                          │
        ├──► led_alert intent ──► ros_bridge ──► set_led
        ├──► wake on level change ──────────────► PowerManager   (existing hook)
        └──► shutdown request ──► sentinel file ──► host unit ──► halt
```

Configuration, all additive under the existing `safety:` block, with the current
two-point keys retained as fallback:

```yaml
safety:
  battery_warning_percent: 20        # SAF-005, unchanged
  battery_critical_percent: 10       # SAF-005, unchanged
  battery_critical_policy: RETURN_HOME
  battery_deep_percent: 5            # new — motors off, then shutdown
  battery_deep_dwell_s: 60           # new — level must hold this long
  battery_shutdown_grace_s: 120      # new — written into the sentinel
  battery_filter_tau_s: 5.0          # new — low-pass time constant
  battery_enter_samples: 3           # new
  battery_exit_samples: 5            # new
  battery_hysteresis_percent: 3.0    # new
  battery_curve:                     # new — 2S Li-ion OCV, pack volts
    - [8.40, 100]
    - [8.12, 90]
    - [7.96, 80]
    - [7.84, 70]
    - [7.74, 60]
    - [7.64, 50]
    - [7.58, 40]
    - [7.50, 30]
    - [7.42, 20]
    - [7.32, 10]
    - [6.60, 5]
    - [6.40, 0]
  battery_full_voltage: 8.4          # corrected from 12.6 — fallback only
  battery_empty_voltage: 6.4         # corrected from 10.0 — fallback only
```

`bringup.py`'s standalone 6.8 V constant stays where it is. It is a log warning
in a node that runs without `rosy_core`, and 6.8 V is a sane 2S warning point.
Making it read core configuration would couple the two packages for no benefit.

## Non-goals

**Charging detection.** `batt_state` reports `current`, `temperature`,
`percentage` as NaN and `power_supply_status` as hardcoded `UNKNOWN`
([`main_node.cpp:147-153`](../../src/rosy_sensor_adc/src/main_node.cpp)). There
is no signal to detect charging with, and manufacturing one from a rising
voltage trend is unreliable enough to be worse than nothing. This is the docking
design's problem and the reason that design proposes an instrumented dock.

**Coulomb counting.** No current sensor, so no integration. Voltage plus a
curve is the ceiling of what this hardware supports.

**Load compensation.** Requires current. Rejected transients are the best
available substitute.

**Return-to-dock.** There is no dock. SAF-005's existing `RETURN_HOME` and
`STOP` actions are untouched by this work.

## Verification

The policy module is ROS-independent with an injected clock, so the whole level
machine, filter, hysteresis, and dwell are exercised in `pytest` by advancing
time directly, as `test_power.py` does today.

The properties that must hold:

- A 2S pack at 8.4 V reports ~100%, at 7.4 V reports a plausible mid-range, and
  at 6.4 V reports 0 — the regression that motivated this work.
- A single-sample sag from 7.8 V to 7.3 V changes no level.
- A sustained decline crosses `warning`, `critical`, and `deep` once each, in
  order, with no duplicate events.
- A pack oscillating on a threshold emits one event, not a stream.
- `deep` held past the dwell writes the sentinel; recovery before the dwell
  writes nothing; recovery after it removes the file.
- The LED intent follows the priority table, and the info-window gauge never
  overrides an active alert.
- The sentinel is written atomically and is never observable as partial content.

On hardware, the acceptance checklist gains a bench item: charge the pack, read
the reported percent against a multimeter at several points down the discharge,
and confirm the shutdown fires and the host actually halts.
