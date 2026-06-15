# WorkNotOver Forecast Module Reference Kit

Эта папка является методической базой для разработки `Module B`: обвязки
`OPM Flow`, генерации OPM/Eclipse-compatible deck-файлов, запуска
`simulation_runs` и импорта результатов в нормализованные scenario-bound
артефакты.

## Основной источник истины

Для гидродинамического симулятора и генерации исходных данных приоритет имеют:

1. `references/OPM_Flow_Reference_Manual_2025-10_Rev-0_compressed.pdf` —
   локальная копия OPM Flow Reference Manual.
2. `docs/OPM_FLOW_REFERENCE_GUIDE.md` — рабочий справочник по структуре deck,
   ключевым словам, include-файлам и ожидаемым выходным артефактам.
3. `references/opm_flow_manual_2025_10_index.json` — извлечённый из PDF индекс
   оглавления и ключевых слов для быстрых проверок.
4. `../contracts/module-b-forecast.md` — контракт WorkNotOver для Module B.


## Что внутри

- `references/` — локальные методические источники и машинный индекс manual.
- `docs/OPM_FLOW_REFERENCE_GUIDE.md` — основной рабочий справочник для
  case-builder, runner, importer и UI-потребителей результатов.
- `docs/EXTERNAL_REFERENCES.md` — внешние ссылки и локальные primary references.
- `PROMPT_MASTER.md` — legacy prompt-kit для reduced-order waterflood/proxy
  ветки; он не является источником истины для OPM deck generation.

## Правило для разработки

Перед добавлением или изменением OPM-ключевого слова в runtime-коде нужно
сверить его с локальным manual, `OPM_FLOW_REFERENCE_GUIDE.md` и индексом. Новая
логика должна сохранять inspectable input artifacts в `simulation_runs`:

```text
input/FIELD_2D_<SCENARIO>.DATA
input/includes/runspec.inc
input/includes/grid.inc
input/includes/edit.inc
input/includes/props.inc
input/includes/regions.inc
input/includes/init.inc
input/includes/summary.inc
input/includes/schedule.inc
```

Если поведение не подтверждено manual или справочником, оно считается
экспериментальным и должно быть явно помечено в diagnostics/warnings.
