import os
from pathlib import Path

# =========================
# 생성할 프로젝트 경로 (요청하신 경로)
# =========================
TARGET_DIR = Path(r"C:\Users\USER\data-hub\Project_01")

# =========================
# 파일 내용들
# =========================
APP_PY = r'''from __future__ import annotations

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_from_directory, abort
)
from werkzeug.utils import secure_filename
import pandas as pd
import os
import json
import uuid
from datetime import datetime

# =========================
# App Config
# =========================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
META_FILE = os.path.join(BASE_DIR, "datasets.json")
MAX_UPLOAD_MB = 30

os.makedirs(DATA_DIR, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024  # upload size limit


# =========================
# Helpers
# =========================
def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def read_csv_safe(path: str) -> pd.DataFrame:
    # try utf-8 then cp949 (common in KR)
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949")


def load_datasets() -> dict:
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_datasets(datasets: dict) -> None:
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(datasets, f, ensure_ascii=False, indent=2)


def build_profile(df: pd.DataFrame) -> dict:
    dtypes = {c: str(df[c].dtype) for c in df.columns}
    nulls = {c: int(df[c].isna().sum()) for c in df.columns}

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    numeric_summary = None
    if numeric_cols:
        desc = df[numeric_cols].describe().T
        keep = [c for c in ["count", "mean", "std", "min", "25%", "50%", "75%", "max"] if c in desc.columns]
        numeric_summary = desc[keep].round(6)

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_list": list(df.columns),
        "dtypes": dtypes,
        "nulls": nulls,
        "numeric_cols": numeric_cols,
        "has_numeric": bool(numeric_cols),
        "numeric_summary_html": numeric_summary.to_html(classes="table table-sm table-striped", border=0)
        if numeric_summary is not None else None,
    }


def allowed_csv(filename: str) -> bool:
    return filename.lower().endswith(".csv")


DATASETS = load_datasets()


# =========================
# Error Pages
# =========================
@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_):
    return render_template("500.html"), 500


# =========================
# Home: list/search/sort
# =========================
@app.route("/")
def home():
    q = (request.args.get("q") or "").strip().lower()
    sort = (request.args.get("sort") or "new").strip()        # new | name | rows
    direction = (request.args.get("dir") or "desc").strip()   # asc | desc

    items = []
    for ds_id, ds in DATASETS.items():
        item = {"id": ds_id, **ds}
        items.append(item)

    if q:
        items = [
            it for it in items
            if q in (it.get("name", "").lower())
            or q in (it.get("provider", "").lower())
            or q in (it.get("license", "").lower())
        ]

    reverse = (direction == "desc")

    def safe_int(x, default=0):
        try:
            return int(x)
        except Exception:
            return default

    if sort == "name":
        items.sort(key=lambda x: (x.get("name") or "").lower(), reverse=reverse)
    elif sort == "rows":
        items.sort(key=lambda x: safe_int(x.get("rows", 0)), reverse=reverse)
    else:  # new
        items.sort(key=lambda x: (x.get("created_at") or ""), reverse=True)

    return render_template("home.html", datasets=items, q=q, sort=sort, direction=direction)


# =========================
# Dataset detail: preview/profile/download
# =========================
@app.route("/dataset/<dataset_id>")
def dataset_detail(dataset_id: str):
    ds = DATASETS.get(dataset_id)
    if not ds:
        abort(404)

    path = os.path.join(DATA_DIR, ds["file"])
    if not os.path.exists(path):
        flash("CSV 파일이 서버에 존재하지 않습니다. 메타데이터를 확인하세요.", "danger")
        return redirect(url_for("home"))

    df = read_csv_safe(path)

    try:
        limit = int(request.args.get("limit", "50"))
    except Exception:
        limit = 50
    limit = max(10, min(limit, 500))

    profile = ds.get("profile")
    if not profile or profile.get("rows") != len(df) or profile.get("columns") != len(df.columns):
        profile = build_profile(df)
        ds["profile"] = profile
        ds["rows"] = profile["rows"]
        ds["columns"] = profile["columns"]
        ds["updated_at"] = now_iso()
        DATASETS[dataset_id] = ds
        save_datasets(DATASETS)

    preview_df = df.head(limit)
    preview_html = preview_df.to_html(
        index=False,
        classes="table table-hover table-sm align-middle",
        border=0
    )

    schema_rows = []
    for c in df.columns:
        schema_rows.append({
            "name": c,
            "dtype": profile["dtypes"].get(c, ""),
            "nulls": profile["nulls"].get(c, 0),
        })

    return render_template(
        "dataset_detail.html",
        dataset=ds,
        dataset_id=dataset_id,
        preview_html=preview_html,
        schema_rows=schema_rows,
        limit=limit
    )


@app.route("/download/<dataset_id>")
def download(dataset_id: str):
    ds = DATASETS.get(dataset_id)
    if not ds:
        abort(404)
    filename = ds["file"]
    return send_from_directory(DATA_DIR, filename, as_attachment=True, download_name=secure_filename(filename))


# =========================
# Upload
# =========================
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        name = (request.form.get("name") or "").strip()
        provider = (request.form.get("provider") or "").strip()
        license_ = (request.form.get("license") or "").strip()
        description = (request.form.get("description") or "").strip()

        if not name or not provider or not license_:
            flash("필수 입력값(이름/제공자/라이선스)을 확인해주세요.", "warning")
            return redirect(url_for("upload"))

        if not file or not file.filename:
            flash("CSV 파일을 선택해주세요.", "warning")
            return redirect(url_for("upload"))

        if not allowed_csv(file.filename):
            flash("CSV 파일만 업로드할 수 있습니다.", "danger")
            return redirect(url_for("upload"))

        dataset_id = str(uuid.uuid4())
        orig = secure_filename(file.filename)
        saved_name = f"{dataset_id}.csv"
        save_path = os.path.join(DATA_DIR, saved_name)

        try:
            file.save(save_path)
            df = read_csv_safe(save_path)
        except Exception as e:
            if os.path.exists(save_path):
                os.remove(save_path)
            flash(f"업로드/파싱 실패: {e}", "danger")
            return redirect(url_for("upload"))

        profile = build_profile(df)
        DATASETS[dataset_id] = {
            "name": name,
            "provider": provider,
            "license": license_,
            "description": description or "Uploaded dataset",
            "source_filename": orig,
            "file": saved_name,
            "rows": profile["rows"],
            "columns": profile["columns"],
            "profile": profile,
            "created_at": now_iso(),
            "updated_at": now_iso()
        }
        save_datasets(DATASETS)

        flash("업로드 완료! 데이터셋이 추가되었습니다.", "success")
        return redirect(url_for("dataset_detail", dataset_id=dataset_id))

    return render_template("upload.html", max_mb=MAX_UPLOAD_MB)


# =========================
# Delete (POST)
# =========================
@app.route("/delete/<dataset_id>", methods=["POST"])
def delete(dataset_id: str):
    ds = DATASETS.get(dataset_id)
    if not ds:
        abort(404)

    path = os.path.join(DATA_DIR, ds["file"])
    if os.path.exists(path):
        os.remove(path)

    del DATASETS[dataset_id]
    save_datasets(DATASETS)

    flash("데이터셋이 삭제되었습니다.", "info")
    return redirect(url_for("home"))


# =========================
# Run
# =========================
if __name__ == "__main__":
    app.run(debug=True)
'''

