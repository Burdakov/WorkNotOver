<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8010/api'
const SESSION_KEY = 'worknotover-krs-session'
const VERSIONS_KEY = 'worknotover-krs-versions'
const CHART_PLOT_HEIGHT = 180

const sidebarCollapsed = ref(false)
const currentView = ref('upload')
const loading = ref(false)
const message = ref('')
const messageType = ref('info')

const uploadedFiles = ref([])
const uploadedFile = ref(null)
const selectedFileId = ref('')
const selectedSheet = ref('')
const versions = ref([])
const activeVersionId = ref('base')
const timelineZoom = ref(12)
const timelineStartOffset = ref(0)
const timelineEndOffset = ref(0)
const minIncrementFilter = ref(0)
const showPpd = ref(true)
const selectedPrefixes = ref([])
const selectedAreas = ref([])
const selectedWorkTypes = ref([])
const inputTab = ref('upload')
const selectedSourceKind = ref('external_krs_schedule')
const datasets = ref([])
const selectedDatasetId = ref('')
const datasetDetail = ref(null)
const manualInputSets = ref([])
const latestNormalization = ref(null)
const plannerSourceMode = ref('file')
const plannerDatasetReference = ref(null)
const knownLuOptions = ref([])
const forecastScenarios = ref([])
const selectedScenarioId = ref('')
const forecastScenarioDetail = ref(null)
const selectedProductionKeys = ref([])

const PRODUCTION_CHART_HEIGHT = 260
const PRODUCTION_CHART_MIN_WIDTH = 920

const INPUT_TABS = [
  { id: 'upload', label: 'Загрузка' },
  { id: 'reservoir', label: 'Характеристики пласта' },
  { id: 'economics', label: 'Экономические вводные' },
  { id: 'brigades', label: 'Ограничения бригад' },
  { id: 'optimizer', label: 'Схема работы оптимизатора' },
]

const SOURCE_KIND_OPTIONS = [
  { id: 'external_krs_schedule', label: '1. Загрузить существующий график КРС' },
  { id: 'wells', label: '2. Загрузить базовый фонд' },
  { id: 'gtm', label: '3. Загрузить план ГТМ' },
  { id: 'infrastructure', label: '4. Загрузить ограничения инфраструктуры' },
]

const SOURCE_KIND_FIELD_LABELS = {
  brigade: 'Бригада',
  area: 'Участок',
  lu: 'LU',
  sloy: 'SLOY',
  well_pad: 'Куст',
  well: 'Скважина',
  fund_type: 'Тип фонда',
  start_date: 'Дата начала',
  end_date: 'Дата завершения',
  planned_work: 'Планируемый объем работ',
  increment: 'Oil increment / Qн',
  liquid_increment: 'Liquid increment',
  gas_increment: 'Gas increment',
  gor_change: 'GOR change',
  oil_rate: 'Текущая нефть',
  gas_rate: 'Текущий газ',
  liquid_rate: 'Текущая жидкость',
  watercut: 'Обводненность',
  gor: 'Газовый фактор',
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
  connection_well: 'Привязка скважины',
  parent_object: 'Родительский объект',
}

const SOURCE_KIND_FIELDS = {
  external_krs_schedule: ['brigade', 'area', 'lu', 'sloy', 'well_pad', 'well', 'start_date', 'end_date', 'planned_work', 'increment', 'liquid_increment', 'gas_increment', 'gor_change'],
  wells: ['area', 'lu', 'sloy', 'well_pad', 'well', 'fund_type', 'oil_rate', 'gas_rate', 'liquid_rate', 'watercut', 'gor', 'cumulative_oil', 'cumulative_gas', 'niz'],
  gtm: ['area', 'lu', 'sloy', 'well_pad', 'well', 'gtm_type', 'planned_work', 'start_date', 'end_date', 'duration_days', 'increment', 'liquid_increment', 'gas_increment', 'gor_change'],
  infrastructure: ['area', 'lu', 'sloy', 'well_pad', 'object_name', 'object_type', 'commissioning_date', 'capacity_oil', 'capacity_gas', 'capacity_liquid', 'capacity_water', 'connection_well', 'parent_object'],
}

const columns = reactive({
  brigade: '',
  area: '',
  well: '',
  start_date: '',
  end_date: '',
  increment: '',
  planned_work: '',
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

const reservoirForm = reactive({
  name: 'Характеристики пласта',
  selectedLu: '',
  selectedSloy: '',
  watercutUnit: 'percent',
  displacementPoints: Array.from({ length: 21 }, (_, index) => ({
    watercut: index * 5,
    niz: '',
  })),
  declineMode: 'annual_percent_by_month',
  baseDeclineRows: Array.from({ length: 24 }, (_, index) => ({
    month_index: index + 1,
    decline_percent: 5,
  })),
  newWellsDeclineRows: Array.from({ length: 24 }, (_, index) => ({
    month_index: index + 1,
    decline_percent: index < 12 ? 50 : 5,
  })),
  notes: '',
})

const economicsForm = reactive({
  name: 'Экономические вводные',
  rows: [{
    lu_id: '',
    net_back: '',
    oil_price: '',
    gas_price: '',
    liquid_handling_cost: '',
    water_handling_cost: '',
    gas_handling_cost: '',
    discount_rate: '',
  }],
  gtmCostsText: '',
  notes: '',
})

const brigadesForm = reactive({
  name: 'Ограничения бригад',
  capacityRows: [{ lu_id: '', month_date: '', brigade_count: '' }],
  failureRows: [{ scope_type: 'lu', lu_id: '', sloy_id: '', coefficient: '' }],
  durationRows: [{ gtm_type: '', duration_days: '' }],
  fallbackBrigadeCount: '',
  notes: '',
})

const optimizerForm = reactive({
  name: 'Схема работы оптимизатора',
  targetFunction: 'max_npv',
  buildMode: 'build_and_optimize',
  scenarioSelection: 'best_feasible',
  infraReactionMode: 'hard_stop',
  heuristicMode: 'guided_search',
  scenarioDescription: '',
  constraintsLogic: '',
})

const showMessage = (text, type = 'info') => {
  message.value = text
  messageType.value = type
}

const readJson = (key, fallback) => {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback))
  } catch {
    return fallback
  }
}

const writeJson = (key, value) => localStorage.setItem(key, JSON.stringify(value))

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

const addDays = (value, days) => {
  const next = parseIsoDate(value)
  if (!next) return value
  next.setUTCDate(next.getUTCDate() + days)
  return formatIsoDate(next)
}

const diffDays = (from, to) => {
  const left = parseIsoDate(from)
  const right = parseIsoDate(to)
  if (!left || !right) return 0
  return Math.round((right - left) / 86400000)
}

const formatDayNumber = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { day: '2-digit' }).format(parsed) : ''
}

const formatMonthLabel = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { month: 'short' }).format(parsed).replace('.', '') : ''
}

const formatDateCell = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(parsed) : '—'
}

const formatIncrement = (value) => (value && value > 0 ? Number(value).toFixed(1) : '0')
const cloneItems = (items) => items.map((item) => ({ ...item }))
const wellPrefix = (value) => String(value || '').trim().slice(0, 2).toUpperCase() || 'NA'
const gtmOpacity = (item) => {
  if (item.is_ppd) return 1
  const threshold = Number(minIncrementFilter.value || 0)
  if (threshold <= 0) return 1
  const increment = item.increment && item.increment > 0 ? Number(item.increment) : 0
  if (increment >= threshold) return 1
  return 0.18 + (increment / threshold) * 0.82
}
const colorFromPrefix = (prefix) => {
  const hash = [...prefix].reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return `hsl(${(hash * 19) % 360} 72% 56%)`
}

const availableColumns = computed(() => uploadedFile.value?.columns_info || [])
const activeVersion = computed(() => versions.value.find((version) => version.id === activeVersionId.value) || versions.value[0] || null)
const activeItems = computed(() => activeVersion.value?.items || [])
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
const canEditVersion = computed(() => activeVersionId.value !== 'base')
const totalIncrement = computed(() => visibleItems.value.reduce((sum, item) => sum + (item.increment && item.increment > 0 ? Number(item.increment) : 0), 0))
const previewColumns = computed(() => Object.keys(uploadedFile.value?.preview?.[0] || {}))
const sourceKindFields = computed(() => SOURCE_KIND_FIELDS[selectedSourceKind.value] || [])
const selectedSourceKindLabel = computed(() => SOURCE_KIND_OPTIONS.find((item) => item.id === selectedSourceKind.value)?.label || 'Источник')
const viewTitle = computed(() => {
  if (currentView.value === 'upload') return 'Исходные данные'
  if (currentView.value === 'production') return 'Добыча'
  return 'Планировщик КРС'
})
const viewSubtitle = computed(() => {
  if (currentView.value === 'upload') {
    return 'Подготовка внешнего графика КРС, базового фонда, плана ГТМ, ограничений инфраструктуры и ручных вводных для расчётного контура.'
  }
  if (currentView.value === 'production') {
    return 'Сценарный просмотр накопленной добычи по БАЗЕ, ГТМ и ВНС с фильтрацией по полной иерархии LU → SLOY → куст → скважина.'
  }
  return 'Светлый рабочий интерфейс для версий графика, анализа приростов, ручной корректировки и последующей выгрузки обновлённого плана.'
})
const uploadedFileRowCount = computed(() => uploadedFile.value?.preview?.length || 0)
const datasetsByType = computed(() => {
  const grouped = new Map()
  datasets.value.forEach((item) => {
    const type = item.dataset_reference.dataset_type
    if (!grouped.has(type)) grouped.set(type, [])
    grouped.get(type).push(item)
  })
  return grouped
})
const sourceKindStatusCards = computed(() =>
  SOURCE_KIND_OPTIONS.map((option) => {
    const items = datasetsByType.value.get(option.id) || []
    const latest = items[0] || null
    return {
      id: option.id,
      label: option.label,
      loaded: Boolean(latest),
      rows: latest?.dataset_reference?.row_count || 0,
      name: latest?.dataset_reference?.name || 'Не загружено',
    }
  }),
)
const manualInputSummaryCards = computed(() => {
  const categories = [
    { id: 'displacement_config', label: 'Характеристики пласта' },
    { id: 'economics_config', label: 'Экономические вводные' },
    { id: 'brigade_capacity_by_lu_config', label: 'Ограничения бригад' },
    { id: 'optimizer_config', label: 'Схема оптимизатора' },
  ]
  return categories.map((category) => {
    const latest = manualInputSets.value.find((item) => item.payload?.[category.id])
    return {
      ...category,
      loaded: Boolean(latest),
      name: latest?.reference?.name || 'Не сохранено',
    }
  })
})
const luSelectOptions = computed(() => [...knownLuOptions.value].sort((a, b) => a.localeCompare(b, 'ru')))

