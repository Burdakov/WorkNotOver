# OPM Flow Reference Guide for WorkNotOver

## Source Files

Primary manual:

- `docs/forecast-module/references/OPM_Flow_Reference_Manual_2025-10_Rev-0_compressed.pdf`

Generated index:

- `docs/forecast-module/references/opm_flow_manual_2025_10_index.json`

The JSON index was generated from the local PDF with `pypdf`. It contains the
PDF metadata, outline entries with page numbers, keyword hit counts, and sample
pages for OPM/Eclipse keywords used by the WorkNotOver case builder.

Manual extraction summary:

- Title: `OPEN POROUS MEDIA`
- Subject: `OPM Flow Reference Manual`
- Author: `David Baxendale`
- PDF pages: `2712`
- Outline entries: `3665`

## Status in WorkNotOver

This guide is the operational reference for implementing the OPM Flow wrapper,
case generation, validation, and `simulation_runs` artifacts in Module B.

Precedence for hydrodynamic simulator behavior:

1. The local OPM Flow reference manual PDF.
2. This generated guide and the extracted keyword index.
3. `docs/contracts/module-b-forecast.md`.
4. Existing `forecast-module` legacy prompt-kit documents.

Legacy proxy, CRM, MRST, or waterflood diagnostic documents can inform optional
diagnostics, but they must not override OPM Flow deck rules, keyword placement,
output artifact expectations, or scenario-bound `SimulationRun` contracts.

## Manual Navigation

Use the manual pages below when changing deck generation or result import.

| Area | Manual location |
| --- | --- |
| Running Flow | Chapter 2, page 75 |
| Keyword documentation structure | Chapter 3, page 162 |
| Global keywords | Chapter 4, page 173 |
| `RUNSPEC` | Chapter 5, page 198 |
| `GRID` | Chapter 6, page 427 |
| `EDIT` | Chapter 7, page 731 |
| `PROPS` | Chapter 8, page 767 |
| `REGIONS` | Chapter 9, page 1339 |
| `SOLUTION` | Chapter 10, page 1401 |
| `SUMMARY` | Chapter 11, page 1564 |
| `SCHEDULE` | Chapter 12, page 1666 |
| Alphabetic keyword index | Appendix A, page 2284 |
| Output file formats | Appendix F, page 2571 |
| SUMMARY output files | Appendix F.10, page 2700 |

## Deck Assembly Contract

The generated OPM deck must be sectioned in Eclipse-compatible order:

```text
RUNSPEC
GRID
EDIT
PROPS
REGIONS
SOLUTION
SUMMARY
SCHEDULE
END
```

`EDIT` can be omitted when no array editing is needed. For the current 2D field
model, separate include files are preferred:

```text
input/FIELD_2D_<SCENARIO>.DATA
input/includes/runspec.inc
input/includes/grid.inc
input/includes/edit.inc
input/includes/props.inc
input/includes/regions.inc
input/includes/init.inc
input/includes/summary.inc
input/includes/schedule.inc
```

The main `.DATA` file should only define section order and include files. The
include files are the inspectable source artifacts in `simulation_runs`.

## Required Keyword Families

### RUNSPEC

Purpose: global model declaration, dimensions, phases, output policy, table and
region limits.

Core keywords for the current 2D black-oil workflow:

- `RUNSPEC`
- `TITLE`
- `DIMENS`
- `OIL`, `WATER`, `GAS` according to selected phases
- `FIELD` or another explicit unit system chosen by the project
- `TABDIMS`, `REGDIMS`, `WELLDIMS`, `SMRYDIMS`
- `START`
- output policy: `UNIFOUT`, `UNIFOUTS`, `FMTOUT` when requested

Manual anchors:

- `RUNSPEC`: page 373
- `DIMENS`: keyword hits in Chapter 5 and Appendix A
- `REGDIMS`: page 364
- `SMRYDIMS`: page 382
- `UNIFOUT`: page 410
- `UNIFOUTS`: page 412

Implementation rule:

- Grid dimensions in `DIMENS` must match the generated grid arrays and the
  normalized grid metadata stored in `field_2d_analysis.json`.

### GRID

Purpose: static grid geometry and static cell properties.

Current 2D field model can use regular Cartesian arrays:

