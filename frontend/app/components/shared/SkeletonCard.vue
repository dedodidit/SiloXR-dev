<!-- frontend/app/components/shared/SkeletonCard.vue -->

<script setup lang="ts">
defineProps<{ type?: "decision" | "chart" | "strip" | "stat" }>()
</script>

<template>
  <div class="sk-wrap">
    <!-- Decision skeleton -->
    <template v-if="type === 'decision' || !type">
      <div class="sk-card surface" v-for="i in 3" :key="i" :style="{ animationDelay: `${i * 80}ms` }">
        <div class="sk-strip skeleton" />
        <div class="sk-body">
          <div class="sk-row">
            <div class="skeleton skeleton--text" style="width:60px" />
            <div class="skeleton skeleton--text" style="width:40px;margin-left:auto" />
          </div>
          <div class="skeleton skeleton--title" style="width:70%;margin-top:8px" />
          <div class="skeleton skeleton--text" style="width:100%;margin-top:6px" />
          <div class="skeleton skeleton--text" style="width:85%;margin-top:3px" />
          <div class="sk-conf skeleton" style="margin-top:10px" />
        </div>
      </div>
    </template>

    <!-- Chart skeleton -->
    <div v-if="type === 'chart'" class="skeleton skeleton--chart" />

    <!-- Strip skeleton -->
    <div v-if="type === 'strip'" class="surface" style="padding:18px 20px">
      <div class="skeleton skeleton--text" style="width:120px;margin-bottom:14px" />
      <div style="display:flex;gap:6px;align-items:flex-end;height:88px">
        <div v-for="i in 7" :key="i" class="skeleton"
          :style="{ flex:1, height: `${30 + Math.random() * 60}%`, borderRadius: 'var(--r-sm)' }" />
      </div>
    </div>

    <!-- Stat skeleton -->
    <template v-if="type === 'stat'">
      <div v-for="i in 4" :key="i" class="surface" style="padding:20px 22px">
        <div class="skeleton" style="width:50px;height:32px;border-radius:4px" />
        <div class="skeleton skeleton--text" style="width:80px;margin-top:8px" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.sk-wrap     { display: contents; }
.sk-card     { display: flex; overflow: hidden; animation: fade-up 0.4s var(--ease-out) both; }
.sk-strip    { width: 4px; flex-shrink: 0; border-radius: 0; }
.sk-body     { flex: 1; padding: 16px 18px; display: flex; flex-direction: column; gap: 0; }
.sk-row      { display: flex; align-items: center; }
.sk-conf     { height: 5px; border-radius: 99px; }
</style>