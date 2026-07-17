# Contributing

- Add or update a regression fixture before changing scientific behavior.
- State the coordinate basis, origin, PBC, units, parser version, and tolerance.
- Never silently reorder species/sites; return an explicit index map.
- Never commit external structures without provenance and redistribution rights.
- Keep symmetry inference, application workflows, and institution-specific configuration out of this package.
- Require an independent reviewer for parser, coordinate, hashing, or equivalence changes.