const formatCompactDateTime = (value) => {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed)
}

const productionTypeLabel = (row) => {
  if (row.type === 'total') return 'Итого'
  if (row.type === 'lu') return 'LU'
  if (row.type === 'sloy') return 'SLOY'
  if (row.type === 'well_pad') return 'Куст'
  if (row.type === 'well') return row.fund_type || 'Скважина'
  return row.type
}

const sumPointSeries = (points, field) =>
  (points || []).reduce((sum, point) => sum + Number(point?.[field] || 0), 0)

const buildProductionHierarchy = (wells) => {
  const nodeMap = new Map()
  const root = {
    key: 'total',
    parentKey: null,
    type: 'total',
    depth: 0,
    label: 'Итого',
    fund_type: null,
    wellIds: new Set(),
    totals: { oil: 0, liquid: 0, gas: 0 },
    children: [],
  }
  nodeMap.set(root.key, root)

  const ensureNode = (parent, key, type, label, fundType = null) => {
    if (nodeMap.has(key)) return nodeMap.get(key)
    const node = {
      key,
      parentKey: parent.key,
      type,
      depth: parent.depth + 1,
      label,
      fund_type: fundType,
      wellIds: new Set(),
      totals: { oil: 0, liquid: 0, gas: 0 },
      children: [],
    }
    parent.children.push(node)
    nodeMap.set(key, node)
    return node
  }

  const addWellToNode = (node, wellId, totals) => {
    node.wellIds.add(wellId)
    node.totals.oil += totals.oil
    node.totals.liquid += totals.liquid
    node.totals.gas += totals.gas
  }

  for (const well of wells || []) {
    const wellId = String(well.well_id || well.well_name || '')
    const totals = {
      oil: Number(well.total_oil || 0),
      liquid: Number(well.total_liquid || 0),
      gas: Number(well.total_gas || 0),
    }
    const lu = String(well.lu_id || 'Без LU')
    const sloy = String(well.sloy_id || 'Без слоя')
    const wellPad = String(well.well_pad_id || 'Без куста')
    const wellName = String(well.well_name || wellId || 'Скважина')

    const luNode = ensureNode(root, `lu:${lu}`, 'lu', lu)
    const sloyNode = ensureNode(luNode, `lu:${lu}|sloy:${sloy}`, 'sloy', sloy)
    const padNode = ensureNode(sloyNode, `lu:${lu}|sloy:${sloy}|pad:${wellPad}`, 'well_pad', wellPad)
    const wellNode = ensureNode(
      padNode,
      `lu:${lu}|sloy:${sloy}|pad:${wellPad}|well:${wellId}`,
      'well',
      wellName,
      well.fund_type || null,
    )

    addWellToNode(root, wellId, totals)
    addWellToNode(luNode, wellId, totals)
    addWellToNode(sloyNode, wellId, totals)
    addWellToNode(padNode, wellId, totals)
    addWellToNode(wellNode, wellId, totals)
  }

  const sortNodes = (nodes) => {
    nodes.sort((left, right) => left.label.localeCompare(right.label, 'ru'))
    nodes.forEach((child) => sortNodes(child.children))
  }
  sortNodes(root.children)

  const rows = []
  const walk = (node) => {
    rows.push({
      key: node.key,
      parentKey: node.parentKey,
      type: node.type,
      depth: node.depth,
      label: node.label,
      fund_type: node.fund_type,
      wellCount: node.wellIds.size,
      totals: {
        oil: Number(node.totals.oil.toFixed(2)),
        liquid: Number(node.totals.liquid.toFixed(2)),
        gas: Number(node.totals.gas.toFixed(2)),
      },
    })
    node.children.forEach(walk)
  }
  walk(root)

  return {
    rows,
    nodeMap,
  }
}

const forecastScenarioOptions = computed(() =>
  [...forecastScenarios.value].sort((left, right) => {
    const leftDate = new Date(left.latest_result_created_at || left.created_at || 0).getTime()
    const rightDate = new Date(right.latest_result_created_at || right.created_at || 0).getTime()
    return rightDate - leftDate
  }),
)
const selectedForecastScenarioMeta = computed(() =>
  forecastScenarioOptions.value.find((item) => item.scenario_id === selectedScenarioId.value) || null,
)
const forecastScenarioWells = computed(() => forecastScenarioDetail.value?.wells || [])
const productionHierarchy = computed(() => buildProductionHierarchy(forecastScenarioWells.value))
const productionRowLookup = computed(() => productionHierarchy.value.nodeMap)
const selectedProductionRows = computed(() =>
  selectedProductionKeys.value
    .map((key) => productionHierarchy.value.rows.find((row) => row.key === key))
    .filter(Boolean),
)
const selectedProductionWellIds = computed(() => {
  if (!selectedProductionKeys.value.length) return new Set(forecastScenarioWells.value.map((well) => String(well.well_id)))
  const wellIds = new Set()
  selectedProductionKeys.value.forEach((key) => {
    const node = productionRowLookup.value.get(key)
    node?.wellIds?.forEach((wellId) => wellIds.add(String(wellId)))
  })
  return wellIds
})
const selectedForecastWells = computed(() => {
  const allowed = selectedProductionWellIds.value
  return forecastScenarioWells.value.filter((well) => allowed.has(String(well.well_id)))
})
const selectedProductionTotals = computed(() => ({
  oil: Number(selectedForecastWells.value.reduce((sum, well) => sum + Number(well.total_oil || 0), 0).toFixed(2)),
  liquid: Number(selectedForecastWells.value.reduce((sum, well) => sum + Number(well.total_liquid || 0), 0).toFixed(2)),
  gas: Number(selectedForecastWells.value.reduce((sum, well) => sum + Number(well.total_gas || 0), 0).toFixed(2)),
}))
const productionSeries = computed(() => {
  if (!forecastScenarioDetail.value) return []
  const pointsByDate = new Map()
  selectedForecastWells.value.forEach((well) => {
    const fundBucket = String(well.fund_type || '').toLowerCase() === 'new wells' ? 'vns' : 'base'
    ;(well.points || []).forEach((point) => {
      const existing = pointsByDate.get(point.date) || { date: point.date, base: 0, gtm: 0, vns: 0 }
      existing[fundBucket] += Number(point.oil_rate || 0)
      existing.gtm += Number(point.oil_increment || 0)
      pointsByDate.set(point.date, existing)
    })
  })
  const orderedDates = (forecastScenarioDetail.value.production_points || [])
    .map((point) => point.date)
    .filter((date, index, items) => items.indexOf(date) === index)
  let cumulativeBase = 0
  let cumulativeGtm = 0
  let cumulativeVns = 0
  return orderedDates.map((date) => {
    const bucket = pointsByDate.get(date) || { base: 0, gtm: 0, vns: 0 }
    cumulativeBase += bucket.base
    cumulativeGtm += bucket.gtm
    cumulativeVns += bucket.vns
    return {
      date,
      base: Number(cumulativeBase.toFixed(2)),
      gtm: Number(cumulativeGtm.toFixed(2)),
      vns: Number(cumulativeVns.toFixed(2)),
      total: Number((cumulativeBase + cumulativeGtm + cumulativeVns).toFixed(2)),
    }
  })
})
const productionChartWidth = computed(() => Math.max(PRODUCTION_CHART_MIN_WIDTH, productionSeries.value.length * 2.2))
const productionChartMax = computed(() => productionSeries.value.reduce((max, point) => Math.max(max, point.total), 0))
const productionChartLegend = computed(() => {
  const last = productionSeries.value[productionSeries.value.length - 1]
  return [
    { key: 'base', label: 'БАЗА', color: '#497ee8', value: last?.base || 0 },
    { key: 'gtm', label: 'ГТМ', color: '#f08b32', value: last?.gtm || 0 },
    { key: 'vns', label: 'ВНС', color: '#41b77a', value: last?.vns || 0 },
  ]
})
const productionSelectedLabel = computed(() =>
  selectedProductionRows.value.length ? selectedProductionRows.value.map((row) => row.label).join(', ') : 'Весь сценарий',
)

