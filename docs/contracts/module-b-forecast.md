# Контракт Module B

## Модуль

`Module B: Waterflood proxy forecast, history matching и расчёт добычи`

## Назначение

`Module B` владеет расчётной логикой прогноза добычи нефти, воды, жидкости, газа, `GOR`, обводнённости, пластового давления и material-balance diagnostics.
Модуль формирует `ProductionScenario`, `WellForecastResult[]`, scenario-level результаты калибровки и совместимые outputs для downstream-модулей.

## Методические исходники для новой версии

Исходные материалы для проектирования новой версии прогнозного ядра вынесены в отдельную папку:

- `docs/forecast-module/README.md`
- `docs/forecast-module/PROMPT_MASTER.md`
- `docs/forecast-module/AGENTS.md`
- `docs/forecast-module/docs/MVP_PROMPTS.md`
- `docs/forecast-module/docs/ACCEPTANCE_CHECKLIST.md`
- `docs/forecast-module/docs/EXTERNAL_REFERENCES.md`
- `docs/forecast-module/config.example.yaml`
- `docs/forecast-module/scenarios.example.yaml`
- `docs/forecast-module/data_templates/`
- `docs/forecast-module/scripts/mrst_export_flow_diagnostics_template.m`

Эти документы являются основным методическим источником для новой версии `Module B`.
Они описывают proxy-модель заводнения с закачкой, материальным балансом, пластовым давлением, насыщенностью, PVT/SCAL/ROCK-свойствами, injector-producer participation coefficients и history matching.

Текущий контракт фиксирует согласованный целевой интерфейс `Module B`, обязательные scenario-level outputs и правила совместимости с `Module C`, `Module D`, `Module E`, `Module F` и `Module G`.
Сущности, необходимые для этой методики, закреплены в `core-data-model.md`.

Основной контрактный метод расчёта:

- `forecast_method = waterflood_proxy_hm`
- directed waterflood graph: нагнетательные скважины -> добывающие скважины;
- первичная injector-producer связность строится по координатам скважин и радиусу влияния 3000 м;
- каждая активная связь является 1D proxy-edge с `alpha`, `eta`, `tau`, `PV`, `IPVI`, насыщенностью и fractional-flow response;
- свойства флюидов, породы и SCAL берутся из явных PVT/SCAL/ROCK таблиц, совместимых по смыслу с OPM/Eclipse deck conventions;
- пластовое давление рассчитывается через PVT-aware material balance по cell/region;
- обводнённость рассчитывается через SCAL/PVT fractional flow от насыщенности;
- калибровка подбирает coefficients/parameters по истории добычи, закачки, обводнённости, `p_res`, rates и material balance;
- forecast scenarios применяют изменения закачки, добывающие ограничения, shut-ins, conversions, link changes и pressure constraints.

Legacy-режим совместимости:

- базовый контроль прогноза ведётся по жидкости;
- расчётный шаг прогноза является посуточным;
- если пользователь явно не задал иной горизонт сценария, расчёт по умолчанию ведётся от даты запуска сценария до `31 декабря` следующего календарного года; например, для сценария, запущенного `26 апреля 2026 года`, горизонт по умолчанию заканчивается `31 декабря 2027 года`;
- нефть считается расчётно от жидкости через обводнённость;
- для базового фонда используется последний фактический режим и кривая снижения жидкости;
- эффект ГТМ сначала влияет на жидкость, а нефть пересчитывается уже из новой жидкости и новой обводнённости;
- для новых скважин (`New wells`) liquid increment применяется по той же логике, что и для `Base`: на дату события к жидкости на дату прибавляется `expected_liquid_increment`; для события запуска этот инкремент может быть равен стартовому дебиту, если так задано входными сценарными данными.
- если в `wells` dataset отсутствуют новые скважины, но они присутствуют в `gtm`, `Module B` обязан синтезировать для них прогнозные `WellState` внутри сценарного расчета и считать их как `New wells` от даты соответствующего GTM-события.

