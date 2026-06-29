import os
import sys
import csv

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

def read_csv(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"❌ File tidak ditemukan: {filepath}")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))