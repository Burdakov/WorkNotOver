<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8010/api'
const PLANNER_CHART_HEIGHT = 180
const PRODUCTION_CHART_HEIGHT = 260
const PRODUCTION_CHART_WIDTH = 1280
const DEFAULT_PLANNER_COLUMNS = {
  brigade: 'Бригада',
  area: 'Участок',
  well: 'Скв.',
  start_date: 'Дата начала (план)',
  end_date: 'Заверш рем (план)',
  increment: 'Qн, тн/сут',
  planned_work: 'Планируемый объем работ',
}
const INPUT_TABS = [
  { key: 'upload', label: 'Загрузка' },
  { key: 'reservoir', label: 'Характеристики пласта' },
  { key: 'economics', label: 'Экономические вводные' },
  { key: 'brigades', label: 'Ограничения бригад' },
  { key: 'optimizer', label: 'Схема работы оптимизатора' },
]
const SOURCE_KIND_META = {
  external_krs_schedule: {
    title: 'Загрузить существующий график КРС',
    description: 'Импортирует внешний график КРС в Module A и открывает его в Planner как загруженную версию.',
    fields: ['brigade', 'area', 'lu', 'sloy', 'well_pad', 'well', 'start_date', 'end_date', 'planned_work', 'increment', 'liquid_increment', 'gas_increment', 'gor_change'],
  },
  wells: {
    title: 'Загрузить базовый фонд',
    description: 'Формирует dataset типа wells для Module B.',
    fields: ['well', 'area', 'lu', 'sloy', 'well_pad', 'brigade', 'fund_type', 'oil_rate', 'liquid_rate', 'gas_rate', 'watercut', 'gor', 'cumulative_oil', 'cumulative_gas', 'niz'],
  },
  gtm: {
    title: 'Загрузить план ГТМ',
    description: 'Формирует dataset типа gtm для расчета и планирования.',
    fields: ['well', 'area', 'lu', 'sloy', 'well_pad', 'brigade', 'gtm_type', 'planned_work', 'start_date', 'end_date', 'duration_days', 'increment', 'liquid_increment', 'gas_increment', 'gor_change'],
  },
  infrastructure: {
    title: 'Загрузить ограничения инфраструктуры',
    description: 'Формирует dataset типа infrastructure для дальнейшей проверки ограничений.',
    fields: ['area', 'lu', 'sloy', 'well_pad', 'object_name', 'object_type', 'commissioning_date', 'capacity_oil', 'capacity_gas', 'capacity_liquid', 'capacity_water', 'connection_well', 'parent_object'],
  },
}
const MAPPING_LABELS = {
  well: 'Скважина',
  area: 'Участок',
  lu: 'LU',
  sloy: 'SLOY',
  well_pad: 'Куст',
  brigade: 'Бригада',
  fund_type: 'Вид фонда',
  start_date: 'Дата начала',
  end_date: 'Дата окончания',
  planned_work: 'Планируемый объем работ',
  increment: 'Прирост нефти',
  liquid_increment: 'Прирост жидкости',
  gas_increment: 'Прирост газа',
  gor_change: 'Изменение GOR',
  oil_rate: 'Нефть',
  gas_rate: 'Газ',
  liquid_rate: 'Жидкость',
  watercut: 'Обводненность',
  gor: 'GOR',
  cumulative_oil: 'Накопленная нефть',
  cumulative_gas: 'Накопленный газ',
  niz: 'НИЗ',
  gtm_type: 'Тип ГТМ',
  duration_days: 'Длительность, дни',
  object_name: 'Объект инфраструктуры',
  object_type: 'Тип объекта',
  commissioning_date: 'Дата ввода',
  capacity_oil: 'Мощность по нефти',
  capacity_gas: 'Мощность по газу',
  capacity_liquid: 'Мощность по жидкости',
  capacity_water: 'Мощность по воде',
  connection_well: 'Связанная скважина',
  parent_object: 'Родительский объект',
}

const parseIsoDate = (value) => {
  if (!value) return null
  const [y, m, d] = String(value).slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(Date.UTC(y, m - 1, d))
}