Legacy-режим должен быть явно обозначен как `forecast_method = legacy_decline_liquid` в scenario metadata/result metadata и не должен подменять основную методику `waterflood_proxy_hm`.

## Входы

Обязательные входы для основной методики `forecast_method = waterflood_proxy_hm`:

- `NormalizedWellDataset` со скважинами `producer` и `injector`, координатами `x/y`, `cell_id`/`region_id` при наличии и явной координатной системой;
- `ProductionHistoryDataset`;
- `InjectionHistoryDataset`;
- `DevelopmentCellDataset`;
- `ReservoirPropertyDataset` с PVT/SCAL/ROCK tables и `RegionMap`;
- `ForecastModelConfig`;
- `ForecastScenarioDefinition[]`;
- optional `WaterfloodConnectionOverrideDataset`;
- optional `NormalizedGtmDataset` / `KrsScheduleScenario` / `PlannerScheduleRevision`, приведённые к forecast events;
- optional `NizDataset` для совместимости с текущей сценарной моделью и экономическими/отчётными разрезами.

Входы legacy-режима `forecast_method = legacy_decline_liquid`:

- `NormalizedWellDataset`
- `NizDataset`
- `NormalizedGtmDataset`
- `DisplacementConfig`
- `DeclineConfig`
- при пересчёте из planner: `PlannerScheduleRevision` из `Module F`; `Module G` может инициировать такой пересчёт, но planner revision читается из `Planner`

Шаблоны и смысл дополнительных входов описаны в `docs/forecast-module/PROMPT_MASTER.md`, `docs/forecast-module/config.example.yaml` и `docs/forecast-module/data_templates/`.

Перед запуском расчета `Module B` сценарий должен пройти проверку полноты входов.
Для `waterflood_proxy_hm` отсутствие координат, production history, injection history, development cells, PVT/SCAL/ROCK properties или forecast config должно блокировать расчёт.
Если у сценария с `external_krs_schedule` есть скважины, которые отсутствуют в `NormalizedWellDataset` или `NormalizedGtmDataset`, такой сценарий считается недозаполненным и в расчет не допускается.
Для `legacy_decline_liquid` или сценариев, где `metadata.requires_niz = true`, отсутствие scenario-bound dataset типа `niz` или отсутствие значений `NIZ` для всех релевантных скважин считается недозаполненностью и в расчет не допускается.
При этом неполнота `NIZ` должна маркироваться как проблема узла `NIZ`, а не автоматически как дефект самого `wells` dataset.

## Выходы

- `ProductionScenario`
- `WellForecastResult[]`
- `ScenarioProductionSummary`
- `CalibrationResult`
- `WaterfloodAnalysisPayload` для UI/diagnostics
- fitted injector-producer connections / fitted edges
- history match time series
- material balance by cell / region
- scenario summary metrics
- diagnostic artifacts: alpha heatmap, network diagnostics, watercut/pressure plots, report metadata
- рассчитанные инкременты по мероприятиям
- автоматически сформированный связанный сценарий без GTM с именем `чистая База`, если исходный сценарий рассчитывался с GTM-входом

`WellForecastResult` в текущем контракте должен быть пригоден не только для downstream-расчётов, но и для UI-агрегации раздела `Добыча`, поэтому как минимум обязан нести:

- `well_id`
- `well_name`
- `fund_type`
- `fund_state`
- `lu_id`
- `sloy_id`
- `well_pad_id`
- `development_cell_id`
- `region_id`
- `forecast_method`
- `calibration_status`
- профиль `ProductionPoint[]`

`ProductionPoint[]` должен содержать посуточные `oil_rate`, `water_rate`, `liquid_rate`, `gas_rate`, `watercut`, `GOR`, `reservoir_pressure` при наличии, насыщенности и material-balance diagnostics, чтобы UI раздела `Добыча` мог без пересчёта forecast math агрегировать их в дневные, месячные и годовые buckets и отображать анализ разработки.

