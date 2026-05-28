<script setup>
import { ref, onUnmounted, computed } from "vue";

const API = "/api";

const question = ref(null);
const loading = ref(false);
const showAnswer = ref(false);
const showExplanation = ref(false);
const answerIndex = ref(0);
const timer = ref(0);
const timerInterval = ref(null);
const completedSet = ref(new Set());
const totalPages = ref(0);
const completedCount = ref(0);
const history = ref([]);
const historyIndex = ref(-1);
const showChecklist = ref(false);

const qid = computed(() => {
  if (!question.value) return null;
  return `${question.value.year}_${question.value.page}`;
});

const isCompleted = computed(() => {
  if (!qid.value) return false;
  return completedSet.value.has(qid.value);
});

const progressPercent = computed(() => {
  if (totalPages.value === 0) return 0;
  return Math.round((completedCount.value / totalPages.value) * 100);
});

const timerDisplay = computed(() => {
  const m = Math.floor(timer.value / 60);
  const s = timer.value % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
});

const canGoBack = computed(() => historyIndex.value > 0);
const canGoForward = computed(() => historyIndex.value < history.value.length - 1);

function startTimer() {
  stopTimer();
  timer.value = 0;
  timerInterval.value = setInterval(() => {
    timer.value++;
  }, 1000);
}

function stopTimer() {
  if (timerInterval.value) {
    clearInterval(timerInterval.value);
    timerInterval.value = null;
  }
}

async function loadIndex() {
  const res = await fetch(`${API}/index`);
  const data = await res.json();
  totalPages.value = data.total_pages;
  completedCount.value = data.completed;
  if (data.checklist) {
    completedSet.value = new Set(Object.keys(data.checklist));
  }
}

