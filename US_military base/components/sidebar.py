import streamlit as st
import os
import uuid
from datetime import datetime
from utils.io import load_datasets, save_datasets, DATA_DIR


def render_dataset_manager():
    st.sidebar.title("🗂 데이터 관리")
    datasets = load_datasets()

    # =========================
    # ➕ 데이터 업로드 (form 사용 / 한글 파일명 안전 처리)
    # =========================
    st.sidebar.subheader("➕ 데이터 추가")

    with st.sidebar.form("upload_form", clear_on_submit=True):
        uploaded = st.file_uploader(
            "CSV / XLSX 업로드",
            type=["csv", "xlsx"]
        )
        name = st.text_input("데이터 이름")
        submitted = st.form_submit_button("업로드 저장")

        if submitted:
            if uploaded is None:
                st.warning("파일을 선택하세요.")
            else:
                # 🔒 서버 저장용 파일명은 무조건 ASCII (UUID)
                ext = os.path.splitext(uploaded.name)[1].lower()
                safe_fname = f"{uuid.uuid4().hex}{ext}"

                with open(os.path.join(DATA_DIR, safe_fname), "wb") as f:
                    f.write(uploaded.getbuffer())

                # 메타데이터에는 사용자 친화적인 이름 유지
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                datasets[ts] = {
                    "name": name or uploaded.name,  # UI 표시용 (한글 OK)
                    "file": safe_fname              # 시스템 저장용 (영문만)
                }
                save_datasets(datasets)

                st.success("✅ 업로드 완료")

    # =========================
    # ❌ 데이터 삭제 (기존 기능 유지)
    # =========================
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
                except FileNotFoundError:
                    pass

                datasets.pop(did)
                save_datasets(datasets)

                # 삭제는 rerun 안전
                st.rerun()

    return datasets


def render_dataset_selector(datasets):
    if not datasets:
        st.info("📂 먼저 데이터를 업로드하세요.")
        st.stop()

    return st.selectbox(
        "📁 데이터 선택",
        list(datasets.keys()),
        format_func=lambda k: datasets[k]["name"]
    )
