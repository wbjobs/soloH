<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from './Sidebar.vue'
import Header from './Header.vue'

const sidebarCollapsed = ref(false)

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}
</script>

<template>
  <div class="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden">
    <Header />
    <div class="flex-1 flex overflow-hidden">
      <Sidebar :collapsed="sidebarCollapsed" @toggle-collapse="toggleSidebar" />
      <main class="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950">
        <div class="p-6">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
