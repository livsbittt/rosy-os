---
title: A safety orchestrator re-checks after every await, and lets every liveness signal decay
date: 2026-09-09
category: design-patterns
module: rosy_fleet
problem_type: design_pattern
component: service_layer
severity: critical
applies_when:
  - "an asyncio (or any cooperative) orchestrator holds a safety state machine and also awaits remote calls"
  - "a watcher task can change state while an operator-initiated coroutine is between awaits"
  - "a component reports a rate, age, or health that is derived from the last N samples"
  - "a transport layer collapses 'the peer refused us' and 'the peer closed' into one quiet return"
  - "an operator command pauses or stops a stream and something else is expected to un-pause it"
symptoms:
  - "a trigger that lands during reform() or resume() is recorded and then overwritten by the unconditional tail of that coroutine"
  - "a relay reports 10 Hz for a leader that was powered off ten minutes ago"
  - "a formation halts with every follower holding while the session and the console say RUNNING"
  - "a bad token makes a socket retry forever with nothing in any status field saying why"
root_cause: async_timing
resolution_type: code_fix
related_components:
  - testing_framework
  - observability
tags:
  - asyncio
  - state-machine
  - safety-invariant
  - multi-await-window
  - liveness-decay
  - fail-loud
  - code-review
  - swarm
---

# A safety orchestrator re-checks after every await, and lets every liveness signal decay

> **Track: knowledge.** Seven review rounds on the swarm formation slice (branch
> `feat/swarm-formation-slice`, 2026-09-08 → 09) each found a new instance of the same
> two shapes in `src/rosy_fleet/rosy_fleet/swarm/`. None was visible from the code that
> introduced it; every one was found by a reviewer probing the code with the test fakes.
> The commits are branch SHAs and the repo has no remote, so there are no PR numbers;
> the branch is not merged to `main` as of writing.

## Context

`rosy_fleet` is the first Fleet-side orchestrator in this repo: a `FormationSession`
that arms N followers, pauses and resumes a reference-stream `Relay`, and watches every
robot's event socket for FOR-004 triggers (stuck, failed, e-stop, aborted). Its whole
purpose is one safety promise — *when one robot fails, the formation stops, and the
operator can see why* — and it is written as asyncio coroutines that await HTTP and
WebSocket calls to each robot.

The first implementation passed its 100+ unit tests. Reviewers then found, in order:

1. `reform()` awaited N `follow()` calls, then unconditionally resumed the relay and set
   `RUNNING`. A `safety.estop` landing during those awaits set `HOLDING` — and was erased.
   Under the ABORT policy the same window re-armed robots that had just been cancelled,
   onto a relay that had been stopped.
2. The fix added a generation counter to `reform()`. The next review found the identical
   hole in `resume()`, which had *become* multi-await when it gained a per-follower
   `swarm_state()` verification — and wrote `RUNNING` unconditionally at the end.
3. The fix for that moved pre-flight planning before `relay.pause()`. The next review found
   the new pre-flight window itself (`_plan`, N `state()` awaits) had the same shape.
4. Separately: `_Rate.hz()` divided sample count by the span of the last 20 stamps and
   never consulted the clock. A dead leader read 10 Hz forever. The relay correctly
   refused to synthesize *frames* and then synthesized a healthy *rate* — and the slice's
   acceptance metric (`relay_tx_hz ≥ 10`) could not fail.
5. Separately: the transport swallowed every socket end as a quiet return, so a robot
   that *refused* the socket (bad token, missing capability) looked like a closed one and
   the relay retried it forever with no reason anywhere. That was fixed for the leader;
   the next review found followers still nameless; the one after found the leader still
   nameless for every failure that was not an explicit refusal.
6. Separately: `reform()` paused the relay *before* validating the new spec. An invalid
   spec raised a `ValueError` subclass that slipped past `except SessionError`, leaving
   `RUNNING` with the relay paused and `resume()` a no-op — every follower held, the
   console said RUNNING.

## Guidance

**1. Treat the tail of every coroutine that awaits as a decision, not a conclusion.**
Anything that awaits between reading state and writing state must, after its last await,
re-read the state it is about to overwrite. The pattern that survived review:

```python
seq = self._policy_seq          # bumped by every watcher-driven transition
carried = len(self.pending_triggers)
... await ... await ...          # the window
if self.state is STOPPED:        # someone aborted while we worked
    undo what this coroutine armed; raise
if self._policy_seq != seq:      # someone HELD while we worked
    keep the new arming, stay HOLDING with *their* reason; do not resume
relay.resume(); self.state = RUNNING   # only now, and synchronously
```

