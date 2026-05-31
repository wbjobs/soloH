<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Search, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-vue-next'

interface Column<T> {
  key: keyof T | string
  label: string
  sortable?: boolean
  width?: string
  align?: 'left' | 'center' | 'right'
  render?: (row: T, index: number) => string | number | unknown
  formatter?: (value: unknown) => string
}

interface Props<T> {
  columns: Column<T>[]
  data: T[]
  selectable?: boolean
  searchable?: boolean
  searchFields?: (keyof T)[]
  pageSize?: number
  loading?: boolean
}

const props = withDefaults(defineProps<Props<any>>(), {
  selectable: false,
  searchable: false,
  pageSize: 10,
  loading: false
})

const emit = defineEmits<{
  (e: 'row-click', row: any, index: number): void
  (e: 'selection-change', selected: any[]): void
  (e: 'sort-change', key: string, direction: 'asc' | 'desc' | null): void
}>()

const searchQuery = ref('')
const currentPage = ref(1)
const sortKey = ref<string | null>(null)
const sortDirection = ref<'asc' | 'desc' | null>(null)
const selectedRows = ref<Set<number>>(new Set())

const filteredData = computed(() => {
  let result = [...props.data]

  if (props.searchable && searchQuery.value && props.searchFields) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(row =>
      props.searchFields!.some(field =>
        String(row[field]).toLowerCase().includes(query)
      )
    )
  }

  if (sortKey.value && sortDirection.value) {
    result.sort((a, b) => {
      const aVal = a[sortKey.value!]
      const bVal = b[sortKey.value!]
      if (sortDirection.value === 'asc') {
        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
      }
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
    })
  }

  return result
})

const totalPages = computed(() => Math.ceil(filteredData.value.length / props.pageSize))

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * props.pageSize
  return filteredData.value.slice(start, start + props.pageSize)
})

const isAllSelected = computed(() => {
  return paginatedData.value.length > 0 &&
    paginatedData.value.every((_, idx) => selectedRows.value.has((currentPage.value - 1) * props.pageSize + idx))
})

const isIndeterminate = computed(() => {
  const pageStart = (currentPage.value - 1) * props.pageSize
  const pageSelected = paginatedData.value.filter((_, idx) =>
    selectedRows.value.has(pageStart + idx)
  ).length
  return pageSelected > 0 && pageSelected < paginatedData.value.length
})

const handleSort = (column: Column<any>) => {
  if (!column.sortable) return

  const key = String(column.key)
  if (sortKey.value === key) {
    if (sortDirection.value === 'asc') {
      sortDirection.value = 'desc'
    } else if (sortDirection.value === 'desc') {
      sortKey.value = null
      sortDirection.value = null
    }
  } else {
    sortKey.value = key
    sortDirection.value = 'asc'
  }

  emit('sort-change', key, sortDirection.value)
}

const toggleRowSelection = (index: number) => {
  const globalIndex = (currentPage.value - 1) * props.pageSize + index
  if (selectedRows.value.has(globalIndex)) {
    selectedRows.value.delete(globalIndex)
  } else {
    selectedRows.value.add(globalIndex)
  }
  emitSelection()
}

const toggleAllSelection = () => {
  const pageStart = (currentPage.value - 1) * props.pageSize
  if (isAllSelected.value) {
    for (let i = 0; i < paginatedData.value.length; i++) {
      selectedRows.value.delete(pageStart + i)
    }
  } else {
    for (let i = 0; i < paginatedData.value.length; i++) {
      selectedRows.value.add(pageStart + i)
    }
  }
  emitSelection()
}

const emitSelection = () => {
  const selected = Array.from(selectedRows.value)
    .map(idx => filteredData.value[idx])
    .filter(Boolean)
  emit('selection-change', selected)
}

const getCellValue = (row: any, column: Column<any>) => {
  if (column.render) {
    return column.render(row, filteredData.value.indexOf(row))
  }
  const value = row[column.key as keyof typeof row]
  if (column.formatter) {
    return column.formatter(value)
  }
  return value
}

const goToPage = (page: number) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
  }
}

watch(() => props.data, () => {
  currentPage.value = 1
  selectedRows.value.clear()
})

watch(searchQuery, () => {
  currentPage.value = 1
})
</script>

