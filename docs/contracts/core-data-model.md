# WorkNotOver: Базовая модель данных

## Назначение

Этот документ определяет ключевые shared entities, которые используются во всех модулях `A-G`.

Именно эти схемы считаются каноническими контрактами между модулями.
Ни один модуль не должен вводить параллельные версии этих сущностей без явного обновления контракта.

---

## Правила контракта

1. Shared entities считаются стабильными на уровне контракта, пока не выполнена их ревизия.
2. Любое изменение смысла поля требует обновления этого документа.
3. Backend schemas должны отражать эти сущности через Pydantic-модели.
4. UI должен потреблять эти сущности через API, а не придумывать локальные альтернативы.

---

## Entity: Dataset

Описывает логический набор данных, загруженный в систему и сохранённый в storage layer.

### Поля

- `dataset_id: str`
- `dataset_type: str`
- `name: str`
- `source_format: str`
- `source_file_name: str | None`
- `status: str`
- `created_at: str`
- `created_by: str | None`
- `metadata: dict[str, object] | None`

### Dataset Types

- `wells`
- 'trajectories'
- 'perforations'
- 'PVT'
- 'Initialization inputs'
- `niz`
- `gtm`
- `infrastructure`
- `external_krs_schedule`
- `production_history`
- `injection_history`
- `well_groups`
- `reservoir_properties`
- `forecast_model_config`
- `forecast_scenarios`
- другие документированные типы наборов данных

### Инварианты

- `dataset_id` устойчив во всех модулях;
- `source_format` для Excel-импорта обычно равен `xlsx` или `xls` или `xlsm`;
- `Dataset` описывает логическую сущность набора, а не конкретную ревизию его строк.

---

## Entity: DatasetVersion

Описывает конкретную сохранённую версию нормализованного набора данных.

### Поля

- `dataset_version_id: str`
- `dataset_id: str`
- `version_number: int`
- `schema_version: str | None`
- `row_count: int | None`
- `stored_at: str`
- `storage_backend: str`
- `validation_report_id: str | None`
- `is_active: bool`
- `metadata: dict[str, object] | None`

### Инварианты

- `dataset_id` ссылается на `Dataset.dataset_id`;
- `version_number >= 1`;
- только одна версия набора может быть `is_active = true`, если не оговорено иное;
- `DatasetVersion` представляет уже нормализованные и сохранённые данные, а не raw upload.

---

## Entity: DatasetReference

Описывает ссылку на сохранённый набор данных, которую downstream-модули используют вместо raw Excel.

### Поля

- `dataset_id: str`
- `dataset_version_id: str`
- `dataset_type: str`
- `name: str | None`
- `row_count: int | None`
- `created_at: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `DatasetReference` должен быть достаточен для повторного чтения нормализованных данных из storage layer;
- downstream-модули получают `DatasetReference` или сущности, извлечённые по нему, а не raw workbook.

---

## Entity: ManualInputSet

Описывает логический набор ручных вводных данных, введённых пользователем через UI и сохранённых в storage layer.

### Поля

- `manual_input_set_id: str`
- `name: str`
- `status: str`
- `created_at: str`
- `created_by: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `ManualInputSet` является ручным аналогом `Dataset` для конфигурационных входов;
- один набор может содержать несколько связанных конфигов для одного сценарного расчёта;
- downstream-модули используют не raw form-state, а сохранённые manual inputs.

---

## Entity: ManualInputReference

Описывает ссылку на сохранённый набор ручных вводных данных.

### Поля

- `manual_input_set_id: str`
- `name: str | None`
- `created_at: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `ManualInputReference` должен быть достаточен для повторного чтения связанного набора конфигов из storage layer;
- ручные вводные данные передаются downstream-модулям через reference или через извлечённые по нему сущности.

---

## Entity: LU

Описывает сущность верхнего уровня иерархии: участок недр.

### Поля

- `lu_id: str`
- `name: str`
- `code: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `lu_id` устойчив во всех модулях;
- `LU` используется как верхний уровень принадлежности для `SLOY`, кустов и скважин, обычно связанный единой инфраструктурой.

---

## Entity: SLOY

Описывает слой внутри участка недр `LU`.

### Поля

- `sloy_id: str`
- `lu_id: str`
- `name: str`
- `code: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `sloy_id` устойчив во всех модулях;
- `lu_id` ссылается на `LU.lu_id`;
- `SLOY` является уровнем иерархии выше куста и скважины.

---

## Entity: WellPad

Описывает куст как отдельную доменную сущность.

### Поля

- `well_pad_id: str`
- `lu_id: str | None`
- `sloy_id: str | None`
- `infrastructure_object_id: str | None`
- `name: str`
- `code: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `well_pad_id` устойчив во всех модулях;
- `lu_id` и `sloy_id` должны быть согласованы, если заданы;
- `infrastructure_object_id` может ссылаться на связанный инфраструктурный объект, но не заменяет саму иерархию принадлежности.