const formatIsoDate = (date) => {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return ''
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`
}

const isoToday = () => formatIsoDate(new Date())
const endOfNextYearIso = (startIso) => {
  const start = parseIsoDate(startIso) || new Date()
  return `${start.getUTCFullYear() + 1}-12-31`
}

const addDays = (value, days) => {
  const next = parseIsoDate(value)
  if (!next) return value
  next.setUTCDate(next.getUTCDate() + days)
  return formatIsoDate(next)
}

const addMonthsToIso = (value, count) => {
  const next = parseIsoDate(value)
  if (!next) return value
  next.setUTCMonth(next.getUTCMonth() + count)
  next.setUTCDate(1)
  return formatIsoDate(next)
}

const diffDays = (from, to) => {
  const left = parseIsoDate(from)
  const right = parseIsoDate(to)
  if (!left || !right) return 0
  return Math.round((right - left) / 86400000)
}

const monthStartIso = (value) => {
  const date = parseIsoDate(value)
  if (!date) return value
  date.setUTCDate(1)
  return formatIsoDate(date)
}

const formatDateCell = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(parsed) : '—'
}

const formatMonthLabel = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { month: 'short' }).format(parsed).replace('.', '') : ''
}

const formatMonthLong = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' }).format(parsed) : '—'
}

const formatDayNumber = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { day: '2-digit' }).format(parsed) : ''
}

const formatCompactNumber = (value) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(value || 0))
const formatIncrement = (value) => (value && value > 0 ? Number(value).toFixed(1) : '0')
const wellPrefix = (value) => String(value || '').trim().slice(0, 2).toUpperCase() || 'NA'
const colorFromPrefix = (prefix) => {
  const hash = [...prefix].reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return `hsl(${(hash * 19) % 360} 72% 56%)`
}
const compactObject = (value) => Object.fromEntries(Object.entries(value).filter(([, item]) => item !== '' && item !== null && item !== undefined))
const cloneItems = (items) => items.map((item) => ({ ...item }))
const uniqueId = (prefix) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
const datasetReferenceKey = (reference) => reference ? `${reference.dataset_id}:${reference.dataset_version_id || 'latest'}` : ''
const datasetSelectionPayload = (reference) => reference ? ({
  dataset_id: reference.dataset_id,
  dataset_version_id: reference.dataset_version_id,
}) : null

const buildWatercutRows = () => Array.from({ length: 21 }, (_, index) => ({ watercut: index * 5, NIZ: '' }))
const buildDeclineRows = (kind) => Array.from({ length: 24 }, (_, index) => ({
  month_index: index + 1,
  liquid_decline_factor: kind === 'base' ? 5 : (index < 12 ? 50 : 5),
}))
const createReservoirConfig = () => ({
  config_id: uniqueId('reservoir'),
  lu_id: '',
  sloy_id: '',
  notes: '',
  displacement_rows: buildWatercutRows(),
  base_decline_rows: buildDeclineRows('base'),
  new_wells_decline_rows: buildDeclineRows('new'),
})
const createEconomicsRow = () => ({ id: uniqueId('economics'), lu_id: '', net_back: '' })
const createFailureRow = () => ({ id: uniqueId('failure'), scope_type: 'LU', lu_id: '', sloy_id: '', coefficient: '' })
const createDurationRow = () => ({ id: uniqueId('duration'), gtm_type: '', duration_days: '' })
const createBrigadeRow = () => ({ id: uniqueId('brigade'), lu_id: '', month_date: monthStartIso(isoToday()), brigade_count: '' })
const buildAreaPath = (series, topKey, bottomKey, maxValue) => {
  if (!series.length || maxValue <= 0) return ''
  const width = PRODUCTION_CHART_WIDTH
  const height = PRODUCTION_CHART_HEIGHT
  const step = series.length === 1 ? 0 : width / (series.length - 1)
  const top = series.map((point, index) => {
    const x = index * step
    const y = height - ((point[topKey] || 0) / maxValue) * height
    return `${x},${y}`
  })
  const bottom = [...series].reverse().map((point, reverseIndex) => {
    const index = series.length - 1 - reverseIndex
    const x = index * step
    const y = height - ((point[bottomKey] || 0) / maxValue) * height
    return `${x},${y}`
  })
  return `M ${top.join(' L ')} L ${bottom.join(' L ')} Z`
}
const buildWellNodeKey = (well) => `well:${well.lu_id || 'Без LU'}:${well.sloy_id || 'Без SLOY'}:${well.well_pad_id || 'Без куста'}:${well.well_id}`

const request = async (path, options = {}) => {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    let detail = 'Ошибка запроса.'
    try {
      const payload = await response.json()
      detail = payload.detail || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return response
}

const sidebarCollapsed = ref(false)
const currentSection = ref('inputs')
const currentInputsTab = ref('upload')
const loading = ref(false)
const message = ref('')
const messageType = ref('info')

const showMessage = (text, type = 'info') => {
  message.value = text
  messageType.value = type
}

const uploadedFiles = ref([])
const datasets = ref([])
const manualInputSets = ref([])
const scenarios = ref([])

const inputFile = ref(null)
const selectedUploadSourceKind = ref('external_krs_schedule')
const selectedUploadFileId = ref('')
const selectedUploadSheet = ref('')
const datasetName = ref('')
const targetDatasetId = ref('')
const lastNormalizedDatasetReference = ref(null)
const datasetDetails = reactive({})
const datasetDetailKey = ref('')

const selectedDatasets = reactive({
  wells: null,
  gtm: null,
  infrastructure: null,
  external_krs_schedule: null,
})
const selectedDatasetKeys = reactive({
  wells: '',
  gtm: '',
  infrastructure: '',
  external_krs_schedule: '',
})

const normalizeColumns = reactive({
  well: '',
  area: '',
  lu: '',
  sloy: '',
  well_pad: '',
  brigade: '',
  fund_type: '',
  start_date: '',
  end_date: '',
  planned_work: '',
  increment: '',
  liquid_increment: '',
  gas_increment: '',
  gor_change: '',
  oil_rate: '',
  gas_rate: '',
  liquid_rate: '',
  watercut: '',
  gor: '',
  cumulative_oil: '',
  cumulative_gas: '',
  niz: '',
  gtm_type: '',
  duration_days: '',
  object_name: '',
  object_type: '',
  commissioning_date: '',
  capacity_oil: '',
  capacity_gas: '',
  capacity_liquid: '',
  capacity_water: '',
  connection_well: '',
  parent_object: '',
})

const manualInputName = ref(`Вводные ${isoToday()}`)
const selectedManualInputSetId = ref('')
const reservoirConfigs = ref([createReservoirConfig()])
const activeReservoirConfigId = ref(reservoirConfigs.value[0].config_id)
const economicsRows = ref([createEconomicsRow()])
const economicsNotes = ref('')
const brigadeCapacityRows = ref([])
const brigadeCapacitySeedLu = ref('')
const brigadeCapacityNotes = ref('')
const failureRows = ref([createFailureRow()])
const failureNotes = ref('')
const durationRows = ref([createDurationRow()])
const krsFallbackBrigades = ref('')
const krsResourceNotes = ref('')
const optimizerForm = reactive({
  scenario_name: 'Сценарий расчета',
  forecast_start_date: isoToday(),
  forecast_end_date: endOfNextYearIso(isoToday()),
  run_mode: 'forecast_only',
  objective: 'oil_max',
  infra_policy: 'warn',
  heuristic_mode: 'basic',
  notes: '',
})

const selectedScenarioId = ref('')
const scenarioSourceMode = ref('new_krs')
const scenarioDetail = ref(null)
const expandedProductionKeys = ref([])
const selectedProductionKeys = ref([])

const plannerDatasetSelectionKey = ref('')
const plannerDatasetReference = ref(null)
const plannerVersionName = ref('')
const versions = ref([])
const activeVersionId = ref('base')
const plannerColumns = reactive({ ...DEFAULT_PLANNER_COLUMNS })
const timelineZoom = ref(12)
const timelineStartOffset = ref(0)
const timelineEndOffset = ref(0)
const minIncrementFilter = ref(0)
const showPpd = ref(true)
const selectedPrefixes = ref([])
const selectedAreas = ref([])
const selectedWorkTypes = ref([])

const sourceDatasetOptions = computed(() => datasets.value.filter((item) => item.dataset_reference.dataset_type === selectedUploadSourceKind.value))
const availableColumns = computed(() => inputFile.value?.columns_info || [])
const previewColumns = computed(() => Object.keys(inputFile.value?.preview?.[0] || {}))
const datasetTypes = computed(() => {
  const groups = { wells: [], gtm: [], infrastructure: [], external_krs_schedule: [] }
  datasets.value.forEach((item) => {
    const type = item.dataset_reference.dataset_type
    if (groups[type]) groups[type].push(item)
  })
  return groups
})
const selectedDatasetDetail = computed(() => datasetDetails[datasetDetailKey.value] || null)
const activeReservoirConfig = computed(() => reservoirConfigs.value.find((item) => item.config_id === activeReservoirConfigId.value) || reservoirConfigs.value[0] || null)
const groupedScenarios = computed(() => [...scenarios.value].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')))
const selectedScenarioSummary = computed(() => groupedScenarios.value.find((item) => item.scenario_id === selectedScenarioId.value) || null)
const scenarioContextStatus = computed(() => ({
  wells: Boolean(selectedDatasets.wells),
  gtm: Boolean(selectedDatasets.gtm),
  infrastructure: Boolean(selectedDatasets.infrastructure),
  manual_input: Boolean(selectedManualInputSetId.value),
  external_krs_schedule: scenarioSourceMode.value === 'existing_krs' ? Boolean(selectedDatasets.external_krs_schedule) : true,
}))
const canCalculateScenario = computed(() => Boolean(
  selectedScenarioId.value
  && scenarioContextStatus.value.wells
  && scenarioContextStatus.value.gtm
  && scenarioContextStatus.value.manual_input
  && scenarioContextStatus.value.external_krs_schedule,
))
const workflowSteps = computed(() => {
  const selectedScenario = selectedScenarioSummary.value
  const hasScenario = Boolean(selectedScenarioId.value)
  const hasSource = scenarioSourceMode.value === 'existing_krs'
    ? Boolean(selectedDatasets.external_krs_schedule)
    : true
  const hasInputs = Boolean(
    selectedDatasets.wells
    && selectedDatasets.gtm
    && selectedManualInputSetId.value
    && (scenarioSourceMode.value === 'new_krs' || selectedDatasets.external_krs_schedule),
  )
  const hasResult = Boolean(scenarioDetail.value?.production_summary)
  const isPlannerDerived = selectedScenario?.source_type === 'planner_manual_edit'
  return [
    {
      key: 'scenario',
      label: '1. Сценарий',
      description: hasScenario ? (selectedScenario?.name || 'Активный сценарий выбран') : 'Нужно создать или выбрать сценарий.',
      ready: hasScenario,
    },
    {
      key: 'krs-source',
      label: '2. Источник графика КРС',
      description: scenarioSourceMode.value === 'existing_krs'
        ? (selectedDatasets.external_krs_schedule?.name || 'Нужно привязать imported KRS dataset.')
        : 'График будет сформирован в расчетно-планировочном контуре.',
      ready: hasSource,
    },
    {
      key: 'inputs',
      label: '3. Исходные данные',
      description: hasInputs ? 'Wells, GTM и ManualInputSet привязаны.' : 'Нужно привязать Wells, GTM и ManualInputSet.',
      ready: hasInputs,
    },
    {
      key: 'calculate',
      label: '4. Расчет',
      description: hasResult ? 'Профиль добычи для сценария рассчитан.' : 'Сценарий еще не рассчитан.',
      ready: hasResult,
    },
    {
      key: 'planner',
      label: '5. Planner / Версия',
      description: isPlannerDerived
        ? 'Текущий сценарий создан автоматически из Planner revision.'
        : (activeVersion.value ? 'В Planner есть активная версия графика.' : 'Planner version пока не опубликована в сценарный поток.'),
      ready: isPlannerDerived || Boolean(activeVersion.value),
    },
  ]
})
const pageTitle = computed(() => {
  if (currentSection.value === 'planner') return 'Планировщик КРС'
  if (currentSection.value === 'production') return 'Добыча'
  return 'Исходные данные'
})
const pageSubtitle = computed(() => {
  if (currentSection.value === 'planner') return 'Отдельный модуль Planner. Открывает импортированные графики КРС, ведет версии и выгружает измененный план.'
  if (currentSection.value === 'production') return 'Просмотр сохраненных сценариев Module B с накопительной диаграммой нефти и иерархической фильтрацией по LU, SLOY, кусту и скважине.'
  return 'Сценарный контур Module G: загрузка datasets, ручные вводные, расчетный горизонт и запуск Module B.'
})
const activeVersion = computed(() => versions.value.find((version) => version.id === activeVersionId.value) || versions.value[0] || null)
const activeItems = computed(() => activeVersion.value?.items || [])
const canEditVersion = computed(() => activeVersionId.value !== 'base')
const prefixOptions = computed(() => [...new Set(activeItems.value.map((item) => wellPrefix(item.well)).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru')))
const areaOptions = computed(() => [...new Set(activeItems.value.map((item) => String(item.area || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru')))
const plannedWorkOptions = computed(() => [...new Set(activeItems.value.map((item) => String(item.planned_work || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru')))
const visibleItems = computed(() =>
  activeItems.value.filter((item) => {
    if (selectedPrefixes.value.length && !selectedPrefixes.value.includes(wellPrefix(item.well))) return false
    if (!showPpd.value && item.is_ppd) return false
    if (selectedAreas.value.length && !selectedAreas.value.includes(String(item.area || '').trim())) return false
    if (selectedWorkTypes.value.length && !selectedWorkTypes.value.includes(String(item.planned_work || '').trim())) return false
    return true
  }),
)
const totalIncrement = computed(() => visibleItems.value.reduce((sum, item) => sum + (item.increment && item.increment > 0 ? Number(item.increment) : 0), 0))
const fullScheduleBounds = computed(() => {
  if (!visibleItems.value.length) return { min: null, max: null }
  return {
    min: visibleItems.value.reduce((acc, item) => (!acc || item.start_date < acc ? item.start_date : acc), null),
    max: visibleItems.value.reduce((acc, item) => (!acc || item.end_date > acc ? item.end_date : acc), null),
  }
})
const fullTimelineDays = computed(() => {
  if (!fullScheduleBounds.value.min || !fullScheduleBounds.value.max) return 0
  return diffDays(fullScheduleBounds.value.min, fullScheduleBounds.value.max)
})
const timelineWindowStart = computed(() => {
  if (!fullScheduleBounds.value.min) return null
  return addDays(fullScheduleBounds.value.min, Math.min(timelineStartOffset.value, timelineEndOffset.value))
})
const timelineWindowEnd = computed(() => {
  if (!fullScheduleBounds.value.min) return null
  return addDays(fullScheduleBounds.value.min, Math.max(timelineStartOffset.value, timelineEndOffset.value))
})
const scheduleBounds = computed(() => ({ min: timelineWindowStart.value, max: timelineWindowEnd.value }))
const ganttDates = computed(() => {
  if (!scheduleBounds.value.min || !scheduleBounds.value.max) return []
  const dates = []
  let cursor = scheduleBounds.value.min
  while (cursor <= scheduleBounds.value.max) {
    dates.push(cursor)
    cursor = addDays(cursor, 1)
  }
  return dates
})
const monthSegments = computed(() => {
  const segments = []
  ganttDates.value.forEach((date) => {
    const key = date.slice(0, 7)
    const last = segments[segments.length - 1]
    if (last && last.key === key) {
      last.span += 1
      return
    }
    segments.push({ key, label: formatMonthLabel(date), span: 1 })
  })
  return segments
})
const timelineDayWidth = computed(() => timelineZoom.value)
const todayOffset = computed(() => {
  const today = isoToday()
  if (!scheduleBounds.value.min || !scheduleBounds.value.max) return null
  if (today < scheduleBounds.value.min || today > scheduleBounds.value.max) return null
  return diffDays(scheduleBounds.value.min, today)
})
const gtmOpacity = (item) => {
  if (item.is_ppd) return 1
  const threshold = Number(minIncrementFilter.value || 0)
  if (threshold <= 0) return 1
  const increment = item.increment && item.increment > 0 ? Number(item.increment) : 0
  if (increment >= threshold) return 1
  return 0.18 + (increment / threshold) * 0.82
}
const ganttRows = computed(() => {
  const byBrigade = new Map()
  visibleItems.value
    .filter((item) => item.end_date >= scheduleBounds.value.min && item.start_date <= scheduleBounds.value.max)
    .forEach((item) => {
      if (!byBrigade.has(item.brigade)) byBrigade.set(item.brigade, [])
      byBrigade.get(item.brigade).push(item)
    })
  return [...byBrigade.entries()]
    .sort((a, b) => a[0].localeCompare(b[0], 'ru'))
    .map(([brigade, items]) => {
      const sorted = [...items].sort((a, b) => a.start_date.localeCompare(b.start_date) || a.well.localeCompare(b.well, 'ru'))
      const laneEnds = []
      const bars = sorted.map((item) => {
        const visibleStart = item.start_date < scheduleBounds.value.min ? scheduleBounds.value.min : item.start_date
        const visibleEnd = item.end_date > scheduleBounds.value.max ? scheduleBounds.value.max : item.end_date
        const clippedStart = diffDays(scheduleBounds.value.min, visibleStart)
        const clippedEnd = diffDays(scheduleBounds.value.min, visibleEnd)
        let lane = laneEnds.findIndex((laneEnd) => clippedStart >= laneEnd)
        if (lane === -1) {
          lane = laneEnds.length
          laneEnds.push(clippedEnd)
        } else {
          laneEnds[lane] = clippedEnd
        }
        const prefix = wellPrefix(item.well)
        return {
          ...item,
          lane,
          startOffset: clippedStart,
          visibleDurationDays: clippedEnd - clippedStart + 1,
          prefix,
          color: colorFromPrefix(prefix),
        }
      })
      return { brigade, laneCount: Math.max(laneEnds.length, 1), bars }
    })
})
const incrementTimeline = computed(() => {
  const grouped = new Map()
  visibleItems.value
    .filter((item) => item.end_date >= scheduleBounds.value.min && item.end_date <= scheduleBounds.value.max)
    .forEach((item) => {
      const key = item.end_date
      if (!grouped.has(key)) grouped.set(key, [])
      grouped.get(key).push(item)
    })
  return [...grouped.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, items]) => ({
      date,
      offset: diffDays(scheduleBounds.value.min, date),
      positive: items
        .filter((item) => item.increment && item.increment > 0)
        .sort((a, b) => Number(b.increment) - Number(a.increment))
        .map((item) => {
          const prefix = wellPrefix(item.well)
          return { ...item, prefix, color: colorFromPrefix(prefix), value: Number(item.increment) }
        }),
      zero: items
        .filter((item) => !item.increment || item.increment <= 0)
        .map((item) => {
          const prefix = wellPrefix(item.well)
          return { ...item, prefix, color: colorFromPrefix(prefix) }
        }),
    }))
})
const topChartBars = computed(() => incrementTimeline.value.map((group) => ({
  ...group,
  total: group.positive.reduce((sum, item) => sum + item.value, 0),
  labels: group.positive.map((item) => `${item.well} ${formatIncrement(item.increment)}`),
})))
const topChartMax = computed(() => Math.max(...topChartBars.value.map((group) => group.total), 10))
const cumulativeIncrementSeries = computed(() => ganttDates.value.map((date, index) => ({
  date,
  index,
  total: visibleItems.value.reduce((sum, item) => {
    const value = item.increment && item.increment > 0 ? Number(item.increment) : 0
    return item.end_date <= date ? sum + value : sum
  }, 0),
  x: index * timelineDayWidth.value + timelineDayWidth.value / 2,
})))
const cumulativeIncrementMax = computed(() => Math.max(...cumulativeIncrementSeries.value.map((point) => point.total), 10))
const cumulativeLinePoints = computed(() =>
  cumulativeIncrementSeries.value
    .map((point) => `${point.x},${PLANNER_CHART_HEIGHT - (point.total / cumulativeIncrementMax.value) * PLANNER_CHART_HEIGHT}`)
    .join(' '),
)
const cumulativeLineLabels = computed(() => cumulativeIncrementSeries.value.filter((point, index, source) => index % 7 === 0 || index === source.length - 1))
const incrementLegend = computed(() => {
  const seen = new Map()
  visibleItems.value.forEach((item) => {
    const prefix = wellPrefix(item.well)
    if (!seen.has(prefix)) seen.set(prefix, colorFromPrefix(prefix))
  })
  return [...seen.entries()].slice(0, 16).map(([prefix, color]) => ({ prefix, color }))
})
const luOptions = computed(() => {
  const values = new Set()
  Object.values(selectedDatasets).forEach((reference) => {
    const payload = datasetDetails[datasetReferenceKey(reference)]?.normalized_payload
    const rows = Array.isArray(payload)
      ? payload
      : Array.isArray(payload?.schedule?.items)
        ? payload.schedule.items
        : Array.isArray(payload?.items)
          ? payload.items
          : []
    rows.forEach((row) => {
      const value = row.lu_id || row.lu
      if (value) values.add(String(value))
    })
  })
  reservoirConfigs.value.forEach((item) => item.lu_id && values.add(item.lu_id))
  economicsRows.value.forEach((item) => item.lu_id && values.add(item.lu_id))
  brigadeCapacityRows.value.forEach((item) => item.lu_id && values.add(item.lu_id))
  failureRows.value.forEach((item) => item.lu_id && values.add(item.lu_id))
  return [...values].sort((a, b) => a.localeCompare(b, 'ru'))
})
const sloyOptions = computed(() => {
  const values = new Set()
  Object.values(selectedDatasets).forEach((reference) => {
    const payload = datasetDetails[datasetReferenceKey(reference)]?.normalized_payload
    const rows = Array.isArray(payload)
      ? payload
      : Array.isArray(payload?.schedule?.items)
        ? payload.schedule.items
        : Array.isArray(payload?.items)
          ? payload.items
          : []
    rows.forEach((row) => {
      const value = row.sloy_id || row.sloy
      if (value) values.add(String(value))
    })
  })
  reservoirConfigs.value.forEach((item) => item.sloy_id && values.add(item.sloy_id))
  failureRows.value.forEach((item) => item.sloy_id && values.add(item.sloy_id))
  return [...values].sort((a, b) => a.localeCompare(b, 'ru'))
})

const productionTree = computed(() => {
  const wells = Array.isArray(scenarioDetail.value?.wells) ? scenarioDetail.value.wells : []
  const totalNode = {
    key: 'total',
    nodeType: 'total',
    depth: 0,
    label: 'Итого',
    fundType: null,
    totalOil: 0,
    totalLiquid: 0,
    totalGas: 0,
    wellCount: 0,
    leafKeys: [],
    children: [],
  }
  const luMap = new Map()
  wells.forEach((well) => {
    const luId = well.lu_id || 'Без LU'
    const sloyId = well.sloy_id || 'Без SLOY'
    const padId = well.well_pad_id || 'Без куста'
    const wellKey = buildWellNodeKey(well)
    let luNode = luMap.get(luId)
    if (!luNode) {
      luNode = { key: `lu:${luId}`, nodeType: 'lu', depth: 1, label: luId, fundType: null, totalOil: 0, totalLiquid: 0, totalGas: 0, wellCount: 0, leafKeys: [], children: [] }
      luMap.set(luId, luNode)
      totalNode.children.push(luNode)
    }
    let sloyNode = luNode.children.find((item) => item.label === sloyId)
    if (!sloyNode) {
      sloyNode = { key: `sloy:${luId}:${sloyId}`, nodeType: 'sloy', depth: 2, label: sloyId, fundType: null, totalOil: 0, totalLiquid: 0, totalGas: 0, wellCount: 0, leafKeys: [], children: [] }
      luNode.children.push(sloyNode)
    }
    let padNode = sloyNode.children.find((item) => item.label === padId)
    if (!padNode) {
      padNode = { key: `pad:${luId}:${sloyId}:${padId}`, nodeType: 'pad', depth: 3, label: padId, fundType: null, totalOil: 0, totalLiquid: 0, totalGas: 0, wellCount: 0, leafKeys: [], children: [] }
      sloyNode.children.push(padNode)
    }
    const leafNode = {
      key: wellKey,
      nodeType: 'well',
      depth: 4,
      label: well.well_name || well.well_id,
      fundType: well.fund_type || null,
      totalOil: Number(well.total_oil || 0),
      totalLiquid: Number(well.total_liquid || 0),
      totalGas: Number(well.total_gas || 0),
      wellCount: 1,
      leafKeys: [wellKey],
      children: [],
    }
    padNode.children.push(leafNode)
    ;[totalNode, luNode, sloyNode, padNode].forEach((node) => {
      node.totalOil += leafNode.totalOil
      node.totalLiquid += leafNode.totalLiquid
      node.totalGas += leafNode.totalGas
      node.wellCount += 1
      node.leafKeys.push(wellKey)
    })
  })
  const nodeMap = new Map()
  const register = (node) => {
    nodeMap.set(node.key, node)
    node.children.forEach(register)
  }
  register(totalNode)
  const rows = []
  const flatten = (node) => {
    rows.push(node)
    if (!node.children.length) return
    if (!expandedProductionKeys.value.includes(node.key)) return
    node.children
      .sort((left, right) => left.label.localeCompare(right.label, 'ru'))
      .forEach(flatten)
  }
  flatten(totalNode)
  return { rows, nodeMap, totalNode }
})
const selectedLeafWells = computed(() => {
  const allWells = Array.isArray(scenarioDetail.value?.wells) ? scenarioDetail.value.wells : []
  const selectedKeys = selectedProductionKeys.value.length
    ? new Set(selectedProductionKeys.value.flatMap((key) => productionTree.value.nodeMap.get(key)?.leafKeys || []))
    : new Set(productionTree.value.totalNode.leafKeys)
  return allWells.filter((well) => selectedKeys.has(buildWellNodeKey(well)))
})
const productionSeries = computed(() => {
  if (!selectedLeafWells.value.length) return []
  const dateMap = new Map()
  selectedLeafWells.value.forEach((well) => {
    well.points.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, { date: point.date, baseDaily: 0, gtmDaily: 0, vnsDaily: 0 })
      }
      const bucket = dateMap.get(point.date)
      const oilRate = Number(point.oil_rate || 0)
      const oilIncrement = Number(point.oil_increment || 0)
      if (String(well.fund_type || '').toLowerCase() === 'new wells') {
        bucket.vnsDaily += oilRate
      } else {
        bucket.gtmDaily += oilIncrement
        bucket.baseDaily += Math.max(oilRate - oilIncrement, 0)
      }
    })
  })
  const ordered = [...dateMap.values()].sort((a, b) => a.date.localeCompare(b.date))
  let baseCum = 0
  let gtmCum = 0
  let vnsCum = 0
  return ordered.map((point) => {
    baseCum += point.baseDaily
    gtmCum += point.gtmDaily
    vnsCum += point.vnsDaily
    return {
      ...point,
      zero: 0,
      baseCum,
      gtmCum,
      vnsCum,
      gtmTop: baseCum + gtmCum,
      totalCum: baseCum + gtmCum + vnsCum,
    }
  })
})
const productionMax = computed(() => Math.max(...productionSeries.value.map((point) => point.totalCum), 1))
const productionBasePath = computed(() => buildAreaPath(productionSeries.value, 'baseCum', 'zero', productionMax.value))
const productionGtmPath = computed(() => buildAreaPath(productionSeries.value.map((point) => ({ ...point, zero: point.baseCum })), 'gtmTop', 'zero', productionMax.value))
const productionVnsPath = computed(() => buildAreaPath(productionSeries.value.map((point) => ({ ...point, zero: point.gtmTop })), 'totalCum', 'zero', productionMax.value))
const productionLabelPoints = computed(() => {
  if (!productionSeries.value.length) return []
  const source = productionSeries.value
  return source.filter((point, index) => index === 0 || index === source.length - 1 || index === Math.floor(source.length / 2))
})
const selectedProductionSummary = computed(() => selectedLeafWells.value.reduce((acc, well) => {
  acc.totalOil += Number(well.total_oil || 0)
  acc.totalLiquid += Number(well.total_liquid || 0)
  acc.totalGas += Number(well.total_gas || 0)
  return acc
}, { totalOil: 0, totalLiquid: 0, totalGas: 0 }))
const productionChartLegend = computed(() => ([
  { label: 'БАЗА', color: 'rgba(47, 128, 255, 0.78)', value: productionSeries.value.at(-1)?.baseCum || 0 },
  { label: 'ГТМ', color: 'rgba(76, 195, 154, 0.78)', value: productionSeries.value.at(-1)?.gtmCum || 0 },
  { label: 'ВНС', color: 'rgba(230, 124, 37, 0.8)', value: productionSeries.value.at(-1)?.vnsCum || 0 },
]))

const resetNormalizeColumns = () => {
  Object.keys(normalizeColumns).forEach((key) => { normalizeColumns[key] = '' })
}

const fetchDatasetDetail = async (reference) => {
  if (!reference) return null
  const key = datasetReferenceKey(reference)
  if (datasetDetails[key]) return datasetDetails[key]
  const response = await request(`/datasets/${reference.dataset_id}?dataset_version_id=${reference.dataset_version_id || ''}`)
  const payload = await response.json()
  datasetDetails[key] = payload
  return payload
}

const setActiveDataset = async (reference) => {
  if (!reference) return
  selectedDatasets[reference.dataset_type] = { ...reference }
  selectedDatasetKeys[reference.dataset_type] = datasetReferenceKey(reference)
  await fetchDatasetDetail(reference)
}

const selectDatasetByKey = async (type, key) => {
  const item = datasetTypes.value[type].find((dataset) => datasetReferenceKey(dataset.dataset_reference) === key)
  if (!item) return
  await setActiveDataset(item.dataset_reference)
}

const ensureSelectedDatasets = async () => {
  for (const type of Object.keys(selectedDatasets)) {
    if (selectedDatasets[type]) continue
    const candidate = datasetTypes.value[type]?.[0]?.dataset_reference || null
    if (candidate) await setActiveDataset(candidate)
  }
  if (!plannerDatasetSelectionKey.value) {
    plannerDatasetSelectionKey.value = selectedDatasetKeys.external_krs_schedule
  }
}

const applyScenarioContext = async (context) => {
  if (!context) return
  const mapping = {
    wells: context.wells_dataset,
    gtm: context.gtm_dataset,
    infrastructure: context.infrastructure_dataset,
    external_krs_schedule: context.external_krs_schedule_dataset,
  }
  for (const [type, reference] of Object.entries(mapping)) {
    if (reference) {
      await setActiveDataset(reference)
    }
  }
  if (context.manual_input_set?.manual_input_set_id) {
    selectedManualInputSetId.value = context.manual_input_set.manual_input_set_id
  }
  scenarioSourceMode.value = context.external_krs_schedule_dataset ? 'existing_krs' : 'new_krs'
}

const buildScenarioRequestPayload = () => ({
  name: optimizerForm.scenario_name,
  source_type: selectedScenarioSummary.value?.source_type || 'uploaded_gtm',
  parent_scenario_id: selectedScenarioSummary.value?.parent_scenario_id || null,
  forecast_start_date: optimizerForm.forecast_start_date,
  forecast_end_date: optimizerForm.forecast_end_date,
  inputs: {
    wells: datasetSelectionPayload(selectedDatasets.wells),
    gtm: datasetSelectionPayload(selectedDatasets.gtm),
    infrastructure: datasetSelectionPayload(selectedDatasets.infrastructure),
    external_krs_schedule: scenarioSourceMode.value === 'existing_krs'
      ? datasetSelectionPayload(selectedDatasets.external_krs_schedule)
      : null,
    manual_input_set_id: selectedManualInputSetId.value || null,
  },
  metadata: {
    scenario_source_mode: scenarioSourceMode.value,
    run_mode: optimizerForm.run_mode,
    objective: optimizerForm.objective,
    infra_policy: optimizerForm.infra_policy,
    heuristic_mode: optimizerForm.heuristic_mode,
    notes: optimizerForm.notes,
  },
})

const loadUploadedFiles = async () => {
  const response = await request('/files')
  uploadedFiles.value = await response.json()
}

const loadDatasets = async () => {
  const response = await request('/datasets')
  datasets.value = await response.json()
  await ensureSelectedDatasets()
}

const loadManualInputSets = async () => {
  const response = await request('/manual-inputs')
  manualInputSets.value = await response.json()
  if (!selectedManualInputSetId.value && manualInputSets.value.length) {
    selectedManualInputSetId.value = manualInputSets.value[0].reference.manual_input_set_id
  }
}

const loadScenarios = async () => {
  const response = await request('/scenarios')
  scenarios.value = await response.json()
  if (!selectedScenarioId.value && scenarios.value.length) {
    selectedScenarioId.value = groupedScenarios.value[0].scenario_id
  }
}

const createScenario = async () => {
  loading.value = true
  try {
    const response = await request('/scenarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildScenarioRequestPayload()),
    })
    const payload = await response.json()
    selectedScenarioId.value = payload.scenario_id
    await loadScenarios()
    await loadScenarioDetail(payload.scenario_id)
    showMessage('Сценарий создан.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const saveActiveScenarioContext = async ({ silent = false } = {}) => {
  if (!selectedScenarioId.value) {
    if (!silent) showMessage('Сначала создайте или выберите сценарий.', 'error')
    return false
  }
  loading.value = true
  try {
    const response = await request(`/scenarios/${selectedScenarioId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildScenarioRequestPayload()),
    })
    const payload = await response.json()
    await loadScenarios()
    if (!silent) {
      showMessage('Контекст сценария сохранен.', 'success')
    }
    return payload
  } catch (error) {
    showMessage(error.message, 'error')
    return false
  } finally {
    loading.value = false
  }
}

