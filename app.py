from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import os
import json

app = Flask(__name__)

# =========================
# 기본 경로 설정
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
META_FILE = os.path.join(BASE_DIR, "datasets.json")

os.makedirs(DATA_DIR, exist_ok=True)

# =========================
# CSV 안전 로딩 함수
# =========================
def read_csv_safe(path):
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949")

# =========================
# 메타데이터 로드/저장
# =========================
def load_datasets():
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_datasets(datasets):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(datasets, f, ensure_ascii=False, indent=2)

# =========================
# 서버 시작 시 메타데이터 로드
# =========================
DATASETS = load_datasets()

# =========================
# 데이터셋 목록 페이지
# =========================
@app.route("/")
def home():
    html = """
    <h1>📊 Data Hub</h1>
    <p>Available Datasets</p>

    <a href="/upload">➕ Upload New Dataset</a>
    <ul>
        {% for key, ds in datasets.items() %}
            <li>
                <strong>{{ ds.name }}</strong>
                <small>
                    ({{ ds.provider }} | {{ ds.license }})
                </small>

                <!-- ❌ 삭제 버튼 -->
                <form method="post" action="/delete/{{ key }}" style="display:inline;">
                    <button type="submit" style="color:red;">❌ Delete</button>
                </form>

                <br>
                <a href="/dataset/{{ key }}">View dataset</a>
            </li>
        {% endfor %}
    </ul>
    """
    return render_template_string(html, datasets=DATASETS)

# =========================
# 데이터셋 상세 페이지
# =========================
@app.route("/dataset/<dataset_id>")
def dataset_detail(dataset_id):
    if dataset_id not in DATASETS:
        return "Dataset not found", 404

    dataset = DATASETS[dataset_id]
    data_path = os.path.join(DATA_DIR, dataset["file"])

    df = read_csv_safe(data_path)

    html = """
    <h1>{{ dataset.name }}</h1>

    <p><strong>Provider:</strong> {{ dataset.provider }}</p>
    <p><strong>License:</strong> {{ dataset.license }}</p>

    <a href="/">← Back</a>
    <hr>
    {{ table | safe }}
    """

    return render_template_string(
        html,
        dataset=dataset,
        table=df.to_html(index=False)
    )

# =========================
# CSV 업로드
# =========================
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        name = request.form.get("name")
        provider = request.form.get("provider")
        license_ = request.form.get("license")

        if not file or not file.filename.endswith(".csv"):
            return "Only CSV files are allowed", 400

        dataset_id = os.path.splitext(file.filename)[0]
        save_path = os.path.join(DATA_DIR, file.filename)
        file.save(save_path)

        read_csv_safe(save_path)

        DATASETS[dataset_id] = {
            "name": name,
            "description": "Uploaded dataset",
            "provider": provider,
            "source": "User upload",
            "license": license_,
            "file": file.filename
        }

        save_datasets(DATASETS)
        return redirect(url_for("home"))

    html = """
    <h1>➕ Upload New Dataset</h1>
    <form method="post" enctype="multipart/form-data">
        <p>Dataset Name:<br><input name="name" required></p>
        <p>Provider:<br><input name="provider" required></p>
        <p>License:<br><input name="license" required></p>
        <p>CSV File:<br><input type="file" name="file" required></p>
        <button type="submit">Upload</button>
    </form>
    <a href="/">← Back</a>
    """
    return render_template_string(html)

# =========================
# ❌ 데이터셋 삭제
# =========================
@app.route("/delete/<dataset_id>", methods=["POST"])
def delete_dataset(dataset_id):
    if dataset_id not in DATASETS:
        return "Dataset not found", 404

    dataset = DATASETS[dataset_id]

    # CSV 파일 삭제
    file_path = os.path.join(DATA_DIR, dataset["file"])
    if os.path.exists(file_path):
        os.remove(file_path)

    # 메타데이터 삭제
    del DATASETS[dataset_id]
    save_datasets(DATASETS)

    return redirect(url_for("home"))

# =========================
# 앱 실행
# =========================
if __name__ == "__main__":
    app.run(debug=True)
