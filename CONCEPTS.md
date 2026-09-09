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

## Swarm formation

### Reference stream
The stream of a leader robot's own pose that followers consume to hold their place in a formation.

The follower does not ask where the stream came from — a Fleet relay, a direct link from the leader, or a future peer source all deliver the same frames — and it holds position on its own when the stream stops for longer than its timeout. Nothing in the path may invent a frame: a repeated or synthesized pose makes a dead leader look alive, and so does a health figure that does not decay when frames stop.

### Formation hold
The formation-wide stop taken when any one robot reports it cannot continue, made by withholding the reference stream so that every follower's own stream-loss behavior fires.

*Avoid:* group stop, all-stop (those name an e-stop, which is a different, faster path)

A hold leaves each follower's following session alive, so resuming is a matter of letting the stream flow again; it never resumes on its own, and resuming first re-verifies that every robot is still following and none has a newer reason to stop. A refusal that touched no robot — a bad formation shape, robots on different maps, a leader in e-stop — never causes or lifts a hold; it leaves the formation exactly as it was.

### Slot offset
A follower's place in a formation, expressed as a distance behind the leader and a lateral offset to the leader's left, in the leader's own heading frame.

Every formation shape reduces to one slot offset per follower, so changing shape is re-issuing offsets rather than a new kind of command. Offsets have a floor below which two robots' footprints, with their obstacle inflation, would overlap.

## Flagged ambiguities

- "Robot id" had been used for both the Robot number and the namespace derived from it — these are distinct, and only the number is supplied by a person.
- "Hold" in swarm material means the formation-wide stop made by withholding the stream; "e-stop" is the robot's own emergency path and is faster. The two are not interchangeable even though both leave robots stationary.
- "Profile" is used by the container tooling for its own service grouping; Runtime mode is the project concept, and the two are not interchangeable even where they share names.
