<!-- frontend/app/pages/upload.vue -->

<script setup lang="ts">
const { $api }    = useNuxtApp()
const route       = useRoute()
const currentUser = useState<any | null>("current-user", () => null)
const file        = ref<File | null>(null)
const uploading   = ref(false)
const result      = ref<any>(null)
const error       = ref("")
const dragOver    = ref(false)
const mode        = ref<"sales" | "stock">(route.query.mode === "stock" ? "stock" : "sales")
const defaultType = ref(mode.value === "stock" ? "RESTOCK" : "SALE")
const config = useRuntimeConfig()
const isProUser = computed(() => Boolean(currentUser.value?.is_pro))
const uploadLimitLabel = computed(() =>
  isProUser.value ? "Unlimited upload size on Pro" : "Max 1MB on Free"
)
useHead({ title: "Import data — SiloXR" })

const handleFile = (f: File) => {
  file.value   = f
  result.value = null
  error.value  = ""
  if (!isProUser.value && f.size > 1024 * 1024) {
    error.value = "Free plan uploads are limited to 1MB. Upgrade to Pro for unlimited upload size."
  }
}

const onDrop = (e: DragEvent) => {
  dragOver.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) handleFile(f)
}

const upload = async () => {
  if (!file.value) return
  if (!isProUser.value && file.value.size > 1024 * 1024) {
    error.value = "Free plan uploads are limited to 1MB. Upgrade to Pro for unlimited upload size."
    return
  }
  uploading.value = true
  error.value     = ""
  result.value    = null

  const form = new FormData()
  form.append("file",               file.value)
  form.append("default_event_type", defaultType.value)

  try {
    result.value = await $api("/upload/", { method: "POST", body: form })
  } catch (e: any) {
    error.value = e?.data?.detail ?? "Upload failed."
  } finally {
    uploading.value = false
  }
}

const ext = computed(() => file.value?.name.split(".").pop()?.toLowerCase() ?? "")
const valid = computed(() => ["csv", "xlsx", "xls", "pdf"].includes(ext.value))

watch(mode, (next) => {
  defaultType.value = next === "stock" ? "RESTOCK" : "SALE"
})

onMounted(async () => {
  if (currentUser.value) return
  currentUser.value = await $api("/auth/me/").catch(() => null)
})
</script>

<template>
  <div class="page-pad upload-page">

    <div class="upload-page__header">
      <h1 class="t-heading">Import data</h1>
      <p class="t-body" style="margin-top:4px">
        Upload sales logs or stock files with their real dates so inventory history stays accurate.
      </p>
    </div>

    <div class="upload-mode surface">
      <button class="upload-mode__pill" :class="{ 'upload-mode__pill--active': mode === 'sales' }" @click="mode = 'sales'">
        Sales upload
      </button>
      <button class="upload-mode__pill" :class="{ 'upload-mode__pill--active': mode === 'stock' }" @click="mode = 'stock'">
        Stock upload
      </button>
      <p class="upload-mode__copy">
        {{ mode === "sales"
          ? "CSV and Excel are supported for sales history. Include the sale date or date-time on each row."
          : "CSV and Excel are supported for restocks and stock counts. Include the real movement date or count date on each row." }}
        {{ ` ${uploadLimitLabel}.` }}
      </p>
    </div>

    <div class="upload-grid">

      <!-- Drop zone -->
      <div
        class="upload-zone surface"
        :class="{ 'upload-zone--over': dragOver, 'upload-zone--ready': file && valid }"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="onDrop"
      >
        <input
          type="file"
          accept=".csv,.xlsx,.xls,.pdf"
          class="upload-zone__input"
          @change="e => handleFile((e.target as HTMLInputElement).files![0])"
        />

        <div class="upload-zone__content">
          <div class="upload-zone__icon">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <path d="M16 4v16M10 10l6-6 6 6" stroke="var(--purple)" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M6 22v4h20v-4" stroke="var(--text-3)" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <p v-if="!file" class="upload-zone__label">
            Drop a file here, or click to browse
          </p>
          <p v-else class="upload-zone__label" style="color:var(--purple)">
            {{ file.name }}
            <span v-if="!valid" style="color:var(--red)"> — unsupported format</span>
          </p>
          <p class="t-hint" style="margin-top:4px">CSV, Excel, or PDF · max 10MB</p>
        </div>
      </div>

      <!-- Options + actions -->
      <div class="upload-options surface">
        <h2 class="t-subheading" style="margin-bottom:16px">Import options</h2>

        <div class="field">
          <label class="field__label">Default event type</label>
          <select v-model="defaultType" class="field__input">
            <option value="SALE">Sale (most common)</option>
            <option value="RESTOCK">Restock</option>
            <option value="STOCK_COUNT">Stock count</option>
          </select>
          <span class="field__hint">
            Used when the file doesn't include an event_type column. `date` or `occurred_at` should be included for every row.
          </span>
        </div>

        <p v-if="error" class="upload-error">{{ error }}</p>

        <button
          class="btn btn-primary"
          style="width:100%;margin-top:16px"
          :disabled="!file || !valid || uploading"
          @click="upload"
        >
          {{ uploading ? "Importing…" : "Import data" }}
        </button>

        <a
          :href="`${config.public.apiBase}/upload/sample/?kind=${mode}`"
          class="btn btn-secondary"
          style="width:100%;margin-top:8px"
          target="_blank"
        >
          Download {{ mode === "sales" ? "sales" : "stock" }} sample CSV
        </a>
      </div>
    </div>

    <!-- Result -->
    <div v-if="result" class="upload-result surface animate-fade-up">
      <div class="upload-result__header">
        <span class="upload-result__check">✓</span>
        <span class="t-subheading">Import complete</span>
      </div>
      <div class="upload-result__stats">
        <div class="upload-result__stat">
          <span class="upload-result__val" style="color:var(--teal)">{{ result.created }}</span>
          <span class="t-hint">events created</span>
        </div>
        <div class="upload-result__stat">
          <span class="upload-result__val">{{ result.products_created?.length ?? 0 }}</span>
          <span class="t-hint">new products</span>
        </div>
        <div class="upload-result__stat">
          <span class="upload-result__val" style="color:var(--amber)">{{ result.skipped }}</span>
          <span class="t-hint">rows skipped</span>
        </div>
      </div>
      <div v-if="result.errors?.length" class="upload-result__errors">
        <p class="t-small" style="margin-bottom:6px">Some rows had issues:</p>
        <ul>
          <li v-for="e in result.errors.slice(0,5)" :key="e" class="t-hint">{{ e }}</li>
        </ul>
      </div>
      <NuxtLink to="/dashboard" class="btn btn-primary" style="margin-top:16px">
        View dashboard →
      </NuxtLink>
    </div>

  </div>
