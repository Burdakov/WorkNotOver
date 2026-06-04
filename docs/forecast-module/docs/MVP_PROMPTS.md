# Incremental Codex prompts

Use these prompts after the master prompt if you want to build the project in controlled stages.

## Stage 1 — Skeleton and data contracts

```text
Implement only the first MVP stage:

- package skeleton;
- pydantic schemas;
- config loader;
- CSV loaders;
- CLI stubs;
- validation for wells, production, injection, cells, and normalized property files;
- pytest tests for schemas and validation.

Do not implement calibration yet. Run pytest and show results.
```

## Stage 2 — Coordinate-based connectivity

```text
Implement coordinate-based injector-producer initialization:

- validate x/y coordinates and CRS;
- create links inside 3000 m radius;
- compute distance weights with power cutoff kernel;
- apply screen/normal/channel/unknown multipliers;
- normalize alpha_prior by injector;
- estimate tau_prior and pv_prior;
- export connections_initial.csv;
- add network and alpha heatmap plots;
- add tests for geometry rules.

Run pytest and show results.
```

## Stage 3 — PVT/SCAL/ROCK property evaluators

```text
Implement normalized PVT/SCAL/ROCK table readers and evaluators:

- DENSITY equivalents;
- PVTW;
- PVTO/PVDO-style oil PVT;
- PVDG/PVTG-style gas PVT;
- ROCK;
- SWOF and SGOF;
- region mapping with PVTNUM/SATNUM/ROCKNUM/FIPNUM equivalents;
- interpolation with no silent extrapolation;
- fractional-flow calculation from kr and viscosity.

Add tests proving that properties affect fractional flow and material-balance calculations.
Run pytest and show results.
```

## Stage 4 — Native proxy simulator

```text
Implement the native waterflood proxy simulator:

- graph model;
- 1D edge displacement with IPVI and saturation;
- PVT/SCAL fractional flow on edges;
- PVT-aware tank material-balance pressure model;
- simulation loop over historical timesteps;
- outputs for watercut, pressure, edge states, and material balance.

Add synthetic example and tests.
Run pytest and show results.
```

## Stage 5 — Calibration and forecast

```text
Implement scipy-based calibration and forecast:

- parameter vector for alpha, eta, tau, PV, displacement efficiency, pressure parameters;
- objective components for watercut, pressure, rates, material balance, regularization;
- bounds and constraints;
- multi-start fitting;
- scenario runner;
- fitted parameter export;
- forecast outputs;
- synthetic recovery tests.

Run pytest and show results.
```

## Stage 6 — External adapters

```text
Add optional adapters:

- pywaterflood CRM and Buckley-Leverett adapter with graceful fallback;
- MRST CSV import adapter and MATLAB/Octave script template;
- OPM/res2df property and results import adapter;
- skip tests when optional dependencies are missing.

Run pytest and show results.
```
