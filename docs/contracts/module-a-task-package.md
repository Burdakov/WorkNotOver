# Пакет задачи для Module A

## Модуль

`Module A: Загрузка и нормализация Excel`

---

## Название задачи

Реализовать нормализованный pipeline входных данных для Excel-источников и ручных конфигурационных вводов.

---

## Цель

Создать первую production-ready версию import layer, которая:

- принимает исходные Excel-файлы;
- принимает ручные вводные данные через UI-формы;
- автоматически определяет или вручную сопоставляет нужные колонки;
- валидирует входящие данные;
- преобразует их в нормализованные внутренние наборы данных;
- сохраняет эти наборы данных в persistence layer проекта;
- формирует warnings и validation details;
- публикует стабильные контракты для downstream-модулей.

`Module A` является единственной точкой входа структурированных исходных данных. Excel в нём рассматривается как `exchange format`, а ручные параметры — как `manual input configs`. Каноническое operational storage для `normalized datasets` и `manual inputs` — persistence layer проекта на `Postgres`. Нормализованные наборы данных и ручные вводные сохраняются в storage layer и затем используются `Module B`, `Module D` и `Module E`. В сценарном контуре эти данные косвенно доходят до `Module F: Planner` и `Module G: Сценарный UI и обратный пересчёт`, но сам `Module A` не должен знать их внутреннюю логику.

---

## Scope

### Входит в задачу

- загрузка и чтение Excel-файлов для:
  - текущего режима скважин;
  - графика ГТМ / кандидатных мероприятий;
  - инфраструктурных ограничений;
  - внешнего готового графика КРС;
- приём и валидация ручных конфигурационных вводов для:
  - характеристик вытеснения;
  - графика доступности бригад;
  - коэффициентов отказности;
  - экономических вводных;
- извлечение листов и колонок;
- auto-detection и manual mapping обязательных полей;
- нормализация дат, чисел, строк, идентификаторов и категориальных значений;
- нормализация доменной иерархии:
  - `LU`
  - `SLOY`
  - `WellPad`
- формирование:
  - `NormalizedWellDataset`;
  - `NormalizedGtmDataset`;
  - `NormalizedInfrastructureDataset`;
  - `ImportedKrsSchedulePayload`;
- формирование и сохранение:
  - `ManualInputSet`
  - `ManualInputReference`
  - связанных config entities;
- сохранение нормализованных наборов данных в persistence layer;
- возврат validation report с:
  - отсутствующими полями;
  - пропущенными строками;
  - ошибками преобразования типов;
  - неоднозначными mapping-сопоставлениями.

### Не входит в задачу

- расчёт профиля добычи;
- расчёт экономики;
- построение и оптимизация графика КРС;
- проверка инфраструктурной допустимости сценария;
- логика `Planner`, кроме подготовки нормализованного внешнего графика КРС к открытию;
- логика `Scenario UI` и обратного пересчёта.

---

## Зависимости

### Зависит от

- shared contract definitions из [core-data-model.md](/C:/Users/Burda/Documents/IRITO/WorkNotOver/docs/contracts/core-data-model.md)
- текущей backend-структуры проекта
- storage layer / repository layer проекта

### Не должен зависеть от

- business logic `Module B`
- economics logic `Module C`
- schedule/optimizer logic `Module D`
- planner logic `Module F`
- scenario orchestration logic `Module G`
- frontend-only structures

---

## Входы

### Входной источник 1

Excel-файл текущего режима скважин.

Ожидаемые логические поля:

Обязательные для нормализации `wells` dataset:

- well identifier / well name
- LU
- WellPad
- fund state (`в работе` / иные статусы)
- current oil rate
- current liquid rate
- current watercut

Необязательные, но допустимые к загрузке:

- current gas rate
- current GOR
- SLOY

### Входной источник 2

Excel-файл значений `NIZ` по скважинам.

Ожидаемые логические поля:

