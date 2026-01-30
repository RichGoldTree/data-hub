import pandas as pd
import os


# =========================================================
# 1. 기준표 로딩
# =========================================================
def load_standards(filename: str) -> pd.DataFrame:
    """
    기준표 CSV 로딩
    (utils 폴더 기준)
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, filename)

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"기준표 파일을 찾을 수 없습니다: {full_path}")

    df = pd.read_csv(full_path, encoding="utf-8")
    df.columns = df.columns.str.strip()
    return df


# =========================================================
# 2. 기준 lookup 테이블 생성
# =========================================================
def build_standard_map(std_df: pd.DataFrame) -> dict:
    """
    {(지역, 기준종류, 항목): 기준값} 형태의 lookup dict 생성
    """
    std_map = {}

    for _, r in std_df.iterrows():
        region = r.iloc[0]
        level = r.iloc[1]

        for item in std_df.columns[2:]:
            val = r[item]

            if pd.isna(val):
                continue

            try:
                std_map[(region, level, item)] = float(val)
            except (ValueError, TypeError):
                continue

    return std_map


# =========================================================
# 3. 단일 기준 초과 요약
# =========================================================
def summarize_exceed(
    df: pd.DataFrame,
    items: list[str],
    std_map: dict,
    level: str
) -> pd.DataFrame:
    """
    항목별 기준 초과 지점수 / 시료수 집계
    """

    rows = []

    # 지점 컬럼 자동 결정
    site_col = None
    if "시료명" in df.columns:
        site_col = "시료명"
    elif "지점명" in df.columns:
        site_col = "지점명"

    for item in items:
        if item not in df.columns:
            rows.append({"항목": item, "지점수": 0, "시료수": 0})
            continue

        exceed_rows = []

        for _, r in df.iterrows():
            key = (r["_지역"], level, item)
            std = std_map.get(key)

            if std is None:
                continue

            val = r[item]
            if pd.notna(val) and val > std:
                exceed_rows.append(r)

        if exceed_rows:
            ex_df = pd.DataFrame(exceed_rows)

            site_cnt = ex_df[site_col].nunique() if site_col else len(ex_df)
            sample_cnt = len(ex_df)
        else:
            site_cnt = 0
            sample_cnt = 0

        rows.append({
            "항목": item,
            "지점수": site_cnt,
            "시료수": sample_cnt
        })

    return pd.DataFrame(rows)


# =========================================================
# 4. 기준 초과 분석 (종합 결과 반환)
# =========================================================
def analyze_exceedance(
    df: pd.DataFrame,
    items: list[str],
    standard_csv: str
) -> pd.DataFrame:
    """
    기준 초과 분석 결과를 하나의 DataFrame으로 반환
    (기준은 컬럼으로 표현)
    """

    if df.empty:
        return pd.DataFrame({"항목": items})

    std_df = load_standards(standard_csv)
    std_map = build_standard_map(std_df)

    merged_df = None

    for level in ["우려40", "우려기준", "대책기준"]:
        tmp = summarize_exceed(
            df=df,
            items=items,
            std_map=std_map,
            level=level
        )

        tmp = tmp.rename(columns={
            "지점수": f"{level}_지점수",
            "시료수": f"{level}_시료수"
        })

        if merged_df is None:
            merged_df = tmp
        else:
            merged_df = merged_df.merge(tmp, on="항목", how="outer")

    # NaN → 0
    count_cols = [c for c in merged_df.columns if c != "항목"]
    merged_df[count_cols] = merged_df[count_cols].fillna(0).astype(int)

    return merged_df
