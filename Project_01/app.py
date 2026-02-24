from __future__ import annotations

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
