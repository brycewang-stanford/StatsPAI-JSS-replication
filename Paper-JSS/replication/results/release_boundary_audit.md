# Release Boundary Audit

Status: PASS

Scope: distinguish the submitted source snapshot from the final clean
tagged release. This audit allows an explicit source-snapshot submission,
but fails if source-snapshot evidence is framed as already released.
It also keeps the future JSS package boundary separate from the
active JOSS review without requiring edits to `paper.md`.

Source snapshot:
- Package metadata version: 1.32.0
- Source `__version__`: 1.32.0
- Schema-bundle version: 1.32.0
- Version-consistent: True
- Ready for final publication release: False
- Final-publication gate blocker paths: 5
- Generated dirty paths: 20
- Unreleased CHANGELOG nonempty: False
- Structured release gate checks: 6
- JSS submission archive status: Audited source-snapshot submission archive; the failing final-publication release gate is a tag/changelog synchronization gate, not a JSS upload reproducibility failure.

Disclosure files checked: 9

Failures: none
