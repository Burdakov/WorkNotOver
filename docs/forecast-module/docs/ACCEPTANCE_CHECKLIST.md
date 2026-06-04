# Acceptance checklist

## Geometry and initial alpha

- [ ] `wells.csv` requires `x`, `y`, and coordinate config.
- [ ] Producers inside 3000 m get positive alpha prior.
- [ ] Producers outside 3000 m are excluded by default.
- [ ] Active alpha priors sum to 1 per injector.
- [ ] Screen links reduce prior weight.
- [ ] Channel links increase prior weight.
- [ ] Empty injector neighborhoods do not create strong artificial links.
- [ ] `connections_initial.csv` is exported.
- [ ] Network plot and alpha heatmap are exported.

## PVT / SCAL / ROCK

- [ ] Production runs fail if required PVT/SCAL/ROCK data is missing.
- [ ] DENSITY is parsed.
- [ ] PVTW is parsed.
- [ ] PVTO/PVDO-style oil PVT is parsed.
- [ ] PVDG/PVTG-style gas PVT is parsed if gas is active.
- [ ] ROCK is parsed.
- [ ] SWOF/SGOF or SWFN/SGFN/SOF tables are parsed.
- [ ] PVTNUM/SATNUM/ROCKNUM/FIPNUM equivalents select correct region properties.
- [ ] No silent extrapolation.
- [ ] PVT/SCAL changes alter fractional flow and material-balance response.

## Model and calibration

- [ ] 1D edge model tracks IPVI and saturation.
- [ ] Watercut uses SCAL/PVT fractional flow.
- [ ] Pressure uses PVT-aware material balance.
- [ ] Calibration estimates alpha, eta, tau, PV, displacement, and pressure parameters.
- [ ] Calibration can override geometric priors.
- [ ] Fitted parameters are exported.
- [ ] Train/validation metrics are exported.

## Forecast and reporting

- [ ] Scenario YAML supports injection/production changes, shut-ins, link changes, and constraints.
- [ ] Forecast outputs are written to Parquet/CSV.
- [ ] HTML report is generated.
- [ ] Russian labels are supported.

## External adapters

- [ ] OPM adapter is optional.
- [ ] MRST adapter is optional.
- [ ] pywaterflood adapter is optional.
- [ ] Tests skip gracefully when external tools are unavailable.
