# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Robot commissioning

### Robot number
The single value that identifies one physical robot within a fleet, chosen when the unit is commissioned and never inferred from anything else.

Everything else about a unit's identity derives from it, so it is the only identity value a person supplies. It is a plain decimal with no leading zero — a leading zero is refused rather than interpreted, because shell arithmetic and zero-padded formatting can read the same written value as two different numbers and agree with each other while both are wrong. Its upper bound is whatever keeps the derived domain inside the range the host operating system reserves for it.

### Robot identity
The pair of a robot's DDS domain and its ROS namespace, derived together from one Robot number.

*Avoid:* robot id

The two halves must agree, because separating robots by domain alone still leaves their topic names colliding. Identity is device state, not repository content: no template, installer default, or compose default supplies it, and a missing identity stops the runtime rather than being filled in — a default is what once shipped every unit with the same one. Re-provisioning a unit under a different number fails loudly instead of renumbering it in place, and all derived values are validated before any of them is written, so a unit is never left half-migrated.

### Runtime mode
The staged capability level a unit runs at: core, then motor, then hardware, each admitting more physical hardware than the last.

*Avoid:* profile

Core is the safe default a unit boots into and the only one that starts no motion hardware; motor adds the drivetrain for bench commissioning; hardware adds navigation and the remaining sensors. Promotion is explicit and is expected to be re-earned after an update or rollback. A board catalog may define aliases that resolve to one of the three; anything that resolves to none of them is an error rather than a fallback.

### Recovery hold
A recorded refusal that stops a unit's runtime from starting after a release failed to prove itself healthy.

A hold is evaluated before the runtime starts, and its verdict is specifically "does this block the runtime" rather than "did everything succeed" — the two differ, and keying on the latter is how a held device boots anyway. The gate expresses its verdict as a process exit status, and nothing in the boot path may retry or restart past it, since either would convert a hold into a boot.

## Docking

### Dock
The charging station a robot drives into, which measures the charge it delivers rather than leaving the robot to infer it.

It carries a controller for a safety reason rather than a reporting one: its contacts sit on the floor at pet and toddler height, so it detects a load before it energises anything and de-energises the moment the load leaves. Measurement is the second benefit of a controller that had to exist anyway, and it matters because the robot has no current sensor of its own. The dock never opens a connection to a robot — the robot asks, because the robot knows which dock it is going to and an inbound path into the robot would be an unauthenticated surface for no gain. It reports load and current as separate facts, because contacts can be engaged while nothing flows, and those two situations need different recoveries.

### Docking
The staged approach that takes a robot from somewhere in the map to engaged contacts.

Map coordinates get it near; every stage after that closes the loop on the observed dock, because localisation error is two orders of magnitude larger than the contact tolerance. The whole approach holds one mode from start to finish, which both stops a fleet command from pushing a half-engaged robot out and avoids widening the mode transition table. Stages exist so that a failure's location is known: not arriving and arriving without conduction need different recoveries, and the second re-seats rather than starting over. A funnel absorbs the last centimetre or two of lateral error, so a controller that must be millimetre-accurate on its own is a controller that fails on a dusty floor.

### Charging confirmation
The judgement that a robot is actually charging, requiring two independent sources rather than the dock's word.

*Avoid:* charge detection

The dock's reported current is one source; the robot's own filtered pack voltage not falling is the other. Two are required because this judgement suppresses the deep-discharge shutdown, so anything on the network able to assert charging would otherwise be able to switch off a safety path. The asymmetry is deliberate: confirming requires the whole window, and losing it is immediate.

### Dock detector
The sensing boundary that reports where the dock is, relative to the robot, and nothing else about how it knows.

Which physical signal it uses is deliberately not decided by the boundary, so the approach logic could be built and verified before the sensing was chosen. A detector also has a usable distance band whose near edge is not zero — features leave the sensor's view close in — and that near edge is measured rather than assumed, because it sets how early the dock type hands off to the funnel and the contact judgement. A detector that reports nothing invites a retry; a detector that confidently reports the wrong pose drives the robot into something that is not the dock, which is why refusing is preferred to guessing.

### Measurement rig
A harness whose product is a recorded verdict about which candidate approach ships, rather than a feature.

*Avoid:* test harness

A rig is held to a stricter standard than the thing it measures, because its errors emerge as numbers about something else and a number gets believed. Its pass criteria are fixed before any measurement is taken, since choosing them afterward produces whichever answer was wanted. Its collection paths write one shared record and are judged against one shared set of criteria, so candidates stay comparable; a verdict is still rendered per path, because truths established by different means cannot be averaged together and a large path would otherwise dilute a small one. The failure that matters most is a rig that returns a verdict about itself while looking exactly like a verdict about its subject.

## Flagged ambiguities

- "Robot id" had been used for both the Robot number and the namespace derived from it — these are distinct, and only the number is supplied by a person.
- "Profile" is used by the container tooling for its own service grouping; Runtime mode is the project concept, and the two are not interchangeable even where they share names.
- "Candidate" is used for two different things in the docking work: a detection approach under evaluation by the Measurement rig, and a scan feature that might be one of the dock's own features. The first is what a verdict is about; the second is an intermediate the detector discards.
