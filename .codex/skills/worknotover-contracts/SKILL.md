---
name: worknotover-contracts
description: Используй, когда создаются или меняются shared schemas, API payloads, database models, scenario entities или межмодульные data contracts в WorkNotOver. Включай этот skill перед добавлением новых полей или изменением смысла сущностей.
---

# WorkNotOver Contracts

## Назначение

Защищать согласованность shared entities и API-контрактов между модулями.

## Что читать в первую очередь

- `docs/contracts/core-data-model.md`
- соответствующий модульный контракт в `docs/contracts/`

## Когда использовать

- при добавлении поля в shared entity;
- при создании request/response schemas;
- при создании ORM-моделей, отражающих shared entities;
- при изменении planner payload;
- при проектировании storage-level сущностей `Dataset`, `DatasetVersion`, `DatasetReference`;
- при добавлении новых ручных конфигурационных сущностей, например коэффициента отказности по `LU` или `SLOY`;
- при добавлении или изменении газовых полей, `GOR`, gas production и связанных economics/infra-показателей;
- при проектировании `Scenario`, `KrsScheduleItem`, `ProductionScenario`, `EconomicsResult` и связанных DTO.

## Правила контракта

1. Названия и смысл shared entities берутся из `core-data-model.md`.
2. Если добавляешь поле в код, то:
   - либо это уже существующее документированное поле;
   - либо нужно обновить контракт в той же задаче.
3. Жёстко различай:
   - raw uploaded data;
   - stored dataset layer (`Dataset`, `DatasetVersion`, `DatasetReference`);
   - normalized datasets;
   - scenario results.
4. UI должен потреблять backend contracts, а не изобретать локальные параллельные структуры.
5. Избегай временных полей с размытым смыслом.
6. Газовые поля (`gas_rate`, `current_gor`, `gas_increment`, `gas_revenue` и т.п.) считаются частью canonical shared model, а не временным расширением "сбоку".

## Рабочий порядок

1. Найди владеющую сущность в `core-data-model.md`.
2. Проверь, к какому уровню относится поле:
   - import layer;
   - dataset storage layer;
   - normalized model;
   - scenario result;
   - planner revision.
3. Обнови schema definitions.
4. Обнови serialization / deserialization.
5. Обнови contract docs, если изменился смысл.
6. Добавь целевой тест на новый контрактный surface.

## Рекомендации по именованию

- IDs — стабильные строки.
- Даты — ISO `YYYY-MM-DD`.
- Scenario-level outputs несут `scenario_id`.
- Dataset-level outputs несут `dataset_id` и, при необходимости, `dataset_version_id`.
- Предпочитай явные имена вроде `expected_oil_increment`, а не размытые вроде `increment`.
- Для газовых полей придерживайся явных имён вроде `current_gas_rate`, `expected_gas_increment`, `average_gor`.
- Для ручных конфигураций с областью действия используй явные поля уровня, например `scope_type`, `lu_id`, `sloy_id`, вместо неструктурированных словарей.

## Красные флаги

- одна сущность представлена по-разному в двух модулях;
- API возвращает поля, не описанные в docs;
- storage layer сущности существуют в коде, но не описаны в `core-data-model.md`;
- газовые поля добавлены в один модуль, но не протянуты через весь shared contract;
- одно поле означает разное в разных местах;
- frontend зависит от внутренних деталей backend вместо контракта.
