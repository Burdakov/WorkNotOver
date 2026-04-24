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

const columns = reactive({
  brigade: '',
  area: '',
  well: '',
  start_date: '',
  end_date: '',
  increment: '',
  planned_work: '',
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
  if (!uploadedFile.value?.file_id) return
  writeJson(SESSION_KEY, {
    file_id: uploadedFile.value.file_id,
    sheet_name: uploadedFile.value.selected_sheet,
    columns: { ...columns },
    view: currentView.value,
    active_version_id: activeVersionId.value,
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

const openFile = async (fileId, sheetName = null, keepVersions = true) => {
  loading.value = true
  try {
    const query = sheetName ? `?sheet_name=${encodeURIComponent(sheetName)}` : ''
    const response = await request(`/files/${fileId}${query}`)
    uploadedFile.value = await response.json()
    selectedFileId.value = uploadedFile.value.file_id
    selectedSheet.value = uploadedFile.value.selected_sheet
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
    await parseSchedule(null, false)
    await loadUploadedFiles()
    currentView.value = 'planner'
    showMessage('Excel загружен и разобран.', 'success')
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

onMounted(async () => {
  await loadUploadedFiles()
  const session = readJson(SESSION_KEY, null)
  if (!session?.file_id) return
  currentView.value = session.view || 'upload'
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
          <span v-if="!sidebarCollapsed">Загрузка графика</span>
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
          <h1>{{ currentView === 'upload' ? 'Загрузка графика КРС' : 'Планировщик КРС' }}</h1>
          <p>Светлый рабочий интерфейс для загрузки, редактирования версий, анализа приростов и последующей выгрузки обновлённого графика.</p>
        </div>
      </header>

      <div v-if="message" class="message" :class="messageType">{{ message }}</div>

      <section v-if="currentView === 'upload'" class="page-stack">
        <div class="split-grid">
          <div class="panel soft">
            <h2>Источник данных</h2>
            <p class="subtitle">Загрузите Excel-файл с графиком КРС или откройте уже сохранённый график из сервиса.</p>

            <label class="upload-dropzone">
              <input type="file" accept=".xlsx,.xls" @change="handleFileChange" />
              <strong>Перетащите Excel-файл сюда или выберите его</strong>
              <span>Поддерживаются форматы .xlsx и .xls</span>
            </label>

            <div class="form-grid single">
              <select v-model="selectedFileId">
                <option value="">Сохранённый график</option>
                <option v-for="item in uploadedFiles" :key="item.file_id" :value="item.file_id">{{ item.original_name }}</option>
              </select>
              <select v-model="selectedSheet" :disabled="!selectedFileId">
                <option value="">Лист Excel</option>
                <option v-for="sheet in (uploadedFiles.find((item) => item.file_id === selectedFileId)?.sheets || [])" :key="sheet" :value="sheet">{{ sheet }}</option>
              </select>
              <button class="button" :disabled="!selectedFileId || loading" @click="openFile(selectedFileId, selectedSheet || null, true)">Открыть</button>
            </div>

            <div v-if="uploadedFile" class="info-cards">
              <div class="info-card"><span>Файл</span><strong>{{ uploadedFile.original_name }}</strong></div>
              <div class="info-card"><span>Лист</span><strong>{{ uploadedFile.selected_sheet }}</strong></div>
            <div class="info-card"><span>Мероприятий</span><strong>{{ visibleItems.length }}</strong></div>
              <div class="info-card"><span>Период</span><strong>{{ scheduleBounds.min ? `${formatDateCell(scheduleBounds.min)} — ${formatDateCell(scheduleBounds.max)}` : '—' }}</strong></div>
            </div>
          </div>

          <div class="panel">
            <h2>Сопоставление колонок</h2>
            <p class="subtitle">Сервис пытается найти нужные поля автоматически, но вы всегда можете выбрать реальные колонки вручную.</p>

            <div class="form-grid">
              <select v-model="columns.brigade"><option value="">Бригада</option><option v-for="column in availableColumns" :key="`brigade-${column.name}`" :value="column.name">{{ column.name }}</option></select>
              <select v-model="columns.area"><option value="">Участок</option><option v-for="column in availableColumns" :key="`area-${column.name}`" :value="column.name">{{ column.name }}</option></select>
              <select v-model="columns.well"><option value="">Скв.</option><option v-for="column in availableColumns" :key="`well-${column.name}`" :value="column.name">{{ column.name }}</option></select>
              <select v-model="columns.start_date"><option value="">Дата начала (план)</option><option v-for="column in availableColumns" :key="`start-${column.name}`" :value="column.name">{{ column.name }}</option></select>
              <select v-model="columns.end_date"><option value="">Заверш рем (план)</option><option v-for="column in availableColumns" :key="`end-${column.name}`" :value="column.name">{{ column.name }}</option></select>
              <select v-model="columns.increment"><option value="">Qн, тн/сут</option><option v-for="column in availableColumns" :key="`increment-${column.name}`" :value="column.name">{{ column.name }}</option></select>
              <select v-model="columns.planned_work"><option value="">Планируемый объем работ</option><option v-for="column in availableColumns" :key="`work-${column.name}`" :value="column.name">{{ column.name }}</option></select>
            </div>

            <div class="toolbar">
              <button class="button primary" :disabled="!uploadedFile || loading" @click="applyColumnMapping">Применить сопоставление</button>
              <button class="button ghost" :disabled="!uploadedFile" @click="currentView = 'planner'">Открыть планировщик</button>
            </div>
          </div>
        </div>

        <div v-if="uploadedFile?.preview?.length" class="panel">
          <h2>Предпросмотр исходных данных</h2>
          <div class="table-wrap preview-wrap">
            <table>
              <thead><tr><th v-for="column in previewColumns" :key="column">{{ column }}</th></tr></thead>
              <tbody><tr v-for="(row, index) in uploadedFile.preview" :key="index"><td v-for="column in previewColumns" :key="`${index}-${column}`">{{ row[column] }}</td></tr></tbody>
            </table>
          </div>
        </div>
      </section>

      <section v-else class="page-stack planner-stack">
        <div v-if="!activeItems.length" class="panel empty-state">Сначала загрузите график КРС на вкладке «Загрузка графика». После этого здесь появятся диаграмма Ганта, версии графика и аналитика приростов.</div>

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
