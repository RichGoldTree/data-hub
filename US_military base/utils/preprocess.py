import pandas as pd
import streamlit as st

ITEM_GROUPS = {
    "중금속": ["Cd(mg/kg)", "Cu(mg/kg)", "As(mg/kg)", "Hg(mg/kg)",
            "Pb(mg/kg)", "Cr6+(mg/kg)", "Zn(mg/kg)", "Ni(mg/kg)"],
    "유류": ["Benzene", "Toluene", "Ethylbenzene", "Xylene", "TPH"],
    "유기용제": ["TCE", "PCE", "1,2DCA (1,2-디클로로에탄)"],
    "기타": ["F(mg/kg)", "PCBs(mg/kg)", "CN(mg/kg)",
            "Phenol(mg/kg)", "Pentachlorophenol(mg/kg)", "Dioxin", "pH"]
}
ALL_ITEMS = [i for g in ITEM_GROUPS.values() for i in g]

def normalize_numeric_series(s):
    return pd.to_numeric(
        s.astype(str).str.replace(r"[^0-9eE\.\+\-]", "", regex=True),
        errors="coerce"
    )

def preprocess_dataframe(df):
    survey_col = next((c for c in df.columns if "조사" in c), None)
    df["_조사"] = "A" if survey_col is None else df[survey_col].apply(
        lambda v: "A" if "개황" in str(v) else "B" if "정밀" in str(v) else None
    )

    region_col = next((c for c in df.columns if "지목" in c or "지역" in c), None)
    if region_col is None:
        st.error("❌ 지역 컬럼을 찾을 수 없습니다.")
        st.stop()

    df["_지역"] = df[region_col].apply(
        lambda v: "1지역" if "1" in str(v) else "2지역" if "2" in str(v) else "3지역" if "3" in str(v) else None
    )

    for c in ALL_ITEMS:
        if c in df.columns:
            df[c] = normalize_numeric_series(df[c])

    return df