const productionStackedPaths = computed(() => {
  if (!productionSeries.value.length || !productionChartMax.value) return []
  const width = productionChartWidth.value
  const maxValue = productionChartMax.value
  const toX = (index) => (productionSeries.value.length === 1 ? width / 2 : (index / (productionSeries.value.length - 1)) * width)
  const toY = (value) => PRODUCTION_CHART_HEIGHT - (value / maxValue) * PRODUCTION_CHART_HEIGHT
  const buildPath = (upperValues, lowerValues) => {
    const upper = upperValues.map((value, index) => `${index === 0 ? 'M' : 'L'} ${toX(index)} ${toY(value)}`).join(' ')
    const lower = lowerValues
      .map((value, index) => {
        const reverseIndex = lowerValues.length - 1 - index
        return `L ${toX(reverseIndex)} ${toY(lowerValues[reverseIndex])}`
      })
      .join(' ')
    return `${upper} ${lower} Z`
  }
  const baseUpper = productionSeries.value.map((point) => point.base)
  const gtmUpper = productionSeries.value.map((point) => point.base + point.gtm)
  const vnsUpper = productionSeries.value.map((point) => point.total)
  const zeroLine = productionSeries.value.map(() => 0)
  return [
    { key: 'base', label: 'БАЗА', color: '#497ee8', path: buildPath(baseUpper, zeroLine) },
    { key: 'gtm', label: 'ГТМ', color: '#f08b32', path: buildPath(gtmUpper, baseUpper) },
    { key: 'vns', label: 'ВНС', color: '#41b77a', path: buildPath(vnsUpper, gtmUpper) },
  ]
})
const productionTotalLine = computed(() => {
  if (!productionSeries.value.length || !productionChartMax.value) return ''
  const width = productionChartWidth.value
  const toX = (index) => (productionSeries.value.length === 1 ? width / 2 : (index / (productionSeries.value.length - 1)) * width)
  const toY = (value) => PRODUCTION_CHART_HEIGHT - (value / productionChartMax.value) * PRODUCTION_CHART_HEIGHT
  return productionSeries.value.map((point, index) => `${index === 0 ? 'M' : 'L'} ${toX(index)} ${toY(point.total)}`).join(' ')
})
const productionAxisLabels = computed(() => {
  if (!productionSeries.value.length) return []
  const every = Math.max(1, Math.floor(productionSeries.value.length / 6))
  return productionSeries.value
    .map((point, index) => ({ ...point, index }))
    .filter((point, index, items) => index === 0 || index === items.length - 1 || index % every === 0)
    .map((point) => ({
      key: point.date,
      date: point.date,
      left: productionSeries.value.length === 1 ? productionChartWidth.value / 2 : (point.index / (productionSeries.value.length - 1)) * productionChartWidth.value,
    }))
})

const fullScheduleBounds = computed(() => {
  if (!visibleItems.value.length) return { min: null, max: null }
  const min = visibleItems.value.reduce((acc, item) => (!acc || item.start_date < acc ? item.start_date : acc), null)
  const max = visibleItems.value.reduce((acc, item) => (!acc || item.end_date > acc ? item.end_date : acc), null)
  return { min, max }
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

const scheduleBounds = computed(() => ({
  min: timelineWindowStart.value,
  max: timelineWindowEnd.value,
}))

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
    const existing = segments[segments.length - 1]
    if (existing && existing.key === key) {
      existing.span += 1
      return
    }
    segments.push({ key, label: formatMonthLabel(date), span: 1 })
  })
  return segments
})

const timelineDayWidth = computed(() => timelineZoom.value)
const todayIso = computed(() => formatIsoDate(new Date()))
const todayOffset = computed(() => {
  if (!scheduleBounds.value.min || !scheduleBounds.value.max) return null
  if (todayIso.value < scheduleBounds.value.min || todayIso.value > scheduleBounds.value.max) return null
  return diffDays(scheduleBounds.value.min, todayIso.value)
})

const chartMax = computed(() => Math.max(...visibleItems.value.map((item) => (item.increment && item.increment > 0 ? Number(item.increment) : 0)), 10))

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

const topChartBars = computed(() =>
  incrementTimeline.value.map((group) => ({
    ...group,
    total: group.positive.reduce((sum, item) => sum + item.value, 0),
    labels: group.positive.map((item) => `${item.well} ${formatIncrement(item.increment)}`),
  })),
)

const topChartMax = computed(() => Math.max(...topChartBars.value.map((group) => group.total), 10))
const cumulativeIncrementSeries = computed(() => {
  const grouped = new Map(
    topChartBars.value.map((group) => [group.date, group.total]),
  )
  return ganttDates.value.map((date, index) => {
    const runningTotal = visibleItems.value.reduce((sum, item) => {
      const value = item.increment && item.increment > 0 ? Number(item.increment) : 0
      return item.end_date <= date ? sum + value : sum
    }, 0)
    return {
      date,
      index,
      total: runningTotal,
      x: index * timelineDayWidth.value + timelineDayWidth.value / 2,
    }
  })
})
const cumulativeIncrementMax = computed(() => Math.max(...cumulativeIncrementSeries.value.map((point) => point.total), 10))
const cumulativeLinePoints = computed(() =>
  cumulativeIncrementSeries.value
    .map((point) => {
      const y = CHART_PLOT_HEIGHT - (point.total / cumulativeIncrementMax.value) * CHART_PLOT_HEIGHT
      return `${point.x},${y}`
    })
    .join(' '),
)
const cumulativeLineLabels = computed(() =>
  cumulativeIncrementSeries.value.filter((point, index, source) => index % 7 === 0 || index === source.length - 1),
)
const incrementLegend = computed(() => {
  const seen = new Map()
  visibleItems.value.forEach((item) => {
    const prefix = wellPrefix(item.well)
    if (!seen.has(prefix)) seen.set(prefix, colorFromPrefix(prefix))
  })
  return [...seen.entries()].slice(0, 16).map(([prefix, color]) => ({ prefix, color }))
})

watch([fullScheduleBounds, todayIso], ([bounds]) => {
  if (!bounds.min || !bounds.max) {
    timelineStartOffset.value = 0
    timelineEndOffset.value = 0
    return
  }
  const totalDays = diffDays(bounds.min, bounds.max)
  const preferredStart = addDays(todayIso.value, -7)
  const startOffset = preferredStart <= bounds.min ? 0 : Math.min(diffDays(bounds.min, preferredStart), totalDays)
  timelineStartOffset.value = startOffset
  timelineEndOffset.value = totalDays
}, { immediate: true })

const syncColumns = (nextColumns) => {
  Object.assign(columns, {
    brigade: nextColumns?.brigade || '',
    area: nextColumns?.area || '',
    well: nextColumns?.well || '',
    start_date: nextColumns?.start_date || '',
    end_date: nextColumns?.end_date || '',
    increment: nextColumns?.increment || '',
    planned_work: nextColumns?.planned_work || '',
  })
}

const persistSession = () => {
  writeJson(SESSION_KEY, {
    file_id: uploadedFile.value?.file_id || null,
    sheet_name: uploadedFile.value?.selected_sheet || null,
    columns: { ...columns },
    view: currentView.value,
    active_version_id: activeVersionId.value,
    planner_source_mode: plannerSourceMode.value,
    planner_dataset_reference: plannerDatasetReference.value,
    selected_scenario_id: selectedScenarioId.value || null,
  })
}

const persistVersions = () => {
  if (!uploadedFile.value?.file_id) return
  const allVersions = readJson(VERSIONS_KEY, {})
  allVersions[uploadedFile.value.file_id] = {
    versions: versions.value,
    active_version_id: activeVersionId.value,
  }
  writeJson(VERSIONS_KEY, allVersions)
  persistSession()
}

const restoreVersions = (fileId, items, keepExisting) => {
  const allVersions = readJson(VERSIONS_KEY, {})
  const saved = allVersions[fileId]
  if (keepExisting && saved?.versions?.length) {
    versions.value = saved.versions
    activeVersionId.value = saved.active_version_id || saved.versions[0].id
    return
  }
  versions.value = [{
    id: 'base',
    name: 'Базовая версия',
    created_at: new Date().toISOString(),
    items: cloneItems(items),
  }]
  activeVersionId.value = 'base'
}

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

const syncPlannerDefaults = () => {
  syncColumns({
    brigade: columns.brigade || 'Бригада',
    area: columns.area || 'Участок',
    well: columns.well || 'Скв.',
    start_date: columns.start_date || 'Дата начала (план)',
    end_date: columns.end_date || 'Заверш рем (план)',
    increment: columns.increment || 'Qн, тн/сут',
    planned_work: columns.planned_work || 'Планируемый объем работ',
  })
}

const normalizeColumnsPayload = () =>
  Object.fromEntries(
    sourceKindFields.value
      .map((field) => [field, normalizeColumns[field]])
      .filter(([, value]) => Boolean(value)),
  )

const loadDatasets = async () => {
  const response = await request('/datasets')
  datasets.value = await response.json()
  await hydrateLuOptions()
}

const loadManualInputSets = async () => {
  const response = await request('/manual-inputs')
  manualInputSets.value = await response.json()
}

const loadForecastScenarios = async () => {
  const response = await request('/forecast/scenarios')
  const payload = await response.json()
  forecastScenarios.value = Array.isArray(payload) ? payload : []
  if (
    selectedScenarioId.value
    && !forecastScenarios.value.some((item) => item.scenario_id === selectedScenarioId.value)
  ) {
    selectedScenarioId.value = ''
  }
  if (!selectedScenarioId.value && forecastScenarioOptions.value.length) {
    selectedScenarioId.value = forecastScenarioOptions.value[0].scenario_id
  }
}