---

## Entity: WellState

Описывает текущее или сценарно скорректированное состояние скважины.

### Поля

- `well_id: str`
- `well_name: str`
- `well_type: str | None`
- `lu_id: str | None`
- `sloy_id: str | None`
- `well_pad_id: str | None`
- `development_cell_id: str | None`
- `region_id: str | None`
- `infrastructure_object_id: str | None`
- `fund_type: str | None`
- `fund_state: str | None`
- `status: str | None`
- `x: float | None`
- `y: float | None`
- `z: float | None`
- `coordinate_crs: str | None`
- `trajectory_type: str | None`
- `heel_x: float | None`
- `heel_y: float | None`
- `toe_x: float | None`
- `toe_y: float | None`
- `current_oil_rate: float | None`
- `current_gas_rate: float | None`
- `current_liquid_rate: float | None`
- `current_watercut: float | None`
- `current_gor: float | None`
- `current_cumulative_oil: float | None`
- `current_cumulative_gas: float | None`
- `current_cumulative_liquid: float | None`
- `niz: float | None`
- `reserves_group: str | None`
- `metadata: dict[str, object] | None`

### Fund Types

- `Base`
- `New wells`

### Well Types

- `producer`
- `injector`

### Инварианты

- `well_id` должен быть устойчивым во всех модулях;
- для новой waterflood proxy методики `well_type`, `x` и `y` обязательны для всех скважин, участвующих в построении injector-producer связности;
- `coordinate_crs` должен быть явно задан на уровне dataset metadata или строки; смешивание координатных систем без явной нормализации запрещено;
- `well_type = producer` используется как добывающая скважина, `well_type = injector` используется как нагнетательная скважина;
- `lu_id`, `sloy_id`, `well_pad_id` задают иерархию принадлежности скважины, если доступны;
- `development_cell_id` и `region_id` связывают скважину с расчётной ячейкой / material-balance region для новой методики Module B;
- `fund_type`, если задан, должен использовать канонические значения `Base` и `New wells`;
- для `fund_type = Base` скважина считается частью базового фонда, и её baseline forecast строится от последнего фактического режима;
- `fund_state` задаёт стартовое состояние базового фонда: при `fund_type = Base` и `fund_state = в работе` скважина участвует в первом расчётном шаге с входным дебитом из wells dataset;
- при `fund_type = Base` и любом другом значении `fund_state` скважина не участвует в первом расчётном шаге, её стартовый дебит должен считаться равным нулю до наступления GTM-события;
- для `fund_type = New wells` baseline-rule базового фонда не должен применяться автоматически без отдельной сценарной логики; дата запуска в текущей методике определяется датой соответствующего ГТМ или planner-side события, а не отдельным полем `WellState`;
- после наступления события ГТМ или запуска для `fund_type = New wells` жидкостный инкремент применяется по той же логике `expected_liquid_increment`, что и для `Base`;
- дебиты и накопленные показатели неотрицательны, если заданы;
- `current_gor` задаётся в одном согласованном формате и единицах измерения по проекту;
- `current_watercut` задаётся в одном согласованном формате: доля или проценты;
- `niz` в runtime-контуре должен считаться каноническим сценарио-связанным значением, полученным из отдельного dataset типа `niz`, привязанного к `Scenario` по `well_name`; inline-значение в `WellState`, если оно присутствует в импортированном wells dataset, не должно считаться единственным источником истины;
- `current_cumulative_oil` и `current_cumulative_gas` в runtime-контуре также должны считаться каноническими scenario-bound значениями, полученными из dataset типа `niz`; inline-значения этих полей в wells dataset не должны считаться источником истины для расчётного контура;
- `niz`, `current_cumulative_oil` и `current_watercut`, если доступны, должны быть достаточны для расчёта текущего положения скважины на характеристике вытеснения и обратного расчёта remaining NIZ.

---

## Entity: NizByWell

Описывает scenario-bound значение `NIZ` для отдельной скважины.

### Поля

