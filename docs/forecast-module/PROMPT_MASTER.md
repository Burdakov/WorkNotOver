Ты - senior reservoir simulation / Python / UI developer. Нужно реализовать модуль автоматической адаптации модели на историю добычи, закачки, давлений и затем сделать генератор сценариев на основе набора внешних ограничений.

Система должна выполнять следующие действия по порядку:

1. На основе данных координат скважин и их перфораций создавать модель вокруг скважин в радиусе `3000 м` или другом значении, заданном пользователем. Модель формируется с полным набором исходных данных, получаемых из `Module A`. Модель содержит все необходимые ключевые слова, указанные в мануале из папки `references`. Так получается базовый вариант геометрии сетки с набором немодифицированных параметров.
2. Производится построение куба регионов с использованием внешней CRM-системы `pywaterflood`, определяющей первую догадку связности между добывающими и нагнетательными скважинами. На этой основе формируется единый для всей модели куб регионов `OPERNUM` / `connection_region_id`. Для каждой добывающей скважины формируется регион связи с нагнетательными скважинами.
3. Для каждого региона задаются переменные значения проницаемости, формы кривых относительных фазовых проницаемостей и порового объёма. Перебором достигается автоматическая адаптация пластового давления и обводнённости с установленными критериями точности. После настройки модель считается готовой для прогноза.
4. Прогнозы формируются сразу как минимум два: базовый расчёт, сформированный из технологического режима скважин как входной точки без каких-либо действий, и расчёт с ГТМ. Используются ГТМ с приростами из dataset `gtm` и датами из внешнего графика КРС, формируемой ветки `Сформировать график` или planner revision.
5. Формируемый в `Module D: KRS Optimizer` график КРС и соответствующий график ГТМ используются для формирования `SCHEDULE`; оптимизатор является итеративным генератором schedule-файла.

---

# Детализация пунктов 1-3

## Проверенные источники

Эта спецификация сверена с:

- `docs/contracts/core-data-model.md`;
- `docs/contracts/module-a-task-package.md`;
- `docs/contracts/module-b-forecast.md`;
- `docs/contracts/module-g-scenario-ui.md`;
- `docs/forecast-module/docs/OPM_FLOW_REFERENCE_GUIDE.md`;
- текущим кодом `backend/app/api/simulation.py`;
- текущим кодом `backend/app/api/scenarios.py`;
- текущими схемами `backend/app/services/opm_flow/schemas.py`;
- текущей реализацией `backend/app/services/opm_flow/field_2d.py`;
- текущим UI `frontend/src/ModuleGApp.vue`;
- импортом Module A в `backend/app/api/import_api.py` и `backend/app/services/importing/normalizers.py`.

Контрактное имя целевого production-метода: `forecast_method = opm_flow_blackoil`.
Текущая реализация использует переходный runtime-профиль `forecast_method = opm_flow_2d_field`. До миграции оба имени должны быть явно сопоставлены, но новые алгоритмы должны проектироваться как `opm_flow_blackoil`, где `opm_flow_2d_field` является MVP-профилем одного 2D field model.

## Текущее состояние кода

### Уже есть

- `Module A` умеет сохранять normalized datasets: `well_groups`, `well_trajectories`, `perforations`, `production_history`, `injection_history`, `pvt_properties`, `niz`.
- Scenario context хранит ссылки на эти datasets через `DatasetReference`.
- `Field2DModelService.prepare()` строит единый 2D grid, интерполирует перфорации по траекториям, активирует ячейки и формирует well/region diagnostics.
- `Field2DModelService.run()` создаёт `SimulationRun`, пишет `.DATA` и include-файлы, может запускать внешний `flow`, сохраняет JSON analysis.
- Case builder пишет ключевые секции `RUNSPEC`, `GRID`, `PROPS`, `REGIONS`, `SOLUTION`, `SCHEDULE`, `SUMMARY`.
- UI уже содержит сценарный контекст, настройки `field_2d_config`, запуск `field-2d/run-from-context`, просмотр grid cells, regions, artifacts и history-vs-calc diagnostics.

### Частично есть

