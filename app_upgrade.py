from flask import Flask, render_template_string, request, redirect, Response
import pandas as pd
import os
import json

app = Flask(__name__)

# =========================
# 기본 경로
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
META_FILE = os.path.join(BASE_DIR, "datasets.json")
STANDARD_FILE = os.path.join(BASE_DIR, "example_table2.csv")

os.makedirs(DATA_DIR, exist_ok=True)

# =========================
# 항목 그룹 정의
# =========================
ITEM_GROUPS = {
    "중금속": [
        "Cd(mg/kg)", "Cu(mg/kg)", "As(mg/kg)", "Hg(mg/kg)",
        "Pb(mg/kg)", "Cr6+(mg/kg)", "Zn(mg/kg)", "Ni(mg/kg)"
    ],
    "유류": [
        "Benzene", "Toluene", "Ethylbenzene", "Xylene", "TPH"
    ],
    "유기용제": [
        "TCE", "PCE", "1,2DCA (1,2-디클로로에탄)"
    ],
    "기타": [
        "F(mg/kg)", "PCBs(mg/kg)", "CN(mg/kg)", "Phenol(mg/kg)",
        "Pentachlorophenol(mg/kg)", "Dioxin", "pH"
    ]
}

# =========================
# CSV 로딩
# =========================
def read_csv_safe(path):
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949")

def normalize_columns(df):
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace("\n", "", regex=False)
        .str.replace("\r", "", regex=False)
    )
    return df

# =========================
# 조사구분 / 지역
# =========================
def get_survey_column(df):
    for c in df.columns:
        if "조사구분" in c:
            return c
    return None

def normalize_survey_type(v):
    if pd.isna(v):
        return None
    v = str(v)
    if "개황" in v:
        return "A"
    if "정밀" in v or "상세" in v:
        return "B"
    return None

def normalize_region(v):
    if pd.isna(v):
        return None
    v = str(v)
    if "1" in v:
        return "1지역"
    if "2" in v:
        return "2지역"
    if "3" in v:
        return "3지역"
    return None

# =========================
# 숫자 정규화
# =========================
def normalize_numeric_series(s):
    cleaned = (
        s.astype(str)
         .str.replace("－", "", regex=False)
         .str.replace(r"[^0-9eE\.\+\-]", "", regex=True)
         .str.strip()
         .replace("", pd.NA)
    )
    return pd.to_numeric(cleaned, errors="coerce")

# =========================
# 기준 로딩
# =========================
def load_standards(path):
    df = normalize_columns(read_csv_safe(path))
    standards = {}
    for _, r in df.iterrows():
        region = str(r.iloc[0]).strip()
        criteria_raw = str(r.iloc[1]).strip()
        if not region or not criteria_raw:
            continue
        criteria = "우려40" if "40" in criteria_raw else "우려기준"
        standards.setdefault(region, {})
        standards[region].setdefault(criteria, {})
        for col in df.columns[2:]:
            standards[region][criteria][col] = r[col]
    return standards

STANDARDS = load_standards(STANDARD_FILE) if os.path.exists(STANDARD_FILE) else {}

# =========================
# 메타데이터
# =========================
def load_datasets():
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

DATASETS = load_datasets()

# =========================
# 분석 로직
# =========================
def get_site_series(df):
    if "시료명" in df.columns:
        return df["시료명"].astype(str)
    if "지점명" in df.columns:
        return df["지점명"].astype(str)
    return None

def is_exceed(row, item, region):
    v = row[item]
    if pd.isna(v):
        return False
    std = STANDARDS.get(region, {}).get("우려기준", {}).get(item)
    try:
        return v > float(std)
    except:
        return False

def analyze_dataset(df, items):
    site = get_site_series(df)
    out = []

    for item in items:
        r = {"항목": item}

        if item not in df.columns:
            for region in ["1지역", "2지역", "3지역"]:
                r[f"{region}_지점수"] = 0
                r[f"{region}_최고"] = None
                r[f"{region}_우려초과_지점수"] = 0
            out.append(r)
            continue

        for region in ["1지역", "2지역", "3지역"]:
            sub = df[df["_지역"] == region]
            r[f"{region}_지점수"] = site.loc[sub.index].nunique() if site is not None else len(sub)
            r[f"{region}_최고"] = None if sub[item].isna().all() else float(sub[item].max())
            ex = sub[sub.apply(lambda x: is_exceed(x, item, region), axis=1)]
            r[f"{region}_우려초과_지점수"] = site.loc[ex.index].nunique() if site is not None else len(ex)

        out.append(r)

    return pd.DataFrame(out).where(pd.notna, None)

# =========================
# 홈
# =========================
@app.route("/")
def home():
    return render_template_string("""
    <h1>📊 Data Hub</h1>
    <ul>
    {% for k, ds in datasets.items() %}
      <li>
        <b>{{ ds.name }}</b><br>
        <a href="/dataset/{{k}}">원본</a> |
        <a href="/dataset/{{k}}/analysis">분석</a> |
        <a href="/dataset/{{k}}/log">로그</a>
      </li>
    {% endfor %}
    </ul>
    """, datasets=DATASETS)

