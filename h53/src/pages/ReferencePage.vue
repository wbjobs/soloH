<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { 
  Dna, 
  BookOpen, 
  Database, 
  GitBranch, 
  Info,
  ChevronRight,
  Search,
  Filter
} from 'lucide-vue-next';
import { referenceAPI } from '@/services/api';
import type { ReferenceGenome, MaizeInbredLine } from '@/types';

const isLoading = ref(false);
const genomes = ref<ReferenceGenome[]>([]);
const maizeLines = ref<MaizeInbredLine[]>([]);
const searchQuery = ref('');
const activeTab = ref<'genomes' | 'maize'>('maize');

const loadReferenceData = async () => {
  try {
    isLoading.value = true;
    const [genomesData, maizeData] = await Promise.all([
      referenceAPI.listGenomes(),
      referenceAPI.getMaizeInbredLines(),
    ]);
    genomes.value = genomesData;
    maizeLines.value = maizeData;
  } catch (e) {
    console.error('Failed to load reference data:', e);
  } finally {
    isLoading.value = false;
  }
};

const filteredMaizeLines = () => {
  if (!searchQuery.value) return maizeLines.value;
  const query = searchQuery.value.toLowerCase();
  return maizeLines.value.filter(line => 
    line.name.toLowerCase().includes(query) ||
    line.description.toLowerCase().includes(query)
  );
};

const getStatusBadge = (line: MaizeInbredLine) => {
  const statusMap: Record<string, { label: string; color: string; bgColor: string }> = {
    'B73_v5': { label: '黄金标准', color: '#00B42A', bgColor: 'rgba(0, 180, 42, 0.15)' },
    'Mo17_v1': { label: '常用', color: '#165DFF', bgColor: 'rgba(22, 93, 255, 0.15)' },
    'W22_v2': { label: '常用', color: '#165DFF', bgColor: 'rgba(22, 93, 255, 0.15)' },
    'PH207_v1': { label: '可用', color: '#FF7D00', bgColor: 'rgba(255, 125, 0, 0.15)' },
    'B97_v1': { label: '可用', color: '#FF7D00', bgColor: 'rgba(255, 125, 0, 0.15)' },
  };
  return statusMap[`${line.name}_${line.version}`] || { label: '可用', color: '#64748B', bgColor: 'rgba(100, 116, 139, 0.15)' };
};

onMounted(() => {
  loadReferenceData();
});
</script>