- Радиус влияния настраивается, но default в коде/UI сейчас `1000 м`; целевой default для этой методики - `3000 м`.
- Куб регионов строится геометрически по ближайшим injector-producer парам, а не через `pywaterflood`.
- Есть `FIPNUM/SATNUM/ROCKNUM/PVTNUM`, но нет отдельного подтверждённого OPM keyword `OPERNUM`; поэтому `OPERNUM` должен быть WorkNotOver normalized cube, а deck обязан писать поддерживаемые OPM region arrays. Если `OPERNUM` подтверждён локальным manual, его можно добавить через guide-first change.
- Историческая адаптация сейчас эвристическая и однопроходная: меняются multipliers в памяти и JSON diagnostics, но нет полноценного итерационного контура `run -> import -> objective -> parameter update`.
- Importer raw OPM artifacts сейчас проверяет наличие файлов и пишет `import_report.json`, но не извлекает полноценно `UNSMRY/EGRID/INIT/UNRST/RFT` в normalized tables.

### Нет и нужно добавить

- Зависимость/adapter для `pywaterflood` и отдельный backend-контур CRM connectivity.
- Сущности `CrmConnectivityResult`, `RegionCube`, `RegionParameterSet`, `CalibrationIteration`, `CalibrationResult`.
- Генерацию `EDIT` include для `MULTPV`, `MULTX`, `MULTY`, `MULTZ`, `MULTREGT` или эквивалентных OPM-supported array edits.
- Генерацию region-specific SCAL через варианты `SWOF/SGOF` и `SATNUM`.
- Управляемый перебор параметров по регионам с критериями остановки.
- UI для матрицы CRM-связности, куба регионов, таблицы параметров регионов, журнала итераций и принятия калиброванной модели.

---

## Общий контракт входов для пунктов 1-3

`Module B` не читает raw Excel/CSV/YAML напрямую. Все входы приходят из `Module A` как `DatasetReference` или как нормализованные payloads, полученные по этим ссылкам.

Обязательные scenario-bound datasets:

| Dataset type | Назначение |
| --- | --- |
| `well_groups` | принадлежность скважин к `LU/SLOY/WellPad`, OPM group hierarchy, группировка результатов |
| `well_trajectories` | точки траекторий `well, md, x, y, z` для интерполяции перфораций и `COMPDAT` |
| `perforations` | интервалы `top_md/bottom_md`, active completions и связка со слоями |
| `production_history` | история нефти, воды, жидкости, газа, `BHP/THP`, пластового давления по добывающим |
| `injection_history` | история закачки воды/газа, `BHP/WHP/THP`, пластового давления по нагнетательным |
| `pvt_properties` или `reservoir_properties` | raw OPM include или структурированные PVT/SCAL/ROCK таблицы |
| `niz` | target pore-volume/OOIP sanity check и распределение начальных запасов по скважинам/регионам |

Опциональные, но целевые datasets/configs:

| Dataset/config | Назначение |
| --- | --- |
| `forecast_model_config` | grid resolution, default radius, фазовый режим, bounds адаптации, tolerances |
| `waterflood_connections_dataset` | сохранённая или ручная связность, если CRM нужно переиспользовать |
| `development_cells_dataset` | готовая сетка/ячейки, если Module A поставляет grid вместо генерации |
| `reservoir_properties_dataset` | структурированные PVT/SCAL/ROCK вместо raw include |

Основные инварианты:

- `well_name` должен совпадать во всех hydrodynamic datasets и сценарных datasets.
- Координатная система должна быть единой; `coordinate_crs` фиксируется в metadata dataset или строки.
- Все даты - ISO `YYYY-MM-DD`.
- Все дебиты неотрицательны и имеют согласованные единицы.
- Каждая перфорация должна попадать в активную ячейку.
- `pvt_properties.include_text` не должен теряться: raw include является evidence layer для deck.
- Любой generated fallback PVT/SCAL/ROCK допустим только при явном `allow_generated_pvt = true` и записывается в warnings.

---

## Пункт 1. Построение базовой OPM-модели вокруг скважин

### Цель

Построить inspectable OPM/Eclipse-compatible case с базовой геометрией и немодифицированными свойствами пласта. Результат пункта 1 не является прогнозом и не считается history matched model; это исходное состояние для CRM-регионов и адаптации.

### Backend algorithm

1. Загрузить scenario context:
   - получить `Scenario` по `scenario_id`;
   - извлечь `metadata.forecast_method`, `metadata.field_2d_config` или `metadata.opm_blackoil_config`;
   - загрузить normalized payloads по `DatasetReference`;
   - проверить обязательные datasets.

2. Нормализовать идентификаторы:
   - привести `well_name` к каноническому виду для runtime matching;
   - построить lookup `well_name -> group row`;
   - построить lookup `well_name -> trajectory points`;
   - построить lookup `well_name -> production/injection history`.