- well identifier / well name
- LU
- WellPad
- NIZ
- cumulative oil production, если доступно
- cumulative gas production, если доступно

Результат должен сохраняться как отдельный dataset с `dataset_type = niz` и использоваться для сценарного связывания `well_name -> NIZ`, `well_name -> current_cumulative_oil` и `well_name -> current_cumulative_gas`.

При загрузке dataset типа `niz` UI и import-layer должны поддерживать дополнительное построчное сопоставление `well_name` из NIZ с уже загруженными скважинами из `wells` и `gtm`.

Правила:

- сначала выполняется обычное сопоставление колонок;
- затем для каждой строки `niz` должен формироваться список предложенных скважин по похожему буквенному и числовому индексу;
- пользователь должен иметь возможность выбрать корректную скважину из dropdown;
- если для части скважин из `wells` и `gtm` соответствующая строка `niz` не нашлась, UI должен показывать отдельный список unmatched-скважин с ручным вводом `NIZ`, `current_cumulative_oil` и `current_cumulative_gas`;
- для unmatched-скважин ручной ввод должен поддерживать вставку значений по столбцам через copy-paste;
- после подтверждения dataset должен сохраняться уже с каноническим `well_name`, используемым в scenario-bound связывании.

### Входной источник 3

Excel-файл графика ГТМ / кандидатных мероприятий.

Ожидаемые логические поля:

- well identifier / well name
- area
- LU
- SLOY
- WellPad
- brigade, если доступно
- GTM type
- planned work
- candidate dates
- expected OIl increment
- expected liquid increment
- expected gas increment, если доступно
- expected GOR change, если доступно
- duration, если доступно

### Входной источник 4

Excel-файл инфраструктурных ограничений.

Ожидаемые логические поля:

- infrastructure object name
- object type
- commissioning date
- capacities Oil
- capacities Liquid
- capacities Gas
- connection / relation to wells or upstream object

### Входной источник 5

Excel-файл внешнего готового графика КРС.

Ожидаемые логические поля:

- brigade
- area, если доступно
- well
- start date
- end date
- planned work
- oil increment
- liquid increment, если доступно
- gas increment, если доступно
- GOR / gas factor, если доступно
- duration, если доступно

Результат должен нормализоваться в `KrsScheduleScenario` и сохраняться в storage layer как dataset с `dataset_type = external_krs_schedule`.

### Входной источник 6

Ручной ввод через UI-формы.

Ожидаемые логические группы:

- `DisplacementConfig`
- `BrigadeAvailabilityConfig`
- `FailureCoefficientConfig`
- `EconomicsConfig`

Результат должен сохраняться как `ManualInputSet` и связанные config entities.

---

## Выходы

### Выход 1

`NormalizedWellDataset`

Содержит валидированный набор нормализованных сущностей `WellState` c reference-полями иерархии `LU`, `SLOY`, `WellPad`.

### Выход 2

`NizDataset`

Содержит валидированный набор scenario-bound сущностей `NizByWell`, пригодных для связывания `well_name -> NIZ`, `well_name -> current_cumulative_oil` и `well_name -> current_cumulative_gas` внутри активного сценария.

### Выход 3

`NormalizedGtmDataset`

Содержит валидированный набор нормализованных сущностей `GtmCandidate` c reference-полями иерархии `LU`, `SLOY`, `WellPad`.

### Выход 4

`NormalizedInfrastructureDataset`

Содержит:

- `InfrastructureObject[]`
- `InfrastructureConnection[]`

### Выход 5

`ImportValidationReport`

Должен включать:

- file metadata;
- sheet metadata;
- column mappings;
- skipped rows;
- warnings;
- fatal validation errors, если есть.

### Выход 6

`DatasetReference` / metadata сохранённого набора данных

Должен позволять downstream-модулям и сценарному контуру работать уже с сохранённым dataset, а не с raw Excel-файлом.

### Выход 7