- `well_id: str | None`
- `well_name: str`
- `lu_id: str | None`
- `well_pad_id: str | None`
- `niz: float`
- `current_cumulative_oil: float | None`
- `current_cumulative_gas: float | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `well_name` должен совпадать с именем скважины, используемым для связывания `WellState` и `GtmCandidate`;
- `lu_id` Рё `well_pad_id` РґРѕР»Р¶РЅС‹ С…СЂР°РЅРёС‚СЊ СЃС†РµРЅР°СЂРЅС‹Р№ РєРѕРЅС‚РµРєСЃС‚ С‚РѕР№ Р¶Рµ СЃРєРІР°Р¶РёРЅС‹ РЅР° СѓСЂРѕРІРЅРµ `LU -> WellPad`;
- `niz > 0`;
- dataset типа `niz` должен позволять построить полное отображение `well_name -> NIZ` для активного сценария;
- если накопленные показатели доступны, они должны храниться здесь же как scenario-bound значения `current_cumulative_oil` и `current_cumulative_gas` для соответствующей скважины.

---

## Entity: GtmCandidate

Описывает кандидатное ГТМ или мероприятие для КРС.

### Поля

- `gtm_id: str`
- `well_id: str`
- `well_name: str`
- `lu_id: str | None`
- `sloy_id: str | None`
- `well_pad_id: str | None`
- `infrastructure_object_id: str | None`
- `gtm_type: str`
- `planned_work: str`
- `candidate_start_date: str | None`
- `candidate_end_date: str | None`
- `duration_days: int | None`
- `expected_oil_increment: float | None`
- `expected_gas_increment: float | None`
- `expected_liquid_increment: float | None`
- `expected_watercut_change: float | None`
- `expected_gor_change: float | None`
- `priority: float | None`
- `source_row_number: int | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `gtm_id` устойчив внутри набора данных;
- `well_id` ссылается на `WellState.well_id`;
- `lu_id`, `sloy_id`, `well_pad_id` должны быть согласованы с соответствующей скважиной, если заданы;
- `duration_days` положительна, если задана.

---

## Entity: ProductionHistoryPoint

Описывает историческую точку добычи для настройки гидродинамичской модели на историю

### Поля

- `date: str`
- `producer_id: str`
- `well_name: str | None`
- `oil_rate: float`
- `water_rate: float`
- `liquid_rate: float | None`
- `gas_rate: float | None`
- `bhp: float | None`
- `thp: float | None`
- `reservoir_pressure: float | None`
- `status: str | None`
- `measurement_quality: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `producer_id` должен ссылаться на `WellState.well_id` с `well_type = producer`;
- `date` хранится в ISO-формате;
- `liquid_rate`, если отсутствует, может быть рассчитан как `oil_rate + water_rate`;
- дебиты неотрицательны;
- `reservoir_pressure` используется для history matching давления, если задано.

---

## Entity: InjectionHistoryPoint

Описывает историческую точку закачки для нагнетательной скважины.

### Поля

- `date: str`
- `injector_id: str`
- `injection_agent: str`
- `water_injection_rate: float | None`
- `gas_injection_rate: float | None`
- `bhp: float | None`
- `whp: float | None`
- `thp: float | None`
- `status: str | None`
- `measurement_quality: str | None`
- `metadata: dict[str, object] | None`

### Injection Agents

- `water`
- `gas`

### Инварианты

- `injector_id` должен ссылаться на `WellState.well_id` с `well_type = injector`;
- `date` хранится в ISO-формате;
- хотя бы один дебит закачки должен быть задан;
- дебиты неотрицательны.

---


## Entity: RegionMap

Связывает расчётные ячейки с PVT/SCAL/ROCK/FIP regions.

### Поля

- `development_cell_id: str`
- `pvt_region: str`
- `sat_region: str`
- `rock_region: str`
- `fip_region: str | None`
- `region_name: str | None`
- `formation: str | None`
- `reservoir: str | None`
- `zone: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- каждая ячейка, участвующая в material-balance режиме, должна иметь однозначные region mappings.

---

## Entity: ReservoirPropertySet

Описывает набор PVT/SCAL/ROCK-свойств.

### Поля

- `property_set_id: str`
- `density_rows: list[dict[str, object]]`
- `water_pvt_rows: list[dict[str, object]]`
- `oil_pvt_rows: list[dict[str, object]]`
- `gas_pvt_rows: list[dict[str, object]] | None`
- `rock_rows: list[dict[str, object]]`
- `swof_rows: list[dict[str, object]]`
- `sgof_rows: list[dict[str, object]] | None`
- `region_map: list[RegionMap]`
- `metadata: dict[str, object] | None`

### Инварианты

- production run не должен использовать молчаливые константные PVT/SCAL/ROCK-свойства;
- extrapolation PVT/SCAL запрещён по умолчанию и допустим только при явной настройке с логированием события;
- таблицы должны быть привязаны к region identifiers, совместимым с `PVTNUM/SATNUM/ROCKNUM/FIPNUM` по смыслу.

---


## Entity: SimulationRun

Описывает один запуск гидродинамического расчёта Module B.

### Поля

- `run_id: str`
- `scenario_id: str`
- `forecast_method: str`
- `engine: str`
- `engine_version: str | None`
- `status: str`
- `case_name: str`
- `case_root: str`
- `input_dir: str`
- `output_dir: str`
- `normalized_dir: str`
- `started_at: str | None`
- `finished_at: str | None`
- `created_at: str`
- `created_by: str | None`
- `opm_case_manifest: OpmCaseManifest | None`
- `artifacts: list[SimulationArtifact]`
- `import_result: OpmImportResult | None`
- `metadata: dict[str, object] | None`

### Status Values