3. Определить тип скважины:
   - если скважина есть в `injection_history`, считать `well_type = injector`;
   - если скважина есть в `production_history`, считать `well_type = producer`;
   - если скважина есть в обоих потоках, использовать последнюю фактическую роль или явную роль из dataset/config, а конфликт писать в diagnostics.

4. Построить точки контакта с пластом:
   - для каждого perforation interval взять `top_md`, `center_md`, `bottom_md`;
   - интерполировать `x/y/z` по траектории;
   - если в перфорации есть explicit `x/y/z`, использовать их только как fallback;
   - сохранить `perforation_points[]` с `point_type`, `md`, `x/y/z`.

5. Построить границу модели:
   - взять все координаты скважин и perforation points;
   - применить пользовательский радиус `model_radius_m`, default `3000`;
   - граница `min_x/max_x/min_y/max_y` должна покрывать все активные перфорации плюс radius;
   - если есть `development_cells_dataset`, границу можно расширить до пересечения с готовыми ячейками.

6. Построить grid:
   - MVP: regular Cartesian 2D/one-layer grid с `nx, ny, nz=1`;
   - target: допускается multilayer/corner-point grid, если Module A поставляет `COORD/ZCORN` или структурированные cells;
   - `dx_m`, `dy_m`, `dz_m` берутся из config;
   - если `nx * ny * nz > max_grid_cells`, grid coarsening должен быть явным и записан в diagnostics;
   - каждая ячейка получает `i/j/k`, центр `x/y/z`, `ACTNUM`.

7. Назначить базовые свойства:
   - `PORO`, `PERMX`, `PERMY`, `PERMZ` из `reservoir_properties_dataset` или config;
   - `PRESSURE`, `SWAT`, `SGAS` из initialization inputs/config;
   - `PVTNUM`, `SATNUM`, `ROCKNUM`, `FIPNUM` default `1`, если нет region map;
   - `MULTPV = 1.0` на базовом шаге.

8. Активировать ячейки:
   - все ячейки с perforation points должны иметь `ACTNUM = 1`;
   - ячейки в пределах radius от скважин и будущих CRM corridors активируются;
   - inactive cells допускаются только вне области моделирования и не должны попадать в `COMPDAT`.

9. Сформировать OPM case:
   - root deck: `input/FIELD_2D_<SCENARIO>.DATA`;
   - includes:
     - `input/includes/runspec.inc`;
     - `input/includes/grid.inc`;
     - `input/includes/edit.inc`, если есть generated edits;
     - `input/includes/props.inc`;
     - `input/includes/regions.inc`;
     - `input/includes/init.inc`;
     - `input/includes/summary.inc`;
     - `input/includes/schedule.inc`.

10. Выполнить validation:
    - порядок deck sections валиден;
    - длины массивов равны `nx * ny * nz`;
    - каждая перфорация попала в active cell;
    - каждая `COMPDAT` completion попала в active cell;
    - `DIMENS` совпадает с grid arrays;
    - PVT/SCAL/ROCK keywords присутствуют или есть explicit generated fallback warning.

### OPM keyword contract

`RUNSPEC`:

- `TITLE`;
- `DIMENS`;
- `OIL`, `WATER`, `GAS` по включённым фазам;
- `METRIC` или другой единый unit system проекта;
- `TABDIMS`, `REGDIMS`, `WELLDIMS`, `SMRYDIMS`;
- `START`;
- при необходимости `UNIFOUT`, `UNIFOUTS`, `FMTOUT`.

`GRID`:

- `DX`, `DY`, `DZ` или `COORD/ZCORN` для corner-point grid;
- `TOPS`;
- `PORO`;
- `PERMX`, `PERMY`, `PERMZ`;
- `ACTNUM`.

`EDIT`:

- пустой или отсутствует на базовом шаге;
- после адаптации содержит `MULTPV`, `MULTX`, `MULTY`, `MULTZ`, `MULTREGT`, `EQUALS/MULTIPLY/BOX/ENDBOX`.

`PROPS`:

- `DENSITY`;
- `PVTW`;
- `PVDO` или `PVTO`;
- `PVDG` или `PVTG`, если включён gas phase;
- `ROCK`;
- `SWOF`;
- `SGOF` или поддерживаемые альтернативы.

`REGIONS`:

- `PVTNUM`;
- `SATNUM`;
- `ROCKNUM`;
- `FIPNUM`;
- `EQLNUM`, если используется equilibration by region.

`SOLUTION`:

