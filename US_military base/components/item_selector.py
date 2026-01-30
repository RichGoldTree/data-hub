import streamlit as st
from utils.preprocess import ITEM_GROUPS, ALL_ITEMS

def render_item_selector():
    st.subheader("✅ 분석 항목 선택")

    if st.button("🔘 전체 선택"):
        for i in ALL_ITEMS:
            st.session_state[i] = True
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