BASE_HTML = r'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title or "Data Hub" }}</title>

  <!-- Bootstrap 5 (CDN) -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}">
</head>
<body class="bg-body-tertiary">

<nav class="navbar navbar-expand-lg navbar-dark bg-dark sticky-top shadow-sm">
  <div class="container">
    <a class="navbar-brand fw-semibold" href="{{ url_for('home') }}">Data Hub</a>

    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#nav">
      <span class="navbar-toggler-icon"></span>
    </button>

    <div class="collapse navbar-collapse" id="nav">
      <ul class="navbar-nav me-auto">
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('home') }}">홈</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('upload') }}">파일 추가</a>
        </li>
      </ul>

      <form class="d-flex" method="get" action="{{ url_for('home') }}">
        <input class="form-control form-control-sm me-2" name="q" placeholder="검색 (이름/제공자/라이선스)" value="{{ request.args.get('q','') }}">
        <button class="btn btn-sm btn-outline-light" type="submit">검색</button>
      </form>
    </div>
  </div>
</nav>

<main class="container my-4">
  {% with messages = get_flashed_messages(with_categories=True) %}
    {% if messages %}
      {% for category, msg in messages %}
        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
          {{ msg }}
          <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  {% block content %}{% endblock %}
</main>

<footer class="border-top bg-white">
  <div class="container py-3 d-flex justify-content-between small text-muted">
    <div>© Data Hub</div>
    <div>Flask · Bootstrap</div>
  </div>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script src="{{ url_for('static', filename='app.js') }}"></script>
</body>
</html>
'''

HOME_HTML = r'''{% extends "base.html" %}
{% set title = "Data Hub · Home" %}
{% block content %}