- `draft`
- `case_built`
- `running`
- `completed`
- `failed`
- `imported`

### Инварианты

- каждый production-запуск `Module B` создает новый `SimulationRun`;
- raw OPM artifacts не перезаписываются после завершения запуска;
- downstream-модули читают нормализованные результаты, но raw artifacts сохраняются как evidence/debug layer;
- `scenario_id` обязателен для всех результатов, таблиц и artifacts.

---

## Entity: OpmCaseManifest

Описывает подготовленный OPM/Eclipse-compatible case.

### Поля

- `case_name: str`
- `deck_path: str`
- `include_files: list[str]`
- `sections: list[str]`
- `summary_vectors: list[str]`
- `input_bindings_hash: str | None`
- `deck_hash: str | None`
- `validation_warnings: list[str]`
- `metadata: dict[str, object] | None`

### Инварианты

- manifest должен позволять воспроизвести, какие входные данные и include-файлы были использованы;
- `RUNSPEC`, `GRID`, `PROPS`, `REGIONS`, `SOLUTION`, `SCHEDULE`, `SUMMARY` являются каноническими секциями production case.

---

## Entity: SimulationArtifact

Описывает raw или normalized файл, связанный с `SimulationRun`.

### Поля

- `artifact_id: str`
- `run_id: str`
- `artifact_type: str`
- `path: str`
- `format: str`
- `size_bytes: int | None`
- `checksum: str | None`
- `created_at: str | None`
- `metadata: dict[str, object] | None`

### Artifact Types

- `opm_deck`
- `opm_include`
- `opm_egrid`
- `opm_init`
- `opm_smspec`
- `opm_unsmry`
- `opm_unrst`
- `opm_rft`
- `opm_prt`
- `opm_log`
- `normalized_parquet`
- `import_report`

---

## Entity: OpmImportResult

Описывает результат импорта raw OPM artifacts в нормализованные таблицы WorkNotOver.

### Поля

- `run_id: str`
- `status: str`
- `well_timeseries_path: str | None`
- `field_timeseries_path: str | None`
- `grid_static_path: str | None`
- `grid_dynamic_path: str | None`
- `region_material_balance_path: str | None`
- `rft_connections_path: str | None`
- `warnings: list[str]`
- `errors: list[str]`
- `metadata: dict[str, object] | None`

### Инварианты

- importer не должен считать расчётную физику повторно;
- importer только читает OPM/Eclipse artifacts и приводит их к каноническим таблицам;
- отсутствие optional artifacts, например `.RFT`, не должно ломать импорт summary/grid results, но должно фиксироваться в warnings.

---

## Entity: CalibrationResult

Описывает результат history matching.

### Поля

- `calibration_id: str`
- `scenario_id: str`
- `forecast_method: str`
- `status: str`
- `fitted_connections: list[WaterfloodConnection]`
- `fitted_parameters: dict[str, object]`
- `objective_components: dict[str, float]`
- `train_metrics: dict[str, object]`
- `validation_metrics: dict[str, object]`
- `history_match_timeseries: list[ProductionPoint] | None`
- `material_balance_by_cell: list[dict[str, object]] | None`
- `diagnostic_artifacts: dict[str, object] | None`
- `metadata: dict[str, object] | None`

### Инварианты

- результат калибровки должен быть воспроизводимым по входным datasets, config и random seed;
- fitted parameters и train/validation metrics должны сохраняться как scenario-bound output;
- калибровка может изменять distance-based priors, но не должна удалять исходные diagnostics.

---

## Entity: BrigadeAvailabilityConfig

Описывает ручной график доступности бригад КРС.

### Поля

- `config_id: str`
- `manual_input_set_id: str`
- `brigade_items: list[BrigadeAvailabilityItem]`
- `notes: str | None`

### Related Entity: BrigadeAvailabilityItem

