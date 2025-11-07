<template>
  <div class="page">
    <header class="hero">
      <div class="hero-content">
        <h1>Betalindienst Fraud Sentinel</h1>
        <p>
          Upload evidence files for an instant readiness check. We will soon wire this panel
          to powerful Python risk detectors that can parse structured exports, media and audit trails.
        </p>
      </div>
    </header>

    <main class="card">
      <section class="upload">
        <div
          class="dropzone"
          :class="{ 'dropzone--active': isDragging }"
          @dragover.prevent="onDragOver"
          @dragleave.prevent="onDragLeave"
          @drop.prevent="onDrop"
        >
          <div class="dropzone-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" role="img" focusable="false">
              <path
                d="M12 16.75a.75.75 0 0 1-.75-.75V9.56l-1.72 1.72a.75.75 0 1 1-1.06-1.06l3.25-3.25a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1-1.06 1.06L12.75 9.56v6.44a.75.75 0 0 1-.75.75Z"
                fill="currentColor"
              />
              <path
                d="M6.5 18.75a4.25 4.25 0 0 1-.46-8.49 5.75 5.75 0 0 1 11.2-1.88 4.5 4.5 0 0 1-.24 8.99H6.5Z"
                fill="currentColor"
                opacity="0.7"
              />
            </svg>
          </div>
          <h2>Drop your case material</h2>
          <p>Images, CSV, PDF, XLSX, audio logs &mdash; everything investigators rely on.</p>
          <label class="file-input">
            <input type="file" multiple @change="onFileChange" />
            <span>Select files</span>
          </label>
        </div>

        <transition-group name="list" tag="ul" class="file-list" v-if="files.length">
          <li v-for="file in files" :key="file.name" class="file-item">
            <div class="file-meta">
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">{{ formatSize(file.size) }}</span>
            </div>
            <button class="remove" type="button" @click="removeFile(file.name)">
              <span aria-hidden="true">&times;</span>
              <span class="sr-only">Remove</span>
            </button>
          </li>
        </transition-group>
      </section>

      <footer class="action">
        <button class="cta" type="button">
          <span>Check for Fraud</span>
        </button>
        <p class="disclaimer">
          The fraud engine will execute server-side Python analytics. Hook your API endpoint to bring it
          alive.
        </p>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue';
const files = ref([]);
const isDragging = ref(false);
const onFileChange = (event) => {
  if (!event.target.files?.length) return;
  files.value = [...files.value, ...Array.from(event.target.files)];
  event.target.value = '';
};

const onDragOver = () => {
  isDragging.value = true;
};

const onDragLeave = () => {
  isDragging.value = false;
};

const onDrop = (event) => {
  const droppedFiles = event.dataTransfer?.files;
  if (!droppedFiles?.length) return;
  files.value = [...files.value, ...Array.from(droppedFiles)];
  isDragging.value = false;
};

const removeFile = (name) => {
  files.value = files.value.filter((file) => file.name !== name);
};

const formatSize = (bytes) => {
  if (!Number.isFinite(bytes)) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let index = 0;
  let value = bytes;

  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }

  return `${value.toFixed(value < 10 && index > 0 ? 1 : 0)} ${units[index]}`;
};
</script>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4rem 1.5rem 3rem;
  background: transparent;
}

.hero {
  text-align: center;
  margin-bottom: 3rem;
}

.hero-content {
  max-width: 720px;
  margin: 0 auto;
}

.hero h1 {
  font-size: clamp(2.75rem, 6vw, 3.75rem);
  letter-spacing: -0.03em;
  margin-bottom: 1rem;
  color: #f7fafc;
}

.hero p {
  font-size: 1.1rem;
  color: rgba(211, 223, 237, 0.78);
  line-height: 1.7;
}

.card {
  width: min(960px, 100%);
  border-radius: 28px;
  padding: 3rem;
  backdrop-filter: blur(24px);
  background: rgba(9, 12, 20, 0.85);
  box-shadow: 0 32px 80px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(88, 255, 195, 0.12);
}

@media (max-width: 768px) {
  .card {
    padding: 2rem;
  }
}

.upload {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.dropzone {
  border: 2px dashed rgba(102, 255, 204, 0.35);
  border-radius: 22px;
  padding: 3rem 2rem;
  text-align: center;
  background: linear-gradient(135deg, rgba(37, 55, 70, 0.35), rgba(12, 16, 26, 0.6));
  transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease;
  position: relative;
  overflow: hidden;
}

.dropzone::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at top, rgba(0, 255, 170, 0.18), transparent 65%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.dropzone--active {
  border-color: rgba(109, 255, 217, 0.8);
  box-shadow: 0 0 25px rgba(0, 255, 170, 0.3);
  transform: translateY(-4px) scale(1.01);
}

.dropzone--active::before {
  opacity: 1;
}

.dropzone-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 1.5rem;
  display: grid;
  place-items: center;
  border-radius: 24px;
  background: rgba(28, 217, 175, 0.15);
  color: #58ffc3;
  font-size: 2.5rem;
  box-shadow: inset 0 0 0 1px rgba(88, 255, 195, 0.2);
}

.dropzone h2 {
  margin: 0 0 0.75rem;
  font-size: 1.8rem;
  color: #f3f8ff;
}

.dropzone p {
  color: rgba(207, 226, 239, 0.7);
  margin-bottom: 2rem;
  max-width: 480px;
  margin-left: auto;
  margin-right: auto;
}

.file-input {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 1.6rem;
  border-radius: 999px;
  background: rgba(88, 255, 195, 0.12);
  color: #58ffc3;
  border: 1px solid rgba(88, 255, 195, 0.35);
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background 0.3s ease, color 0.3s ease, transform 0.3s ease;
}

.file-input input {
  display: none;
}

.file-input:hover {
  background: rgba(88, 255, 195, 0.22);
  transform: translateY(-2px);
}

.file-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1.15rem;
  border-radius: 16px;
  background: rgba(15, 19, 30, 0.95);
  border: 1px solid rgba(88, 255, 195, 0.12);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.file-meta {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.file-name {
  font-weight: 600;
  color: #e8f5ff;
}

.file-size {
  font-size: 0.85rem;
  color: rgba(197, 222, 237, 0.55);
}

.remove {
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.55);
  font-size: 1.35rem;
  cursor: pointer;
  position: relative;
  transition: color 0.2s ease, transform 0.2s ease;
}

.remove:hover {
  color: #ff7373;
  transform: scale(1.1);
}

.list-enter-active,
.list-leave-active {
  transition: all 0.25s ease;
}

.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.action {
  display: grid;
  gap: 1rem;
  margin-top: 2.5rem;
  text-align: center;
}

.cta {
  --glow-color: rgba(88, 255, 195, 0.95);
  padding: 1.1rem 2.6rem;
  border-radius: 999px;
  border: none;
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #05060a;
  background: linear-gradient(135deg, #3bff8c, #00ffc6);
  box-shadow: 0 0 24px var(--glow-color), 0 12px 35px rgba(0, 255, 184, 0.35);
  cursor: pointer;
  transition: transform 0.25s ease, box-shadow 0.25s ease, filter 0.25s ease;
}

.cta:hover {
  transform: translateY(-3px) scale(1.02);
  box-shadow: 0 0 30px var(--glow-color), 0 16px 40px rgba(0, 255, 184, 0.45);
}

.cta span {
  position: relative;
  z-index: 1;
}

.disclaimer {
  color: rgba(164, 199, 214, 0.55);
  font-size: 0.95rem;
  line-height: 1.6;
}
</style>