# =========================
# 원본
# =========================
@app.route("/dataset/<dataset_id>")
def dataset_detail(dataset_id):
    df = normalize_columns(read_csv_safe(os.path.join(DATA_DIR, DATASETS[dataset_id]["file"])))
    return render_template_string("""
    <a href="/">🏠 Data Hub 홈으로</a>
    <h2>원본 데이터</h2>
    {{ table|safe }}
    """, table=df.to_html(index=False))

# =========================
# 분석
# =========================
@app.route("/dataset/<dataset_id>/analysis")
def dataset_analysis(dataset_id):
    df = normalize_columns(read_csv_safe(os.path.join(DATA_DIR, DATASETS[dataset_id]["file"])))

    survey_col = get_survey_column(df)
    df["_조사"] = df[survey_col].apply(normalize_survey_type)
    df["_지역"] = df["지목(1/2/3)"].apply(normalize_region)

    all_items = list(STANDARDS["1지역"]["우려기준"].keys())
    for c in all_items:
        if c in df.columns:
            df[c] = normalize_numeric_series(df[c])

    selected = request.args.getlist("items")
    use_items = selected if selected else all_items

    df_A = df[df["_조사"] == "A"]
    df_B = df[df["_조사"] == "B"]

    A = analyze_dataset(df_A, use_items)
    B = analyze_dataset(df_B, use_items)

    return render_template_string("""
    <a href="/">🏠 Data Hub 홈으로</a>
    <h2>📊 분석</h2>

    <button type="button" onclick="selectAllItems()">전체선택</button>
    <button type="button" onclick="clearAllItems()">전체선택해제</button>

    <form method="get">
      <table border="1" cellpadding="8">
        <tr>
          {% for g in ITEM_GROUPS.keys() %}
            <th>{{ g }}</th>
          {% endfor %}
        </tr>
        <tr>
          {% for g, items in ITEM_GROUPS.items() %}
            <td valign="top">
              {% for item in items %}
                <label>
                  <input type="checkbox" name="items" value="{{ item }}"
                    {% if item in selected %}checked{% endif %}>
                  {{ item }}
                </label><br>
              {% endfor %}
            </td>
          {% endfor %}
        </tr>
      </table>
      <br>
      <button>선택 항목 보기</button>
    </form>

    <form method="get" action="/dataset/{{ dataset_id }}/download">
      {% for item in selected %}
        <input type="hidden" name="items" value="{{ item }}">
      {% endfor %}
      <button type="submit">📥 CSV 다운로드</button>
    </form>

    <hr>
    <h3>개황조사</h3>
    {{ A|safe }}

    <h3>정밀조사</h3>
    {{ B|safe }}

    <script>
    function selectAllItems() {
      document.querySelectorAll('input[name="items"]').forEach(cb => cb.checked = true);
    }
    function clearAllItems() {
      document.querySelectorAll('input[name="items"]').forEach(cb => cb.checked = false);
    }
    </script>
    """,
    ITEM_GROUPS=ITEM_GROUPS,
    selected=use_items,
    dataset_id=dataset_id,
    A=A.to_html(index=False),
    B=B.to_html(index=False)
    )

# =========================
# CSV 다운로드
# =========================
@app.route("/dataset/<dataset_id>/download")
def dataset_download(dataset_id):
    df = normalize_columns(read_csv_safe(os.path.join(DATA_DIR, DATASETS[dataset_id]["file"])))

    survey_col = get_survey_column(df)
    df["_조사"] = df[survey_col].apply(normalize_survey_type)
    df["_지역"] = df["지목(1/2/3)"].apply(normalize_region)

    all_items = list(STANDARDS["1지역"]["우려기준"].keys())
    for c in all_items:
        if c in df.columns:
            df[c] = normalize_numeric_series(df[c])

    selected = request.args.getlist("items")
    use_items = selected if selected else all_items

    df_A = df[df["_조사"] == "A"]
    df_B = df[df["_조사"] == "B"]

    result_A = analyze_dataset(df_A, use_items)
    result_B = analyze_dataset(df_B, use_items)

    result_A.insert(0, "조사구분", "개황(A)")
    result_B.insert(0, "조사구분", "정밀(B)")

    final_df = pd.concat([result_A, result_B], ignore_index=True)
    csv_data = final_df.to_csv(index=False, encoding="utf-8-sig")

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={dataset_id}_analysis.csv"
        }
    )


# =========================
# 로그
# =========================
@app.route("/dataset/<dataset_id>/log")
def dataset_log(dataset_id):
    df = normalize_columns(read_csv_safe(os.path.join(DATA_DIR, DATASETS[dataset_id]["file"])))
    df["_지역"] = df["지목(1/2/3)"].apply(normalize_region)
    fail = df[df["_지역"].isna()]

    return render_template_string("""
    <a href="/">🏠 Data Hub 홈으로</a>
    <h2>⚠ 로그 (지역 매칭 실패)</h2>
    {% if t %}
      {{ t|safe }}
    {% else %}
      <p>문제 없음</p>
    {% endif %}
    """,
    t=fail[["지목(1/2/3)"]].drop_duplicates().to_html(index=False)
      if not fail.empty else None
    )

# =========================
# 실행
# =========================
if __name__ == "__main__":
    app.run(debug=True)