- `brigade_name: str`
- `available_from: str`
- `available_to: str | None`
- `capacity_share: float | None`
- `status: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `manual_input_set_id` ссылается на `ManualInputSet.manual_input_set_id`;
- `available_from` хранится в ISO-формате;
- `available_to >= available_from`, если задано;
- `capacity_share` положителен, если задан.

---

## Entity: BrigadeCapacityByLuConfig

Описывает помесячную доступность бригад КРС по участкам недр для optimizer-level планирования.

### Поля

- `config_id: str`
- `manual_input_set_id: str`
- `items: list[BrigadeCapacityByLuItem]`
- `notes: str | None`

### Related Entity: BrigadeCapacityByLuItem

- `lu_id: str`
- `month_date: str`
- `brigade_count: int`
- `metadata: dict[str, object] | None`

### Инварианты

- `manual_input_set_id` ссылается на `ManualInputSet.manual_input_set_id`;
- `month_date` хранится в ISO-формате и представляет месяц расчёта;
- `brigade_count >= 0`;
- для одной пары `lu_id + month_date` внутри одного `BrigadeCapacityByLuConfig` не должно быть более одной активной записи.

---

## Entity: FailureCoefficientConfig

Описывает набор коэффициентов отказности, задаваемых вручную для доменной иерархии.

Коэффициент отказности может задаваться:

- на уровне `LU`;
- на уровне `SLOY`.

### Поля

- `config_id: str`
- `manual_input_set_id: str`
- `items: list[FailureCoefficientItem]`
- `notes: str | None`

### Related Entity: FailureCoefficientItem

- `scope_type: str`
- `lu_id: str | None`
- `sloy_id: str | None`
- `coefficient: float`
- `metadata: dict[str, object] | None`

### Scope Types

- `lu`
- `sloy`

### Инварианты

- `manual_input_set_id` ссылается на `ManualInputSet.manual_input_set_id`;
- `coefficient >= 0`;
- если `scope_type = lu`, то `lu_id` обязателен, а `sloy_id` должен быть `None` или не использоваться;
- если `scope_type = sloy`, то `sloy_id` обязателен;
- если `scope_type = sloy`, то `lu_id` может быть дополнительно задан для проверки согласованности, но каноническим ключом уровня является `sloy_id`;
- для одной и той же области действия не должно существовать более одного активного коэффициента внутри одного `ManualInputSet`.

---

## Entity: ProductionPoint

Описывает одну точку производственного профиля по времени.

### Поля

- `date: str`
- `scenario_id: str`
- `well_id: str | None`
- `development_cell_id: str | None`
- `region_id: str | None`
- `connection_id: str | None`
- `oil_rate: float`
- `gas_rate: float | None`
- `liquid_rate: float`
- `water_rate: float | None`
- `gor: float | None`
- `watercut: float | None`
- `reservoir_pressure: float | None`
- `bhp: float | None`
- `thp: float | None`
- `water_saturation: float | None`
- `oil_saturation: float | None`
- `gas_saturation: float | None`
- `injected_water_received: float | None`
- `injected_gas_received: float | None`
- `effective_injection_by_edge: dict[str, float] | None`
- `material_balance: dict[str, float] | None`
- `oil_increment: float | None`
- `gas_increment: float | None`
- `liquid_increment: float | None`

### Инварианты

- `date` хранится в ISO-формате;
- дебиты неотрицательны.

---

## Entity: ProductionScenario

Описывает рассчитанный сценарий добычи.

### Поля

- `scenario_id: str`
- `name: str`
- `source_type: str`
- `parent_scenario_id: str | None`
- `start_date: str`
- `end_date: str`
- `well_results: list[WellForecastResult]`
- `aggregated_profile: list[ProductionPoint]`
- `summary: ScenarioProductionSummary`

### Related Entity: WellForecastResult

- `well_id: str`
- `well_name: str`
- `fund_type: str | None`
- `fund_state: str | None`
- `lu_id: str | None`
- `sloy_id: str | None`
- `well_pad_id: str | None`
- `development_cell_id: str | None`
- `region_id: str | None`
- `forecast_method: str | None`
- `calibration_status: str | None`
- `calibration_quality: dict[str, object] | None`
- `profile: list[ProductionPoint]`
- `summary: dict[str, float | str | None]`

### Related Entity: ScenarioProductionSummary

- `total_oil: float`
- `total_gas: float | None`
- `total_liquid: float`
- `peak_oil_rate: float | None`
- `peak_gas_rate: float | None`
- `peak_liquid_rate: float | None`
- `average_gor: float | None`
- `average_watercut: float | None`

### Инварианты

- сценарий всегда имеет временное окно;
- агрегированный профиль покрывает то же окно, что и скважинные профили.

---

## Entity: EconomicsConfig

Описывает экономические предпосылки.

### Поля

- `config_id: str`
- `items: list[EconomicsConfigItem]`
- `oil_price: float | None`
- `gas_price: float | None`
- `liquid_handling_cost: float | None`
- `water_handling_cost: float | None`
- `gas_handling_cost: float | None`
- `discount_rate: float | None`
- `gtm_costs_by_type: dict[str, float] | None`
- `tax_config: dict[str, object] | None`
- `notes: str | None`

### Related Entity: EconomicsConfigItem

- `lu_id: str`
- `net_back: float | None`

### Инварианты

- `EconomicsConfig` может содержать общие экономические параметры сценария и LU-специфичные значения `net_back`;
- список `items` используется как каноническая форма ввода `Net Back` по участкам недр;
- для одной пары `lu_id` внутри одного `EconomicsConfig` не должно существовать более одной активной записи.

---

## Entity: GtmEconomicsResult

Описывает экономику одного ГТМ.

### Поля

- `gtm_id: str`
- `scenario_id: str`
- `well_id: str`
- `gtm_type: str`
- `capex: float | None`
- `incremental_oil: float | None`
- `incremental_gas: float | None`
- `incremental_liquid: float | None`
- `revenue: float | None`
- `gas_revenue: float | None`
- `opex: float | None`
- `npv: float | None`
- `payback_months: float | None`

---

## Entity: EconomicsResult

Описывает экономику всего сценария.

### Поля

- `scenario_id: str`
- `scenario_name: str`
- `total_capex: float | None`
- `total_revenue: float | None`
- `total_gas_revenue: float | None`
- `total_opex: float | None`
- `npv: float | None`
- `cashflow_profile: list[CashflowPoint]`
- `gtm_results: list[GtmEconomicsResult]`

### Related Entity: CashflowPoint

- `date: str`
- `cash_in: float | None`
- `cash_out: float | None`
- `net_cashflow: float | None`
- `discounted_cashflow: float | None`

---

## Entity: KrsResourceConfig

Описывает ресурсные предпосылки для построения графика КРС.

### Поля

- `brigade_count: int | None`
- `durations_by_gtm_type: dict[str, int]`
- `calendar_rules: dict[str, object] | None`
- `notes: str | None`

### Инварианты

- `brigade_count`, если задан, > 0;
- все длительности положительные целые.
- `brigade_count` может использоваться как глобальный fallback, если детальный `BrigadeCapacityByLuConfig` не задан.

---

## Entity: KrsScheduleItem

Описывает одно мероприятие в графике КРС.

### Поля

- `schedule_item_id: str`
- `scenario_id: str`
- `gtm_id: str`
- `well_id: str`
- `well_name: str`
- `area: str | None`
- `brigade: str`
- `gtm_type: str`
- `planned_work: str`
- `start_date: str`
- `end_date: str`
- `duration_days: int`
- `rank: int | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `end_date >= start_date`;
- `duration_days > 0`.

