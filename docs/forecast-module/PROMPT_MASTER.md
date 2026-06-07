# Master prompt for Codex: Waterflood proxy history matching and forecasting

## WorkNotOver implementation override

For the current WorkNotOver architecture, `Module B` production calculation is OPM-first:

- primary production method: `forecast_method = opm_flow_blackoil`;
- external `OPM Flow` is the hydrodynamic simulation engine;
- WorkNotOver backend builds OPM/Eclipse-compatible cases, runs `flow`, imports raw OPM artifacts and stores normalized scenario-bound results;
- native `waterflood_proxy_hm` logic is retained only as optional reduced-order diagnostics / legacy compatibility, not as the production calculation core;
- base tests may still validate case building, manifest generation and importer behavior without requiring the external `flow` executable.

The rest of this document remains useful for data requirements, PVT/SCAL/ROCK discipline, diagnostics, history-match concepts and optional adapters, but production implementation must not preserve the previous decline/proxy calculation as the main result source.

You are a senior reservoir simulation engineer, reservoir surveillance specialist, and Python software architect.

Build a production-quality Python package named `waterflood_proxy_hm` for automated history matching and forecasting of a waterflood proxy model. The model must combine:

1. A native Python graph/tank/1D-edge proxy model that works without external simulators.
2. OPM Flow as an optional high-fidelity black-oil simulator and validation/source-of-truth adapter.
3. MRST Flow Diagnostics as an optional source of allocation factors, time-of-flight, swept/drainage volumes, and connectivity diagnostics.
4. pywaterflood as an optional CRM and Buckley-Leverett helper.
5. OPM/Eclipse-style PVT/SCAL/ROCK property requirements as the canonical source for fluid, rock, and saturation-function data.

The package must support automated history matching of:

- producer watercut;
- reservoir pressure `p_res` / `Рпл` by well, cell, or region;
- material balance by development cell / FIPNUM / flood cell;
- injector-producer participation coefficients;
- injection efficiency coefficients;
- 1D displacement / saturation state on injector-producer links.

After calibration, the package must run forecast scenarios with different injection schedules, production constraints, shut-ins, well conversions, pressure constraints, link changes, and efficiency assumptions.

Do not build a monolithic reservoir simulator. Build a modular, testable Python package with clear data contracts, explicit engineering assumptions, strict validation, and optional external adapters.

---

## 1. Required technology stack

Use Python 3.11+.

Required libraries:

- numpy
- pandas
- scipy
- pydantic
- pyyaml
- matplotlib
- networkx
- pyarrow
- pytest
- typer or click

Optional libraries:

- optuna for multi-start / global optimization;
- pywaterflood for CRM and Buckley-Leverett helpers;
- res2df, resdata, opm.io, or ecl-like libraries for OPM/Eclipse input/output when available;
- oct2py or MATLAB/Octave command wrappers for MRST when available.

The base unit test suite must not require OPM Flow, MATLAB, MRST, Octave, pywaterflood, res2df, opm.io, or resdata. All external integrations must fail gracefully and skip integration tests when optional dependencies are unavailable.

---

## 2. Repository structure

Create this structure:

```text
waterflood_proxy_hm/
  __init__.py
  cli.py

  data/
    __init__.py
    schemas.py
    loaders.py
    validation.py
    units.py

  geometry/
    __init__.py
    distances.py
    connectivity_initializer.py
    well_trajectory.py

  graph/
    __init__.py
    nodes.py
    edges.py
    network.py

  properties/
    __init__.py
    units.py
    regions.py
    pvt_tables.py
    pvt_evaluator.py
    relperm_tables.py
    relperm_evaluator.py
    rock_tables.py
    rock_evaluator.py
    property_deck.py
    opm_import.py
    mrst_import.py
    validation.py

  model/
    __init__.py
    edge_displacement.py
    response_kernels.py
    fractional_flow.py
    material_balance.py
    pressure.py
    simulator.py

  calibration/
    __init__.py
    parameters.py
    priors.py
    objective.py
    optimizer.py
    metrics.py

  forecast/
    __init__.py
    scenarios.py
    runner.py

  adapters/
    __init__.py
    opm.py
    mrst.py
    pywaterflood_adapter.py
    res2df_adapter.py

  reporting/
    __init__.py
    plots.py
    html_report.py
    russian_labels.py

  examples/
    synthetic.py

tests/
  test_schemas.py
  test_geometry_initializer.py
  test_pvt_tables.py
  test_relperm_tables.py
  test_rock_tables.py
  test_property_regions.py
  test_fractional_flow.py
  test_edge_displacement.py
  test_material_balance.py
  test_calibration_synthetic.py
  test_forecast_scenarios.py
  test_optional_adapters_skip.py

examples/
  synthetic_small/
    wells.csv
    production.csv
    injection.csv
    cells.csv
    config.yaml
    scenarios.yaml
    properties/
      density.csv
      oil_pvt.csv
      water_pvt.csv
      gas_pvt.csv
      rock.csv
      swof.csv
      sgof.csv
      region_map.csv
```

