<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8010/api'
const PLANNER_CHART_HEIGHT = 180
const PRODUCTION_CHART_HEIGHT = 260
const PRODUCTION_CHART_WIDTH = 1280
const PRODUCTION_CHART_LEFT_PADDING = 72
const PRODUCTION_CHART_RIGHT_PADDING = 72
const PRODUCTION_CHART_TOP_PADDING = 18
const PRODUCTION_CHART_BOTTOM_PADDING = 54
const PRODUCTION_TIME_MODES = [
  { key: 'day', label: 'День' },
  { key: 'month', label: 'Месяц' },
  { key: 'year', label: 'Год' },
]
const PRODUCTION_METRICS = [
  { key: 'oil', label: 'Нефть', unit: 'т' },
  { key: 'liquid', label: 'Жидкость', unit: 'т' },
  { key: 'gas', label: 'Газ', unit: 'м3' },
]
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
const FRONTEND_MAPPING_HINTS = {
  well: ['скв', 'скваж', 'well'],
  area: ['участок', 'area'],
  lu: ['участок недр', 'лу', 'lu'],
  sloy: ['слой', 'пласт', 'sloy'],
  well_pad: ['куст', 'wellpad', 'well_pad'],
  brigade: ['бригада', 'brigade'],
  fund_type: ['вид фонда', 'тип фонда', 'fund type'],
  start_date: ['дата начала', 'начало', 'start'],
  end_date: ['заверш', 'оконч', 'конец', 'end'],
  planned_work: ['планируемый объем работ', 'планируемый объём работ', 'объем работ', 'объём работ', 'мероприят'],
  increment: ['qн', 'прирост нефти', 'дебит нефти', 'oil increment'],
  liquid_increment: ['прирост жидкости', 'прирост жидк', 'liquid increment', 'qж'],
  gas_increment: ['прирост газа', 'дебит газа', 'gas increment', 'qг'],
  gor_change: ['газовый фактор', 'gor', 'изменение gor'],
  oil_rate: ['дебит нефти', 'oil rate', 'qн'],
  gas_rate: ['дебит газа', 'gas rate', 'qг'],
  liquid_rate: ['дебит жидкости', 'liquid rate', 'qж'],
  watercut: ['обводнен', 'watercut'],
  gor: ['газовый фактор', 'gor', 'гф'],
  cumulative_oil: ['накоп', 'добыча нефти'],
  cumulative_gas: ['накоп', 'добыча газа'],
  niz: ['низ', 'извлекаемых запасов'],
  gtm_type: ['тип гтм', 'gtm type', 'гтм'],
  duration_days: ['длитель', 'продолжительность', 'duration'],
  object_name: ['объект', 'наименование объекта'],
  object_type: ['тип объекта'],
  commissioning_date: ['дата ввода', 'ввод'],
  capacity_oil: ['мощн', 'нефть'],
  capacity_gas: ['мощн', 'газ'],
  capacity_liquid: ['мощн', 'жидк'],
  capacity_water: ['мощн', 'вода'],
  connection_well: ['связанная скважина', 'скв'],
  parent_object: ['родител', 'parent'],
}
const REQUIRED_MAPPING_FIELDS = {
  wells: ['well', 'liquid_rate'],
  gtm: ['well', 'planned_work', 'start_date'],
  infrastructure: ['object_name', 'object_type'],
  external_krs_schedule: ['brigade', 'well', 'start_date', 'end_date', 'planned_work'],
}
const ACTIVE_SCENARIO_STORAGE_KEY = 'worknotover.activeScenarioId'

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

const yearStartIso = (value) => {
  const date = parseIsoDate(value)
  if (!date) return value
  date.setUTCMonth(0, 1)
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
const formatShortDayTick = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit' }).format(parsed) : ''
}
const formatShortMonthTick = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { month: 'short', year: '2-digit' }).format(parsed).replace('.', '') : ''
}

const bucketKeyForProductionMode = (value, mode) => {
  if (mode === 'month') return monthStartIso(value)
  if (mode === 'year') return yearStartIso(value)
  return String(value || '')
}

const formatProductionBucketLabel = (value, mode) => {
  if (mode === 'month') return formatMonthLong(value)
  if (mode === 'year') {
    const parsed = parseIsoDate(value)
    return parsed ? String(parsed.getUTCFullYear()) : '—'
  }
  return formatDateCell(value)
}

const productionMetricField = (metric) => ({
  oil: 'oil_rate',
  liquid: 'liquid_rate',
  gas: 'gas_rate',
}[metric] || 'oil_rate')

const productionMetricTotalField = (metric) => ({
  oil: 'total_oil',
  liquid: 'total_liquid',
  gas: 'total_gas',
}[metric] || 'total_oil')

const getProductionPointMetricValue = (point, metric) => Number(point?.[productionMetricField(metric)] || 0)
const getProductionWellMetricTotal = (well, metric) => Number(well?.[productionMetricTotalField(metric)] || 0)

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
const createEconomicsCostRow = () => ({ id: uniqueId('economics-cost'), gtm_type: '', cost: '' })
const createFailureRow = () => ({ id: uniqueId('failure'), scope_type: 'LU', lu_id: '', sloy_id: '', coefficient: '' })
const createDurationRow = () => ({ id: uniqueId('duration'), gtm_type: '', duration_days: '' })
const createBrigadeRow = () => ({ id: uniqueId('brigade'), lu_id: '', month_date: monthStartIso(isoToday()), brigade_count: '' })
const hasFilledValue = (value) => value !== '' && value !== null && value !== undefined
const hasFilledText = (value) => String(value ?? '').trim() !== ''
const resolveTouchedStatus = (entries, isTouched, isValid) => {
  const touchedEntries = entries.filter((entry) => isTouched(entry))
  if (!touchedEntries.length) return 'empty'
  return touchedEntries.every((entry) => isValid(entry)) ? 'ready' : 'partial'
}
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
const formatScenarioWindow = (scenario) => {
  if (!scenario?.forecast_start_date && !scenario?.forecast_end_date) return '—'
  return `${formatDateCell(scenario?.forecast_start_date)} — ${formatDateCell(scenario?.forecast_end_date)}`
}
const scenarioSourceTypeLabel = (sourceType) => {
  if (sourceType === 'planner_manual_edit') return 'Planner revision'
  if (sourceType === 'optimized_krs') return 'Оптимизированный КРС'
  return 'Исходный сценарий'
}
const scenarioOriginLabel = (scenario) => {
  if (scenario?.source_type === 'planner_manual_edit') return 'Создан на основе planner revision'
  if (scenario?.metadata?.scenario_source_mode === 'existing_krs' || scenario?.context?.external_krs_schedule_dataset) {
    return 'Создан на основе внешнего графика КРС'
  }
  return 'Создан пользователем'
}
const scenarioHasPlannerVersion = (scenario) => Boolean(
  scenario?.source_type === 'planner_manual_edit'
  || scenario?.metadata?.planner_revision_id
  || scenario?.metadata?.planner_version_id,
)
const normalizeHeaderText = (value) => String(value || '')
  .toLowerCase()
  .replaceAll('ё', 'е')
  .replace(/[^a-zа-я0-9]+/gi, ' ')
  .trim()

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
const currentSection = ref('scenarios')
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
const uploadInputRef = ref(null)
const showMappingModal = ref(false)
const showPlannerPublishModal = ref(false)
const plannerPublishScenarioName = ref('')

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
const economicsCostRows = ref([createEconomicsCostRow()])
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
const activeCanvasNode = ref('scenario')
const infrastructureMetric = ref('liquid')
const selectedInfrastructureRowKey = ref('infra:total')
const krsInspectorTab = ref('brigades')
const expandedWellsKeys = ref([])
const expandedGtmKeys = ref([])
const expandedInfrastructureKeys = ref([])

const selectedScenarioId = ref(typeof window !== 'undefined' ? (window.localStorage.getItem(ACTIVE_SCENARIO_STORAGE_KEY) || '') : '')
const scenarioSourceMode = ref('new_krs')
const scenarioDetail = ref(null)
const pureBaseScenarioDetail = ref(null)
const expandedProductionKeys = ref([])
const selectedProductionKeys = ref([])
const productionTimeMode = ref('month')
const productionMetric = ref('oil')
const hoveredProductionBucketDate = ref('')

const plannerDatasetReference = ref(null)
const plannerVersionName = ref('')
const plannerRevisions = ref([])
const selectedPlannerRevisionId = ref('')
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
const availableColumnNames = computed(() => availableColumns.value.map((column) => column.name))
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
const requiredMappingFields = computed(() => new Set(REQUIRED_MAPPING_FIELDS[selectedUploadSourceKind.value] || []))
const mappingFieldsOrdered = computed(() => {
  const fields = SOURCE_KIND_META[selectedUploadSourceKind.value]?.fields || []
  return [...fields].sort((left, right) => {
    const leftRequired = requiredMappingFields.value.has(left)
    const rightRequired = requiredMappingFields.value.has(right)
    if (leftRequired === rightRequired) return 0
    return leftRequired ? -1 : 1
  })
})
const mappingSuggestionRows = computed(() => mappingFieldsOrdered.value.map((fieldName) => ({
  fieldName,
  label: MAPPING_LABELS[fieldName],
  required: requiredMappingFields.value.has(fieldName),
  selectedColumn: normalizeColumns[fieldName],
})))
const activeReservoirConfig = computed(() => reservoirConfigs.value.find((item) => item.config_id === activeReservoirConfigId.value) || reservoirConfigs.value[0] || null)
const isPureBaseScenarioRecord = (scenario) => scenario?.metadata?.scenario_role === 'pure_base'
const groupedScenarios = computed(() => [...scenarios.value].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')))
const userVisibleScenarios = computed(() => groupedScenarios.value.filter((item) => !isPureBaseScenarioRecord(item)))
const selectedScenarioSummary = computed(() => userVisibleScenarios.value.find((item) => item.scenario_id === selectedScenarioId.value) || null)
const selectedScenarioValidation = computed(() => (
  scenarioDetail.value?.input_validation
  || selectedScenarioSummary.value?.input_validation
  || null
))
const selectedManualInputSetSummary = computed(() => manualInputSets.value.find((item) => item.reference.manual_input_set_id === selectedManualInputSetId.value) || null)
const isPlannerDerivedScenario = computed(() => Boolean(
  selectedScenarioSummary.value?.source_type === 'planner_manual_edit'
  || selectedScenarioSummary.value?.metadata?.planner_revision_id
))
const plannerRevisionSourceScenarioId = computed(() => selectedScenarioSummary.value?.parent_scenario_id || selectedScenarioId.value || '')
const scenarioFlowMode = computed(() => {
  if (scenarioSourceMode.value === 'planner') return 'planner'
  if (isPlannerDerivedScenario.value) return 'planner'
  return scenarioSourceMode.value === 'existing_krs' ? 'external' : 'generated'
})
const scenarioFlowModeLabel = computed(() => {
  if (scenarioFlowMode.value === 'planner') return 'Полученный из Planner'
  if (scenarioFlowMode.value === 'external') return 'Внешний график'
  return 'Сформировать график'
})
const sourceFlowReady = computed(() => ({
  external: Boolean(selectedDatasets.external_krs_schedule),
  generated: scenarioFlowMode.value === 'generated',
  planner: isPlannerDerivedScenario.value || plannerRevisions.value.length > 0,
}))
const selectedPlannerRevision = computed(() => (
  plannerRevisions.value.find((item) => item.revision_id === selectedPlannerRevisionId.value) || null
))
const selectedScenarioPlannerRevisionId = computed(() => (
  scenarioDetail.value?.scenario?.metadata?.planner_revision_id
  || selectedScenarioSummary.value?.metadata?.planner_revision_id
  || ''
))
const selectedScenarioExternalKrsReference = computed(() => (
  scenarioDetail.value?.context?.external_krs_schedule_dataset
  || selectedScenarioSummary.value?.context?.external_krs_schedule_dataset
  || null
))
const plannerHasBoundSource = computed(() => Boolean(
  selectedScenarioPlannerRevisionId.value || selectedScenarioExternalKrsReference.value,
))
const plannerSourceLabel = computed(() => {
  if (selectedScenarioPlannerRevisionId.value) return 'Planner revision'
  if (selectedScenarioExternalKrsReference.value) return 'Внешний график КРС'
  if (scenarioFlowMode.value === 'generated') return 'График ещё не сформирован'
  return 'Источник не привязан'
})
const derivedScenarioForSelectedRevision = computed(() => {
  if (!selectedPlannerRevisionId.value) return null
  return userVisibleScenarios.value.find((item) => item.metadata?.planner_revision_id === selectedPlannerRevisionId.value) || null
})
const plannerDerivedScenarioMap = computed(() => Object.fromEntries(
  userVisibleScenarios.value
    .filter((item) => item.metadata?.planner_revision_id)
    .map((item) => [item.metadata.planner_revision_id, item]),
))
const scenarioContextStatus = computed(() => ({
  wells: selectedScenarioValidation.value?.wells?.state || (selectedDatasets.wells ? 'ready' : 'empty'),
  gtm: selectedScenarioValidation.value?.gtm?.state || (selectedDatasets.gtm ? 'ready' : 'empty'),
  infrastructure: selectedScenarioValidation.value?.infrastructure?.state || (selectedDatasets.infrastructure ? 'ready' : 'empty'),
  manual_input: selectedScenarioValidation.value?.manual_input_set?.state || (selectedManualInputSetId.value ? 'ready' : 'empty'),
  external_krs_schedule: scenarioFlowMode.value === 'external'
    ? (selectedScenarioValidation.value?.external_krs_schedule?.state || (selectedDatasets.external_krs_schedule ? 'ready' : 'empty'))
    : 'ready',
}))
const reservoirInputStatus = computed(() => resolveTouchedStatus(
  reservoirConfigs.value,
  (config) => Boolean(
    hasFilledText(config.lu_id)
    || hasFilledText(config.sloy_id)
    || (config.displacement_rows || []).some((row) => hasFilledValue(row.NIZ))
  ),
  (config) => Boolean(
    (hasFilledText(config.lu_id) || hasFilledText(config.sloy_id))
    && (config.displacement_rows || []).some((row) => hasFilledValue(row.NIZ))
  ),
))
const economicsInputStatus = computed(() => {
  const rowStatus = resolveTouchedStatus(
    economicsRows.value,
    (row) => hasFilledText(row.lu_id) || hasFilledValue(row.net_back),
    (row) => hasFilledText(row.lu_id) && hasFilledValue(row.net_back),
  )
  const costStatus = resolveTouchedStatus(
    economicsCostRows.value,
    (row) => hasFilledText(row.gtm_type) || hasFilledValue(row.cost),
    (row) => hasFilledText(row.gtm_type) && hasFilledValue(row.cost),
  )
  if (rowStatus === 'partial' || costStatus === 'partial') return 'partial'
  if (rowStatus === 'ready' || costStatus === 'ready') return 'ready'
  return 'empty'
})
const krsInputStatus = computed(() => {
  const brigadeStatus = resolveTouchedStatus(
    brigadeCapacityRows.value,
    (row) => hasFilledText(row.lu_id) || hasFilledValue(row.brigade_count),
    (row) => hasFilledText(row.lu_id) && hasFilledText(row.month_date) && hasFilledValue(row.brigade_count),
  )
  const failureStatus = resolveTouchedStatus(
    failureRows.value,
    (row) => hasFilledValue(row.coefficient) || hasFilledText(row.lu_id) || hasFilledText(row.sloy_id),
    (row) => hasFilledValue(row.coefficient) && (row.scope_type === 'SLOY' ? hasFilledText(row.sloy_id) : hasFilledText(row.lu_id)),
  )
  const durationStatus = resolveTouchedStatus(
    durationRows.value,
    (row) => hasFilledText(row.gtm_type) || hasFilledValue(row.duration_days),
    (row) => hasFilledText(row.gtm_type) && hasFilledValue(row.duration_days),
  )
  if (brigadeStatus === 'partial' || failureStatus === 'partial' || durationStatus === 'partial') return 'partial'
  if (brigadeStatus === 'ready' || failureStatus === 'ready' || durationStatus === 'ready') return 'ready'
  return 'empty'
})
const inputNodeStatuses = computed(() => ({
  wells: scenarioContextStatus.value.wells,
  gtm: scenarioContextStatus.value.gtm,
  infrastructure: scenarioContextStatus.value.infrastructure,
  reservoir: reservoirInputStatus.value,
  economics: economicsInputStatus.value,
  krs: krsInputStatus.value,
}))
const scenarioBlockingIssue = computed(() => selectedScenarioValidation.value?.issues?.[0] || '')
const canCalculateScenario = computed(() => {
  if (!selectedScenarioId.value) return false
  if (selectedScenarioValidation.value) {
    return Boolean(selectedScenarioValidation.value.is_forecast_ready)
  }
  return Boolean(
    scenarioContextStatus.value.wells === 'ready'
    && scenarioContextStatus.value.gtm === 'ready'
    && scenarioContextStatus.value.manual_input === 'ready'
    && scenarioContextStatus.value.external_krs_schedule === 'ready'
  )
})
const scenarioReadiness = computed(() => {
  const selectedScenario = selectedScenarioSummary.value
  const hasScenario = Boolean(selectedScenarioId.value)
  const hasSource = scenarioFlowMode.value === 'external'
    ? scenarioContextStatus.value.external_krs_schedule === 'ready'
      : scenarioFlowMode.value === 'planner'
        ? (isPlannerDerivedScenario.value || plannerRevisions.value.length > 0)
        : true
  const hasInputs = Boolean(
    scenarioContextStatus.value.wells === 'ready'
    && scenarioContextStatus.value.gtm === 'ready'
    && scenarioContextStatus.value.manual_input === 'ready'
    && (scenarioFlowMode.value !== 'external' || scenarioContextStatus.value.external_krs_schedule === 'ready'),
  )
  const hasResult = Boolean(scenarioDetail.value?.production_summary)
  const isPlannerDerived = isPlannerDerivedScenario.value
  const hasPlannerVersion = Boolean(activeVersion.value)
  const hasDerivedScenario = isPlannerDerived || userVisibleScenarios.value.some((item) => (
    item.parent_scenario_id === selectedScenarioId.value && item.source_type === 'planner_manual_edit'
  ))
  return {
    hasScenario,
    hasSource,
    hasInputs,
    hasResult,
    isPlannerDerived,
    hasPlannerVersion,
    hasDerivedScenario,
  }
})
const workflowSteps = computed(() => {
  const selectedScenario = selectedScenarioSummary.value
  const {
    hasScenario,
    hasSource,
    hasInputs,
    hasResult,
    isPlannerDerived,
    hasPlannerVersion,
  } = scenarioReadiness.value
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
      description: scenarioFlowMode.value === 'planner'
        ? 'Источник графика получен из Planner revision.'
        : scenarioFlowMode.value === 'external'
          ? (selectedDatasets.external_krs_schedule?.name || 'Нужно привязать imported KRS dataset.')
          : 'График будет сформирован в расчетно-оптимизационном контуре.',
      ready: hasSource,
    },
    {
      key: 'inputs',
      label: '3. Входы сценария',
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
      ready: isPlannerDerived || hasPlannerVersion,
    },
  ]
})
const pageTitle = computed(() => {
  if (currentSection.value === 'planner') return 'Планировщик КРС'
  if (currentSection.value === 'production') return 'Добыча'
  return 'Сценарии'
})
const pageSubtitle = computed(() => {
  if (currentSection.value === 'planner') return 'Отдельный модуль Planner. Открывает импортированные графики КРС, ведет версии и выгружает измененный план.'
  if (currentSection.value === 'production') return 'Просмотр сохраненных сценариев Module B с накопительной диаграммой нефти и иерархической фильтрацией по LU, SLOY, кусту и скважине.'
  return 'Scenario-first workspace: сценарный контекст, входные datasets, manual inputs, запуск Module B и подготовка ядра Module D.'
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

const datasetRowsFromReference = (reference) => {
  if (!reference) return []
  const payload = datasetDetails[datasetReferenceKey(reference)]?.normalized_payload
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.schedule?.items)) return payload.schedule.items
  return []
}

