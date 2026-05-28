import os
import sys
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_loader import (
    get_question_index,
    refresh_index,
    get_random_question,
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
    total_pages = sum(q["problem_pages"] for q in questions)
    completed = len(checklist)
    return jsonify({
        "questions": questions,
        "total_pages": total_pages,
        "completed": completed,
        "checklist": checklist,
    })


@app.route("/api/refresh")
def api_refresh():
    questions = refresh_index()
    return jsonify({"status": "ok", "questions": questions})


@app.route("/api/random")
def api_random():
    completed = set(load_checklist().keys())
    q = get_random_question(completed)
    if q is None:
        return jsonify({"error": "not found"}), 404
    qid = f"{q['year']}_{q['page']}"
    checklist = load_checklist()
    done = qid in checklist
    return jsonify({
        "year": q["year"],
        "page": q["page"],
        "problem_file": q["problem_file"],
        "answer_files": q["answer_files"],
        "qid": qid,
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
    questions = get_question_index()
    total_pages = sum(q["problem_pages"] for q in questions)
    return jsonify({
        "checklist": cl,
        "completed": len(cl),
        "total": total_pages,
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
