import pandas as pd

def analyze_dataset(df, items):
    out = []
    for item in items:
        r = {"항목": item}
        for region in ["1지역", "2지역", "3지역"]:
            sub = df[df["_지역"] == region]
            r[f"{region}_지점수"] = len(sub)
            r[f"{region}_최고"] = (
                float(sub[item].max())
                if item in sub.columns and not sub[item].isna().all()
                else None
            )
        out.append(r)
    return pd.DataFrame(out)
