<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8010/api'
const SESSION_KEY = 'worknotover-krs-session'
const VERSIONS_KEY = 'worknotover-krs-versions'

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

const columns = reactive({
  brigade: '',
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

const formatDateLabel = (value) => {
  const parsed = parseIsoDate(value)
  return parsed ? new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit' }).format(parsed) : ''
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

const availableColumns = computed(() => uploadedFile.value?.columns_info || [])
const activeVersion = computed(() => versions.value.find((version) => version.id === activeVersionId.value) || versions.value[0] || null)
const activeItems = computed(() => activeVersion.value?.items || [])
const canEditVersion = computed(() => activeVersionId.value !== 'base')
const totalIncrement = computed(() => activeItems.value.reduce((sum, item) => sum + (item.increment && item.increment > 0 ? Number(item.increment) : 0), 0))
const zeroCount = computed(() => activeItems.value.filter((item) => !item.increment || item.increment <= 0).length)
const ppdZeroCount = computed(() => activeItems.value.filter((item) => (!item.increment || item.increment <= 0) && item.is_ppd).length)
const sortedSummary = computed(() => [...activeItems.value].sort((left, right) => left.start_date.localeCompare(right.start_date) || left.brigade.localeCompare(right.brigade) || left.well.localeCompare(right.well)))

const scheduleBounds = computed(() => {
  if (!activeItems.value.length) return { min: null, max: null }
  const min = activeItems.value.reduce((acc, item) => (!acc || item.start_date < acc ? item.start_date : acc), null)
  const max = activeItems.value.reduce((acc, item) => (!acc || item.end_date > acc ? item.end_date : acc), null)
  return { min, max }
})

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

const timelineDayWidth = computed(() => {
  if (!ganttDates.value.length) return 10
  return Math.max(6, Math.min(14, Math.floor(960 / ganttDates.value.length)))
})

const ganttRows = computed(() => {
  const byBrigade = new Map()
  activeItems.value.forEach((item) => {
    if (!byBrigade.has(item.brigade)) byBrigade.set(item.brigade, [])
    byBrigade.get(item.brigade).push(item)
  })

  return [...byBrigade.entries()]
    .sort((a, b) => a[0].localeCompare(b[0], 'ru'))
    .map(([brigade, items]) => {
      const sorted = [...items].sort((a, b) => a.start_date.localeCompare(b.start_date) || a.well.localeCompare(b.well, 'ru'))
      const laneEnds = []
      const bars = sorted.map((item) => {
        const start = diffDays(scheduleBounds.value.min, item.start_date)
        const end = diffDays(scheduleBounds.value.min, item.end_date)
        let lane = laneEnds.findIndex((laneEnd) => start > laneEnd)
        if (lane === -1) {
          lane = laneEnds.length
          laneEnds.push(end)
        } else {
          laneEnds[lane] = end
        }
        return { ...item, lane, startOffset: start }
      })
      return { brigade, laneCount: Math.max(laneEnds.length, 1), bars }
    })
})

const chartMax = computed(() => Math.max(...activeItems.value.map((item) => (item.increment && item.increment > 0 ? Number(item.increment) : 0)), 10))
const incrementTimeline = computed(() => {
  const laneEnds = []
  const countsByDate = new Map()
  const items = [...activeItems.value]
    .sort((a, b) => a.end_date.localeCompare(b.end_date) || a.brigade.localeCompare(b.brigade, 'ru') || a.well.localeCompare(b.well, 'ru'))
    .map((item) => {
      const endOffset = diffDays(scheduleBounds.value.min, item.end_date)
      const virtualStart = Math.max(endOffset - 1, 0)
      let lane = laneEnds.findIndex((laneEnd) => virtualStart > laneEnd)
      if (lane === -1) {
        lane = laneEnds.length
        laneEnds.push(endOffset)
      } else {
        laneEnds[lane] = endOffset
      }
      const sameDateCount = countsByDate.get(item.end_date) || 0
      countsByDate.set(item.end_date, sameDateCount + 1)
      return { ...item, lane, endOffset, colorIndex: sameDateCount }
    })

  const totalsByDate = items.reduce((acc, item) => {
    acc.set(item.end_date, (acc.get(item.end_date) || 0) + 1)
    return acc
  }, new Map())

  const palette = ['#2f80ff', '#35b36b', '#f59e0b', '#8b5cf6', '#ef4444', '#14b8a6']

  return {
    laneCount: Math.max(laneEnds.length, 1),
    items: items.map((item) => ({
      ...item,
      color: palette[item.colorIndex % palette.length],
      clusterOffset: item.colorIndex - (totalsByDate.get(item.end_date) - 1) / 2,
    })),
  }
})
const previewColumns = computed(() => Object.keys(uploadedFile.value?.preview?.[0] || {}))

const syncColumns = (nextColumns) => {
  Object.assign(columns, {
    brigade: nextColumns?.brigade || '',
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
        <button class="icon-button" @click="sidebarCollapsed = !sidebarCollapsed">
          {{ sidebarCollapsed ? '→' : '←' }}
        </button>
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

      <div v-if="!sidebarCollapsed" class="sidebar-note">
        Базовая версия служит эталоном. Для перетаскивания мероприятий сначала создайте новую версию графика.
      </div>
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
              <div class="info-card">
                <span>Файл</span>
                <strong>{{ uploadedFile.original_name }}</strong>
              </div>
              <div class="info-card">
                <span>Лист</span>
                <strong>{{ uploadedFile.selected_sheet }}</strong>
              </div>
              <div class="info-card">
                <span>Мероприятий</span>
                <strong>{{ activeItems.length }}</strong>
              </div>
              <div class="info-card">
                <span>Период</span>
                <strong>{{ scheduleBounds.min ? `${formatDateCell(scheduleBounds.min)} — ${formatDateCell(scheduleBounds.max)}` : '—' }}</strong>
              </div>
            </div>
          </div>

          <div class="panel">
            <h2>Сопоставление колонок</h2>
            <p class="subtitle">Сервис пытается найти нужные поля автоматически, но вы всегда можете выбрать реальные колонки вручную.</p>

            <div class="form-grid">
              <select v-model="columns.brigade">
                <option value="">Бригада</option>
                <option v-for="column in availableColumns" :key="`brigade-${column.name}`" :value="column.name">{{ column.name }}</option>
              </select>
              <select v-model="columns.well">
                <option value="">Скв.</option>
                <option v-for="column in availableColumns" :key="`well-${column.name}`" :value="column.name">{{ column.name }}</option>
              </select>
              <select v-model="columns.start_date">
                <option value="">Дата начала (план)</option>
                <option v-for="column in availableColumns" :key="`start-${column.name}`" :value="column.name">{{ column.name }}</option>
              </select>
              <select v-model="columns.end_date">
                <option value="">Заверш рем (план)</option>
                <option v-for="column in availableColumns" :key="`end-${column.name}`" :value="column.name">{{ column.name }}</option>
              </select>
              <select v-model="columns.increment">
                <option value="">Qн, тн/сут</option>
                <option v-for="column in availableColumns" :key="`increment-${column.name}`" :value="column.name">{{ column.name }}</option>
              </select>
              <select v-model="columns.planned_work">
                <option value="">Планируемый объем работ</option>
                <option v-for="column in availableColumns" :key="`work-${column.name}`" :value="column.name">{{ column.name }}</option>
              </select>
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
              <thead>
                <tr>
                  <th v-for="column in previewColumns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, index) in uploadedFile.preview" :key="index">
                  <td v-for="column in previewColumns" :key="`${index}-${column}`">{{ row[column] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section v-else class="page-stack planner-stack">
        <div v-if="!activeItems.length" class="panel empty-state">
          Сначала загрузите график КРС на вкладке «Загрузка графика». После этого здесь появятся диаграмма Ганта, версии графика и аналитика приростов.
        </div>

        <template v-else>
          <div class="stats-grid">
            <div class="stat-card">
              <span>Активная версия</span>
              <strong>{{ activeVersion?.name }}</strong>
            </div>
            <div class="stat-card">
              <span>Мероприятий</span>
              <strong>{{ activeItems.length }}</strong>
            </div>
            <div class="stat-card">
              <span>Суммарный прирост Qн</span>
              <strong>{{ totalIncrement.toFixed(1) }}</strong>
            </div>
          </div>

          <div class="panel soft">
            <div class="toolbar between align-start">
              <div>
                <h2>Версии графика</h2>
                <p class="subtitle">Создайте новую версию, чтобы переносить мероприятия между датами и бригадами без изменения эталонного плана.</p>
              </div>
              <div class="toolbar actions-wrap">
                <select v-model="activeVersionId">
                  <option v-for="version in versions" :key="version.id" :value="version.id">{{ version.name }}</option>
                </select>
                <button class="button primary" @click="createVersion">Создать версию</button>
                <button class="button success" @click="exportVersion">Выгрузить Excel</button>
              </div>
            </div>
            <div class="notice">
              {{ canEditVersion ? 'Редактирование активно: перетаскивайте карточки мероприятий по строкам бригад и по датам.' : 'Редактирование выключено: сначала создайте новую версию графика.' }}
            </div>
          </div>

          <div class="panel planner-panel">
            <div class="section-head">
              <div>
                <h2>Лента приростов и диаграмма Ганта</h2>
                <p class="subtitle">Приросты и безприростные мероприятия стоят на дате завершения ремонта, а ниже остаётся тот же календарь для строк бригад.</p>
              </div>
              <div class="legend">
                <span class="legend-item"><i class="legend-swatch"></i> Ремонт с приростом</span>
                <span class="legend-item"><i class="legend-swatch zero"></i> Без прироста</span>
                <span class="legend-item"><i class="legend-swatch ppd"></i> Перевод в ППД</span>
              </div>
            </div>

            <div class="gantt-wrap compact-board">
              <div class="gantt-board" :style="{ '--day-count': ganttDates.length, '--summary-lane-count': incrementTimeline.laneCount, '--day-width': `${timelineDayWidth}px` }">
                <div class="gantt-header gantt-grid month-grid">
                  <div class="gantt-corner">Месяц</div>
                  <div
                    v-for="segment in monthSegments"
                    :key="segment.key"
                    class="gantt-month"
                    :style="{ gridColumn: `span ${segment.span}` }"
                  >
                    {{ segment.label }}
                  </div>
                </div>

                <div class="gantt-header gantt-grid day-grid">
                  <div class="gantt-corner">День</div>
                  <div v-for="date in ganttDates" :key="date" class="gantt-date">{{ formatDayNumber(date) }}</div>
                </div>

                <div class="gantt-grid summary-row" :style="{ '--lane-count': incrementTimeline.laneCount }">
                  <div class="summary-side">
                    <strong>Приросты</strong>
                    <span>Столбец стоит на дате завершения.</span>
                    <div class="summary-pills">
                      <span class="pill red">{{ zeroCount }} без прироста</span>
                      <span class="pill blue">{{ ppdZeroCount }} ППД</span>
                    </div>
                  </div>
                  <div class="summary-track">
                    <div
                      v-for="item in incrementTimeline.items"
                      :key="`summary-${item.event_id}`"
                      class="summary-point"
                      :class="{ zero: !item.has_increment, ppd: item.is_ppd }"
                      :style="{
                        left: `calc(${item.endOffset} * var(--day-width) + (var(--day-width) / 2) + ${item.clusterOffset * 8}px - 13px)`,
                        top: `calc(${item.lane} * var(--summary-lane-height) + 6px)`,
                      }"
                      :title="`${item.well} · ${formatIncrement(item.increment)} · ${item.planned_work}`"
                    >
                      <div class="summary-marker">
                        <div
                          v-if="item.increment && item.increment > 0"
                          class="summary-bar"
                          :style="{ height: `${Math.max((Number(item.increment) / chartMax) * 34, 4)}px`, background: item.color }"
                        ></div>
                        <div v-else class="summary-dot" :class="{ ppd: item.is_ppd }" :style="item.is_ppd ? {} : { background: item.color }"></div>
                      </div>
                      <div class="summary-value">{{ formatIncrement(item.increment) }}</div>
                    </div>
                  </div>
                </div>

                <div
                  v-for="row in ganttRows"
                  :key="row.brigade"
                  class="gantt-grid gantt-row"
                  :style="{ '--lane-count': row.laneCount }"
                >
                  <div class="gantt-brigade">{{ row.brigade }}</div>
                  <div class="gantt-track">
                    <div class="gantt-drop-grid">
                      <div
                        v-for="date in ganttDates"
                        :key="`${row.brigade}-${date}`"
                        class="gantt-drop-cell"
                        :class="{ editable: canEditVersion }"
                        @dragover.prevent
                        @drop="moveEvent($event.dataTransfer.getData('text/plain'), row.brigade, date)"
                      ></div>
                    </div>

                    <div
                      v-for="item in row.bars"
                      :key="item.event_id"
                      class="gantt-bar"
                      :class="{ zero: !item.has_increment, ppd: item.is_ppd, readonly: !canEditVersion }"
                      :style="{
                        left: `calc(${item.startOffset} * var(--day-width))`,
                        width: `calc(${item.duration_days} * var(--day-width) - 8px)`,
                        top: `calc(${item.lane} * var(--lane-height) + 8px)`,
                      }"
                      :draggable="canEditVersion"
                      @dragstart="dragStart($event, item)"
                    >
                      <strong>{{ item.well }}</strong>
                      <span>{{ formatIncrement(item.increment) }} · {{ item.planned_work }}</span>
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