- `GRID`
- `DX`, `DY`, `DZ` or equivalent vector keywords
- `TOPS`
- `PORO`
- `PERMX`, `PERMY`, `PERMZ`
- `ACTNUM`
- `INIT` if INIT output is required
- optional `GRIDFILE` or output controls if importer expectations require them

Corner-point expansion requires:

- `COORD`
- `ZCORN`

Manual anchors:

- `GRID`: page 550
- `ACTNUM`: page 446
- `COORD`: page 484
- `DX`: page 516
- `DY`: page 518
- `DZ`: page 520
- `INIT`: page 571
- `GRIDFILE`: page 551

Implementation rule:

- Every perforation top, center, and bottom point must map to an active cell.
- `ACTNUM`, `FIPNUM`, `SATNUM`, `PVTNUM`, and well completion indices must use
  the same grid coordinate convention.

### EDIT

Purpose: post-grid edits for arrays and transmissibilities.

Use when history matching requires explicit multipliers:

- `EDIT`
- `MULTPV`
- `MULTX`, `MULTY`, `MULTZ`
- `MULTX-`, `MULTY-`, `MULTZ-`
- `MULTREGT`
- `EQUALS`, `MULTIPLY`, `BOX`, `ENDBOX`

Manual anchors:

- `EDIT`: page 744
- `MULTPV`: page 755
- `MULTX`: page 757
- `MULTY`: page 757
- `MULTZ`: page 757
- `MULTREGT`: page 756

Implementation rule:

- Region adaptation must be traceable: every generated multiplier should have a
  region id, reason, source metric, and applied value in normalized diagnostics.

### PROPS

Purpose: PVT, rock compressibility, saturation functions, and relative
permeability/capillary pressure tables.

Current required families:

- `PROPS`
- `DENSITY`
- oil PVT: `PVDO` or `PVTO`
- water PVT: `PVTW`
- gas PVT: `PVDG` or `PVTG`, when gas phase is enabled
- rock compressibility: `ROCK`
- saturation tables: `SWOF`, `SGOF`, or alternatives such as `SWFN`, `SGFN`,
  `SOF2`, `SOF3`

Manual anchors:

- `PROPS`: page 1108
- `DENSITY`: page 845
- `PVTW`: page 1140
- `ROCK`: page 1153
- Saturation table overview: page 788

Implementation rule:

- `pvt_properties` datasets must preserve raw OPM include text. The case builder
  can append generated defaults only when the scenario explicitly allows it and
  must record that in warnings.
- Region-specific relative permeability variants should be represented by
  `SATNUM` and multiple saturation tables, not by hidden UI-only settings.

### REGIONS

Purpose: assign cells to PVT, saturation, equilibration, rock, and material
balance regions.

Current required families:

- `REGIONS`
- `FIPNUM`
- `SATNUM`
- `PVTNUM`
- `ROCKNUM`
- `EQLNUM` when using equilibration by region

Manual anchors:

- `REGIONS`: page 1385
- `PVTNUM`: page 1382
- `EQLNUM`: page 1352

Implementation rule:

- `FIPNUM` is the material-balance/reporting region axis.
- `SATNUM` is the relative permeability/SCAL region axis.
- `PVTNUM` is the fluid-property region axis.
- These arrays can coincide for a simple model, but the code must treat them as
  separate contract fields because history matching may change them differently.

### SOLUTION

Purpose: initial state.

Supported initialization modes:

- equilibrium initialization: `EQUIL`
- explicit enumeration: `PRESSURE`, `SWAT`, `SGAS`, `RS`, `RV`
- restart initialization

Manual anchors:

- `SOLUTION`: Chapter 10, page 1401
- equilibrium initialization: page 1407
- enumeration initialization: page 1408
- restart initialization: page 1410
- `EQUIL`: page 1456
- `PRESSURE`: page 1487
- `RPTRST`: page 1497
- `RPTSOL`: page 1503
- `RS`: page 1506
- `RV`: page 1514

Implementation rule:

- WorkNotOver scenario manual config must expose initial pressure and
  saturations. These values must be written to `init.inc`, stored in
  `run_manifest.opm_case_manifest.metadata.init`, and copied into normalized
  analysis metadata.

### SUMMARY

Purpose: define time-based vectors to write for field, wells, groups, and
performance diagnostics.

Current minimum vectors:

