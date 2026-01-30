import streamlit as st
import os

from components.sidebar import (
    render_dataset_manager,
    render_dataset_selector
)
from components.item_selector import render_item_selector
from components.downloader import render_xlsx_download

from utils.io import read_table
from utils.preprocess import preprocess_dataframe
from utils.analysis import analyze_exceedance


# =========================
# 메인 대시보드
# =========================
def main():
    st.set_page_config(page_title="📊 Data Hub", layout="wide")
    st.title("📊 Streamlit Data Hub")

    # -------------------------
    # 1. 데이터 관리 / 선택
    # -------------------------
    datasets = render_dataset_manager()
    dataset_id = render_dataset_selector(datasets)

    data_path = os.path.join("data", datasets[dataset_id]["file"])
    df_raw = read_table(data_path)

    st.subheader("📄 원본 데이터")
    st.dataframe(df_raw, use_container_width=True)

    # -------------------------
    # 2. 전처리
    # -------------------------
    df = preprocess_dataframe(df_raw)

    # -------------------------
    # 3. 분석 항목 선택
    # -------------------------
    selected_items = render_item_selector()

    if not selected_items:
        st.warning("⚠️ 분석할 항목을 선택해주세요.")
        return

    # -------------------------
    # 4. 조사구분(A/B) 분리
    # -------------------------
    SURVEY_COL = "조사구분"

    if SURVEY_COL not in df.columns:
        st.error(f"❌ 데이터에 '{SURVEY_COL}' 컬럼이 없습니다.")
        return

    df_A = df[df[SURVEY_COL] == "A"]   # 개황조사
    df_B = df[df[SURVEY_COL] == "B"]   # 상세조사

    # -------------------------
    # 5. 기준 초과 분석
    # -------------------------
    results_A = analyze_exceedance(
        df=df_A,
        items=selected_items,
        standard_csv="example_table2.csv"
    )

    results_B = analyze_exceedance(
        df=df_B,
        items=selected_items,
        standard_csv="example_table2.csv"
    )

    results_AB = analyze_exceedance(
        df=df,
        items=selected_items,
        standard_csv="example_table2.csv"
    )

    # -------------------------
    # 6. 결과 표시 (조사단계별 탭)
    # -------------------------
    st.subheader("📊 기준 초과 분석 결과")

    tab_A, tab_B, tab_AB = st.tabs(
        ["🅰️ 개황조사(A)", "🅱️ 상세조사(B)", "🅰️➕🅱️ 통합(A+B)"]
    )

    with tab_A:
        st.markdown("### 🅰️ 개황조사 기준 초과 현황")
        st.dataframe(results_A, use_container_width=True)

    with tab_B:
        st.markdown("### 🅱️ 상세조사 기준 초과 현황")
        st.dataframe(results_B, use_container_width=True)

    with tab_AB:
        st.markdown("### 🅰️➕🅱️ 개황 + 상세 통합 현황")
        st.dataframe(results_AB, use_container_width=True)

    # -------------------------
    # 7. XLSX 다운로드 (통합 결과)
    # -------------------------
    st.markdown("### ⬇️ 결과 다운로드")

    render_xlsx_download(
        A=results_AB,
        dataset_id=dataset_id
    )


# =========================
# 실행
# =========================
if __name__ == "__main__":
    main()
