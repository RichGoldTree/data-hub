import streamlit as st
import pandas as pd
import os
import json
from io import BytesIO
from datetime import datetime

# =========================
# 기본 설정
# =========================
st.set_page_config(page_title="📊 Data Hub", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
META_FILE = os.path.join(BASE_DIR, "datasets.json")
os.makedirs(DATA_DIR, exist_ok=True)

# =========================
# 항목 그룹 (도메인 정의)
# =========================
ITEM_GROUPS = {
    "중금속": ["Cd(mg/kg)", "Cu(mg/kg)", "As(mg/kg)", "Hg(mg/kg)",
            "Pb(mg/kg)", "Cr6+(mg/kg)", "Zn(mg/kg)", "Ni(mg/kg)"],
    "유류": ["Benzene", "Toluene", "Ethylbenzene", "Xylene", "TPH"],
    "유기용제": ["TCE", "PCE", "1,2DCA (1,2-디클로로에탄)"],
    "기타": ["F(mg/kg)", "PCBs(mg/kg)", "CN(mg/kg)",
            "Phenol(mg/kg)", "Pentachlorophenol(mg/kg)", "Dioxin", "pH"]
}
ALL_ITEMS = [i for g in ITEM_GROUPS.values() for i in g]

# =========================
# 공통 유틸
# =========================
def load_datasets():
    if os.path.exists(META_FILE):
        with open(META_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_datasets(d):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def read_table(path):
    if path.endswith(".xlsx"):
        return pd.read_excel(path)
    try:
        return pd.read_csv(path, encoding="utf-8")
    except:
        return pd.read_csv(path, encoding="cp949")

def normalize_numeric_series(s):
    return pd.to_numeric(
        s.astype(str).str.replace(r"[^0-9eE\.\+\-]", "", regex=True),
        errors="coerce"
    )

def get_survey_column(df):
    for c in df.columns:
        if "조사" in c:
            return c
    return None

def get_region_column(df):
    for c in df.columns:
        if "지목" in c or "지역" in c:
            return c
    return None

def normalize_survey_type(v):
    if pd.isna(v): return None
    if "개황" in str(v): return "A"
    if "정밀" in str(v) or "상세" in str(v): return "B"
    return None

def normalize_region(v):
    if pd.isna(v): return None
    if "1" in str(v): return "1지역"
    if "2" in str(v): return "2지역"
    if "3" in str(v): return "3지역"
    return None

# =========================
# 🧩 컴포넌트 1: 데이터 관리
# =========================
def render_dataset_manager():
    st.sidebar.title("🗂 데이터 관리")
    datasets = load_datasets()

    # ➕ 업로드
    st.sidebar.subheader("➕ 데이터 추가")
    uploaded = st.sidebar.file_uploader("CSV / XLSX 업로드", type=["csv", "xlsx"])
    if uploaded:
        name = st.sidebar.text_input("데이터 이름", uploaded.name)
        if st.sidebar.button("업로드 저장"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{ts}{os.path.splitext(uploaded.name)[1]}"
            with open(os.path.join(DATA_DIR, fname), "wb") as f:
                f.write(uploaded.getbuffer())
            datasets[ts] = {"name": name, "file": fname}
            save_datasets(datasets)
            st.experimental_rerun()

    # ❌ 삭제
    st.sidebar.subheader("❌ 데이터 삭제")
    if datasets:
        did = st.sidebar.selectbox(
            "삭제 대상",
            list(datasets.keys()),
            format_func=lambda k: datasets[k]["name"]
        )
        if st.sidebar.checkbox("⚠ 정말 삭제"):
            if st.sidebar.button("삭제 실행"):
                try:
                    os.remove(os.path.join(DATA_DIR, datasets[did]["file"]))
                except:
                    pass
                datasets.pop(did)
                save_datasets(datasets)
                st.experimental_rerun()

    return datasets

# =========================
# 🧩 컴포넌트 2: 데이터 선택
# =========================
def render_dataset_selector(datasets):
    if not datasets:
        st.info("📂 먼저 데이터를 업로드하세요.")
        st.stop()

    return st.selectbox(
        "📁 데이터 선택",
        list(datasets.keys()),
        format_func=lambda k: datasets[k]["name"]
    )

# =========================
# 🧩 컴포넌트 3: 전처리
# =========================
def preprocess_dataframe(df):
    survey_col = get_survey_column(df)
    df["_조사"] = "A" if survey_col is None else df[survey_col].apply(normalize_survey_type)

    region_col = get_region_column(df)
    if region_col is None:
        st.error("❌ 지역 컬럼을 찾을 수 없습니다.")
        st.stop()

    df["_지역"] = df[region_col].apply(normalize_region)

    for c in ALL_ITEMS:
        if c in df.columns:
            df[c] = normalize_numeric_series(df[c])

    return df

# =========================
# 🧩 컴포넌트 4: 분석 항목 선택
# =========================
def render_item_selector():
    st.subheader("✅ 분석 항목 선택")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔘 전체 선택"):
            for i in ALL_ITEMS:
                st.session_state[i] = True
    with c2:
        if st.button("⭕ 전체 해제"):
            for i in ALL_ITEMS:
                st.session_state[i] = False

    selected = []
    cols = st.columns(len(ITEM_GROUPS))
    for col, (g, items) in zip(cols, ITEM_GROUPS.items()):
        with col:
            st.markdown(f"**{g}**")
            for i in items:
                if st.checkbox(i, key=i):
                    selected.append(i)

    if not selected:
        st.warning("⚠ 항목을 선택하세요.")
        st.stop()

    return selected

# =========================
# 🧩 컴포넌트 5: 분석
# =========================
def analyze_dataset(df, items):
    out = []
    for item in items:
        r = {"항목": item}
        for region in ["1지역", "2지역", "3지역"]:
            sub = df[df["_지역"] == region]
            r[f"{region}_지점수"] = len(sub)
            r[f"{region}_최고"] = (
                float(sub[item].max())
                if item in sub.columns and not sub[item].isna().all()
                else None
            )
        out.append(r)
    return pd.DataFrame(out)

# =========================
# 🧩 컴포넌트 6: 결과 표시
# =========================
def render_analysis_result(A, B):
    st.subheader("📊 개황조사")
    st.dataframe(A, use_container_width=True)
    st.subheader("📊 정밀조사")
    st.dataframe(B, use_container_width=True)

# =========================
# 🧩 컴포넌트 7: 다운로드
# =========================
def render_xlsx_download(A, B, dataset_id):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        A.to_excel(writer, index=False, sheet_name="개황(A)")
        B.to_excel(writer, index=False, sheet_name="정밀(B)")

    st.download_button(
        "📥 XLSX 다운로드",
        data=buffer.getvalue(),
        file_name=f"{dataset_id}_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =========================
# 🚀 메인 실행
# =========================
def main():
    st.title("📊 Streamlit Data Hub")

    datasets = render_dataset_manager()
    dataset_id = render_dataset_selector(datasets)

    df = read_table(os.path.join(DATA_DIR, datasets[dataset_id]["file"]))
    st.subheader("📄 원본 데이터")
    st.dataframe(df, use_container_width=True)

    df = preprocess_dataframe(df)
    selected_items = render_item_selector()

    A = analyze_dataset(df[df["_조사"] == "A"], selected_items)
    B = analyze_dataset(df[df["_조사"] == "B"], selected_items)

    render_analysis_result(A, B)
    render_xlsx_download(A, B, dataset_id)

main()
