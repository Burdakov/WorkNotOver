# External References for Implementation Alignment

These references help align the forecast module with OPM Flow and related
reservoir-engineering tooling.

## Local Primary References

Use these local files before external links when implementing the OPM Flow
wrapper, case generation, validation, result import, or `simulation_runs`
artifact layout:

- OPM Flow Reference Manual PDF:
  `docs/forecast-module/references/OPM_Flow_Reference_Manual_2025-10_Rev-0_compressed.pdf`
- WorkNotOver OPM Flow guide:
  `docs/forecast-module/docs/OPM_FLOW_REFERENCE_GUIDE.md`
- Extracted manual index:
  `docs/forecast-module/references/opm_flow_manual_2025_10_index.json`

The local manual and generated guide are the primary references for OPM deck
section order, keyword placement, include-file structure, output artifacts, and
importer expectations. The external links below are supporting references.

## OPM Flow / OPM Common

- OPM Flow page: https://opm-project.org/?page_id=19
- OPM Flow manual page: https://opm-project.org/?page_id=955
- OPM opm-common repository: https://github.com/OPM/opm-common

Use OPM/Eclipse deck conventions as the canonical basis for PVT/SCAL/ROCK
properties:

- `DENSITY`
- `PVTO` / `PVDO`
- `PVTW`
- `PVDG` / `PVTG`
- `ROCK`
- `SWOF` / `SGOF`
- `SWFN` / `SGFN` / `SOF2` / `SOF3`
- `PVTNUM` / `SATNUM` / `ROCKNUM` / `FIPNUM`

## pywaterflood

- pywaterflood documentation: https://pywaterflood.readthedocs.io/
- CRM module: https://pywaterflood.readthedocs.io/en/v0.3.1/autoapi/pywaterflood/crm/index.html
- Buckley-Leverett module: https://pywaterflood.readthedocs.io/en/stable/autoapi/pywaterflood/buckleyleverett/index.html

## res2df

- res2df PVT usage: https://equinor.github.io/res2df/usage/pvt.html
- res2df repository: https://github.com/equinor/res2df
