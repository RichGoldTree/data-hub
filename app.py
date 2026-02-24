from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import os
import json
import uuid

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
META_FILE = os.path.join(BASE_DIR, "datasets.json")

os.makedirs(DATA_DIR, exist_ok=True)

# =========================
# CSV 안전 로딩
# =========================
def read_csv_safe(path):
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949")

# =========================
# 메타데이터
# =========================
def load_datasets():
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_datasets(data):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

DATASETS = load_datasets()

# =========================
# 홈 (검색 추가)
# =========================
@app.route("/")
def home():
    query = request.args.get("q", "").lower()

    if query:
        filtered = {
            k: v for k, v in DATASETS.items()
            if query in v["name"].lower()
        }
    else:
        filtered = DATASETS

    return render_template("home.html", datasets=filtered, query=query)

# =========================
# 상세 페이지 (요약 추가)
# =========================
@app.route("/dataset/<dataset_id>")
def dataset_detail(dataset_id):
    if dataset_id not in DATASETS:
        return "Dataset not found", 404

    dataset = DATASETS[dataset_id]
    path = os.path.join(DATA_DIR, dataset["file"])
    df = read_csv_safe(path)

    summary = {
        "rows": len(df),
        "columns": len(df.columns),
        "column_list": list(df.columns)
    }

    numeric_summary = df.describe().to_html()

    preview = df.head(50).to_html(index=False)

    return render_template(
        "dataset_detail.html",
        dataset=dataset,
        summary=summary,
        preview=preview,
        numeric_summary=numeric_summary
    )

# =========================
# 업로드
# =========================
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        name = request.form.get("name")
        provider = request.form.get("provider")
        license_ = request.form.get("license")

        if not file or not file.filename.endswith(".csv"):
            return "Only CSV allowed", 400

        dataset_id = str(uuid.uuid4())
        filename = dataset_id + ".csv"
        save_path = os.path.join(DATA_DIR, filename)
        file.save(save_path)

        df = read_csv_safe(save_path)

        DATASETS[dataset_id] = {
            "name": name,
            "provider": provider,
            "license": license_,
            "file": filename,
            "rows": len(df),
            "columns": len(df.columns)
        }

        save_datasets(DATASETS)
        return redirect(url_for("home"))

    return render_template("upload.html")

# =========================
# 삭제
# =========================
@app.route("/delete/<dataset_id>", methods=["POST"])
def delete(dataset_id):
    if dataset_id not in DATASETS:
        return "Not found", 404

    path = os.path.join(DATA_DIR, DATASETS[dataset_id]["file"])
    if os.path.exists(path):
        os.remove(path)

    del DATASETS[dataset_id]
    save_datasets(DATASETS)

    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)