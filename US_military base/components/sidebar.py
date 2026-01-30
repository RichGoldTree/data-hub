import streamlit as st
import json, os
from datetime import datetime

META_FILE = "datasets.json"
DATA_DIR = "data"

def render_sidebar():
    st.sidebar.title("🗂 데이터 관리")

    datasets = json.load(open(META_FILE, encoding="utf-8"))

    # 데이터 선택
    dataset_id = st.sidebar.selectbox(
        "데이터 선택",
        list(datasets.keys()),
        format_func=lambda k: datasets[k]["name"]
    )

    # 업로드
    uploaded = st.sidebar.file_uploader("CSV/XLSX 업로드", type=["csv", "xlsx"])
    if uploaded and st.sidebar.button("업로드"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{ts}_{uploaded.name}"
        with open(os.path.join(DATA_DIR, fname), "wb") as f:
            f.write(uploaded.getbuffer())
        datasets[ts] = {"name": uploaded.name, "file": fname}
        json.dump(datasets, open(META_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        st.experimental_rerun()

    return dataset_id