async function fetchRandom() {
  loading.value = true;
  showAnswer.value = false;
  showExplanation.value = false;
  answerIndex.value = 0;
  try {
    const res = await fetch(`${API}/random`);
    if (!res.ok) throw new Error("no question available");
    const data = await res.json();
    question.value = data;
    history.value = [...history.value.slice(0, historyIndex.value + 1), data];
    historyIndex.value = history.value.length - 1;
    if (data.qid) {
      completedSet.value.has(data.qid)
        ? null
        : null;
    }
    startTimer();
    await loadIndex();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

function goToHistory(idx) {
  if (idx < 0 || idx >= history.value.length) return;
  historyIndex.value = idx;
  question.value = history.value[idx];
  showAnswer.value = false;
  showExplanation.value = false;
  answerIndex.value = 0;
  startTimer();
}

function prevQuestion() {
  goToHistory(historyIndex.value - 1);
}

function nextQuestion() {
  goToHistory(historyIndex.value + 1);
}

function onDone() {
  stopTimer();
  showAnswer.value = false;
  showExplanation.value = false;
}

function onShowAnswer() {
  showAnswer.value = true;
  showExplanation.value = false;
  if (question.value) {
    fetch(`${API}/answer_index/${question.value.year}/${question.value.page}`)
      .then((r) => r.json())
      .then((d) => {
        answerIndex.value = d.answer_file_index;
      });
  }
}

function onShowExplanation() {
  showExplanation.value = true;
  showAnswer.value = false;
  if (question.value) {
    fetch(`${API}/answer_index/${question.value.year}/${question.value.page}`)
      .then((r) => r.json())
      .then((d) => {
        answerIndex.value = d.answer_file_index;
      });
  }
}

async function toggleChecklist() {
  if (!qid.value) return;
  const res = await fetch(`${API}/checklist/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qid: qid.value }),
  });
  const data = await res.json();
  if (data.checked) {
    completedSet.value.add(qid.value);
  } else {
    completedSet.value.delete(qid.value);
  }
  completedCount.value = data.completed;
}

function problemImageUrl() {
  if (!question.value) return "";
  return `${API}/pdf/${question.value.year}/problem/${question.value.page}`;
}

function answerImageUrl() {
  if (!question.value) return "";
  return `${API}/pdf/${question.value.year}/answer${answerIndex.value}/${question.value.page}`;
}

function explanationImageUrl() {
  if (!question.value) return "";
  return `${API}/pdf/${question.value.year}/answer${answerIndex.value}/${question.value.page}`;
}

function getAllTags() {
  const all = [];
  for (let y = 2003; y <= 2025; y++) {
    for (let p = 0; p < 20; p++) {
      const id = `${y}_${p}`;
      all.push({ qid: id, year: y, page: p, done: completedSet.value.has(id) });
    }
  }
  return all;
}

const groupedTags = computed(() => {
  const groups = {};
  const tags = getAllTags();
  for (const t of tags) {
    if (!groups[t.year]) groups[t.year] = [];
    groups[t.year].push(t);
  }
  return Object.entries(groups).sort((a, b) => Number(a[0]) - Number(b[0]));
});

onUnmounted(() => {
  stopTimer();
});

fetchRandom();
</script>

<template>
  <div class="app-container">
    <header class="app-header">
      <div class="logo-area">
        <span class="logo-icon">&#x2211;</span>
        <h1 class="app-title">EMaT</h1>
        <span class="app-subtitle">山口大学大学院 数学入試 推薦システム</span>
      </div>
      <button class="checklist-btn" @click="showChecklist = !showChecklist">
        {{ showChecklist ? "閉じる" : "CheckList" }}
        <span class="checklist-badge">{{ completedCount }}/{{ totalPages }}</span>
      </button>
    </header>

    <div class="timer-bar-container">
      <div class="timer-display">{{ timerDisplay }}</div>
      <div class="progress-bar-bg">
        <div
          class="progress-bar-fill"
          :style="{ width: progressPercent + '%' }"
        ></div>
      </div>
      <div class="progress-label">{{ progressPercent }}% 完了</div>
    </div>

    <div class="main-content">
      <div class="question-area" v-if="!showChecklist">
        <div class="nav-buttons top-nav">
          <button class="nav-btn" :disabled="!canGoBack" @click="prevQuestion">&#x25C0; 前へ</button>
          <button class="nav-btn primary" @click="fetchRandom">&#x1F3B2; ランダム出題</button>
          <button class="nav-btn" :disabled="!canGoForward" @click="nextQuestion">次へ &#x25B6;</button>
        </div>

        <div v-if="loading" class="loading">読み込み中...</div>

        <div v-else-if="question" class="question-card">
          <div class="question-meta">
            <span class="year-tag">{{ question.year }}年</span>
            <span class="page-tag">{{ question.page + 1 }}ページ目</span>
            <span
              class="status-tag"
              :class="{ done: isCompleted }"
              @click="toggleChecklist"
            >
              {{ isCompleted ? "&#x2611; 完了" : "&#x2610; 未完了" }}
            </span>
          </div>

          <div class="pdf-image-wrapper">
            <img
              :src="problemImageUrl()"
              alt="問題"
              class="pdf-image"
              @error="(e) => e.target.style.display = 'none'"
            />
          </div>

          <div v-if="!showAnswer && !showExplanation" class="action-area">
            <button class="done-btn" @click="onDone">
              <span class="done-icon">&#x2705;</span>
              やった！
            </button>
          </div>

          <div v-if="showAnswer || showExplanation" class="result-area">
            <div class="result-buttons">
              <button
                class="result-btn answer-btn"
                :class="{ active: showAnswer }"
                @click="onShowAnswer"
              >
                &#x1F4D6; 答えを見る
              </button>
              <button
                class="result-btn explanation-btn"
                :class="{ active: showExplanation }"
                @click="onShowExplanation"
              >
                &#x1F4DD; 解説を見る
              </button>
            </div>

            <div v-if="showAnswer" class="result-image-area">
              <h3>答え</h3>
              <div class="pdf-image-wrapper">
                <img
                  :src="answerImageUrl()"
                  alt="答え"
                  class="pdf-image"
                  @error="(e) => e.target.style.display = 'none'"
                />
              </div>
            </div>

            <div v-if="showExplanation" class="result-image-area">
              <h3>解説</h3>
              <div class="pdf-image-wrapper">
                <img
                  :src="explanationImageUrl()"
                  alt="解説"
                  class="pdf-image"
                  @error="(e) => e.target.style.display = 'none'"
                />
              </div>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <p>問題がありません。「ランダム出題」を押してください。</p>
        </div>
      </div>

      <div class="checklist-panel" v-if="showChecklist">
        <h2>CheckList</h2>
        <div class="checklist-tags">
          <div v-for="[year, tags] in groupedTags" :key="year" class="year-group">
            <div class="year-label">{{ year }}</div>
            <div class="page-tags">
              <span
                v-for="t in tags"
                :key="t.qid"
                class="check-tag"
                :class="{ done: t.done }"
                :title="`${t.year}年 ${t.page + 1}ページ目`"
              >
                {{ t.page + 1 }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: "Segoe UI", "Hiragino Sans", "Meiryo", sans-serif;
  background: #0f0f1a;
  color: #e0e0e0;
  min-height: 100vh;
}

.app-container {
  max-width: 900px;
  margin: 0 auto;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1a1a2e;
  box-shadow: 0 0 40px rgba(0, 0, 0, 0.5);
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: linear-gradient(135deg, #16213e, #1a1a2e);
  border-bottom: 2px solid #e94560;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 32px;
  color: #e94560;
  font-weight: bold;
}

.app-title {
  font-size: 28px;
  font-weight: 800;
  color: #e94560;
  letter-spacing: 3px;
}

.app-subtitle {
  font-size: 12px;
  color: #a0a0b0;
  margin-left: 8px;
}

.checklist-btn {
  background: #16213e;
  color: #e0e0e0;
  border: 1px solid #e94560;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.checklist-btn:hover {
  background: #e94560;
  color: #fff;
}

.checklist-badge {
  background: #e94560;
  color: #fff;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: bold;
}

.timer-bar-container {
  padding: 12px 24px;
  background: #16213e;
  display: flex;
  align-items: center;
  gap: 16px;
}

.timer-display {
  font-size: 24px;
  font-weight: bold;
  color: #e94560;
  font-family: "Consolas", "Courier New", monospace;
  min-width: 70px;
}

.progress-bar-bg {
  flex: 1;
  height: 10px;
  background: #0f0f1a;
  border-radius: 5px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #e94560, #f39c12);
  border-radius: 5px;
  transition: width 0.3s ease;
}

.progress-label {
  font-size: 13px;
  color: #a0a0b0;
  min-width: 70px;
  text-align: right;
}

.main-content {
  flex: 1;
  padding: 24px;
  display: flex;
  flex-direction: column;
}

.nav-buttons {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 20px;
}

.nav-buttons.top-nav {
  margin-bottom: 16px;
}

.nav-btn {
  background: #16213e;
  color: #e0e0e0;
  border: 1px solid #333;
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.nav-btn:hover:not(:disabled) {
  background: #1f3060;
  border-color: #e94560;
}

.nav-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.nav-btn.primary {
  background: #e94560;
  border-color: #e94560;
  color: #fff;
  font-weight: bold;
  font-size: 16px;
  padding: 10px 28px;
}

.nav-btn.primary:hover {
  background: #c0392b;
  border-color: #c0392b;
}

.loading {
  text-align: center;
  padding: 60px;
  font-size: 18px;
  color: #a0a0b0;
}

.empty-state {
  text-align: center;
  padding: 60px;
  color: #a0a0b0;
  font-size: 16px;
}

.question-card {
  background: #16213e;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #333;
}

.question-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.year-tag {
  background: #e94560;
  color: #fff;
  padding: 4px 14px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 15px;
}

.page-tag {
  background: #1a1a2e;
  color: #a0a0b0;
  padding: 4px 14px;
  border-radius: 4px;
  font-size: 14px;
  border: 1px solid #333;
}

.status-tag {
  margin-left: auto;
  background: #1a1a2e;
  color: #a0a0b0;
  padding: 4px 14px;
  border-radius: 4px;
  font-size: 14px;
  border: 1px solid #333;
  cursor: pointer;
  transition: all 0.2s;
}

.status-tag.done {
  background: #27ae60;
  color: #fff;
  border-color: #27ae60;
}

.status-tag:hover {
  border-color: #e94560;
}

.pdf-image-wrapper {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.pdf-image {
  width: 100%;
  display: block;
}

.action-area {
  text-align: center;
  padding: 20px 0;
}

.done-btn {
  background: linear-gradient(135deg, #27ae60, #2ecc71);
  color: #fff;
  border: none;
  padding: 14px 48px;
  border-radius: 30px;
  font-size: 20px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 15px rgba(39, 174, 96, 0.4);
}

.done-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(39, 174, 96, 0.6);
}

.done-btn:active {
  transform: translateY(0);
}

.done-icon {
  margin-right: 8px;
}

.result-area {
  margin-top: 20px;
}

.result-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 24px;
}

.result-btn {
  padding: 12px 28px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: bold;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.answer-btn {
  background: #2c3e50;
  color: #e0e0e0;
  border-color: #3498db;
}

.answer-btn:hover,
.answer-btn.active {
  background: #3498db;
  color: #fff;
}

.explanation-btn {
  background: #2c3e50;
  color: #e0e0e0;
  border-color: #e67e22;
}

.explanation-btn:hover,
.explanation-btn.active {
  background: #e67e22;
  color: #fff;
}

.result-image-area h3 {
  color: #e94560;
  font-size: 18px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #333;
}

.checklist-panel {
  flex: 1;
  overflow-y: auto;
}

.checklist-panel h2 {
  color: #e94560;
  margin-bottom: 20px;
  font-size: 22px;
}

.checklist-tags {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.year-group {
  background: #16213e;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #333;
}

.year-label {
  font-weight: bold;
  color: #e94560;
  margin-bottom: 8px;
  font-size: 14px;
}

.page-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.check-tag {
  width: 32px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a1a2e;
  color: #666;
  border: 1px solid #333;
  border-radius: 4px;
  font-size: 11px;
  cursor: default;
  transition: all 0.2s;
}

.check-tag.done {
  background: #27ae60;
  color: #fff;
  border-color: #27ae60;
}
</style>