</template>

<style scoped>
.upload-page__header { margin-bottom: 28px; }
.upload-mode {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.upload-mode__pill {
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--text-3);
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.upload-mode__pill--active {
  background: var(--purple-bg);
  border-color: var(--purple-border);
  color: var(--purple);
}
.upload-mode__copy {
  margin-left: auto;
  max-width: 50ch;
  font-size: 12px;
  color: var(--text-3);
}
.upload-grid {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 20px;
  align-items: start;
}
@media (max-width: 720px) {
  .upload-grid { grid-template-columns: 1fr; }
  .upload-mode__copy { margin-left: 0; }
}

.upload-zone {
  position: relative;
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--border);
  transition: all var(--dur-base) var(--ease-out);
  cursor: pointer;
}
.upload-zone--over  { border-color: var(--purple); background: var(--purple-bg); }
.upload-zone--ready { border-color: var(--purple); border-style: solid; }
.upload-zone__input {
  position:  absolute;
  inset:     0;
  opacity:   0;
  cursor:    pointer;
  width:     100%;
  height:    100%;
}
.upload-zone__content {
  display:        flex;
  flex-direction: column;
  align-items:    center;
  gap:            10px;
  pointer-events: none;
}
.upload-zone__icon {
  width:           56px;
  height:          56px;
  border-radius:   50%;
  background:      var(--purple-bg);
  display:         flex;
  align-items:     center;
  justify-content: center;
}
.upload-zone__label { font-size: 14px; font-weight: 500; color: var(--text); }
.upload-options { padding: 24px; }
.upload-error {
  font-size: 13px; color: var(--red);
  padding: 8px 12px; background: var(--red-bg);
  border-radius: var(--r-sm); margin-top: 8px;
}
.upload-result { padding: 24px; margin-top: 20px; }
.upload-result__header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.upload-result__check {
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--teal-bg); color: var(--teal);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700;
}
.upload-result__stats { display: flex; gap: 28px; flex-wrap: wrap; }
.upload-result__stat  { display: flex; flex-direction: column; gap: 2px; }
.upload-result__val   { font-size: 24px; font-weight: 700; letter-spacing: -0.03em; color: var(--text); }
.upload-result__errors { margin-top: 14px; padding: 10px 12px; background: var(--amber-bg); border-radius: var(--r-sm); }
</style>
