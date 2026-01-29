import pandas as pd

# CSV 파일 읽기
df = pd.read_csv("data/weather_data.csv")

# 데이터 확인
print("=== Weather Data ===")
print(df)

print("\n=== Basic Statistics ===")
print(df.describe())