const pickRowValue = (row, keys) => {
  for (const key of keys) {
    const value = row?.[key]
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      return String(value)
    }
  }
  return ''
}

const pickNumberValue = (row, keys) => {
  for (const key of keys) {
    const value = row?.[key]
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      const parsed = Number(value)
      if (!Number.isNaN(parsed)) return parsed
    }
  }
  return 0
}

const buildVisibleHierarchyRows = (rows, expandedKeys) => {
  const rowMap = new Map(rows.map((row) => [row.key, row]))
  const expanded = new Set(expandedKeys)
  return rows.filter((row) => {
    let parentKey = row.parentKey
    while (parentKey) {
      if (!expanded.has(parentKey)) return false
      parentKey = rowMap.get(parentKey)?.parentKey
    }
    return true
  })
}

const buildGroupedHierarchyRows = (rows, metricBuilder) => {
  const totals = metricBuilder()
  const luMap = new Map()
  rows.forEach((row) => {
    const luId = pickRowValue(row, ['lu_id', 'lu']) || 'Без LU'
    const padId = pickRowValue(row, ['well_pad_id', 'well_pad']) || 'Без куста'
    const wellId = pickRowValue(row, ['well_id', 'well', 'connection_well']) || 'Без скважины'
    if (!luMap.has(luId)) {
      luMap.set(luId, { key: `lu:${luId}`, depth: 1, label: luId, metrics: metricBuilder(), children: new Map() })
    }
    const luNode = luMap.get(luId)
    if (!luNode.children.has(padId)) {
      luNode.children.set(padId, { key: `pad:${luId}:${padId}`, depth: 2, label: padId, metrics: metricBuilder(), children: new Map() })
    }
    const padNode = luNode.children.get(padId)
    if (!padNode.children.has(wellId)) {
      padNode.children.set(wellId, { key: `well:${luId}:${padId}:${wellId}`, depth: 3, label: wellId, metrics: metricBuilder(), children: null })
    }
    const wellNode = padNode.children.get(wellId)
    const rowMetrics = metricBuilder(row)
    Object.keys(rowMetrics).forEach((key) => {
      totals[key] += rowMetrics[key]
      luNode.metrics[key] += rowMetrics[key]
      padNode.metrics[key] += rowMetrics[key]
      wellNode.metrics[key] += rowMetrics[key]
    })
  })
  const result = [{ key: 'total', depth: 0, label: 'Итого', metrics: totals, nodeType: 'total', parentKey: null, children: [] }]
  ;[...luMap.values()]
    .sort((left, right) => left.label.localeCompare(right.label, 'ru'))
    .forEach((luNode) => {
      const padKeys = [...luNode.children.values()].map((padNode) => padNode.key)
      result.push({ key: luNode.key, depth: luNode.depth, label: luNode.label, metrics: luNode.metrics, nodeType: 'lu', parentKey: 'total', children: padKeys })
      ;[...luNode.children.values()]
        .sort((left, right) => left.label.localeCompare(right.label, 'ru'))
        .forEach((padNode) => {
          const wellKeys = [...padNode.children.values()].map((wellNode) => wellNode.key)
          result.push({ key: padNode.key, depth: padNode.depth, label: padNode.label, metrics: padNode.metrics, nodeType: 'pad', parentKey: luNode.key, children: wellKeys })
          ;[...padNode.children.values()]
            .sort((left, right) => left.label.localeCompare(right.label, 'ru'))
            .forEach((wellNode) => {
              result.push({ key: wellNode.key, depth: wellNode.depth, label: wellNode.label, metrics: wellNode.metrics, nodeType: 'well', parentKey: padNode.key, children: [] })
            })
        })
    })
  result[0].children = result.filter((row) => row.parentKey === 'total').map((row) => row.key)
  return result
}

const wellsDatasetRows = computed(() => datasetRowsFromReference(selectedDatasets.wells))
const gtmDatasetRows = computed(() => datasetRowsFromReference(selectedDatasets.gtm))
const infrastructureDatasetRows = computed(() => datasetRowsFromReference(selectedDatasets.infrastructure))

const wellsHierarchyRows = computed(() => buildGroupedHierarchyRows(
  wellsDatasetRows.value,
  (row) => row
    ? { count: 1, oil: pickNumberValue(row, ['current_oil_rate', 'oil_rate']), liquid: pickNumberValue(row, ['current_liquid_rate', 'liquid_rate']), gas: pickNumberValue(row, ['current_gas_rate', 'gas_rate']) }
    : { count: 0, oil: 0, liquid: 0, gas: 0 },
))
const visibleWellsHierarchyRows = computed(() => buildVisibleHierarchyRows(wellsHierarchyRows.value, expandedWellsKeys.value))

const gtmHierarchyRows = computed(() => buildGroupedHierarchyRows(
  gtmDatasetRows.value,
  (row) => row
    ? {
      count: 1,
      oil: pickNumberValue(row, ['oil_increment', 'expected_oil_increment', 'increment']),
      liquid: pickNumberValue(row, ['liquid_increment', 'expected_liquid_increment']),
      gas: pickNumberValue(row, ['gas_increment', 'expected_gas_increment']),
    }
    : { count: 0, oil: 0, liquid: 0, gas: 0 },
))
const visibleGtmHierarchyRows = computed(() => buildVisibleHierarchyRows(gtmHierarchyRows.value, expandedGtmKeys.value))

const reservoirChartPoints = computed(() => {
  const config = activeReservoirConfig.value
  if (!config) return []
  return config.displacement_rows
    .filter((row) => row.NIZ !== '' && row.NIZ !== null && row.NIZ !== undefined)
    .map((row) => ({ watercut: Number(row.watercut), NIZ: Number(row.NIZ) }))
    .filter((row) => !Number.isNaN(row.NIZ))
})

