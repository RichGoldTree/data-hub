import streamlit as st
import pandas as pd
from io import BytesIO
import re

st.set_page_config(page_title="EX 기준 초과 분석", layout="wide")

# =========================
# 컬럼 매핑 (ex.csv ↔ ex_std.csv)
# =========================
COLUMN_MAP = {
    "유기인": "유기인화합물",
    "페놀류": "Phenol",
    "PCB": "PCBs",
    "B(a)P": "BaP",
    "1,2-DCA": "1,2DCA",
}

STD_TYPES = ["40%/70%", "우려기준", "대책기준"]
REGIONS = ["1지역", "2지역", "3지역"]

# =========================
# 유틸 함수
# =========================
def clean_text(v):
    if pd.isna(v):
        return ""
    return str(v).strip().replace(" ", "")

def normalize_numeric_series(s):
    return pd.to_numeric(
        s.astype(str).str.replace(r"[^0-9eE\.\+\-]", "", regex=True),
        errors="coerce"
    )

def normalize_numeric_df(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = normalize_numeric_series(df[c])
    return df

def normalize_sample_name(name):
    if pd.isna(name):
        return ""
    return re.sub(r"-\d+$", "", str(name))

def ex_col_from_std_item(std_item: str, df_columns):
    for ex_name, std_name in COLUMN_MAP.items():
        if std_name == std_item and ex_name in df_columns:
            return ex_name
    return std_item

# =========================
# 결과 생성 함수
# =========================
def make_ex_result(df, std_df, mode="전체"):

    if mode == "개황":
        df = df[df["시료명"].astype(str).str.contains("A", na=False)]
    elif mode == "상세":
        df = df[df["시료명"].astype(str).str.contains("B", na=False)]

    df = df.copy()
    std_df = std_df.copy()

    df["지역"] = df["지역"].apply(clean_text)
    std_df["지역"] = std_df["지역"].apply(clean_text)
    std_df["구분"] = std_df["구분"].apply(clean_text)

    item_cols = [c for c in std_df.columns if c not in ["지역", "구분"]]
    std_df = normalize_numeric_df(std_df, item_cols)

    ex_item_cols = []
    for std_item in item_cols:
        ex_col = ex_col_from_std_item(std_item, df.columns)
        ex_item_cols.append(ex_col)

    df = normalize_numeric_df(df, ex_item_cols)

    result = {}
    detail_rows = []

    for std_item in item_cols:
        result[std_item] = {}
        ex_col = ex_col_from_std_item(std_item, df.columns)

        if ex_col not in df.columns:
            continue

        result[std_item]["최고농도"] = (
            float(df[ex_col].max()) if df[ex_col].notna().any() else None
        )

        for std_type in STD_TYPES:
            for region in REGIONS:

                row_key_count = f"{std_type}_{region}_지점수"
                row_key_sample = f"{std_type}_{region}_시료수"

                std_row = std_df[
                    (std_df["지역"] == clean_text(region)) &
                    (std_df["구분"] == clean_text(std_type))
                ]

                if std_row.empty:
                    result[std_item][row_key_count] = 0
                    result[std_item][row_key_sample] = 0
                    continue

                std_val = std_row.iloc[0][std_item]
                if pd.isna(std_val):
                    result[std_item][row_key_count] = 0
                    result[std_item][row_key_sample] = 0
                    continue

                sub = df[df["지역"] == clean_text(region)].copy()
                exceed = sub[sub[ex_col] > float(std_val)].copy()

                if exceed.empty:
                    result[std_item][row_key_count] = 0
                    result[std_item][row_key_sample] = 0
                    continue

                normalized_points = exceed["시료명"].apply(normalize_sample_name)

                result[std_item][row_key_count] = normalized_points.nunique()
                result[std_item][row_key_sample] = exceed["시료명"].nunique()

                tmp = pd.DataFrame({
                    "구분": std_type,
                    "지역": region,
                    "항목(기준)": std_item,
                    "시료명": exceed["시료명"],
                    "지점명(정규화)": normalized_points,
                    "농도": exceed[ex_col],
                    "기준값": float(std_val),
                })

                tmp["초과배수"] = tmp["농도"] / tmp["기준값"]
                detail_rows.append(tmp)

    result_df = pd.DataFrame(result)

    sum_row = {}
    for col in result_df.columns:
        total = 0
        for idx in result_df.index:
            if "_지점수" in idx or "_시료수" in idx:
                val = result_df.loc[idx, col]
                if pd.notna(val):
                    total += val
        sum_row[col] = total

    result_df.loc["합계"] = sum_row

    ordered_rows = []
    for std_type in STD_TYPES:
        for region in REGIONS:
            ordered_rows.append(f"{std_type}_{region}_지점수")
            ordered_rows.append(f"{std_type}_{region}_시료수")

    ordered_rows.append("최고농도")
    ordered_rows.append("합계")

    result_df = result_df.reindex(ordered_rows)

    detail_df = pd.concat(detail_rows, ignore_index=True) if detail_rows else pd.DataFrame()

    return result_df, detail_df


# =========================
# UI
# =========================
st.title("📊 EX 기준 초과 매트릭스 생성기")

mode = st.radio(
    "결과 유형 선택",
    ["개황", "상세", "개황+상세"],
    horizontal=True
)

mode_map = {
    "개황": "개황",
    "상세": "상세",
    "개황+상세": "전체"
}

ex_file = st.file_uploader("📁 ex.csv 업로드", type=["csv", "xlsx"])
std_file = st.file_uploader("📁 ex_std.csv 업로드", type=["csv", "xlsx"])

if ex_file and std_file:

    df = pd.read_excel(ex_file) if ex_file.name.endswith(".xlsx") else pd.read_csv(ex_file)
    std_df = pd.read_excel(std_file) if std_file.name.endswith(".xlsx") else pd.read_csv(std_file)

    # =========================
    # 📌 요약 블럭
    # =========================
    st.divider()
    st.subheader("📌 총 시료수 · 지점수 요약")

    summary_df = df.copy()

    if mode == "개황":
        summary_df = summary_df[summary_df["시료명"].astype(str).str.contains("A", na=False)]
    elif mode == "상세":
        summary_df = summary_df[summary_df["시료명"].astype(str).str.contains("B", na=False)]

    summary_df["정규화지점"] = summary_df["시료명"].apply(normalize_sample_name)

    col1, col2 = st.columns(2)
    col1.metric("총 시료수", summary_df["시료명"].nunique())
    col2.metric("총 지점수", summary_df["정규화지점"].nunique())

    # =========================
    # 📊 항목별 시료수
    # =========================
    st.markdown("### 📊 항목별 시료수")

    exclude_cols = ["지역", "시료명", "정규화지점"]
    item_cols = [c for c in summary_df.columns if c not in exclude_cols]

    item_count_df = pd.DataFrame({
        col: summary_df[col].notna().sum()
        for col in item_cols
    }, index=["시료수"]).T

    default_items = []
    if "TPH" in item_cols and "pH" in item_cols:
        start = item_cols.index("TPH")
        end = item_cols.index("pH")
        if start <= end:
            default_items = item_cols[start:end+1]

    if not default_items:
        default_items = item_cols[:5]

    selected_items = st.multiselect(
        "표시할 항목 선택",
        options=item_cols,
        default=default_items
    )

    filtered_item_df = item_count_df.loc[selected_items]

    transpose_item = st.checkbox("🔄 행/열 전환 (항목별 시료수)")

    if transpose_item:
        filtered_item_df = filtered_item_df.T

    st.dataframe(filtered_item_df, use_container_width=True)

    # =========================
    # 결과표
    # =========================
    st.subheader("📄 EX 데이터")
    st.dataframe(df, use_container_width=True)

    st.subheader("📄 기준 데이터")
    st.dataframe(std_df, use_container_width=True)

    result_df, detail_df = make_ex_result(df, std_df, mode_map[mode])

    st.subheader(f"📊 ex_result.csv 결과 ({mode})")

    transpose_view = st.checkbox("🔄 행/열 전환해서 보기 (결과표)")

    if transpose_view:
        display_df = result_df.T
    else:
        display_df = result_df

    st.dataframe(display_df, use_container_width=True)

    buffer = BytesIO()
    display_df.to_csv(buffer, encoding="utf-8-sig")
    st.download_button(
        "📥 ex_result.csv 다운로드",
        buffer.getvalue(),
        file_name=f"ex_result_{mode}.csv",
        mime="text/csv"
    )

    # =========================
    # 🔎 초과 원본 상세 (고급 필터)
    # =========================
    if not detail_df.empty:

        st.divider()
        st.subheader("🔎 초과 원본 상세 (고급 필터)")

        if st.checkbox("📌 초과 원본 데이터 보기"):

            col1, col2, col3 = st.columns(3)

            with col1:
                pick_std_type = st.multiselect(
                    "구분", sorted(detail_df["구분"].unique()),
                    default=sorted(detail_df["구분"].unique())
                )
                pick_region = st.multiselect(
                    "지역", sorted(detail_df["지역"].unique()),
                    default=sorted(detail_df["지역"].unique())
                )

            with col2:
                pick_item = st.multiselect(
                    "항목", sorted(detail_df["항목(기준)"].unique()),
                    default=sorted(detail_df["항목(기준)"].unique())
                )
                sample_search = st.text_input("시료명 검색")

            with col3:
                point_search = st.text_input("지점명 검색")
                min_factor, max_factor = st.slider(
                    "초과배수 범위",
                    float(detail_df["초과배수"].min()),
                    float(detail_df["초과배수"].max()),
                    (
                        float(detail_df["초과배수"].min()),
                        float(detail_df["초과배수"].max())
                    )
                )

            filtered = detail_df.copy()
            filtered = filtered[filtered["구분"].isin(pick_std_type)]
            filtered = filtered[filtered["지역"].isin(pick_region)]
            filtered = filtered[filtered["항목(기준)"].isin(pick_item)]

            if sample_search:
                filtered = filtered[filtered["시료명"].str.contains(sample_search, case=False, na=False)]
            if point_search:
                filtered = filtered[filtered["지점명(정규화)"].str.contains(point_search, case=False, na=False)]

            filtered = filtered[
                (filtered["초과배수"] >= min_factor) &
                (filtered["초과배수"] <= max_factor)
            ]

            st.dataframe(filtered, use_container_width=True)

            st.markdown("### 📈 필터 결과 기초통계")

            if not filtered.empty:

                stat_col1, stat_col2, stat_col3 = st.columns(3)

                total_n = len(filtered)
                unique_points = filtered["지점명(정규화)"].nunique()
                mean_conc = filtered["농도"].mean()
                max_conc = filtered["농도"].max()
                mean_factor = filtered["초과배수"].mean()
                max_factor = filtered["초과배수"].max()

                with stat_col1:
                    st.metric("데이터 개수 (n)", f"{total_n:,}")
                    st.metric("지점 수", f"{unique_points:,}")

                with stat_col2:
                    st.metric("평균 농도", f"{mean_conc:.3f}")
                    st.metric("최대 농도", f"{max_conc:.3f}")

                with stat_col3:
                    st.metric("평균 초과배수", f"{mean_factor:.2f}")
                    st.metric("최대 초과배수", f"{max_factor:.2f}")

            else:
                st.info("선택 조건에 해당하는 데이터가 없습니다.")

            buffer2 = BytesIO()
            filtered.to_csv(buffer2, index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 필터 결과 다운로드",
                buffer2.getvalue(),
                file_name="filtered_exceed_detail.csv",
                mime="text/csv"
            )

    else:
        st.info("초과 데이터가 없습니다.")