const openUploadedPreview = async (fileId, sheetName = null) => {
  if (!fileId) return
  loading.value = true
  try {
    const query = sheetName ? `?sheet_name=${encodeURIComponent(sheetName)}` : ''
    const response = await request(`/files/${fileId}${query}`)
    inputFile.value = await response.json()
    selectedUploadFileId.value = inputFile.value.file_id
    selectedUploadSheet.value = inputFile.value.selected_sheet
    if (!datasetName.value) {
      datasetName.value = `${selectedUploadSourceKind.value}:${inputFile.value.original_name}`
    }
    showMessage('Файл открыт для нормализации.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const uploadSourceFile = async (event) => {
  const [file] = event.target.files || []
  if (!file) return
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await request('/files/upload', { method: 'POST', body: formData })
    inputFile.value = await response.json()
    selectedUploadFileId.value = inputFile.value.file_id
    selectedUploadSheet.value = inputFile.value.selected_sheet
    datasetName.value = `${selectedUploadSourceKind.value}:${inputFile.value.original_name}`
    await loadUploadedFiles()
    showMessage('Excel загружен в Module A.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
    event.target.value = ''
  }
}

const normalizeDataset = async () => {
  if (!inputFile.value?.file_id) {
    showMessage('Сначала откройте файл для нормализации.', 'error')
    return
  }
  loading.value = true
  try {
    const response = await request('/import/normalize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_id: inputFile.value.file_id,
        source_kind: selectedUploadSourceKind.value,
        sheet_name: inputFile.value.selected_sheet,
        dataset_name: datasetName.value || `${selectedUploadSourceKind.value}:${inputFile.value.original_name}`,
        dataset_id: targetDatasetId.value || null,
        columns: compactObject({ ...normalizeColumns }),
      }),
    })
    const payload = await response.json()
    lastNormalizedDatasetReference.value = payload.dataset_reference
    await loadDatasets()
    await setActiveDataset(payload.dataset_reference)
    datasetDetailKey.value = datasetReferenceKey(payload.dataset_reference)
    if (payload.dataset_reference.dataset_type === 'external_krs_schedule') {
      plannerDatasetSelectionKey.value = datasetReferenceKey(payload.dataset_reference)
    }
    showMessage('Dataset сохранен в Postgres.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const openDatasetDetail = async (reference) => {
  datasetDetailKey.value = datasetReferenceKey(reference)
  await fetchDatasetDetail(reference)
}

const addReservoirConfig = () => {
  const config = createReservoirConfig()
  reservoirConfigs.value.push(config)
  activeReservoirConfigId.value = config.config_id
}

const removeReservoirConfig = (configId) => {
  if (reservoirConfigs.value.length === 1) return
  reservoirConfigs.value = reservoirConfigs.value.filter((item) => item.config_id !== configId)
  if (activeReservoirConfigId.value === configId) {
    activeReservoirConfigId.value = reservoirConfigs.value[0]?.config_id || ''
  }
}

const handleNizPaste = (event, config, startIndex) => {
  const text = event.clipboardData?.getData('text/plain')
  if (!text) return
  event.preventDefault()
  const values = text
    .split(/\r?\n/)
    .flatMap((line) => line.split('\t'))
    .map((item) => item.replace(',', '.').trim())
    .filter(Boolean)
  values.forEach((value, offset) => {
    const row = config.displacement_rows[startIndex + offset]
    if (!row) return
    row.NIZ = value
  })
}

const seedBrigadeCapacityRows = () => {
  if (!brigadeCapacitySeedLu.value) return
  const startDate = monthStartIso(optimizerForm.forecast_start_date || isoToday())
  const existingKeys = new Set(brigadeCapacityRows.value.map((item) => `${item.lu_id}:${item.month_date}`))
  for (let index = 0; index < 12; index += 1) {
    const monthDate = addMonthsToIso(startDate, index)
    const key = `${brigadeCapacitySeedLu.value}:${monthDate}`
    if (existingKeys.has(key)) continue
    brigadeCapacityRows.value.push({
      id: uniqueId('brigade'),
      lu_id: brigadeCapacitySeedLu.value,
      month_date: monthDate,
      brigade_count: '',
    })
  }
}

const addEconomicsRow = () => economicsRows.value.push(createEconomicsRow())
const addBrigadeRow = () => brigadeCapacityRows.value.push(createBrigadeRow())
const addFailureRow = () => failureRows.value.push(createFailureRow())
const addDurationRow = () => durationRows.value.push(createDurationRow())

const buildManualInputPayload = () => ({
  displacement_config: reservoirConfigs.value.map((config) => ({
    config_id: config.config_id,
    lu_id: config.lu_id || null,
    sloy_id: config.sloy_id || null,
    curve_points: config.displacement_rows
      .filter((row) => row.NIZ !== '' && row.NIZ !== null && row.NIZ !== undefined)
      .map((row) => ({ NIZ: Number(row.NIZ), watercut: Number(row.watercut) })),
    watercut_unit: 'percent',
    notes: config.notes || null,
  })),
  decline_config: reservoirConfigs.value.map((config) => ({
    config_id: config.config_id,
    lu_id: config.lu_id || null,
    sloy_id: config.sloy_id || null,
    base_monthly_decline_values: config.base_decline_rows.map((row) => ({
      month_index: Number(row.month_index),
      liquid_decline_factor: Number(row.liquid_decline_factor || 0),
    })),
    new_wells_monthly_decline_values: config.new_wells_decline_rows.map((row) => ({
      month_index: Number(row.month_index),
      liquid_decline_factor: Number(row.liquid_decline_factor || 0),
    })),
    notes: config.notes || null,
  })),
  brigade_capacity_by_lu_config: {
    items: brigadeCapacityRows.value
      .filter((item) => item.lu_id && item.month_date)
      .map((item) => ({
        lu_id: item.lu_id,
        month_date: item.month_date,
        brigade_count: Number(item.brigade_count || 0),
      })),
    notes: brigadeCapacityNotes.value || null,
  },
  failure_coefficient_config: {
    items: failureRows.value
      .filter((item) => item.coefficient !== '' && (item.lu_id || item.sloy_id))
      .map((item) => ({
        scope_type: item.scope_type,
        lu_id: item.lu_id || null,
        sloy_id: item.sloy_id || null,
        coefficient: Number(item.coefficient || 0),
      })),
    notes: failureNotes.value || null,
  },
  krs_resource_config: {
    brigade_count: krsFallbackBrigades.value === '' ? null : Number(krsFallbackBrigades.value),
    durations_by_gtm_type: Object.fromEntries(
      durationRows.value
        .filter((item) => item.gtm_type && item.duration_days !== '')
        .map((item) => [item.gtm_type, Number(item.duration_days)]),
    ),
    notes: krsResourceNotes.value || null,
  },
  economics_config: {
    items: economicsRows.value
      .filter((item) => item.lu_id)
      .map((item) => ({
        lu_id: item.lu_id,
        net_back: item.net_back === '' ? null : Number(item.net_back),
      })),
    notes: economicsNotes.value || null,
  },
  optimizer_config: {
    run_mode: optimizerForm.run_mode,
    objective: optimizerForm.objective,
    infra_policy: optimizerForm.infra_policy,
    heuristic_mode: optimizerForm.heuristic_mode,
    forecast_start_date: optimizerForm.forecast_start_date,
    forecast_end_date: optimizerForm.forecast_end_date,
    notes: optimizerForm.notes || null,
  },
  metadata: {
    scenario_name: optimizerForm.scenario_name,
  },
})

const applyManualInputPayload = (payload) => {
  const displacementConfigs = Array.isArray(payload.displacement_configs) ? payload.displacement_configs : []
  const declineConfigs = Array.isArray(payload.decline_configs) ? payload.decline_configs : []
  const configMap = new Map()

  displacementConfigs.forEach((item) => {
    configMap.set(item.config_id || uniqueId('reservoir'), {
      config_id: item.config_id || uniqueId('reservoir'),
      lu_id: item.lu_id || '',
      sloy_id: item.sloy_id || '',
      notes: item.notes || '',
      displacement_rows: buildWatercutRows(),
      base_decline_rows: buildDeclineRows('base'),
      new_wells_decline_rows: buildDeclineRows('new'),
    })
  })

  declineConfigs.forEach((item) => {
    const key = item.config_id || uniqueId('reservoir')
    if (!configMap.has(key)) {
      configMap.set(key, createReservoirConfig())
    }
    const config = configMap.get(key)
    config.config_id = key
    config.lu_id = item.lu_id || config.lu_id
    config.sloy_id = item.sloy_id || config.sloy_id
    config.notes = item.notes || config.notes
    config.base_decline_rows = buildDeclineRows('base').map((row) => {
      const stored = (item.base_monthly_decline_values || []).find((candidate) => Number(candidate.month_index) === row.month_index)
      return stored ? { month_index: row.month_index, liquid_decline_factor: Number(stored.liquid_decline_factor || 0) } : row
    })
    config.new_wells_decline_rows = buildDeclineRows('new').map((row) => {
      const stored = (item.new_wells_monthly_decline_values || []).find((candidate) => Number(candidate.month_index) === row.month_index)
      return stored ? { month_index: row.month_index, liquid_decline_factor: Number(stored.liquid_decline_factor || 0) } : row
    })
  })

  displacementConfigs.forEach((item) => {
    const key = item.config_id || [...configMap.keys()][0]
    const config = configMap.get(key)
    if (!config) return
    config.displacement_rows = buildWatercutRows().map((row) => {
      const stored = (item.curve_points || []).find((candidate) => Number(candidate.watercut) === row.watercut)
      return stored ? { watercut: row.watercut, NIZ: String(stored.NIZ ?? '') } : row
    })
  })

  reservoirConfigs.value = configMap.size ? [...configMap.values()] : [createReservoirConfig()]
  activeReservoirConfigId.value = reservoirConfigs.value[0].config_id

  const economicsItems = Array.isArray(payload.economics_config?.items) ? payload.economics_config.items : []
  economicsRows.value = economicsItems.length ? economicsItems.map((item) => ({
    id: uniqueId('economics'),
    lu_id: item.lu_id || '',
    net_back: item.net_back === null || item.net_back === undefined ? '' : String(item.net_back),
  })) : [createEconomicsRow()]
  economicsNotes.value = payload.economics_config?.notes || ''

  const brigadeItems = Array.isArray(payload.brigade_capacity_by_lu_config?.items) ? payload.brigade_capacity_by_lu_config.items : []
  brigadeCapacityRows.value = brigadeItems.map((item) => ({
    id: uniqueId('brigade'),
    lu_id: item.lu_id || '',
    month_date: item.month_date || monthStartIso(isoToday()),
    brigade_count: item.brigade_count === null || item.brigade_count === undefined ? '' : String(item.brigade_count),
  }))
  brigadeCapacityNotes.value = payload.brigade_capacity_by_lu_config?.notes || ''

  const failureItems = Array.isArray(payload.failure_coefficient_config?.items) ? payload.failure_coefficient_config.items : []
  failureRows.value = failureItems.length ? failureItems.map((item) => ({
    id: uniqueId('failure'),
    scope_type: item.scope_type || 'LU',
    lu_id: item.lu_id || '',
    sloy_id: item.sloy_id || '',
    coefficient: item.coefficient === null || item.coefficient === undefined ? '' : String(item.coefficient),
  })) : [createFailureRow()]
  failureNotes.value = payload.failure_coefficient_config?.notes || ''

  const durations = payload.krs_resource_config?.durations_by_gtm_type || {}
  durationRows.value = Object.keys(durations).length
    ? Object.entries(durations).map(([gtmType, durationDays]) => ({
      id: uniqueId('duration'),
      gtm_type: gtmType,
      duration_days: String(durationDays),
    }))
    : [createDurationRow()]
  krsFallbackBrigades.value = payload.krs_resource_config?.brigade_count === null || payload.krs_resource_config?.brigade_count === undefined
    ? ''
    : String(payload.krs_resource_config.brigade_count)
  krsResourceNotes.value = payload.krs_resource_config?.notes || ''

  optimizerForm.run_mode = payload.optimizer_config?.run_mode || 'forecast_only'
  optimizerForm.objective = payload.optimizer_config?.objective || 'oil_max'
  optimizerForm.infra_policy = payload.optimizer_config?.infra_policy || 'warn'
  optimizerForm.heuristic_mode = payload.optimizer_config?.heuristic_mode || 'basic'
  optimizerForm.forecast_start_date = payload.optimizer_config?.forecast_start_date || isoToday()
  optimizerForm.forecast_end_date = payload.optimizer_config?.forecast_end_date || endOfNextYearIso(optimizerForm.forecast_start_date)
  optimizerForm.notes = payload.optimizer_config?.notes || ''
  optimizerForm.scenario_name = payload.metadata?.scenario_name || optimizerForm.scenario_name
}

const saveManualInputs = async () => {
  loading.value = true
  try {
    const response = await request('/manual-inputs/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: manualInputName.value,
        payload: buildManualInputPayload(),
      }),
    })
    const payload = await response.json()
    selectedManualInputSetId.value = payload.reference.manual_input_set_id
    await loadManualInputSets()
    showMessage('ManualInputSet сохранен.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const loadManualInputSet = async (manualInputSetId) => {
  if (!manualInputSetId) return
  loading.value = true
  try {
    const response = await request(`/manual-inputs/${manualInputSetId}`)
    const payload = await response.json()
    selectedManualInputSetId.value = payload.reference.manual_input_set_id
    manualInputName.value = payload.reference.name
    applyManualInputPayload(payload.payload || {})
    showMessage('Набор ручных вводных загружен в редактор.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const calculateForecast = async () => {
  if (!selectedScenarioId.value) {
    showMessage('Для расчета нужны активные datasets wells и gtm.', 'error')
    return
  }
  if (!canCalculateScenario.value) {
    showMessage('Сначала сохраните или выберите ManualInputSet.', 'error')
    return
  }
  loading.value = true
  try {
    const saved = await saveActiveScenarioContext({ silent: true })
    if (!saved) {
      return
    }
    const response = await request(`/scenarios/${selectedScenarioId.value}/calculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    const payload = await response.json()
    await loadScenarios()
    selectedScenarioId.value = payload.scenario.scenario_id
    await loadScenarioDetail(payload.scenario.scenario_id)
    currentSection.value = 'production'
    showMessage('Сценарий Module B рассчитан.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const loadScenarioDetail = async (scenarioId) => {
  if (!scenarioId) return
  loading.value = true
  try {
    const response = await request(`/scenarios/${scenarioId}`)
    scenarioDetail.value = await response.json()
    optimizerForm.scenario_name = scenarioDetail.value.scenario?.name || optimizerForm.scenario_name
    optimizerForm.forecast_start_date = scenarioDetail.value.scenario?.forecast_start_date || optimizerForm.forecast_start_date
    optimizerForm.forecast_end_date = scenarioDetail.value.scenario?.forecast_end_date || optimizerForm.forecast_end_date
    scenarioSourceMode.value = scenarioDetail.value.scenario?.metadata?.scenario_source_mode || (scenarioDetail.value.context?.external_krs_schedule_dataset ? 'existing_krs' : 'new_krs')
    if (scenarioDetail.value.context) {
      await applyScenarioContext(scenarioDetail.value.context)
    }
    const luKeys = [...new Set((scenarioDetail.value.wells || []).map((item) => item.lu_id || 'Без LU'))].map((item) => `lu:${item}`)
    expandedProductionKeys.value = ['total', ...luKeys]
    selectedProductionKeys.value = []
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const toggleProductionExpand = (key) => {
  if (expandedProductionKeys.value.includes(key)) {
    expandedProductionKeys.value = expandedProductionKeys.value.filter((item) => item !== key)
    return
  }
  expandedProductionKeys.value = [...expandedProductionKeys.value, key]
}

const toggleProductionSelection = (key) => {
  if (selectedProductionKeys.value.includes(key)) {
    selectedProductionKeys.value = selectedProductionKeys.value.filter((item) => item !== key)
    return
  }
  selectedProductionKeys.value = [...selectedProductionKeys.value, key]
}

const openImportedSchedule = async (reference) => {
  if (!reference) return
  if (!selectedScenarioId.value) {
    showMessage('Сначала создайте или выберите сценарий.', 'error')
    return
  }
  loading.value = true
  try {
    scenarioSourceMode.value = 'existing_krs'
    await setActiveDataset(reference)
    await saveActiveScenarioContext({ silent: true })
    const response = await request('/schedule/open-imported', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_id: reference.dataset_id,
        dataset_version_id: reference.dataset_version_id,
      }),
    })
    const payload = await response.json()
    plannerDatasetReference.value = payload.dataset_reference
    plannerVersionName.value = payload.version_name
    versions.value = [{
      id: 'base',
      name: payload.version_name || 'Загруженный график',
      created_at: new Date().toISOString(),
      items: cloneItems(payload.items || []),
    }]
    activeVersionId.value = 'base'
    currentSection.value = 'planner'
    plannerDatasetSelectionKey.value = datasetReferenceKey(reference)
    showMessage('Импортированный график КРС открыт в Planner.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const createPlannerVersion = () => {
  if (!activeVersion.value) return
  const name = window.prompt('Название новой версии графика', `Версия ${versions.value.length}`)
  if (!name) return
  const nextVersion = {
    id: `version-${Date.now()}`,
    name,
    created_at: new Date().toISOString(),
    items: cloneItems(activeVersion.value.items),
  }
  versions.value = [...versions.value, nextVersion]
  activeVersionId.value = nextVersion.id
  showMessage('Новая версия графика создана.', 'success')
}

const publishPlannerVersion = async () => {
  if (!selectedScenarioId.value) {
    showMessage('Сначала выберите активный сценарий для Planner.', 'error')
    return
  }
  if (!activeVersion.value) return
  loading.value = true
  try {
    const revisionResponse = await request('/planner/revisions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        parent_scenario_id: selectedScenarioId.value,
        version_name: activeVersion.value.name,
        planner_version_id: activeVersion.value.id,
        items: activeVersion.value.items,
        metadata: {
          dataset_reference: plannerDatasetReference.value,
        },
      }),
    })
    const revision = await revisionResponse.json()
    const scenarioResponse = await request(`/scenarios/${selectedScenarioId.value}/from-planner-revision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        revision_id: revision.revision_id,
        name: `${optimizerForm.scenario_name} / ${activeVersion.value.name}`,
      }),
    })
    const derivedScenario = await scenarioResponse.json()
    await loadScenarios()
    selectedScenarioId.value = derivedScenario.scenario.scenario_id
    await loadScenarioDetail(derivedScenario.scenario.scenario_id)
    currentSection.value = 'production'
    showMessage('Planner revision сохранен и новая версия сценария создана автоматически.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const movePlannerEvent = (eventId, brigade, startDate) => {
  if (!canEditVersion.value || !eventId || !startDate || !activeVersion.value) return
  activeVersion.value.items = activeVersion.value.items.map((item) => {
    if (item.event_id !== eventId) return item
    return {
      ...item,
      brigade,
      start_date: startDate,
      end_date: addDays(startDate, Number(item.duration_days) - 1),
    }
  })
}

const dragPlannerEvent = (event, item) => {
  if (!canEditVersion.value) return
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', item.event_id)
}

const exportPlannerVersion = async () => {
  if (!activeVersion.value) return
  try {
    const response = await request('/schedule/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        version_name: activeVersion.value.name,
        columns: { ...plannerColumns },
        items: activeVersion.value.items,
      }),
    })
    const blob = await response.blob()
    const disposition = response.headers.get('content-disposition') || ''
    const match = disposition.match(/filename=\"?([^\"]+)\"?/i)
    const filename = match?.[1] || `${activeVersion.value.name}.xlsx`
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    showMessage('Версия Planner выгружена.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  }
}

watch(selectedScenarioId, async (scenarioId) => {
  if (!scenarioId) return
  await loadScenarioDetail(scenarioId)
})

watch([fullScheduleBounds], ([bounds]) => {
  if (!bounds.min || !bounds.max) {
    timelineStartOffset.value = 0
    timelineEndOffset.value = 0
    return
  }
  const totalDays = diffDays(bounds.min, bounds.max)
  const preferredStart = addDays(isoToday(), -7)
  const startOffset = preferredStart <= bounds.min ? 0 : Math.min(diffDays(bounds.min, preferredStart), totalDays)
  timelineStartOffset.value = startOffset
  timelineEndOffset.value = totalDays
}, { immediate: true })

watch(selectedUploadSourceKind, () => {
  resetNormalizeColumns()
  targetDatasetId.value = ''
  if (inputFile.value?.original_name) {
    datasetName.value = `${selectedUploadSourceKind.value}:${inputFile.value.original_name}`
  }
})

onMounted(async () => {
  await Promise.all([loadUploadedFiles(), loadDatasets(), loadManualInputSets(), loadScenarios()])
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-top">
        <div v-if="!sidebarCollapsed" class="sidebar-copy">
          <div class="brand">WorkNotOver</div>
          <div class="brand-subtitle">Module G + Planner shell</div>
        </div>
        <button class="icon-button" @click="sidebarCollapsed = !sidebarCollapsed">{{ sidebarCollapsed ? '→' : '←' }}</button>
      </div>

      <nav class="nav-list">
        <button class="nav-item" :class="{ active: currentSection === 'inputs' }" @click="currentSection = 'inputs'">
          <span class="nav-icon">⇪</span>
          <span v-if="!sidebarCollapsed">Исходные данные</span>
        </button>
        <button class="nav-item" :class="{ active: currentSection === 'production' }" @click="currentSection = 'production'">
          <span class="nav-icon">◔</span>
          <span v-if="!sidebarCollapsed">Добыча</span>
        </button>
        <button class="nav-item" :class="{ active: currentSection === 'planner' }" @click="currentSection = 'planner'">
          <span class="nav-icon">▦</span>
          <span v-if="!sidebarCollapsed">Планировщик КРС</span>
        </button>
      </nav>

      <div v-if="!sidebarCollapsed" class="sidebar-note">
        `Исходные данные` работает поверх Module A и ManualInputSet. `Добыча` читает сохраненные outputs Module B. `Планировщик КРС` остается отдельным модулем Planner.
      </div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div class="topbar-accent"></div>
        <div>
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageSubtitle }}</p>
        </div>
      </header>

      <div v-if="message" class="message" :class="messageType">{{ message }}</div>

      <section v-if="currentSection === 'inputs'" class="page-stack">
        <div class="panel soft">
          <div class="toolbar between align-start">
            <div>
              <h2>Активный сценарий</h2>
              <p class="subtitle">Scenario-first workflow: сначала создайте или выберите сценарий, затем привяжите datasets и ManualInputSet, после этого запускайте расчет или Planner.</p>
            </div>
            <div class="toolbar actions-wrap">
              <select v-model="selectedScenarioId" class="compact-dropdown">
                <option value="">Новый сценарий</option>
                <option v-for="item in groupedScenarios" :key="item.scenario_id" :value="item.scenario_id">
                  {{ item.name }} · {{ item.source_type }}
                </option>
              </select>
              <button class="button" :disabled="loading" @click="createScenario">Создать сценарий</button>
              <button class="button primary" :disabled="!selectedScenarioId || loading" @click="saveActiveScenarioContext()">Сохранить контекст</button>
            </div>
          </div>
          <div class="form-grid">
            <label class="field">
              <span>Имя сценария</span>
              <input v-model="optimizerForm.scenario_name" type="text" placeholder="Название сценария" />
            </label>
            <label class="field">
              <span>Источник графика КРС</span>
              <select v-model="scenarioSourceMode">
                <option value="new_krs">Новый график КРС</option>
                <option value="existing_krs">Загрузить существующий график КРС</option>
              </select>
            </label>
            <label class="field">
              <span>Дата старта прогноза</span>
              <input v-model="optimizerForm.forecast_start_date" type="date" />
            </label>
            <label class="field">
              <span>Дата конца прогноза</span>
              <input v-model="optimizerForm.forecast_end_date" type="date" />
            </label>
          </div>
          <div class="stats-grid scenario-stats">
            <div class="stat-card"><span>Wells</span><strong>{{ scenarioContextStatus.wells ? (selectedDatasets.wells?.name || 'OK') : 'Не задан' }}</strong></div>
            <div class="stat-card"><span>GTM</span><strong>{{ scenarioContextStatus.gtm ? (selectedDatasets.gtm?.name || 'OK') : 'Не задан' }}</strong></div>
            <div class="stat-card"><span>Infrastructure</span><strong>{{ scenarioContextStatus.infrastructure ? (selectedDatasets.infrastructure?.name || 'OK') : 'Опционально' }}</strong></div>
            <div class="stat-card"><span>ManualInputSet</span><strong>{{ scenarioContextStatus.manual_input ? (manualInputName || 'OK') : 'Не задан' }}</strong></div>
          </div>
          <div class="workflow-tree">
            <div
              v-for="step in workflowSteps"
              :key="step.key"
              class="workflow-item"
              :class="{ ready: step.ready }"
            >
              <div class="workflow-badge">{{ step.ready ? 'OK' : '...' }}</div>
              <div class="workflow-copy">
                <strong>{{ step.label }}</strong>
                <span>{{ step.description }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="tabs">
          <button
            v-for="tab in INPUT_TABS"
            :key="tab.key"
            class="tab-button"
            :class="{ active: currentInputsTab === tab.key }"
            @click="currentInputsTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <div v-if="currentInputsTab === 'upload'" class="page-stack">
          <div class="source-actions">
            <button
              v-for="(meta, key) in SOURCE_KIND_META"
              :key="key"
              class="source-action"
              :class="{ active: selectedUploadSourceKind === key }"
              @click="selectedUploadSourceKind = key"
            >
              <strong>{{ meta.title }}</strong>
              <span>{{ meta.description }}</span>
            </button>
          </div>

          <div class="module-grid two-wide">
            <div class="panel soft">
              <h2>Текущая загрузка</h2>
              <p class="subtitle">Excel загружается как source-файл, затем нормализуется в Dataset и сохраняется в Postgres.</p>
              <label class="upload-dropzone">
                <input type="file" accept=".xlsx,.xls" @change="uploadSourceFile" />
                <strong>Загрузить Excel</strong>
                <span>{{ SOURCE_KIND_META[selectedUploadSourceKind].title }}</span>
              </label>
              <div class="form-grid">
                <label class="field">
                  <span>Сохраненный файл</span>
                  <select v-model="selectedUploadFileId">
                    <option value="">Выберите файл</option>
                    <option v-for="item in uploadedFiles" :key="item.file_id" :value="item.file_id">{{ item.original_name }}</option>
                  </select>
                </label>
                <label class="field">
                  <span>Лист Excel</span>
                  <select v-model="selectedUploadSheet" :disabled="!selectedUploadFileId">
                    <option value="">Выберите лист</option>
                    <option v-for="sheet in (uploadedFiles.find((item) => item.file_id === selectedUploadFileId)?.sheets || [])" :key="sheet" :value="sheet">{{ sheet }}</option>
                  </select>
                </label>
                <label class="field">
                  <span>Имя Dataset</span>
                  <input v-model="datasetName" type="text" placeholder="Название набора данных" />
                </label>
                <label class="field">
                  <span>Новая версия existing dataset</span>
                  <select v-model="targetDatasetId">
                    <option value="">Новый dataset</option>
                    <option v-for="item in sourceDatasetOptions" :key="datasetReferenceKey(item.dataset_reference)" :value="item.dataset_reference.dataset_id">
                      {{ item.dataset_reference.name }}
                    </option>
                  </select>
                </label>
              </div>
              <div class="toolbar">
                <button class="button" :disabled="!selectedUploadFileId || loading" @click="openUploadedPreview(selectedUploadFileId, selectedUploadSheet || null)">Открыть preview</button>
                <button class="button primary" :disabled="!inputFile || loading" @click="normalizeDataset">Нормализовать и сохранить</button>
                <button
                  v-if="lastNormalizedDatasetReference?.dataset_type === 'external_krs_schedule'"
                  class="button success"
                  :disabled="loading"
                  @click="openImportedSchedule(lastNormalizedDatasetReference)"
                >
                  Открыть в Planner
                </button>
              </div>
              <div v-if="inputFile" class="info-cards">
                <div class="info-card"><span>Файл</span><strong>{{ inputFile.original_name }}</strong></div>
                <div class="info-card"><span>Лист</span><strong>{{ inputFile.selected_sheet }}</strong></div>
                <div class="info-card"><span>Колонок</span><strong>{{ inputFile.columns_info.length }}</strong></div>
                <div class="info-card"><span>Preview строк</span><strong>{{ inputFile.preview.length }}</strong></div>
              </div>
            </div>

            <div class="panel">
              <h2>Mapping колонок</h2>
              <p class="subtitle">Пустое поле означает auto-detect. Для wells и gtm имеет смысл задавать только спорные поля.</p>
              <div class="mapping-grid">
                <label v-for="fieldName in SOURCE_KIND_META[selectedUploadSourceKind].fields" :key="fieldName" class="field">
                  <span>{{ MAPPING_LABELS[fieldName] }}</span>
                  <select v-model="normalizeColumns[fieldName]">
                    <option value="">Автоопределение</option>
                    <option v-for="column in availableColumns" :key="`${fieldName}-${column.name}`" :value="column.name">{{ column.name }}</option>
                  </select>
                </label>
              </div>
            </div>
          </div>

          <div class="module-grid two-wide">
            <div class="panel">
              <div class="toolbar between">
                <div>
                  <h2>Реестр datasets</h2>
                  <p class="subtitle">Здесь выбираются активные datasets для расчета и для открытия в Planner.</p>
                </div>
                <button class="button ghost" :disabled="loading" @click="loadDatasets">Обновить</button>
              </div>
              <div class="dataset-groups">
                <div v-for="(items, type) in datasetTypes" :key="type" class="dataset-group">
                  <div class="dataset-group-title">{{ SOURCE_KIND_META[type]?.title || type }}</div>
                  <div v-if="!items.length" class="empty-inline">Нет наборов.</div>
                  <div v-else class="dataset-list">
                    <button
                      v-for="item in items"
                      :key="datasetReferenceKey(item.dataset_reference)"
                      class="dataset-card"
                      :class="{ active: datasetReferenceKey(selectedDatasets[type]) === datasetReferenceKey(item.dataset_reference) }"
                      @click="openDatasetDetail(item.dataset_reference)"
                    >
                      <div class="dataset-card-head">
                        <strong>{{ item.dataset_reference.name }}</strong>
                        <span>{{ item.dataset_reference.row_count || 0 }} строк</span>
                      </div>
                      <div class="dataset-card-meta">
                        <span>{{ item.source_file_name }}</span>
                        <span>{{ formatDateCell(item.dataset_reference.created_at) }}</span>
                      </div>
                      <div class="dataset-card-actions">
                        <button class="mini-button" @click.stop="setActiveDataset(item.dataset_reference)">Сделать активным</button>
                        <button v-if="type === 'external_krs_schedule'" class="mini-button accent" @click.stop="openImportedSchedule(item.dataset_reference)">Planner</button>
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div class="panel">
              <h2>Детали dataset</h2>
              <p class="subtitle">Нормализованный payload и validation summary для выбранного dataset.</p>
              <div v-if="selectedDatasetDetail" class="page-stack tight">
                <div class="detail-summary">
                  <div><span>Тип</span><strong>{{ selectedDatasetDetail.dataset_reference.dataset_type }}</strong></div>
                  <div><span>Имя</span><strong>{{ selectedDatasetDetail.dataset_reference.name }}</strong></div>
                  <div><span>Источник</span><strong>{{ selectedDatasetDetail.source_file_name }}</strong></div>
                </div>
                <div class="validation-box">
                  <strong>Validation</strong>
                  <div>Источник: {{ selectedDatasetDetail.validation_report?.source_kind || '—' }}</div>
                  <div>Лист: {{ selectedDatasetDetail.validation_report?.sheet_name || '—' }}</div>
                  <div>Строк: {{ selectedDatasetDetail.validation_report?.row_count || 0 }}</div>
                </div>

                <div v-if="Array.isArray(selectedDatasetDetail.normalized_payload)" class="table-wrap preview-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th v-for="column in Object.keys(selectedDatasetDetail.normalized_payload[0] || {})" :key="column">{{ column }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, index) in selectedDatasetDetail.normalized_payload.slice(0, 6)" :key="index">
                        <td v-for="column in Object.keys(selectedDatasetDetail.normalized_payload[0] || {})" :key="`${index}-${column}`">{{ row[column] }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else-if="selectedDatasetDetail.normalized_payload?.schedule?.items" class="table-wrap preview-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th v-for="column in Object.keys(selectedDatasetDetail.normalized_payload.schedule.items[0] || {})" :key="column">{{ column }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, index) in selectedDatasetDetail.normalized_payload.schedule.items.slice(0, 6)" :key="index">
                        <td v-for="column in Object.keys(selectedDatasetDetail.normalized_payload.schedule.items[0] || {})" :key="`${index}-${column}`">{{ row[column] }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <div v-else class="empty-state">Выберите dataset в реестре.</div>
            </div>
          </div>

          <div v-if="inputFile?.preview?.length" class="panel">
            <h2>Preview исходного Excel</h2>
            <div class="table-wrap preview-wrap">
              <table>
                <thead>
                  <tr><th v-for="column in previewColumns" :key="column">{{ column }}</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(row, index) in inputFile.preview" :key="index">
                    <td v-for="column in previewColumns" :key="`${index}-${column}`">{{ row[column] }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div v-else-if="currentInputsTab === 'reservoir'" class="page-stack">
          <div class="module-grid two-wide">
            <div class="panel">
              <div class="toolbar between">
                <div>
                  <h2>Конфигурации пласта</h2>
                  <p class="subtitle">Каждая запись задает общую характеристику вытеснения и два ряда annual decline для выбранного LU / SLOY.</p>
                </div>
                <button class="button primary" @click="addReservoirConfig">Добавить конфигурацию</button>
              </div>
              <div class="config-list">
                <button
                  v-for="config in reservoirConfigs"
                  :key="config.config_id"
                  class="config-pill"
                  :class="{ active: activeReservoirConfigId === config.config_id }"
                  @click="activeReservoirConfigId = config.config_id"
                >
                  {{ config.lu_id || 'Без LU' }} / {{ config.sloy_id || 'Все слои' }}
                </button>
              </div>
            </div>

            <div class="panel" v-if="activeReservoirConfig">
              <div class="toolbar between">
                <h2>Scope</h2>
                <button class="button ghost" :disabled="reservoirConfigs.length === 1" @click="removeReservoirConfig(activeReservoirConfig.config_id)">Удалить конфигурацию</button>
              </div>
              <div class="form-grid">
                <label class="field">
                  <span>LU</span>
                  <select v-model="activeReservoirConfig.lu_id">
                    <option value="">Выберите LU</option>
                    <option v-for="lu in luOptions" :key="lu" :value="lu">{{ lu }}</option>
                  </select>
                </label>
                <label class="field">
                  <span>SLOY</span>
                  <select v-model="activeReservoirConfig.sloy_id">
                    <option value="">Все слои</option>
                    <option v-for="sloy in sloyOptions" :key="sloy" :value="sloy">{{ sloy }}</option>
                  </select>
                </label>
              </div>
              <label class="field">
                <span>Заметки</span>
                <textarea v-model="activeReservoirConfig.notes" rows="2"></textarea>
              </label>
            </div>
          </div>

          <div v-if="activeReservoirConfig" class="module-grid two-wide">
            <div class="panel">
              <h2>Обводненность → NIZ</h2>
              <p class="subtitle">Таблица предзаполнена шагом 5%. В колонку NIZ можно вставить целый столбец через Ctrl+V.</p>
              <div class="table-wrap medium-wrap">
                <table>
                  <thead>
                    <tr><th>Обводненность, %</th><th>NIZ</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, index) in activeReservoirConfig.displacement_rows" :key="`watercut-${index}`">
                      <td>{{ row.watercut }}</td>
                      <td><input v-model="row.NIZ" type="text" class="table-input" @paste="handleNizPaste($event, activeReservoirConfig, index)" /></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="panel">
              <h2>Падение жидкости</h2>
              <div class="decline-split">
                <div>
                  <h3>База</h3>
                  <div class="table-wrap medium-wrap">
                    <table>
                      <thead><tr><th>Месяц</th><th>Годовой темп, %</th></tr></thead>
                      <tbody>
                        <tr v-for="row in activeReservoirConfig.base_decline_rows" :key="`base-${row.month_index}`">
                          <td>{{ row.month_index }}</td>
                          <td><input v-model="row.liquid_decline_factor" type="number" step="0.1" class="table-input" /></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <h3>ВНС</h3>
                  <div class="table-wrap medium-wrap">
                    <table>
                      <thead><tr><th>Месяц</th><th>Годовой темп, %</th></tr></thead>
                      <tbody>
                        <tr v-for="row in activeReservoirConfig.new_wells_decline_rows" :key="`new-${row.month_index}`">
                          <td>{{ row.month_index }}</td>
                          <td><input v-model="row.liquid_decline_factor" type="number" step="0.1" class="table-input" /></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="panel compact-save-panel">
            <div>
              <h2>ManualInputSet</h2>
              <p class="subtitle">Этот набор используется Module B при расчете посуточного профиля.</p>
            </div>
            <div class="toolbar">
              <input v-model="manualInputName" type="text" placeholder="Имя набора ручных вводных" />
              <button class="button primary" :disabled="loading" @click="saveManualInputs">Сохранить вводные</button>
            </div>
          </div>
        </div>

        <div v-else-if="currentInputsTab === 'economics'" class="page-stack">
          <div class="module-grid two-wide">
            <div class="panel">
              <div class="toolbar between">
                <div>
                  <h2>Экономические вводные</h2>
                  <p class="subtitle">MVP-лист: net back по LU. Хранится в ManualInputSet и затем используется Module C.</p>
                </div>
                <button class="button primary" @click="addEconomicsRow">Добавить LU</button>
              </div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>LU</th><th>Net Back</th></tr></thead>
                  <tbody>
                    <tr v-for="row in economicsRows" :key="row.id">
                      <td>
                        <select v-model="row.lu_id" class="table-input">
                          <option value="">Выберите LU</option>
                          <option v-for="lu in luOptions" :key="lu" :value="lu">{{ lu }}</option>
                        </select>
                      </td>
                      <td><input v-model="row.net_back" type="number" step="0.01" class="table-input" /></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <label class="field">
                <span>Заметки</span>
                <textarea v-model="economicsNotes" rows="3"></textarea>
              </label>
            </div>

            <div class="panel">
              <h2>Сохраненные наборы</h2>
              <p class="subtitle">Загрузка сохраненного ManualInputSet обратно в редактор.</p>
              <div class="form-grid single">
                <select v-model="selectedManualInputSetId">
                  <option value="">Выберите набор</option>
                  <option v-for="item in manualInputSets" :key="item.reference.manual_input_set_id" :value="item.reference.manual_input_set_id">
                    {{ item.reference.name }}
                  </option>
                </select>
                <button class="button" :disabled="!selectedManualInputSetId" @click="loadManualInputSet(selectedManualInputSetId)">Загрузить в редактор</button>
                <button class="button primary" :disabled="loading" @click="saveManualInputs">Сохранить текущий набор</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="currentInputsTab === 'brigades'" class="page-stack">
          <div class="module-grid three-wide">
            <div class="panel">
              <div class="toolbar between">
                <div>
                  <h2>Количество бригад по LU</h2>
                  <p class="subtitle">Помесечный ресурсный ввод начиная с текущего месяца.</p>
                </div>
              </div>
              <div class="toolbar">
                <select v-model="brigadeCapacitySeedLu">
                  <option value="">Выберите LU</option>
                  <option v-for="lu in luOptions" :key="lu" :value="lu">{{ lu }}</option>
                </select>
                <button class="button" @click="seedBrigadeCapacityRows">Добавить 12 месяцев</button>
                <button class="button ghost" @click="addBrigadeRow">Добавить строку</button>
              </div>
              <div class="table-wrap medium-wrap">
                <table>
                  <thead><tr><th>LU</th><th>Месяц</th><th>Бригад</th></tr></thead>
                  <tbody>
                    <tr v-for="row in brigadeCapacityRows" :key="row.id">
                      <td>
                        <select v-model="row.lu_id" class="table-input">
                          <option value="">LU</option>
                          <option v-for="lu in luOptions" :key="lu" :value="lu">{{ lu }}</option>
                        </select>
                      </td>
                      <td><input v-model="row.month_date" type="date" class="table-input" /></td>
                      <td><input v-model="row.brigade_count" type="number" min="0" step="1" class="table-input" /></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="panel">
              <div class="toolbar between">
                <div>
                  <h2>Коэффициент отказности</h2>
                  <p class="subtitle">Scope по LU или по SLOY.</p>
                </div>
                <button class="button ghost" @click="addFailureRow">Добавить строку</button>
              </div>
              <div class="table-wrap medium-wrap">
                <table>
                  <thead><tr><th>Scope</th><th>LU</th><th>SLOY</th><th>Коэффициент</th></tr></thead>
                  <tbody>
                    <tr v-for="row in failureRows" :key="row.id">
                      <td>
                        <select v-model="row.scope_type" class="table-input">
                          <option value="LU">LU</option>
                          <option value="SLOY">SLOY</option>
                        </select>
                      </td>
                      <td>
                        <select v-model="row.lu_id" class="table-input">
                          <option value="">LU</option>
                          <option v-for="lu in luOptions" :key="lu" :value="lu">{{ lu }}</option>
                        </select>
                      </td>
                      <td>
                        <select v-model="row.sloy_id" class="table-input">
                          <option value="">SLOY</option>
                          <option v-for="sloy in sloyOptions" :key="sloy" :value="sloy">{{ sloy }}</option>
                        </select>
                      </td>
                      <td><input v-model="row.coefficient" type="number" step="0.01" class="table-input" /></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="panel">
              <div class="toolbar between">
                <div>
                  <h2>Длительности работ</h2>
                  <p class="subtitle">KrsResourceConfig плюс global fallback по числу бригад.</p>
                </div>
                <button class="button ghost" @click="addDurationRow">Добавить тип</button>
              </div>
              <label class="field">
                <span>Fallback brigade_count</span>
                <input v-model="krsFallbackBrigades" type="number" min="0" step="1" />
              </label>
              <div class="table-wrap medium-wrap">
                <table>
                  <thead><tr><th>Тип ГТМ</th><th>Длительность, дни</th></tr></thead>
                  <tbody>
                    <tr v-for="row in durationRows" :key="row.id">
                      <td><input v-model="row.gtm_type" type="text" class="table-input" /></td>
                      <td><input v-model="row.duration_days" type="number" min="0" step="1" class="table-input" /></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="panel compact-save-panel">
            <div>
              <h2>Сохранение</h2>
              <p class="subtitle">Эти три блока уходят в один ManualInputSet, но как разные config payloads.</p>
            </div>
            <div class="toolbar">
              <button class="button primary" :disabled="loading" @click="saveManualInputs">Сохранить вводные</button>
            </div>
          </div>
        </div>

        <div v-else class="page-stack">
          <div class="module-grid two-wide">
            <div class="panel">
              <h2>Схема работы оптимизатора</h2>
              <p class="subtitle">UI настраивает payload запуска. Сам optimizer еще не реализован, но расчетный сценарий Module B уже можно запускать отсюда.</p>
              <div class="form-grid">
                <label class="field">
                  <span>Название сценария</span>
                  <input v-model="optimizerForm.scenario_name" type="text" />
                </label>
                <label class="field">
                  <span>Режим</span>
                  <select v-model="optimizerForm.run_mode">
                    <option value="forecast_only">Только расчет профиля</option>
                    <option value="build_schedule">Построение графика</option>
                    <option value="optimize">Построение + оптимизация</option>
                  </select>
                </label>
                <label class="field">
                  <span>Целевая функция</span>
                  <select v-model="optimizerForm.objective">
                    <option value="oil_max">Максимум нефти</option>
                    <option value="npv_max">Максимум NPV</option>
                    <option value="liq_max">Максимум жидкости</option>
                  </select>
                </label>
                <label class="field">
                  <span>Реакция на infra constraints</span>
                  <select v-model="optimizerForm.infra_policy">
                    <option value="warn">Только предупреждение</option>
                    <option value="hard_stop">Жесткий стоп</option>
                    <option value="penalty">Штраф в ранжировании</option>
                  </select>
                </label>
                <label class="field">
                  <span>Heuristic mode</span>
                  <select v-model="optimizerForm.heuristic_mode">
                    <option value="basic">Basic</option>
                    <option value="balanced">Balanced</option>
                    <option value="aggressive">Aggressive</option>
                  </select>
                </label>
                <label class="field">
                  <span>Wells dataset</span>
                  <select v-model="selectedDatasetKeys.wells" @change="selectDatasetByKey('wells', selectedDatasetKeys.wells)">
                    <option value="">Выберите dataset</option>
                    <option v-for="item in datasetTypes.wells" :key="datasetReferenceKey(item.dataset_reference)" :value="datasetReferenceKey(item.dataset_reference)">
                      {{ item.dataset_reference.name }}
                    </option>
                  </select>
                </label>
                <label class="field">
                  <span>GTM dataset</span>
                  <select v-model="selectedDatasetKeys.gtm" @change="selectDatasetByKey('gtm', selectedDatasetKeys.gtm)">
                    <option value="">Выберите dataset</option>
                    <option v-for="item in datasetTypes.gtm" :key="datasetReferenceKey(item.dataset_reference)" :value="datasetReferenceKey(item.dataset_reference)">
                      {{ item.dataset_reference.name }}
                    </option>
                  </select>
                </label>
                <label class="field">
                  <span>ManualInputSet</span>
                  <select v-model="selectedManualInputSetId">
                    <option value="">Выберите набор</option>
                    <option v-for="item in manualInputSets" :key="item.reference.manual_input_set_id" :value="item.reference.manual_input_set_id">
                      {{ item.reference.name }}
                    </option>
                  </select>
                </label>
                <label class="field">
                  <span>Forecast start</span>
                  <input v-model="optimizerForm.forecast_start_date" type="date" />
                </label>
                <label class="field">
                  <span>Forecast end</span>
                  <input v-model="optimizerForm.forecast_end_date" type="date" />
                </label>
              </div>
              <label class="field">
                <span>Заметки</span>
                <textarea v-model="optimizerForm.notes" rows="3"></textarea>
              </label>
              <div class="toolbar">
                <button class="button" :disabled="loading" @click="saveManualInputs">Сохранить ManualInputSet</button>
                <button class="button primary" :disabled="loading" @click="calculateForecast">Рассчитать профиль Module B</button>
              </div>
            </div>

            <div class="panel">
              <h2>Активные входы сценария</h2>
              <div class="detail-summary">
                <div><span>Wells</span><strong>{{ selectedDatasets.wells?.name || '—' }}</strong></div>
                <div><span>GTM</span><strong>{{ selectedDatasets.gtm?.name || '—' }}</strong></div>
                <div><span>Infrastructure</span><strong>{{ selectedDatasets.infrastructure?.name || '—' }}</strong></div>
                <div><span>ManualInputSet</span><strong>{{ manualInputSets.find((item) => item.reference.manual_input_set_id === selectedManualInputSetId)?.reference.name || '—' }}</strong></div>
              </div>
              <div class="validation-box">
                <strong>Дефолтный горизонт</strong>
                <div>Старт: {{ formatDateCell(optimizerForm.forecast_start_date) }}</div>
                <div>Конец: {{ formatDateCell(optimizerForm.forecast_end_date) }}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-else-if="currentSection === 'production'" class="page-stack">
        <div class="panel soft">
          <div class="toolbar between align-start">
            <div>
              <h2>Сценарий расчета</h2>
              <p class="subtitle">Раздел читает сохраненные outputs Module B. UI только агрегирует и фильтрует их по иерархии.</p>
            </div>
            <div class="toolbar">
              <select v-model="selectedScenarioId" class="compact-dropdown">
                <option value="">Выберите сценарий</option>
                <option v-for="scenario in groupedScenarios" :key="scenario.scenario_id" :value="scenario.scenario_id">
                  {{ scenario.name }}
                </option>
              </select>
              <button class="button ghost" :disabled="loading" @click="loadScenarios">Обновить</button>
            </div>
          </div>
        </div>

        <div v-if="!scenarioDetail" class="panel empty-state">
          Сохраненные сценарии пока не загружены. Запустите расчет на листе `Схема работы оптимизатора`.
        </div>

        <template v-else>
          <div class="stats-grid production-stats">
            <div class="stat-card"><span>Период</span><strong>{{ formatDateCell(scenarioDetail.scenario.forecast_start_date) }} — {{ formatDateCell(scenarioDetail.scenario.forecast_end_date) }}</strong></div>
            <div class="stat-card"><span>Нефть по выборке</span><strong>{{ formatCompactNumber(selectedProductionSummary.totalOil) }}</strong></div>
            <div class="stat-card"><span>Жидкость по выборке</span><strong>{{ formatCompactNumber(selectedProductionSummary.totalLiquid) }}</strong></div>
          </div>

          <div class="panel production-panel">
            <div class="toolbar between">
              <div>
                <h2>Накопительная добыча нефти</h2>
                <p class="subtitle">Категории `БАЗА`, `ГТМ`, `ВНС` агрегируются по выбранным leaf-скважинам.</p>
              </div>
              <div class="legend">
                <span v-for="item in productionChartLegend" :key="item.label" class="legend-item"><i class="legend-dot" :style="{ background: item.color }"></i>{{ item.label }} {{ formatCompactNumber(item.value) }}</span>
              </div>
            </div>
            <div class="production-chart-wrap">
              <svg v-if="productionSeries.length" class="production-chart" :viewBox="`0 0 ${PRODUCTION_CHART_WIDTH} ${PRODUCTION_CHART_HEIGHT}`" preserveAspectRatio="none">
                <path :d="productionBasePath" class="production-area base" />
                <path :d="productionGtmPath" class="production-area gtm" />
                <path :d="productionVnsPath" class="production-area vns" />
              </svg>
              <div v-else class="empty-inline">Нет данных по выбранной группе.</div>
              <div class="production-labels">
                <span v-for="item in productionLabelPoints" :key="item.date">{{ formatDateCell(item.date) }} · {{ formatCompactNumber(item.totalCum) }}</span>
              </div>
            </div>
          </div>

          <div class="panel">
            <div class="toolbar between">
              <div>
                <h2>Иерархия профиля</h2>
                <p class="subtitle">Выделение работает по leaf rows. Parent-узлы только разворачивают и задают область выбора.</p>
              </div>
              <button class="button ghost" @click="selectedProductionKeys = []">Сбросить выбор</button>
            </div>
            <div class="table-wrap hierarchy-wrap">
              <table class="hierarchy-table">
                <thead>
                  <tr>
                    <th>Выбор</th>
                    <th>Узел</th>
                    <th>Фонд</th>
                    <th>Скважин</th>
                    <th>Нефть</th>
                    <th>Жидкость</th>
                    <th>Газ</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in productionTree.rows" :key="row.key" :class="`node-${row.nodeType}`">
                    <td><input type="checkbox" :checked="selectedProductionKeys.includes(row.key)" @change="toggleProductionSelection(row.key)" /></td>
                    <td>
                      <div class="node-cell" :style="{ paddingLeft: `${row.depth * 18}px` }">
                        <button v-if="row.children.length" class="node-toggle" @click="toggleProductionExpand(row.key)">{{ expandedProductionKeys.includes(row.key) ? '−' : '+' }}</button>
                        <span v-else class="node-spacer"></span>
                        <strong>{{ row.label }}</strong>
                      </div>
                    </td>
                    <td>{{ row.fundType || '—' }}</td>
                    <td>{{ row.wellCount }}</td>
                    <td>{{ formatCompactNumber(row.totalOil) }}</td>
                    <td>{{ formatCompactNumber(row.totalLiquid) }}</td>
                    <td>{{ formatCompactNumber(row.totalGas) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </section>

      <section v-else class="page-stack planner-stack">
        <div class="panel soft">
          <div class="toolbar between align-start">
            <div>
              <h2>Источник Planner</h2>
              <p class="subtitle">Planner открывает только импортированные datasets типа `external_krs_schedule` через runtime flow `open-imported`.</p>
            </div>
            <div class="toolbar">
              <select v-model="plannerDatasetSelectionKey" class="compact-dropdown">
                <option value="">Выберите imported KRS dataset</option>
                <option
                  v-for="item in datasetTypes.external_krs_schedule"
                  :key="datasetReferenceKey(item.dataset_reference)"
                  :value="datasetReferenceKey(item.dataset_reference)"
                >
                  {{ item.dataset_reference.name }}
                </option>
              </select>
              <button
                class="button primary"
                :disabled="!plannerDatasetSelectionKey || loading"
                @click="openImportedSchedule(datasetTypes.external_krs_schedule.find((item) => datasetReferenceKey(item.dataset_reference) === plannerDatasetSelectionKey)?.dataset_reference)"
              >
                Открыть
              </button>
            </div>
          </div>
        </div>

        <div v-if="!activeItems.length" class="panel empty-state">
          Сначала импортируйте существующий график КРС на листе `Загрузка`, затем откройте его здесь через dataset runtime flow.
        </div>

        <template v-else>
          <div class="stats-grid">
            <div class="stat-card"><span>Источник</span><strong>{{ plannerVersionName || plannerDatasetReference?.name || '—' }}</strong></div>
            <div class="stat-card"><span>Мероприятий</span><strong>{{ visibleItems.length }}</strong></div>
            <div class="stat-card"><span>Суммарный прирост Qн</span><strong>{{ totalIncrement.toFixed(1) }}</strong></div>
          </div>

          <div class="panel soft">
            <div class="toolbar between align-start">
              <div>
                <h2>Версии графика</h2>
                <p class="subtitle">Базовая версия остается эталоном. Для drag-and-drop создайте отдельную planner-версию.</p>
              </div>
              <div class="toolbar actions-wrap">
                <select v-model="activeVersionId"><option v-for="version in versions" :key="version.id" :value="version.id">{{ version.name }}</option></select>
                <button class="button" @click="createPlannerVersion">Локальная версия</button>
                <button class="button primary" :disabled="!selectedScenarioId || loading" @click="publishPlannerVersion">Создать версию</button>
                <button class="button success" @click="exportPlannerVersion">Выгрузить Excel</button>
              </div>
            </div>
            <div class="notice">{{ canEditVersion ? 'Редактирование активно: перетаскивайте карточки между бригадами и датами.' : 'Редактирование выключено: создайте новую версию графика.' }}</div>
          </div>

          <div class="panel planner-panel summary-panel">
            <div class="section-head">
              <div></div>
              <div class="legend">
                <span class="legend-item"><i class="legend-swatch today"></i> Сегодня</span>
                <span class="legend-item"><i class="legend-swatch zero"></i> Без прироста</span>
                <span class="legend-item"><i class="legend-swatch ppd"></i> Перевод в ППД</span>
              </div>
            </div>
            <div class="prefix-legend top-prefix-legend">
              <span v-for="item in incrementLegend" :key="item.prefix" class="prefix-chip"><i :style="{ background: item.color }"></i>{{ item.prefix }}</span>
            </div>

            <div class="gantt-wrap compact-board summary-wrap">
              <div class="gantt-board" :style="{ '--day-count': ganttDates.length, '--day-width': `${timelineDayWidth}px` }">
                <div class="gantt-grid chart-grid chart-month-grid">
                  <div class="gantt-corner"></div>
                  <div v-for="segment in monthSegments" :key="segment.key" class="gantt-month" :style="{ gridColumn: `span ${segment.span}` }">{{ segment.label }}</div>
                </div>
                <div class="gantt-grid chart-grid chart-day-grid">
                  <div class="gantt-corner"></div>
                  <div v-for="date in ganttDates" :key="date" class="gantt-date">{{ formatDayNumber(date) }}</div>
                </div>
                <div class="gantt-grid chart-row">
                  <div class="chart-side"></div>
                  <div class="chart-track">
                    <div v-if="todayOffset !== null" class="today-line" :style="{ left: `calc(${todayOffset} * var(--day-width) + (var(--day-width) / 2))` }"></div>
                    <svg v-if="cumulativeIncrementSeries.length" class="chart-line-overlay" :viewBox="`0 0 ${Math.max(ganttDates.length * timelineDayWidth, 1)} ${PLANNER_CHART_HEIGHT}`" preserveAspectRatio="none">
                      <polyline :points="cumulativeLinePoints" class="chart-cumulative-line" />
                    </svg>
                    <div
                      v-for="point in cumulativeLineLabels"
                      :key="`cum-${point.date}`"
                      class="chart-cumulative-label"
                      :style="{ left: `${point.x}px`, top: `${PLANNER_CHART_HEIGHT - (point.total / cumulativeIncrementMax) * PLANNER_CHART_HEIGHT - 14}px` }"
                    >
                      {{ point.total.toFixed(1) }}
                    </div>
                    <div v-for="group in topChartBars" :key="group.date" class="chart-group" :style="{ left: `calc(${group.offset} * var(--day-width))` }">
                      <div v-if="group.total > 0" class="chart-total" :title="group.labels.join('\n')">
                        <div class="chart-total-label">{{ group.total.toFixed(1) }}</div>
                        <div class="chart-total-bar-wrap" :style="{ height: `${Math.max((group.total / topChartMax) * 100, 10)}%` }">
                          <div class="chart-total-bar">
                            <div
                              v-for="item in group.positive"
                              :key="item.event_id"
                              class="chart-segment"
                              :style="{ background: item.color, flex: `${Math.max(item.value, 1)} 1 0`, opacity: gtmOpacity(item) }"
                            ></div>
                          </div>
                        </div>
                      </div>
                      <div class="chart-zeroes">
                        <div
                          v-for="item in group.zero"
                          :key="`${item.event_id}-zero`"
                          class="summary-dot"
                          :class="{ ppd: item.is_ppd }"
                          :style="item.is_ppd ? {} : { background: item.color, opacity: gtmOpacity(item) }"
                          :title="`${item.well} · ${item.is_ppd ? '0 / ППД' : '0 / без прироста'} · ${item.planned_work}`"
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="zoom-strip">
            <div class="zoom-strip-row">
              <label class="control-inline">
                <span>ГТМ</span>
                <input v-model="minIncrementFilter" type="range" min="0" max="100" step="1" />
                <strong>от {{ minIncrementFilter }}</strong>
              </label>
              <label class="control-inline compact-select">
                <span>УН</span>
                <select v-model="selectedPrefixes" multiple size="1">
                  <option v-for="prefix in prefixOptions" :key="prefix" :value="prefix">{{ prefix }}</option>
                </select>
              </label>
              <label class="toggle-inline toggle-inline-ppd">
                <input v-model="showPpd" type="checkbox" />
                <span>ППД</span>
              </label>
              <label class="control-inline compact-select">
                <span>Участки</span>
                <select v-model="selectedAreas" multiple size="1">
                  <option v-for="area in areaOptions" :key="area" :value="area">{{ area }}</option>
                </select>
              </label>
              <label class="control-inline">
                <span>От</span>
                <input v-model="timelineStartOffset" type="range" min="0" :max="fullTimelineDays" step="1" />
                <strong>{{ formatDateCell(timelineWindowStart) }}</strong>
              </label>
              <label class="control-inline">
                <span>До</span>
                <input v-model="timelineEndOffset" type="range" min="0" :max="fullTimelineDays" step="1" />
                <strong>{{ formatDateCell(timelineWindowEnd) }}</strong>
              </label>
              <span>Масштаб</span>
              <input v-model="timelineZoom" type="range" min="8" max="28" step="1" />
              <span>{{ timelineZoom }} px/день</span>
            </div>
            <div class="zoom-strip-row zoom-strip-row-secondary">
              <label class="control-inline compact-select">
                <span>Планируемый объем работ</span>
                <select v-model="selectedWorkTypes" multiple size="1">
                  <option v-for="workType in plannedWorkOptions" :key="workType" :value="workType">{{ workType }}</option>
                </select>
              </label>
            </div>
          </div>

          <div class="panel planner-panel">
            <div class="gantt-main-wrap">
              <div class="gantt-wrap gantt-main-scroll">
                <div class="gantt-board" :style="{ '--day-count': ganttDates.length, '--day-width': `${timelineDayWidth}px` }">
                  <div class="gantt-header gantt-grid month-grid">
                    <div class="gantt-corner"></div>
                    <div v-for="segment in monthSegments" :key="`gantt-${segment.key}`" class="gantt-month" :style="{ gridColumn: `span ${segment.span}` }">{{ segment.label }}</div>
                  </div>
                  <div class="gantt-header gantt-grid day-grid">
                    <div class="gantt-corner"></div>
                    <div v-for="date in ganttDates" :key="`gantt-${date}`" class="gantt-date">{{ formatDayNumber(date) }}</div>
                  </div>
                  <div v-for="row in ganttRows" :key="row.brigade" class="gantt-grid gantt-row" :style="{ '--lane-count': row.laneCount }">
                    <div class="gantt-brigade">{{ row.brigade }}</div>
                    <div class="gantt-track">
                      <div v-if="todayOffset !== null" class="today-line" :style="{ left: `calc(${todayOffset} * var(--day-width) + (var(--day-width) / 2))` }"></div>
                      <div class="gantt-drop-grid">
                        <div v-for="date in ganttDates" :key="`${row.brigade}-${date}`" class="gantt-drop-cell" :class="{ editable: canEditVersion }" @dragover.prevent @drop="movePlannerEvent($event.dataTransfer.getData('text/plain'), row.brigade, date)"></div>
                      </div>
                      <div
                        v-for="item in row.bars"
                        :key="item.event_id"
                        class="gantt-bar"
                        :class="{ readonly: !canEditVersion }"
                        :style="{ left: `calc(${item.startOffset} * var(--day-width))`, width: `calc(${item.visibleDurationDays} * var(--day-width))`, top: `calc(${item.lane} * var(--lane-height))`, background: item.color, opacity: gtmOpacity(item) }"
                        :draggable="canEditVersion"
                        @dragstart="dragPlannerEvent($event, item)"
                        :title="`${item.planned_work}\n${formatDateCell(item.start_date)} - ${formatDateCell(item.end_date)}`"
                      >
                        <strong>{{ item.well }}</strong>
                        <span>{{ formatIncrement(item.increment) }}</span>
                        <div class="gantt-tooltip">
                          <div>{{ item.planned_work }}</div>
                          <div>{{ formatDateCell(item.start_date) }} - {{ formatDateCell(item.end_date) }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </section>
    </main>
  </div>
</template>

<style scoped>
:global(:root) {
  --day-width: 12px;
  --lane-height: 12px;
}

.app-shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: 100vh;
}

.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100vh;
  padding: 20px 14px;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(12px);
  border-right: 1px solid rgba(35, 50, 68, 0.08);
}

.sidebar.collapsed {
  width: 88px;
  padding-inline: 12px;
}

.sidebar-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.brand {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #172132;
}

.brand-subtitle,
.subtitle,
.sidebar-note,
.field span,
.topbar p {
  color: #70839a;
}

.brand-subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.4;
}

.sidebar-note {
  margin-top: auto;
  padding: 12px;
  border-radius: 16px;
  background: linear-gradient(180deg, #f5f9ff, #eef6ff);
  border: 1px solid rgba(47, 128, 255, 0.12);
  line-height: 1.45;
  font-size: 13px;
}

.icon-button {
  width: 40px;
  height: 40px;
  border: 1px solid rgba(35, 50, 68, 0.1);
  border-radius: 999px;
  background: #fff;
  color: #516072;
  cursor: pointer;
  box-shadow: 0 8px 16px rgba(32, 56, 88, 0.06);
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-item,
.tab-button,
.source-action,
.dataset-card,
.button,
.mini-button,
.config-pill {
  transition: transform 0.15s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.nav-item:hover,
.tab-button:hover,
.source-action:hover,
.dataset-card:hover,
.button:hover:not(:disabled),
.mini-button:hover:not(:disabled),
.config-pill:hover {
  transform: translateY(-1px);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: none;
  border-radius: 14px;
  background: transparent;
  color: #465568;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
}

.nav-item.active,
.nav-item:hover {
  background: #edf4ff;
  color: #162131;
}

.nav-icon {
  width: 20px;
  text-align: center;
  font-size: 16px;
}

.main-area {
  min-width: 0;
  padding: 18px 20px 22px;
}

.topbar {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.topbar-accent {
  width: 4px;
  height: 40px;
  border-radius: 999px;
  background: linear-gradient(180deg, #2f80ff, #4cc39a);
}

.topbar h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.topbar p {
  margin: 6px 0 0;
  line-height: 1.35;
  max-width: 980px;
}

.message {
  margin-bottom: 10px;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 12px;
}

.message.success {
  background: #ecf9f1;
  color: #157347;
  border-color: #b7e4c7;
}

.message.error {
  background: #fff1f1;
  color: #b42318;
  border-color: #f4c7c3;
}

.message.info {
  background: #eef6ff;
  color: #1d4ed8;
  border-color: #bfd6ff;
}

.page-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tabs,
.toolbar,
.config-list,
.source-actions,
.legend,
.prefix-legend,
.zoom-strip-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.tabs {
  gap: 8px;
}

.tab-button,
.config-pill {
  padding: 10px 14px;
  border: 1px solid rgba(35, 50, 68, 0.1);
  border-radius: 999px;
  background: #fff;
  color: #516072;
  cursor: pointer;
}

.tab-button.active,
.config-pill.active {
  background: #edf4ff;
  color: #18314e;
  border-color: rgba(47, 128, 255, 0.24);
}

.source-actions {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.source-action {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 108px;
  padding: 16px;
  border: 1px solid rgba(35, 50, 68, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.95);
  text-align: left;
  cursor: pointer;
}

.source-action.active {
  background: linear-gradient(180deg, #edf4ff, #f7fbff);
  border-color: rgba(47, 128, 255, 0.24);
}

.source-action span {
  color: #70839a;
  line-height: 1.35;
}

.module-grid {
  display: grid;
  gap: 12px;
}

.module-grid.two-wide {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.module-grid.three-wide {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.panel {
  min-width: 0;
  padding: 16px;
  border: 1px solid rgba(35, 50, 68, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 10px 24px rgba(30, 55, 90, 0.05);
}

.panel.soft {
  background: linear-gradient(180deg, #ffffff, #f7fbff);
}

.panel h2,
.panel h3 {
  margin: 0 0 6px;
  letter-spacing: -0.03em;
}

.panel h2 {
  font-size: 22px;
}

.panel h3 {
  font-size: 16px;
}

.subtitle {
  margin: 0;
  line-height: 1.35;
  font-size: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.field span {
  font-size: 12px;
  font-weight: 600;
}

.form-grid,
.detail-summary,
.info-cards,
.stats-grid {
  display: grid;
  gap: 10px;
}

.form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-summary {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.info-cards,
.stats-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

input,
select,
textarea,
.button,
.compact-dropdown {
  min-height: 40px;
  padding: 9px 12px;
  border: 1px solid rgba(38, 51, 68, 0.12);
  border-radius: 12px;
  background: #fff;
  color: #243345;
  font: inherit;
}

textarea {
  min-height: 72px;
  resize: vertical;
}

.table-input {
  min-height: 34px;
  width: 100%;
  padding: 6px 8px;
}

.button,
.mini-button {
  font-weight: 700;
  cursor: pointer;
}

.button.primary,
.mini-button.accent {
  color: #fff;
  background: #2f80ff;
  border-color: #2f80ff;
}

.button.success {
  color: #fff;
  background: #35b36b;
  border-color: #35b36b;
}

.button.ghost,
.mini-button {
  background: #f3f7fc;
}

.button:disabled,
.mini-button:disabled,
select:disabled,
input:disabled,
textarea:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.toolbar.between {
  justify-content: space-between;
}

.align-start {
  align-items: flex-start;
}

.actions-wrap {
  justify-content: flex-end;
}

.compact-dropdown {
  min-width: 280px;
}

.upload-dropzone {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 10px;
  min-height: 150px;
  padding: 18px;
  border: 1px dashed rgba(47, 128, 255, 0.3);
  border-radius: 18px;
  background: #fbfdff;
  text-align: center;
  cursor: pointer;
}

.upload-dropzone input {
  display: none;
}

.dataset-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dataset-group-title {
  font-size: 13px;
  font-weight: 700;
  color: #4d6178;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.dataset-list {
  display: grid;
  gap: 10px;
}

.dataset-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid rgba(35, 50, 68, 0.08);
  border-radius: 16px;
  background: linear-gradient(180deg, #fff, #f7fbff);
  cursor: pointer;
  text-align: left;
}

.dataset-card.active {
  border-color: rgba(47, 128, 255, 0.24);
  background: linear-gradient(180deg, #eef5ff, #f9fbff);
}

.dataset-card-head,
.dataset-card-meta,
.dataset-card-actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.dataset-card-head span,
.dataset-card-meta span,
.validation-box,
.notice,
.empty-inline {
  color: #627286;
  font-size: 13px;
}

.validation-box,
.notice {
  padding: 10px 12px;
  border-radius: 12px;
  background: #f4f7fb;
}

.detail-summary > div,
.info-card,
.stat-card {
  padding: 12px 14px;
  border: 1px solid rgba(35, 50, 68, 0.08);
  border-radius: 16px;
  background: linear-gradient(180deg, #fff, #f7fbff);
}

.detail-summary span,
.info-card span,
.stat-card span {
  display: block;
  color: #7a8ca1;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.detail-summary strong,
.info-card strong,
.stat-card strong {
  display: block;
  margin-top: 6px;
  font-size: 18px;
  color: #1c2736;
}

.table-wrap {
  overflow: auto;
  border: 1px solid rgba(35, 50, 68, 0.08);
  border-radius: 16px;
}

.preview-wrap {
  max-height: 360px;
}

.medium-wrap {
  max-height: 420px;
}

.hierarchy-wrap {
  max-height: 520px;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}

th,
td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(35, 50, 68, 0.08);
  text-align: left;
  vertical-align: top;
}

th {
  position: sticky;
  top: 0;
  background: #f8fbff;
  color: #5d6f84;
  font-size: 12px;
  z-index: 1;
}

.node-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-toggle {
  width: 24px;
  height: 24px;
  border: 1px solid rgba(35, 50, 68, 0.12);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

.node-spacer {
  width: 24px;
  display: inline-block;
}

.node-total td {
  font-weight: 800;
}

.node-lu td strong,
.node-sloy td strong,
.node-pad td strong {
  font-weight: 700;
}

.decline-split {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.compact-save-panel {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: center;
}

.production-stats {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.production-panel {
  gap: 14px;
}

.legend {
  justify-content: flex-end;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #617388;
  font-size: 13px;
}

.legend-dot,
.legend-swatch {
  display: inline-block;
  border-radius: 999px;
}

.legend-dot {
  width: 12px;
  height: 12px;
}

.legend-swatch {
  width: 14px;
  height: 14px;
  background: #3f8dff;
}

.legend-swatch.zero {
  background: #dd4c4c;
}

.legend-swatch.ppd {
  background: #2f67ec;
}

.legend-swatch.today {
  width: 3px;
  height: 16px;
  background: #e53935;
}

.production-chart-wrap {
  overflow-x: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.production-chart {
  min-width: 100%;
  height: 260px;
}

.production-area.base {
  fill: rgba(47, 128, 255, 0.78);
}

.production-area.gtm {
  fill: rgba(76, 195, 154, 0.78);
}

.production-area.vns {
  fill: rgba(230, 124, 37, 0.8);
}

.production-labels {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: #627286;
  font-size: 12px;
}

.planner-stack {
  gap: 10px;
}

.planner-panel {
  padding-bottom: 12px;
}

.gantt-wrap {
  overflow: auto;
  border-radius: 16px;
}

.compact-board {
  max-height: calc(100vh - 220px);
}

.gantt-main-wrap {
  overflow: visible;
  max-height: none;
}

.gantt-main-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  max-height: none;
}

.summary-wrap {
  max-height: 270px;
  overflow-y: hidden;
}

.gantt-board {
  min-width: fit-content;
  background: #fff;
}

.gantt-grid {
  display: grid;
  grid-template-columns: 78px repeat(var(--day-count), var(--day-width));
}

.gantt-header {
  position: sticky;
  z-index: 4;
  background: #fbfdff;
}

.month-grid { top: 0; }
.day-grid { top: 28px; z-index: 3; }

.gantt-corner,
.gantt-date,
.gantt-brigade,
.chart-side {
  display: flex;
  align-items: center;
  min-height: 28px;
  padding: 4px 6px;
  border-right: 1px solid rgba(35, 50, 68, 0.08);
}

.gantt-corner,
.gantt-brigade,
.chart-side {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #fbfdff;
  font-weight: 700;
  color: #1f2937;
}

.gantt-corner { color: transparent; }

.gantt-date {
  justify-content: center;
  color: #6f8095;
  font-size: 8px;
  letter-spacing: -0.02em;
}

.gantt-month {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 4px 2px;
  border-right: 1px solid rgba(35, 50, 68, 0.08);
  color: #5f7289;
  font-size: 10px;
  font-weight: 700;
  text-transform: lowercase;
}

.chart-side {
  min-height: 202px;
}

.top-prefix-legend {
  margin: 0 0 8px 78px;
}

.prefix-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 7px;
  border-radius: 999px;
  background: #f5f8fc;
  color: #5f7289;
  font-size: 10px;
}

.prefix-chip i {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  display: inline-block;
}

.chart-track,
.gantt-track {
  position: relative;
  background: linear-gradient(90deg, rgba(35, 50, 68, 0.05) 1px, transparent 1px);
  background-size: var(--day-width) 100%;
}

.chart-track { min-height: 202px; }

.chart-line-overlay {
  position: absolute;
  left: 0;
  bottom: 18px;
  width: calc(var(--day-count) * var(--day-width));
  height: 180px;
  pointer-events: none;
  z-index: 2;
}

.chart-cumulative-line {
  fill: none;
  stroke: #111111;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chart-cumulative-label {
  position: absolute;
  transform: translateX(-50%);
  font-size: 9px;
  font-weight: 700;
  color: #111111;
  white-space: nowrap;
  pointer-events: none;
  z-index: 3;
}

.chart-group {
  position: absolute;
  bottom: 8px;
  width: max(var(--day-width), 18px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}

.chart-total {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  width: max(calc(var(--day-width) - 1px), 16px);
  height: 180px;
  gap: 2px;
}

.chart-total-label {
  font-size: 7px;
  line-height: 1;
  color: #56697f;
  white-space: nowrap;
}

.chart-total-bar-wrap {
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.chart-total-bar {
  display: flex;
  flex-direction: column-reverse;
  width: 100%;
  height: 100%;
  border-radius: 3px 3px 0 0;
  overflow: hidden;
  background: rgba(47, 128, 255, 0.06);
}

.chart-segment {
  min-height: 2px;
}

.chart-zeroes {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 2px;
  max-width: 24px;
}

.summary-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #dd4c4c;
}

.summary-dot.ppd {
  background: #2f67ec;
}

.today-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #e53935;
  z-index: 2;
  pointer-events: none;
}

.gantt-track {
  min-height: calc(var(--lane-count) * var(--lane-height));
}

.gantt-row {
  align-items: stretch;
}

.gantt-row + .gantt-row .gantt-brigade,
.gantt-row + .gantt-row .gantt-track {
  box-shadow: inset 0 1px 0 rgba(35, 50, 68, 0.16);
}

.gantt-drop-grid {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: repeat(var(--day-count), var(--day-width));
}

.gantt-drop-cell.editable:hover {
  background: rgba(47, 128, 255, 0.08);
}

.gantt-brigade {
  min-height: calc(var(--lane-count) * var(--lane-height));
  align-items: flex-start;
  font-size: 11px;
  line-height: 1.05;
  word-break: break-word;
  padding-top: 0;
  padding-bottom: 0;
}

.gantt-bar {
  position: absolute;
  min-height: 12px;
  padding: 0 4px;
  border-radius: 4px;
  color: #fff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
  border: 2px solid rgba(20, 30, 44, 0.28);
  cursor: grab;
  overflow: visible;
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.gantt-bar.readonly { cursor: default; }
.gantt-bar strong { font-size: 10px; }
.gantt-bar span { font-size: 9px; }

.gantt-tooltip {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 4px);
  transform: translateX(-50%);
  max-width: 180px;
  padding: 4px 6px;
  border-radius: 6px;
  background: rgba(19, 27, 38, 0.92);
  color: #fff;
  font-size: 10px;
  line-height: 1.2;
  white-space: normal;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  z-index: 5;
}

.gantt-bar:hover .gantt-tooltip { opacity: 1; }

.zoom-strip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  color: #6d7f94;
  font-size: 11px;
}

.zoom-strip-row {
  align-items: center;
  justify-content: center;
  width: 100%;
  flex-wrap: nowrap;
  overflow-x: auto;
}

.zoom-strip-row-secondary {
  justify-content: center;
}

.control-inline,
.toggle-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  color: #5e7187;
}

.control-inline strong {
  font-size: 10px;
  color: #203044;
}

.compact-select select {
  min-height: 24px;
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 11px;
  min-width: 100px;
}

.toggle-inline input {
  margin: 0;
}

.toggle-inline-ppd {
  gap: 3px;
}

.empty-state {
  color: #5b6b7d;
  font-size: 18px;
}

@media (max-width: 1280px) {
  .source-actions,
  .module-grid.two-wide,
  .module-grid.three-wide,
  .form-grid,
  .detail-summary,
  .info-cards,
  .stats-grid,
  .decline-split {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 980px) {
  .app-shell {
    grid-template-columns: 92px minmax(0, 1fr);
  }

  .sidebar {
    width: 92px;
  }

  .brand,
  .brand-subtitle,
  .sidebar-note,
  .nav-item span:last-child {
    display: none;
  }

  .main-area {
    padding: 16px 14px 18px;
  }

  .topbar h1 {
    font-size: 28px;
  }

  .gantt-grid {
    grid-template-columns: 64px repeat(var(--day-count), var(--day-width));
  }

  .compact-save-panel {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
