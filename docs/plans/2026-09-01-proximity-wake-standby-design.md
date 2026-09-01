# Rosy Proximity Wake and Sensor Standby Design

## Objective

Cut the power the robot burns while parked, and turn the ultrasonic sensor into
a deliberate wake trigger. When a person approaches or touches Rosy, the robot
wakes and shows battery and status information on the LCD, on the LED ring, and
over the API. Standby must never weaken E-Stop, the cmd_vel mux, or the teleop
watchdog.

## Where the power goes

Two continuous consumers dominate an idle Rosy:

- `rosy_sensor_adc` polls five I2C ADC channels at 20 Hz. Each channel costs a
  6 ms write/settle/read round trip, so a full cycle is ~30 ms of bus and CPU
  time, twenty times a second, forever.
- `rosy_emotion` pushes a 240x320 RGB565 frame over SPI at 10 Hz with the LCD
  backlight held at 100% PWM. The backlight is the single largest draw.

Neither can be switched off outright: the ultrasonic channel is the wake
trigger, and the battery channel must keep feeding SAF-005. The answer is duty
cycling, not shutdown.

## Architecture

Policy lives in one ROS-independent module, `rosy_core.power.manager`, next to
the existing safety and navigation managers. Hardware nodes own only the
mapping from a declared mode to their own device behavior.

```
us_sensor/range ─┐
cmd_vel/nav/API ─┼─> PowerManager ─┬─> power/mode (String)      -> rosy_sensor_adc, rosy_emotion
battery/safety  ─┘                 ├─> display/info (JSON)      -> rosy_emotion
                                   ├─> set_led (service client) -> rosy_led
                                   ├─> EventBus                 -> /ws/events, Fleet
                                   └─> StateSnapshot.power      -> REST, dashboard
```

### Power modes

`ACTIVE -> IDLE -> STANDBY`, with any wake source returning directly to
`ACTIVE`.

| Mode | Entered when | ADC rate | LCD |
|---|---|---|---|
| `ACTIVE` | activity, wake, or non-idle robot mode | 20 Hz | animation on, backlight on |
| `IDLE` | no activity for `idle_after_s` | 5 Hz | animation on, backlight dimmed |
| `STANDBY` | no activity for `standby_after_s` | 2 Hz | animation stopped, backlight off |

At 2 Hz the ultrasonic channel still sees an approaching hand inside 500 ms,
which is below the threshold where the delay is noticeable.

### Presence detection

The ultrasonic range is the only wake sensor. Detection is debounced in both
directions so a single stray echo cannot wake the robot and a single dropout
cannot dismiss the info screen.

- `range < near_m` for `detect_samples` consecutive samples -> `NEAR`.
- `range < contact_m` -> `CONTACT`, treated as a touch.
- `range > near_m + hysteresis_m` for `release_samples` samples -> cleared.
- Non-finite ranges, and ranges outside the sensor's own `min_range`/`max_range`,
  are discarded without touching the debounce counters.

`NEAR` or `CONTACT` while `IDLE` or `STANDBY` raises a wake with the matching
reason. Presence is a UI signal only; obstacle avoidance stays with Nav2 and is
not routed through this module.

### Info window

A wake opens an info window of `info_hold_s`. While it is open the robot
publishes a payload carrying battery percent and voltage, robot mode,
navigation state, the worst diagnostics health, and the API address, and it
paints the battery level onto the LED ring. Continued presence extends the
window; its expiry returns the LCD to the emotion animation and lets the idle
timer run again.

## Safety boundary

Standby is a display and sampling policy. It has no authority over motion.

- Any accepted motion command, navigation transition, or robot mode other than
  `IDLE` forces `ACTIVE` before the command is acted on, so the ADC is already
  back at full rate whenever the robot can move.
- E-Stop, the 50 Hz cmd_vel publisher, the teleop watchdog, and SAF-005 battery
  policy run unchanged in every mode.
- A battery warning or critical crossing forces a wake so the fault is visible
  on the robot itself, not only in the API.
- `power.enabled: false` pins `ACTIVE` and restores today's behavior exactly.
- The ADC node keeps its 20 Hz default and only changes rate after a valid
  `power/mode` message, so a `rosy_core` outage cannot leave sensors slow.

## Verification

Pure unit tests with an injected clock cover the mode machine, both debounce
directions, hysteresis, invalid range rejection, rate mapping, wake reasons,
event emission, the forced-active interlocks, and the disabled configuration.
API tests cover the new read and control routes and their role checks. The C++
duty cycle and the LCD backlight path are reviewed against the default-safe
contract above and confirmed on the Raspberry Pi bench, which stays a separate
acceptance gate.