const loadForecastScenarioDetail = async (scenarioId) => {
  if (!scenarioId) {
    forecastScenarioDetail.value = null
    selectedProductionKeys.value = []
    return
  }
  const response = await request(`/forecast/scenarios/${encodeURIComponent(scenarioId)}`)
  forecastScenarioDetail.value = await response.json()
  selectedProductionKeys.value = []
}

const loadDatasetDetail = async (datasetId, datasetVersionId = null) => {
  const query = datasetVersionId ? `?dataset_version_id=${encodeURIComponent(datasetVersionId)}` : ''
  const response = await request(`/datasets/${datasetId}${query}`)
  datasetDetail.value = await response.json()
  selectedDatasetId.value = datasetId
  appendLuOptionsFromPayload(datasetDetail.value.normalized_payload)
}

const toggleProductionNode = (key) => {
  if (key === 'total') {
    selectedProductionKeys.value = selectedProductionKeys.value.includes('total') ? [] : ['total']
    return
  }
  const next = new Set(selectedProductionKeys.value.filter((item) => item !== 'total'))
  if (next.has(key)) next.delete(key)
  else next.add(key)
  selectedProductionKeys.value = [...next]
}

const clearProductionSelection = () => {
  selectedProductionKeys.value = []
}

const loadUploadedFiles = async () => {
  const response = await request('/files')
  uploadedFiles.value = await response.json()
}

const parseSchedule = async (customColumns = null, keepVersions = true) => {
  if (!uploadedFile.value?.file_id) return
  const response = await request('/schedule/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: uploadedFile.value.file_id,
      sheet_name: uploadedFile.value.selected_sheet,
      columns: customColumns,
    }),
  })
  const payload = await response.json()
  syncColumns(payload.columns)
  restoreVersions(payload.file_id, payload.items, keepVersions)
  persistVersions()
}

const loadSourceFile = async (fileId, sheetName = null) => {
  loading.value = true
  try {
    const query = sheetName ? `?sheet_name=${encodeURIComponent(sheetName)}` : ''
    const response = await request(`/files/${fileId}${query}`)
    uploadedFile.value = await response.json()
    selectedFileId.value = uploadedFile.value.file_id
    selectedSheet.value = uploadedFile.value.selected_sheet
    latestNormalization.value = null
    showMessage('Файл исходных данных открыт.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const openFile = async (fileId, sheetName = null, keepVersions = true) => {
  loading.value = true
  try {
    const query = sheetName ? `?sheet_name=${encodeURIComponent(sheetName)}` : ''
    const response = await request(`/files/${fileId}${query}`)
    uploadedFile.value = await response.json()
    selectedFileId.value = uploadedFile.value.file_id
    selectedSheet.value = uploadedFile.value.selected_sheet
    plannerSourceMode.value = 'file'
    plannerDatasetReference.value = null
    await parseSchedule(null, keepVersions)
    showMessage('График КРС открыт.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const handleFileChange = async (event) => {
  const [file] = event.target.files || []
  if (!file) return
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await request('/files/upload', { method: 'POST', body: formData })
    uploadedFile.value = await response.json()
    selectedFileId.value = uploadedFile.value.file_id
    selectedSheet.value = uploadedFile.value.selected_sheet
    await loadUploadedFiles()
    latestNormalization.value = null
    datasetDetail.value = null
    showMessage('Excel загружен. Проверьте сопоставление и сохраните набор данных.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
    event.target.value = ''
  }
}

const applyColumnMapping = async () => {
  loading.value = true
  try {
    await parseSchedule({ ...columns }, false)
    showMessage('Сопоставление колонок применено.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const openImportedDataset = async (datasetReference, keepVersions = false) => {
  if (!datasetReference?.dataset_id) return
  loading.value = true
  try {
    const response = await request('/schedule/open-imported', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_id: datasetReference.dataset_id,
        dataset_version_id: datasetReference.dataset_version_id,
      }),
    })
    const payload = await response.json()
    const storageKey = `dataset:${payload.dataset_reference.dataset_id}:${payload.dataset_reference.dataset_version_id}`
    uploadedFile.value = {
      file_id: storageKey,
      original_name: payload.source_file_name || payload.version_name,
      sheets: ['normalized'],
      selected_sheet: 'normalized',
      preview: [],
      columns_info: [],
    }
    plannerSourceMode.value = 'dataset'
    plannerDatasetReference.value = payload.dataset_reference
    selectedFileId.value = ''
    selectedSheet.value = 'normalized'
    syncPlannerDefaults()
    restoreVersions(
      storageKey,
      payload.items,
      keepVersions,
    )
    if (!keepVersions) {
      versions.value = [{
        id: 'base',
        name: payload.version_name || 'Загруженный график',
        version_type: 'uploaded',
        created_at: new Date().toISOString(),
        items: cloneItems(payload.items),
      }]
      activeVersionId.value = 'base'
    }
    persistVersions()
    currentView.value = 'planner'
    showMessage('Импортированный график КРС открыт в planner.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const normalizeDataset = async () => {
  if (!uploadedFile.value?.file_id) {
    showMessage('Сначала загрузите или откройте Excel-файл.', 'error')
    return
  }
  loading.value = true
  try {
    const response = await request('/import/normalize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_id: uploadedFile.value.file_id,
        sheet_name: uploadedFile.value.selected_sheet,
        source_kind: selectedSourceKind.value,
        dataset_name: `${selectedSourceKindLabel.value} · ${uploadedFile.value.original_name}`,
        columns: normalizeColumnsPayload(),
      }),
    })
    latestNormalization.value = await response.json()
    await loadDatasets()
    await loadDatasetDetail(
      latestNormalization.value.dataset_reference.dataset_id,
      latestNormalization.value.dataset_reference.dataset_version_id,
    )
    appendLuOptionsFromPayload(latestNormalization.value.normalized_payload)
    if (selectedSourceKind.value === 'external_krs_schedule') {
      await openImportedDataset(latestNormalization.value.dataset_reference, false)
      return
    }
    showMessage('Набор данных нормализован и сохранён в базе.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const appendLuOptions = (values) => {
  const next = new Set(knownLuOptions.value)
  values.filter(Boolean).forEach((value) => next.add(String(value).trim()))
  knownLuOptions.value = [...next]
}

const appendLuOptionsFromPayload = (payload) => {
  if (!payload) return
  if (Array.isArray(payload)) {
    appendLuOptions(payload.map((item) => item?.lu_id))
    return
  }
  if (payload.schedule?.items) {
    appendLuOptions(payload.schedule.items.map((item) => item?.lu_id))
    return
  }
  if (payload.objects) {
    appendLuOptions(payload.objects.map((item) => item?.lu_id))
  }
}

const hydrateLuOptions = async () => {
  if (knownLuOptions.value.length || !datasets.value.length) return
  const candidate = datasets.value.find((item) => ['wells', 'gtm', 'external_krs_schedule'].includes(item.dataset_reference.dataset_type))
  if (!candidate) return
  try {
    const response = await request(`/datasets/${candidate.dataset_reference.dataset_id}?dataset_version_id=${encodeURIComponent(candidate.dataset_reference.dataset_version_id)}`)
    const payload = await response.json()
    appendLuOptionsFromPayload(payload.normalized_payload)
  } catch {
    // ignore optional hydration errors
  }
}

const handleDisplacementPaste = (event, startIndex) => {
  const text = event.clipboardData?.getData('text/plain')
  if (!text) return
  const values = text
    .split(/\r?\n/)
    .flatMap((line) => line.split('\t'))
    .map((value) => value.trim())
    .filter(Boolean)
  if (!values.length) return
  event.preventDefault()
  values.forEach((value, offset) => {
    const row = reservoirForm.displacementPoints[startIndex + offset]
    if (!row) return
    row.niz = value.replace(',', '.')
  })
}

const addReservoirPoint = () => reservoirForm.displacementPoints.push({ niz: '', watercut: reservoirForm.displacementPoints.length * 5 })
const removeReservoirPoint = (index) => {
  if (reservoirForm.displacementPoints.length === 1) return
  reservoirForm.displacementPoints.splice(index, 1)
}
const addBaseDeclineRow = () => reservoirForm.baseDeclineRows.push({ month_index: reservoirForm.baseDeclineRows.length + 1, decline_percent: 5 })
const removeBaseDeclineRow = (index) => {
  if (reservoirForm.baseDeclineRows.length === 1) return
  reservoirForm.baseDeclineRows.splice(index, 1)
}
const addNewWellsDeclineRow = () => reservoirForm.newWellsDeclineRows.push({
  month_index: reservoirForm.newWellsDeclineRows.length + 1,
  decline_percent: reservoirForm.newWellsDeclineRows.length < 12 ? 50 : 5,
})
const removeDeclineRow = (index) => {
  if (reservoirForm.newWellsDeclineRows.length === 1) return
  reservoirForm.newWellsDeclineRows.splice(index, 1)
}

const addEconomicsRow = () => economicsForm.rows.push({
  lu_id: '',
  net_back: '',
  oil_price: '',
  gas_price: '',
  liquid_handling_cost: '',
  water_handling_cost: '',
  gas_handling_cost: '',
  discount_rate: '',
})
const removeEconomicsRow = (index) => {
  if (economicsForm.rows.length === 1) return
  economicsForm.rows.splice(index, 1)
}

const addBrigadeCapacityRow = () => brigadesForm.capacityRows.push({ lu_id: '', month_date: '', brigade_count: '' })
const removeBrigadeCapacityRow = (index) => {
  if (brigadesForm.capacityRows.length === 1) return
  brigadesForm.capacityRows.splice(index, 1)
}
const addFailureRow = () => brigadesForm.failureRows.push({ scope_type: 'lu', lu_id: '', sloy_id: '', coefficient: '' })
const removeFailureRow = (index) => {
  if (brigadesForm.failureRows.length === 1) return
  brigadesForm.failureRows.splice(index, 1)
}
const addDurationRow = () => brigadesForm.durationRows.push({ gtm_type: '', duration_days: '' })
const removeDurationRow = (index) => {
  if (brigadesForm.durationRows.length === 1) return
  brigadesForm.durationRows.splice(index, 1)
}

const toNumberOrNull = (value) => {
  if (value === '' || value === null || value === undefined) return null
  const normalized = Number(String(value).replace(',', '.'))
  return Number.isFinite(normalized) ? normalized : null
}

const parseKeyValueLines = (value) =>
  Object.fromEntries(
    String(value || '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [key, ...rest] = line.split(':')
        return [key.trim(), toNumberOrNull(rest.join(':').trim()) ?? rest.join(':').trim()]
      })
      .filter(([key]) => key),
  )

const saveManualInputSet = async (name, payload) => {
  loading.value = true
  try {
    await request('/manual-inputs/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        payload,
      }),
    })
    await loadManualInputSets()
    showMessage(`Набор «${name}» сохранён.`, 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

const saveReservoirInputs = async () => saveManualInputSet(reservoirForm.name, {
  displacement_config: {
    lu_id: reservoirForm.selectedLu || null,
    sloy_id: reservoirForm.selectedSloy || null,
    watercut_unit: reservoirForm.watercutUnit,
    curve_points: reservoirForm.displacementPoints
      .map((item) => ({
        NIZ: toNumberOrNull(item.niz),
        watercut: toNumberOrNull(item.watercut),
      }))
      .filter((item) => item.NIZ !== null && item.watercut !== null),
  },
  decline_config: {
    decline_mode: reservoirForm.declineMode,
    lu_id: reservoirForm.selectedLu || null,
    sloy_id: reservoirForm.selectedSloy || null,
    base_monthly_decline_values: reservoirForm.baseDeclineRows
      .map((item) => ({
        month_index: toNumberOrNull(item.month_index),
        liquid_decline_factor: toNumberOrNull(item.decline_percent),
      }))
      .filter((item) => item.month_index !== null && item.liquid_decline_factor !== null),
    new_wells_monthly_decline_values: reservoirForm.newWellsDeclineRows
      .map((item) => ({
        month_index: toNumberOrNull(item.month_index),
        liquid_decline_factor: toNumberOrNull(item.decline_percent),
      }))
      .filter((item) => item.month_index !== null && item.liquid_decline_factor !== null),
  },
  metadata: {
    notes: reservoirForm.notes,
  },
})

const saveEconomicsInputs = async () => saveManualInputSet(economicsForm.name, {
  economics_config: {
    lu_items: economicsForm.rows.map((item) => ({
      lu_id: item.lu_id,
      net_back: toNumberOrNull(item.net_back),
      oil_price: toNumberOrNull(item.oil_price),
      gas_price: toNumberOrNull(item.gas_price),
      liquid_handling_cost: toNumberOrNull(item.liquid_handling_cost),
      water_handling_cost: toNumberOrNull(item.water_handling_cost),
      gas_handling_cost: toNumberOrNull(item.gas_handling_cost),
      discount_rate: toNumberOrNull(item.discount_rate),
    })).filter((item) => item.lu_id),
    gtm_costs_by_type: parseKeyValueLines(economicsForm.gtmCostsText),
    notes: economicsForm.notes,
  },
})

const saveBrigadeInputs = async () => saveManualInputSet(brigadesForm.name, {
  brigade_capacity_by_lu_config: {
    items: brigadesForm.capacityRows.map((item) => ({
      lu_id: item.lu_id,
      month_date: item.month_date,
      brigade_count: toNumberOrNull(item.brigade_count),
    })).filter((item) => item.lu_id && item.month_date && item.brigade_count !== null),
  },
  failure_coefficient_config: {
    items: brigadesForm.failureRows.map((item) => ({
      scope_type: item.scope_type,
      lu_id: item.lu_id || null,
      sloy_id: item.sloy_id || null,
      coefficient: toNumberOrNull(item.coefficient),
    })).filter((item) => item.coefficient !== null && ((item.scope_type === 'lu' && item.lu_id) || (item.scope_type === 'sloy' && item.sloy_id))),
  },
  krs_resource_config: {
    brigade_count: toNumberOrNull(brigadesForm.fallbackBrigadeCount),
    durations_by_gtm_type: Object.fromEntries(
      brigadesForm.durationRows
        .map((item) => [item.gtm_type.trim(), toNumberOrNull(item.duration_days)])
        .filter(([key, value]) => key && value !== null),
    ),
    notes: brigadesForm.notes,
  },
})

const saveOptimizerInputs = async () => saveManualInputSet(optimizerForm.name, {
  optimizer_config: {
    target_metric: optimizerForm.targetFunction,
    search_mode: optimizerForm.heuristicMode,
    build_mode: optimizerForm.buildMode,
    scenario_selection: optimizerForm.scenarioSelection,
    infrastructure_reaction_mode: optimizerForm.infraReactionMode,
    notes: optimizerForm.scenarioDescription,
    hard_constraints: {
      constraints_logic: optimizerForm.constraintsLogic,
    },
  },
})

const createVersion = () => {
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
  persistVersions()
  showMessage('Новая версия графика создана.', 'success')
}

const moveEvent = (eventId, brigade, startDate) => {
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
  persistVersions()
}

const dragStart = (event, item) => {
  if (!canEditVersion.value) return
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', item.event_id)
}

const exportVersion = async () => {
  if (!activeVersion.value) return
  try {
    const response = await request('/schedule/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        version_name: activeVersion.value.name,
        columns: { ...columns },
        items: activeVersion.value.items,
      }),
    })
    const blob = await response.blob()
    const disposition = response.headers.get('content-disposition') || ''
    const match = disposition.match(/filename="?([^\"]+)"?/i)
    const filename = match?.[1] || `${activeVersion.value.name}.xlsx`
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    showMessage('Версия графика выгружена.', 'success')
  } catch (error) {
    showMessage(error.message, 'error')
  }
}