<template>
  <div class="min-h-screen bg-slate-950 p-6">
    <div class="max-w-7xl mx-auto">
      <div class="mb-8">
        <div class="flex items-center gap-3 mb-2">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
            <Dna class="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 class="text-2xl font-bold text-white">参考基因组</h1>
            <p class="text-slate-400 text-sm">预存储的玉米自交系参考基因组数据</p>
          </div>
        </div>
      </div>

      <div class="flex gap-4 mb-6">
        <button
          @click="activeTab = 'maize'"
          :class="[
            'px-6 py-2.5 rounded-lg font-medium transition-all duration-200 flex items-center gap-2',
            activeTab === 'maize'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
              : 'bg-slate-800/50 text-slate-400 hover:bg-slate-800 hover:text-white'
          ]"
        >
          <Database class="w-4 h-4" />
          玉米自交系
        </button>
        <button
          @click="activeTab = 'genomes'"
          :class="[
            'px-6 py-2.5 rounded-lg font-medium transition-all duration-200 flex items-center gap-2',
            activeTab === 'genomes'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
              : 'bg-slate-800/50 text-slate-400 hover:bg-slate-800 hover:text-white'
          ]"
        >
          <BookOpen class="w-4 h-4" />
          全部基因组
        </button>
      </div>

      <div v-if="activeTab === 'maize'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div class="relative">
            <Search class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索自交系名称或描述..."
              class="pl-10 pr-4 py-2.5 w-80 bg-slate-800/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div class="flex items-center gap-2 text-slate-400">
            <Filter class="w-4 h-4" />
            <span class="text-sm">共 {{ maizeLines.length }} 个参考基因组</span>
          </div>
        </div>

        <div v-if="isLoading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div v-for="i in 6" :key="i" class="animate-pulse">
            <div class="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
              <div class="h-6 bg-slate-700 rounded w-1/3 mb-4"></div>
              <div class="h-4 bg-slate-700 rounded w-full mb-2"></div>
              <div class="h-4 bg-slate-700 rounded w-3/4 mb-4"></div>
              <div class="grid grid-cols-2 gap-3">
                <div class="h-12 bg-slate-700 rounded"></div>
                <div class="h-12 bg-slate-700 rounded"></div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="line in filteredMaizeLines()"
            :key="line.id"
            class="group bg-slate-800/30 rounded-xl p-6 border border-slate-700/50 hover:border-blue-500/50 hover:bg-slate-800/50 transition-all duration-300 cursor-pointer"
          >
            <div class="flex items-start justify-between mb-4">
              <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                  <GitBranch class="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-white group-hover:text-blue-400 transition-colors">
                    {{ line.name }}
                  </h3>
                  <p class="text-slate-400 text-sm">版本 {{ line.version }}</p>
                </div>
              </div>
              <span
                :style="{ color: getStatusBadge(line).color, backgroundColor: getStatusBadge(line).bgColor }"
                class="px-2.5 py-1 rounded-full text-xs font-medium"
              >
                {{ getStatusBadge(line).label }}
              </span>
            </div>

            <p class="text-slate-400 text-sm mb-4 line-clamp-2">
              {{ line.description }}
            </p>

            <div class="grid grid-cols-2 gap-3 mb-4">
              <div class="bg-slate-900/50 rounded-lg p-3">
                <p class="text-slate-500 text-xs mb-1">染色体数</p>
                <p class="text-white font-semibold">{{ line.chromosomeCount }}</p>
              </div>
              <div class="bg-slate-900/50 rounded-lg p-3">
                <p class="text-slate-500 text-xs mb-1">基因组大小</p>
                <p class="text-white font-semibold">{{ line.genomeSize }}</p>
              </div>
            </div>

            <div class="bg-slate-900/50 rounded-lg p-3 mb-4">
              <p class="text-slate-500 text-xs mb-1">注释版本</p>
              <p class="text-white font-medium">{{ line.annotationVersion }}</p>
            </div>

            <div class="flex items-center justify-between">
              <div class="flex items-center gap-1.5 text-blue-400 text-sm">
                <Info class="w-4 h-4" />
                <span>可用于GWAS分析</span>
              </div>
              <ChevronRight class="w-5 h-5 text-slate-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
            </div>
          </div>
        </div>

        <div v-if="filteredMaizeLines().length === 0 && !isLoading" class="text-center py-16">
          <Database class="w-16 h-16 text-slate-600 mx-auto mb-4" />
          <p class="text-slate-400 text-lg">未找到匹配的参考基因组</p>
          <p class="text-slate-500 text-sm mt-1">请尝试其他搜索关键词</p>
        </div>
      </div>

      <div v-if="activeTab === 'genomes'" class="space-y-4">
        <div v-if="isLoading" class="space-y-3">
          <div v-for="i in 5" :key="i" class="animate-pulse">
            <div class="h-16 bg-slate-800/50 rounded-xl border border-slate-700/50"></div>
          </div>
        </div>

        <div v-else class="bg-slate-800/30 rounded-xl border border-slate-700/50 overflow-hidden">
          <table class="w-full">
            <thead class="bg-slate-800/50">
              <tr>
                <th class="text-left px-6 py-4 text-sm font-semibold text-slate-300">物种</th>
                <th class="text-left px-6 py-4 text-sm font-semibold text-slate-300">名称</th>
                <th class="text-left px-6 py-4 text-sm font-semibold text-slate-300">版本</th>
                <th class="text-left px-6 py-4 text-sm font-semibold text-slate-300">描述</th>
                <th class="text-left px-6 py-4 text-sm font-semibold text-slate-300">创建时间</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-700/50">
              <tr
                v-for="genome in genomes"
                :key="genome.id"
                class="hover:bg-slate-800/30 transition-colors"
              >
                <td class="px-6 py-4">
                  <span class="px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-400 text-xs font-medium">
                    {{ genome.species }}
                  </span>
                </td>
                <td class="px-6 py-4 text-white font-medium">{{ genome.name }}</td>
                <td class="px-6 py-4 text-slate-400">{{ genome.version }}</td>
                <td class="px-6 py-4 text-slate-400 text-sm max-w-xs truncate">{{ genome.description }}</td>
                <td class="px-6 py-4 text-slate-500 text-sm">{{ genome.createdAt }}</td>
              </tr>
            </tbody>
          </table>

          <div v-if="genomes.length === 0" class="text-center py-12">
            <Database class="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <p class="text-slate-400">暂无参考基因组数据</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