`WaterfloodAnalysisPayload` должен быть сохранённым scenario-bound diagnostic payload и включать:

- `model`: методика, режим, радиус влияния, степень distance kernel, координатная система и property mode;
- `calibration`: статус, objective до/после адаптации, количество итераций, train/validation metrics, warnings;
- `cells[]`: `cell_id`, `lu_id`, `sloy_id`, `well_pad_id`, начальные/остаточные запасы, pore volume, добывающие/нагнетательные counts, rates факт/расчёт, `pressure_actual`, `pressure_calc`, `Sw`, `So`, `Sg`;
- `wells[]`: добывающие и нагнетательные скважины с координатами, ролью, ячейкой, rates факт/расчёт, `watercut_actual`, `watercut_calc`, `pressure_actual`, `pressure_calc`, запасами при наличии;
- `links[]`: directed injector-producer edges с `injector_id`, `producer_id`, `distance_m`, `alpha_prior`, fitted `alpha`, `eta`, `tau_days`, `PV`, `IPVI`, `Sw`, `So`, `Sg`, `link_type`, pressure/watercut факт-расчёт;
- `aggregates`: таблицы факт-расчёт по уровням `well`, `pad`, `sloy`, `lu`, `cell`.

Временный MVP endpoint:

- `GET /api/forecast/waterflood/mock-analysis?scenario_id=<id>`
- возвращает synthetic `WaterfloodAnalysisPayload` для проверки UI и формы результата;
- не является production run и должен быть заменён чтением сохранённого scenario-bound результата после полной реализации `waterflood_proxy_hm`.

## Зона ответственности

- data readiness validation для forecast inputs основной методики;
- coordinate-based injector-producer connectivity initialization;
- расчёт distance-based `alpha_prior`, `tau_prior` и `pv_prior`;
- применение manual/MRST/CRM priors как уточнений, а не замены обязательной координатной инициализации;
- PVT/SCAL/ROCK property validation and evaluation;
- native waterflood proxy simulation;
- 1D edge displacement model with `IPVI`, saturation and fractional-flow response;
- PVT-aware material-balance pressure calculation;
- calibration / history matching по watercut, pressure, rates и material balance;
- forecast scenarios с изменениями закачки, ограничениями добычи, shut-ins, conversions, link changes и pressure constraints;
- сохранение fitted parameters, objective components, train/validation metrics и diagnostics;
- baseline forecast
- baseline+GTM forecast
- watercut / displacement logic
- liquid decline logic
- агрегация профилей по датам и скважинам
- получение дат ГТМ согласно формируемому итеративно графику КРС из оптимизатора
- Возврат в оптимизатор профиля добычи
- пересчёт по скорректированному вручную графику из planner

## Не входит

- экономика
- построение графика КРС
- инфраструктурная валидация
- UI orchestration
- хранение planner revisions

## Зависимости

- получает нормализованные данные из `Module A`
- отдаёт результаты в `Module C`, `Module D`, `Module E`, `Module G`
- получает графики ГТМ из графиков КРС из `Module D`
- получает `PlannerScheduleRevision` из `Module F` для planner-side recalculation

## Методика расчёта

Основная методика Module B должна соответствовать `docs/forecast-module/PROMPT_MASTER.md`.
Текущая жидкостная decline-методика ниже сохраняется как `legacy_decline_liquid` для совместимости со старыми сценариями и synthetic smoke tests.

### 1. Data contracts and validation

Module B не читает raw Excel/CSV/YAML напрямую.
Все входы приходят из Module A как normalized datasets, references или сохранённые manual/config entities.

Для `waterflood_proxy_hm` validation должна проверять:

