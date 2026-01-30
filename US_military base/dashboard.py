import streamlit as st
import os

from components.sidebar import render_dataset_manager, render_dataset_selector
from components.item_selector import render_item_selector
from components.result_table import render_analysis_result
from components.downloader import render_xlsx_download

from utils.io import read_table
from utils.preprocess import preprocess_dataframe
from utils.analysis import analyze_dataset

def main():
    st.set_page_config(page_title="📊 Data Hub", layout="wide")
    st.title("📊 Streamlit Data Hub")

    datasets = render_dataset_manager()
    dataset_id = render_dataset_selector(datasets)

    df = read_table(os.path.join("data", datasets[dataset_id]["file"]))
    st.subheader("📄 원본 데이터")
    st.dataframe(df, use_container_width=True)

    df = preprocess_dataframe(df)
    selected_items = render_item_selector()

    A = analyze_dataset(df[df["_조사"] == "A"], selected_items)
    B = analyze_dataset(df[df["_조사"] == "B"], selected_items)

    render_analysis_result(A, B)
    render_xlsx_download(A, B, dataset_id)

if __name__ == "__main__":
    main()
