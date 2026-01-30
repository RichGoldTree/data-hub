import streamlit as st
from components.sidebar import render_sidebar
from components.dataTable import render_data_table
from utils.io import load_dataset
from utils.preprocess import preprocess_df
from utils.analysis import analyze

def main():
    st.set_page_config(layout="wide")
    st.title("📊 Data Hub Dashboard")

    dataset_id = render_sidebar()
    if dataset_id is None:
        st.stop()

    df = load_dataset(dataset_id)
    df = preprocess_df(df)

    A, B = analyze(df)
    render_data_table(A, B)

if __name__ == "__main__":
    main()
