# pulsar_auto -- instructions for Claude

**Current mode of work (since 2026-10-05): boundary perfection from captured golden bundles.**
Read `aligner2/PERFECTION_WORKFLOW.md` IN FULL at the start of every session that touches the aligner and again after
every context compaction. It defines the goal (system output == golden labels on every boundary), how the user
collects data (CURRENT = the labels the current system generates and injects -- NOT the platform's prelabels;
GOLDEN = those labels after the user perfected them; + change notes per bundle), the gold semantics (every boundary of a golden
capture is gold, unchanged ones included -- not circular), and the engineering loop (inspect raw data per case,
explicit rules, and investigate every regression one by one instead of abandoning a change).

Also: `aligner2/HANDOFF.md` (system overview, versions), `bench/cache/aligner2/fullread/NOTES.md` (experiment log).