<div class="d-flex align-items-center justify-content-between mb-3">
  <div>
    <h1 class="h3 mb-1">데이터셋</h1>
    <div class="text-muted small">업로드된 CSV를 탐색하고 다운로드할 수 있습니다.</div>
  </div>
  <a class="btn btn-primary" href="{{ url_for('upload') }}">➕ 파일 추가</a>
</div>

<div class="card shadow-sm mb-3">
  <div class="card-body">
    <form class="row g-2 align-items-end" method="get">
      <div class="col-12 col-md-6">
        <label class="form-label small text-muted">검색</label>
        <input class="form-control" name="q" value="{{ q }}" placeholder="이름/제공자/라이선스">
      </div>

      <div class="col-6 col-md-3">
        <label class="form-label small text-muted">정렬</label>
        <select class="form-select" name="sort">
          <option value="new"  {{ "selected" if sort=="new" else "" }}>최신</option>
          <option value="name" {{ "selected" if sort=="name" else "" }}>이름</option>
          <option value="rows" {{ "selected" if sort=="rows" else "" }}>행 수</option>
        </select>
      </div>

      <div class="col-6 col-md-2">
        <label class="form-label small text-muted">방향</label>
        <select class="form-select" name="dir">
          <option value="desc" {{ "selected" if direction=="desc" else "" }}>내림차순</option>
          <option value="asc"  {{ "selected" if direction=="asc" else "" }}>오름차순</option>
        </select>
      </div>

      <div class="col-12 col-md-1 d-grid">
        <button class="btn btn-outline-secondary" type="submit">적용</button>
      </div>
    </form>
  </div>
</div>

{% if datasets|length == 0 %}
  <div class="text-center p-5 bg-white border rounded-3">
    <div class="display-6 mb-2">📭</div>
    <div class="fw-semibold">데이터셋이 없습니다.</div>
    <div class="text-muted">오른쪽 상단 “파일 추가”로 CSV를 업로드하세요.</div>
  </div>
{% else %}
  <div class="row g-3">
    {% for ds in datasets %}
      <div class="col-12 col-lg-6">
        <div class="card shadow-sm h-100">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start">
              <div>
                <div class="fw-semibold fs-5 mb-1">{{ ds.name }}</div>
                <div class="text-muted small">{{ ds.description or "" }}</div>
              </div>
              <span class="badge text-bg-secondary">{{ ds.rows }} rows · {{ ds.columns }} cols</span>
            </div>

            <hr>

            <div class="small text-muted">
              <div><span class="fw-semibold">Provider:</span> {{ ds.provider }}</div>
              <div><span class="fw-semibold">License:</span> {{ ds.license }}</div>
              <div class="mt-1"><span class="fw-semibold">Created:</span> {{ ds.created_at or "-" }}</div>
            </div>
          </div>

          <div class="card-footer bg-white border-0 pt-0">
            <div class="d-flex gap-2">
              <a class="btn btn-sm btn-outline-primary" href="{{ url_for('dataset_detail', dataset_id=ds.id) }}">보기</a>
              <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('download', dataset_id=ds.id) }}">다운로드</a>

              <button class="btn btn-sm btn-outline-danger ms-auto"
                      data-bs-toggle="modal"
                      data-bs-target="#deleteModal"
                      data-dsid="{{ ds.id }}"
                      data-dsname="{{ ds.name }}">
                삭제
              </button>
            </div>
          </div>
        </div>
      </div>
    {% endfor %}
  </div>
{% endif %}

<div class="modal fade" id="deleteModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">삭제 확인</h5>
        <button class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="text-muted">다음 데이터셋을 삭제할까요?</div>
        <div class="fw-semibold mt-2" id="modalDsName">-</div>
        <div class="small text-danger mt-2">삭제하면 CSV 파일도 함께 삭제되며 복구할 수 없습니다.</div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline-secondary" data-bs-dismiss="modal">취소</button>
        <form id="deleteForm" method="post">
          <button class="btn btn-danger" type="submit">삭제</button>
        </form>
      </div>
    </div>
  </div>
</div>

{% endblock %}
'''

UPLOAD_HTML = r'''{% extends "base.html" %}
{% set title = "Data Hub · Upload" %}
{% block content %}

