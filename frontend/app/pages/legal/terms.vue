<script setup lang="ts">
import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../../constants/site"

definePageMeta({ auth: false })

useHead({ title: "Terms and conditions placeholder - SiloXR" })
</script>

<template>
  <div class="legal page-pad">
    <section class="legal__card surface">
      <p class="legal__eyebrow">Legal placeholder</p>
      <h1 class="legal__title">SiloXR terms and conditions</h1>
      <p class="legal__copy">
        This is a placeholder for the full SiloXR legal framework. The final document will include terms of use,
        privacy commitments, notification consent, and billing conditions before launch.
      </p>
      <p class="legal__copy">
        Questions can be sent to
        <a :href="SITE_CONTACT_MAILTO" class="legal__link">{{ SITE_CONTACT_EMAIL }}</a>.
      </p>
    </section>
  </div>
</template>

<style scoped>
.legal {
  min-height: calc(100vh - var(--header-h));
  display: flex;
  align-items: center;
  justify-content: center;
}
.legal__card {
  width: min(760px, 100%);
  padding: 32px;
}
.legal__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.legal__title {
  margin-top: 10px;
  font-size: clamp(30px, 5vw, 44px);
  line-height: 1.08;
  letter-spacing: -.04em;
  color: var(--text);
}
.legal__copy {
  margin-top: 14px;
  line-height: 1.7;
  color: var(--text-2);
}
.legal__link {
  color: var(--purple);
  font-weight: 600;
  text-decoration: none;
}
.legal__link:hover {
  text-decoration: underline;
}
</style>
