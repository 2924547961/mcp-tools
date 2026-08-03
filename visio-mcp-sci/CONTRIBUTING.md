# Contributing

Contributions are welcome. Please keep the following invariants:

- Arrows must use native Visio `BeginArrow` / `EndArrow` cells.
- Do not introduce separate polygon arrowheads.
- Connector terminals must be perpendicular to the attached shape side.
- Do not place attachment points inside the rounded-corner exclusion zone.
- Preserve the profile's minimum straight terminal stub before a bend.
- Scientific figure changes must remain editable in Visio.
- New routing behavior needs both a geometry unit test and a Windows/Visio smoke test.
- Do not weaken strict export checks without documenting the false-positive case.

Before opening a pull request:

```powershell
python -m compileall -q src
python -m unittest discover -s tests -p "test_*.py"
```
