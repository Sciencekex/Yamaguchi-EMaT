import fitz
import os
import json
import re
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "QuestionData")
OUTPUT_FILE = os.path.join(BASE_DIR, "classification.json")

SECTION_KEYWORDS = ["微分積分", "線形代数", "常微分方程式", "確率・統計"]

CONTENT_KW = {
    "微分積分": ["lim", "極限", "積分", "微分", "導関数", "偏微分", "重積分", "勾配",
                "テイラー", "マクローリン", "sin", "cos", "tan", "arctan",
                "曲線", "曲面", "接線", "法線", "級数", "収束", "grad", "rot", "div",
                "面積", "体積", "線積分", "面積分", "∇", "∂", "連続"],
    "線形代数": ["行列", "固有値", "固有ベクトル", "一次独立", "一次従属", "基底", "次元",
                "正則", "逆行列", "行列式", "対角化", "det", "直交", "正規直交",
                "Gram", "Schmidt", "転置行列", "対称行列", "交代行列",
                "ker", "像", "核", "ランク", "単位行列"],
    "常微分方程式": ["微分方程式", "一般解", "特殊解", "初期条件", "初期値問題",
                   "ラプラス変換", "特性方程式", "定数係数", "線形微分",
                   "ロンスキアン", "Wronskian", "変数分離", "斉次", "同次",
                   "非同次", "基本解", "平衡点", "安定性"],
    "確率・統計": ["確率", "期待値", "分散", "標準偏差", "正規分布", "統計", "標本", "推定",
                  "検定", "確率密度", "分布", "二項分布", "条件付き確率",
                  "ベイズ", "Bayes", "母平均", "母分散", "カイ二乗", "t分布",
                  "F分布", "有意", "信頼区間", "回帰", "相関", "共分散", "確率変数",
                  "仮説", "有意水準", "Poisson", "ポアソン"],
}


def parse_toc_from_lines(lines):
    section_starts = {}
    section_ends = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        matched_sec = None
        for kw in SECTION_KEYWORDS:
            if kw in line:
                matched_sec = kw
                break

        if matched_sec:
            start_page = None
            end_page = None

            for j in range(i + 1, min(i + 4, len(lines))):
                candidate = lines[j].strip()
                range_match = re.match(r"(\d+)\s*[～~]\s*(\d+)", candidate)
                if range_match:
                    start_page = int(range_match.group(1))
                    end_page = int(range_match.group(2))
                    break
                single_match = re.match(r"(\d+)", candidate)
                if single_match:
                    val = int(single_match.group(1))
                    if 1 <= val <= 200:
                        start_page = val
                        break

            if start_page is not None:
                section_starts[matched_sec] = start_page
                if end_page is not None:
                    section_ends[matched_sec] = end_page

        i += 1

    if len(section_starts) < 2:
        return None, None

    if len(section_ends) == len(section_starts):
        return section_starts, section_ends

    sorted_secs = sorted(section_starts.items(), key=lambda x: x[1])
    for idx in range(len(sorted_secs) - 1):
        section_ends[sorted_secs[idx][0]] = sorted_secs[idx + 1][1] - 1

    return section_starts, section_ends


def classify_via_toc(pdf_path):
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count

    toc_page_idx = -1
    for pi in range(min(5, total_pages)):
        text = doc[pi].get_text("text")
        if "目次" in text:
            toc_page_idx = pi
            break

    if toc_page_idx < 0:
        doc.close()
        return None

    toc_text = doc[toc_page_idx].get_text("text")
    lines = toc_text.split('\n')
    section_starts, section_ends = parse_toc_from_lines(lines)
    doc.close()

    if section_starts is None or section_ends is None:
        return None

    for sec in section_starts:
        if sec not in section_ends or section_ends[sec] is None:
            section_ends[sec] = total_pages - 1

    page_map = {}
    for page_idx in range(total_pages):
        if page_idx <= toc_page_idx:
            continue
        for sec in SECTION_KEYWORDS:
            if sec in section_starts and sec in section_ends:
                s = section_starts[sec]
                e = section_ends.get(sec, total_pages - 1)
                if s <= page_idx <= e:
                    page_map[page_idx] = sec
                    break

    sections_info = []
    for sec in SECTION_KEYWORDS:
        if sec in section_starts:
            sections_info.append({
                "name": sec,
                "start": section_starts[sec],
                "end": section_ends.get(sec, total_pages - 1),
            })

    return {
        "method": "toc",
        "toc_page": toc_page_idx,
        "sections": sections_info,
        "page_map": page_map,
    }


def classify_via_keywords(pdf_path):
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count

    skip_keywords = ["受験上の注意", "解答上の注意", "目次", "空白", "計算用紙"]

    page_map = {}
    for page_idx in range(total_pages):
        text = doc[page_idx].get_text("text")
        if len(text.strip()) < 30:
            continue
        if any(kw in text for kw in skip_keywords):
            continue

        scores = {}
        for cat, kws in CONTENT_KW.items():
            scores[cat] = sum(1 for kw in kws if kw in text)

        best_score = max(scores.values())
        if best_score == 0:
            continue

        best_cats = [cat for cat, s in scores.items() if s == best_score]
        page_map[page_idx] = best_cats[0]

    doc.close()

    if len(page_map) < 5:
        return None

    sections = {}
    for pi, cat in page_map.items():
        if cat not in sections:
            sections[cat] = []
        sections[cat].append(pi)

    sections_info = []
    for cat in SECTION_KEYWORDS:
        if cat in sections:
            sections_info.append({
                "name": cat,
                "start": min(sections[cat]),
                "end": max(sections[cat]),
            })

    return {
        "method": "keyword",
        "toc_page": -1,
        "sections": sections_info,
        "page_map": page_map,
    }


def main():
    all_results = {}

    for year_dir in sorted(os.listdir(DATA_DIR)):
        year_path = os.path.join(DATA_DIR, year_dir)
        if not os.path.isdir(year_path):
            continue
        try:
            year = int(year_dir)
        except ValueError:
            continue

        for fname in os.listdir(year_path):
            if fname.startswith("problem") and fname.endswith(".pdf"):
                pdf_path = os.path.join(year_path, fname)

                result = classify_via_toc(pdf_path)
                if result is None:
                    result = classify_via_keywords(pdf_path)

                if result:
                    all_results[str(year)] = result
                    total = len(result["page_map"])
                    counts = {}
                    for name in result["page_map"].values():
                        counts[name] = counts.get(name, 0) + 1
                    print(f"  {year}: {result['method']:>7} | {total:>2} pages | {counts}")
                else:
                    print(f"  {year}: FAILED")
                break

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    total_classified = sum(len(v["page_map"]) for v in all_results.values())
    print(f"\nclassified: {len(all_results)}/23 years, {total_classified} pages")

    global_counts = {}
    for v in all_results.values():
        for name in v["page_map"].values():
            global_counts[name] = global_counts.get(name, 0) + 1
    for kw in SECTION_KEYWORDS:
        print(f"  {kw}: {global_counts.get(kw, 0)}")


if __name__ == "__main__":
    main()
