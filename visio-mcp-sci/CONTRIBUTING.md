# Contributing

Contributions are welcome. Preserve these drawing rules:

- Arrows must use native Visio `BeginArrow` / `EndArrow` cells.
- Do not introduce separate polygon arrowheads.
- Prefer clean horizontal or vertical terminal segments into controls.
- Do not force visible terminal stubs by default; use them only when they improve clarity.
- Avoid routes that touch rounded corners, cross text, or overlap controls.
- Scientific figure changes must remain editable in Visio.
- New routing behavior needs both a geometry unit test and a Windows/Visio smoke test.
- Do not weaken strict export checks for overlap, crossings, or hidden arrowheads without documenting the false-positive case.

Before opening a pull request:

```powershell
python -m compileall -q src
python -m unittest discover -s tests -p "test_*.py"
```
