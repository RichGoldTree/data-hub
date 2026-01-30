import streamlit as st

def render_data_table(A, B):
    st.subheader("📊 개황(A)")
    st.dataframe(A, use_container_width=True)

    st.subheader("📊 정밀(B)")
    st.dataframe(B, use_container_width=True)
