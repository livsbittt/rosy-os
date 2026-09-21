## D-158 UI Component Consistency: Strict Outline Borders (Law 2)

**Date:** 2026-09-21
**Status:** Accepted
**Context:** G3 validation identified visual discomfort from combining flat
primary button fills with inset sheens on procedural panels. This weakened the
Law 2 distinction between reporting surfaces and actions.
**Decision:** Procedural container panels use a standard one-pixel
`var(--surface-line)` outline and spacing instead of an inset sheen. Quiet
actions remain outlined; primary actions retain a flat background.
