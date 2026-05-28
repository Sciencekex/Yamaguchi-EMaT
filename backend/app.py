import os
import sys
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_loader import (
    get_question_index,
    refresh_index,
    get_random_question_item,
    load_question_map,
    load_classification,
    render_page_as_image,
    load_checklist,
    toggle_checklist,
    get_answer_file_index_for_page,
)

app = Flask(__name__, static_folder="../frontend/dist", static_url_path="")
CORS(app)


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/index")
def api_index():
    questions = get_question_index()
    checklist = load_checklist()
    qmap = load_question_map()
    classification = load_classification()

    total_pages = sum(q["problem_pages"] for q in questions)
    completed = len(checklist)
    total_questions = len(qmap)

    section_counts = {}
    for q in qmap:
        s = q.get("section", "")
        if s:
            section_counts[s] = section_counts.get(s, 0) + 1

    return jsonify({
        "total_pages": total_pages,
        "total_questions": total_questions,
        "completed": completed,
        "checklist": checklist,
        "section_counts": section_counts,
    })


@app.route("/api/refresh")
def api_refresh():
    refresh_index()
    return jsonify({"status": "ok"})


@app.route("/api/random")
def api_random():
    completed = set(load_checklist().keys())
    section_filter = request.args.get("section")
    exclude_sections = request.args.get("exclude_sections", "").split(",") if request.args.get("exclude_sections") else None
    exclude_years = request.args.get("exclude_years", "").split(",") if request.args.get("exclude_years") else None
    item = get_random_question_item(completed, section_filter, exclude_sections, exclude_years)
    if item is None:
        return jsonify({"error": "not found"}), 404

    qid = item["id"]
    done = qid in load_checklist()

    return jsonify({
        "id": item["id"],
        "year": item["year"],
        "section": item.get("section"),
        "qnum": item.get("qnum", 0),
        "pages": item["pages"],
        "page_start": item["page_start"],
        "page_end": item["page_end"],
        "done": done,
    })


@app.route("/api/pdf/<int:year>/<ftype>/<int:page>")
def api_pdf_page(year, ftype, page):
    img_bytes = render_page_as_image(year, ftype, page)
    if img_bytes is None:
        return jsonify({"error": "page not found"}), 404
    return send_file(io.BytesIO(img_bytes), mimetype="image/png")


@app.route("/api/checklist")
def api_checklist():
    cl = load_checklist()
    qmap = load_question_map()
    return jsonify({
        "checklist": cl,
        "completed": len(cl),
        "total": len(qmap),
    })


@app.route("/api/checklist/toggle", methods=["POST"])
def api_toggle_checklist():
    data = request.get_json(silent=True) or {}
    qid = data.get("qid")
    if not qid:
        return jsonify({"error": "qid required"}), 400
    result = toggle_checklist(qid)
    cl = load_checklist()
    return jsonify({
        "status": "ok",
        "checked": result,
        "qid": qid,
        "completed": len(cl),
    })


@app.route("/api/answer_index/<int:year>/<int:page>")
def api_answer_index(year, page):
    idx = get_answer_file_index_for_page(year, page)
    return jsonify({"answer_file_index": idx})


if __name__ == "__main__":
    refresh_index()
    app.run(port=5000, debug=False)
