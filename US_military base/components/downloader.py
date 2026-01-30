import pandas as pd
from io import BytesIO
import streamlit as st

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
