<!-- frontend/app/components/shared/OfflineBanner.vue -->

<script setup lang="ts">
const { queueLength, isSyncing, isOnline, sync } = useOfflineQueue()

const visible = computed(() => !isOnline.value || queueLength.value > 0)
</script>

<template>
  <Transition name="banner">
    <div v-if="visible" class="offline-banner" :class="{ 'offline-banner--online': isOnline }">
      <span v-if="!isOnline">
        You are offline. {{ queueLength }} event{{ queueLength !== 1 ? "s" : "" }} queued locally.
      </span>
      <span v-else-if="isSyncing">
        Syncing {{ queueLength }} event{{ queueLength !== 1 ? "s" : "" }}…
      </span>
      <span v-else>
        Back online. {{ queueLength }} event{{ queueLength !== 1 ? "s" : "" }} ready to sync.
        <button class="offline-banner__sync" @click="sync">Sync now</button>
      </span>
    </div>
  </Transition>
</template>

<style scoped>
.offline-banner {
  position:        fixed;
  bottom:          16px;
  left:            50%;
  transform:       translateX(-50%);
  background:      #2C2C2A;
  color:           #e8e6e0;
  font-size:       13px;
  font-weight:     500;
  padding:         10px 20px;
  border-radius:   var(--radius-md);
  box-shadow:      var(--shadow-md);
  z-index:         1000;
  white-space:     nowrap;
  display:         flex;
  align-items:     center;
  gap:             10px;
}
.offline-banner--online { background: #085041; }
.offline-banner__sync {
  background:    rgba(255,255,255,0.15);
  border:        none;
  color:         #fff;
  padding:       4px 10px;
  border-radius: var(--radius-sm);
  cursor:        pointer;
  font-size:     12px;
  font-weight:   600;
}
.banner-enter-active, .banner-leave-active { transition: all 0.25s ease; }
.banner-enter-from, .banner-leave-to       { opacity: 0; transform: translateX(-50%) translateY(8px); }
</style>