---

## Entity: KrsScheduleScenario

Описывает полный график КРС для одного сценария.

### Поля

- `scenario_id: str`
- `name: str`
- `items: list[KrsScheduleItem]`
- `brigade_count: int`
- `summary: dict[str, object] | None`

### Инварианты

- `KrsScheduleScenario` может быть построен `Module D` либо получен из внешнего готового графика КРС, нормализованного в `Module A`;
- внешний график КРС после нормализации должен храниться в storage layer как `Dataset` / `DatasetVersion` с `dataset_type = external_krs_schedule`;
- downstream-модули работают не с raw Excel внешнего графика КРС, а с сохранённым `DatasetReference` и извлечённым из него `KrsScheduleScenario`.

---

## Entity: ImportedKrsSchedulePayload

Описывает нормализованный результат загрузки внешнего готового графика КРС.

### Поля

- `dataset_reference: DatasetReference`
- `schedule: KrsScheduleScenario`
- `source_format: str | None`
- `source_file_name: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `ImportedKrsSchedulePayload` создаётся только `Module A`;
- после создания payload может быть открыт в `Module F: Planner` без участия `Module D`;
- структура `schedule.items` должна быть совместима с planner-side editable model без промежуточного преобразования в UI.

---

## Entity: OptimizationConfig

Описывает настройки оптимизатора.

### Поля

- `target_metric: str`
- `max_iterations: int | None`
- `search_mode: str`
- `penalty_rules: dict[str, object] | None`
- `hard_constraints: dict[str, object] | None`

---

## Entity: OptimizationResult

Описывает результат оптимизации графика.

### Поля

- `scenario_id: str`
- `best_schedule: KrsScheduleScenario`
- `best_score: float | None`
- `target_metric: str`
- `ranked_scenarios: list[OptimizationCandidateResult]`
- `selected_candidate_id: str | None`

### Related Entity: OptimizationCandidateResult

- `candidate_id: str`
- `score: float | None`
- `is_feasible: bool`
- `constraint_summary: dict[str, object] | None`
- `economics_summary: dict[str, object] | None`

---

## Entity: InfrastructureObject

Описывает инфраструктурный объект с ограничениями по мощности.

### Поля

- `object_id: str`
- `name: str`
- `object_type: str`
- `commissioning_date: str | None`
- `capacity_oil: float | None`
- `capacity_liquid: float | None`
- `capacity_water: float | None`
- `capacity_gas: float | None`
- `parent_object_id: str | None`
- `metadata: dict[str, object] | None`

### Object Types

- `pipeline`
- `collector`
- `flowline`
- `upsv`
- `dns`
- `upn`
- `surface_facility`
- другие документированные типы

---

## Entity: InfrastructureConnection

Описывает связь между скважиной и инфраструктурным объектом.

### Поля

- `connection_id: str`
- `well_id: str`
- `object_id: str`
- `start_date: str | None`
- `end_date: str | None`
- `priority: int | None`
- `metadata: dict[str, object] | None`

---

## Entity: InfrastructureViolation

Описывает одно нарушение инфраструктурного ограничения.

### Поля

- `object_id: str`
- `object_name: str`
- `date: str`
- `metric: str`
- `actual_value: float`
- `limit_value: float`
- `overflow_value: float`
- `severity: str | None`

---

## Entity: InfrastructureConstraintCheckResult

Описывает результат проверки сценария на инфраструктурные ограничения.

### Поля

- `scenario_id: str`
- `is_feasible: bool`
- `first_violation_date: str | None`
- `violations: list[InfrastructureViolation]`
- `object_loads: list[InfrastructureLoadPoint] | None`

### Related Entity: InfrastructureLoadPoint

- `object_id: str`
- `date: str`
- `oil_load: float | None`
- `gas_load: float | None`
- `liquid_load: float | None`
- `water_load: float | None`

---

## Entity: Scenario

Описывает ревизию сценария в системе.

### Поля

- `scenario_id: str`
- `name: str`
- `source_type: str`
- `parent_scenario_id: str | None`
- `forecast_start_date: str | None`
- `forecast_end_date: str | None`
- `input_bindings: ScenarioInputBindings`
- `created_at: str`
- `status: str`
- `metadata: dict[str, object] | None`

### Related Entity: ScenarioInputBindings

- `wells_dataset: DatasetReference | None`
- `well_groups_dataset: DatasetReference | None`
- `niz_dataset: DatasetReference | None`
- `gtm_dataset: DatasetReference | None`
- `infrastructure_dataset: DatasetReference | None`
- `external_krs_schedule_dataset: DatasetReference | None`
- `well_trajectories_dataset: DatasetReference | None`
- `perforations_dataset: DatasetReference | None`
- `production_history_dataset: DatasetReference | None`
- `injection_history_dataset: DatasetReference | None`
- `development_cells_dataset: DatasetReference | None`
- `waterflood_connections_dataset: DatasetReference | None`
- `reservoir_properties_dataset: DatasetReference | None`
- `forecast_model_config: DatasetReference | ManualInputReference | None`
- `forecast_scenarios_dataset: DatasetReference | None`
- `manual_input_set: ManualInputReference | None`

### Related Entity: ScenarioInputValidation

- `wells_state: str`
- `well_groups_state: str`
- `niz_state: str`
- `gtm_state: str`
- `infrastructure_state: str`
- `external_krs_schedule_state: str`
- `well_trajectories_state: str`
- `perforations_state: str`
- `production_history_state: str`
- `injection_history_state: str`
- `development_cells_state: str`
- `waterflood_connections_state: str`
- `reservoir_properties_state: str`
- `forecast_model_config_state: str`
- `forecast_scenarios_state: str`
- `manual_input_set_state: str`
- `is_forecast_ready: bool`
- `issues: list[str]`

### Source Types

- `uploaded_gtm`
- `optimized_krs`
- `planner_manual_edit`

### Инварианты

- `Scenario` является центральной сущностью `Scenario-first` workflow и всегда должен иметь собственные `input_bindings`, даже если часть входов еще не задана;
- сценарий может находиться в статусе `draft`, пока пользователь привязывает datasets и manual inputs;
- сценарий не должен считаться неизменяемым, пока он находится в статусе `draft`;
- после запуска расчета или создания производной версии сценария ревизия сценария должна рассматриваться как неизменяемая;
- если `forecast_start_date` и `forecast_end_date` не заданы явно пользователем, система должна назначать default horizon от даты запуска сценария до `31 декабря` следующего календарного года;
- производные сценарии ссылаются на родителя, если это применимо;
- для `source_type = planner_manual_edit` ссылка на родительский сценарий обязательна;
- если сценарий рассчитывается с GTM-входом, система может автоматически формировать связанный производный сценарий без GTM с именем `чистая База`;
- для такого производного сценария `parent_scenario_id` указывает на исходный расчетный сценарий, а `metadata.scenario_role` должно иметь значение `pure_base`;
- исходный сценарий с GTM может хранить в `metadata.pure_base_scenario_id` ссылку на автоматически сформированный связанный сценарий `чистая База`;
- если сценарий собран по ветке `Загрузить существующий график КРС`, в `input_bindings.external_krs_schedule_dataset` должна присутствовать ссылка на dataset типа `external_krs_schedule`;
- в `input_bindings.niz_dataset` должна присутствовать ссылка на dataset типа `niz`, если сценарий использует `metadata.forecast_method = legacy_decline_liquid` или явно задаёт `metadata.requires_niz = true`;
- `input_bindings` описывают канонические привязки сценария к данным, а не временное состояние локального UI.
- у сценария должно существовать каноническое состояние валидации входов `ScenarioInputValidation`, чтобы один и тот же статус полноты входных данных читался одинаково в `Сценарии`, `Добыча` и planner-side flows;
- если сценарий использует `external_krs_schedule`, но wells или gtm datasets не покрывают все скважины из внешнего графика, соответствующие узлы должны считаться `partial`, а `is_forecast_ready` должно быть `false`;
- если сценарий требует `NIZ`, а wells dataset или gtm dataset содержат скважины, для которых отсутствует `NIZ` в привязанном scenario-bound dataset `niz`, соответствующие узлы `wells`, `gtm` и `niz` должны считаться `partial`, а `is_forecast_ready` должно быть `false`;
- для `metadata.forecast_method = opm_flow_blackoil` сценарий должен иметь привязанные `production_history_dataset`, `injection_history_dataset`, `development_cells_dataset`, `reservoir_properties_dataset`, `forecast_model_config` и schedule source (`gtm`, `external_krs_schedule`, `optimized_krs` или `planner_revision`);
- для `metadata.forecast_method = opm_flow_blackoil` `wells_dataset` должен содержать добывающие и нагнетательные скважины, координаты/привязку к grid completions или достаточные данные для построения `WELSPECS`/`COMPDAT`;
---

## Entity: PlannerScheduleRevision

Описывает версию графика, возвращаемую из planner обратно в расчётный контур.

### Поля

- `revision_id: str`
- `planner_version_id: str | None`
- `version_name: str`
- `parent_scenario_id: str`
- `items: list[KrsScheduleItem]`
- `edited_at: str`
- `editor: str | None`
- `metadata: dict[str, object] | None`

### Инварианты

- `parent_scenario_id` всегда указывает на сценарий, в контексте которого была создана revision;
- `version_name` обязателен для отображения planner-side версии в `Module G`;
- `PlannerScheduleRevision` является source of truth для ручной календарной правки, а не локальный UI-state `Module G`.

---

## Entity: RecalculationScenarioInput

Описывает вход для нового пересчёта на основе графика, скорректированного в planner.

### Поля

- `parent_scenario_id: str`
- `planner_revision_id: str | None`
- `schedule: KrsScheduleScenario | None`
- `recalculation_mode: str`
- `metadata: dict[str, object] | None`

### Инварианты

- `RecalculationScenarioInput` может ссылаться либо на `planner_revision_id`, либо напрямую содержать `schedule`, если это оговорено в runtime flow;
- в каноническом planner-side workflow `Module B` читает revision по `planner_revision_id` из `Module F`, а `Module G` лишь оркестрирует запуск пересчета;
- хотя бы одно из полей `planner_revision_id` или `schedule` должно быть задано.

---

## Entity: PlannerTransferPayload

Описывает payload, отправляемый в planner.

### Поля

- `scenario_id: str`
- `version_name: str`
- `schedule_items: list[KrsScheduleItem]`
- `summary: dict[str, object] | None`

---

## Entity: ScenarioResult

Описывает итоговый результат сценария в едином представлении.

### Поля

- `scenario: Scenario`
- `production_result: ProductionScenario`
- `economics_result: EconomicsResult | None`
- `krs_schedule: KrsScheduleScenario | None`
- `infra_check_result: InfrastructureConstraintCheckResult | None`
- `summary_kpis: dict[str, float | str | None]`

---

## Соглашения по ID и датам

- все идентификаторы строковые;
- все даты в формате ISO `YYYY-MM-DD`;
- timestamp хранится как ISO datetime;
- единицы измерения должны быть явно документированы для каждого набора данных и API.

---

## Слои данных

- `raw uploaded data` — исходные файлы и preview до нормализации;
- `Dataset / DatasetVersion / DatasetReference` — сохранённый в storage layer канонический слой нормализованных данных;
- `ManualInputSet / ManualInputReference` и связанные config entities — сохранённый в storage layer канонический слой ручных исходных данных;
- `scenario results` — производные расчётные и planner-сущности, привязанные к сценарию.

---


## Иерархия принадлежности

В системе поддерживаются две разные модели:

1. Иерархия принадлежности:
   - `LU -> SLOY -> WellPad -> WellState`
2. Инфраструктурный граф:
   - `WellState / WellPad -> InfrastructureObject -> parent InfrastructureObject`

Эти модели нельзя смешивать:

- `LU`, `SLOY` и `WellPad` описывают доменную принадлежность;
- `InfrastructureObject` и `InfrastructureConnection` описывают инфраструктурную и потоковую связность.

---

## Карта владения сущностями

- Module A владеет raw upload, ручными исходными вводными, нормализацией и сущностями `Dataset`, `DatasetVersion`, `DatasetReference`, `ManualInputSet`, `ManualInputReference`;
- Module B владеет production outputs;
- Module C владеет economics outputs;
- Module D владеет KRS schedule и optimization outputs и потребляет `BrigadeAvailabilityConfig`, `BrigadeCapacityByLuConfig`, `FailureCoefficientConfig` и `KrsResourceConfig`;
- Module E владеет infrastructure validation outputs;
- Module F владеет planner revisions и editable schedule payloads;
- Module G владеет orchestration payloads для пересчёта сценариев;
- Module G потребляет API contracts и не должен переопределять их локально.