- `PRESSURE`, `SWAT`, `SGAS`;
- или `EQUIL`, если выбран equilibrium initialization.

`SCHEDULE`:

- `RPTRST`, `RPTSCHED`;
- `WELSPECS`;
- `COMPDAT`;
- `WCONPROD`;
- `WCONINJE`;
- `DATES`;
- `END`.

`SUMMARY`:

- field vectors: `FOPR`, `FOPT`, `FWPR`, `FWPT`, `FGPR`, `FGPT`, `FWIR`, `FWIT`;
- well vectors: `WOPR`, `WWPR`, `WGPR`, `WLPR`, `WBHP`, `WWCT`, `WGOR`;
- pressure/material balance vectors, если они нужны для calibration objective.

### Backend interface

Existing compatible endpoint:

```text
POST /api/forecast/opm-flow/scenarios/{scenario_id}/field-2d/prepare-from-context
```

Target endpoint:

```text
POST /api/forecast/opm-flow/scenarios/{scenario_id}/model/prepare
```

Request:

```json
{
  "forecast_method": "opm_flow_blackoil",
  "model_radius_m": 3000,
  "grid": {
    "mode": "cartesian_2d",
    "dx_m": 150,
    "dy_m": 150,
    "dz_m": 5,
    "max_grid_cells": 60000
  },
  "initial_state": {
    "pressure_bar": 220,
    "swat": 0.30,
    "sgas": 0.04,
    "top_depth_m": 2000,
    "datum_depth_m": 2000
  },
  "pvt_policy": {
    "allow_generated_pvt": false,
    "append_missing_props_with_warning": true
  },
  "summary_vectors": ["FOPR", "FWPR", "FWIR", "WOPR", "WWPR", "WBHP", "WWCT"]
}
```

Response:

```json
{
  "scenario_id": "string",
  "model_id": "string",
  "simulation_run": {
    "run_id": "string",
    "status": "case_built",
    "case_root": "storage/simulation_runs/..."
  },
  "geometry": {
    "nx": 1,
    "ny": 1,
    "nz": 1,
    "cell_count": 1,
    "active_cell_count": 1,
    "model_radius_m": 3000
  },
  "wells": [],
  "perforation_points": [],
  "validation": {
    "is_valid": true,
    "warnings": [],
    "errors": []
  },
  "artifacts": []
}
```

### UI contract

В `Module G`, узел `Module B: Forecast` должен иметь panel `Модель`:

- selector сценария и метод `OPM Flow black-oil`;
- status cards по datasets: `well_groups`, `well_trajectories`, `perforations`, `production_history`, `injection_history`, `pvt_properties`, `niz`;
- numeric controls:
  - `model_radius_m`, default `3000`;
  - `dx_m`, `dy_m`, `dz_m`;
  - `max_grid_cells`;
  - `initial_pressure_bar`, `SWAT`, `SGAS`;
  - `top_depth_m`, `datum_depth_m`;
  - `run_external_flow`;
- кнопка `Подготовить модель`;
- grid preview:
  - карта активных/inactive cells;
  - скважины и перфорации;
  - coverage summary;
- deck artifacts browser:
  - root `.DATA`;
  - include-файлы;
  - validation warnings.

---

## Пункт 2. CRM-связность и единый куб регионов

### Цель

Получить первую физически осмысленную догадку связности между нагнетательными и добывающими скважинами через `pywaterflood`, затем превратить её в единый cell-level region cube для всей модели.

### Важное правило по OPERNUM

В `PROMPT_MASTER` используется термин `OPERNUM`. В текущем локальном `OPM_FLOW_REFERENCE_GUIDE.md` подтверждены `FIPNUM`, `SATNUM`, `PVTNUM`, `ROCKNUM`, но не подтверждён `OPERNUM`. Поэтому:

- внутри WorkNotOver создаётся normalized cube `opernum` / `connection_region_id`;
- OPM deck обязательно получает поддерживаемые массивы `FIPNUM/SATNUM/ROCKNUM/PVTNUM`;
- если локальный manual подтверждает `OPERNUM`, добавление keyword выполняется через обновление `OPM_FLOW_REFERENCE_GUIDE.md` и только потом через runtime-code.

### Backend algorithm

1. Подготовить aligned history matrices:
   - выбрать history window для CRM;
   - привести production и injection history к общему daily/monthly timestep;
   - для добывающих сформировать `q_oil`, `q_water`, `q_liq`, `watercut`, `p_res/bhp`;
   - для нагнетательных сформировать `q_water_inj` и pressure controls;
   - заполнение пропусков выполнять только по явной policy: `zero`, `ffill`, `drop_period`.

