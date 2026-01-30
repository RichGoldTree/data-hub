import pandas as pd
import os, json

DATA_DIR = "data"
META_FILE = "datasets.json"

def load_dataset(dataset_id):
    meta = json.load(open(META_FILE, encoding="utf-8"))
    path = os.path.join(DATA_DIR, meta[dataset_id]["file"])
    if path.endswith(".xlsx"):
        return pd.read_excel(path)
    return pd.read_csv(path)
