# Project instructions for Codex

This repository implements a waterflood proxy history-matching and forecasting model.

## Core modeling rules

The first injector-producer connectivity estimate must be generated from well coordinates before using MRST, CRM, OPM, or manual coefficients.

Default geometric rule:

- For each injector, producers within 3000 m are inside the initial influence zone.
- Distance weight: `g_dist_ij = max(0, 1 - d_ij / 3000)^p`.
- Default `p = 2`.
- Apply link-type multipliers:
  - `screen = 0.2`
  - `normal = 1.0`
  - `channel = 2.5`
  - `unknown = 1.0`
- Normalize `alpha_prior` by injector.

Coordinates:

- `wells.csv` must include `x` and `y` in meters.
- Coordinate reference system must be explicitly defined in `config.yaml`.
- Do not silently mix coordinate systems.
- Do not silently treat latitude/longitude as meters.

Each injector-producer edge is a 1D hydrodynamic proxy connection with:

- distance;
- alpha;
- injection efficiency eta;
- delay tau;
- effective pore volume;
- saturation state;
- injected pore volumes;
- fractional-flow / Buckley-Leverett-style displacement response.

Distance-based alpha is only a prior. The optimizer must be able to adjust alpha, eta, tau, PV, displacement parameters, and pressure/material-balance parameters based on watercut, `p_res`, and material balance.

## PVT / SCAL / ROCK rules

Production runs must use explicit PVT, SCAL, and ROCK properties.

Do not use guessed constant fluid properties in production mode.

Canonical external basis:

- OPM/Eclipse-style PROPS and REGIONS.
- PVT keywords: `DENSITY`, `PVTO`, `PVDO`, `PVTW`, `PVDG`, `PVTG`.
- Rock keyword: `ROCK`.
- Saturation function keywords: `SWOF`, `SGOF`, `SWFN`, `SGFN`, `SOF2`, `SOF3`.
- Region keywords: `PVTNUM`, `SATNUM`, `ROCKNUM`, `FIPNUM`.

The Python proxy must implement property evaluators:

- `Bo(p, Rs)`
- `Rs_sat(p)`
- `Pb(Rs)`
- `mu_o(p, Rs)`
- `Bw(p)`
- `mu_w(p)`
- `Cw(p)`
- `Bg(p)`
- `mu_g(p)`
- oil/water/gas reservoir density
- rock pore-volume multiplier
- `krw(Sw)`, `krow(Sw)`, `krg(Sg)`, `krog(Sg)`
- `pcow(Sw)`, `pcog(Sg)`

The material-balance model must use pressure-dependent PVT properties and rock/water compressibility.

The 1D edge displacement model must use tabular SCAL and pressure-dependent viscosities when available.

Corey/Brooks-Corey curves are allowed only for synthetic tests or explicitly configured parametric mode.

Never silently extrapolate PVT/SCAL tables. Extrapolation is disabled by default.

## External tools

- OPM Flow is optional and used for high-fidelity validation and material-balance imports.
- MRST Flow Diagnostics is optional and used for allocation factors, time-of-flight, swept volume, and drainage volume priors.
- pywaterflood is optional and used for CRM and simplified Buckley-Leverett functions.
- The base test suite must not require OPM, MRST, MATLAB, Octave, pywaterflood, res2df, opm.io, or resdata.

## Testing rules

Synthetic tests must include coordinates and explicit toy PVT/SCAL/ROCK tables.

Tests must prove:

1. Producers outside 3000 m are excluded by default.
2. Alpha priors are positive inside 3000 m.
3. Alpha priors sum to 1 per injector.
4. Screen links have lower priors.
5. Channel links have higher priors.
6. PVT/SCAL/ROCK tables affect material balance and fractional flow.
7. Missing production properties fail validation.
8. Calibration can override the distance prior when history data requires it.

## Engineering rules

- Keep code modular and testable.
- Use type hints.
- Use pydantic for configs and data schemas.
- Do not invent field data.
- Do not hide unit conversions.
- Save config snapshots with calibration results.
- Save fitted parameters, objective components, train/validation metrics, and diagnostic plots.
- Reports must support Russian labels.