2. Сформировать candidate injector-producer pairs:
   - ограничить пары радиусом `model_radius_m` или отдельным `crm_radius_m`;
   - исключить пары с разными `LU/SLOY`, если config запрещает cross-layer connectivity;
   - добавить distance, azimuth, overlap score по perforation depth/layer;
   - если user/manual connections заданы, использовать их как hard или soft prior.

3. Запустить `pywaterflood` через adapter:
   - adapter получает matrices `injector_rates[t, i]`, `producer_rates[t, p]`, optional pressure vectors и candidate mask;
   - adapter возвращает connectivity weights `alpha[i, p]`, time constants `tau_days[i, p]`, quality metrics;
   - все library-specific вызовы изолируются в `PywaterfloodCrmAdapter`, чтобы API библиотеки не протекал в Module B schemas.

4. Постобработать связность:
   - отрицательные weights запрещены;
   - weights ниже `min_connection_weight` отбрасываются;
   - для каждого producer weights нормируются так, чтобы сумма активных injection weights была `1.0`, если есть хотя бы одна связь;
   - если `pywaterflood` не вернул связь для producer, fallback policy:
     - `nearest_injectors` с warning;
     - или `unconnected_producer` и blocking warning, если fallback запрещён.

5. Сформировать region table:
   - `producer_region_id` - основной регион связи для добывающей скважины;
   - `connection_id = injector:producer` - диагностический sub-connection;
   - сохранить `alpha`, `tau_days`, `distance_m`, `prior_source`, `crm_quality`, `manual_override`.

6. Построить cube:
   - один cube на всю модель, dimensions равны OPM grid;
   - каждая active cell получает:
     - `opernum` / `connection_region_id`;
     - `producer_region_id`;
     - `dominant_injector_name`;
     - `crm_weight`;
     - `FIPNUM`;
     - `SATNUM`;
     - `ROCKNUM`;
     - `PVTNUM`.
   - алгоритм allocation:
     - cells вокруг producer получают producer region;
     - corridors от injector к producer строятся по line-segment distance или более точной flow-diagnostic геометрии;
     - при пересечении нескольких corridors выбирается максимальный weighted score `alpha / distance_to_corridor`;
     - well-region cells имеют приоритет над corridor cells.

7. Сформировать deck region arrays:
   - `REGIONS` получает `FIPNUM/SATNUM/ROCKNUM/PVTNUM`;
   - optional `EDIT` получает region edit boxes/multipliers только после пункта 3;
   - normalized outputs сохраняют полный `opernum` cube независимо от того, пишется ли OPM keyword.

8. Записать diagnostics:
   - coverage by producer;
   - unconnected producers/injectors;
   - filtered connections;
   - CRM fit metrics;
   - fallback events.

### Backend interface

Target endpoint:

```text
POST /api/forecast/opm-flow/scenarios/{scenario_id}/crm-connectivity
```

Request:

```json
{
  "run_id": "optional-prepared-run-id",
  "history_window": {
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
    "frequency": "month"
  },
  "crm": {
    "engine": "pywaterflood",
    "radius_m": 3000,
    "min_connection_weight": 0.03,
    "max_connections_per_producer": 8,
    "allow_cross_lu": false,
    "allow_cross_sloy": false,
    "fallback_policy": "nearest_injectors"
  }
}
```

Response:

```json
{
  "scenario_id": "string",
  "run_id": "string",
  "connectivity": [
    {
      "connection_id": "INJ:PROD",
      "injector_name": "INJ",
      "producer_name": "PROD",
      "producer_region_id": 101,
      "alpha": 0.42,
      "tau_days": 90,
      "distance_m": 1400,
      "source": "pywaterflood",
      "quality": {
        "rmse": 0.12,
        "r2": 0.78
      }
    }
  ],
  "region_cube": {
    "nx": 1,
    "ny": 1,
    "nz": 1,
    "cube_path": "storage/.../normalized/region_cube.json",
    "arrays": ["opernum", "fipnum", "satnum", "rocknum", "pvtnum"]
  },
  "diagnostics": {
    "unconnected_producers": [],
    "fallback_connections": [],
    "warnings": []
  }
}
```

Target endpoint для явного перестроения cube из сохранённой связности:

```text
POST /api/forecast/opm-flow/scenarios/{scenario_id}/region-cube/build
```

Request:

