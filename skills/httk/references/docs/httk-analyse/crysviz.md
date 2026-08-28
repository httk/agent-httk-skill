# CrysViz structure viewer

Install the optional integration with:

```bash
python -m pip install "httk-analyse[crysviz]"
```

CrysViz uses pywebview for its desktop window. Install the matching backend
extra, such as `crysviz[gtk]` or `crysviz[qt]`, when your platform needs one.

```python
from httk.analyse.crysviz import show, to_payload
from httk.atomistic import UnitcellStructureView

structure = UnitcellStructureView("example.cif")
viewer = show(structure)
viewer.wait()
payload = to_payload(structure)  # pass it to crysviz.Viewer for advanced control
```

`show()` returns after the viewer window is ready and remains non-blocking
afterwards. The returned viewer can also be used as a context manager. Use
`to_payload()` when constructing `crysviz.Viewer` yourself or when a serialized
payload needs to be inspected before launching.