---

## 3. Conceptual model

The core model is a directed waterflood graph:

- Injector nodes: water injection wells.
- Producer nodes: oil/water/gas production wells.
- Optional reservoir cell / pattern / FIPNUM nodes: development cells, flooding cells, blocks, regions, or tanks.
- Edges: injector-producer 1D hydrodynamic proxy connections.

Every injector-producer edge must have its own state and parameters:

- `injector_id`
- `producer_id`
- `cell_id` or `region_id`, optional
- `distance_m`
- `inside_influence_radius`
- `active`
- `link_type`: `normal`, `screen`, `channel`, or `unknown`
- `alpha_ij`: fitted participation coefficient
- `alpha_prior`: prior participation coefficient
- `eta_i` or `eta_ij`: injection efficiency coefficient
- `tau_days`: delay / time-of-flight proxy
- `pv_ij`: effective edge pore volume
- `movable_oil_ij`, optional
- `sw_ij`: current water saturation on the edge
- `so_ij`, optional
- `sg_ij`, optional
- `ipvi_ij`: injected pore volumes on the edge
- `length_m`
- `corridor_width_m`
- `area_m2`, optional
- `kh`, optional
- `transmissibility`, optional
- `screen_factor`
- `channel_factor`
- `breakthrough_ipvi_ij`
- `displacement_efficiency_ij`
- `prior_source`
- `prior_weight`

The 1D edge is not just a statistical connection. It represents an approximate injector-producer displacement corridor with effective pore volume, displacement state, saturation-dependent fractional flow, and delay.

---

## 4. Coordinate-based first guess for participation coefficients

Mandatory rule: the first injector-producer connectivity estimate must be generated from well coordinates before using MRST, CRM, OPM, or manually specified coefficients.

### 4.1 Well coordinates

`wells.csv` must contain metric coordinates.

Required columns:

- `well_id`
- `well_type`: `producer` or `injector`
- `x`
- `y`

Optional columns:

- `z`
- `cell_id`
- `region_id`
- `field`
- `reservoir`
- `formation`
- `start_date`
- `end_date`
- `status`
- `coord_source`
- `trajectory_type`: `vertical`, `deviated`, `horizontal`, `unknown`
- `heel_x`, `heel_y`, `toe_x`, `toe_y` for horizontal wells

The configuration must explicitly define the coordinate system:

```yaml
coordinates:
  crs: "EPSG:32640"
  x_unit: "m"
  y_unit: "m"
  allow_latlon: false
```

Do not silently mix coordinate systems. If coordinates are latitude/longitude, fail validation unless explicit conversion is configured.

### 4.2 Influence radius

For every injector `i`, find producer wells `j` within the default influence radius:

```text
R_influence = 3000 m
```

Distance:

```text
d_ij = sqrt((x_i - x_j)^2 + (y_i - y_j)^2)
```

A producer is a primary candidate if:

```text
d_ij <= R_influence
```

Producers outside the radius are excluded by default. Optionally create inactive candidate links outside the radius if configured.

### 4.3 Distance kernel

Default distance kernel:

```text
g_dist_ij = max(0, 1 - d_ij / R_influence)^p
```

Default:

```text
p = 2.0
```

Also support optional kernels:

```text
gaussian: g_dist_ij = exp(-(d_ij / R_influence)^beta)
inverse:  g_dist_ij = 1 / (d_ij + d_min)^p
```

Use the finite cutoff power kernel by default because it implements a clear 3000 m influence zone.

### 4.4 Link type multipliers

Apply geological/engineering link-type multipliers:

```text
g_ij = g_dist_ij * m_link_type_ij
```

Default multipliers:

```yaml
link_type_multipliers:
  screen: 0.2
  normal: 1.0
  channel: 2.5
  unknown: 1.0
```

Meaning:

- `screen`: barrier-like or poorly communicating connection; lower prior alpha, higher delay, weaker transmissibility, later water response.
- `channel`: high-conductivity / fracture / washed-out preferential path; higher prior alpha, lower delay, smaller effective PV, earlier water breakthrough.
- `normal`: regular connection.
- `unknown`: weak prior; let calibration infer behavior.

These labels are priors, not hard truth. The optimizer must be able to override them if history data supports another behavior.

### 4.5 Alpha prior normalization

Normalize the geometric prior by injector:

```text
alpha_prior_ij = g_ij / sum_j(g_ij)
```

If an injector has no producer inside 3000 m:

- do not invent a strong link;
- optionally connect it to the nearest producer with a very weak prior only if `connect_nearest_if_empty: true`;
- mark such links as `low_confidence`.

### 4.6 Distance-based delay prior

Initial delay:

```text
tau_prior_days = tau_min_days + distance_m / front_velocity_prior_m_per_day
```

Default:

```yaml
tau_initializer:
  tau_min_days: 10
  front_velocity_prior_m_per_day: 5.0
```

Apply link-type multipliers:

```yaml
link_type_tau_multipliers:
  screen: 2.5
  normal: 1.0
  channel: 0.4
  unknown: 1.0
```

### 4.7 Distance-based edge PV prior

If no cell volume, OPM volume, or MRST swept/drainage volume is available, initialize edge pore volume geometrically:

```text
pv_prior_ij = phi_ij * ntg_ij * h_ij * corridor_width_ij * distance_m
```

Default:

```yaml
edge_pv_initializer:
  method: "corridor"
  default_phi: 0.20
  default_ntg: 0.75
  default_h_m: 10.0
  default_corridor_width_m: 300.0
```

If cell material-balance volume is available, allow:

```text
pv_prior_ij = alpha_prior_ij * pv_cell
```

If MRST diagnostics are available, prefer MRST swept/drainage volume as a stronger prior.

---

## 5. PVT / SCAL / ROCK property system

Production runs must not use guessed constant fluid and rock properties. Implement a full property input and evaluation layer based on OPM/Eclipse-style black-oil requirements.

The native Python proxy must accept properties in either:

1. OPM/Eclipse deck/include format, where import support is available; or
2. normalized CSV/Parquet equivalents.

Synthetic examples may use toy property tables, but these toy properties must be explicit, versioned, and clearly marked as synthetic.

### 5.1 Canonical external basis

Use OPM/Eclipse-style `PROPS` and `REGIONS` concepts as the canonical input basis.

Support these keywords or normalized equivalents:

PVT / fluid properties:

- `DENSITY`
- `PVTO`
- `PVDO`
- `PVTW`
- `PVDG`
- `PVTG`
- optional later: `RSCONST`, `RSVD`, `RVVD`

Rock properties:

- `ROCK`
- optional later: `ROCKTAB`, `ROCKCOMP`, `ROCKOPTS`

Saturation functions / SCAL:

- `SWOF`
- `SGOF`
- `SWFN`
- `SGFN`
- `SOF2`
- `SOF3`
- optional later: endpoint scaling and hysteresis keywords

Region mapping:

- `PVTNUM`
- `SATNUM`
- `ROCKNUM`
- `FIPNUM` or custom material-balance regions

The internal normalized tables must preserve source keyword, source file, units, and region number.

### 5.2 Required property evaluators

Implement pressure-dependent and saturation-dependent evaluators:

PVT:

- `Bo(p, Rs, pvt_region)`
- `Rs_sat(p, pvt_region)`
- `Pb(Rs, pvt_region)`, derived from PVTO saturated rows when possible
- `mu_o(p, Rs, pvt_region)`
- `Bw(p, pvt_region)`
- `mu_w(p, pvt_region)`
- `Cw(p, pvt_region)`
- `Bg(p, pvt_region)`
- `mu_g(p, pvt_region)`
- `density_oil_reservoir(p, Rs, pvt_region)`
- `density_water_reservoir(p, pvt_region)`
- `density_gas_reservoir(p, pvt_region)`

Rock:

- `phi_multiplier_from_rock(p, rock_region)`
- optional pore-volume compressibility derivative

SCAL / relative permeability:

- `krw(Sw, sat_region)`
- `krow(Sw, sat_region)`
- `pcow(Sw, sat_region)`
- `krg(Sg, sat_region)`
- `krog(Sg, sat_region)`
- `pcog(Sg, sat_region)`