```json
{
  "run_id": "string",
  "connectivity_result_id": "string",
  "allocation": {
    "corridor_width_m": 225,
    "well_region_radius_m": 150,
    "producer_region_mode": "one_region_per_producer",
    "store_pair_subregions": true
  }
}
```

### UI contract

В `Module B: Forecast` должен быть panel `CRM и регионы`:

- controls:
  - `CRM radius`;
  - timestep `day/month`;
  - `min_connection_weight`;
  - `max_connections_per_producer`;
  - toggles `cross-LU`, `cross-SLOY`;
  - fallback policy;
- action `Рассчитать CRM`;
- connectivity matrix:
  - rows: producers;
  - columns: injectors;
  - cell value: `alpha`;
  - tooltip: `tau_days`, distance, quality;
- map:
  - wells;
  - injector-producer links;
  - cell-level `opernum`/`FIPNUM` cube;
  - switch between `opernum`, `fipnum`, `satnum`, `rocknum`, `pvtnum`;
- editable connection table:
  - enable/disable pair;
  - manual weight override;
  - lock pair before calibration;
- diagnostics:
  - unconnected producers;
  - fallback links;
  - CRM quality summary;
  - number of regions and active cells by region.

---

## Пункт 3. Региональная адаптация на историю

### Цель

Автоматически подобрать региональные multipliers и формы SCAL-кривых так, чтобы модель воспроизводила историю пластового давления и обводнённости в заданных tolerances. После успешной адаптации case получает статус `calibrated` / `ready_for_forecast`.

### Настраиваемые параметры региона

Каждый `producer_region_id` или `connection_region_id` имеет `RegionParameterSet`:

```json
{
  "region_id": 101,
  "permx_multiplier": 1.0,
  "permy_multiplier": 1.0,
  "permz_multiplier": 1.0,
  "transmissibility_multiplier": 1.0,
  "pv_multiplier": 1.0,
  "satnum": 101,
  "swof_shape": {
    "swc": 0.18,
    "sorw": 0.15,
    "krw_end": 1.0,
    "kro_end": 1.0,
    "nw": 2.0,
    "no": 2.0
  },
  "sgof_shape": {
    "sgc": 0.0,
    "sorg": 0.10,
    "krg_end": 1.0,
    "krog_end": 1.0,
    "ng": 2.0,
    "nog": 2.0
  }
}
```

Parameter bounds:

- `permx/permy multiplier`: `0.05 .. 20.0`;
- `permz multiplier`: `0.01 .. 10.0`;
- `transmissibility multiplier`: `0.05 .. 20.0`;
- `pv_multiplier`: `0.05 .. 500.0`;
- Corey exponents `nw/no/ng/nog`: `0.5 .. 8.0`;
- endpoints `kr*_end`: `0.05 .. 1.0`;
- residual saturations must preserve physical ordering: `0 <= swc < 1 - sorw`, `0 <= sgc < 1 - sorg`.

### Objective function

Для каждой итерации импортируются расчётные time series и считается objective:

```text
objective =
  pressure_weight * normalized_rmse(p_res_fact, p_res_calc)
  + watercut_weight * rmse(watercut_fact, watercut_calc)
  + rate_weight * normalized_rmse(q_liq_fact, q_liq_calc)
  + regularization_weight * parameter_distance_from_base
```

Default criteria:

- `abs(p_res_fact - p_res_calc) <= pressure_tolerance_bar`, default `5 bar`;
- `abs(watercut_fact - watercut_calc) <= watercut_tolerance_fraction`, default `0.03`;
- optional `q_liq_error <= rate_tolerance_fraction`, default `0.10`;
- at least `min_history_coverage_fraction` of valid dates per calibrated producer.

### Backend algorithm

1. Создать calibration run:
   - взять prepared case из пункта 1;
   - взять region cube из пункта 2;
   - создать `SimulationRun` или child calibration run;
   - сохранить base `RegionParameterSet`.

2. Сформировать baseline simulation:
   - записать deck без regional edits или с current params;
   - запустить `flow`;
   - импортировать `UNSMRY/SMSPEC/UNRST/INIT/EGRID` в normalized tables;
   - если `flow` недоступен, calibration не должна помечаться successful; допускается только diagnostic fallback.

3. Посчитать baseline objective:
   - сопоставить `W*` summary vectors с original well names;
   - агрегировать well metrics до region metrics;
   - записать `CalibrationIteration(iteration=0)`.

