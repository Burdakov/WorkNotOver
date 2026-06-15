# Контракт Module B

## Модуль

`Module B: OPM Flow hydrodynamic forecast и расчёт добычи`

## Назначение

`Module B` владеет расчётным контуром прогноза добычи нефти, воды, жидкости, газа, `GOR`, обводнённости, пластового давления, насыщенностей строится вокруг внешнего гидродинамического симулятора `OPM Flow`: модуль подготавливает OPM/Eclipse-compatible case, запускает симулятор, импортирует raw results и сохраняет scenario-bound нормализованные результаты для downstream-модулей.

## Методические исходники для новой версии

Исходные материалы для проектирования новой версии прогнозного ядра вынесены в отдельную папку:

- `docs/forecast-module/references/OPM_Flow_Reference_Manual_2025-10_Rev-0_compressed.pdf`
- `docs/forecast-module/docs/OPM_FLOW_REFERENCE_GUIDE.md`
- `docs/forecast-module/references/opm_flow_manual_2025_10_index.json`
- `docs/forecast-module/README.md`
- `docs/forecast-module/PROMPT_MASTER.md`
- `docs/forecast-module/docs/EXTERNAL_REFERENCES.md`

Локальный OPM Flow manual, сформированный по нему справочник и JSON-индекс
являются основным методическим источником для новой версии `Module B`.
Они определяют порядок секций OPM/Eclipse deck, размещение ключевых слов,
структуру include-файлов, ожидаемые raw output artifacts и правила подготовки
`simulation_runs`.

Текущий контракт фиксирует согласованный целевой интерфейс `Module B`, обязательные scenario-level outputs и правила совместимости с `Module C`, `Module D`, `Module E`, `Module F` и `Module G`.
Сущности, необходимые для этой методики, закреплены в `core-data-model.md`.

Основной контрактный метод расчёта:

- `forecast_method = opm_flow_blackoil`
- `Module B` формирует из нормализованных данных `Module A` расчётный OPM case: `RUNSPEC`, `GRID`, `PROPS`, `REGIONS`, `SOLUTION`, `SCHEDULE`, `SUMMARY`;
- `Module B` запускает внешний `flow` executable, если он доступен в runtime environment;
- raw OPM artifacts сохраняются неизменяемо в scenario/run storage;
- importer переводит raw artifacts в нормализованные scenario-bound tables: well/field/group time series, grid static state, grid dynamic state, material balance by region/FIPNUM, RFT/connection diagnostics;
- UI и downstream-модули читают только нормализованные результаты `SimulationRun`, а не выполняют forecast math повторно.

## Входы
минимально необходимый набор исходных данных, описанный в мануале
## Выходы
набор выходных файлов OPM Flow, считанных и загруженных в систему

## Зона ответственности
функционал, описанный в PROMPT_MASTER.md в forecast-module/docs
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
описана в PROMPT_MASTER.md в forecast-module/docs

### 1. Data contracts and validation

Module B не читает raw Excel/CSV/YAML напрямую.
Все входы приходят из Module A как normalized datasets, references или сохранённые manual/config entities.