Use table interpolation for production. Do not use black-oil correlations unless explicitly configured.

Validation must fail on pressure or saturation outside table range unless extrapolation is explicitly enabled. Every extrapolation event must be logged.

### 5.3 Normalized property files

Support these normalized input files under `data/properties/`:

```text
density.csv
water_pvt.csv
oil_pvt.csv
gas_pvt.csv
rock.csv
swof.csv
sgof.csv
swfn.csv
sgfn.csv
sof2.csv
sof3.csv
region_map.csv
```

#### density.csv

Required columns:

- `pvt_region`
- `oil_density_surface`
- `water_density_surface`
- `gas_density_surface`
- `density_unit`

#### water_pvt.csv

Required columns:

- `pvt_region`
- `p_ref`
- `bw_ref`
- `cw`
- `muw_ref`
- `cvw`
- `pressure_unit`
- `viscosity_unit`

#### oil_pvt.csv

For live-oil PVTO-style data:

- `pvt_region`
- `rs`
- `pressure`
- `bo`
- `muo`
- `is_saturated_row`
- `pressure_unit`
- `rs_unit`
- `viscosity_unit`

For dead-oil PVDO-style data:

- `pvt_region`
- `pressure`
- `bo`
- `muo`
- `pressure_unit`
- `viscosity_unit`

#### gas_pvt.csv

For dry-gas PVDG-style data:

- `pvt_region`
- `pressure`
- `bg`
- `mug`
- `pressure_unit`
- `bg_unit`
- `viscosity_unit`

For wet-gas PVTG-style data, allow:

- `pvt_region`
- `pressure`
- `rv`
- `bg`
- `mug`
- `pressure_unit`
- `rv_unit`
- `bg_unit`
- `viscosity_unit`

#### rock.csv

Required columns:

- `rock_region`
- `p_ref`
- `rock_compressibility`
- `pressure_unit`
- `compressibility_unit`

#### swof.csv

Required columns:

- `sat_region`
- `sw`
- `krw`
- `krow`
- `pcow`
- `pressure_unit`

#### sgof.csv

Required columns:

- `sat_region`
- `sg`
- `krg`
- `krog`
- `pcog`
- `pressure_unit`

#### region_map.csv

Required columns:

- `cell_id`
- `pvt_region`
- `sat_region`
- `rock_region`
- `fip_region`

Optional columns:

- `region_name`
- `formation`
- `reservoir`
- `zone`

### 5.4 Bubble-point handling

For PVTO-style live oil:

- treat saturated PVTO rows as the source of `Rs_sat(p)` and `Pb(Rs)`;
- do not require a separate Pb table if PVTO is available;
- allow an explicit bubble-point table only as an additional normalized input;
- validate monotonicity and physical consistency where possible.

For PVDO-style dead oil:

- do not use dissolved gas unless explicit `RSCONST` or equivalent is provided.

### 5.5 PVT-aware material balance

Replace simplified liquid-volume balance with black-oil, stock-tank/reservoir-volume-aware material balance.

For each material-balance cell or region, track at least:

- pressure `p`
- pore volume `PV`
- porosity multiplier from rock compressibility
- water saturation `Sw`
- oil saturation `So`
- gas saturation `Sg`, optional
- stock-tank oil in place
- water in place
- free gas in place, optional
- dissolved gas in oil if live-oil PVT is used

Use black-oil component volumes:

```text
N_oil_stock = PV * phi_mult(p) * So / Bo(p, Rs)
W_water_stock = PV * phi_mult(p) * Sw / Bw(p)
G_gas_stock = PV * phi_mult(p) * Sg / Bg(p) + PV * phi_mult(p) * So * Rs(p) / Bo(p, Rs)
```

Production/injection conversions:

```text
oil_reservoir_volume   = q_oil_surface   * Bo(p, Rs)
water_reservoir_volume = q_water_surface * Bw(p)
gas_reservoir_volume   = q_gas_surface   * Bg(p)
```

Injected water should use `Bw` at local pressure or injection-condition pressure depending on configuration.

Calculate voidage replacement ratio using PVT-corrected reservoir volumes.

### 5.6 Pressure update

Initial MVP may use a tank pressure solver, but it must use:

- rock compressibility from `ROCK`;
- water compressibility from `PVTW`;
- pressure-dependent `Bo`, `Bw`, `Bg`, `Rs`, and viscosities from PVT tables;
- region-specific `PVTNUM` / `ROCKNUM`.