const reservoirChartMax = computed(() => Math.max(...reservoirChartPoints.value.map((item) => item.NIZ), 1))
const reservoirChartPath = computed(() => {
  if (!reservoirChartPoints.value.length) return ''
  return reservoirChartPoints.value
    .map((item, index) => {
      const x = reservoirChartPoints.value.length === 1 ? 8 : 8 + (index / (reservoirChartPoints.value.length - 1)) * 224
      const y = 92 - (item.NIZ / reservoirChartMax.value) * 76
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
})

const buildMiniSeriesPath = (points, valueKey, width = 224, height = 96, leftPad = 8, bottomPad = 12) => {
  if (!points.length) return ''
  const maxValue = Math.max(...points.map((point) => Number(point[valueKey] || 0)), 1)
  return points
    .map((point, index) => {
      const x = points.length === 1 ? leftPad : leftPad + (index / (points.length - 1)) * (width - leftPad * 2)
      const y = height - bottomPad - ((Number(point[valueKey] || 0) / maxValue) * (height - bottomPad - 8))
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
}

const baseDeclineChartPoints = computed(() => (activeReservoirConfig.value?.base_decline_rows || []).map((row) => ({
  month_index: row.month_index,
  liquid_decline_factor: Number(row.liquid_decline_factor || 0),
})))
const newWellsDeclineChartPoints = computed(() => (activeReservoirConfig.value?.new_wells_decline_rows || []).map((row) => ({
  month_index: row.month_index,
  liquid_decline_factor: Number(row.liquid_decline_factor || 0),
})))
const baseDeclineChartPath = computed(() => buildMiniSeriesPath(baseDeclineChartPoints.value, 'liquid_decline_factor'))
const newWellsDeclineChartPath = computed(() => buildMiniSeriesPath(newWellsDeclineChartPoints.value, 'liquid_decline_factor'))

const infrastructureTreeRows = computed(() => {
  const objects = new Map()
  const metricFromRow = (row) => ({
    oil: pickNumberValue(row, ['capacity_oil']),
    liquid: pickNumberValue(row, ['capacity_liquid']),
    gas: pickNumberValue(row, ['capacity_gas']),
  })
  infrastructureDatasetRows.value.forEach((row) => {
    const objectName = pickRowValue(row, ['object_name'])
    if (!objectName) return
    if (!objects.has(objectName)) {
      objects.set(objectName, {
        key: `object:${objectName}`,
        name: objectName,
        type: pickRowValue(row, ['object_type']) || 'Объект',
        parent: pickRowValue(row, ['parent_object']),
        metrics: metricFromRow(row),
        children: [],
        pads: new Map(),
      })
    }
    const node = objects.get(objectName)
    const padId = pickRowValue(row, ['well_pad_id', 'well_pad'])
    const wellId = pickRowValue(row, ['connection_well', 'well_id', 'well'])
    if (padId) {
      if (!node.pads.has(padId)) {
        node.pads.set(padId, { key: `pad:${objectName}:${padId}`, name: padId, wells: new Set(), metrics: { oil: 0, liquid: 0, gas: 0 } })
      }
      const pad = node.pads.get(padId)
      if (wellId) pad.wells.add(wellId)
    }
  })

  const rootsByType = new Map()
  objects.forEach((node) => {
    if (node.parent && objects.has(node.parent)) {
      objects.get(node.parent).children.push(node)
      return
    }
    if (!rootsByType.has(node.type)) rootsByType.set(node.type, [])
    rootsByType.get(node.type).push(node)
  })

  const total = { oil: 0, liquid: 0, gas: 0 }
  const visit = (node, depth) => {
    const childMetrics = { ...node.metrics }
    const childRows = []
    node.children
      .sort((left, right) => left.name.localeCompare(right.name, 'ru'))
      .forEach((child) => {
        const { metrics, rows } = visit(child, depth + 1)
        childMetrics.oil += metrics.oil
        childMetrics.liquid += metrics.liquid
        childMetrics.gas += metrics.gas
        childRows.push(...rows)
      })
    const rows = [{
      key: node.key,
      depth,
      label: node.name,
      nodeType: 'object',
      parentKey: node.parent ? `object:${node.parent}` : `type:${node.type}`,
      children: node.children.map((child) => child.key),
      metrics: childMetrics,
    }]
    rows.push(...childRows)
    ;[...node.pads.values()]
      .sort((left, right) => left.name.localeCompare(right.name, 'ru'))
      .forEach((pad) => {
        rows[0].children.push(pad.key)
        rows.push({ key: pad.key, depth: depth + 1, label: pad.name, nodeType: 'pad', parentKey: node.key, children: [], metrics: childMetrics })
        ;[...pad.wells.values()].sort((left, right) => left.localeCompare(right, 'ru')).forEach((well) => {
          const wellKey = `${pad.key}:${well}`
          rows.find((row) => row.key === pad.key)?.children.push(wellKey)
          rows.push({ key: wellKey, depth: depth + 2, label: well, nodeType: 'well', parentKey: pad.key, children: [], metrics: childMetrics })
        })
      })
    return { metrics: childMetrics, rows }
  }

  const rows = [{ key: 'infra:total', depth: 0, label: 'Итого', nodeType: 'total', parentKey: null, children: [], metrics: total }]
  rootsByType.forEach((nodes, type) => {
    const typeMetrics = { oil: 0, liquid: 0, gas: 0 }
    const typeRows = []
    nodes
      .sort((left, right) => left.name.localeCompare(right.name, 'ru'))
      .forEach((node) => {
        const { metrics, rows: objectRows } = visit(node, 2)
        typeMetrics.oil += metrics.oil
        typeMetrics.liquid += metrics.liquid
        typeMetrics.gas += metrics.gas
        typeRows.push(...objectRows)
    })
    total.oil += typeMetrics.oil
    total.liquid += typeMetrics.liquid
    total.gas += typeMetrics.gas
    const typeKey = `type:${type}`
    rows[0].children.push(typeKey)
    rows.push({ key: typeKey, depth: 1, label: type, nodeType: 'type', parentKey: 'infra:total', children: nodes.map((node) => node.key), metrics: typeMetrics })
    rows.push(...typeRows)
  })
  rows[0] = { key: 'infra:total', depth: 0, label: 'Итого', nodeType: 'total', parentKey: null, children: rows[0].children, metrics: total }
  return rows
})
const visibleInfrastructureTreeRows = computed(() => buildVisibleHierarchyRows(infrastructureTreeRows.value, expandedInfrastructureKeys.value))

const selectedInfrastructureRow = computed(() => (
  infrastructureTreeRows.value.find((row) => row.key === selectedInfrastructureRowKey.value)
  || infrastructureTreeRows.value[0]
  || null
))

const nodeInspectorTitle = computed(() => {
  switch (activeCanvasNode.value) {
    case 'scenario': return scenarioFlowMode.value === 'external' ? 'Внешний график КРС' : 'Сценарий'
    case 'wells': return 'Wells'
    case 'gtm': return 'ГТМ'
    case 'infrastructure': return 'Infrastructure'
    case 'reservoir': return 'Характеристика вытеснения'
    case 'economics': return 'Экономика'
    case 'krs': return 'KRS ограничения'
    case 'optimizer': return 'Параметры оптимизатора'
    case 'forecast': return 'Forecast'
    default: return 'Сценарий'
  }
})

const productionTree = computed(() => {
  const wells = Array.isArray(scenarioDetail.value?.wells) ? scenarioDetail.value.wells : []
  const bucketOrder = []
  const bucketSet = new Set()
  const ensureBucketOrder = (bucketDate) => {
    if (!bucketSet.has(bucketDate)) {
      bucketSet.add(bucketDate)
      bucketOrder.push(bucketDate)
    }
  }
  const createTreeNode = (payload) => ({
    ...payload,
    totalOil: 0,
    totalLiquid: 0,
    totalGas: 0,
    bucketValues: new Map(),
  })
  const addBucketMetric = (node, bucketDate, point) => {
    ensureBucketOrder(bucketDate)
    if (!node.bucketValues.has(bucketDate)) {
      node.bucketValues.set(bucketDate, { oil: 0, liquid: 0, gas: 0 })
    }
    const bucket = node.bucketValues.get(bucketDate)
    bucket.oil += getProductionPointMetricValue(point, 'oil')
    bucket.liquid += getProductionPointMetricValue(point, 'liquid')
    bucket.gas += getProductionPointMetricValue(point, 'gas')
  }
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
    bucketValues: new Map(),
  }
  const luMap = new Map()
  wells.forEach((well) => {
    const luId = well.lu_id || 'Без LU'
    const sloyId = well.sloy_id || 'Без SLOY'
    const padId = well.well_pad_id || 'Без куста'
    const wellKey = buildWellNodeKey(well)
    let luNode = luMap.get(luId)
    if (!luNode) {
      luNode = createTreeNode({ key: `lu:${luId}`, nodeType: 'lu', depth: 1, label: luId, fundType: null, wellCount: 0, leafKeys: [], children: [] })
      luMap.set(luId, luNode)
      totalNode.children.push(luNode)
    }
    let sloyNode = luNode.children.find((item) => item.label === sloyId)
    if (!sloyNode) {
      sloyNode = createTreeNode({ key: `sloy:${luId}:${sloyId}`, nodeType: 'sloy', depth: 2, label: sloyId, fundType: null, wellCount: 0, leafKeys: [], children: [] })
      luNode.children.push(sloyNode)
    }
    let padNode = sloyNode.children.find((item) => item.label === padId)
    if (!padNode) {
      padNode = createTreeNode({ key: `pad:${luId}:${sloyId}:${padId}`, nodeType: 'pad', depth: 3, label: padId, fundType: null, wellCount: 0, leafKeys: [], children: [] })
      sloyNode.children.push(padNode)
    }
    const leafNode = createTreeNode({
      key: wellKey,
      nodeType: 'well',
      depth: 4,
      label: well.well_name || well.well_id,
      fundType: well.fund_type || null,
      wellCount: 1,
      leafKeys: [wellKey],
      children: [],
    })
    leafNode.totalOil = getProductionWellMetricTotal(well, 'oil')
    leafNode.totalLiquid = getProductionWellMetricTotal(well, 'liquid')
    leafNode.totalGas = getProductionWellMetricTotal(well, 'gas')
    well.points.forEach((point) => {
      const bucketDate = bucketKeyForProductionMode(point.date, productionTimeMode.value)
      ;[totalNode, luNode, sloyNode, padNode, leafNode].forEach((node) => addBucketMetric(node, bucketDate, point))
    })
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
  bucketOrder.sort((left, right) => left.localeCompare(right))
  return { rows, nodeMap, totalNode, bucketOrder }
})
const activeScenarioWells = computed(() => Array.isArray(scenarioDetail.value?.wells) ? scenarioDetail.value.wells : [])
const activeScenarioRole = computed(() => scenarioDetail.value?.scenario?.metadata?.scenario_role || '')
const baseScenarioWells = computed(() => {
  if (activeScenarioRole.value === 'pure_base') {
    return activeScenarioWells.value
  }
  return Array.isArray(pureBaseScenarioDetail.value?.wells) ? pureBaseScenarioDetail.value.wells : []
})
const selectedLeafWellKeys = computed(() => (
  selectedProductionKeys.value.length
    ? new Set(selectedProductionKeys.value.flatMap((key) => productionTree.value.nodeMap.get(key)?.leafKeys || []))
    : new Set(productionTree.value.totalNode.leafKeys)
))
const selectedLeafWells = computed(() => activeScenarioWells.value.filter((well) => selectedLeafWellKeys.value.has(buildWellNodeKey(well))))
const selectedBaseLeafWells = computed(() => baseScenarioWells.value.filter((well) => selectedLeafWellKeys.value.has(buildWellNodeKey(well))))
const productionSeries = computed(() => {
  if (!selectedLeafWells.value.length && !selectedBaseLeafWells.value.length) return []
  const dateMap = new Map()
  const ensureBucket = (bucketDate) => {
    if (!dateMap.has(bucketDate)) {
      dateMap.set(bucketDate, {
        date: bucketDate,
        basePeriod: 0,
        activeBasePeriod: 0,
        gtmPeriod: 0,
        vnsPeriod: 0,
      })
    }
    return dateMap.get(bucketDate)
  }

  selectedBaseLeafWells.value.forEach((well) => {
    well.points.forEach((point) => {
      const bucket = ensureBucket(bucketKeyForProductionMode(point.date, productionTimeMode.value))
      bucket.basePeriod += getProductionPointMetricValue(point, productionMetric.value)
    })
  })

  selectedLeafWells.value.forEach((well) => {
    well.points.forEach((point) => {
      const bucket = ensureBucket(bucketKeyForProductionMode(point.date, productionTimeMode.value))
      const pointMetric = getProductionPointMetricValue(point, productionMetric.value)
      if (String(well.fund_type || '').toLowerCase() === 'new wells') {
        bucket.vnsPeriod += pointMetric
      } else if (activeScenarioRole.value === 'pure_base') {
        bucket.basePeriod += pointMetric
      } else {
        bucket.activeBasePeriod += pointMetric
      }
    })
  })

  const hasLinkedPureBase = activeScenarioRole.value === 'pure_base' || selectedBaseLeafWells.value.length > 0
  const ordered = [...dateMap.values()]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((point) => {
      const basePeriod = hasLinkedPureBase ? point.basePeriod : point.activeBasePeriod
      return {
        ...point,
        basePeriod,
        gtmPeriod: activeScenarioRole.value === 'pure_base' || !hasLinkedPureBase
          ? 0
          : Math.max(point.activeBasePeriod - point.basePeriod, 0),
      }
    })

  let baseCum = 0
  let gtmCum = 0
  let vnsCum = 0
  return ordered.map((point) => {
    baseCum += point.basePeriod
    gtmCum += point.gtmPeriod
    vnsCum += point.vnsPeriod
    const totalPeriod = point.basePeriod + point.gtmPeriod + point.vnsPeriod
    return {
      ...point,
      label: formatProductionBucketLabel(point.date, productionTimeMode.value),
      baseCum,
      gtmCum,
      vnsCum,
      totalPeriod,
      totalCum: baseCum + gtmCum + vnsCum,
    }
  })
})
const productionTableColumns = computed(() => productionTree.value.bucketOrder.map((date) => ({
  key: date,
  date,
  label: productionTimeMode.value === 'day'
    ? formatShortDayTick(date)
    : productionTimeMode.value === 'month'
      ? formatShortMonthTick(date)
      : String(parseIsoDate(date)?.getUTCFullYear() || ''),
  fullLabel: formatProductionBucketLabel(date, productionTimeMode.value),
})))
const productionTableRows = computed(() => productionTree.value.rows.map((row) => ({
  ...row,
  metricTotal: productionMetric.value === 'oil'
    ? row.totalOil
    : productionMetric.value === 'liquid'
      ? row.totalLiquid
      : row.totalGas,
  bucketSeries: productionTableColumns.value.map((column) => row.bucketValues.get(column.date)?.[productionMetric.value] || 0),
})))
const productionChartTitle = computed(() => ({
  day: `Посуточная добыча ${PRODUCTION_METRICS.find((item) => item.key === productionMetric.value)?.label.toLowerCase() || 'нефти'}`,
  month: `Добыча ${PRODUCTION_METRICS.find((item) => item.key === productionMetric.value)?.label.toLowerCase() || 'нефти'} по месяцам`,
  year: `Годовая добыча ${PRODUCTION_METRICS.find((item) => item.key === productionMetric.value)?.label.toLowerCase() || 'нефти'}`,
}[productionTimeMode.value] || 'Добыча'))
const productionChartSubtitle = computed(() => ({
  day: 'Столбцы показывают добычу за сутки. Накопленная добыча отображается линией поверх категорий БАЗА, ГТМ и ВНС.',
  month: 'Столбцы показывают добычу, агрегированную по календарным месяцам. Накопленная добыча отображается линией поверх категорий БАЗА, ГТМ и ВНС.',
  year: 'Столбцы показывают добычу, агрегированную по календарным годам. Накопленная добыча отображается линией поверх категорий БАЗА, ГТМ и ВНС.',
}[productionTimeMode.value] || ''))
const productionBarMax = computed(() => Math.max(...productionSeries.value.map((point) => point.totalPeriod), 1))
const productionCumMax = computed(() => Math.max(...productionSeries.value.map((point) => point.totalCum), 1))
const productionPlotHeight = computed(() => PRODUCTION_CHART_HEIGHT - PRODUCTION_CHART_TOP_PADDING - PRODUCTION_CHART_BOTTOM_PADDING)
const productionPlotWidth = computed(() => PRODUCTION_CHART_WIDTH - PRODUCTION_CHART_LEFT_PADDING - PRODUCTION_CHART_RIGHT_PADDING)
const productionChartBars = computed(() => {
  if (!productionSeries.value.length) return []
  const plotHeight = productionPlotHeight.value
  const bandWidth = productionPlotWidth.value / productionSeries.value.length
  const barWidth = Math.max(10, Math.min(36, bandWidth * 0.62))
  const baselineY = PRODUCTION_CHART_TOP_PADDING + plotHeight

  const scaledHeight = (value) => {
    if (value <= 0 || productionBarMax.value <= 0) return 0
    return Math.max((value / productionBarMax.value) * plotHeight, 1.5)
  }

  return productionSeries.value.map((point, index) => {
    const bandX = PRODUCTION_CHART_LEFT_PADDING + index * bandWidth
    const x = bandX + (bandWidth - barWidth) / 2
    const centerX = x + barWidth / 2
    const baseHeight = scaledHeight(point.basePeriod)
    const gtmHeight = scaledHeight(point.gtmPeriod)
    const vnsHeight = scaledHeight(point.vnsPeriod)
    const baseY = baselineY - baseHeight
    const gtmY = baseY - gtmHeight
    const vnsY = gtmY - vnsHeight

    return {
      ...point,
      bandX,
      bandWidth,
      x,
      width: barWidth,
      centerX,
      baselineY,
      baseHeight,
      gtmHeight,
      vnsHeight,
      baseY,
      gtmY,
      vnsY,
    }
  })
})
const productionCumulativePolyline = computed(() => {
  if (!productionChartBars.value.length || productionCumMax.value <= 0) return ''
  const plotHeight = productionPlotHeight.value
  return productionChartBars.value
    .map((point) => {
      const y = PRODUCTION_CHART_TOP_PADDING + plotHeight - (point.totalCum / productionCumMax.value) * plotHeight
      return `${point.centerX},${y}`
    })
    .join(' ')
})
const productionAxisTicks = computed(() => {
  const tickCount = 5
  return Array.from({ length: tickCount }, (_, index) => {
    const ratio = index / (tickCount - 1)
    const value = productionBarMax.value * (1 - ratio)
    const y = PRODUCTION_CHART_TOP_PADDING + ratio * productionPlotHeight.value
    return { value, y }
  })
})
const productionCumulativeTicks = computed(() => {
  const tickCount = 5
  return Array.from({ length: tickCount }, (_, index) => {
    const ratio = index / (tickCount - 1)
    const value = productionCumMax.value * (1 - ratio)
    const y = PRODUCTION_CHART_TOP_PADDING + ratio * productionPlotHeight.value
    return { value, y }
  })
})
const productionDateTicks = computed(() => {
  const bars = productionChartBars.value
  if (!bars.length) return []
  if (productionTimeMode.value === 'day') {
    return bars
      .filter((point, index) => {
        const parsed = parseIsoDate(point.date)
        if (!parsed) return index === 0 || index === bars.length - 1
        const dayOfMonth = parsed.getUTCDate()
        return index === 0 || index === bars.length - 1 || dayOfMonth === 1 || ((dayOfMonth - 1) % 7 === 0)
      })
      .map((point) => ({ x: point.centerX, label: formatShortDayTick(point.date) }))
  }
  if (productionTimeMode.value === 'month') {
    const step = bars.length > 18 ? 2 : 1
    return bars
      .filter((_, index) => index % step === 0 || index === bars.length - 1)
      .map((point) => ({ x: point.centerX, label: formatShortMonthTick(point.date) }))
  }
  return bars.map((point) => ({
    x: point.centerX,
    label: String(parseIsoDate(point.date)?.getUTCFullYear() || ''),
  }))
})
const productionLabelPoints = computed(() => [])
const hoveredProductionBucket = computed(() => productionChartBars.value.find((point) => point.date === hoveredProductionBucketDate.value) || null)
const productionTooltipStyle = computed(() => {
  if (!hoveredProductionBucket.value) return {}
  const ratio = hoveredProductionBucket.value.centerX / PRODUCTION_CHART_WIDTH
  return { left: `calc(${(ratio * 100).toFixed(3)}% - 76px)` }
})
const selectedProductionSummary = computed(() => selectedLeafWells.value.reduce((acc, well) => {
  acc.totalOil += Number(well.total_oil || 0)
  acc.totalLiquid += Number(well.total_liquid || 0)
  acc.totalGas += Number(well.total_gas || 0)
  return acc
}, { totalOil: 0, totalLiquid: 0, totalGas: 0 }))
const productionChartLegend = computed(() => ([
  { label: 'БАЗА', color: 'rgba(47, 128, 255, 0.78)', kind: 'bar', value: productionSeries.value.at(-1)?.baseCum || 0 },
  { label: 'ГТМ', color: 'rgba(76, 195, 154, 0.78)', kind: 'bar', value: productionSeries.value.at(-1)?.gtmCum || 0 },
  { label: 'ВНС', color: 'rgba(230, 124, 37, 0.8)', kind: 'bar', value: productionSeries.value.at(-1)?.vnsCum || 0 },
  { label: 'Накопленная', color: '#132233', kind: 'line', value: productionSeries.value.at(-1)?.totalCum || 0 },
]))

const resetNormalizeColumns = () => {
  Object.keys(normalizeColumns).forEach((key) => { normalizeColumns[key] = '' })
}

const suggestColumnForField = (fieldName) => {
  const hints = FRONTEND_MAPPING_HINTS[fieldName] || []
  if (!hints.length) return ''
  const match = availableColumnNames.value.find((columnName) => {
    const normalized = normalizeHeaderText(columnName)
    return hints.some((hint) => normalized.includes(normalizeHeaderText(hint)))
  })
  return match || ''
}

const prefillSuggestedMappings = ({ overwrite = false } = {}) => {
  for (const fieldName of SOURCE_KIND_META[selectedUploadSourceKind.value]?.fields || []) {
    if (!overwrite && normalizeColumns[fieldName]) continue
    normalizeColumns[fieldName] = suggestColumnForField(fieldName)
  }
}

const openMappingModalForCurrentFile = ({ overwrite = false } = {}) => {
  if (!inputFile.value?.columns_info?.length) {
    showMessage('Сначала выберите или загрузите Excel.', 'error')
    return
  }
  prefillSuggestedMappings({ overwrite })
  showMappingModal.value = true
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
  if (context.external_krs_schedule_dataset) {
    scenarioSourceMode.value = 'existing_krs'
  } else if (scenarioSourceMode.value !== 'planner') {
    scenarioSourceMode.value = 'new_krs'
  }
}

const buildScenarioRequestPayload = () => ({
  name: optimizerForm.scenario_name.trim(),
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
  const selectedScenario = groupedScenarios.value.find((item) => item.scenario_id === selectedScenarioId.value) || null
  if (selectedScenario && isPureBaseScenarioRecord(selectedScenario) && selectedScenario.parent_scenario_id) {
    selectedScenarioId.value = selectedScenario.parent_scenario_id
    return
  }
  if ((!selectedScenarioId.value || !userVisibleScenarios.value.some((item) => item.scenario_id === selectedScenarioId.value)) && userVisibleScenarios.value.length) {
    selectedScenarioId.value = userVisibleScenarios.value[0].scenario_id
  }
}

const loadPlannerRevisions = async (scenarioId) => {
  if (!scenarioId) {
    plannerRevisions.value = []
    selectedPlannerRevisionId.value = ''
    return
  }
  const response = await request(`/planner/revisions?parent_scenario_id=${encodeURIComponent(scenarioId)}`)
  plannerRevisions.value = await response.json()
  if (!plannerRevisions.value.some((item) => item.revision_id === selectedPlannerRevisionId.value)) {
    selectedPlannerRevisionId.value = plannerRevisions.value[0]?.revision_id || ''
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

const saveScenarioContextAction = async () => {
  if (!selectedScenarioId.value) {
    await createScenario()
    return
  }
  await saveActiveScenarioContext()
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
    await loadScenarioDetail(payload.scenario_id || selectedScenarioId.value)
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
    prefillSuggestedMappings({ overwrite: true })
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
    prefillSuggestedMappings({ overwrite: true })
    showMappingModal.value = true
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
    if (
      selectedScenarioId.value
      && selectedUploadSourceKind.value === 'external_krs_schedule'
      && scenarioSourceMode.value === 'existing_krs'
    ) {
      await saveActiveScenarioContext({ silent: true })
      if (currentSection.value === 'planner') {
        await syncPlannerWithActiveScenario({ silent: true })
      }
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
const addEconomicsCostRow = () => economicsCostRows.value.push(createEconomicsCostRow())
const addBrigadeRow = () => brigadeCapacityRows.value.push(createBrigadeRow())
const addFailureRow = () => failureRows.value.push(createFailureRow())
const addDurationRow = () => durationRows.value.push(createDurationRow())

const syncExpandedHierarchy = (expandedRef, rows) => {
  const expandableKeys = rows.filter((row) => row.children?.length).map((row) => row.key)
  if (!expandableKeys.length) {
    expandedRef.value = []
    return
  }
  if (!expandedRef.value.length) {
    expandedRef.value = [...expandableKeys]
    return
  }
  const next = expandedRef.value.filter((key) => expandableKeys.includes(key))
  if (!next.length) {
    expandedRef.value = [...expandableKeys]
    return
  }
  expandedRef.value = next
}

const toggleHierarchyExpand = (expandedRef, key) => {
  if (expandedRef.value.includes(key)) {
    expandedRef.value = expandedRef.value.filter((item) => item !== key)
    return
  }
  expandedRef.value = [...expandedRef.value, key]
}

const toggleWellsExpand = (key) => toggleHierarchyExpand(expandedWellsKeys, key)
const toggleGtmExpand = (key) => toggleHierarchyExpand(expandedGtmKeys, key)
const toggleInfrastructureExpand = (key) => toggleHierarchyExpand(expandedInfrastructureKeys, key)
const setScenarioFlowSource = (mode) => {
  if (mode === 'external') {
    activeCanvasNode.value = 'scenario'
    scenarioSourceMode.value = 'existing_krs'
    currentInputsTab.value = 'upload'
    selectedUploadSourceKind.value = 'external_krs_schedule'
    return
  }
  if (mode === 'generated') {
    activeCanvasNode.value = 'wells'
    scenarioSourceMode.value = 'new_krs'
    currentInputsTab.value = 'upload'
    selectedUploadSourceKind.value = 'wells'
    return
  }
  activeCanvasNode.value = 'scenario'
  scenarioSourceMode.value = 'planner'
}

const selectCanvasNode = async (nodeKey) => {
  activeCanvasNode.value = nodeKey
  if (nodeKey === 'scenario' && scenarioFlowMode.value === 'external') {
    currentInputsTab.value = 'upload'
    selectedUploadSourceKind.value = 'external_krs_schedule'
    return
  }
  if (nodeKey === 'scenario' && scenarioFlowMode.value === 'planner') {
    return
  }
  if (nodeKey === 'wells') {
    currentInputsTab.value = 'upload'
    selectedUploadSourceKind.value = 'wells'
    if (selectedDatasets.wells) await openDatasetDetail(selectedDatasets.wells)
    return
  }
  if (nodeKey === 'gtm') {
    currentInputsTab.value = 'upload'
    selectedUploadSourceKind.value = 'gtm'
    if (selectedDatasets.gtm) await openDatasetDetail(selectedDatasets.gtm)
    return
  }
  if (nodeKey === 'infrastructure') {
    currentInputsTab.value = 'upload'
    selectedUploadSourceKind.value = 'infrastructure'
    if (selectedDatasets.infrastructure) await openDatasetDetail(selectedDatasets.infrastructure)
    return
  }
}

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
    gtm_costs_by_type: Object.fromEntries(
      economicsCostRows.value
        .filter((item) => item.gtm_type && item.cost !== '')
        .map((item) => [item.gtm_type, Number(item.cost)]),
    ),
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
  const economicsCosts = payload.economics_config?.gtm_costs_by_type || {}
  economicsCostRows.value = Object.keys(economicsCosts).length
    ? Object.entries(economicsCosts).map(([gtmType, cost]) => ({
      id: uniqueId('economics-cost'),
      gtm_type: gtmType,
      cost: String(cost),
    }))
    : [createEconomicsCostRow()]
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
    showMessage(scenarioBlockingIssue.value || 'Сценарий недозаполнен для расчета добычи.', 'error')
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
    currentSection.value = 'planner'
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
    if (scenarioDetail.value?.scenario?.metadata?.scenario_role === 'pure_base' && scenarioDetail.value?.scenario?.parent_scenario_id) {
      selectedScenarioId.value = scenarioDetail.value.scenario.parent_scenario_id
      return
    }
    pureBaseScenarioDetail.value = null
    optimizerForm.scenario_name = scenarioDetail.value.scenario?.name || optimizerForm.scenario_name
    optimizerForm.forecast_start_date = scenarioDetail.value.scenario?.forecast_start_date || optimizerForm.forecast_start_date
    optimizerForm.forecast_end_date = scenarioDetail.value.scenario?.forecast_end_date || optimizerForm.forecast_end_date
    scenarioSourceMode.value = scenarioDetail.value.scenario?.metadata?.scenario_source_mode || (scenarioDetail.value.context?.external_krs_schedule_dataset ? 'existing_krs' : 'new_krs')
    const pureBaseScenarioId = scenarioDetail.value.source_payload?.pure_base_scenario_id || scenarioDetail.value.scenario?.metadata?.pure_base_scenario_id || ''
    if (scenarioDetail.value.scenario?.metadata?.scenario_role !== 'pure_base' && pureBaseScenarioId) {
      const pureBaseResponse = await request(`/scenarios/${pureBaseScenarioId}`)
      pureBaseScenarioDetail.value = await pureBaseResponse.json()
    } else if (scenarioDetail.value.scenario?.metadata?.scenario_role === 'pure_base') {
      pureBaseScenarioDetail.value = scenarioDetail.value
    }
    if (scenarioDetail.value.context) {
      await applyScenarioContext(scenarioDetail.value.context)
    }
    const luKeys = [...new Set((scenarioDetail.value.wells || []).map((item) => item.lu_id || 'Без LU'))].map((item) => `lu:${item}`)
    expandedProductionKeys.value = ['total', ...luKeys]
    selectedProductionKeys.value = []
    hoveredProductionBucketDate.value = ''
    await loadPlannerRevisions(scenarioDetail.value.scenario?.parent_scenario_id || scenarioDetail.value.scenario?.scenario_id || '')
    selectedPlannerRevisionId.value = scenarioDetail.value.scenario?.metadata?.planner_revision_id || selectedPlannerRevisionId.value
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
    hoveredProductionBucketDate.value = ''
    return
  }
  selectedProductionKeys.value = [...selectedProductionKeys.value, key]
  hoveredProductionBucketDate.value = ''
}

const openPlannerFromScenario = async () => {
  if (!selectedScenarioId.value) {
    showMessage('Сначала создайте или выберите сценарий.', 'error')
    return
  }
  currentSection.value = 'planner'
  await syncPlannerWithActiveScenario({ silent: true })
  showMessage('Открыт модуль Planner для активного сценария.', 'info')
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

const resetPlannerRuntime = () => {
  plannerDatasetReference.value = null
  plannerVersionName.value = ''
  versions.value = []
  activeVersionId.value = 'base'
}

const applyPlannerScheduleRuntime = ({ items, versionName, datasetReference = null }) => {
  plannerDatasetReference.value = datasetReference
  plannerVersionName.value = versionName || datasetReference?.name || ''
  versions.value = [{
    id: 'base',
    name: versionName || datasetReference?.name || 'График КРС',
    created_at: new Date().toISOString(),
    items: cloneItems(items || []),
  }]
  activeVersionId.value = 'base'
}

const loadImportedScheduleIntoPlanner = async (reference) => {
  if (!reference) return null
  const response = await request('/schedule/open-imported', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataset_id: reference.dataset_id,
      dataset_version_id: reference.dataset_version_id,
    }),
  })
  const payload = await response.json()
  applyPlannerScheduleRuntime({
    items: payload.items || [],
    versionName: payload.version_name || 'Загруженный график',
    datasetReference: payload.dataset_reference,
  })
  return payload
}

const loadPlannerRevisionIntoPlanner = async (revisionId) => {
  if (!revisionId) return null
  const response = await request(`/planner/revisions/${revisionId}`)
  const revision = await response.json()
  applyPlannerScheduleRuntime({
    items: revision.items || [],
    versionName: revision.version_name || 'Planner revision',
    datasetReference: revision.metadata?.dataset_reference || selectedScenarioExternalKrsReference.value || null,
  })
  return revision
}

const syncPlannerWithActiveScenario = async ({ silent = false } = {}) => {
  if (!selectedScenarioId.value) {
    resetPlannerRuntime()
    if (!silent) showMessage('Сначала выберите активный сценарий для Planner.', 'error')
    return false
  }

  const revisionId = selectedScenarioPlannerRevisionId.value
  const externalReference = selectedScenarioExternalKrsReference.value

  loading.value = true
  try {
    if (revisionId) {
      await loadPlannerRevisionIntoPlanner(revisionId)
      if (!silent) showMessage('Planner синхронизирован с revision активного сценария.', 'info')
      return true
    }
    if (externalReference) {
      await loadImportedScheduleIntoPlanner(externalReference)
      if (!silent) showMessage('Planner синхронизирован с внешним графиком активного сценария.', 'info')
      return true
    }
    resetPlannerRuntime()
    if (!silent) showMessage('Для активного сценария пока нет связанного графика КРС для Planner.', 'info')
    return false
  } catch (error) {
    resetPlannerRuntime()
    showMessage(error.message, 'error')
    return false
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

const openPublishPlannerVersionDialog = () => {
  if (!selectedScenarioId.value) {
    showMessage('Сначала выберите активный сценарий для Planner.', 'error')
    return
  }
  if (!activeVersion.value) return
  plannerPublishScenarioName.value = `${optimizerForm.scenario_name} / ${activeVersion.value.name}`.trim()
  showPlannerPublishModal.value = true
}

const publishPlannerVersion = async () => {
  if (!selectedScenarioId.value) {
    showMessage('Сначала выберите активный сценарий для Planner.', 'error')
    return
  }
  if (!activeVersion.value) return
  if (!plannerPublishScenarioName.value.trim()) {
    showMessage('Введите имя нового сценария.', 'error')
    return
  }
  loading.value = true
  try {
    const publishResponse = await request('/planner/revisions/publish', {
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
        scenario_name: plannerPublishScenarioName.value.trim(),
      }),
    })
    const publishPayload = await publishResponse.json()
    const derivedScenario = publishPayload.scenario
    await loadScenarios()
    selectedScenarioId.value = derivedScenario.scenario.scenario_id
    await loadScenarioDetail(derivedScenario.scenario.scenario_id)
    currentSection.value = 'planner'
    showPlannerPublishModal.value = false
    showMessage('Planner revision сохранен и новая версия сценария создана автоматически.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const applyPlannerRevisionToScenario = async () => {
  if (!plannerRevisionSourceScenarioId.value) {
    showMessage('Сначала выберите базовый сценарий для planner revision.', 'error')
    return
  }
  if (!selectedPlannerRevisionId.value) {
    showMessage('Сначала выберите planner revision.', 'error')
    return
  }
  loading.value = true
  try {
    const revision = selectedPlannerRevision.value
    const response = await request(`/scenarios/${plannerRevisionSourceScenarioId.value}/from-planner-revision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        revision_id: selectedPlannerRevisionId.value,
        name: `${selectedScenarioSummary.value?.name || optimizerForm.scenario_name || 'Сценарий'} / ${revision?.version_name || 'Planner revision'}`,
      }),
    })
    const derivedScenario = await response.json()
    await loadScenarios()
    selectedScenarioId.value = derivedScenario.scenario.scenario_id
    await loadScenarioDetail(derivedScenario.scenario.scenario_id)
    currentSection.value = 'production'
    showMessage('Planner revision применена, новая версия сценария создана.', 'success')
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
  if (typeof window !== 'undefined') {
    if (scenarioId) {
      window.localStorage.setItem(ACTIVE_SCENARIO_STORAGE_KEY, scenarioId)
    } else {
      window.localStorage.removeItem(ACTIVE_SCENARIO_STORAGE_KEY)
    }
  }
  if (!scenarioId) {
    scenarioDetail.value = null
    pureBaseScenarioDetail.value = null
    return
  }
  await loadScenarioDetail(scenarioId)
  if (currentSection.value === 'planner') {
    await syncPlannerWithActiveScenario({ silent: true })
  }
})

watch(currentSection, async (section) => {
  if (section === 'planner') {
    await syncPlannerWithActiveScenario({ silent: true })
  }
})

watch(productionTimeMode, () => {
  hoveredProductionBucketDate.value = ''
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
    prefillSuggestedMappings({ overwrite: true })
  }
})

watch(wellsHierarchyRows, (rows) => {
  syncExpandedHierarchy(expandedWellsKeys, rows)
}, { immediate: true })

watch(gtmHierarchyRows, (rows) => {
  syncExpandedHierarchy(expandedGtmKeys, rows)
}, { immediate: true })

watch(infrastructureTreeRows, (rows) => {
  syncExpandedHierarchy(expandedInfrastructureKeys, rows)
  if (rows.length && !rows.some((row) => row.key === selectedInfrastructureRowKey.value)) {
    selectedInfrastructureRowKey.value = rows[0].key
  }
}, { immediate: true })

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
        <button class="nav-item" :class="{ active: currentSection === 'scenarios' }" @click="currentSection = 'scenarios'">
          <span class="nav-icon">⇪</span>
          <span v-if="!sidebarCollapsed">Сценарии</span>
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
        `Сценарии` собирает контекст сценария, загрузку datasets и manual inputs. `Добыча` читает сохраненные outputs Module B. `Планировщик КРС` остается отдельным модулем Planner.
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

      <section v-if="currentSection === 'scenarios'" class="page-stack scenarios-page">
        <div class="panel soft scenario-toolbar-panel">
          <div class="scenario-compact-bar">
            <label class="compact-field">
              <span>Сценарий</span>
              <select v-model="selectedScenarioId" class="compact-dropdown">
                <option value="">Новый сценарий</option>
                <option v-for="item in userVisibleScenarios" :key="item.scenario_id" :value="item.scenario_id">
                  {{ item.name }} · {{ item.source_type }}
                </option>
              </select>
            </label>
            <label class="compact-field">
              <span>Имя</span>
              <input v-model="optimizerForm.scenario_name" type="text" class="compact-dropdown" placeholder="Введите имя сценария" />
            </label>
            <label class="compact-field period">
              <span>Период</span>
              <div class="compact-period">
                <input v-model="optimizerForm.forecast_start_date" type="date" />
                <span>—</span>
                <input v-model="optimizerForm.forecast_end_date" type="date" />
              </div>
            </label>
            <div class="compact-actions">
              <button class="button primary" :disabled="loading" @click="saveScenarioContextAction">Сохранить контекст</button>
              <button class="button primary" :disabled="loading || !canCalculateScenario" :title="scenarioBlockingIssue || ''" @click="calculateForecast">Рассчитать</button>
            </div>
          </div>
        </div>

        <div class="scenario-workspace">
          <div class="panel soft scenario-canvas-panel">
            <div class="toolbar between align-start">
              <div>
                <h2>Workflow canvas</h2>
                <p class="subtitle">Кликайте по узлу. Нижний inspector показывает только данные выбранного блока. Центр бизнес-логики — `Module D: KRS Optimizer`.</p>
              </div>
            </div>

            <div class="scenario-canvas branch-canvas">
              <button type="button" class="canvas-node source-start" :class="{ ready: scenarioReadiness.hasSource, active: activeCanvasNode === 'scenario' }" @click="selectCanvasNode('scenario')">
                <span class="canvas-node-kicker">Старт</span>
                <strong>Источник графика</strong>
                <small>{{ scenarioFlowModeLabel }}</small>
              </button>

              <div class="source-branch-connectors" aria-hidden="true">
                <span></span>
                <span></span>
                <span></span>
              </div>

              <div class="source-actions workflow-source-actions">
                <button type="button" class="source-action" :class="{ active: scenarioFlowMode === 'external', ready: sourceFlowReady.external }" @click="setScenarioFlowSource('external')">
                  <div class="source-action-head">
                    <strong>Внешний график</strong>
                    <span v-if="sourceFlowReady.external" class="source-check">✓</span>
                  </div>
                  <span>{{ selectedDatasets.external_krs_schedule?.name || 'Нужно загрузить и привязать внешний график КРС.' }}</span>
                </button>
                <button type="button" class="source-action" :class="{ active: scenarioFlowMode === 'generated', ready: sourceFlowReady.generated }" @click="setScenarioFlowSource('generated')">
                  <div class="source-action-head">
                    <strong>Сформировать график</strong>
                    <span v-if="sourceFlowReady.generated" class="source-check">✓</span>
                  </div>
                  <span>График строится через расчетный контур и `Module D: KRS Optimizer`.</span>
                </button>
                <button type="button" class="source-action" :class="{ active: scenarioFlowMode === 'planner', ready: sourceFlowReady.planner }" @click="setScenarioFlowSource('planner')">
                  <div class="source-action-head">
                    <strong>Полученный из Planner</strong>
                    <span v-if="sourceFlowReady.planner" class="source-check">✓</span>
                  </div>
                  <span>{{ sourceFlowReady.planner ? 'Ниже можно выбрать опубликованную planner revision для применения.' : 'Для этого сценария ещё нет опубликованных planner revisions.' }}</span>
                </button>
              </div>

              <div class="flow-down-arrow" aria-hidden="true">↓</div>

              <div class="flow-main-row">
                <div class="canvas-node inputs-group" :class="{ ready: scenarioReadiness.hasInputs, active: ['wells', 'gtm', 'reservoir', 'economics', 'krs', 'infrastructure'].includes(activeCanvasNode) }">
                  <span class="canvas-node-kicker">Module A + Manual Inputs</span>
                  <strong>Исходные данные</strong>
                  <small>Загрузка datasets и настройка ручных вводных.</small>
                  <div class="input-mini-grid">
                    <button type="button" class="input-mini-node" :class="[inputNodeStatuses.wells, { active: activeCanvasNode === 'wells' }]" @click="selectCanvasNode('wells')">
                      <span class="input-mini-label">Wells</span>
                      <span v-if="inputNodeStatuses.wells !== 'empty'" class="input-mini-status">{{ inputNodeStatuses.wells === 'ready' ? '✓' : '−' }}</span>
                    </button>
                    <button type="button" class="input-mini-node" :class="[inputNodeStatuses.gtm, { active: activeCanvasNode === 'gtm' }]" @click="selectCanvasNode('gtm')">
                      <span class="input-mini-label">ГТМ</span>
                      <span v-if="inputNodeStatuses.gtm !== 'empty'" class="input-mini-status">{{ inputNodeStatuses.gtm === 'ready' ? '✓' : '−' }}</span>
                    </button>
                    <button type="button" class="input-mini-node" :class="[inputNodeStatuses.reservoir, { active: activeCanvasNode === 'reservoir' }]" @click="activeCanvasNode = 'reservoir'; currentInputsTab = 'reservoir'">
                      <span class="input-mini-label">Вытеснение</span>
                      <span v-if="inputNodeStatuses.reservoir !== 'empty'" class="input-mini-status">{{ inputNodeStatuses.reservoir === 'ready' ? '✓' : '−' }}</span>
                    </button>
                    <button type="button" class="input-mini-node" :class="[inputNodeStatuses.economics, { active: activeCanvasNode === 'economics' }]" @click="activeCanvasNode = 'economics'; currentInputsTab = 'economics'">
                      <span class="input-mini-label">Экономика</span>
                      <span v-if="inputNodeStatuses.economics !== 'empty'" class="input-mini-status">{{ inputNodeStatuses.economics === 'ready' ? '✓' : '−' }}</span>
                    </button>
                    <button type="button" class="input-mini-node" :class="[inputNodeStatuses.krs, { active: activeCanvasNode === 'krs' }]" @click="activeCanvasNode = 'krs'; currentInputsTab = 'brigades'">
                      <span class="input-mini-label">KRS огр.</span>
                      <span v-if="inputNodeStatuses.krs !== 'empty'" class="input-mini-status">{{ inputNodeStatuses.krs === 'ready' ? '✓' : '−' }}</span>
                    </button>
                    <button type="button" class="input-mini-node" :class="[inputNodeStatuses.infrastructure, { active: activeCanvasNode === 'infrastructure' }]" @click="selectCanvasNode('infrastructure')">
                      <span class="input-mini-label">Infrastructure</span>
                      <span v-if="inputNodeStatuses.infrastructure !== 'empty'" class="input-mini-status">{{ inputNodeStatuses.infrastructure === 'ready' ? '✓' : '−' }}</span>
                    </button>
                  </div>
                </div>

                <div class="flow-direct-branch" :class="{ inactive: scenarioFlowMode === 'generated' }">
                  <div class="flow-arrow">→</div>

                  <button type="button" class="canvas-node module-b" :class="{ ready: scenarioReadiness.hasResult, active: activeCanvasNode === 'forecast' }" @click="activeCanvasNode = 'forecast'">
                    <span class="canvas-node-kicker">Module B</span>
                    <strong>Forecast</strong>
                    <small>{{ scenarioReadiness.hasResult ? 'Профиль рассчитан' : 'Ожидает расчета' }}</small>
                  </button>

                  <div class="flow-arrow">→</div>

                  <div class="canvas-node module-c" :class="{ ready: scenarioReadiness.hasResult }">
                    <span class="canvas-node-kicker">Module C</span>
                    <strong>Economics</strong>
                    <small>{{ scenarioReadiness.hasResult ? 'Экономика сценария готова' : 'После Forecast' }}</small>
                  </div>
                </div>
              </div>

              <div class="generated-flow-shell" :class="{ inactive: scenarioFlowMode !== 'generated' }">
                <div class="generated-flow-note">
                  <span class="merge-chip">Forecast</span>
                  <span class="flow-arrow diagonal">↘</span>
                  <span class="merge-chip target">в KRS Optimizer</span>
                  <span class="flow-arrow diagonal">↗</span>
                  <span class="merge-chip">Economics</span>
                  <span class="flow-arrow diagonal">↘</span>
                  <span class="merge-chip">Infra Check</span>
                </div>

                <div class="generated-flow-row">
                  <button type="button" class="canvas-node module-d core" :class="{ ready: scenarioReadiness.hasInputs, active: activeCanvasNode === 'optimizer' }" @click="activeCanvasNode = 'optimizer'; currentInputsTab = 'optimizer'">
                    <span class="canvas-node-kicker">Module D</span>
                    <strong>KRS Optimizer</strong>
                    <small>Формирует и оптимизирует график КРС.</small>
                  </button>
                  <span class="flow-arrow">→</span>
                  <div class="canvas-node revision" :class="{ ready: scenarioReadiness.hasPlannerVersion }">
                    <span class="canvas-node-kicker">Revision</span>
                    <strong>Planner Revision</strong>
                    <small>{{ scenarioReadiness.hasPlannerVersion ? 'Доступна ревизия' : 'Пока нет revision' }}</small>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="panel workbench-shell">
          <div class="toolbar between align-start">
            <div>
              <h2>{{ nodeInspectorTitle }}</h2>
              <p class="subtitle">
                <template v-if="activeCanvasNode === 'scenario' && scenarioFlowMode === 'external'">Для внешнего графика КРС нижний inspector показывает загрузку, preview и mapping колонок с автопредложением сопоставления.</template>
                <template v-else-if="activeCanvasNode === 'scenario' && scenarioFlowMode === 'planner'">Нижний inspector показывает опубликованные planner revisions и позволяет выбрать, какую revision применить к активному сценарию.</template>
                <template v-else-if="activeCanvasNode === 'scenario'">Источник графика уже выбран на диаграмме.</template>
                <template v-else-if="activeCanvasNode === 'wells'">Версия wells dataset и сводная иерархия `LU -> куст -> скважина`.</template>
                <template v-else-if="activeCanvasNode === 'gtm'">Версия GTM dataset и сводная иерархия `LU -> куст -> скважина` с приростами.</template>
                <template v-else-if="activeCanvasNode === 'reservoir'">LU / SLOY, характеристика вытеснения и годовые темпы падения жидкости.</template>
                <template v-else-if="activeCanvasNode === 'economics'">Net back по LU и стоимости мероприятий по типам ГТМ.</template>
                <template v-else-if="activeCanvasNode === 'krs'">Ограничения КРС: бригады по месяцам, отказность и длительности.</template>
                <template v-else-if="activeCanvasNode === 'infrastructure'">Иерархия infrastructure и срезы мощностей по жидкости, нефти и газу.</template>
                <template v-else-if="activeCanvasNode === 'forecast'">Forecast не требует отдельных настроек optimizer. Здесь показывается только готовность сценария, а расчёт `Module B` запускается верхней кнопкой `Рассчитать`.</template>
                <template v-else-if="activeCanvasNode === 'optimizer'">Настройки `Module D: KRS Optimizer`: политика ограничений, целевая функция и режим построения графика КРС.</template>
                <template v-else>Параметры выбранного блока.</template>
              </p>
            </div>
          </div>

        <div v-if="activeCanvasNode === 'scenario' && scenarioFlowMode === 'planner'" class="page-stack">
          <div class="panel soft">
            <h2>Выбор planner revision</h2>
            <p class="subtitle">Выберите revision графика КРС, которую нужно применить к текущему сценарию. На основе выбранной revision будет создана новая версия сценария.</p>
            <div v-if="!plannerRevisionSourceScenarioId" class="empty-state">
              <strong>Нет базового сценария</strong>
              <span>Сначала выберите сценарий, для которого нужно применить planner revision.</span>
            </div>
            <div v-else-if="!plannerRevisions.length" class="empty-state">
              <strong>Planner revisions не найдены</strong>
              <span>Для этого сценария ещё не опубликованы версии из Planner.</span>
            </div>
            <div v-else class="page-stack">
              <div class="table-wrap medium-wrap">
                <table class="hierarchy-table">
                  <thead>
                    <tr>
                      <th>Выбор</th>
                      <th>Версия</th>
                      <th>Дата</th>
                      <th>Событий</th>
                      <th>Derived scenario</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="revision in plannerRevisions"
                      :key="revision.revision_id"
                      :class="{ selected: revision.revision_id === selectedPlannerRevisionId }"
                      @click="selectedPlannerRevisionId = revision.revision_id"
                    >
                      <td>
                        <input
                          type="radio"
                          name="planner-revision"
                          :checked="revision.revision_id === selectedPlannerRevisionId"
                          @change="selectedPlannerRevisionId = revision.revision_id"
                        />
                      </td>
                      <td><strong>{{ revision.version_name }}</strong></td>
                      <td>{{ formatDateCell(revision.edited_at) }}</td>
                      <td>{{ revision.item_count }}</td>
                      <td>{{ plannerDerivedScenarioMap[revision.revision_id]?.name || 'Не создан' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div class="detail-summary" v-if="selectedPlannerRevision">
                <div><span>Revision</span><strong>{{ selectedPlannerRevision.version_name }}</strong></div>
                <div><span>Сценарий-источник</span><strong>{{ selectedScenarioSummary?.parent_scenario_id ? (userVisibleScenarios.find((item) => item.scenario_id === plannerRevisionSourceScenarioId)?.name || plannerRevisionSourceScenarioId) : (selectedScenarioSummary?.name || '—') }}</strong></div>
                <div><span>Событий</span><strong>{{ selectedPlannerRevision.item_count }}</strong></div>
                <div><span>Derived</span><strong>{{ derivedScenarioForSelectedRevision?.name || 'Будет создан' }}</strong></div>
              </div>

              <div class="toolbar align-end">
                <button class="button primary" :disabled="!selectedPlannerRevisionId || loading" @click="applyPlannerRevisionToScenario">Применить revision</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeCanvasNode === 'wells' || activeCanvasNode === 'gtm' || activeCanvasNode === 'infrastructure' || (activeCanvasNode === 'scenario' && scenarioFlowMode === 'external')" class="page-stack">
          <div class="page-stack">
            <div class="panel soft">
              <h2>{{ SOURCE_KIND_META[selectedUploadSourceKind].title }}</h2>
              <p class="subtitle">{{ SOURCE_KIND_META[selectedUploadSourceKind].description }}</p>
              <input ref="uploadInputRef" type="file" accept=".xlsx,.xls" class="hidden-file-input" @change="uploadSourceFile" />
              <div class="upload-compact-row">
                <label class="compact-field">
                  <span>Файл</span>
                  <select v-model="selectedUploadFileId">
                    <option value="">Выберите файл</option>
                    <option v-for="item in uploadedFiles" :key="item.file_id" :value="item.file_id">{{ item.original_name }}</option>
                  </select>
                </label>
                <label class="compact-field">
                  <span>Лист</span>
                  <select v-model="selectedUploadSheet" :disabled="!selectedUploadFileId">
                    <option value="">Выберите лист</option>
                    <option v-for="sheet in (uploadedFiles.find((item) => item.file_id === selectedUploadFileId)?.sheets || [])" :key="sheet" :value="sheet">{{ sheet }}</option>
                  </select>
                </label>
                <label class="compact-field">
                  <span>Dataset</span>
                  <input v-model="datasetName" type="text" placeholder="Название набора данных" />
                </label>
                <label class="compact-field">
                  <span>Активная версия</span>
                  <select :value="selectedDatasetKeys[selectedUploadSourceKind]" @change="selectDatasetByKey(selectedUploadSourceKind, $event.target.value)">
                    <option value="">Не выбрана</option>
                    <option v-for="item in sourceDatasetOptions" :key="datasetReferenceKey(item.dataset_reference)" :value="datasetReferenceKey(item.dataset_reference)">
                      {{ item.dataset_reference.name }}
                    </option>
                  </select>
                </label>
                <div class="compact-actions upload-actions">
                  <button class="button" :disabled="loading" @click="uploadInputRef?.click()">Загрузить Excel</button>
                  <button class="button" :disabled="!selectedUploadFileId || loading" @click="openUploadedPreview(selectedUploadFileId, selectedUploadSheet || null)">Открыть</button>
                  <button class="button" :disabled="!inputFile || loading" @click="openMappingModalForCurrentFile()">Сопоставление</button>
                  <button class="button primary" :disabled="!inputFile || loading" @click="normalizeDataset">Сохранить dataset</button>
                </div>
              </div>
            </div>

            <div v-if="activeCanvasNode === 'wells'" class="panel">
              <h2>Сводка wells</h2>
              <div class="table-wrap medium-wrap">
                <table class="hierarchy-table">
                  <thead>
                    <tr><th>Узел</th><th>Скважин</th><th>Нефть</th><th>Жидкость</th><th>Газ</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in visibleWellsHierarchyRows" :key="row.key" :class="`node-${row.nodeType}`">
                      <td>
                        <div class="node-cell" :style="{ paddingLeft: `${row.depth * 18}px` }">
                          <button v-if="row.children.length" type="button" class="node-toggle" @click="toggleWellsExpand(row.key)">{{ expandedWellsKeys.includes(row.key) ? '−' : '+' }}</button>
                          <span v-else class="node-spacer"></span>
                          <strong>{{ row.label }}</strong>
                        </div>
                      </td>
                      <td>{{ row.metrics.count }}</td>
                      <td>{{ formatCompactNumber(row.metrics.oil) }}</td>
                      <td>{{ formatCompactNumber(row.metrics.liquid) }}</td>
                      <td>{{ formatCompactNumber(row.metrics.gas) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="activeCanvasNode === 'gtm'" class="panel">
              <h2>Сводка ГТМ</h2>
              <div class="table-wrap medium-wrap">
                <table class="hierarchy-table">
                  <thead>
                    <tr><th>Узел</th><th>Мероприятий</th><th>Прирост нефти</th><th>Прирост жидкости</th><th>Прирост газа</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in visibleGtmHierarchyRows" :key="row.key" :class="`node-${row.nodeType}`">
                      <td>
                        <div class="node-cell" :style="{ paddingLeft: `${row.depth * 18}px` }">
                          <button v-if="row.children.length" type="button" class="node-toggle" @click="toggleGtmExpand(row.key)">{{ expandedGtmKeys.includes(row.key) ? '−' : '+' }}</button>
                          <span v-else class="node-spacer"></span>
                          <strong>{{ row.label }}</strong>
                        </div>
                      </td>
                      <td>{{ row.metrics.count }}</td>
                      <td>{{ formatCompactNumber(row.metrics.oil) }}</td>
                      <td>{{ formatCompactNumber(row.metrics.liquid) }}</td>
                      <td>{{ formatCompactNumber(row.metrics.gas) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="activeCanvasNode === 'infrastructure'" class="module-grid two-wide">
              <div class="panel">
                <h2>Иерархия infrastructure</h2>
                <div class="table-wrap medium-wrap">
                  <table class="hierarchy-table">
                    <thead>
                      <tr><th>Узел</th><th>Жидкость</th><th>Нефть</th><th>Газ</th></tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="row in visibleInfrastructureTreeRows"
                        :key="row.key"
                        :class="[{ selected: selectedInfrastructureRowKey === row.key }, `node-${row.nodeType}`]"
                        @click="selectedInfrastructureRowKey = row.key"
                      >
                        <td>
                          <div class="node-cell" :style="{ paddingLeft: `${row.depth * 18}px` }">
                            <button v-if="row.children.length" type="button" class="node-toggle" @click.stop="toggleInfrastructureExpand(row.key)">{{ expandedInfrastructureKeys.includes(row.key) ? '−' : '+' }}</button>
                            <span v-else class="node-spacer"></span>
                            <strong>{{ row.label }}</strong>
                          </div>
                        </td>
                        <td>{{ formatCompactNumber(row.metrics.liquid) }}</td>
                        <td>{{ formatCompactNumber(row.metrics.oil) }}</td>
                        <td>{{ formatCompactNumber(row.metrics.gas) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div class="panel">
                <div class="toolbar between">
                  <div>
                    <h2>Срез мощностей</h2>
                    <p class="subtitle">Выберите узел в таблице и метрику для просмотра.</p>
                  </div>
                  <div class="mode-toggle">
                    <button type="button" class="mode-toggle-button" :class="{ active: infrastructureMetric === 'liquid' }" @click="infrastructureMetric = 'liquid'">Жидкость</button>
                    <button type="button" class="mode-toggle-button" :class="{ active: infrastructureMetric === 'oil' }" @click="infrastructureMetric = 'oil'">Нефть</button>
                    <button type="button" class="mode-toggle-button" :class="{ active: infrastructureMetric === 'gas' }" @click="infrastructureMetric = 'gas'">Газ</button>
                  </div>
                </div>
                <div class="detail-summary">
                  <div><span>Выбранный узел</span><strong>{{ selectedInfrastructureRow?.label || '—' }}</strong></div>
                  <div><span>Значение</span><strong>{{ formatCompactNumber(selectedInfrastructureRow?.metrics?.[infrastructureMetric] || 0) }}</strong></div>
                </div>
                <div class="infrastructure-bar-chart">
                  <div
                    v-for="metric in ['liquid', 'oil', 'gas']"
                    :key="metric"
                    class="infra-bar"
                  >
                    <span>{{ metric === 'liquid' ? 'Жидкость' : metric === 'oil' ? 'Нефть' : 'Газ' }}</span>
                    <div class="infra-bar-track">
                      <div
                        class="infra-bar-fill"
                        :class="metric"
                        :style="{ width: `${Math.min(100, ((selectedInfrastructureRow?.metrics?.[metric] || 0) / Math.max(selectedInfrastructureRow?.metrics?.liquid || 0, selectedInfrastructureRow?.metrics?.oil || 0, selectedInfrastructureRow?.metrics?.gas || 0, 1)) * 100)}%` }"
                      ></div>
                    </div>
                    <strong>{{ formatCompactNumber(selectedInfrastructureRow?.metrics?.[metric] || 0) }}</strong>
                  </div>
                </div>
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
        </div>

        <div v-else-if="activeCanvasNode === 'reservoir'" class="page-stack">
          <div class="panel reservoir-strip compact" v-if="activeReservoirConfig">
            <div class="reservoir-strip-title">
              <h2>Конфигурации пласта</h2>
              <p class="subtitle">LU / SLOY, характеристика вытеснения и годовые темпы падения жидкости.</p>
            </div>
            <div class="reservoir-strip-row single-line">
              <div class="field reservoir-strip-field reservoir-configs inline">
                <span>Конфигурации</span>
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

              <div class="field reservoir-strip-field reservoir-lu-field inline">
                <span>LU</span>
                <div class="lu-button-group">
                  <button type="button" class="lu-chip-button" :class="{ active: activeReservoirConfig.lu_id === '' }" @click="activeReservoirConfig.lu_id = ''">Без LU</button>
                  <button
                    v-for="lu in luOptions"
                    :key="lu"
                    type="button"
                    class="lu-chip-button"
                    :class="{ active: activeReservoirConfig.lu_id === lu }"
                    @click="activeReservoirConfig.lu_id = lu"
                  >
                    {{ lu }}
                  </button>
                </div>
              </div>

              <label class="field reservoir-strip-field reservoir-sloy-field inline">
                <span>SLOY</span>
                <select v-model="activeReservoirConfig.sloy_id">
                  <option value="">Все слои</option>
                  <option v-for="sloy in sloyOptions" :key="sloy" :value="sloy">{{ sloy }}</option>
                </select>
              </label>

              <label class="field reservoir-strip-field reservoir-notes-field inline">
                <span>Заметки</span>
                <input v-model="activeReservoirConfig.notes" type="text" placeholder="Комментарий к конфигурации" />
              </label>

              <div class="reservoir-strip-actions">
                <button class="button primary" @click="addReservoirConfig">Добавить конфигурацию</button>
                <button class="button ghost" :disabled="reservoirConfigs.length === 1" @click="removeReservoirConfig(activeReservoirConfig.config_id)">Удалить</button>
              </div>
            </div>
          </div>

          <div v-if="activeReservoirConfig" class="module-grid two-wide">
            <div class="panel">
              <h2>Обводненность → NIZ</h2>
              <p class="subtitle">Таблица предзаполнена шагом 5%. В колонку NIZ можно вставить целый столбец через Ctrl+V.</p>
              <div class="reservoir-grid">
                <div class="table-wrap compact-grid-wrap">
                  <table class="compact-grid-table">
                    <thead>
                      <tr><th>Обв., %</th><th>NIZ</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, index) in activeReservoirConfig.displacement_rows" :key="`watercut-${index}`">
                        <td>{{ row.watercut }}</td>
                        <td><input v-model="row.NIZ" type="text" class="table-input compact-table-input" @paste="handleNizPaste($event, activeReservoirConfig, index)" /></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div class="mini-chart-card">
                  <svg viewBox="0 0 240 100" class="mini-chart">
                    <line x1="8" y1="88" x2="232" y2="88" class="mini-axis" />
                    <line x1="8" y1="8" x2="8" y2="88" class="mini-axis" />
                    <polyline v-if="reservoirChartPath" :points="reservoirChartPath.replaceAll('M ', '').replaceAll(' L ', ' ')" class="mini-line" />
                  </svg>
                  <div class="mini-chart-caption">Кривая NIZ по обводненности</div>
                </div>
              </div>
            </div>

            <div class="panel">
              <h2>Падение жидкости</h2>
              <div class="decline-split">
                <div>
                  <h3>База</h3>
                  <div class="decline-editor-grid">
                    <div class="table-wrap compact-grid-wrap">
                      <table class="compact-grid-table">
                        <thead><tr><th>Мес.</th><th>Год. темп, %</th></tr></thead>
                        <tbody>
                          <tr v-for="row in activeReservoirConfig.base_decline_rows" :key="`base-${row.month_index}`">
                            <td>{{ row.month_index }}</td>
                            <td><input v-model="row.liquid_decline_factor" type="number" step="0.1" class="table-input compact-table-input" /></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div class="mini-chart-card">
                      <svg viewBox="0 0 240 100" class="mini-chart">
                        <line x1="8" y1="88" x2="232" y2="88" class="mini-axis" />
                        <line x1="8" y1="8" x2="8" y2="88" class="mini-axis" />
                        <polyline v-if="baseDeclineChartPath" :points="baseDeclineChartPath.replaceAll('M ', '').replaceAll(' L ', ' ')" class="mini-line decline" />
                      </svg>
                      <div class="mini-chart-caption">Base decline</div>
                    </div>
                  </div>
                </div>
                <div>
                  <h3>ВНС</h3>
                  <div class="decline-editor-grid">
                    <div class="table-wrap compact-grid-wrap">
                      <table class="compact-grid-table">
                        <thead><tr><th>Мес.</th><th>Год. темп, %</th></tr></thead>
                        <tbody>
                          <tr v-for="row in activeReservoirConfig.new_wells_decline_rows" :key="`new-${row.month_index}`">
                            <td>{{ row.month_index }}</td>
                            <td><input v-model="row.liquid_decline_factor" type="number" step="0.1" class="table-input compact-table-input" /></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div class="mini-chart-card">
                      <svg viewBox="0 0 240 100" class="mini-chart">
                        <line x1="8" y1="88" x2="232" y2="88" class="mini-axis" />
                        <line x1="8" y1="8" x2="8" y2="88" class="mini-axis" />
                        <polyline v-if="newWellsDeclineChartPath" :points="newWellsDeclineChartPath.replaceAll('M ', '').replaceAll(' L ', ' ')" class="mini-line decline" />
                      </svg>
                      <div class="mini-chart-caption">New wells decline</div>
                    </div>
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

        <div v-else-if="activeCanvasNode === 'economics'" class="page-stack">
          <div class="module-grid two-wide">
            <div class="panel">
              <div class="toolbar between">
                <div>
                  <h2>Net Back по LU</h2>
                  <p class="subtitle">LU-специфичная часть EconomicsConfig.</p>
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
              <div class="toolbar between">
                <div>
                  <h2>Стоимости мероприятий</h2>
                  <p class="subtitle">`gtm_costs_by_type` из EconomicsConfig.</p>
                </div>
                <button class="button primary" @click="addEconomicsCostRow">Добавить тип</button>
              </div>
              <div class="table-wrap medium-wrap">
                <table>
                  <thead><tr><th>Тип ГТМ</th><th>Стоимость</th></tr></thead>
                  <tbody>
                    <tr v-for="row in economicsCostRows" :key="row.id">
                      <td><input v-model="row.gtm_type" type="text" class="table-input" /></td>
                      <td><input v-model="row.cost" type="number" step="0.01" class="table-input" /></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="module-grid two-wide">
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

            <div class="panel">
              <h2>Сводка EconomicsConfig</h2>
              <div class="detail-summary">
                <div><span>LU записей</span><strong>{{ economicsRows.filter((row) => row.lu_id).length }}</strong></div>
                <div><span>Типов затрат</span><strong>{{ economicsCostRows.filter((row) => row.gtm_type).length }}</strong></div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeCanvasNode === 'krs'" class="page-stack">
          <div class="tabs">
            <button class="tab-button" :class="{ active: krsInspectorTab === 'brigades' }" @click="krsInspectorTab = 'brigades'">Бригады</button>
            <button class="tab-button" :class="{ active: krsInspectorTab === 'failure' }" @click="krsInspectorTab = 'failure'">Отказность</button>
            <button class="tab-button" :class="{ active: krsInspectorTab === 'durations' }" @click="krsInspectorTab = 'durations'">Длительности</button>
          </div>

          <div class="module-grid three-wide">
            <div v-if="krsInspectorTab === 'brigades'" class="panel">
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

            <div v-if="krsInspectorTab === 'failure'" class="panel">
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

            <div v-if="krsInspectorTab === 'durations'" class="panel">
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

        <div v-else-if="activeCanvasNode === 'forecast'" class="page-stack">
          <div class="module-grid two-wide">
            <div class="panel">
              <h2>Forecast</h2>
              <p class="subtitle">`Module B` считает профиль добычи напрямую по привязанным входам сценария. Ограничения optimizer и infra policy на этот расчёт не влияют.</p>
              <div class="detail-summary">
                <div><span>Сценарий</span><strong>{{ optimizerForm.scenario_name || selectedScenarioSummary?.name || '—' }}</strong></div>
                <div><span>Статус</span><strong>{{ scenarioDetail?.scenario?.status || 'draft' }}</strong></div>
                <div><span>Период</span><strong>{{ formatDateCell(optimizerForm.forecast_start_date) }} — {{ formatDateCell(optimizerForm.forecast_end_date) }}</strong></div>
                <div><span>Результат</span><strong>{{ scenarioReadiness.hasResult ? 'Профиль рассчитан' : 'Ещё не рассчитан' }}</strong></div>
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
                <strong>Поведение расчёта</strong>
                <div>Forecast считается без ограничений optimizer и запускается верхней кнопкой `Рассчитать`.</div>
                <div>Infra policy и objective применяются только на этапе `KRS Optimizer`.</div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeCanvasNode === 'optimizer'" class="page-stack">
          <div class="module-grid">
            <div class="panel">
              <h2>Схема работы оптимизатора</h2>
              <p class="subtitle">Этот блок относится к `Module D: KRS Optimizer`. Здесь задаются настройки построения и оптимизации графика КРС, а не параметры расчёта `Forecast`.</p>
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
              </div>
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
                <option v-for="scenario in userVisibleScenarios" :key="scenario.scenario_id" :value="scenario.scenario_id">
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
                <h2>{{ productionChartTitle }}</h2>
                <p class="subtitle">{{ productionChartSubtitle }}</p>
              </div>
              <div class="toolbar-actions">
                <div class="mode-toggle">
                  <button
                    v-for="metric in PRODUCTION_METRICS"
                    :key="metric.key"
                    type="button"
                    class="mode-toggle-button"
                    :class="{ active: productionMetric === metric.key }"
                    @click="productionMetric = metric.key"
                  >
                    {{ metric.label }}
                  </button>
                </div>
                <div class="mode-toggle">
                  <button
                    v-for="mode in PRODUCTION_TIME_MODES"
                    :key="mode.key"
                    type="button"
                    class="mode-toggle-button"
                    :class="{ active: productionTimeMode === mode.key }"
                    @click="productionTimeMode = mode.key"
                  >
                    {{ mode.label }}
                  </button>
                </div>
                <div class="legend">
                  <span v-for="item in productionChartLegend" :key="item.label" class="legend-item">
                    <i :class="item.kind === 'line' ? 'legend-line' : 'legend-dot'" :style="{ background: item.kind === 'line' ? 'transparent' : item.color, borderColor: item.color }"></i>
                    {{ item.label }} {{ formatCompactNumber(item.value) }}
                  </span>
                </div>
              </div>
            </div>
            <div class="production-chart-wrap">
              <div
                v-if="hoveredProductionBucket"
                class="production-tooltip"
                :style="productionTooltipStyle"
              >
                <strong>{{ formatProductionBucketLabel(hoveredProductionBucket.date, productionTimeMode) }}</strong>
                <span>БАЗА {{ formatCompactNumber(hoveredProductionBucket.basePeriod) }}</span>
                <span>ГТМ {{ formatCompactNumber(hoveredProductionBucket.gtmPeriod) }}</span>
                <span>ВНС {{ formatCompactNumber(hoveredProductionBucket.vnsPeriod) }}</span>
                <span>Накопленная {{ formatCompactNumber(hoveredProductionBucket.totalCum) }}</span>
              </div>
              <svg v-if="productionSeries.length" class="production-chart" :viewBox="`0 0 ${PRODUCTION_CHART_WIDTH} ${PRODUCTION_CHART_HEIGHT}`" preserveAspectRatio="none">
                <g class="production-grid">
                  <line
                    v-for="tick in productionAxisTicks"
                    :key="`grid-${tick.y}`"
                    :x1="PRODUCTION_CHART_LEFT_PADDING"
                    :x2="PRODUCTION_CHART_WIDTH - PRODUCTION_CHART_RIGHT_PADDING"
                    :y1="tick.y"
                    :y2="tick.y"
                    class="production-grid-line"
                  />
                  <line
                    :x1="PRODUCTION_CHART_LEFT_PADDING"
                    :x2="PRODUCTION_CHART_LEFT_PADDING"
                    :y1="PRODUCTION_CHART_TOP_PADDING"
                    :y2="PRODUCTION_CHART_HEIGHT - PRODUCTION_CHART_BOTTOM_PADDING"
                    class="production-axis-line"
                  />
                  <line
                    :x1="PRODUCTION_CHART_WIDTH - PRODUCTION_CHART_RIGHT_PADDING"
                    :x2="PRODUCTION_CHART_WIDTH - PRODUCTION_CHART_RIGHT_PADDING"
                    :y1="PRODUCTION_CHART_TOP_PADDING"
                    :y2="PRODUCTION_CHART_HEIGHT - PRODUCTION_CHART_BOTTOM_PADDING"
                    class="production-axis-line secondary"
                  />
                  <line
                    :x1="PRODUCTION_CHART_LEFT_PADDING"
                    :x2="PRODUCTION_CHART_WIDTH - PRODUCTION_CHART_RIGHT_PADDING"
                    :y1="PRODUCTION_CHART_HEIGHT - PRODUCTION_CHART_BOTTOM_PADDING"
                    :y2="PRODUCTION_CHART_HEIGHT - PRODUCTION_CHART_BOTTOM_PADDING"
                    class="production-axis-line"
                  />
                  <text
                    v-for="tick in productionAxisTicks"
                    :key="`left-${tick.y}`"
                    :x="PRODUCTION_CHART_LEFT_PADDING - 10"
                    :y="tick.y + 4"
                    class="production-axis-label left"
                  >
                    {{ formatCompactNumber(tick.value) }}
                  </text>
                  <text
                    v-for="tick in productionCumulativeTicks"
                    :key="`right-${tick.y}`"
                    :x="PRODUCTION_CHART_WIDTH - PRODUCTION_CHART_RIGHT_PADDING + 10"
                    :y="tick.y + 4"
                    class="production-axis-label right"
                  >
                    {{ formatCompactNumber(tick.value) }}
                  </text>
                  <text
                    v-for="tick in productionDateTicks"
                    :key="`x-${tick.x}-${tick.label}`"
                    :x="tick.x"
                    :y="PRODUCTION_CHART_HEIGHT - 14"
                    class="production-axis-label bottom"
                  >
                    {{ tick.label }}
                  </text>
                  <text
                    :x="18"
                    :y="PRODUCTION_CHART_HEIGHT / 2"
                    class="production-axis-title"
                    transform="rotate(-90 18 130)"
                  >
                    {{ `${PRODUCTION_METRICS.find((item) => item.key === productionMetric)?.label || 'Добыча'} за период, ${PRODUCTION_METRICS.find((item) => item.key === productionMetric)?.unit || ''}` }}
                  </text>
                  <text
                    :x="PRODUCTION_CHART_WIDTH - 16"
                    :y="PRODUCTION_CHART_HEIGHT / 2"
                    class="production-axis-title right"
                    transform="rotate(90 1264 130)"
                  >
                    {{ `Накопленная ${PRODUCTION_METRICS.find((item) => item.key === productionMetric)?.label.toLowerCase() || 'добыча'}, ${PRODUCTION_METRICS.find((item) => item.key === productionMetric)?.unit || ''}` }}
                  </text>
                </g>
                <g v-for="bar in productionChartBars" :key="bar.date">
                  <rect
                    :x="bar.bandX"
                    :y="PRODUCTION_CHART_TOP_PADDING"
                    :width="bar.bandWidth"
                    :height="productionPlotHeight"
                    class="production-hit-area"
                    @mouseenter="hoveredProductionBucketDate = bar.date"
                    @mouseleave="hoveredProductionBucketDate = ''"
                  />
                  <rect v-if="bar.baseHeight > 0" :x="bar.x" :y="bar.baseY" :width="bar.width" :height="bar.baseHeight" class="production-bar base" />
                  <rect v-if="bar.gtmHeight > 0" :x="bar.x" :y="bar.gtmY" :width="bar.width" :height="bar.gtmHeight" class="production-bar gtm" />
                  <rect v-if="bar.vnsHeight > 0" :x="bar.x" :y="bar.vnsY" :width="bar.width" :height="bar.vnsHeight" class="production-bar vns" />
                </g>
                <polyline v-if="productionCumulativePolyline" :points="productionCumulativePolyline" class="production-line" />
              </svg>
              <div v-else class="empty-inline">Нет данных по выбранной группе.</div>
              <div v-if="false" class="production-labels">
                <span v-for="item in productionLabelPoints" :key="item.date">{{ item.label }} · {{ formatCompactNumber(item.totalPeriod) }} / накопл. {{ formatCompactNumber(item.totalCum) }}</span>
              </div>
            </div>
          </div>

          <div class="panel">
            <div class="toolbar between">
              <div>
                <h2>Иерархия профиля</h2>
                <p class="subtitle">Выделение работает по leaf rows. Parent-узлы только разворачивают и задают область выбора. Справа показан временной ряд по выбранной агрегации.</p>
              </div>
              <button class="button ghost" @click="selectedProductionKeys = []">Сбросить выбор</button>
            </div>
            <div class="table-wrap hierarchy-wrap production-hierarchy-wrap">
              <table class="hierarchy-table production-hierarchy-table">
                <thead>
                  <tr>
                    <th>Выбор</th>
                    <th>Узел</th>
                    <th>Фонд</th>
                    <th>Скважин</th>
                    <th>{{ PRODUCTION_METRICS.find((item) => item.key === productionMetric)?.label || 'Показатель' }}</th>
                    <th
                      v-for="column in productionTableColumns"
                      :key="column.key"
                      class="production-date-column"
                      :title="column.fullLabel"
                    >
                      {{ column.label }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in productionTableRows" :key="row.key" :class="`node-${row.nodeType}`">
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
                    <td class="production-total-cell">{{ formatCompactNumber(row.metricTotal) }}</td>
                    <td
                      v-for="(value, index) in row.bucketSeries"
                      :key="`${row.key}:${productionTableColumns[index]?.key || index}`"
                      class="production-value-cell"
                    >
                      {{ formatCompactNumber(value) }}
                    </td>
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
              <p class="subtitle">Planner автоматически открывает график активного сценария: внешний imported KRS dataset или опубликованную planner revision.</p>
            </div>
            <div class="toolbar">
              <select v-if="false" v-model="plannerDatasetSelectionKey" class="compact-dropdown">
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
                v-if="false"
                :disabled="!plannerDatasetSelectionKey || loading"
                @click="openImportedSchedule(datasetTypes.external_krs_schedule.find((item) => datasetReferenceKey(item.dataset_reference) === plannerDatasetSelectionKey)?.dataset_reference)"
              >
                Открыть
              </button>
              <div class="detail-summary planner-source-summary">
                <div><span>Сценарий</span><strong>{{ selectedScenarioSummary?.name || optimizerForm.scenario_name || '—' }}</strong></div>
                <div><span>Источник</span><strong>{{ plannerSourceLabel }}</strong></div>
              </div>
              
            </div>
          </div>
        </div>

        <div v-if="!activeItems.length" class="panel empty-state">Planner пока не получил график из активного сценария. Загрузите внешний график КРС или создайте planner revision в рамках выбранного сценария.</div>

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
                <button class="button primary" :disabled="!selectedScenarioId || loading" @click="openPublishPlannerVersionDialog">Создать версию</button>
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

      <div v-if="showPlannerPublishModal" class="modal-overlay" @click.self="showPlannerPublishModal = false">
        <div class="modal-card planner-publish-modal">
          <div class="toolbar between align-start">
            <div>
              <h2>Новый сценарий из Planner</h2>
              <p class="subtitle">Planner revision создаст новый сценарий типа `Полученный из Planner` и сразу сделает его активным во всей системе.</p>
            </div>
            <button class="button ghost" @click="showPlannerPublishModal = false">Закрыть</button>
          </div>
          <label class="compact-field full-width">
            <span>Имя нового сценария</span>
            <input v-model="plannerPublishScenarioName" type="text" class="compact-dropdown" placeholder="Введите имя сценария" />
          </label>
          <div class="toolbar end">
            <button class="button" :disabled="loading" @click="showPlannerPublishModal = false">Отмена</button>
            <button class="button primary" :disabled="loading || !plannerPublishScenarioName.trim()" @click="publishPlannerVersion">Создать версию</button>
          </div>
        </div>
      </div>

      <div v-if="showMappingModal" class="modal-overlay" @click.self="showMappingModal = false">
        <div class="modal-card mapping-modal">
          <div class="toolbar between align-start">
            <div>
              <h2>Сопоставление колонок</h2>
              <p class="subtitle">Проверьте предложенные соответствия. Если все верно, подтвердите и сохраните dataset без ручного прокликивания всех полей.</p>
            </div>
            <button class="button ghost" @click="showMappingModal = false">Закрыть</button>
          </div>

          <div class="mapping-columns-strip">
            <span v-for="columnName in availableColumnNames" :key="columnName" class="mapping-column-chip">{{ columnName }}</span>
          </div>

          <div class="table-wrap medium-wrap">
            <table>
              <thead>
                <tr>
                  <th>Поле</th>
                  <th>Обязательное</th>
                  <th>Колонка Excel</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in mappingSuggestionRows" :key="row.fieldName">
                  <td>{{ row.label }}</td>
                  <td>{{ row.required ? 'Да' : 'Нет' }}</td>
                  <td>
                    <select v-model="normalizeColumns[row.fieldName]" class="table-input">
                      <option value="">Не сопоставлять</option>
                      <option v-for="columnName in availableColumnNames" :key="`${row.fieldName}-${columnName}`" :value="columnName">{{ columnName }}</option>
                    </select>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="toolbar between">
            <div class="subtitle">Обязательные поля вынесены вверх. Предложения уже проставлены автоматически.</div>
            <div class="toolbar">
              <button class="button" :disabled="loading" @click="showMappingModal = false">Принять</button>
              <button
                class="button primary"
                :disabled="!inputFile || loading"
                @click="showMappingModal = false; normalizeDataset()"
              >
                Принять и сохранить
              </button>
            </div>
          </div>
        </div>
      </div>
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

.scenario-list {
  display: grid;
  gap: 10px;
}

.scenario-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  padding: 14px;
  border: 1px solid rgba(35, 50, 68, 0.08);
  border-radius: 16px;
  background: linear-gradient(180deg, #fff, #f7fbff);
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
  appearance: none;
}

.scenario-card.active {
  border-color: rgba(47, 128, 255, 0.24);
  background: linear-gradient(180deg, #eef5ff, #f9fbff);
}

.scenario-card-head,
.scenario-card-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.scenario-card-head strong {
  display: block;
  font-size: 16px;
  color: #1c2736;
}

.scenario-card-id,
.scenario-card-links span,
.scenario-card-footer span {
  color: #627286;
  font-size: 13px;
}

.scenario-card-id {
  display: block;
  margin-top: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  word-break: break-all;
}

.scenario-badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #edf4ff;
  color: #18314e;
  font-size: 12px;
  font-weight: 700;
}

.scenario-card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.scenario-card-grid > div {
  padding: 10px 12px;
  border: 1px solid rgba(35, 50, 68, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
}

.scenario-card-grid span {
  display: block;
  color: #7a8ca1;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.scenario-card-grid strong {
  display: block;
  margin-top: 6px;
  color: #1c2736;
  font-size: 14px;
}

.scenario-card-links {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 14px;
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
.node-type td strong,
.node-object td strong,
.node-pad td strong {
  font-weight: 700;
}

.reservoir-strip.compact {
  padding: 12px 16px;
}

.reservoir-strip.compact .reservoir-strip-title {
  display: none;
}

.reservoir-strip-row.single-line {
  display: flex;
  align-items: end;
  gap: 12px;
  flex-wrap: nowrap;
}

.reservoir-strip-field.inline {
  margin: 0;
  min-width: 0;
}

.reservoir-strip-field.inline span {
  margin-bottom: 4px;
  font-size: 11px;
  line-height: 1;
}

.reservoir-configs {
  flex: 1 1 360px;
}

.reservoir-lu-field {
  flex: 1.4 1 520px;
}

.reservoir-sloy-field {
  flex: 0 0 200px;
}

.reservoir-notes-field {
  flex: 0 0 220px;
}

.reservoir-notes-field input {
  min-height: 36px;
}

.reservoir-strip-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}

.reservoir-strip-actions .button {
  min-height: 36px;
  padding: 0 14px;
}

.reservoir-configs .config-list {
  min-height: 36px;
  align-items: center;
}

.reservoir-strip.compact .lu-button-group {
  gap: 6px;
}

.reservoir-strip.compact .lu-chip-button {
  min-height: 36px;
  padding: 0 10px;
}

@media (max-width: 1580px) {
  .reservoir-strip-row.single-line {
    flex-wrap: wrap;
  }
}

.lu-button-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.lu-chip-button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(35, 50, 68, 0.12);
  border-radius: 999px;
  background: #f5f8fc;
  color: #41556c;
  font-weight: 700;
  cursor: pointer;
}

.lu-chip-button.active {
  background: #eaf3ff;
  border-color: rgba(47, 128, 255, 0.26);
  color: #154a9a;
}

.reservoir-grid,
.decline-editor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 12px;
  align-items: start;
}

.compact-grid-wrap {
  max-height: 420px;
}

.compact-grid-table {
  table-layout: fixed;
}

.compact-grid-table th,
.compact-grid-table td {
  padding: 4px 6px;
  font-size: 12px;
  line-height: 1.15;
}

.compact-table-input {
  min-height: 28px;
  padding: 4px 6px;
  border-radius: 6px;
}

.mini-chart-card {
  display: grid;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(35, 50, 68, 0.08);
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff, #f9fbff);
}

.mini-chart {
  width: 100%;
  height: 100px;
  overflow: visible;
}

.mini-axis {
  stroke: rgba(35, 50, 68, 0.18);
  stroke-width: 1;
}

.mini-line {
  fill: none;
  stroke: #2f80ff;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.mini-line.decline {
  stroke: #ff8a2b;
}

.mini-chart-caption {
  color: #5b6d82;
  font-size: 12px;
  font-weight: 600;
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

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.mode-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px;
  border-radius: 999px;
  background: #eef4fb;
}

.mode-toggle-button {
  border: 0;
  background: transparent;
  color: #5b6d82;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  font-weight: 700;
  cursor: pointer;
}

.mode-toggle-button.active {
  background: #ffffff;
  color: #1d2f42;
  box-shadow: 0 6px 18px rgba(38, 60, 86, 0.12);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #617388;
  font-size: 13px;
}

.legend-dot,
.legend-swatch,
.legend-line {
  display: inline-block;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
}

.legend-line {
  width: 16px;
  height: 0;
  border-top: 3px solid #132233;
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
  position: relative;
  overflow-x: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.production-hierarchy-wrap {
  overflow: auto;
}

.production-hierarchy-table {
  min-width: max-content;
}

.production-hierarchy-table th,
.production-hierarchy-table td {
  white-space: nowrap;
}

.production-hierarchy-table th:nth-child(1),
.production-hierarchy-table td:nth-child(1) {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #fff;
}

.production-hierarchy-table th:nth-child(2),
.production-hierarchy-table td:nth-child(2) {
  position: sticky;
  left: 64px;
  z-index: 2;
  background: #fff;
}

.production-hierarchy-table th:nth-child(3),
.production-hierarchy-table td:nth-child(3) {
  position: sticky;
  left: 324px;
  z-index: 2;
  background: #fff;
}

.production-hierarchy-table th:nth-child(4),
.production-hierarchy-table td:nth-child(4) {
  position: sticky;
  left: 444px;
  z-index: 2;
  background: #fff;
}

.production-hierarchy-table th:nth-child(5),
.production-hierarchy-table td:nth-child(5) {
  position: sticky;
  left: 544px;
  z-index: 2;
  background: #fff;
}

.production-date-column,
.production-value-cell {
  min-width: 86px;
  text-align: right;
}

.production-total-cell {
  text-align: right;
  font-weight: 700;
}

.production-chart {
  min-width: 100%;
  height: 260px;
}

.production-tooltip {
  position: absolute;
  top: 10px;
  z-index: 4;
  display: grid;
  gap: 4px;
  min-width: 152px;
  padding: 10px 12px;
  border: 1px solid rgba(19, 34, 51, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 10px 24px rgba(24, 39, 56, 0.12);
  pointer-events: none;
}

.production-tooltip strong {
  color: #1c2736;
  font-size: 13px;
}

.production-tooltip span {
  color: #5d6f84;
  font-size: 12px;
}

.production-grid-line {
  stroke: rgba(35, 50, 68, 0.08);
  stroke-width: 1;
}

.production-axis-line {
  stroke: rgba(35, 50, 68, 0.18);
  stroke-width: 1.2;
}

.production-axis-line.secondary {
  stroke: rgba(19, 34, 51, 0.14);
}

.production-axis-label {
  fill: #66778b;
  font-size: 11px;
}

.production-axis-label.left {
  text-anchor: end;
}

.production-axis-label.right {
  text-anchor: start;
}

.production-axis-label.bottom {
  text-anchor: middle;
}

.production-axis-title {
  fill: #5d6f84;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.production-hit-area {
  fill: transparent;
}

.production-bar.base {
  fill: rgba(47, 128, 255, 0.78);
}

.production-bar.gtm {
  fill: rgba(76, 195, 154, 0.78);
}

.production-bar.vns {
  fill: rgba(230, 124, 37, 0.8);
}

.production-line {
  fill: none;
  stroke: #132233;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
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
  .decline-split,
  .reservoir-grid,
  .decline-editor-grid,
  .scenario-card-grid,
  .scenario-card-links {
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

