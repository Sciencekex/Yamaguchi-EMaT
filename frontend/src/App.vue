<script setup>
import { ref, onUnmounted, computed } from "vue";

const API = "/api";

const question = ref(null);
const currentPageIdx = ref(0);
const loading = ref(false);
const showAnswer = ref(false);
const showExplanation = ref(false);
const answerIndex = ref(0);
const timer = ref(0);
const timerInterval = ref(null);
const completedSet = ref(new Set());
const totalQuestions = ref(0);
const completedCount = ref(0);
const history = ref([]);
const historyIndex = ref(-1);
const showChecklist = ref(false);
const sectionFilter = ref(null);
const sectionCounts = ref({});
const showSettings = ref(false);

const LS_HIDE_OLD = "emat_hide_old_years";
const LS_HIDE_ODE = "emat_hide_ode";

function loadSetting(key, def) {
  try { const v = localStorage.getItem(key); return v !== null ? v === "true" : def; }
  catch { return def; }
}
function saveSetting(key, val) {
  try { localStorage.setItem(key, String(val)); } catch {}
}

const hideOldYears = ref(loadSetting(LS_HIDE_OLD, true));
const hideODE = ref(loadSetting(LS_HIDE_ODE, true));

function toggleHideOld() { hideOldYears.value = !hideOldYears.value; saveSetting(LS_HIDE_OLD, hideOldYears.value); fetchRandom(); }
function toggleHideODE() { hideODE.value = !hideODE.value; saveSetting(LS_HIDE_ODE, hideODE.value); fetchRandom(); }

const SECTIONS = ["微分積分", "線形代数", "常微分方程式", "確率・統計"];
const visibleSections = computed(() => {
  return hideODE.value ? SECTIONS.filter(s => s !== "常微分方程式") : SECTIONS;
});
const SECTION_COLORS = {
  "微分積分": { bg: "#e74c3c", text: "#fff" },
  "線形代数": { bg: "#3498db", text: "#fff" },
  "常微分方程式": { bg: "#e67e22", text: "#fff" },
  "確率・統計": { bg: "#27ae60", text: "#fff" },
};

const qid = computed(() => {
  if (!question.value) return null;
  return question.value.id;
});

const isCompleted = computed(() => {
  if (!qid.value) return false;
  return completedSet.value.has(qid.value);
});

const progressPercent = computed(() => {
  if (totalQuestions.value === 0) return 0;
  return Math.round((completedCount.value / totalQuestions.value) * 100);
});

const timerDisplay = computed(() => {
  const m = Math.floor(timer.value / 60);
  const s = timer.value % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
});

const canGoBackHistory = computed(() => historyIndex.value > 0);
const canGoForwardHistory = computed(() => historyIndex.value < history.value.length - 1);

const pagesArray = computed(() => {
  if (!question.value) return [];
  const start = question.value.page_start;
  const end = question.value.page_end;
  const arr = [];
  for (let p = start; p <= end; p++) arr.push(p);
  return arr;
});

const currentPage = computed(() => {
  if (!pagesArray.value.length) return 0;
  return pagesArray.value[currentPageIdx.value];
});

const totalPagesInQuestion = computed(() => pagesArray.value.length);

const canGoPrevPage = computed(() => currentPageIdx.value > 0);
const canGoNextPage = computed(() => currentPageIdx.value < pagesArray.value.length - 1);

function startTimer() {
  stopTimer();
  timer.value = 0;
  timerInterval.value = setInterval(() => { timer.value++; }, 1000);
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
  totalQuestions.value = data.total_questions || data.total_pages;
  completedCount.value = data.completed;
  if (data.checklist) {
    completedSet.value = new Set(Object.keys(data.checklist));
  }
  if (data.section_counts) {
    sectionCounts.value = data.section_counts;
  }
}