A conceptual update is:

```text
p_c(t+dt) = p_c(t) + pressure_solver(
    pore_volume,
    rock_compressibility,
    water_compressibility,
    oil_pvt,
    gas_pvt,
    injection_reservoir_volume,
    withdrawal_reservoir_volume,
    intercell_flux,
    aquifer_support
)
```

Do not use a single constant formation volume factor in production mode.

### 5.7 SCAL/PVT fractional flow

Oil-water fractional flow must use tabular relative permeability and pressure-dependent viscosity:

```text
lambda_w = krw(Sw, SATNUM) / mu_w(p, PVTNUM)
lambda_o = krow(Sw, SATNUM) / mu_o(p, Rs, PVTNUM)
fw = lambda_w / (lambda_w + lambda_o)
```

For gas-oil if gas is active:

```text
lambda_g = krg(Sg, SATNUM) / mu_g(p, PVTNUM)
lambda_o_g = krog(Sg, SATNUM) / mu_o(p, Rs, PVTNUM)
```

Corey/Brooks-Corey parametric curves are allowed only:

- for synthetic tests;
- when explicitly configured as parametric SCAL mode;
- as a simplified pywaterflood compatibility example.

Native tabular SCAL/PVT fractional flow is the authoritative implementation.

---

## 6. 1D edge displacement model

For every active injector-producer edge, track effective injection and injected pore volumes:

```text
q_inj_eff_ij(t) = alpha_ij * eta_ij * q_inj_i(t)
dIPVI_ij(t) = q_inj_eff_ij(t) * dt / pv_ij
IPVI_ij(t+dt) = IPVI_ij(t) + dIPVI_ij(t)
```

Convert IPVI to saturation using an explicit displacement model:

```text
S_w_ij(t) = clip(S_wc + IPVI_ij(t) * displacement_efficiency_ij, S_wc, 1 - S_orw)
```

Then calculate edge fractional flow from property evaluators:

```text
fw_ij(t) = fractional_flow(S_w_ij, p_cell_or_edge, pvt_region, sat_region)
```

Support at least two water-response options:

1. Native tabular SCAL/PVT fractional-flow response.
2. Optional pywaterflood Buckley-Leverett response if pywaterflood is installed and compatible with the selected simplification.

The native implementation is mandatory.

Producer watercut prediction:

```text
fw_hat_j(t) = aggregate_i(edge_response_ij(t - tau_ij))
```

A simple first implementation may use:

```text
fw_hat_j(t) = clip(
    fw_background_j + sum_i response_weight_ij(t) * fw_ij(t - tau_ij),
    0,
    1
)
```

The aggregation weights must depend on:

- `alpha_ij`
- `eta_ij`
- effective injection rate
- edge PV
- current edge saturation
- link type
- optional historical liquid rate

---

## 7. Calibration / history matching

The calibration engine must estimate:

- `alpha_ij`
- `eta_i` or `eta_ij`
- `tau_days`
- `pv_ij`
- `displacement_efficiency_ij`
- `breakthrough_ipvi_ij`
- selected fractional-flow multipliers, if configured
- pressure/material-balance parameters
- pore-volume and compressibility multipliers, if configured
- optional aquifer and intercell transmissibility parameters
- optional producer base watercut correction

Use constraints:

- `alpha_ij >= 0`
- `0 <= eta_i <= 1.5` or configurable
- `0 <= eta_ij <= 1.5` or configurable
- `tau_days > 0`
- `pv_ij > 0`
- for each injector, `sum_j alpha_ij <= 1.0` or normalized to 1.0 depending on config
- watercut predictions in `[0, 1]`
- pressure positive
- no invalid saturations

Use scipy optimization first. Add optional optuna for multi-start/global search.

Objective function:

```text
L = W_wc * L_watercut
  + W_p  * L_pressure
  + W_q  * L_rates
  + W_mb * L_material_balance
  + W_reg * L_regularization
```

Where:

- `L_watercut` compares observed and predicted producer watercut.
- `L_pressure` compares observed and predicted `p_res` by well/cell/region.
- `L_rates` optionally compares oil, water, and liquid rates.
- `L_material_balance` penalizes unrealistic cell volume imbalance and impossible voidage replacement.
- `L_regularization` penalizes deviations from distance, MRST, CRM, manual, and link-type priors.

Calibration must support:

- train/validation split by time;
- multi-start optimization;
- fixed parameters;
- parameter bounds from YAML config;
- reproducible random seed;
- exporting fitted parameters to JSON and Parquet;
- metrics per producer, injector, cell, and scenario.