<div class="row justify-content-center">
  <div class="col-12 col-lg-8">
    <div class="card shadow-sm">
      <div class="card-body">
        <h1 class="h4 mb-1">파일 추가</h1>
        <div class="text-muted small mb-3">CSV 파일을 업로드하면 Data Hub에 등록됩니다. (최대 {{ max_mb }}MB)</div>

        <form method="post" enctype="multipart/form-data" class="row g-3">
          <div class="col-12">
            <label class="form-label">Dataset Name</label>
            <input class="form-control" name="name" required placeholder="예: Sales 2025 Q4">
          </div>

          <div class="col-12 col-md-6">
            <label class="form-label">Provider</label>
            <input class="form-control" name="provider" required placeholder="예: Internal / Kaggle / etc">
          </div>

          <div class="col-12 col-md-6">
            <label class="form-label">License</label>
            <input class="form-control" name="license" required placeholder="예: CC BY 4.0 / Proprietary">
          </div>

          <div class="col-12">
            <label class="form-label">Description (optional)</label>
            <textarea class="form-control" name="description" rows="2" placeholder="간단 설명"></textarea>
          </div>

          <div class="col-12">
            <label class="form-label">CSV File</label>
            <input class="form-control" type="file" name="file" accept=".csv" required>
            <div class="form-text">UTF-8 또는 CP949 인코딩을 지원합니다.</div>
          </div>

          <div class="col-12 d-grid">
            <button class="btn btn-primary" type="submit">업로드</button>
          </div>
        </form>
      </div>
    </div>

    <div class="text-muted small mt-3">
      팁: 컬럼이 많은 파일은 미리보기/통계 렌더링이 느릴 수 있어요. (미리보기는 최대 500행까지 제한)
    </div>
  </div>
</div>

{% endblock %}
'''

DETAIL_HTML = r'''{% extends "base.html" %}
{% set title = "Data Hub · Detail" %}
{% block content %}

<div class="d-flex align-items-start justify-content-between mb-3">
  <div>
    <h1 class="h3 mb-1">{{ dataset.name }}</h1>
    <div class="text-muted">{{ dataset.description }}</div>
    <div class="small text-muted mt-2">
      <span class="me-3"><span class="fw-semibold">Provider:</span> {{ dataset.provider }}</span>
      <span class="me-3"><span class="fw-semibold">License:</span> {{ dataset.license }}</span>
      <span><span class="fw-semibold">Updated:</span> {{ dataset.updated_at }}</span>
    </div>
  </div>

  <div class="d-flex gap-2">
    <a class="btn btn-outline-secondary" href="{{ url_for('download', dataset_id=dataset_id) }}">다운로드</a>

    <button class="btn btn-outline-danger"
            data-bs-toggle="modal"
            data-bs-target="#deleteModal"
            data-dsid="{{ dataset_id }}"
            data-dsname="{{ dataset.name }}">
      삭제
    </button>
  </div>
</div>

<div class="row g-3">
  <div class="col-12 col-lg-4">
    <div class="card shadow-sm">
      <div class="card-body">
        <div class="fw-semibold mb-2">요약</div>
        <div class="d-flex justify-content-between">
          <span class="text-muted">Rows</span>
          <span class="fw-semibold">{{ dataset.rows }}</span>
        </div>
        <div class="d-flex justify-content-between">
          <span class="text-muted">Columns</span>
          <span class="fw-semibold">{{ dataset.columns }}</span>
        </div>
        <hr>
        <div class="small text-muted">Source file</div>
        <div class="small fw-semibold">{{ dataset.source_filename }}</div>
      </div>
    </div>

    <div class="card shadow-sm mt-3">
      <div class="card-body">
        <div class="fw-semibold mb-2">스키마</div>
        <div class="table-responsive">
          <table class="table table-sm table-striped align-middle mb-0">
            <thead>
              <tr>
                <th>Column</th>
                <th>Type</th>
                <th class="text-end">Nulls</th>
              </tr>
            </thead>
            <tbody>
              {% for r in schema_rows %}
              <tr>
                <td class="text-truncate" style="max-width: 160px;">{{ r.name }}</td>
                <td class="text-muted">{{ r.dtype }}</td>
                <td class="text-end">{{ r.nulls }}</td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <div class="col-12 col-lg-8">
    <div class="card shadow-sm">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <div class="fw-semibold">미리보기</div>

          <form class="d-flex gap-2" method="get">
            <select class="form-select form-select-sm" name="limit" onchange="this.form.submit()">
              {% for n in [50,100,200,500] %}
                <option value="{{ n }}" {{ "selected" if limit==n else "" }}>{{ n }} rows</option>
              {% endfor %}
            </select>
          </form>
        </div>

        <div class="table-responsive">
          {{ preview_html | safe }}
        </div>
      </div>
    </div>

    {% if dataset.profile and dataset.profile.numeric_summary_html %}
    <div class="card shadow-sm mt-3">
      <div class="card-body">
        <div class="fw-semibold mb-2">숫자형 컬럼 통계</div>
        <div class="table-responsive">
          {{ dataset.profile.numeric_summary_html | safe }}
        </div>
      </div>
    </div>
    {% endif %}
  </div>
