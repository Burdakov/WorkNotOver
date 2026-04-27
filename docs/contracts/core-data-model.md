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
- `gtm`
- `infrastructure`
- `external_krs_schedule`
- другие документированные типы наборов данных

### Инварианты

- `dataset_id` устойчив во всех модулях;
- `source_format` для Excel-импорта обычно равен `xlsx` или `xls`;
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
- `LU` используется как верхний уровень принадлежности для `SLOY`, кустов и скважин.

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
- `area: str | None`
- `lu_id: str | None`
- `sloy_id: str | None`
- `well_pad_id: str | None`
- `infrastructure_object_id: str | None`
- `brigade: str | None`
- `fund_type: str | None`
- `status: str | None`
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

### Инварианты

- `well_id` должен быть устойчивым во всех модулях;
- `lu_id`, `sloy_id`, `well_pad_id` задают иерархию принадлежности скважины, если доступны;
- `fund_type`, если задан, должен использовать канонические значения `Base` и `New wells`;
- для `fund_type = Base` скважина считается частью базового фонда, и её baseline forecast строится от последнего фактического режима;
- для `fund_type = New wells` baseline-rule базового фонда не должен применяться автоматически без отдельной сценарной логики; дата запуска в текущей методике определяется датой соответствующего ГТМ или planner-side события, а не отдельным полем `WellState`;
- после наступления события ГТМ или запуска для `fund_type = New wells` жидкостный инкремент применяется по той же логике `expected_liquid_increment`, что и для `Base`;
- дебиты и накопленные показатели неотрицательны, если заданы;
- `current_gor` задаётся в одном согласованном формате и единицах измерения по проекту;
- `current_watercut` задаётся в одном согласованном формате: доля или проценты;
- `niz`, `current_cumulative_oil` и `current_watercut`, если доступны, должны быть достаточны для расчёта текущего положения скважины на характеристике вытеснения и обратного расчёта remaining NIZ.

---

## Entity: GtmCandidate

Описывает кандидатное ГТМ или мероприятие для КРС.

### Поля

- `gtm_id: str`
- `well_id: str`
- `well_name: str`
- `area: str | None`
- `lu_id: str | None`
- `sloy_id: str | None`
- `well_pad_id: str | None`
- `infrastructure_object_id: str | None`
- `brigade: str | None`
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

## Entity: DisplacementConfig

Описывает настройки вытеснения и функции обводнённости.

### Поля

- `config_id: str`
- `lu_id: str | None`
- `sloy_id: str | None`
- `curve_points: list[DisplacementCurvePoint]`
- `watercut_unit: str`
- `notes: str | None`

### Related Entity: DisplacementCurvePoint

- `NIZ: float`
- `watercut: float`

### Инварианты

- `lu_id` и `sloy_id` задают scope конфига по `LU/SLOY`; конфиг может быть привязан к `LU` и при необходимости уточнён до уровня `SLOY`;
- точки отсортированы по `NIZ`;
- `NIZ` монотонен;
- формат `watercut` согласован с `watercut_unit`;
- в текущей методике `Module B` ось `NIZ` используется как нормализованный показатель, рассчитываемый из `NIZ` и накопленной нефти по формуле, зафиксированной в контракте `Module B`;
- поле `NIZ` внутри `DisplacementCurvePoint` хранит именно нормализованную координату характеристики вытеснения, а не абсолютный объём начальных извлекаемых запасов;
- между соседними точками характеристики используется линейная интерполяция.

---

## Entity: DeclineConfig

Описывает предпосылки по падению жидкости во времени.

### Поля

- `config_id: str`
- `lu_id: str | None`
- `sloy_id: str | None`
- `base_monthly_decline_values: list[MonthlyDeclinePoint]`
- `new_wells_monthly_decline_values: list[MonthlyDeclinePoint]`
- `notes: str | None`

### Related Entity: MonthlyDeclinePoint

- `month_index: int`
- `liquid_decline_factor: float`

### Интерпретация

- в текущем интерфейсе `Module G` значение `liquid_decline_factor` вводится как годовой темп падения жидкости для соответствующего месяца горизонта;
- `Module B` не должен трактовать это поле как уже готовый месячный коэффициент, а обязан пересчитывать его во внутренний суточный шаг расчёта.

### Инварианты

- `month_index >= 0`;
- коэффициенты неотрицательны;
- `lu_id` и `sloy_id` задают scope конфига по `LU/SLOY`; конфиг может быть привязан к `LU` и при необходимости уточнён до уровня `SLOY`;
- в текущей методике `Module B` массив `base_monthly_decline_values` используется как характеристика снижения жидкости для фонда `Base`;
- в текущей методике `Module B` массив `new_wells_monthly_decline_values` используется как характеристика снижения жидкости для `New wells` после даты соответствующего ГТМ или события запуска;
- годовой темп падения должен пересчитываться `Module B` в эквивалентный суточный коэффициент перед применением к `liquid_rate`;
- стандартный горизонт ручных рядов decline — 24 месяца, если отдельный сценарий не задаёт иное.

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
- `oil_rate: float`
- `gas_rate: float | None`
- `liquid_rate: float`
- `water_rate: float | None`
- `gor: float | None`
- `watercut: float | None`
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
- `lu_id: str | None`
- `sloy_id: str | None`
- `well_pad_id: str | None`
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
- `Net Back: float  | None`
- `oil_price: float | None`
- `gas_price: float | None`
- `liquid_handling_cost: float | None`
- `water_handling_cost: float | None`
- `gas_handling_cost: float | None`
- `discount_rate: float | None`
- `gtm_costs_by_type: dict[str, float] | None`
- `tax_config: dict[str, object] | None`
- `notes: str | None`

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
- `created_at: str`
- `status: str`
- `metadata: dict[str, object] | None`

### Source Types

- `uploaded_gtm`
- `optimized_krs`
- `planner_manual_edit`

### Инварианты

- сценарии неизменяемы после создания;
- если `forecast_start_date` и `forecast_end_date` не заданы явно пользователем, система должна назначать default horizon от даты запуска сценария до `31 декабря` следующего календарного года;
- производные сценарии ссылаются на родителя, если это применимо.

---

## Entity: PlannerScheduleRevision

Описывает версию графика, возвращаемую из planner обратно в расчётный контур.

### Поля

- `revision_id: str`
- `planner_version_id: str | None`
- `parent_scenario_id: str`
- `items: list[KrsScheduleItem]`
- `edited_at: str`
- `editor: str | None`
- `metadata: dict[str, object] | None`

---

## Entity: RecalculationScenarioInput

Описывает вход для нового пересчёта на основе графика, скорректированного в planner.

### Поля

- `parent_scenario_id: str`
- `schedule: KrsScheduleScenario`
- `recalculation_mode: str`
- `metadata: dict[str, object] | None`

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
