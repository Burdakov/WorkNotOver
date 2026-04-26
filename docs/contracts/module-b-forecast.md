# Контракт Module B

## Модуль

`Module B: Расчёт базовой добычи и эффекта ГТМ`

## Назначение

`Module B` владеет расчётной логикой профиля добычи нефти, газа, жидкости, `GOR` и формирует `ProductionScenario`.

## Входы

- `NormalizedWellDataset`
- `NormalizedGtmDataset`
- `DisplacementConfig`
- `DeclineConfig`
- при пересчёте из planner: `PlannerScheduleRevision` или нормализованный schedule input из `Module G`

## Выходы

- `ProductionScenario`
- `WellForecastResult[]`
- `ScenarioProductionSummary`
- рассчитанные инкременты по мероприятиям

## Зона ответственности

- baseline forecast
- gas forecast
- `GOR` calculation
- GTM effect calculation
- watercut / displacement logic
- liquid decline logic
- агрегация профилей по датам и скважинам
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

## Контрактные правила

1. `Module B` не читает raw Excel напрямую.
2. Любой пересчёт по planner revision создаёт новый scenario-level output.
3. Все scenario-level outputs несут `scenario_id`.
4. Газовые показатели и `GOR` считаются частью того же `ProductionScenario`, а не отдельным параллельным результатом.
5. Внутренние расчётные допущения не дублируются в UI.