The last two lines must contain no `await`. If a later change adds one (as `resume()`'s
verification did), the re-check moves below it. Review question to ask of every edited
coroutine: *"what does this line assume that a watcher could have changed since the
previous `await`?"*

**2. Decide everything refusable before touching the thing that needs un-pausing.**
Spec validation, map consistency, leader mode, slot assignment — all of it can be
computed from already-fetched state as a pure function (`src/rosy_fleet/rosy_fleet/swarm/arming.py`). Do it before
`relay.pause()`. The invariant reads: *the relay is only paused by something that also
sets a state that can un-pause it.* A refusal that touched no robot leaves the session
exactly as it was — RUNNING stays RUNNING with the relay never paused; HOLDING stays
HOLDING. Only a failure *after* the first robot was re-armed may abort.

**3. Every exception a caller is told to catch must be the type they are told to catch.**
`FormationError(ValueError)` escaping `except SessionError` is how (6) happened. Wrap at
the boundary (`InvalidFormation(SessionError)`); do not rely on callers knowing the
transitive hierarchy of a helper module.

**4. A liveness metric that cannot go down cannot fail an acceptance test.**
Any rate, age, or "connected" flag derived from past samples must consult the clock and
decay to its failure value when samples stop. Pin it with a test that advances a fake
clock past the staleness horizon and asserts zero. Then look at every KPI in the plan that
reads that metric and ask whether it could ever have failed before the fix.

**5. "Refused" and "closed" are different words; keep them different all the way up.**
A transport that returns quietly on every socket end erases the one diagnostic the
operator needs. Raise a typed error for a refusal (here `RobotApiError(code="WS_403")`),
end quietly on an ordinary close, and have the consumer record *every* failure reason in
a status field the console prints — for the leader and for every follower, for typed
refusals and for plain `ConnectionRefusedError` alike. "0 Hz forever" must carry a reason.
Check the wire, not the spec: `rosy_core` closes 4401/4403 *before* `accept()`, so uvicorn
sends an HTTP 403 handshake and the finer code is gone by the time the client sees it.

**6. Apply a fix to every lane it applies to, in the same commit.**
Three of the seven rounds found a fix applied to the leader but not the followers, or to
`RobotApiError` but not to other exceptions, or to `reform()` but not to `resume()`. When
a review names a class of defect, grep for the shape before closing it.

## Why This Matters

These are not bugs a unit test on the happy path finds. Every one passed the suite that
existed when it was written, because the suite drove one coroutine at a time. They were
found only by reviewers who wrote a five-line probe with the test fakes — gating one
robot's `follow()` on an `asyncio.Event`, pushing an event on another robot's queue,
releasing the gate — and by a reviewer who advanced a fake clock 600 s and read the rate.
The cost of each fix was small; the cost of shipping any one of them would have been a
formation that looked healthy while it was not, which is the single failure the design
exists to prevent.

## When to Apply

- Writing or reviewing any coroutine in an orchestrator that both awaits I/O and mutates a
  state machine other tasks also mutate.
- Adding an `await` to a coroutine that previously had none after its state check.
- Exposing any rate/age/health derived from a sample window.
- Designing a transport layer's error surface for a consumer that retries.
- Closing a review finding: ask which other lanes, exceptions, or coroutines share the shape.

## Examples

Test shape that catches the window (from `src/rosy_fleet/test/test_session.py`):

```python
followers[1].follow_gate = asyncio.Event()          # park _arm on the second follower
task = asyncio.create_task(session.reform(spec))
await settle()                                       # scheduler rounds, not wall-clock
followers[0].event_frames.put_nowait({"type": "safety.estop", ...})
await settle()
followers[1].follow_gate.set()                       # let reform finish
await task
assert session.state is SessionState.HOLDING and session.relay.paused
```

Test shape that catches the non-decaying metric (`test_relay.py`):

```python
clock.advance(600.0)
assert relay.stats().leader_rx_hz == 0.0
```

## Related

- `docs/plans/2026-09-08-swarm-formation-slice-design.md` §4 (0 Hz invariant), §5 (two
  kinds of reform refusal), §6.3 (pending triggers), §9 (error table incl. the WS_403 wire fact)
- `docs/solutions/workflow-issues/inability-to-check-recorded-as-clean-result.md` — the
  sibling shape: a component that cannot answer returns the value it would return if
  everything were fine. A rate that never decays is that shape applied to a metric.