`ImportedKrsSchedulePayload`

Должен позволять `Module F: Planner` открыть внешний график КРС как готовую planner-compatible schedule model без обязательного прохождения через `Module D`.

### Выход 8

`ManualInputReference`

Должен позволять downstream-модулям получать связанный набор ручных конфигурационных вводов из storage layer без зависимости от raw form-state.

---

## Business Rules

1. Даты нормализуются в ISO-формат `YYYY-MM-DD`.
2. Числа должны корректно принимать:
   - десятичную запятую;
   - пробелы в числовых значениях;
   - Excel numeric cell types.
3. Отсутствие обязательных полей не должно проходить молча.
4. Все skipped rows должны учитываться и попадать в отчёт.
5. Column mapping должен поддерживать:
   - auto-detection по заголовкам и подсказкам;
   - явное ручное сопоставление.
6. Газовые поля и `GOR` должны нормализоваться в одном согласованном формате и единицах измерения по проекту.
7. Стабильные IDs должны быть сохранены или сгенерированы для:
   - wells;
   - GTM;
   - LU;
   - SLOY;
   - WellPad;
   - infrastructure objects;
   - infrastructure connections.
8. Нормализованные выходы не должны содержать raw pandas objects.
9. Иерархические reference-поля `lu_id`, `sloy_id`, `well_pad_id` должны быть согласованы между `WellState` и `GtmCandidate`, если доступны.
10. После успешной нормализации данные и ручные вводные должны сохраняться в `Postgres` или другой согласованный storage layer проекта.
11. `Module A` не должен вшивать forecast-, economics-, planner- или scenario-assumptions.
12. Внешний готовый график КРС после нормализации должен сохраняться как `Dataset` / `DatasetVersion` с `dataset_type = external_krs_schedule` и иметь извлекаемую структуру `KrsScheduleScenario`.
13. Ручной коэффициент отказности должен сохраняться как отдельная конфигурационная сущность в составе `ManualInputSet`, а не как неструктурированное поле UI.
14. Dataset типа `niz` должен позволять построить полное scenario-bound отображение `well_name -> NIZ` для всех скважин, которые downstream-сценарий привяжет из `wells` и `gtm`; если такого покрытия нет, сценарный контур должен маркировать входы как неполные.

---

## Edge Cases

Нужно обработать как минимум:

- пустой лист;
- отсутствие обязательных колонок;
- дубли названий скважин;
- дубли строк ГТМ;
- некорректные даты;
- некорректные capacities;
- некорректные gas rate / GOR значения;
- внешний график КРС с отсутствующей длительностью, но корректными датами начала/конца;
- внешний график КРС с пересечениями или конфликтами, которые допустимы для импорта, но должны быть отражены в validation report;
- смешанные text/numeric cells;
- смещённые заголовки;
- итоговые строки в конце Excel;
- одна и та же скважина встречается с разными `LU` / `SLOY` / `WellPad`;
- инфраструктурный объект без commissioning date;
- скважина есть в GTM, но отсутствует в wells dataset.

---

## Files / Ownership

### Разрешено создавать или менять

- `backend/app/api/import.py`
- `backend/app/schemas/import_models.py`
- `backend/app/schemas/common.py`
- `backend/app/services/import/*`
- `backend/app/db/*`
- `backend/app/repositories/*`
- `backend/app/main.py` только для подключения router при необходимости
- `docs/contracts/module-a-import.md`

### Нельзя менять без отдельного согласования

- forecast logic
- economics logic
- optimizer logic
- planner logic
- scenario UI logic

---

## Рекомендуемое внутреннее разбиение сервиса

- `excel_reader.py`
- `column_mapper.py`
- `normalizers.py`
- `validators.py`
- `dataset_builder.py`
- `dataset_repository.py`
- `manual_input_repository.py`

Опционально:

- `import_warnings.py`

---

## Рекомендуемые API endpoints

