import streamlit as st

def render_analysis_result(A, B):
    st.subheader("📊 개황조사")
    st.dataframe(A, use_container_width=True)
    st.subheader("📊 정밀조사")
    st.dataframe(B, use_container_width=True)
