---
name: field-hierarchy
description: Use when implementing hierarchical table or tree-table rendering in another program and the hierarchy must behave like New project: three levels (license area -> cluster -> well), expandable parent rows, aggregated metrics on parent nodes, and grouped status cells that collapse child states into a parent state.
---

# Hierarchy Display


Target behavior:
- 3 levels only:
  - `license` (`УН` / `license_area`)
  - `cluster` (`Куст` / `cluster_name`)
  - `well` (`Скважина` / `well_name`)
- parent rows are synthetic aggregate nodes
- leaf rows are original domain rows
- expand/collapse works per parent key
- default expansion collapses all `license` nodes after data load

## Required input row contract

Leaf rows must provide at least:
- `license_area`
- `cluster_name`
- `well_name`


## Implementation pattern

Build hierarchy in 3 steps.

### 1. Build grouped date columns

Create display columns from the master date axis:
- `day`: one column per date
- `month`: one column per `YYYY-MM`
- `year`: one column per `YYYY`

Each grouped column must keep the list of original dates it covers.

Minimal shape:

```js
{
  key: "2026-05",
  label: "май 2026",
  dates: ["2026-05-01", "2026-05-02", ...]
}
```

### 2. Convert leaf rows into grouped rows

For each leaf row:
- map `statuses[index]` to `statusByDate[dates[index]]`
- for every grouped display column:
  - collect statuses for all dates inside the group
  - set grouped status to `0` if any child value is `0`
  - otherwise set to `1`

This rule is mandatory if the display must match `New project`.

Pseudo:

```js
groupedStatuses[column.key] = values.includes(0) ? 0 : 1
```

Also derive:

```js
failureCount = event_dates.length
```

### 3. Build hierarchy rows

Group leaf rows by:
- `license_area || "Без УН"`
- inside it by `cluster_name || "Без куста"`

Create synthetic nodes in this order:
1. license row
2. cluster row
3. well rows only if the cluster node is expanded

Keys must be stable:

```text
license:${license}
cluster:${license}:${cluster}
well:${license}:${cluster}:${well}
```

## Parent row aggregation rules

Use these rules exactly.

### Numeric metrics

Average numeric forecast-like values:

```js
averageValue(values.filter(v => v !== null && v !== undefined))
```

Apply averaging to:
- `catboost_nno`
- `probabilistic_nno`
- `predicted_nno`
- `actual_nno`

### Failure count

Sum child counts:

```js
rows.reduce((sum, row) => sum + row.failureCount, 0)
```

### Category label

Parent label is the unique set of child categories joined by comma.

If empty, return `"-"`.

### Prediction source

Parent value rules:
- no child values -> `null`
- one unique value -> that value
- more than one unique value -> `"mixed"`

### Grouped statuses

For every visible grouped date column:
- parent status is `0` if any child grouped status is `0`
- else `1`

Pseudo:

```js
function aggregateStatuses(rows, columns) {
  const groupedStatuses = {}
  columns.forEach((column) => {
    const values = rows.map((row) => row.groupedStatuses[column.key] ?? 1)
    groupedStatuses[column.key] = values.includes(0) ? 0 : 1
  })
  return groupedStatuses
}
```

## Expansion behavior

State:

```js
expandedKeys = Set<string>
```

Rules:
- clicking a parent toggles its key in `expandedKeys`
- on initial load:
  - add all `license:${license_area}` keys to `expandedKeys`
  - leave cluster nodes collapsed unless product requirements say otherwise

## Scope selection behavior

Selection must resolve to leaf rows only.

Rules:
- no selected hierarchy node -> all leaf rows
- selected `license` node -> all leaf rows with this `license_area`
- selected `cluster` node -> all leaf rows with this `license_area` and `cluster_name`
- selected `well` node -> exactly matching leaf row(s)

Do not compute charts from synthetic parent rows. Always resolve selection back to leaf rows first.

## Rendering rules

Render a flat table from `hierarchyRows`, not a recursive DOM tree.

Each row must carry:
- `nodeType`: `license | cluster | well`
- `depth`: `0 | 1 | 2`

Use these for indentation and toggle placement.

Recommended columns:
- level label
- `license_area`
- `cluster_name`
- `well_name`
- aggregated forecast metrics
- one status cell per grouped period

For non-leaf levels:
- show `-` for fields that do not apply

## Invariants

If you want the result to match `New project`, keep these invariants:
- hierarchy depth is fixed at 3
- parent nodes are computed, not stored
- grouped period status uses OR-over-failures semantics:
  - any failure in period -> period cell is failure
- charts and secondary analytics must use resolved leaf rows, not parent rows
- parent metrics are deterministic functions of child rows only

## Minimal validation checklist

After implementation verify:
1. expanding a license reveals clusters only for that license
2. expanding a cluster reveals only its wells
3. collapsing a parent removes all descendants from the rendered flat list
4. a parent status cell becomes `0` if one child has a failure inside the same displayed period
5. selecting a parent node drives charts from underlying leaf rows only
6. default load expands all top-level licenses

## When adapting to another stack

Keep the algorithm unchanged even if the UI stack changes:
- React, Vue, Svelte, Angular, plain JS: all acceptable
- table library vs custom grid: acceptable

What must remain unchanged is:
- grouping order
- synthetic key format
- parent aggregation rules
- leaf-row-only scope resolution