Distance-based alpha is only a prior. The optimizer must be able to correct it when history data shows a better explanation.

Examples of behavior to capture:

- close producer but weak response: possible screen, low eta, high tau, bad connection;
- distant producer but fast watercut growth: possible channel/fracture, low PV, low tau;
- strong injection without pressure increase: low injection efficiency or out-of-pattern losses;
- pressure support without watercut growth: good pressure support before breakthrough;
- watercut growth without pressure support: channeling or small effective connected volume.

---

## 8. Input data contracts

### 8.1 wells.csv

Required:

- `well_id`
- `well_type`: `producer` or `injector`
- `x`
- `y`

Optional:

- `z`
- `cell_id`
- `region_id`
- `start_date`
- `end_date`
- `status`
- `trajectory_type`
- `heel_x`, `heel_y`, `toe_x`, `toe_y`

### 8.2 production.csv

Required:

- `date`
- `producer_id`
- `q_oil`
- `q_water`

Optional:

- `q_liq`; if missing, use `q_oil + q_water`
- `q_gas`
- `bhp`
- `thp`
- `p_res`
- `status`
- `measurement_quality`

### 8.3 injection.csv

Required:

- `date`
- `injector_id`
- `q_water_inj`

Optional:

- `bhp`
- `whp`
- `thp`
- `status`
- `measurement_quality`

### 8.4 cells.csv

Required for pressure/material-balance mode:

- `cell_id`
- `region_id`
- `pv`
- `ooip`
- `initial_pressure`
- `initial_sw`

Optional:

- `initial_so`
- `initial_sg`
- `ct`
- `aquifer_index`
- `area_m2`
- `h_m`
- `phi`
- `ntg`

### 8.5 connections.csv / connections_initial.csv

`init-connections` must generate `connections_initial.csv` with:

- `injector_id`
- `producer_id`
- `distance_m`
- `inside_influence_radius`
- `active`
- `link_type`
- `alpha_prior`
- `alpha_lower_bound`
- `alpha_upper_bound`
- `eta_prior`
- `tau_prior_days`
- `pv_prior`
- `prior_source`
- `prior_weight`
- `geometry_weight`
- `notes`

Manual `connections.csv` may override link type or priors, but the system must preserve the distance-based initialization diagnostics.

---

## 9. External tool integration

### 9.1 OPM Flow adapter

OPM Flow is optional and used as a high-fidelity simulator / validation source.

The OPM adapter must:

1. Run OPM Flow if the `flow` executable is available.
2. Import well rates, pressures, saturations, FIPNUM/region material-balance data if exported.
3. Import PROPS and REGIONS from OPM/Eclipse-style deck/include files where possible.
4. Support at least normalized equivalents of:
   - `DENSITY`
   - `PVTO` / `PVDO`
   - `PVTW`
   - `PVDG` / `PVTG`
   - `ROCK`
   - `SWOF` / `SGOF` or `SWFN` / `SGFN` / `SOF2` / `SOF3`
   - `PVTNUM` / `SATNUM` / `ROCKNUM` / `FIPNUM`
5. Compare proxy history match and forecast against OPM results when available.
6. Never require OPM for the base test suite.

Use `res2df`, `opm.io`, or similar libraries when available, but keep adapters optional.

### 9.2 MRST Flow Diagnostics adapter

MRST is optional and used for flow diagnostics priors.

The MRST adapter must:

1. Generate MATLAB/Octave script templates that use deck-based MRST workflows when available.
2. Import MRST-exported CSV files with:
   - `injector_id`
   - `producer_id`
   - `allocation_factor`
   - `time_of_flight_days`
   - `swept_volume`
   - `drainage_volume`
3. Map:
   - allocation factor -> `alpha_mrst_ij`
   - time-of-flight -> `tau_mrst_ij`
   - swept/drainage volume -> `pv_mrst_ij`
4. Never require MATLAB/MRST for the base Python tests.

### 9.3 pywaterflood adapter

pywaterflood is optional and used for CRM and simplified Buckley-Leverett calculations.

The adapter must:

1. Use pywaterflood CRM to estimate connectivities and time decays when installed.
2. Use pywaterflood Buckley-Leverett helpers only when compatible with simplified inputs.
3. Derive representative oil and water viscosities from the PVT evaluator at current or representative pressure.
4. Derive endpoints from SCAL tables when using a Corey approximation.
5. Prefer native tabular fractional-flow when full SCAL/PVT tables are available.
6. Gracefully fall back when pywaterflood is missing.

