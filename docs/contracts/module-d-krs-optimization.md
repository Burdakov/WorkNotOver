# Контракт Module D

## Модуль

`Module D: График КРС и оптимизатор`

## Назначение

`Module D` строит допустимый график КРС и оптимизирует очередность мероприятий.

## Входы

- `NormalizedGtmDataset`
- `ProductionScenario`
- `EconomicsResult`
- `KrsResourceConfig`
- `OptimizationConfig`
- `BrigadeAvailabilityConfig`
- `FailureCoefficientConfig`
- `InfrastructureConstraintCheckResult` из `Module E`

## Выходы

- `KrsScheduleScenario`
- `OptimizationResult`
- scenario ranking / candidate scenarios

## Зона ответственности

- построение feasible KRS schedule
- учёт количества бригад
- учёт длительностей по типам
- учёт календарных ограничений
- учёт коэффициентов отказности по `LU` и `SLOY`
- генерация и ранжирование сценариев
- вызов infra-check и учёт его ответа в оптимизации
- передача готового графика в `Module F: Planner`

## Не входит

- импорт исходных данных
- расчёт профиля добычи
- расчёт экономики
- хранение planner revisions
- orchestration UI

## Зависимости

- получает данные из `Module A`, `Module B`, `Module C`
- получает ручные ограничения по бригадам и коэффициенты отказности из `Module A`
- обменивается infra-check с `Module E`
- публикует график в `Module F`
- отдаёт сводные результаты в `Module G`

## Контрактные правила

1. `Module D` не реализует infra-rules внутри себя.
2. `Module D` не владеет ручной editable schedule-моделью planner.
3. Любой exported schedule должен быть сериализуем в `PlannerScheduleRevision`.
4. Коэффициент отказности должен читаться как внешний конфигурационный вход, а не как локально зашитое правило optimizer.