- `POST /api/import/wells/upload`
- `POST /api/import/gtm/upload`
- `POST /api/import/infrastructure/upload`
- `POST /api/import/preview`
- `POST /api/import/normalize`
- `POST /api/import/commit`
- `POST /api/manual-inputs/save`
- `GET /api/manual-inputs/{manual_input_set_id}`

Минимально допустимая первая версия:

- по одному combined endpoint на каждый тип файла, который возвращает preview + normalized payload + dataset reference + validation report

---

## Обязательные тесты

### Happy path

- корректный wells file
- корректный GTM file
- корректный infrastructure file

### Validation path

- отсутствует обязательная колонка
- некорректная дата
- некорректные числовые значения
- дубли строк
- пустые строки между валидными строками

### Normalization path

- запятые в десятичных значениях
- пробелы в числовых ячейках
- разные форматы дат
- альтернативные названия колонок
- разные варианты именования газовых полей и `GOR`

### Persistence path

- dataset сохраняется в storage layer
- dataset получает стабильный reference/id
- повторная загрузка не ломает структуру хранения

### Manual input path

- ручные вводные сохраняются как `ManualInputSet`
- `DisplacementConfig`, `BrigadeAvailabilityConfig`, `EconomicsConfig` корректно привязываются к `manual_input_set_id`
- `FailureCoefficientConfig` корректно привязывается к `manual_input_set_id`
- коэффициент отказности корректно сохраняется как для `LU`, так и для `SLOY`

### Hierarchy path

- корректно нормализуются `LU`, `SLOY`, `WellPad`
- `WellState` и `GtmCandidate` получают согласованные reference-поля иерархии

### Cross-entity consistency

- GTM ссылается на неизвестную скважину
- infrastructure connection ссылается на неизвестную скважину или объект

---

## Acceptance Criteria

1. `Module A` умеет принимать Excel-источники и ручные конфигурационные вводы как единый input layer.
2. Normalized outputs соответствуют shared contracts.
3. Validation report структурирован и понятен.
4. Auto-detection работает для типовых русскоязычных заголовков.
5. Manual remapping доступен, если auto-detection не сработал.
6. Газовые поля и `GOR` корректно импортируются и нормализуются в wells и GTM inputs, если они присутствуют.
7. Нормализованные наборы данных сохраняются в `Postgres`/storage layer и получают стабильную dataset reference.
8. Ручные вводные сохраняются в storage layer и получают стабильную `ManualInputReference`.
9. Ручной коэффициент отказности сохраняется в составе `ManualInputSet` как структурированная сущность с областью действия `LU` или `SLOY`.
10. Иерархия `LU -> SLOY -> WellPad -> WellState` корректно отражается в normalized outputs, если исходные данные её содержат.
11. Внешний готовый график КРС может быть загружен, нормализован и сохранён как `external_krs_schedule`.
12. Ни raw Excel-, ни pandas-структуры, ни raw form-state не выходят за границы import layer.
13. Unit- или service-level tests покрывают основные успешные, ошибочные, hierarchy-, gas-, external-krs- и persistence-сценарии.
14. Документация по контракту `Module A` обновляется в той же задаче, что и реализация.
15. Dataset `niz` может быть привязан к сценарию как отдельный вход и использоваться downstream-модулями как канонический источник `NIZ`.

---

## Deliverables

- import schemas
- import API endpoints
- import services
- persistence/repository integration for stored datasets
- persistence/repository integration for manual inputs
- validation report structure
- tests
- contract doc update
- короткая заметка с перечислением допущений и неподдерживаемых Excel-паттернов

---

## Coordinator Note

Этот модуль — фундамент всей системы.
Не оптимизируй его под удобство одного будущего модуля ценой чистых normalized contracts.
Если поле неоднозначно, лучше явно вынести это в validation report, чем молча угадать.
Если данные ещё не сохранены в storage layer, считай import incomplete.