4. Запустить перебор:
   - использовать deterministic coordinate search как базовый backend без внешней optimizer dependency;
   - для каждого региона и семейства параметров генерировать candidates вокруг текущего значения:
     - coarse factors: `[0.5, 0.75, 1.0, 1.25, 1.5, 2.0]`;
     - после улучшения shrink factor: `[0.85, 0.95, 1.0, 1.05, 1.15]`;
   - порядок подбора:
     1. `pv_multiplier` для pressure/material balance;
     2. `permx/permy/transmissibility` для injectivity/productivity and pressure response;
     3. `SWOF/SGOF shape` через `SATNUM` variants для watercut/GOR;
     4. optional well controls только если region params исчерпали bounds.

5. Для каждого candidate:
   - записать новый `edit.inc`, `props.inc`, `regions.inc`;
   - запустить `flow`;
   - импортировать results;
   - посчитать objective;
   - сохранить iteration record, artifacts и logs.

6. Правило принятия:
   - candidate принимается, если objective улучшился минимум на `min_objective_improvement`;
   - если ухудшился, параметры откатываются к best-known set;
   - если регион уже within tolerance, он может быть frozen.

7. Правило остановки:
   - все calibrated regions within tolerances;
   - достигнут `max_iterations`;
   - улучшение меньше `min_objective_improvement` за `patience` итераций;
   - OPM errors или invalid deck превышают `max_failed_candidates`.

8. Зафиксировать calibrated model:
   - `SimulationRun.metadata.calibration_status = calibrated | partial | failed`;
   - сохранить best parameter set;
   - записать final deck artifacts;
   - записать `field/region/well time series`;
   - downstream forecast может стартовать только от `calibrated` или `partial` при explicit user override.

### Deck generation for calibrated params

`EDIT`:

- `MULTPV` array или `MULTIPLY/BOX` edits по region cells;
- `MULTX/MULTY/MULTZ` или `MULTREGT` для transmissibility/permeability effects;
- каждое изменение должно быть traceable в normalized diagnostics.

`PROPS`:

- для каждого unique SCAL variant генерировать набор `SWOF/SGOF`;
- `SATNUM` в `REGIONS` указывает, какой вариант SCAL применён к cell;
- generated SCAL tables должны хранить исходные Corey-параметры в `CalibrationResult`.

`REGIONS`:

- `FIPNUM` сохраняет material balance region;
- `SATNUM` меняется при изменении SCAL формы;
- `ROCKNUM` меняется, если требуется region-specific rock compressibility;
- `PVTNUM` меняется только если PVT реально region-specific.

`SOLUTION`:

- region pressure shifts допустимы только как explicit calibration option;
- по умолчанию давление адаптируется через PV/permeability/transmissibility/SCAL, а не скрытой перезаписью фактического давления.

### Backend interface

Target endpoint:

```text
POST /api/forecast/opm-flow/scenarios/{scenario_id}/calibration/start
```

Request:

```json
{
  "run_id": "prepared-or-region-cube-run-id",
  "connectivity_result_id": "string",
  "history_window": {
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
    "frequency": "month"
  },
  "criteria": {
    "pressure_tolerance_bar": 5,
    "watercut_tolerance_fraction": 0.03,
    "rate_tolerance_fraction": 0.10,
    "min_history_coverage_fraction": 0.70
  },
  "objective_weights": {
    "pressure": 0.45,
    "watercut": 0.35,
    "rate": 0.20,
    "regularization": 0.05
  },
  "search": {
    "method": "coordinate_grid",
    "max_iterations": 60,
    "patience": 8,
    "min_objective_improvement": 0.005,
    "max_failed_candidates": 10
  },
  "parameter_bounds": {
    "permeability_multiplier": [0.05, 20],
    "pv_multiplier": [0.05, 500],
    "corey_exponent": [0.5, 8]
  },
  "run_external_flow": true
}
```

Response:

```json
{
  "calibration_id": "string",
  "scenario_id": "string",
  "run_id": "string",
  "status": "running",
  "current_iteration": 0,
  "best_objective": null,
  "criteria": {},
  "artifacts": []
}
```

Status endpoint:

```text
GET /api/forecast/opm-flow/scenarios/{scenario_id}/calibration/{calibration_id}
```

Response:

```json
{
  "calibration_id": "string",
  "status": "calibrated",
  "best_run_id": "string",
  "best_objective": 0.18,
  "regions_within_tolerance": 42,
  "regions_total": 45,
  "iterations": [
    {
      "iteration": 12,
      "region_id": 101,
      "changed_parameters": {"pv_multiplier": 1.4},
      "objective": 0.18,
      "pressure_rmse_bar": 3.8,
      "watercut_rmse_fraction": 0.024,
      "accepted": true,
      "run_id": "string"
    }
  ],
  "best_parameters_path": "storage/.../normalized/region_parameters_best.json",
  "diagnostics_path": "storage/.../normalized/calibration_report.json"
}
```

Promotion endpoint:

```text
POST /api/forecast/opm-flow/scenarios/{scenario_id}/calibration/{calibration_id}/promote
```

Effect:

- marks calibrated run as ready for forecast;
- writes `metadata.calibrated_run_id`;
- stores calibrated parameter set in scenario result/source payload;
- enables scenario forecast generation for points 4-5.

### UI contract

В `Module B: Forecast` должен быть panel `Адаптация`:

- controls:
  - history window;
  - pressure/watercut/rate tolerances;
  - objective weights;
  - max iterations;
  - candidate search mode;
  - toggles for parameter families: `PV`, `PERM`, `TRANSMISSIBILITY`, `SCAL`;
- region parameter table:
  - `region_id`;
  - producer;
  - injectors;
  - `pv_multiplier`;
  - `perm_multiplier`;
  - `satnum`;
  - Corey params;
  - bounds;
  - freeze checkbox;
- action buttons:
  - `Запустить адаптацию`;
  - `Остановить`;
  - `Принять лучшую модель`;
- iteration log:
  - iteration number;
  - changed region;
  - changed parameters;
  - objective;
  - accepted/rejected;
  - run status;
- plots:
  - pressure fact vs calc;
  - watercut fact vs calc;
  - liquid/oil fact vs calc;
  - objective over iterations;
- map:
  - color by pressure error;
  - color by watercut error;
  - color by accepted parameter multiplier;
- final status:
  - `not_started`;
  - `running`;
  - `calibrated`;
  - `partial`;
  - `failed`;
  - `ready_for_forecast`.

---

## Unified normalized outputs for points 1-3

Every run must write:

```text
run_manifest.json
input/FIELD_2D_<SCENARIO>.DATA
input/includes/runspec.inc
input/includes/grid.inc
input/includes/edit.inc
input/includes/props.inc
input/includes/regions.inc
input/includes/init.inc
input/includes/summary.inc
input/includes/schedule.inc
output/stdout.txt
output/stderr.txt
normalized/field_2d_analysis.json
normalized/grid_static.json
normalized/grid_dynamic.json
normalized/region_cube.json
normalized/crm_connectivity.json
normalized/region_parameters_initial.json
normalized/region_parameters_best.json
normalized/calibration_iterations.json
normalized/calibration_report.json
normalized/well_timeseries.json
normalized/field_timeseries.json
normalized/region_timeseries.json
```

Expected OPM raw output families after actual `flow` run:

- `EGRID`;
- `INIT`;
- `SMSPEC`;
- `UNSMRY` or segmented `S*`;
- `UNRST` or segmented `X*`;
- `PRT`;
- `DBG` or logs when available.

Downstream modules must consume normalized results and `SimulationRun` metadata, not repeat forecast math in UI.

---

## Acceptance checklist for points 1-3

1. Scenario validation blocks run if required hydrodynamic datasets are missing.
2. Model radius default is `3000 м`, user can override it and the value is saved in scenario metadata.
3. Every perforation top/center/bottom maps to an active cell.
4. Root `.DATA` references every include file.
5. `RUNSPEC/GRID/PROPS/REGIONS/SOLUTION/SCHEDULE/SUMMARY` are present and ordered according to `OPM_FLOW_REFERENCE_GUIDE.md`.
6. PVT/SCAL/ROCK comes from scenario-bound input or explicit generated fallback warning.
7. CRM connectivity is produced by `pywaterflood` adapter or explicit fallback policy.
8. One model-wide region cube is created; no separate model per injector-producer pair.
9. `opernum` normalized cube is stored; OPM deck stores supported region arrays.
10. Each calibrated region has traceable parameter values and bounds.
11. Calibration objective includes pressure and watercut at minimum.
12. Every candidate iteration has run artifacts, objective, accepted/rejected flag and diagnostics.
13. A model is marked `ready_for_forecast` only after criteria are met or user explicitly accepts partial calibration.
14. UI shows model geometry, CRM matrix, region cube, calibration status and OPM artifacts from backend results.
15. Existing legacy/reduced-order logic must not be used as a hidden substitute for OPM Flow history matching.