- наличие `well_type`, `x`, `y` и coordinate CRS;
- наличие добывающих и нагнетательных скважин;
- наличие production history и injection history;
- наличие development cells для pressure/material-balance mode;
- наличие PVT/SCAL/ROCK properties и region mapping;
- отсутствие silent extrapolation в properties;
- наличие forecast config и scenario definitions;
- согласованность `cell_id`, `region_id`, `PVTNUM/SATNUM/ROCKNUM/FIPNUM` equivalents.

### 2. Coordinate-based connectivity initialization

Первичная injector-producer связность обязательна и строится до MRST/CRM/manual priors:

1. Для каждой нагнетательной скважины ищутся добывающие скважины в радиусе влияния 3000 м.
2. Расстояние считается по metric coordinates.
3. Distance kernel по умолчанию: `max(0, 1 - d_ij / R_influence)^p`, где `p = 2`.
4. Link type multipliers применяются к geometric score:
   - `screen = 0.2`
   - `normal = 1.0`
   - `channel = 2.5`
   - `unknown = 1.0`
5. `alpha_prior` нормализуется по нагнетательной скважине.
6. `tau_prior_days` и `pv_prior` инициализируются из расстояния и edge PV initializer.
7. Если у нагнетательной нет добывающих скважин в радиусе, Module B не должен создавать сильную искусственную связь.

Manual overrides, MRST diagnostics и CRM priors могут уточнять prior blending, но не отменяют обязательную distance-based диагностику.

### 3. PVT / SCAL / ROCK property system

Основная методика не должна использовать молчаливые константные свойства.

Требуются normalized equivalents:

- `DENSITY`
- `PVTO` / `PVDO`
- `PVTW`
- `PVDG` / `PVTG`, если газ активен
- `ROCK`
- `SWOF` / `SGOF` или `SWFN` / `SGFN` / `SOF2` / `SOF3`
- `PVTNUM` / `SATNUM` / `ROCKNUM` / `FIPNUM`

Property evaluators должны поддерживать pressure-dependent PVT, rock pore-volume multiplier, SCAL fractional flow и запрет silent extrapolation по умолчанию.

### 4. Native waterflood proxy simulator

Расчётная модель является directed graph:

- injector nodes;
- producer nodes;
- optional cell / region / tank nodes;
- injector-producer 1D proxy edges.

Для каждой активной связи хранятся:

- `alpha`
- `eta`
- `tau_days`
- `pv`
- `IPVI`
- `water_saturation`
- `oil_saturation`
- `gas_saturation`, если газ активен
- `breakthrough_ipvi`
- `displacement_efficiency`

Эффективная закачка по связи:

`q_inj_eff_ij(t) = alpha_ij * eta_ij * q_inj_i(t)`

Изменение injected pore volumes:

`dIPVI_ij(t) = q_inj_eff_ij(t) * dt / pv_ij`

Обводнённость добывающей скважины рассчитывается через delayed edge responses и SCAL/PVT fractional flow.

### 5. PVT-aware material balance and pressure

Для каждой material-balance cell / region Module B отслеживает:

- pressure;
- pore volume;
- porosity multiplier from rock compressibility;
- water/oil/gas saturations;
- stock-tank oil in place;
- water in place;
- free gas and dissolved gas, если gas/live oil активны;
- injection and withdrawal reservoir volumes;
- voidage replacement ratio.

Pressure update должен использовать:

- rock compressibility from `ROCK`;
- water compressibility from `PVTW`;
- pressure-dependent `Bo`, `Bw`, `Bg`, `Rs`, viscosities;
- region-specific PVT/ROCK mapping.

### 6. Calibration / history matching

Калибровка подбирает:

- `alpha_ij`;
- `eta_i` или `eta_ij`;
- `tau_days`;
- `pv_ij`;
- `displacement_efficiency`;
- `breakthrough_ipvi`;
- selected fractional-flow multipliers, если разрешено;
- pressure/material-balance parameters;
- optional aquifer/intercell parameters.

Objective function должна включать:

- `L_watercut`;
- `L_pressure`;
- `L_rates`;
- `L_material_balance`;
- `L_regularization`.

Distance-based alpha является prior, а не жёсткой истиной: optimizer может изменить его, если история требует другой связности.

### 7. Forecast scenarios

Forecast scenarios должны поддерживать:

- forecast start/end date;
- injection multipliers and schedules;
- producer constraints;
- shut-ins;
- new/disabled/converted wells;
- link status/type changes;
- pressure constraints;
- property multiplier cases, если разрешено;
- output aggregation level.

`GTM`, `KrsScheduleScenario` и `PlannerScheduleRevision` должны приводиться к forecast events этой модели, а не применяться только как прибавка жидкости.

### 8. Legacy fallback: `legacy_decline_liquid`

Этот раздел описывает старую совместимую методику.

#### 8.1 Базовый принцип

В текущей методике весь прогноз контролируется по жидкости.

- основным управляемым рядом является `liquid_rate`
- `oil_rate` не задаётся как независимый прогнозный ряд, а вычисляется из жидкости и обводнённости
- `gas_rate` и `GOR` считаются частью того же `ProductionScenario`, но не заменяют жидкостный контроль
- горизонт прогноза по умолчанию задаётся посуточно от даты запуска сценария до конца следующего календарного года, если пользователь не переопределил его в сценарных настройках

#### 8.2 Типы фонда в `WellState`

`WellState.fund_type` должен использовать как минимум два канонических значения:

- `Base`
- `New wells`

Смысл:

- `Base` — скважина уже находилась в добыче ранее и имеет последний фактический режим
- `New wells` — новая скважина, для которой исторический baseline-rule базового фонда не применяется в том же виде, но жидкостный инкремент на дату события рассчитывается по той же формуле, что и для `Base`

Для скважин `Base` должен использоваться `WellState.fund_state`:

- `в работе` — скважина включается в первый расчётный шаг с входным дебитом из wells dataset;
- любой иной статус — скважина стартует с нулевым дебитом и может войти в расчёт только после соответствующего GTM-события.

Текущая методика ниже описывает оба фонда, но использует разные ветки decline-логики.
Для `New wells` дата запуска в текущем контуре должна определяться датой соответствующего ГТМ или planner-side события, а не отдельным полем `launch_date`. После наступления такого события жидкостный инкремент применяется по той же формуле, что и для `Base`.
Если скважина отсутствует в `NormalizedWellDataset`, но присутствует в `NormalizedGtmDataset`, `Module B` должен создать для нее синтетическую forecast-сущность с `fund_type = New wells`, нулевым текущим режимом и доменными атрибутами (`LU`, `SLOY`, `WellPad`, имя/идентификатор), полученными из GTM-входа.

#### 8.3 Базовый прогноз жидкости для фонда `Base`

Для скважин с `fund_type = Base`:

1. Если `fund_state = в работе`, берётся последний фактический режим скважины, прежде всего `current_liquid_rate`.
2. Если `fund_state` отличается от `в работе`, начальный дебит для первого расчётного шага должен считаться равным нулю.
3. К активному базовому режиму применяется характеристика снижения жидкости из `DeclineConfig.base_monthly_decline_values`.
4. Характеристика задаётся вручную в `Module A` как годовой темп падения жидкости для каждого месяца горизонта.
5. Расчёт внутри `Module B` выполняется посуточно: для каждого дня используется годовой темп падения, назначенный для текущего месяца горизонта.
6. Базовый горизонт этого ряда — 2 года, если в сценарии не оговорено иное.

Дополнительное правило подготовки входов:

- если строка `gtm` иерархически сопоставлена со скважиной из `wells`, `Module B` должен трактовать её как мероприятие по базовой скважине, а не как отдельную новую скважину;
- только строки `gtm`, которые не были сопоставлены ни с одной скважиной из `wells`, должны образовывать synthetic `New wells / ВНС`.

