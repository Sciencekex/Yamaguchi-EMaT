<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from "vue";
import * as pdfjsLib from "pdfjs-dist";
import pdfjsWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorkerUrl;

const IMG_BASE = import.meta.env.PROD ? "/Yamaguchi-EMaT" : "";
const DATA_URL = IMG_BASE + "/data/question_map.json";
const PDF_BASE = IMG_BASE + "/QuestionData";

const questionMap = ref([]);
const question = ref(null);
const currentPageIdx = ref(0);
const currentProblemImage = ref("");
const currentAnswerImage = ref("");
const loading = ref(false);
const showAnswer = ref(false);
const showExplanation = ref(false);
const answerFileIdx = ref(0);
const timer = ref(0);
const timerInterval = ref(null);
const completedSet = ref(new Set());
const totalQuestions = ref(0);
const completedCount = ref(0);
const history = ref([]);
const historyIndex = ref(-1);
const showChecklist = ref(false);
const showSettings = ref(false);
const sectionFilter = ref(null);
const sectionCounts = ref({});

const LS_HIDE_OLD = "emat_hide_old_years";
const LS_HIDE_ODE = "emat_hide_ode";
const LS_CHECKLIST = "emat_checklist_v3";

function loadSetting(key, def) {
  try { const v = localStorage.getItem(key); return v !== null ? (key === LS_CHECKLIST ? JSON.parse(v) : v === "true") : def; }
  catch { return def; }
}
function saveSetting(key, val) {
  try { localStorage.setItem(key, typeof val === "object" ? JSON.stringify(val) : String(val)); } catch {}
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

const qid = computed(() => question.value?.id || null);
const isCompleted = computed(() => qid.value ? completedSet.value.has(qid.value) : false);
const progressPercent = computed(() => totalQuestions.value === 0 ? 0 : Math.round((completedCount.value / totalQuestions.value) * 100));
const timerDisplay = computed(() => {
  const m = Math.floor(timer.value / 60);
  const s = timer.value % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
});
const canGoBackHistory = computed(() => historyIndex.value > 0);
const canGoForwardHistory = computed(() => historyIndex.value < history.value.length - 1);
const pagesArray = computed(() => {
  if (!question.value) return [];
  const arr = [];
  for (let p = question.value.page_start; p <= question.value.page_end; p++) arr.push(p);
  return arr;
});
const currentPage = computed(() => pagesArray.value[currentPageIdx.value] || 0);
const totalPagesInQuestion = computed(() => pagesArray.value.length);
const canGoPrevPage = computed(() => currentPageIdx.value > 0);
const canGoNextPage = computed(() => currentPageIdx.value < pagesArray.value.length - 1);

let pdfCache = {};

async function renderPdfPage(year, type, pageNum) {
  const key = `${year}_${type}`;
  if (!pdfCache[key]) {
    const fileName = type === "problem"
      ? `problem${year}.pdf`
      : (type === "answer" ? `kaito${year}-01.pdf` : `kaito${year}-02.pdf`);
    const url = `${PDF_BASE}/${year}/${fileName}`;
    try {
      const resp = await fetch(url);
      if (!resp.ok) return "";
      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      const loadingTask = pdfjsLib.getDocument({ url: blobUrl, disableRange: true, disableStream: true });
      pdfCache[key] = { pdf: await loadingTask.promise, blobUrl };
    } catch (e) {
      console.error("PDF load error:", url, e);
      return "";
    }
  }
  try {
    const pdf = pdfCache[key].pdf;
    if (pageNum < 0 || pageNum >= pdf.numPages) {
      if (type === "problem") return "";
      const fileName2 = `kaito${year}-02.pdf`;
      const url2 = `${PDF_BASE}/${year}/${fileName2}`;
      const key2 = `${year}_answer2`;
      if (!pdfCache[key2]) {
        try {
          const resp2 = await fetch(url2);
          if (resp2.ok) {
            const blob2 = await resp2.blob();
            const blobUrl2 = URL.createObjectURL(blob2);
            const lt = pdfjsLib.getDocument({ url: blobUrl2, disableRange: true, disableStream: true });
            pdfCache[key2] = { pdf: await lt.promise, blobUrl: blobUrl2 };
          } else return "";
        } catch { return ""; }
      }
      const pdf2 = pdfCache[key2].pdf;
      const actualPage = pageNum - pdf.numPages;
      if (actualPage < 0 || actualPage >= pdf2.numPages) return "";
      const page = await pdf2.getPage(actualPage + 1);
      const viewport = page.getViewport({ scale: 1.5 });
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const ctx = canvas.getContext("2d");
      await page.render({ canvasContext: ctx, viewport }).promise;
      return canvas.toDataURL("image/png");
    }
    const page = await pdf.getPage(pageNum + 1);
    const viewport = page.getViewport({ scale: 1.5 });
    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext("2d");
    await page.render({ canvasContext: ctx, viewport }).promise;
    return canvas.toDataURL("image/png");
  } catch (e) {
    console.error("PDF render error:", e);
    return "";
  }
}

async function refreshProblemImage() {
  if (!question.value) return;
  currentProblemImage.value = "";
  pdfCache = {};
  const img = await renderPdfPage(question.value.year, "problem", currentPage.value);
  currentProblemImage.value = img;
}

async function refreshAnswerImage() {
  if (!question.value) return;
  currentAnswerImage.value = "";
  const ansType = answerFileIdx.value === 0 ? "answer" : "answer2";
  const img = await renderPdfPage(question.value.year, ansType, currentPage.value);
  currentAnswerImage.value = img;
}

watch(currentPageIdx, () => {
  if (question.value) refreshProblemImage();
});

function startTimer() {
  stopTimer();
  timer.value = 0;
  timerInterval.value = setInterval(() => { timer.value++; }, 1000);
}
function stopTimer() {
  if (timerInterval.value) { clearInterval(timerInterval.value); timerInterval.value = null; }
}

function initData() {
  completedSet.value = new Set(loadSetting(LS_CHECKLIST, []));
  const cl = loadSetting(LS_CHECKLIST, []);
  completedCount.value = cl.length;
}

function computeSectionCounts() {
  const counts = {};
  for (const q of questionMap.value) {
    const s = q.section || "";
    if (s) counts[s] = (counts[s] || 0) + 1;
  }
  sectionCounts.value = counts;
  totalQuestions.value = questionMap.value.length;
}

function fetchRandom() {
  loading.value = true;
  showAnswer.value = false;
  showExplanation.value = false;
  currentPageIdx.value = 0;
  currentProblemImage.value = "";
  currentAnswerImage.value = "";
  pdfCache = {};

  const completed = new Set(loadSetting(LS_CHECKLIST, []));
  let pool = [...questionMap.value];

  if (completed.size > 0) {
    const remaining = pool.filter(q => !completed.has(q.id));
    if (remaining.length > 0) pool = remaining;
  }
  if (hideODE.value) {
    pool = pool.filter(q => q.section !== "常微分方程式");
  }
  if (hideOldYears.value) {
    pool = pool.filter(q => ![2003, 2004, 2005, 2006].includes(q.year));
  }
  if (sectionFilter.value) {
    pool = pool.filter(q => q.section === sectionFilter.value);
  }

  if (pool.length === 0) {
    pool = questionMap.value.filter(q => {
      if (hideODE.value && q.section === "常微分方程式") return false;
      if (hideOldYears.value && [2003, 2004, 2005, 2006].includes(q.year)) return false;
      if (sectionFilter.value && q.section !== sectionFilter.value) return false;
      return true;
    });
  }

  if (pool.length === 0) {
    loading.value = false;
    return;
  }

  const idx = Math.floor(Math.random() * pool.length);
  question.value = pool[idx];
  history.value = [...history.value.slice(0, historyIndex.value + 1), pool[idx]];
  historyIndex.value = history.value.length - 1;
  startTimer();
  loading.value = false;

  nextTick(() => refreshProblemImage());
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
  currentPageIdx.value = 0;
  currentProblemImage.value = "";
  currentAnswerImage.value = "";
  pdfCache = {};
  startTimer();
  nextTick(() => refreshProblemImage());
}

function prevQuestion() { goToHistory(historyIndex.value - 1); }
function nextQuestion() { goToHistory(historyIndex.value + 1); }
function prevPage() { if (currentPageIdx.value > 0) currentPageIdx.value--; }
function nextPage() { if (currentPageIdx.value < pagesArray.value.length - 1) currentPageIdx.value++; }

function onDone() { stopTimer(); }

async function onShowAnswer() {
  showAnswer.value = true;
  showExplanation.value = false;
  await refreshAnswerImage();
}

async function onShowExplanation() {
  showExplanation.value = true;
  showAnswer.value = false;
  await refreshAnswerImage();
}

function toggleChecklist() {
  if (!qid.value) return;
  const cl = new Set(loadSetting(LS_CHECKLIST, []));
  if (cl.has(qid.value)) {
    cl.delete(qid.value);
  } else {
    cl.add(qid.value);
  }
  completedSet.value = cl;
  completedCount.value = cl.size;
  saveSetting(LS_CHECKLIST, [...cl]);
}

function sectionStyle(sec) {
  const c = SECTION_COLORS[sec] || { bg: "#666", text: "#fff" };
  return { background: c.bg, color: c.text };
}

onMounted(async () => {
  initData();
  try {
    const res = await fetch(DATA_URL);
    const data = await res.json();
    questionMap.value = data;
    computeSectionCounts();
    fetchRandom();
  } catch (e) {
    console.error("Failed to load question map:", e);
  }
});

onUnmounted(() => { stopTimer(); });
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
        <button class="settings-btn" @click="showSettings = true" title="設定">&#x2699;</button>
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
        {{ sec }} <span class="sec-count">{{ sectionCounts[sec] || 0 }}</span>
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
            <span v-if="question.section" class="section-tag" :style="sectionStyle(question.section)">{{ question.section }}</span>
            <span v-if="question.qnum" class="qnum-tag">Q{{ question.qnum }}</span>
            <span class="page-indicator">{{ currentPageIdx + 1 }}/{{ totalPagesInQuestion }} ページ</span>
            <span class="status-tag" :class="{ done: isCompleted }" @click="toggleChecklist">
              {{ isCompleted ? "&#x2611; 完了" : "&#x2610; 未完了" }}
            </span>
          </div>

          <div class="pdf-image-wrapper">
            <img v-if="currentProblemImage" :src="currentProblemImage" alt="問題" class="pdf-image" />
            <div v-else class="pdf-loading">PDF 読込中...</div>
          </div>

          <div class="page-nav-area">
            <button class="page-nav-btn" :disabled="!canGoPrevPage" @click="prevPage">&#x25C0; 前頁</button>
            <span class="page-nav-info">
              <template v-for="(p, i) in pagesArray" :key="p">
                <span class="page-dot" :class="{ current: i === currentPageIdx }" @click="currentPageIdx = i">{{ i + 1 }}</span>
                <span v-if="i < pagesArray.length - 1" class="dot-sep"></span>
              </template>
            </span>
            <button class="page-nav-btn" :disabled="!canGoNextPage" @click="nextPage">次頁 &#x25B6;</button>
          </div>

          <div v-if="!showAnswer && !showExplanation" class="action-area">
            <button class="done-btn" @click="onDone"><span class="done-icon">&#x2705;</span> やった！</button>
          </div>

          <div v-if="showAnswer || showExplanation" class="result-area">
            <div class="result-buttons">
              <button class="result-btn answer-btn" :class="{ active: showAnswer }" @click="onShowAnswer">&#x1F4D6; 答えを見る</button>
              <button class="result-btn explanation-btn" :class="{ active: showExplanation }" @click="onShowExplanation">&#x1F4DD; 解説を見る</button>
            </div>
            <div v-if="showAnswer" class="result-image-area">
              <h3>答え</h3>
              <div class="pdf-image-wrapper">
                <img v-if="currentAnswerImage" :src="currentAnswerImage" alt="答え" class="pdf-image" />
                <div v-else class="pdf-loading">読込中...</div>
              </div>
            </div>
            <div v-if="showExplanation" class="result-image-area">
              <h3>解説</h3>
              <div class="pdf-image-wrapper">
                <img v-if="currentAnswerImage" :src="currentAnswerImage" alt="解説" class="pdf-image" />
                <div v-else class="pdf-loading">読込中...</div>
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
            <div class="cl-section-header" :style="sectionStyle(sec)">{{ sec }} — {{ sectionCounts[sec] || 0 }}問</div>
            <div class="cl-question-grid">
              <span v-for="y in 23" :key="y" class="cl-year-row">
                <span class="cl-year-label">{{ y + 2002 }}</span>
                <span v-for="q in 10" :key="q" class="cl-dot"
                  :class="{ done: completedSet.has(`${y + 2002}_${sec}_q${q}`) }"
                  :title="`${y + 2002} ${sec} Q${q}`"></span>
              </span>
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
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: "Segoe UI", "Hiragino Sans", "Meiryo", sans-serif; background: #0f0f1a; color: #e0e0e0; min-height: 100vh; }
.app-container { max-width: 900px; margin: 0 auto; min-height: 100vh; display: flex; flex-direction: column; background: #1a1a2e; box-shadow: 0 0 40px rgba(0,0,0,0.5); }
.app-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; background: linear-gradient(135deg, #16213e, #1a1a2e); border-bottom: 2px solid #e94560; }
.header-actions { display: flex; align-items: center; gap: 10px; }
.settings-btn { background: #16213e; color: #a0a0b0; border: 1px solid #444; width: 34px; height: 34px; border-radius: 50%; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
.settings-btn:hover { background: #e94560; color: #fff; border-color: #e94560; }
.logo-area { display: flex; align-items: center; gap: 10px; }
.logo-icon { font-size: 28px; color: #e94560; font-weight: bold; }
.app-title { font-size: 24px; font-weight: 800; color: #e94560; letter-spacing: 2px; }
.app-subtitle { font-size: 11px; color: #a0a0b0; }
.checklist-btn { background: #16213e; color: #e0e0e0; border: 1px solid #e94560; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 8px; transition: all 0.2s; }
.checklist-btn:hover { background: #e94560; color: #fff; }
.checklist-badge { background: #e94560; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold; }
.timer-bar-container { padding: 10px 20px; background: #16213e; display: flex; align-items: center; gap: 14px; }
.timer-display { font-size: 22px; font-weight: bold; color: #e94560; font-family: "Consolas", monospace; min-width: 65px; }
.progress-bar-bg { flex: 1; height: 8px; background: #0f0f1a; border-radius: 4px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: linear-gradient(90deg, #e94560, #f39c12); border-radius: 4px; transition: width 0.3s; }
.progress-label { font-size: 12px; color: #a0a0b0; min-width: 60px; text-align: right; }
.section-filters { display: flex; gap: 6px; padding: 10px 20px; background: #0f0f1a; flex-wrap: wrap; justify-content: center; }
.section-filter-btn { padding: 5px 12px; border-radius: 16px; border: 1px solid #333; background: #16213e; color: #888; font-size: 12px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 4px; }
.section-filter-btn:hover { border-color: #e94560; color: #e0e0e0; }
.section-filter-btn.active { border-color: transparent; font-weight: bold; }
.section-filter-btn.all-btn { border-color: #555; color: #aaa; }
.section-filter-btn.all-btn.active { background: #555; color: #fff; }
.sec-count { font-size: 10px; opacity: 0.8; }
.main-content { flex: 1; padding: 16px 20px; display: flex; flex-direction: column; }
.nav-buttons { display: flex; justify-content: center; gap: 10px; margin-bottom: 14px; }
.nav-btn { background: #16213e; color: #e0e0e0; border: 1px solid #333; padding: 7px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.nav-btn:hover:not(:disabled) { background: #1f3060; border-color: #e94560; }
.nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.nav-btn.primary { background: #e94560; border-color: #e94560; color: #fff; font-weight: bold; font-size: 15px; padding: 8px 24px; }
.nav-btn.primary:hover { background: #c0392b; }
.loading { text-align: center; padding: 50px; font-size: 16px; color: #a0a0b0; }
.empty-state { text-align: center; padding: 50px; color: #a0a0b0; font-size: 15px; }
.question-card { background: #16213e; border-radius: 10px; padding: 18px; border: 1px solid #333; }
.question-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.year-tag { background: #e94560; color: #fff; padding: 3px 12px; border-radius: 4px; font-weight: bold; font-size: 14px; }
.section-tag { padding: 3px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; }
.qnum-tag { background: #1a1a2e; color: #f39c12; padding: 3px 10px; border-radius: 4px; font-size: 13px; font-weight: bold; border: 1px solid #f39c12; }
.page-indicator { background: #1a1a2e; color: #a0a0b0; padding: 3px 10px; border-radius: 4px; font-size: 12px; border: 1px solid #333; }
.status-tag { margin-left: auto; background: #1a1a2e; color: #a0a0b0; padding: 3px 12px; border-radius: 4px; font-size: 13px; border: 1px solid #333; cursor: pointer; transition: all 0.2s; }
.status-tag.done { background: #27ae60; color: #fff; border-color: #27ae60; }
.status-tag:hover { border-color: #e94560; }
.pdf-image-wrapper { background: #fff; border-radius: 6px; overflow: hidden; margin-bottom: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.3); }
.pdf-image { width: 100%; display: block; }
.pdf-loading { padding: 40px; text-align: center; color: #999; background: #f5f5f5; }
.page-nav-area { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 10px 0; margin-bottom: 12px; }
.page-nav-btn { background: #1a1a2e; color: #a0a0b0; border: 1px solid #444; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; transition: all 0.2s; }
.page-nav-btn:hover:not(:disabled) { background: #e94560; color: #fff; border-color: #e94560; }
.page-nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.page-nav-info { display: flex; align-items: center; gap: 2px; }
.page-dot { width: 24px; height: 22px; display: flex; align-items: center; justify-content: center; background: #0f0f1a; color: #555; border-radius: 3px; font-size: 11px; cursor: pointer; transition: all 0.2s; border: 1px solid transparent; }
.page-dot:hover { border-color: #e94560; color: #e0e0e0; }
.page-dot.current { background: #e94560; color: #fff; font-weight: bold; }
.dot-sep { width: 2px; }
.action-area { text-align: center; padding: 12px 0; }
.done-btn { background: linear-gradient(135deg, #27ae60, #2ecc71); color: #fff; border: none; padding: 12px 40px; border-radius: 24px; font-size: 18px; font-weight: bold; cursor: pointer; transition: all 0.3s; box-shadow: 0 4px 12px rgba(39,174,96,0.4); }
.done-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(39,174,96,0.6); }
.done-btn:active { transform: translateY(0); }
.done-icon { margin-right: 6px; }
.result-area { margin-top: 16px; }
.result-buttons { display: flex; gap: 10px; justify-content: center; margin-bottom: 18px; }
.result-btn { padding: 10px 24px; border-radius: 8px; font-size: 15px; font-weight: bold; border: 2px solid transparent; cursor: pointer; transition: all 0.2s; }
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
.cl-dot { width: 14px; height: 14px; border-radius: 3px; background: #0f0f1a; border: 1px solid #333; cursor: default; transition: all 0.2s; }
.cl-dot.done { background: #27ae60; border-color: #27ae60; }
.settings-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.settings-panel { background: #1a1a2e; border: 1px solid #e94560; border-radius: 12px; width: 380px; max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }
.settings-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #333; }
.settings-header h2 { color: #e94560; font-size: 18px; display: flex; align-items: center; gap: 6px; }
.settings-close { background: none; border: none; color: #888; font-size: 24px; cursor: pointer; }
.settings-close:hover { color: #e94560; }
.settings-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 16px; }
.setting-row { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #16213e; border-radius: 8px; border: 1px solid #333; }
.setting-info { display: flex; flex-direction: column; gap: 3px; }
.setting-label { color: #e0e0e0; font-size: 14px; font-weight: bold; }
.setting-desc { color: #666; font-size: 11px; }
.toggle-switch { position: relative; display: inline-block; width: 44px; height: 24px; flex-shrink: 0; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider { position: absolute; inset: 0; cursor: pointer; background: #333; border-radius: 24px; transition: all 0.3s; }
.toggle-slider::before { content: ""; position: absolute; height: 18px; width: 18px; left: 3px; bottom: 3px; background: #888; border-radius: 50%; transition: all 0.3s; }
.toggle-switch input:checked + .toggle-slider { background: #e94560; }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); background: #fff; }
.settings-footer { padding: 12px 20px; border-top: 1px solid #333; text-align: right; }
.settings-done-btn { background: #e94560; color: #fff; border: none; padding: 8px 24px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; transition: all 0.2s; }
.settings-done-btn:hover { background: #c0392b; }
</style>
