import pandas as pd
import numpy as np

file_path = r"C:\Users\USER\data-hub\US_military base\Sheet_form2.xlsx"

# 시트 로드
df1 = pd.read_excel(file_path, sheet_name="Sheet1")
df2 = pd.read_excel(file_path, sheet_name="Sheet2")

# 오염물질 컬럼
meta_cols = [
    'NO','조사구분','조사구역','시료채취일','시료구분',
    '심도','깊이','토지이용도','지목','원래지목','지점명','시 료 명'
]
pollutants = [c for c in df1.columns if c not in meta_cols]

# 기준 lookup 딕셔너리 생성
# std_dict[(기준구분, 지역)] = 기준 row
std_dict = {}
for _, r in df2.iterrows():
    if pd.notna(r['NO']):
        region = r['NO']
    std_dict[(r['대책구분'], region)] = r

# 결과 저장
rows = []

for pol in pollutants:
    row = {'항목': pol}

    # 최고농도 (Sheet1 전체)
    row['최고농도'] = df1[pol].max(skipna=True)

    for region in ['1지역', '2지역', '3지역']:
        for std_type in ['40%/70%', '우려기준']:

            std_row = std_dict.get((std_type, region))
            if std_row is None:
                row[f"{std_type}_{region}_지점수"] = '-'
                row[f"{std_type}_{region}_시료수"] = '-'
                continue

            std_val = std_row[pol]

            cond = (
                (df1['지목'] == region) &
                (df1[pol] > std_val)
            )

            # 지점 수 = 고유 지점명 개수
            row[f"{std_type}_{region}_지점수"] = df1.loc[cond, '지점명'].nunique()

            # 시료 수 = 행 개수
            row[f"{std_type}_{region}_시료수"] = cond.sum()

    rows.append(row)

# Sheet3 DataFrame
df_sheet3 = pd.DataFrame(rows)

# 컬럼 순서 정렬 (Sheet3와 동일하게)
ordered_cols = ['항목']
for std in ['40%/70%', '우려기준']:
    for r in ['1지역','2지역','3지역']:
        ordered_cols += [f"{std}_{r}_지점수", f"{std}_{r}_시료수"]
ordered_cols.append('최고농도')

df_sheet3 = df_sheet3[ordered_cols]

# 저장
out_path = r"C:\Users\USER\data-hub\US_military base\Sheet3_자동생성.xlsx"
df_sheet3.to_excel(out_path, index=False)

print("✅ Sheet3_자동생성.xlsx 생성 완료")