</div>

<div class="modal fade" id="deleteModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">삭제 확인</h5>
        <button class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="text-muted">다음 데이터셋을 삭제할까요?</div>
        <div class="fw-semibold mt-2" id="modalDsName">-</div>
        <div class="small text-danger mt-2">삭제하면 CSV 파일도 함께 삭제되며 복구할 수 없습니다.</div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline-secondary" data-bs-dismiss="modal">취소</button>
        <form id="deleteForm" method="post">
          <button class="btn btn-danger" type="submit">삭제</button>
        </form>
      </div>
    </div>
  </div>
</div>

{% endblock %}
'''

HTML_404 = r'''{% extends "base.html" %}
{% set title = "404 Not Found" %}
{% block content %}
<div class="text-center p-5 bg-white border rounded-3 shadow-sm">
  <div class="display-5">404</div>
  <div class="fw-semibold mt-2">페이지를 찾을 수 없습니다.</div>
  <div class="text-muted mt-2">주소가 잘못되었거나 삭제된 페이지입니다.</div>
  <a class="btn btn-primary mt-3" href="{{ url_for('home') }}">홈으로</a>
</div>
{% endblock %}
'''

HTML_500 = r'''{% extends "base.html" %}
{% set title = "500 Server Error" %}
{% block content %}
<div class="text-center p-5 bg-white border rounded-3 shadow-sm">
  <div class="display-5">500</div>
  <div class="fw-semibold mt-2">서버 오류가 발생했습니다.</div>
  <div class="text-muted mt-2">잠시 후 다시 시도해주세요.</div>
  <a class="btn btn-primary mt-3" href="{{ url_for('home') }}">홈으로</a>
</div>
{% endblock %}
'''

APP_JS = r'''(() => {
  const deleteModal = document.getElementById("deleteModal");
  if (!deleteModal) return;

  deleteModal.addEventListener("show.bs.modal", (event) => {
    const button = event.relatedTarget;
    if (!button) return;

    const dsid = button.getAttribute("data-dsid");
    const dsname = button.getAttribute("data-dsname");

    const nameEl = deleteModal.querySelector("#modalDsName");
    const formEl = deleteModal.querySelector("#deleteForm");

    if (nameEl) nameEl.textContent = dsname || "-";
    if (formEl) formEl.action = `/delete/${dsid}`;
  });
})();
'''

APP_CSS = r'''.table td, .table th { vertical-align: middle; }
.card { border: 1px solid rgba(0,0,0,.06); }
.text-truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
'''

REQUIREMENTS = r'''flask
pandas
werkzeug
'''

GITIGNORE = r'''__pycache__/
*.pyc
.venv/
venv/
.env
data/
datasets.json
'''

# =========================
# 생성 로직
# =========================
def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    # 폴더 생성
    (TARGET_DIR / "templates").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "static").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "data").mkdir(parents=True, exist_ok=True)

    # 파일 생성
    write_file(TARGET_DIR / "app.py", APP_PY)
    write_file(TARGET_DIR / "requirements.txt", REQUIREMENTS)
    write_file(TARGET_DIR / ".gitignore", GITIGNORE)

    write_file(TARGET_DIR / "templates" / "base.html", BASE_HTML)
    write_file(TARGET_DIR / "templates" / "home.html", HOME_HTML)
    write_file(TARGET_DIR / "templates" / "upload.html", UPLOAD_HTML)
    write_file(TARGET_DIR / "templates" / "dataset_detail.html", DETAIL_HTML)
    write_file(TARGET_DIR / "templates" / "404.html", HTML_404)
    write_file(TARGET_DIR / "templates" / "500.html", HTML_500)

    write_file(TARGET_DIR / "static" / "app.js", APP_JS)
    write_file(TARGET_DIR / "static" / "app.css", APP_CSS)

    # datasets.json은 없으면 비어있는 dict로 생성 (있으면 유지)
    meta = TARGET_DIR / "datasets.json"
    if not meta.exists():
        write_file(meta, "{}\n")

    print("✅ 프로젝트 생성 완료!")
    print(f"📁 위치: {TARGET_DIR}")
    print("\n다음 명령으로 실행하세요:")
    print(f"  cd /d \"{TARGET_DIR}\"")
    print("  python -m venv .venv")
    print("  .venv\\Scripts\\activate")
    print("  pip install -r requirements.txt")
    print("  python app.py")
    print("\n접속: http://127.0.0.1:5000")


if __name__ == "__main__":
    main()