Ожидаемая трактовка `DeclineConfig`:

- `lu_id` и `sloy_id` задают scope применимости decline-конфига
- массив `base_monthly_decline_values` задаёт снижение по месяцам для фонда `Base`
- массив `new_wells_monthly_decline_values` задаёт снижение по месяцам для `New wells` после даты соответствующего ГТМ или planner-side события
- каждое значение в рядах decline трактуется как годовой темп падения, а не как уже готовый месячный коэффициент
- `Module B` обязан пересчитывать годовой темп падения в эквивалентный суточный шаг расчёта; если годовое падение задано как процент `p_year`, то суточный коэффициент падения рассчитывается по формуле `p_day = 1 - (1 - p_year / 100)^(1/365)`
- расчёт идёт последовательно от текущего активного режима по дням
- на каждом следующем дне к текущему прогнозному `liquid_rate` применяется уже пересчитанный суточный коэффициент: `liquid_rate_next_day = liquid_rate_current_day * (1 - p_day)`
- при переходе к следующему месяцу горизонта используется следующее значение годового темпа из соответствующего ряда decline

Для `New wells` базовая ветка `base_monthly_decline_values` не должна применяться автоматически вместо отдельной ветки `new_wells_monthly_decline_values`.

#### 8.4 Эффект ГТМ по жидкости

С момента наступления ГТМ, получаемого из `NormalizedGtmDataset`, жидкость пересчитывается следующим образом:

- сначала берётся рассчитанная на дату ГТМ базовая жидкость скважины
- затем к ней прибавляется `expected_liquid_increment`

То есть новая жидкость после ГТМ:

`liquid_rate_after_gtm = liquid_rate_on_gtm_date + expected_liquid_increment`

Правила:

- для текущей методики приоритетным инкрементом считается именно `expected_liquid_increment`
- эта формула одинаково применяется к `Base` и `New wells`; различие между фондами находится в baseline/startup логике, а не в формуле жидкостного инкремента
- если `expected_liquid_increment` отсутствует, это должно быть явно отражено в допущениях расчёта или validation/result metadata, а не теряться молча
- дальнейшее падение жидкости после ГТМ продолжается в том же посуточном жидкостном контуре, если отдельная методика post-GTM decline не оговорена дополнительно
- для `New wells` датой начала post-startup/post-GTM профиля считается дата соответствующего ГТМ или planner-side события

#### 8.5 Расчёт нефти от жидкости через обводнённость

Нефть считается от жидкости, используя обводнённость.

Обводнённость рассчитывается по `DisplacementConfig` через `NIZ` и накопленную добычу нефти.
Абсолютное значение `NIZ` для каждой скважины должно приходить не из inline-поля wells dataset, а из отдельного scenario-bound dataset типа `niz`, связанного с `wells` и `gtm` по `well_name` / `well_id`.
Для конкретной скважины должен использоваться `DisplacementConfig`, соответствующий её `LU` и при наличии её `SLOY`.
Накопленные показатели `current_cumulative_oil` и `current_cumulative_gas`, если они участвуют в расчёте или сохраняются в runtime-state, должны поступать не из wells dataset, а из scenario-bound dataset типа `niz`, связанного со скважиной по `well_name` / `well_id`.

Используемый в текущей методике нормализованный показатель:

`(NIZ - cumulative_oil) / NIZ`

Именно он подаётся на характеристику вытеснения для получения обводнённости.

Далее:

1. берётся `NIZ`
2. берётся накопленная добыча нефти `current_cumulative_oil`
3. рассчитывается нормализованная координата по формуле выше
4. по `DisplacementConfig.curve_points` находится соответствующая обводнённость
5. между точками используется линейная интерполяция

После получения обводнённости нефть считается из жидкости расчётно.

#### 8.6 Обратный расчёт оставшихся НИЗ по фактической обводнённости

Если по скважине есть фактическая обводнённость, для прогноза должны использоваться оставшиеся НИЗ, рассчитанные обратным счётом:

- по фактической обводнённости находится положение скважины на характеристике вытеснения
- через это положение восстанавливается соответствующий нормализованный показатель
- затем определяется оставшаяся часть НИЗ
- дальнейший прогноз ведётся уже от этого состояния

Это нужно для того, чтобы прогноз продолжался не от условной табличной точки, а от фактического текущего состояния скважины.

#### 8.7 Линейная интерполяция на характеристике вытеснения

Для `DisplacementConfig`:

- точки должны быть отсортированы по оси X
- между соседними точками используется линейная интерполяция
- extrapolation outside bounds должна быть описана явно в реализации и scenario metadata

#### 8.8 Итоговая логика контроля

Вся расчётная цепочка подчиняется следующему правилу:

- контролируется жидкость
- нефть получается расчётно
- GTM сначала меняет жидкость
- затем от новой жидкости и новой обводнённости считается нефть

## Контрактные правила

1. `Module B` не читает raw Excel напрямую.
2. Любой пересчёт по planner revision создаёт новый scenario-level output.
3. Все scenario-level outputs несут `scenario_id`.
4. Газовые показатели считаются частью того же `ProductionScenario`, а не отдельным параллельным результатом.
5. Внутренние расчётные допущения не дублируются в UI.
6. Основной `forecast_method` для новой методики — `waterflood_proxy_hm`.
7. Для `waterflood_proxy_hm` первичная связность строится из координат скважин; MRST/CRM/manual priors не могут быть единственным источником связности.
8. Для `waterflood_proxy_hm` production run должен блокироваться при отсутствии обязательных PVT/SCAL/ROCK данных.
9. Для `waterflood_proxy_hm` silent extrapolation PVT/SCAL запрещён.
10. Для `waterflood_proxy_hm` калибровка должна сохранять fitted parameters, objective components, train/validation metrics и diagnostics.
11. Для `waterflood_proxy_hm` forecast events из GTM/Planner должны преобразовываться в изменения сценария: injection schedule, production constraints, shut-ins, conversions, link changes, pressure constraints.
12. `legacy_decline_liquid` допускается только как явно указанный режим совместимости.
13. `fund_type` в `WellState` должен использовать канонические значения `Base` и `New wells`, если фондовая классификация участвует в legacy-расчёте.
14. Для `fund_type = Base` baseline decline должен стартовать от последнего фактического `current_liquid_rate` только если `fund_state = в работе`.
15. Отсутствие `fund_state` у базовой скважины в legacy wells dataset должно маркировать вход как `partial` и не допускать сценарий к legacy-расчёту.
16. Если методика требует `expected_liquid_increment`, его отсутствие должно быть явно отражено в расчётных допущениях, warnings или metadata результата.
17. Отсутствие `New wells` в `wells` dataset не должно приводить к их пропуску, если они заданы в `gtm`; в таком случае они рассчитываются как синтетические `New wells` от даты GTM.
18. Для legacy-режима `wells` dataset должен требовать как минимум поля `well`, `lu`, `well_pad`, `fund_state`, `oil_rate`, `liquid_rate`, `watercut`; поля `gas_rate`, `gor` и `sloy` являются необязательными, но допустимыми к загрузке.
19. При расчёте сценария с GTM `Module B` должен одновременно формировать связанный производный сценарий без GTM с именем `чистая База`, использовать те же scenario input bindings и временное окно и связывать его с исходным сценарием через `parent_scenario_id` и scenario metadata.
20. Для сценарного UI слой `БАЗА` в разделе `Добыча` должен браться из сохранённых результатов связанного сценария `чистая База`, а не вычисляться в UI как `oil_rate - oil_increment`.
21. Для сценарного UI слой `ГТМ` в разделе `Добыча` должен определяться как разница между сохранёнными результатами активного сценария и связанного сценария `чистая База` по фонду, отличному от `New wells`.