async function fetchRandom() {
  loading.value = true;
  showAnswer.value = false;
  showExplanation.value = false;
  answerIndex.value = 0;
  currentPageIdx.value = 0;
  try {
    let url = `${API}/random`;
    const params = [];
    if (sectionFilter.value) params.push(`section=${encodeURIComponent(sectionFilter.value)}`);
    if (hideODE.value) params.push("exclude_sections=" + encodeURIComponent("常微分方程式"));
    if (hideOldYears.value) params.push("exclude_years=2003,2004,2005,2006");
    if (params.length) url += "?" + params.join("&");
    const res = await fetch(url);
    if (!res.ok) throw new Error("no question available");
    const data = await res.json();
    question.value = data;
    history.value = [...history.value.slice(0, historyIndex.value + 1), data];
    historyIndex.value = history.value.length - 1;
    startTimer();
    await loadIndex();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

function setSectionFilter(sec) {
  sectionFilter.value = sectionFilter.value === sec ? null : sec;
  fetchRandom();
}

function goToHistory(idx) {
  if (idx < 0 || idx >= history.value.length) return;
  historyIndex.value = idx;
  question.value = history.value[idx];
  showAnswer.value = false;
  showExplanation.value = false;
  answerIndex.value = 0;
  currentPageIdx.value = 0;
  startTimer();
}

function prevQuestion() { goToHistory(historyIndex.value - 1); }
function nextQuestion() { goToHistory(historyIndex.value + 1); }

function prevPage() {
  if (currentPageIdx.value > 0) {
    currentPageIdx.value--;
  }
}

function nextPage() {
  if (currentPageIdx.value < pagesArray.value.length - 1) {
    currentPageIdx.value++;
  }
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
    fetch(`${API}/answer_index/${question.value.year}/${currentPage.value}`)
      .then((r) => r.json())
      .then((d) => { answerIndex.value = d.answer_file_index; });
  }
}

function onShowExplanation() {
  showExplanation.value = true;
  showAnswer.value = false;
  if (question.value) {
    fetch(`${API}/answer_index/${question.value.year}/${currentPage.value}`)
      .then((r) => r.json())
      .then((d) => { answerIndex.value = d.answer_file_index; });
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
  return `${API}/pdf/${question.value.year}/problem/${currentPage.value}`;
}

function answerImageUrl() {
  if (!question.value) return "";
  return `${API}/pdf/${question.value.year}/answer${answerIndex.value}/${currentPage.value}`;
}

function sectionStyle(sec) {
  const c = SECTION_COLORS[sec] || { bg: "#666", text: "#fff" };
  return { background: c.bg, color: c.text };
}

onUnmounted(() => { stopTimer(); });

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
      <div class="header-actions">
        <button class="settings-btn" @click="showSettings = true" title="設定">
          &#x2699;
        </button>
        <button class="checklist-btn" @click="showChecklist = !showChecklist">
          {{ showChecklist ? "閉じる" : "CheckList" }}
          <span class="checklist-badge">{{ completedCount }}/{{ totalQuestions }}</span>
        </button>
      </div>
    </header>

    <div class="timer-bar-container">
      <div class="timer-display">{{ timerDisplay }}</div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
      <div class="progress-label">{{ progressPercent }}% 完了</div>
    </div>

    <div class="section-filters">
      <button v-for="sec in visibleSections" :key="sec"
        class="section-filter-btn" :class="{ active: sectionFilter === sec }"
        :style="sectionFilter === sec ? sectionStyle(sec) : {}"
        @click="setSectionFilter(sec)">
        {{ sec }}
        <span class="sec-count">{{ sectionCounts[sec] || 0 }}</span>
      </button>
      <button class="section-filter-btn all-btn" :class="{ active: sectionFilter === null }"
        @click="sectionFilter = null; fetchRandom()">
        全分野 <span class="sec-count">{{ totalQuestions }}</span>
      </button>
    </div>

    <div class="main-content">
      <div class="question-area" v-if="!showChecklist">
        <div class="nav-buttons top-nav">
          <button class="nav-btn" :disabled="!canGoBackHistory" @click="prevQuestion">&#x25C0; 前の問</button>
          <button class="nav-btn primary" @click="fetchRandom">&#x1F3B2; ランダム出題</button>
          <button class="nav-btn" :disabled="!canGoForwardHistory" @click="nextQuestion">次の問 &#x25B6;</button>
        </div>

        <div v-if="loading" class="loading">読み込み中...</div>

        <div v-else-if="question" class="question-card">
          <div class="question-meta">
            <span class="year-tag">{{ question.year }}年</span>
            <span v-if="question.section" class="section-tag" :style="sectionStyle(question.section)">
              {{ question.section }}
            </span>
            <span v-if="question.qnum" class="qnum-tag">Q{{ question.qnum }}</span>
            <span class="page-indicator">
              {{ currentPageIdx + 1 }}/{{ totalPagesInQuestion }} ページ
            </span>
            <span class="status-tag" :class="{ done: isCompleted }" @click="toggleChecklist">
              {{ isCompleted ? "&#x2611; 完了" : "&#x2610; 未完了" }}
            </span>
          </div>

          <div class="pdf-image-wrapper">
            <img :src="problemImageUrl()" alt="問題" class="pdf-image" />
          </div>

          <div class="page-nav-area">
            <button class="page-nav-btn" :disabled="!canGoPrevPage" @click="prevPage">
              &#x25C0; 前頁
            </button>
            <span class="page-nav-info">
              <template v-for="(p, i) in pagesArray" :key="p">
                <span class="page-dot" :class="{ current: i === currentPageIdx }"
                  @click="currentPageIdx = i">{{ i + 1 }}</span>
                <span v-if="i < pagesArray.length - 1" class="dot-sep"></span>
              </template>
            </span>
            <button class="page-nav-btn" :disabled="!canGoNextPage" @click="nextPage">
              次頁 &#x25B6;
            </button>
          </div>

          <div v-if="!showAnswer && !showExplanation" class="action-area">
            <button class="done-btn" @click="onDone">
              <span class="done-icon">&#x2705;</span> やった！
            </button>
          </div>

          <div v-if="showAnswer || showExplanation" class="result-area">
            <div class="result-buttons">
              <button class="result-btn answer-btn" :class="{ active: showAnswer }" @click="onShowAnswer">
                &#x1F4D6; 答えを見る
              </button>
              <button class="result-btn explanation-btn" :class="{ active: showExplanation }" @click="onShowExplanation">
                &#x1F4DD; 解説を見る
              </button>
            </div>
            <div v-if="showAnswer" class="result-image-area">
              <h3>答え</h3>
              <div class="pdf-image-wrapper">
                <img :src="answerImageUrl()" alt="答え" class="pdf-image" />
              </div>
            </div>
            <div v-if="showExplanation" class="result-image-area">
              <h3>解説</h3>
              <div class="pdf-image-wrapper">
                <img :src="answerImageUrl()" alt="解説" class="pdf-image" />
              </div>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <p>問題がありません。「ランダム出題」を押してください。</p>
        </div>
      </div>

      <div class="checklist-panel" v-if="showChecklist">
        <h2>CheckList ({{ completedCount }}/{{ totalQuestions }})</h2>
        <div class="checklist-by-section">
          <div v-for="sec in visibleSections" :key="sec" class="cl-section-group">
            <div class="cl-section-header" :style="sectionStyle(sec)">
              {{ sec }} — {{ sectionCounts[sec] || 0 }}問
            </div>
            <div class="cl-question-grid">
              <span v-for="y in 23" :key="y" class="cl-year-row">
                <span class="cl-year-label">{{ y + 2002 }}</span>
                <span v-for="q in 10" :key="q" class="cl-dot"
                  :class="{ done: completedSet.has(`${y + 2002}_${sec}_q${q}`) }"
                  :title="`${y + 2002} ${sec} Q${q}`">
                </span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-if="showSettings" class="settings-overlay" @click.self="showSettings = false">
    <div class="settings-panel">
      <div class="settings-header">
        <h2>&#x2699; 設定</h2>
        <button class="settings-close" @click="showSettings = false">&times;</button>
      </div>
      <div class="settings-body">
        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-label">古い年度を除外</span>
            <span class="setting-desc">2003〜2006年の問題を出題しない</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" :checked="hideOldYears" @change="toggleHideOld">
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-label">常微分方程式を非表示</span>
            <span class="setting-desc">常微分方程式の分野を出題・表示しない</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" :checked="hideODE" @change="toggleHideODE">
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
      <div class="settings-footer">
        <button class="settings-done-btn" @click="showSettings = false">閉じる</button>
      </div>
    </div>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: "Segoe UI", "Hiragino Sans", "Meiryo", sans-serif;
  background: #0f0f1a; color: #e0e0e0; min-height: 100vh;
}

.app-container {
  max-width: 900px; margin: 0 auto; min-height: 100vh;
  display: flex; flex-direction: column;
  background: #1a1a2e; box-shadow: 0 0 40px rgba(0,0,0,0.5);
}

.app-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px; background: linear-gradient(135deg, #16213e, #1a1a2e);
  border-bottom: 2px solid #e94560;
}

.header-actions { display: flex; align-items: center; gap: 10px; }

.settings-btn {
  background: #16213e; color: #a0a0b0; border: 1px solid #444;
  width: 34px; height: 34px; border-radius: 50%; cursor: pointer; font-size: 18px;
  display: flex; align-items: center; justify-content: center; transition: all 0.2s;
}
.settings-btn:hover { background: #e94560; color: #fff; border-color: #e94560; }

.logo-area { display: flex; align-items: center; gap: 10px; }
.logo-icon { font-size: 28px; color: #e94560; font-weight: bold; }
.app-title { font-size: 24px; font-weight: 800; color: #e94560; letter-spacing: 2px; }
.app-subtitle { font-size: 11px; color: #a0a0b0; }

.checklist-btn {
  background: #16213e; color: #e0e0e0; border: 1px solid #e94560;
  padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px;
  display: flex; align-items: center; gap: 8px; transition: all 0.2s;
}
.checklist-btn:hover { background: #e94560; color: #fff; }
.checklist-badge { background: #e94560; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold; }

.timer-bar-container {
  padding: 10px 20px; background: #16213e;
  display: flex; align-items: center; gap: 14px;
}
.timer-display { font-size: 22px; font-weight: bold; color: #e94560; font-family: "Consolas", monospace; min-width: 65px; }
.progress-bar-bg { flex: 1; height: 8px; background: #0f0f1a; border-radius: 4px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: linear-gradient(90deg, #e94560, #f39c12); border-radius: 4px; transition: width 0.3s; }
.progress-label { font-size: 12px; color: #a0a0b0; min-width: 60px; text-align: right; }

.section-filters {
  display: flex; gap: 6px; padding: 10px 20px; background: #0f0f1a;
  flex-wrap: wrap; justify-content: center;
}
.section-filter-btn {
  padding: 5px 12px; border-radius: 16px; border: 1px solid #333;
  background: #16213e; color: #888; font-size: 12px; cursor: pointer;
  transition: all 0.2s; display: flex; align-items: center; gap: 4px;
}
.section-filter-btn:hover { border-color: #e94560; color: #e0e0e0; }
.section-filter-btn.active { border-color: transparent; font-weight: bold; }
.section-filter-btn.all-btn { border-color: #555; color: #aaa; }
.section-filter-btn.all-btn.active { background: #555; color: #fff; }
.sec-count { font-size: 10px; opacity: 0.8; }

.main-content { flex: 1; padding: 16px 20px; display: flex; flex-direction: column; }

.nav-buttons { display: flex; justify-content: center; gap: 10px; margin-bottom: 14px; }
.nav-btn {
  background: #16213e; color: #e0e0e0; border: 1px solid #333;
  padding: 7px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s;
}
.nav-btn:hover:not(:disabled) { background: #1f3060; border-color: #e94560; }
.nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.nav-btn.primary { background: #e94560; border-color: #e94560; color: #fff; font-weight: bold; font-size: 15px; padding: 8px 24px; }
.nav-btn.primary:hover { background: #c0392b; }

.loading { text-align: center; padding: 50px; font-size: 16px; color: #a0a0b0; }
.empty-state { text-align: center; padding: 50px; color: #a0a0b0; font-size: 15px; }

.question-card { background: #16213e; border-radius: 10px; padding: 18px; border: 1px solid #333; }

.question-meta {
  display: flex; align-items: center; gap: 8px; margin-bottom: 14px; flex-wrap: wrap;
}
.year-tag { background: #e94560; color: #fff; padding: 3px 12px; border-radius: 4px; font-weight: bold; font-size: 14px; }
.section-tag { padding: 3px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; }
.qnum-tag { background: #1a1a2e; color: #f39c12; padding: 3px 10px; border-radius: 4px; font-size: 13px; font-weight: bold; border: 1px solid #f39c12; }
.page-indicator { background: #1a1a2e; color: #a0a0b0; padding: 3px 10px; border-radius: 4px; font-size: 12px; border: 1px solid #333; }
.status-tag {
  margin-left: auto; background: #1a1a2e; color: #a0a0b0; padding: 3px 12px;
  border-radius: 4px; font-size: 13px; border: 1px solid #333; cursor: pointer; transition: all 0.2s;
}
.status-tag.done { background: #27ae60; color: #fff; border-color: #27ae60; }
.status-tag:hover { border-color: #e94560; }

.pdf-image-wrapper { background: #fff; border-radius: 6px; overflow: hidden; margin-bottom: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.3); }
.pdf-image { width: 100%; display: block; }

.page-nav-area {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  padding: 10px 0; margin-bottom: 12px;
}
.page-nav-btn {
  background: #1a1a2e; color: #a0a0b0; border: 1px solid #444;
  padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; transition: all 0.2s;
}
.page-nav-btn:hover:not(:disabled) { background: #e94560; color: #fff; border-color: #e94560; }
.page-nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.page-nav-info { display: flex; align-items: center; gap: 2px; }
.page-dot {
  width: 24px; height: 22px; display: flex; align-items: center; justify-content: center;
  background: #0f0f1a; color: #555; border-radius: 3px; font-size: 11px;
  cursor: pointer; transition: all 0.2s; border: 1px solid transparent;
}
.page-dot:hover { border-color: #e94560; color: #e0e0e0; }
.page-dot.current { background: #e94560; color: #fff; font-weight: bold; }
.dot-sep { width: 2px; }

.action-area { text-align: center; padding: 12px 0; }
.done-btn {
  background: linear-gradient(135deg, #27ae60, #2ecc71); color: #fff; border: none;
  padding: 12px 40px; border-radius: 24px; font-size: 18px; font-weight: bold;
  cursor: pointer; transition: all 0.3s; box-shadow: 0 4px 12px rgba(39,174,96,0.4);
}
.done-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(39,174,96,0.6); }
.done-btn:active { transform: translateY(0); }
.done-icon { margin-right: 6px; }

.result-area { margin-top: 16px; }
.result-buttons { display: flex; gap: 10px; justify-content: center; margin-bottom: 18px; }
.result-btn {
  padding: 10px 24px; border-radius: 8px; font-size: 15px; font-weight: bold;
  border: 2px solid transparent; cursor: pointer; transition: all 0.2s;
}
.answer-btn { background: #2c3e50; color: #e0e0e0; border-color: #3498db; }
.answer-btn:hover, .answer-btn.active { background: #3498db; color: #fff; }
.explanation-btn { background: #2c3e50; color: #e0e0e0; border-color: #e67e22; }
.explanation-btn:hover, .explanation-btn.active { background: #e67e22; color: #fff; }
.result-image-area h3 { color: #e94560; font-size: 16px; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #333; }

.checklist-panel { flex: 1; overflow-y: auto; }
.checklist-panel h2 { color: #e94560; margin-bottom: 16px; font-size: 20px; }
.checklist-by-section { display: flex; flex-direction: column; gap: 14px; }
.cl-section-group { background: #16213e; border-radius: 8px; padding: 12px; border: 1px solid #333; }
.cl-section-header { padding: 4px 10px; border-radius: 4px; font-size: 13px; font-weight: bold; display: inline-block; margin-bottom: 8px; }
.cl-question-grid { display: flex; flex-direction: column; gap: 4px; }
.cl-year-row { display: flex; align-items: center; gap: 5px; }
.cl-year-label { font-size: 11px; color: #666; min-width: 32px; text-align: right; }
.cl-dot {
  width: 14px; height: 14px; border-radius: 3px; background: #0f0f1a;
  border: 1px solid #333; cursor: default; transition: all 0.2s;
}
.cl-dot.done { background: #27ae60; border-color: #27ae60; }

.settings-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.settings-panel {
  background: #1a1a2e; border: 1px solid #e94560; border-radius: 12px;
  width: 380px; max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.settings-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #333;
}
.settings-header h2 { color: #e94560; font-size: 18px; display: flex; align-items: center; gap: 6px; }
.settings-close {
  background: none; border: none; color: #888; font-size: 24px; cursor: pointer;
}
.settings-close:hover { color: #e94560; }
.settings-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 16px; }
.setting-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px; background: #16213e; border-radius: 8px; border: 1px solid #333;
}
.setting-info { display: flex; flex-direction: column; gap: 3px; }
.setting-label { color: #e0e0e0; font-size: 14px; font-weight: bold; }
.setting-desc { color: #666; font-size: 11px; }

.toggle-switch { position: relative; display: inline-block; width: 44px; height: 24px; flex-shrink: 0; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute; inset: 0; cursor: pointer; background: #333;
  border-radius: 24px; transition: all 0.3s;
}
.toggle-slider::before {
  content: ""; position: absolute; height: 18px; width: 18px;
  left: 3px; bottom: 3px; background: #888; border-radius: 50%; transition: all 0.3s;
}
.toggle-switch input:checked + .toggle-slider { background: #e94560; }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); background: #fff; }

.settings-footer { padding: 12px 20px; border-top: 1px solid #333; text-align: right; }
.settings-done-btn {
  background: #e94560; color: #fff; border: none; padding: 8px 24px;
  border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; transition: all 0.2s;
}
.settings-done-btn:hover { background: #c0392b; }
</style>
