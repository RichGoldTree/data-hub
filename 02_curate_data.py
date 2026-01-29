import pandas as pd

# 원본 데이터 불러오기
df = pd.read_csv("data/weather_data.csv")

# 1. 날짜 컬럼을 날짜 타입으로 변환
df["date"] = pd.to_datetime(df["date"])

# 2. 온도 상태 컬럼 추가 (규칙 기반)
def classify_temperature(temp):
    if temp <= 2:
        return "Cold"
    elif temp <= 4:
        return "Mild"
    else:
        return "Warm"

df["temp_category"] = df["temperature"].apply(classify_temperature)

# 3. 필요한 컬럼만 선택
curated_df = df[["date", "temperature", "temp_category", "humidity"]]

# 4. 큐레이션 결과 저장
curated_df.to_csv("data/weather_data_curated.csv", index=False)

print("=== Curated Weather Data ===")
print(curated_df)