- Field: `FOPR`, `FWPR`, `FGPR`, `FWIR`
- Well production: `WOPR`, `WWPR`, `WGPR`, `WWCT`
- Well injection: `WWIR`
- Pressure/control: `WBHP`

Manual anchors:

- `SUMMARY`: page 1663
- summary mnemonic syntax: page 1569
- summary variable format: page 1572
- `ALL`: page 1634
- `RPTONLY`: page 1657
- `SUMTHIN`: page 1664

Implementation rule:

- The UI and importer must not assume a vector exists unless it was requested or
  found in `SMSPEC`/summary output.

### SCHEDULE

Purpose: time stepping, wells, completions, controls, efficiency factors, and
report/restart output controls.

Current required families:

- `SCHEDULE`
- `DATES` or `TSTEP`
- `WELSPECS`
- `COMPDAT`
- `WCONPROD`
- `WCONINJE`
- `WEFAC`
- `WPIMULT` when connection multipliers are generated
- `WELTARG` when modifying constraints after initial controls
- `RPTRST`/schedule reporting as required by restart import
- `END`

Manual anchors:

- `SCHEDULE`: page 1982
- `COMPDAT`: page 1730
- `WCONINJE`: page 2061
- `WCONPROD`: page 2070
- `WEFAC`: page 2098
- `WELSPECS`: page 2133
- `WELTARG`: page 2138
- `WPIMULT`: page 2196
- `TSTEP`: page 1997

Implementation rule:

- Well names, grid indices, well status, and control mode must be fully
  reproducible from normalized scenario inputs and `schedule.inc`.
- History rows are the source for historical controls; forecast changes must be
  scenario-bound and explicit.

## Output Artifact Contract

Raw OPM artifacts must be preserved under each `SimulationRun`:

```text
input/
  FIELD_2D_<SCENARIO>.DATA
  includes/*.inc
output/
  stdout.txt
  stderr.txt
  OPM binary/text outputs
normalized/
  field_2d_analysis.json
  field_2d_grid_cells.json
  field_2d_grid_states.json
  field_2d_region_metrics.json
  field_2d_timeseries.json
  import_report.json
reports/
```

Expected OPM output families:

- grid geometry: `EGRID`
- initial state: `INIT`
- summary index/data: `SMSPEC`, `UNSMRY` or segmented summary files
- restart state: `UNRST` or segmented restart files
- print/debug/log files: `PRT`, `DBG`, `stdout.txt`, `stderr.txt`

Manual anchors:

- output file formats: Appendix F, page 2571
- summary files: Appendix F.10, page 2700

Implementation rule:

- `run_manifest.json` is the authority for `run_id`, status, artifacts, and
  normalized paths.
- Physical folders are named for user inspection:
  `simulation_runs/<scenario-name>/<timestamp>_opm-flow-2d_<run-prefix>/`.
- Consumers must read `run_id` from `run_manifest.json`, not from the folder
  suffix.

## Validation Checklist for Case Builder Changes

Before accepting a change to OPM case generation:

1. The deck contains sections in valid order.
2. Every generated include file is referenced by the root `.DATA` file.
3. `DIMENS` matches generated grid arrays.
4. Array lengths match `nx * ny * nz`.
5. `ACTNUM` marks perforated cells active.
6. Every perforation point maps to a valid `i, j, k`.
7. `COMPDAT` cells are active and match perforation intervals.
8. `PVTNUM`, `SATNUM`, `ROCKNUM`, `FIPNUM` are explicit arrays or explicitly
   defaulted.
9. PVT/SCAL/ROCK keywords are provided by scenario-bound input or a recorded
   generated fallback.
10. Initial pressure/saturations are written in `SOLUTION`.
11. Schedule dates are sorted and reproducible from history/scenario inputs.
12. Requested summary vectors are present in `summary.inc`.
13. `flow` return code and logs are captured in `run_manifest.metadata`.
14. Normalized grid and time-step payloads reference the same `run_id` and
   `scenario_id`.

## Development Rule

When adding or modifying support for an OPM keyword, first update this guide or
the generated keyword index reference with:

- keyword name;
- deck section;
- manual page anchor;
- WorkNotOver source dataset/config field;
- generated include file;
- normalized output field or artifact impact.

No runtime code should introduce a new OPM keyword silently.