watch(currentView, () => persistSession())
watch(activeVersionId, () => persistVersions())
watch(selectedScenarioId, async (scenarioId, previousId) => {
  if (!scenarioId || scenarioId === previousId) return
  await loadForecastScenarioDetail(scenarioId)
  persistSession()
})

onMounted(async () => {
  await loadUploadedFiles()
  await loadDatasets()
  await loadManualInputSets()
  await loadForecastScenarios()
  const session = readJson(SESSION_KEY, null)
  if (!session) return
  currentView.value = session.view || 'upload'
  if (session.selected_scenario_id) {
    selectedScenarioId.value = session.selected_scenario_id
  }
  if (session.planner_source_mode === 'dataset' && session.planner_dataset_reference?.dataset_id) {
    await openImportedDataset(session.planner_dataset_reference, true)
    return
  }
  if (!session.file_id) return
  await openFile(session.file_id, session.sheet_name || null, true)
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-top">
        <div v-if="!sidebarCollapsed" class="sidebar-copy">
          <div class="brand">WorkNotOver</div>
          <div class="brand-subtitle">Интерактивный график КРС</div>
        </div>
        <button class="icon-button" @click="sidebarCollapsed = !sidebarCollapsed">{{ sidebarCollapsed ? '→' : '←' }}</button>
      </div>

      <nav class="nav-list">
        <button class="nav-item" :class="{ active: currentView === 'upload' }" @click="currentView = 'upload'">
          <span class="nav-icon">⇪</span>
          <span v-if="!sidebarCollapsed">Исходные данные</span>
        </button>
        <button class="nav-item" :class="{ active: currentView === 'production' }" @click="currentView = 'production'">
          <span class="nav-icon">◔</span>
          <span v-if="!sidebarCollapsed">Добыча</span>
        </button>
        <button class="nav-item" :class="{ active: currentView === 'planner' }" @click="currentView = 'planner'">
          <span class="nav-icon">▦</span>
          <span v-if="!sidebarCollapsed">Планировщик КРС</span>
        </button>
      </nav>

      <div v-if="!sidebarCollapsed" class="sidebar-note">Базовая версия служит эталоном. Для перетаскивания мероприятий сначала создайте новую версию графика.</div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div class="topbar-accent"></div>
        <div>
          <h1>{{ viewTitle }}</h1>
          <p>{{ viewSubtitle }}</p>
        </div>
      </header>

      <div v-if="message" class="message" :class="messageType">{{ message }}</div>

      <section v-if="currentView === 'upload'" class="page-stack">
        <div class="input-tabs">
          <button v-for="tab in INPUT_TABS" :key="tab.id" class="input-tab" :class="{ active: inputTab === tab.id }" @click="inputTab = tab.id">{{ tab.label }}</button>
        </div>

        <template v-if="inputTab === 'upload'">
          <div class="source-kind-grid">
            <button
              v-for="option in SOURCE_KIND_OPTIONS"
              :key="option.id"
              class="source-kind-card"
              :class="{ active: selectedSourceKind === option.id }"
              @click="selectedSourceKind = option.id"
            >
              <strong>{{ option.label }}</strong>
            </button>
          </div>

          <div class="split-grid">
            <div class="panel soft">
              <h2>Текущая загрузка</h2>
              <p class="subtitle">Выбран режим: {{ selectedSourceKindLabel }}. Сначала откройте Excel, затем проверьте mapping и сохраните его как dataset.</p>

              <label class="upload-dropzone">
                <input type="file" accept=".xlsx,.xls" @change="handleFileChange" />
                <strong>Перетащите Excel-файл сюда или выберите его</strong>
                <span>Поддерживаются форматы .xlsx и .xls</span>
              </label>

              <div class="form-grid single">
                <select v-model="selectedFileId">
                  <option value="">Ранее загруженный файл</option>
                  <option v-for="item in uploadedFiles" :key="item.file_id" :value="item.file_id">{{ item.original_name }}</option>
                </select>
                <select v-model="selectedSheet" :disabled="!selectedFileId">
                  <option value="">Лист Excel</option>
                  <option v-for="sheet in (uploadedFiles.find((item) => item.file_id === selectedFileId)?.sheets || [])" :key="sheet" :value="sheet">{{ sheet }}</option>
                </select>
                <button class="button" :disabled="!selectedFileId || loading" @click="loadSourceFile(selectedFileId, selectedSheet || null)">Открыть</button>
              </div>

              <div v-if="uploadedFile" class="info-cards">
                <div class="info-card"><span>Файл</span><strong>{{ uploadedFile.original_name }}</strong></div>
                <div class="info-card"><span>Лист</span><strong>{{ uploadedFile.selected_sheet }}</strong></div>
                <div class="info-card"><span>Строк preview</span><strong>{{ uploadedFileRowCount }}</strong></div>
                <div class="info-card"><span>Тип набора</span><strong>{{ selectedSourceKind }}</strong></div>
              </div>
            </div>

            <div class="panel">
              <h2>Состояние источников</h2>
              <p class="subtitle">Реестр показывает, какие типы исходных данных уже есть в системе и готовы к сценарию.</p>
              <div class="status-grid">
                <div v-for="card in sourceKindStatusCards" :key="card.id" class="status-card" :class="{ ready: card.loaded }">
                  <span>{{ card.label }}</span>
                  <strong>{{ card.loaded ? 'Готово' : 'Не загружено' }}</strong>
                  <em>{{ card.name }}</em>
                  <small v-if="card.loaded">{{ card.rows }} строк</small>
                </div>
              </div>
            </div>
          </div>

          <div class="panel">
            <div class="toolbar between align-start">
              <div>
                <h2>Сопоставление колонок</h2>
                <p class="subtitle">Для этого типа источника выводятся только релевантные поля. Пустое значение означает автоопределение на backend.</p>
              </div>
              <div class="toolbar actions-wrap">
                <button class="button primary" :disabled="!uploadedFile || loading" @click="normalizeDataset">Нормализовать и сохранить</button>
                <button class="button ghost" :disabled="!activeItems.length" @click="currentView = 'planner'">Открыть планировщик</button>
              </div>
            </div>

            <div class="form-grid">
              <select v-for="field in sourceKindFields" :key="field" v-model="normalizeColumns[field]">
                <option value="">{{ SOURCE_KIND_FIELD_LABELS[field] }}</option>
                <option v-for="column in availableColumns" :key="`${field}-${column.name}`" :value="column.name">{{ column.name }}</option>
              </select>
            </div>
          </div>

          <div class="split-grid">
            <div v-if="uploadedFile?.preview?.length" class="panel">
              <h2>Предпросмотр исходных данных</h2>
              <div class="table-wrap preview-wrap">
                <table>
                  <thead><tr><th v-for="column in previewColumns" :key="column">{{ column }}</th></tr></thead>
                  <tbody><tr v-for="(row, index) in uploadedFile.preview" :key="index"><td v-for="column in previewColumns" :key="`${index}-${column}`">{{ row[column] }}</td></tr></tbody>
                </table>
              </div>
            </div>

            <div class="panel">
              <h2>Сохранённые datasets</h2>
              <p class="subtitle">Результаты нормализации доступны повторно. Для внешнего графика КРС можно сразу открыть planner runtime-flow.</p>
              <div class="dataset-list">
                <button
                  v-for="item in datasets"
                  :key="item.dataset_reference.dataset_id"
                  class="dataset-item"
                  :class="{ active: selectedDatasetId === item.dataset_reference.dataset_id }"
                  @click="loadDatasetDetail(item.dataset_reference.dataset_id, item.dataset_reference.dataset_version_id)"
                >
                  <strong>{{ item.dataset_reference.name }}</strong>
                  <span>{{ item.dataset_reference.dataset_type }} · {{ item.dataset_reference.row_count || 0 }} строк</span>
                </button>
                <div v-if="!datasets.length" class="empty-note">Пока нет сохранённых наборов данных.</div>
              </div>
            </div>
          </div>

          <div v-if="datasetDetail" class="panel">
            <div class="toolbar between align-start">
              <div>
                <h2>Карточка dataset</h2>
                <p class="subtitle">{{ datasetDetail.dataset_reference.name }} · {{ datasetDetail.dataset_reference.dataset_type }}</p>
              </div>
              <button
                v-if="datasetDetail.dataset_reference.dataset_type === 'external_krs_schedule'"
                class="button success"
                @click="openImportedDataset(datasetDetail.dataset_reference, false)"
              >
                Открыть в Planner
              </button>
            </div>
            <div class="info-cards">
              <div class="info-card"><span>Dataset ID</span><strong>{{ datasetDetail.dataset_reference.dataset_id }}</strong></div>
              <div class="info-card"><span>Версия</span><strong>{{ datasetDetail.dataset_reference.dataset_version_id }}</strong></div>
              <div class="info-card"><span>Формат</span><strong>{{ datasetDetail.source_format || '—' }}</strong></div>
              <div class="info-card"><span>Строк</span><strong>{{ datasetDetail.dataset_reference.row_count || 0 }}</strong></div>
            </div>
          </div>
        </template>

        <div v-else-if="inputTab === 'reservoir'" class="panel">
          <div class="toolbar between align-start">
            <div>
              <h2>Характеристики пласта</h2>
              <p class="subtitle">Лист хранит входные конфигурации для `Module B`: характеристику вытеснения и ряды снижения жидкости отдельно для `Base` и `ВНС`.</p>
            </div>
            <input v-model="reservoirForm.name" class="compact-name-input" placeholder="Название набора" />
          </div>

          <div class="form-grid">
            <select v-model="reservoirForm.selectedLu">
              <option value="">Выберите LU</option>
              <option v-for="lu in luSelectOptions" :key="lu" :value="lu">{{ lu }}</option>
            </select>
            <input v-model="reservoirForm.selectedSloy" placeholder="SLOY, если характеристика задаётся для слоя" />
          </div>

          <div class="stacked-sections">
            <div class="section-card">
              <div class="toolbar between">
                <h3>Характеристика вытеснения</h3>
                <div class="toolbar">
                  <span class="section-chip">Шаг 5%</span>
                  <button class="button ghost" @click="addReservoirPoint">Добавить точку</button>
                </div>
              </div>
              <div class="editor-table">
                <div class="editor-table-head two-cols">
                  <span>Обводнённость</span>
                  <span>NIZ</span>
                </div>
                <div v-for="(item, index) in reservoirForm.displacementPoints" :key="`disp-${index}`" class="editor-table-row two-cols">
                  <input :value="`${item.watercut}%`" readonly class="readonly-field" />
                  <div class="inline-action-field">
                    <input v-model="item.niz" placeholder="0.75" @paste="handleDisplacementPaste($event, index)" />
                    <button class="button ghost icon-only" @click="removeReservoirPoint(index)">×</button>
                  </div>
                </div>
              </div>
              <div class="helper-note">Можно вставить колонку значений `NIZ` через `Ctrl+V` в любую ячейку столбца `NIZ`.</div>
            </div>

            <div class="section-card">
              <div class="toolbar between">
                <h3>Падение жидкости во времени</h3>
                <span class="section-chip">24 месяца</span>
              </div>
              <div class="decline-grid">
                <div class="editor-table">
                  <div class="toolbar between">
                    <h4>База</h4>
                    <button class="button ghost" @click="addBaseDeclineRow">Добавить месяц</button>
                  </div>
                  <div class="editor-table-head two-cols">
                    <span>Месяц</span>
                    <span>Снижение, %/год</span>
                  </div>
                  <div v-for="(item, index) in reservoirForm.baseDeclineRows" :key="`base-decline-${index}`" class="editor-table-row two-cols">
                    <input v-model="item.month_index" type="number" min="1" placeholder="1" />
                    <div class="inline-action-field">
                      <input v-model="item.decline_percent" placeholder="5" />
                      <button class="button ghost icon-only" @click="removeBaseDeclineRow(index)">×</button>
                    </div>
                  </div>
                </div>

                <div class="editor-table">
                  <div class="toolbar between">
                    <h4>ВНС</h4>
                    <button class="button ghost" @click="addNewWellsDeclineRow">Добавить месяц</button>
                  </div>
                  <div class="editor-table-head two-cols">
                    <span>Месяц</span>
                    <span>Снижение, %/год</span>
                  </div>
                  <div v-for="(item, index) in reservoirForm.newWellsDeclineRows" :key="`new-decline-${index}`" class="editor-table-row two-cols">
                    <input v-model="item.month_index" type="number" min="1" placeholder="1" />
                    <div class="inline-action-field">
                      <input v-model="item.decline_percent" placeholder="50 / 5" />
                      <button class="button ghost icon-only" @click="removeDeclineRow(index)">×</button>
                    </div>
                  </div>
                </div>
              </div>
              <textarea v-model="reservoirForm.notes" class="text-area compact-text-area" placeholder="Примечания по пласту и допущениям"></textarea>
            </div>
          </div>

          <div class="toolbar">
            <button class="button primary" :disabled="loading" @click="saveReservoirInputs">Сохранить характеристики пласта</button>
          </div>
        </div>

        <div v-else-if="inputTab === 'economics'" class="panel">
          <div class="toolbar between align-start">
            <div>
              <h2>Экономические вводные</h2>
              <p class="subtitle">Экономика задаётся по `LU` и версионируется как отдельный набор ручных вводных.</p>
            </div>
            <input v-model="economicsForm.name" class="compact-name-input" placeholder="Название набора" />
          </div>

          <div class="section-card">
            <div class="toolbar between">
              <h3>Экономика по участкам недр</h3>
              <button class="button ghost" @click="addEconomicsRow">Добавить LU</button>
            </div>
            <div class="wide-table-wrap">
              <table class="editor-table-grid">
                <thead>
                  <tr>
                    <th>LU</th>
                    <th>Net Back</th>
                    <th>Цена нефти</th>
                    <th>Цена газа</th>
                    <th>Liquid cost</th>
                    <th>Water cost</th>
                    <th>Gas cost</th>
                    <th>Discount</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, index) in economicsForm.rows" :key="`eco-${index}`">
                    <td><input v-model="row.lu_id" placeholder="LU-01" /></td>
                    <td><input v-model="row.net_back" placeholder="12000" /></td>
                    <td><input v-model="row.oil_price" placeholder="4800" /></td>
                    <td><input v-model="row.gas_price" placeholder="900" /></td>
                    <td><input v-model="row.liquid_handling_cost" placeholder="120" /></td>
                    <td><input v-model="row.water_handling_cost" placeholder="85" /></td>
                    <td><input v-model="row.gas_handling_cost" placeholder="30" /></td>
                    <td><input v-model="row.discount_rate" placeholder="0.18" /></td>
                    <td><button class="button ghost icon-only" @click="removeEconomicsRow(index)">×</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="form-grid single">
            <textarea v-model="economicsForm.gtmCostsText" class="text-area compact-text-area" placeholder="Стоимость ГТМ по типам, по одной строке:&#10;КРС: 1500000&#10;ППД: 900000"></textarea>
            <textarea v-model="economicsForm.notes" class="text-area compact-text-area" placeholder="Примечания к экономическим вводным"></textarea>
          </div>

          <div class="toolbar">
            <button class="button primary" :disabled="loading" @click="saveEconomicsInputs">Сохранить экономические вводные</button>
          </div>
        </div>

        <div v-else-if="inputTab === 'brigades'" class="panel">
          <div class="toolbar between align-start">
            <div>
              <h2>Ограничения бригад</h2>
              <p class="subtitle">Единый лист для трёх отдельных конфигураций: количества бригад по `LU`, коэффициента отказности и длительностей работ.</p>
            </div>
            <input v-model="brigadesForm.name" class="compact-name-input" placeholder="Название набора" />
          </div>

          <div class="stacked-sections">
            <div class="section-card">
              <div class="toolbar between">
                <h3>Количество бригад по LU и месяцам</h3>
                <button class="button ghost" @click="addBrigadeCapacityRow">Добавить строку</button>
              </div>
              <div class="editor-table">
                <div class="editor-table-head three-cols">
                  <span>LU</span>
                  <span>Месяц</span>
                  <span>Бригад</span>
                </div>
                <div v-for="(item, index) in brigadesForm.capacityRows" :key="`cap-${index}`" class="editor-table-row three-cols">
                  <input v-model="item.lu_id" placeholder="LU-01" />
                  <input v-model="item.month_date" type="date" />
                  <div class="inline-action-field">
                    <input v-model="item.brigade_count" type="number" min="0" placeholder="3" />
                    <button class="button ghost icon-only" @click="removeBrigadeCapacityRow(index)">×</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="section-card">
              <div class="toolbar between">
                <h3>Коэффициент отказности</h3>
                <button class="button ghost" @click="addFailureRow">Добавить коэффициент</button>
              </div>
              <div class="editor-table">
                <div class="editor-table-head four-cols">
                  <span>Область</span>
                  <span>LU</span>
                  <span>SLOY</span>
                  <span>Коэффициент</span>
                </div>
                <div v-for="(item, index) in brigadesForm.failureRows" :key="`fail-${index}`" class="editor-table-row four-cols">
                  <select v-model="item.scope_type">
                    <option value="lu">LU</option>
                    <option value="sloy">SLOY</option>
                  </select>
                  <input v-model="item.lu_id" :disabled="item.scope_type !== 'lu'" placeholder="LU-01" />
                  <input v-model="item.sloy_id" :disabled="item.scope_type !== 'sloy'" placeholder="SLOY-A1" />
                  <div class="inline-action-field">
                    <input v-model="item.coefficient" placeholder="0.12" />
                    <button class="button ghost icon-only" @click="removeFailureRow(index)">×</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="section-card">
              <div class="toolbar between">
                <h3>Длительности мероприятий</h3>
                <button class="button ghost" @click="addDurationRow">Добавить тип работ</button>
              </div>
              <div class="editor-table">
                <div class="editor-table-head two-cols">
                  <span>Тип ГТМ</span>
                  <span>Длительность, дни</span>
                </div>
                <div v-for="(item, index) in brigadesForm.durationRows" :key="`dur-${index}`" class="editor-table-row two-cols">
                  <input v-model="item.gtm_type" placeholder="КРС / ППД / ГРП" />
                  <div class="inline-action-field">
                    <input v-model="item.duration_days" type="number" min="1" placeholder="12" />
                    <button class="button ghost icon-only" @click="removeDurationRow(index)">×</button>
                  </div>
                </div>
              </div>
              <div class="form-grid single">
                <input v-model="brigadesForm.fallbackBrigadeCount" placeholder="Глобальный fallback по бригадам" />
                <textarea v-model="brigadesForm.notes" class="text-area compact-text-area" placeholder="Примечания к ресурсным ограничениям"></textarea>
              </div>
            </div>
          </div>

          <div class="toolbar">
            <button class="button primary" :disabled="loading" @click="saveBrigadeInputs">Сохранить ограничения бригад</button>
          </div>
        </div>

        <div v-else class="panel">
          <div class="toolbar between align-start">
            <div>
              <h2>Схема работы оптимизатора</h2>
              <p class="subtitle">Лист оркестрации `Module D`: как строить график, как выбирать сценарий и как реагировать на ограничения.</p>
            </div>
            <input v-model="optimizerForm.name" class="compact-name-input" placeholder="Название набора" />
          </div>

          <div class="form-grid">
            <select v-model="optimizerForm.buildMode">
              <option value="build_only">Только построение графика</option>
              <option value="build_and_optimize">Построение + оптимизация</option>
            </select>
            <select v-model="optimizerForm.targetFunction">
              <option value="max_npv">Максимум NPV</option>
              <option value="max_oil">Максимум нефти</option>
              <option value="min_delay">Минимум задержки запуска</option>
            </select>
            <select v-model="optimizerForm.scenarioSelection">
              <option value="best_feasible">Лучший допустимый сценарий</option>
              <option value="best_score">Лучший score с предупреждениями</option>
            </select>
            <select v-model="optimizerForm.infraReactionMode">
              <option value="hard_stop">Жёсткая остановка при нарушении</option>
              <option value="warn_and_rank">Предупреждать и ранжировать</option>
            </select>
            <select v-model="optimizerForm.heuristicMode">
              <option value="guided_search">Guided search</option>
              <option value="full_enumeration">Полный перебор</option>
              <option value="priority_rules">Приоритетные правила</option>
            </select>
            <textarea v-model="optimizerForm.scenarioDescription" class="text-area compact-text-area" placeholder="Описание сценария оптимизации"></textarea>
            <textarea v-model="optimizerForm.constraintsLogic" class="text-area compact-text-area" placeholder="Логика реакции на ограничения инфраструктуры и бригад"></textarea>
          </div>

          <div class="optimizer-status">
            <span>Лист сохраняет конфиг запуска и стратегию отбора, но не реализует оптимизатор в UI.</span>
          </div>

          <div class="toolbar">
            <button class="button primary" :disabled="loading" @click="saveOptimizerInputs">Сохранить схему оптимизатора</button>
          </div>
        </div>

        <div v-if="manualInputSets.length && inputTab !== 'upload'" class="panel">
          <h2>Сохранённые ручные вводные</h2>
          <div class="status-grid manual-grid">
            <div v-for="item in manualInputSummaryCards" :key="item.id" class="status-card compact" :class="{ ready: item.loaded }">
              <span>{{ item.label }}</span>
              <strong>{{ item.loaded ? 'Сохранено' : 'Пока пусто' }}</strong>
              <em>{{ item.name }}</em>
            </div>
          </div>
          <div class="dataset-list">
            <div v-for="item in manualInputSets" :key="item.reference.manual_input_set_id" class="dataset-item static">
              <strong>{{ item.reference.name }}</strong>
              <span>{{ item.reference.manual_input_set_id }}</span>
            </div>
          </div>
        </div>
      </section>

      <section v-else-if="currentView === 'production'" class="page-stack production-stack">
        <div v-if="!forecastScenarioOptions.length" class="panel empty-state">
          Сначала выполните расчёт сценария прогноза через backend `Module B`. После этого здесь появятся выбор сценария, накопительная диаграмма добычи и иерархический анализ.
        </div>

        <template v-else>
          <div class="panel soft production-toolbar-panel">
            <div class="toolbar between align-start">
              <div>
                <h2>Сценарий расчёта</h2>
                <p class="subtitle">Выберите сохранённый сценарий прогноза и отберите группы в таблице ниже, чтобы накопительная диаграмма обновилась только по ним.</p>
              </div>
              <div class="toolbar actions-wrap">
                <select v-model="selectedScenarioId" class="compact-select-inline production-scenario-select">
                  <option v-for="item in forecastScenarioOptions" :key="item.scenario_id" :value="item.scenario_id">
                    {{ item.name }} · {{ item.forecast_start_date }} → {{ item.forecast_end_date }}
                  </option>
                </select>
                <button class="button ghost" :disabled="loading" @click="loadForecastScenarios">Обновить</button>
                <button class="button ghost" :disabled="!selectedProductionKeys.length" @click="clearProductionSelection">Сбросить выбор</button>
              </div>
            </div>

            <div class="info-cards production-info-cards">
              <div class="info-card">
                <span>Выбранный контур</span>
                <strong>{{ productionSelectedLabel }}</strong>
              </div>
              <div class="info-card">
                <span>Период</span>
                <strong>{{ selectedForecastScenarioMeta?.forecast_start_date || '—' }} → {{ selectedForecastScenarioMeta?.forecast_end_date || '—' }}</strong>
              </div>
              <div class="info-card">
                <span>Создан</span>
                <strong>{{ formatCompactDateTime(selectedForecastScenarioMeta?.latest_result_created_at || selectedForecastScenarioMeta?.created_at) }}</strong>
              </div>
              <div class="info-card">
                <span>Статус</span>
                <strong>{{ selectedForecastScenarioMeta?.status || '—' }}</strong>
              </div>
            </div>
          </div>

          <div v-if="forecastScenarioDetail" class="stats-grid production-stats-grid">
            <div class="stat-card"><span>Нефть</span><strong>{{ selectedProductionTotals.oil.toFixed(1) }}</strong></div>
            <div class="stat-card"><span>Жидкость</span><strong>{{ selectedProductionTotals.liquid.toFixed(1) }}</strong></div>
            <div class="stat-card"><span>Газ</span><strong>{{ selectedProductionTotals.gas.toFixed(1) }}</strong></div>
          </div>

          <div v-if="forecastScenarioDetail" class="panel production-chart-panel">
            <div class="toolbar between align-start">
              <div>
                <h2>Накопительная добыча нефти</h2>
                <p class="subtitle">Категории `БАЗА`, `ГТМ`, `ВНС` отображаются накопительно на весь период расчёта. При выборе нескольких групп в таблице ниже диаграмма пересчитывается только по их скважинам.</p>
              </div>
              <div class="prefix-legend production-legend">
                <span v-for="item in productionChartLegend" :key="item.key" class="prefix-chip production-chip">
                  <i :style="{ background: item.color }"></i>
                  {{ item.label }} · {{ item.value.toFixed(1) }}
                </span>
              </div>
            </div>

            <div v-if="productionSeries.length" class="production-chart-wrap">
              <div class="production-chart-scroll">
                <svg
                  class="production-chart-svg"
                  :viewBox="`0 0 ${productionChartWidth} ${PRODUCTION_CHART_HEIGHT + 32}`"
                  preserveAspectRatio="none"
                >
                  <g>
                    <path
                      v-for="area in productionStackedPaths"
                      :key="area.key"
                      :d="area.path"
                      :fill="area.color"
                      class="production-area-path"
                    />
                    <path :d="productionTotalLine" class="production-total-line" />
                  </g>
                  <g class="production-axis">
                    <line
                      v-for="label in productionAxisLabels"
                      :key="`tick-${label.key}`"
                      :x1="label.left"
                      :x2="label.left"
                      y1="0"
                      :y2="PRODUCTION_CHART_HEIGHT"
                      class="production-grid-line"
                    />
                  </g>
                  <g>
                    <text
                      v-for="label in productionAxisLabels"
                      :key="label.key"
                      :x="label.left"
                      :y="PRODUCTION_CHART_HEIGHT + 18"
                      text-anchor="middle"
                      class="production-axis-label"
                    >
                      {{ formatDateCell(label.date) }}
                    </text>
                  </g>
                </svg>
              </div>
            </div>
            <div v-else class="empty-note">Для выбранной группы нет точек профиля.</div>
          </div>

          <div v-if="forecastScenarioDetail" class="panel">
            <div class="toolbar between align-start">
              <div>
                <h2>Иерархия добычи</h2>
                <p class="subtitle">Кликайте по строкам, чтобы собрать одну или несколько групп. Поддерживается путь `Итого → LU → SLOY → куст → скважина`.</p>
              </div>
              <div class="notice production-notice">
                {{ selectedProductionKeys.length ? `Выбрано групп: ${selectedProductionKeys.length}` : 'Показан весь сценарий' }}
              </div>
            </div>

            <div class="table-wrap">
              <table class="production-table">
                <thead>
                  <tr>
                    <th>Группа</th>
                    <th>Тип</th>
                    <th>Скважин</th>
                    <th>Нефть</th>
                    <th>Жидкость</th>
                    <th>Газ</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in productionHierarchy.rows"
                    :key="row.key"
                    class="production-row"
                    :class="{ selected: selectedProductionKeys.includes(row.key) || (!selectedProductionKeys.length && row.key === 'total') }"
                    @click="toggleProductionNode(row.key)"
                  >
                    <td>
                      <div class="production-label" :style="{ '--depth': row.depth }">
                        <span class="production-bullet"></span>
                        <strong>{{ row.label }}</strong>
                      </div>
                    </td>
                    <td>{{ productionTypeLabel(row) }}</td>
                    <td>{{ row.wellCount }}</td>
                    <td>{{ row.totals.oil.toFixed(1) }}</td>
                    <td>{{ row.totals.liquid.toFixed(1) }}</td>
                    <td>{{ row.totals.gas.toFixed(1) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </section>

      <section v-else-if="currentView === 'planner'" class="page-stack planner-stack">
        <div v-if="!activeItems.length" class="panel empty-state">Сначала загрузите внешний график КРС в разделе «Исходные данные» или откройте уже импортированный dataset. После этого здесь появятся диаграмма Ганта, версии графика и аналитика приростов.</div>

        <template v-else>
          <div class="stats-grid">
            <div class="stat-card"><span>Активная версия</span><strong>{{ activeVersion?.name }}</strong></div>
            <div class="stat-card"><span>Мероприятий</span><strong>{{ visibleItems.length }}</strong></div>
            <div class="stat-card"><span>Суммарный прирост Qн</span><strong>{{ totalIncrement.toFixed(1) }}</strong></div>
          </div>

          <div class="panel soft">
            <div class="toolbar between align-start">
              <div>
                <h2>Версии графика</h2>
                <p class="subtitle">Создайте новую версию, чтобы переносить мероприятия между датами и бригадами без изменения эталонного плана.</p>
              </div>
              <div class="toolbar actions-wrap">
                <select v-model="activeVersionId"><option v-for="version in versions" :key="version.id" :value="version.id">{{ version.name }}</option></select>
                <button class="button primary" @click="createVersion">Создать версию</button>
                <button class="button success" @click="exportVersion">Выгрузить Excel</button>
              </div>
            </div>
            <div class="notice">{{ canEditVersion ? 'Редактирование активно: перетаскивайте карточки мероприятий по строкам бригад и по датам.' : 'Редактирование выключено: сначала создайте новую версию графика.' }}</div>
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
                    <svg v-if="cumulativeIncrementSeries.length" class="chart-line-overlay" :viewBox="`0 0 ${Math.max(ganttDates.length * timelineDayWidth, 1)} ${CHART_PLOT_HEIGHT}`" preserveAspectRatio="none">
                      <polyline :points="cumulativeLinePoints" class="chart-cumulative-line" />
                    </svg>
                    <div
                      v-for="point in cumulativeLineLabels"
                      :key="`cum-${point.date}`"
                      class="chart-cumulative-label"
                      :style="{
                        left: `${point.x}px`,
                        top: `${CHART_PLOT_HEIGHT - (point.total / cumulativeIncrementMax) * CHART_PLOT_HEIGHT - 14}px`,
                      }"
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
                              :style="{
                                background: item.color,
                                flex: `${Math.max(item.value, 1)} 1 0`,
                                opacity: gtmOpacity(item),
                              }"
                            >
                            </div>
                          </div>
                        </div>
                      </div>
                      <div class="chart-zeroes">
                        <div v-for="item in group.zero" :key="`${item.event_id}-zero`" class="summary-dot" :class="{ ppd: item.is_ppd }" :style="item.is_ppd ? {} : { background: item.color, opacity: gtmOpacity(item) }" :title="`${item.well} · ${item.is_ppd ? '0 / ППД' : '0 / без прироста'} · ${item.planned_work}`"></div>
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
                      <div v-for="date in ganttDates" :key="`${row.brigade}-${date}`" class="gantt-drop-cell" :class="{ editable: canEditVersion }" @dragover.prevent @drop="moveEvent($event.dataTransfer.getData('text/plain'), row.brigade, date)"></div>
                    </div>
                    <div
                      v-for="item in row.bars"
                      :key="item.event_id"
                      class="gantt-bar"
                      :class="{ readonly: !canEditVersion }"
                      :style="{
                        left: `calc(${item.startOffset} * var(--day-width))`,
                        width: `calc(${item.visibleDurationDays} * var(--day-width))`,
                        top: `calc(${item.lane} * var(--lane-height))`,
                        background: item.color,
                        opacity: gtmOpacity(item),
                      }"
                      :draggable="canEditVersion"
                      @dragstart="dragStart($event, item)"
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
