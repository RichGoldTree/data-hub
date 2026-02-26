import streamlit as st
import pandas as pd
import os
import json
from io import BytesIO
from datetime import datetime

# =========================
# 기본 설정
# =========================
st.set_page_config(page_title="📊 Data Hub + 법 기준 비교", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
META_FILE = os.path.join(BASE_DIR, "datasets.json")
os.makedirs(DATA_DIR, exist_ok=True)

# =========================
# 항목 그룹
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
# JSON 로드 (자동 동기화 포함)
# =========================
def load_datasets():
    if not os.path.exists(META_FILE):
        return {}

    with open(META_FILE, encoding="utf-8") as f:
        datasets = json.load(f)

    # 🔥 실제 파일 존재 여부 확인 후 정리
    cleaned = {}
    for k, v in datasets.items():
        file_path = os.path.join(DATA_DIR, v["file"])
        if os.path.exists(file_path):
            cleaned[k] = v

    # JSON 자동 동기화
    if len(cleaned) != len(datasets):
        save_datasets(cleaned)

    return cleaned


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


def get_column(df, keywords):
    for c in df.columns:
        for k in keywords:
            if k in c:
                return c
    return None


def normalize_survey(v):
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
# 데이터 관리
# =========================
def render_dataset_manager():
    st.sidebar.title("🗂 데이터 관리")
    datasets = load_datasets()

    # 업로드
    st.sidebar.subheader("➕ 데이터 추가")
    uploaded = st.sidebar.file_uploader("CSV / XLSX 업로드", type=["csv", "xlsx"])

    if uploaded:
        name = st.sidebar.text_input("데이터 이름", uploaded.name)
        if st.sidebar.button("업로드 저장"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{ts}{os.path.splitext(uploaded.name)[1]}"
            file_path = os.path.join(DATA_DIR, fname)

            with open(file_path, "wb") as f:
                f.write(uploaded.getbuffer())

            datasets[ts] = {"name": name, "file": fname}
            save_datasets(datasets)
            st.rerun()

    # 삭제
    st.sidebar.subheader("❌ 데이터 삭제")
    if datasets:
        did = st.sidebar.selectbox(
            "삭제 대상",
            list(datasets.keys()),
            format_func=lambda k: datasets[k]["name"]
        )

        if st.sidebar.checkbox("⚠ 정말 삭제"):
            if st.sidebar.button("삭제 실행"):
                file_path = os.path.join(DATA_DIR, datasets[did]["file"])

                if os.path.exists(file_path):
                    os.remove(file_path)

                datasets.pop(did, None)
                save_datasets(datasets)
                st.rerun()

    return datasets


# =========================
# 전처리
# =========================
def preprocess_dataframe(df):
    survey_col = get_column(df, ["조사"])
    region_col = get_column(df, ["지역","지목"])
    sample_col = get_column(df, ["시료"])

    df["_조사"] = df[survey_col].apply(normalize_survey) if survey_col else "A"
    df["_지역"] = df[region_col].apply(normalize_region)
    df["_시료"] = df[sample_col] if sample_col else "Unknown"

    for c in ALL_ITEMS:
        if c in df.columns:
            df[c] = normalize_numeric_series(df[c])

    return df


# =========================
# 기존 분석
# =========================
def analyze_dataset(df, items):
    out = []
    for item in items:
        r = {"항목": item}
        for region in ["1지역","2지역","3지역"]:
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
# 기준 비교 분석
# =========================
def analyze_with_standard(df, std_df, items):
    results = []

    for item in items:
        if item not in df.columns:
            continue

        for region in ["1지역","2지역","3지역"]:
            sub_region = df[df["_지역"] == region]
            if sub_region.empty:
                continue

            for sample in sub_region["_시료"].unique():
                sub = sub_region[sub_region["_시료"] == sample]
                max_val = sub[item].max()

                std_val = None
                if "항목" in std_df.columns and item in std_df["항목"].values:
                    std_arr = std_df.loc[
                        std_df["항목"] == item, region
                    ].values
                    std_val = std_arr[0] if len(std_arr) else None

                exceed = (
                    max_val > std_val
                    if std_val is not None and pd.notna(max_val)
                    else None
                )

                results.append({
                    "시료명": sample,
                    "지역": region,
                    "항목": item,
                    "최대값": max_val,
                    "기준": std_val,
                    "초과여부": exceed
                })

    return pd.DataFrame(results)


# =========================
# 메인
# =========================
def main():
    st.title("📊 Data Hub + 법 기준 비교")

    datasets = render_dataset_manager()
    if not datasets:
        st.info("📂 먼저 데이터를 업로드하세요.")
        st.stop()

    dataset_id = st.selectbox(
        "📁 데이터 선택",
        list(datasets.keys()),
        format_func=lambda k: datasets[k]["name"]
    )

    df = read_table(os.path.join(DATA_DIR, datasets[dataset_id]["file"]))
    st.subheader("📄 원본 데이터")
    st.dataframe(df, use_container_width=True)

    df = preprocess_dataframe(df)

    selected_items = st.multiselect(
        "분석 항목 선택",
        ALL_ITEMS,
        default=[i for i in ALL_ITEMS if i in df.columns]
    )

    if not selected_items:
        st.stop()

    # 기존 분석
    A = analyze_dataset(df[df["_조사"]=="A"], selected_items)
    B = analyze_dataset(df[df["_조사"]=="B"], selected_items)

    st.subheader("📊 기존 통계 분석")
    st.markdown("### 개황조사")
    st.dataframe(A, use_container_width=True)
    st.markdown("### 정밀조사")
    st.dataframe(B, use_container_width=True)

    # 기준 업로드
    st.sidebar.header("📏 기준농도 업로드")
    std_file = st.sidebar.file_uploader("기준 CSV / XLSX 업로드", type=["csv","xlsx"])

    if std_file:
        std_df = pd.read_excel(std_file) if std_file.name.endswith(".xlsx") else pd.read_csv(std_file)

        result_std = analyze_with_standard(df, std_df, selected_items)

        st.subheader("🚨 기준 초과 분석 결과")
        st.dataframe(result_std, use_container_width=True)

        # 다운로드
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            A.to_excel(writer, index=False, sheet_name="기존_개황")
            B.to_excel(writer, index=False, sheet_name="기존_정밀")
            result_std.to_excel(writer, index=False, sheet_name="기준초과")

        st.download_button(
            "📥 전체 결과 다운로드",
            buffer.getvalue(),
            file_name=f"{dataset_id}_full_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


if __name__ == "__main__":
    main()