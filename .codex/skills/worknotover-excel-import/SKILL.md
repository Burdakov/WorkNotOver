---
name: worknotover-excel-import
description: Используй, когда задача касается Excel upload, parsing, preview, column mapping, validation, normalization, ручных input-конфигов или сохранения нормализованных наборов данных в storage layer WorkNotOver. Этот skill нужен перед изменениями Module A и любых функций, зависящих от структуры исходных таблиц и ручных исходных вводов.
---

# WorkNotOver Excel Import

## Назначение

Дать устойчивый способ превращать пользовательские Excel-файлы и ручные input-конфиги в нормализованные наборы данных и сохранять их в канонический storage layer проекта.

## Что читать в первую очередь

- `docs/contracts/module-a-task-package.md`
- `docs/contracts/core-data-model.md`

## Когда использовать

- при добавлении новых Excel-источников;
- при изменении auto-mapping колонок;
- при изменении validation rules;
- при изменении preview/import API;
- при изменении ручных input-форм для `DisplacementConfig`, `BrigadeAvailabilityConfig`, `EconomicsConfig`;
- при добавлении новых колонок для газа, `GOR` и связанных производственных показателей;
- при нормализации wells, GTM или infrastructure datasets;
- при развитии `Module A`;
- при переходе от file-based хранения к `Postgres`.

## Принципы импорта

1. Excel — это exchange format, а не business model.
2. Ручные формы — это input mechanism, а не runtime source of truth.
3. Каноническое operational storage для normalized datasets и manual inputs — база данных `Postgres`.
4. Нормализуй данные на границе системы максимально рано.
5. После нормализации сохраняй dataset или manual input set в storage layer и только потом публикуй его downstream-модулям.
6. Лучше явная валидация, чем тихое угадывание.
7. Всегда сообщай о skipped rows и ambiguous mappings.
8. Не выпускай raw DataFrame-структуры и raw form-state за пределы `Module A`.

## Обязательный поток обработки

1. Прочитать workbook и список sheet или принять manual input payload.
2. Построить preview, если источник файловый.
3. Найти колонки по hints, если источник файловый.
4. Дать возможность explicit remapping, если источник файловый.
5. Нормализовать:
   - даты;
   - числа;
   - текст;
   - IDs;
   - категориальные значения;
   - газовые поля и `GOR`;
   - иерархию `LU -> SLOY -> WellPad`.
6. Провалидировать обязательные поля и согласованность иерархии.
7. Сохранить normalized dataset или manual input set в persistence layer.
8. Вернуть normalized payload, dataset/manual input reference и validation report.

## Общие правила нормализации

- Dates -> ISO format
- Numbers -> поддержка decimal comma и embedded spaces
- Пустые значения -> `None`
- Totals/footer rows -> skip and report
- Missing required identifiers -> reject или skip с warning по контракту

## Минимально ожидаемый результат

- preview records
- detected columns
- normalized entities
- dataset reference / stored dataset metadata
- warnings
- skipped row count

## Красные флаги

- parsing logic смешана с forecast logic;
- normalized datasets живут только в памяти и не попадают в `Postgres`;
- manual inputs остаются только в UI-state и не попадают в storage layer;
- `LU`, `SLOY`, `WellPad` теряются или конфликтуют при нормализации;
- газовые поля или `GOR` теряются, получают несогласованные единицы или не доходят до normalized outputs;
- один и тот же тип файла выдаёт разные формы результата в разных ветках;
- column hints зашиты в код без обновления contracts;
- manual mapping есть в UI, но игнорируется backend;
- тихое приведение критичных бизнес-данных без предупреждений.
