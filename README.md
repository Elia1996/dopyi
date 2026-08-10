# Dopyi

**DO**ors **PY**thon **I**nterface: read, edit, and write IBM Rational DOORS modules from Python using pandas.

Dopyi lets you treat a DOORS formal module as a `pandas.DataFrame`: download it, modify it locally, compare your changes in Excel, and write only the differences back to DOORS.

## How it works

Dopyi does not talk to the DOORS database directly. Instead, it starts a small **DXL server** inside your locally installed DOORS client (`dopyi/doorserver/doorserver.dxl`) and communicates with it over a localhost socket. Python sends DXL commands, DOORS executes them and returns the results.

This means:

- The DOORS client must be installed on the same (Windows) machine.
- The first time you connect, dopyi asks for your DOORS username and password and stores them locally (in `~/DoorsLocalDatabase`) so the server can be started automatically in later sessions. If the password changes, dopyi detects it and asks again.
- Multiple servers can run in parallel on different ports.

## Main components

| Module | Purpose |
|---|---|
| `dopyi.doorsmod` | High-level interface: a `doorsmod` object mirrors a DOORS formal module as a DataFrame (`dsm.wcd`), with read/compare/write-back, links, views, attributes, and baselines |
| `dopyi.dxl` | Low-level DXL commands as Python functions (open modules, baselines, links, run custom DXL) |
| `dopyi.doorserver` | Management of the local DXL server process (start/stop, ports, credentials) |
| `dopyi.parameters` | Parameter collections with physical units (via `pint`), loadable from DOORS-exported DataFrames |
| `dopyi.doors_excel_interface` | A small GUI (`dopyi_gui`) to download a module to Excel and upload changes back |

## Requirements

- Windows with an installed IBM Rational DOORS client
- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

From a GitHub release wheel:

```bash
uv add https://github.com/Elia1996/dopyi/releases/latest/download/dopyi-<version>-py3-none-any.whl
```

Directly from the repository:

```bash
pip install git+https://github.com/Elia1996/dopyi.git
```

Or clone and install locally:

```bash
git clone https://github.com/Elia1996/dopyi.git
cd dopyi
uv sync
```

## Quick start

Download a module, edit it, check the changes in Excel, and write them back:

```python
from dopyi.doorsmod import doorsmod

# Create the object bound to a DOORS module (full module path)
dsm = doorsmod("/xxx_SYS_TestsProject/SoW_Example")

# Download the module into a pandas DataFrame (dsm.wcd)
dsm.read()

# Modify the working copy: index is the Absolute Number
dsm.wcd.loc["10", "Object Text"] = "Text loaded from doorsmod"
dsm.wcd.loc["11", "Object Text"] = "Text added from doorsmod"

# Generate an Excel file showing old vs new values
dsm.compare("compare.xlsx")

# Write only the differences back to DOORS
dsm.write()
```

The first call opens DOORS, starts the local DXL server, and asks for your credentials if they are not stored yet.

### Working with links

In/out/external links are downloaded together with the module and stored in dedicated DataFrame columns:

```python
from dopyi.doorsmod import S_INLINK, S_OUTLINK, S_EXTLINK

absno = 12
inlinks = dsm.wcd.loc[absno, S_INLINK]    # list of dicts: absno, linkmod, mod
outlinks = dsm.wcd.loc[absno, S_OUTLINK]
extlinks = dsm.wcd.loc[absno, S_EXTLINK]

# Iterate all links of the requirements in a module
for absno, row in dsm.wcd.iterrows():
    if row["Object Type"] == "requirement":
        for d_inlink in row[S_INLINK]:
            print(f"{absno} has inlink {d_inlink}")
```

Links can be created or deleted with `create_links()`, `create_links_by_attr()`, `delete_links()`, and `delete_all_obj_links()`.

### Baselines

```python
dsm.get_baselines()       # list of all baselines of the module
dsm.get_last_baseline()   # e.g. {'id': 'ExampleModule_1.6', 'annotation': '...',
                          #       'date': datetime(...), 'user': 'user01'}

# Open a specific baseline by appending @<baseline> to the module name
dsm_b = doorsmod("/xxx_SYS_TestsProject/SoW_Example@1.0")
```

### Running custom DXL

The `dxl` class gives lower-level access, including running arbitrary DXL code in the connected DOORS session:

```python
from dopyi.dxl import dxl

dexter = dxl()
dexter.open("/xxx_SYS_TestsProject/SoW_Example")
print(dexter.get_links(4))
```

### Excel GUI

A minimal GUI to download a module to Excel and upload edits back, useful for people who do not use Python directly:

```bash
dopyi_gui
```

### Parameters with units

`dopyi.parameters` builds typed parameter collections (with `pint` units) from a DataFrame exported from DOORS:

```python
from dopyi.parameters import BaseParamCollection

bc = BaseParamCollection()
bc.from_df(df, d_map={"name": "Object Text", "value": "Value",
                      "unit": "Unit", "descr": "Description",
                      "id": "Absolute Number"})
bc.P_DC_ULV_Nominal   # -> <Quantity(14, 'volt')>
```

## Local data

Dopyi stores downloaded module data and credentials under `~/DoorsLocalDatabase`. Delete this folder to reset the local cache and stored credentials.

## Development

```bash
git clone https://github.com/Elia1996/dopyi.git
cd dopyi
uv sync
```

Tests (`tests/`) require a live DOORS installation with test modules, so they cannot run in CI:

```bash
uv run pytest -m <marker>
```

### Releases

Every push to `main` triggers the GitHub Actions workflow, which:

1. Bumps the patch version and pushes a new `X.Y.Z` tag (the package version comes from git tags via `setuptools-scm`).
2. Builds the wheel and sdist with `uv build` and validates them with `twine check`.
3. Creates a GitHub Release with the build artifacts attached.
4. Optionally uploads to a package index if the `TWINE_USERNAME` / `TWINE_PASSWORD` (and optional `TWINE_REPOSITORY_URL`) repository secrets are configured.

## License

MIT — see [LICENSE](LICENSE).

## Author

Elia Ribaldone
