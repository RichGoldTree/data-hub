import streamlit as st
import pandas as pd
from io import BytesIO


def render_xlsx_download(A: pd.DataFrame, dataset_id: str):
    """
    기준 초과 분석 결과(통합 A+B)를 엑셀로 다운로드
    """

    if A is None or A.empty:
        st.warning("다운로드할 데이터가 없습니다.")
        return

    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        A.to_excel(
            writer,
            index=False,
            sheet_name="기준초과_종합"
        )

    st.download_button(
        label="📥 기준 초과 분석 결과 다운로드 (XLSX)",
        data=output.getvalue(),
        file_name=f"{dataset_id}_기준초과분석.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
