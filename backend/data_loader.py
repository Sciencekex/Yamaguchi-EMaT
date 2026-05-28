import os
import json
import random
import fitz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTION_DATA_DIR = os.path.join(BASE_DIR, "..", "QuestionData")
CHECKLIST_FILE = os.path.join(BASE_DIR, "checklist.json")
INDEX_CACHE_FILE = os.path.join(BASE_DIR, "index_cache.json")


def scan_pdfs():
    questions = []

    for year_dir in sorted(os.listdir(QUESTION_DATA_DIR)):
        year_path = os.path.join(QUESTION_DATA_DIR, year_dir)
        if not os.path.isdir(year_path):
            continue

        try:
            year = int(year_dir)
        except ValueError:
            continue

        problem_file = None
        answer_files = []

        for fname in sorted(os.listdir(year_path)):
            if not fname.endswith(".pdf"):
                continue
            if fname.startswith("problem"):
                problem_file = fname
            elif fname.startswith("kaito"):
                answer_files.append(fname)

        if problem_file is None:
            continue

        problem_path = os.path.join(year_path, problem_file)
        try:
            doc = fitz.open(problem_path)
            problem_pages = doc.page_count
            doc.close()
        except Exception:
            continue

        answer_pages_info = []
        for af in answer_files:
            apath = os.path.join(year_path, af)
            try:
                doc = fitz.open(apath)
                answer_pages_info.append({
                    "file": af,
                    "pages": doc.page_count
                })
                doc.close()
            except Exception:
                continue

        questions.append({
            "year": year,
            "problem_file": problem_file,
            "problem_pages": problem_pages,
            "answer_files": answer_pages_info
        })

    return questions


def get_question_index():
    if os.path.exists(INDEX_CACHE_FILE):
        try:
            with open(INDEX_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    questions = scan_pdfs()
    with open(INDEX_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    return questions


def refresh_index():
    questions = scan_pdfs()
    with open(INDEX_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    return questions


def get_random_question(completed_set=None):
    questions = get_question_index()
    if not questions:
        return None

    question_pool = []
    for q in questions:
        for page in range(q["problem_pages"]):
            qid = f"{q['year']}_{page}"
            if completed_set and qid in completed_set:
                continue
            question_pool.append((q["year"], page, q["problem_file"], q["answer_files"]))

    if not question_pool:
        for q in questions:
            for page in range(q["problem_pages"]):
                question_pool.append((q["year"], page, q["problem_file"], q["answer_files"]))

    year, page, pf, af = random.choice(question_pool)
    return {"year": year, "page": page, "problem_file": pf, "answer_files": af}


def render_page_as_image(year, file_type, page_num, zoom=2.0):
    year_dir = os.path.join(QUESTION_DATA_DIR, str(year))
    if not os.path.isdir(year_dir):
        return None

    target_file = None
    if file_type == "problem":
        for f in os.listdir(year_dir):
            if f.startswith("problem") and f.endswith(".pdf"):
                target_file = f
                break
    elif file_type.startswith("answer"):
        idx = file_type.replace("answer", "")
        kaito_files = sorted([f for f in os.listdir(year_dir)
                              if f.startswith("kaito") and f.endswith(".pdf")])
        if idx:
            i = int(idx)
            if 0 <= i < len(kaito_files):
                target_file = kaito_files[i]
        else:
            if kaito_files:
                target_file = kaito_files[0]
    else:
        return None

    if target_file is None:
        return None

    pdf_path = os.path.join(year_dir, target_file)
    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= doc.page_count:
            doc.close()
            return None
        mat = fitz.Matrix(zoom, zoom)
        pix = doc[page_num].get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes
    except Exception:
        return None


def load_checklist():
    if os.path.exists(CHECKLIST_FILE):
        try:
            with open(CHECKLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_checklist(data):
    with open(CHECKLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def toggle_checklist(qid):
    cl = load_checklist()
    if qid in cl:
        del cl[qid]
        result = False
    else:
        cl[qid] = True
        result = True
    save_checklist(cl)
    return result


def get_answer_file_index_for_page(year, page_num):
    questions = get_question_index()
    for q in questions:
        if q["year"] == year:
            afs = q.get("answer_files", [])
            if len(afs) <= 1:
                return 0
            accumulated = 0
            for idx, af in enumerate(afs):
                if page_num < accumulated + af["pages"]:
                    return idx
                accumulated += af["pages"]
            return len(afs) - 1
    return 0
