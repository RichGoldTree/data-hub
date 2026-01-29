from flask import Flask, render_template_string
import pandas as pd
import os

app = Flask(__name__)

# =========================
# Data Hub에 등록된 데이터셋 목록 (메타데이터)
# =========================
DATASETS = {
    "weather": {
        "name": "Weather Dataset",
        "description": "Curated daily weather observations",
        "file": "weather_data_curated.csv"
    }
}

# =========================
# 데이터셋 목록 페이지
# =========================
@app.route("/")
def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Data Hub</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            h1 { color: #333; }
            ul { line-height: 1.8; }
            a { text-decoration: none; color: #0066cc; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>📊 Data Hub</h1>
        <p>Available Datasets</p>
        <ul>
            {% for key, ds in datasets.items() %}
                <li>
                    <a href="/dataset/{{ key }}">
                        <strong>{{ ds.name }}</strong>
                    </a>
                    - {{ ds.description }}
                </li>
            {% endfor %}
        </ul>
    </body>
    </html>
    """

    return render_template_string(
        html,
        datasets=DATASETS
    )

# =========================
# 데이터셋 상세 페이지
# =========================
@app.route("/dataset/<dataset_id>")
def dataset_detail(dataset_id):
    if dataset_id not in DATASETS:
        return "Dataset not found", 404

    dataset = DATASETS[dataset_id]

    # 🔹 현재 파일(app.py) 기준 절대 경로
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = os.path.join(BASE_DIR, "data", dataset["file"])

    # 🔹 데이터 로딩
    df = pd.read_csv(DATA_PATH)

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ dataset.name }}</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            th { background-color: #f2f2f2; }
            a { text-decoration: none; color: #0066cc; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>{{ dataset.name }}</h1>
        <p>{{ dataset.description }}</p>
        <a href="/">← Back to dataset list</a>
        <hr>
        {{ table | safe }}
    </body>
    </html>
    """

    return render_template_string(
        html,
        dataset=dataset,
        table=df.to_html(index=False)
    )

# =========================
# 앱 실행
# =========================
if __name__ == "__main__":
    app.run(debug=True)