### 9.4 Prior blending

Distance-based initialization is mandatory. External tools refine it.

If multiple prior sources exist:

```text
score_ij =
    w_distance * alpha_distance_ij
  + w_mrst     * alpha_mrst_ij
  + w_crm      * alpha_crm_ij
  + w_manual   * alpha_manual_ij
```

Then normalize:

```text
alpha_prior_ij = score_ij / sum_j(score_ij)
```

Default:

```yaml
prior_blending:
  distance_weight: 0.60
  mrst_weight: 0.25
  crm_weight: 0.15
  manual_weight: 1.00
  manual_overrides_automatic: true
```

If MRST or CRM priors are unavailable, redistribute their weights to available sources.

---

## 10. CLI requirements

Create a CLI named `waterflood-proxy` with commands:

```bash
waterflood-proxy validate-data --data-dir data/ --config config.yaml
waterflood-proxy validate-properties --data-dir data/ --config config.yaml
waterflood-proxy import-opm-properties --deck data/model.DATA --out data/properties/
waterflood-proxy inspect-properties --data-dir data/ --config config.yaml
waterflood-proxy plot-pvt --data-dir data/ --config config.yaml --out outputs/pvt_plots/
waterflood-proxy plot-scal --data-dir data/ --config config.yaml --out outputs/scal_plots/
waterflood-proxy init-connections --data-dir data/ --config config.yaml --out data/connections_initial.csv
waterflood-proxy calibrate --data-dir data/ --config config.yaml --out outputs/
waterflood-proxy forecast --data-dir data/ --params outputs/fitted_parameters.json --scenarios scenarios.yaml --out outputs/
waterflood-proxy report --outputs outputs/ --lang ru
```

`validate-data` must call `validate-properties` when material balance or watercut modeling is enabled.

`init-connections` must:

1. Read wells and coordinates.
2. Validate coordinate system and units.
3. Build injector-producer candidates within 3000 m.
4. Calculate distance-based alpha priors.
5. Apply `screen` / `channel` / `normal` / `unknown` multipliers.
6. Estimate tau priors.
7. Estimate 1D edge PV priors.
8. Export `connections_initial.csv`.
9. Produce a network diagnostic plot.
10. Produce a distance/alpha heatmap.

---

## 11. Forecast scenarios

`scenarios.yaml` must support multiple forecast scenarios:

- scenario name;
- forecast start/end date;
- injection multipliers by well/date;
- explicit injection schedules;
- producer constraints;
- shut-ins;
- new wells or disabled wells;
- converted wells;
- changed injection efficiency assumptions;
- changed link status or link type;
- pressure constraints;
- property multiplier cases, if allowed;
- output aggregation level.

Forecast outputs:

- producer oil, water, liquid, gas rates where modeled;
- watercut;
- injector rates;
- effective injection by edge;
- pressure by cell/region/well;
- material balance by cell/region;
- cumulative oil/water/injection;
- scenario summary metrics.

---

## 12. Outputs

The package must produce:

```text
outputs/fitted_parameters.json
outputs/fitted_edges.parquet
outputs/history_match_timeseries.parquet
outputs/forecast_timeseries.parquet
outputs/material_balance_by_cell.parquet
outputs/scenario_summary.csv
outputs/report.html
outputs/plots/watercut_actual_vs_predicted_*.png
outputs/plots/p_res_actual_vs_predicted_*.png
outputs/plots/alpha_matrix_heatmap.png
outputs/plots/eta_by_injector.png
outputs/plots/link_type_diagnostics.png
outputs/plots/forecast_watercut_by_scenario.png
outputs/plots/forecast_pressure_by_scenario.png
outputs/plots/material_balance_by_cell.png
outputs/plots/pvt_*.png
outputs/plots/scal_*.png
```

The generated report must support Russian labels.

---

## 13. Validation rules

Strict validation is mandatory.

Coordinate validation:

- `x` and `y` required in meters.
- CRS required.
- Do not silently treat latitude/longitude as meters.
- Do not silently mix CRS.

Production data validation:

- Missing critical rates must fail unless explicitly configured.
- Negative impossible rates must fail unless status/operation explains them.
- Watercut must be computable for producers.

Property validation:

- `DENSITY` required for active phases.
- `PVTW` required if water is active.
- `PVTO` or `PVDO` required if oil is active.
- `PVDG` or `PVTG` required if gas is active.
- `ROCK` required for pressure/material-balance mode.
- `SWOF` or `SWFN` + `SOF2/SOF3` required for oil-water displacement.
- `SGOF` or `SGFN` + `SOF3` required if gas-oil displacement is active.
- `PVTNUM`, `SATNUM`, `ROCKNUM` mappings must be valid for all active cells/edges.
- Saturation tables must be monotonic in saturation.
- Relative permeability must be non-negative.
- Watercut predictions must remain in `[0, 1]`.
- Pressure must remain positive.
- Extrapolation disabled by default.

Calibration validation:

- constraints respected;
- parameters remain inside bounds;
- all outputs reproducible under fixed seed;
- loss components exported.

---

## 14. Tests / acceptance criteria

Implementation is acceptable when all these tests pass:

### Geometry

1. Producers outside 3000 m are excluded by default.
2. Producers inside 3000 m receive positive `alpha_prior`.
3. For each injector, active `alpha_prior` values sum to 1.0.
4. A closer producer receives a larger distance weight than a farther producer, all else equal.
5. `screen` lowers prior weight.
6. `channel` increases prior weight.
7. If all producers are outside radius, no strong artificial connection is created.
8. Calibration can override distance priors when history requires it.

### PVT / SCAL / ROCK

1. PVTW records are parsed into reference pressure, `Bw`, `Cw`, water viscosity, and water viscosibility.
2. PVTO-style live-oil data is parsed into `Rs`, pressure, `Bo`, and oil viscosity.
3. PVDG-style gas data is parsed into pressure, `Bg`, and gas viscosity.
4. DENSITY is parsed for oil, water, and gas surface densities.
5. ROCK is parsed into reference pressure and rock compressibility.
6. SWOF tables are parsed into `Sw`, `Krw`, `Krow`, and `Pcow`.
7. SGOF tables are parsed into `Sg`, `Krg`, `Krog`, and `Pcog`.
8. PVTNUM/SATNUM/ROCKNUM select the correct regional properties.
9. Material-balance pressure response changes when `Bo`, `Bw`, `Cw`, or rock compressibility changes.
10. 1D edge fractional-flow response changes when SCAL curves or viscosities change.
11. Missing production PVT/SCAL/ROCK data causes validation failure, not silent defaults.
12. Synthetic examples still run with explicitly declared toy PVT/SCAL tables.

### Model / calibration

1. Synthetic data generator creates a small model with known true alpha, eta, tau, PV, pressure parameters, and properties.
2. Calibration approximately recovers known alpha and eta values.
3. Calibration produces watercut and pressure metrics.
4. Forecast scenarios run from fitted parameters.
5. Reports and diagnostic plots are created.
6. Optional OPM/MRST/pywaterflood tests skip gracefully when dependencies are missing.

---

## 15. Engineering requirements

- Use type hints.
- Use pydantic models for configs and schemas.
- Use dataclasses or pydantic for parameter containers.
- Use vectorized numpy/pandas where practical.
- Keep functions small and testable.
- Add docstrings explaining reservoir-engineering assumptions.
- Unit handling must be explicit.
- Do not silently infer units.
- Do not silently fill missing critical data.
- Provide clear validation errors.
- Use reproducible random seeds.
- Save config snapshot with every calibration run.
- Save objective components and train/validation metrics.
- Keep external adapters isolated.
- Base tests must run offline and without external simulators.

---

## 16. Suggested implementation sequence

First inspect the repository. If it is empty, create the package from scratch.

Work in small, testable steps:

1. Create package skeleton, pyproject, schemas, config loader, and CLI stubs.
2. Implement coordinate validation and distance-based `init-connections`.
3. Implement PVT/SCAL/ROCK normalized table readers and validators.
4. Implement property evaluators: PVT, rock, relperm, fractional flow.
5. Implement graph model and 1D edge displacement.
6. Implement PVT-aware tank material balance and pressure model.
7. Implement simulator loop.
8. Implement objective function and scipy optimizer.
9. Implement synthetic data generator and tests.
10. Implement forecast scenario runner.
11. Implement reports and plots.
12. Add optional pywaterflood adapter.
13. Add MRST import adapter and MATLAB/Octave script template.
14. Add OPM/res2df adapters.
15. Add README and examples.

Before coding, provide a concise implementation plan. Then implement. After implementation, run tests and show results.
