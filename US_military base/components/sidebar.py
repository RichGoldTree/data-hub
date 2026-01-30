import streamlit as st
import os
from datetime import datetime
from utils.io import load_datasets, save_datasets, DATA_DIR

def render_dataset_manager():
    st.sidebar.title("🗂 데이터 관리")
    datasets = load_datasets()

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

    if datasets:
        did = st.sidebar.selectbox(
            "❌ 삭제 대상",
            list(datasets.keys()),
            format_func=lambda k: datasets[k]["name"]
        )
        if st.sidebar.checkbox("⚠ 정말 삭제") and st.sidebar.button("삭제 실행"):
            try:
                os.remove(os.path.join(DATA_DIR, datasets[did]["file"]))
            except:
                pass
            datasets.pop(did)
            save_datasets(datasets)
            st.experimental_rerun()

    return datasets

def render_dataset_selector(datasets):
    return st.selectbox(
        "📁 데이터 선택",
        list(datasets.keys()),
        format_func=lambda k: datasets[k]["name"]
    )