<template>
  <div class="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
    <div v-if="searchable" class="p-4 border-b border-slate-700/50">
      <div class="relative">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索..."
          class="w-full pl-10 pr-4 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
        />
      </div>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full">
        <thead>
          <tr class="bg-slate-900/50">
            <th
              v-if="selectable"
              class="px-4 py-3 text-left w-12"
            >
              <input
                type="checkbox"
                :checked="isAllSelected"
                :indeterminate="isIndeterminate"
                class="w-4 h-4 rounded border-slate-600 bg-slate-700 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-slate-800"
                @change="toggleAllSelection"
              />
            </th>
            <th
              v-for="column in columns"
              :key="String(column.key)"
              class="px-4 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider cursor-pointer select-none hover:text-slate-300 transition-colors"
              :class="[
                column.align === 'center' ? 'text-center' :
                column.align === 'right' ? 'text-right' : 'text-left',
                column.sortable ? 'cursor-pointer' : ''
              ]"
              :style="{ width: column.width }"
              @click="handleSort(column)"
            >
              <div class="inline-flex items-center gap-1">
                {{ column.label }}
                <span v-if="column.sortable" class="text-slate-600">
                  <ArrowUpDown
                    v-if="sortKey !== String(column.key)"
                    class="w-3 h-3"
                  />
                  <ArrowUp
                    v-else-if="sortDirection === 'asc'"
                    class="w-3 h-3 text-cyan-400"
                  />
                  <ArrowDown
                    v-else
                    class="w-3 h-3 text-cyan-400"
                  />
                </span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/50">
          <tr
            v-for="(row, idx) in paginatedData"
            :key="idx"
            class="hover:bg-slate-700/30 transition-colors cursor-pointer"
            @click="emit('row-click', row, idx)"
          >
            <td
              v-if="selectable"
              class="px-4 py-3"
              @click.stop
            >
              <input
                type="checkbox"
                :checked="selectedRows.has((currentPage - 1) * pageSize + idx)"
                class="w-4 h-4 rounded border-slate-600 bg-slate-700 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-slate-800"
                @change="toggleRowSelection(idx)"
              />
            </td>
            <td
              v-for="column in columns"
              :key="String(column.key)"
              class="px-4 py-3 text-sm text-slate-300"
              :class="[
                column.align === 'center' ? 'text-center' :
                column.align === 'right' ? 'text-right' : 'text-left'
              ]"
            >
              {{ getCellValue(row, column) }}
            </td>
          </tr>
          <tr v-if="loading">
            <td :colspan="columns.length + (selectable ? 1 : 0)" class="px-4 py-12 text-center">
              <div class="flex flex-col items-center gap-2">
                <div class="w-8 h-8 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin"></div>
                <span class="text-sm text-slate-500">加载中...</span>
              </div>
            </td>
          </tr>
          <tr v-else-if="paginatedData.length === 0">
            <td :colspan="columns.length + (selectable ? 1 : 0)" class="px-4 py-12 text-center">
              <p class="text-slate-500">暂无数据</p>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="totalPages > 1"
      class="px-4 py-3 border-t border-slate-700/50 flex items-center justify-between"
    >
      <div class="text-sm text-slate-500">
        共 {{ filteredData.length }} 条，第 {{ currentPage }} / {{ totalPages }} 页
      </div>
      <div class="flex items-center gap-1">
        <button
          class="p-1.5 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="currentPage === 1"
          @click="goToPage(1)"
        >
          <ChevronsLeft class="w-4 h-4" />
        </button>
        <button
          class="p-1.5 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="currentPage === 1"
          @click="goToPage(currentPage - 1)"
        >
          <ChevronLeft class="w-4 h-4" />
        </button>
        <div class="flex items-center gap-1 mx-2">
          <button
            v-for="page in Math.min(5, totalPages)"
            :key="page"
            class="w-8 h-8 rounded text-sm font-medium transition-colors"
            :class="[
              currentPage === page
                ? 'bg-cyan-500 text-white'
                : 'text-slate-400 hover:text-slate-300 hover:bg-slate-700/50'
            ]"
            @click="goToPage(page)"
          >
            {{ page }}
          </button>
        </div>
        <button
          class="p-1.5 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="currentPage === totalPages"
          @click="goToPage(currentPage + 1)"
        >
          <ChevronRight class="w-4 h-4" />
        </button>
        <button
          class="p-1.5 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="currentPage === totalPages"
          @click="goToPage(totalPages)"
        >
          <ChevronsRight class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
