import argparse
import os
import sys
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ONLINE_DATASET_URL = "https://raw.githubusercontent.com/huayreview/thai-lottery-results/main/thai-lottery-results.csv"

LOCAL_CACHE_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "thai-lottery-results.csv"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "thai-lottery-results", "thai-lottery-results.csv"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "thai-lottery-results.csv"),
]

def fetch_or_load_dataset(custom_path=None, online_url=ONLINE_DATASET_URL, offline=False):
    """
    Fetches latest dataset online from GitHub raw repository.
    Caches locally and falls back to local cache if offline or network error occurs.
    """
    if custom_path and os.path.exists(custom_path):
        print(f"Using custom local data: {custom_path}")
        return pd.read_csv(custom_path, dtype=str)

    cache_target = LOCAL_CACHE_PATHS[0]
    os.makedirs(os.path.dirname(cache_target), exist_ok=True)

    if not offline:
        try:
            print(f"Fetching latest data online: {online_url}")
            req = urllib.request.Request(
                online_url,
                headers={"User-Agent": "Mozilla/5.0 (ThaiLotteryAnalysis/2.0)"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode("utf-8")
                with open(cache_target, "w", encoding="utf-8") as f:
                    f.write(content)
            print(f"Updated local cache: {cache_target}")
            return pd.read_csv(cache_target, dtype=str)
        except Exception as e:
            print(f"Warning: Online fetch failed ({e}). Falling back to local cache...")

    for path in LOCAL_CACHE_PATHS:
        if os.path.exists(path):
            print(f"Using local cached data: {path}")
            return pd.read_csv(path, dtype=str)

    raise FileNotFoundError("Could not fetch online and no local cache found.")

def prepare_dataframe(df):
    df["draw_date"] = pd.to_datetime(df["draw_date"])
    df = df.sort_values(by="draw_date").reset_index(drop=True)
    
    df["bottom2"] = df["last_two_digits"].astype(str).str.zfill(2)
    df["top2"] = df["first_prize"].astype(str).str[-2:]
    df["top3"] = df["first_prize"].astype(str).str[-3:]
    df["day_name"] = df["draw_date"].dt.day_name()
    df["month_day"] = df["draw_date"].dt.strftime("%m-%d")
    return df

def get_parity(num_str):
    d1, d2 = int(num_str[0]), int(num_str[1])
    p1 = "คู่" if d1 % 2 == 0 else "คี่"
    p2 = "คู่" if d2 % 2 == 0 else "คี่"
    return f"{p1}-{p2}"

def calculate_2digit_scores(
    df_history,
    target_date,
    target_col="bottom2",
    w_day=0.35,
    w_seasonal=0.25,
    w_overall=0.25,
    w_recent=0.15,
    recent_draws=24
):
    history = df_history[df_history["draw_date"] < target_date].copy()
    if len(history) == 0:
        raise ValueError(f"No historical records found prior to {target_date}")

    target_dt = pd.to_datetime(target_date)
    target_day = target_dt.day_name()
    target_md = target_dt.strftime("%m-%d")

    df_day = history[history["day_name"] == target_day]
    df_seasonal = history[history["month_day"] == target_md]
    df_recent = history.tail(recent_draws)

    freq_overall = history[target_col].value_counts().to_dict()
    freq_day = df_day[target_col].value_counts().to_dict()
    freq_seasonal = df_seasonal[target_col].value_counts().to_dict()
    freq_recent = df_recent[target_col].value_counts().to_dict()

    last_seen_dict = {}
    reversed_history = history.iloc[::-1].reset_index(drop=True)
    for idx, row in reversed_history.iterrows():
        val = row[target_col]
        if val not in last_seen_dict:
            last_seen_dict[val] = idx + 1

    max_day = max(freq_day.values()) if freq_day else 1
    max_seasonal = max(freq_seasonal.values()) if freq_seasonal else 1
    max_overall = max(freq_overall.values()) if freq_overall else 1
    max_recent = max(freq_recent.values()) if freq_recent else 1

    records = []
    for i in range(100):
        num = f"{i:02d}"
        f_all = freq_overall.get(num, 0)
        f_day = freq_day.get(num, 0)
        f_sea = freq_seasonal.get(num, 0)
        f_rec = freq_recent.get(num, 0)

        s_day = (f_day / max_day) * 100.0 if max_day > 0 else 0.0
        s_sea = (f_sea / max_seasonal) * 100.0 if max_seasonal > 0 else 0.0
        s_all = (f_all / max_overall) * 100.0 if max_overall > 0 else 0.0
        s_rec = (f_rec / max_recent) * 100.0 if max_recent > 0 else 0.0

        composite = (
            w_day * s_day +
            w_seasonal * s_sea +
            w_overall * s_all +
            w_recent * s_rec
        )

        d_sum = int(num[0]) + int(num[1])
        last_seen = last_seen_dict.get(num, len(history))

        records.append({
            "number": num,
            "composite_score": round(composite, 2),
            "day_freq": f_day,
            "seasonal_freq": f_sea,
            "overall_freq": f_all,
            "recent_freq": f_rec,
            "digit_sum": d_sum,
            "parity": get_parity(num),
            "draws_since_last_seen": last_seen,
        })

    return pd.DataFrame(records).sort_values(by="composite_score", ascending=False).reset_index(drop=True)

def score_multivalue_3digit(series_all, series_day, series_sea, top_k=10):
    c_all = Counter()
    for item in series_all.dropna():
        for n in item.split(";"):
            c_all[n.strip().zfill(3)] += 1
    c_day = Counter()
    for item in series_day.dropna():
        for n in item.split(";"):
            c_day[n.strip().zfill(3)] += 1
    c_sea = Counter()
    for item in series_sea.dropna():
        for n in item.split(";"):
            c_sea[n.strip().zfill(3)] += 1

    unique_nums = set(c_all.keys())
    if not unique_nums:
        return pd.DataFrame()

    max_all = max(c_all.values()) if c_all else 1
    max_day = max(c_day.values()) if c_day else 1
    max_sea = max(c_sea.values()) if c_sea else 1

    records = []
    for num in unique_nums:
        f_all = c_all.get(num, 0)
        f_day = c_day.get(num, 0)
        f_sea = c_sea.get(num, 0)
        score = 0.40 * (f_day / max_day * 100) + 0.30 * (f_sea / max_sea * 100) + 0.30 * (f_all / max_all * 100)
        records.append({
            "number": num,
            "composite_score": round(score, 2),
            "day_freq": f_day,
            "seasonal_freq": f_sea,
            "overall_freq": f_all
        })
    df_res = pd.DataFrame(records).sort_values(by=["composite_score", "overall_freq"], ascending=False).reset_index(drop=True)
    return df_res.head(top_k)

def calculate_top3_first_prize(history, target_day, target_md, top_2digit_cand, top_k=10):
    """Scores 3-digit tail of first prize (3 ตัวบน) combining empirical history and top 2-digit tails."""
    history_day = history[history["day_name"] == target_day]
    history_sea = history[history["month_day"] == target_md]

    c_all = history["top3"].value_counts().to_dict()
    c_day = history_day["top3"].value_counts().to_dict()
    c_sea = history_sea["top3"].value_counts().to_dict()

    max_all = max(c_all.values()) if c_all else 1
    max_day = max(c_day.values()) if c_day else 1
    max_sea = max(c_sea.values()) if c_sea else 1

    # Candidate numbers: union of actual historical top3 plus combinations of top 2-digit tails
    all_candidates = set(c_all.keys())
    for d2 in top_2digit_cand[:5]:
        for prefix in range(10):
            all_candidates.add(f"{prefix}{d2}")

    records = []
    for num in all_candidates:
        f_all = c_all.get(num, 0)
        f_day = c_day.get(num, 0)
        f_sea = c_sea.get(num, 0)
        score = 0.40 * (f_day / max_day * 100) + 0.30 * (f_sea / max_sea * 100) + 0.30 * (f_all / max_all * 100)
        # Bonus if ends with top 2-digit candidate
        tail = num[-2:]
        if tail in top_2digit_cand[:3]:
            score += 15.0
        elif tail in top_2digit_cand[:5]:
            score += 8.0

        records.append({
            "number": num,
            "composite_score": round(score, 2),
            "day_freq": f_day,
            "seasonal_freq": f_sea,
            "overall_freq": f_all,
            "tail_2digit": tail
        })

    return pd.DataFrame(records).sort_values(by="composite_score", ascending=False).reset_index(drop=True).head(top_k)

def calculate_first_prize_6digit(history, target_day, target_md, top3_tail_candidates, top_k=10):
    """
    Generates high-probability 6-digit first prize candidates by synthesizing:
    1. Positional digit distribution (Pos 1 to 6)
    2. Empirical Front 3 of First Prize (Pos 1-3)
    3. Empirical Back 3 of First Prize (Pos 4-6)
    """
    history_day = history[history["day_name"] == target_day]
    history_sea = history[history["month_day"] == target_md]
    total_draws = len(history)

    # Positional frequencies
    pos_counts = [Counter() for _ in range(6)]
    for fp in history["first_prize"]:
        if len(fp) == 6:
            for i in range(6):
                pos_counts[i][fp[i]] += 1

    # Front 3 of first prize
    fp_front_all = history["first_prize"].str[:3].value_counts().to_dict()
    fp_front_day = history_day["first_prize"].str[:3].value_counts().to_dict()
    fp_front_sea = history_sea["first_prize"].str[:3].value_counts().to_dict()

    top_fronts = list(history["first_prize"].str[:3].value_counts().head(8).index)
    # Add day-specific top fronts
    for f in history_day["first_prize"].str[:3].value_counts().head(5).index:
        if f not in top_fronts:
            top_fronts.append(f)

    # Candidate back 3s
    cand_backs = list(top3_tail_candidates["number"].head(8))

    six_cands = []
    for f in top_fronts:
        for b in cand_backs:
            num6 = f + b
            # Positional score average
            pos_score = sum(pos_counts[i][num6[i]] / total_draws for i in range(6)) / 6.0 * 100.0
            
            # Front score
            f_score = fp_front_day.get(f, 0) * 0.4 + fp_front_sea.get(f, 0) * 0.3 + fp_front_all.get(f, 0) * 0.3
            
            # Back score from top3_tail_candidates
            b_row = top3_tail_candidates[top3_tail_candidates["number"] == b]
            b_score = b_row["composite_score"].values[0] if len(b_row) > 0 else 0.0

            composite = 0.35 * pos_score + 0.45 * b_score + 0.20 * (f_score * 20.0)
            six_cands.append({
                "number": num6,
                "composite_score": round(composite, 2),
                "front3": f,
                "back3": b,
                "notes": f"หน้า {f} + ท้าย {b}"
            })

    return pd.DataFrame(six_cands).sort_values(by="composite_score", ascending=False).reset_index(drop=True).head(top_k)

def main():
    parser = argparse.ArgumentParser(description="Thai Lottery Complete All-Prize Statistical Model")
    parser.add_argument("--url", type=str, default=ONLINE_DATASET_URL, help="URL to raw online CSV")
    parser.add_argument("--data", type=str, default=None, help="Path to local CSV (skips online fetch)")
    parser.add_argument("--offline", action="store_true", help="Force using local cache without online fetch")
    parser.add_argument("--target-date", type=str, default="2026-11-01", help="Target draw date (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default=None, help="Path to save output CSV")
    parser.add_argument("--top-n", type=int, default=10, help="Number of top candidates per category")
    parser.add_argument("--w-day", type=float, default=0.35, help="Weight for day of week frequency")
    parser.add_argument("--w-seasonal", type=float, default=0.25, help="Weight for seasonal (month-day) frequency")
    parser.add_argument("--w-overall", type=float, default=0.25, help="Weight for overall frequency")
    parser.add_argument("--w-recent", type=float, default=0.15, help="Weight for recent frequency")
    args = parser.parse_args()

    raw_df = fetch_or_load_dataset(custom_path=args.data, online_url=args.url, offline=args.offline)
    df = prepare_dataframe(raw_df)
    
    history = df[df["draw_date"] < args.target_date].copy()
    target_dt = pd.to_datetime(args.target_date)
    target_day = target_dt.day_name()
    target_md = target_dt.strftime("%m-%d")

    history_day = history[history["day_name"] == target_day]
    history_sea = history[history["month_day"] == target_md]

    print(f"Loaded {len(history)} historical draws (Prior to {args.target_date})")
    print(f"Target Draw: {args.target_date} ({target_day})")

    # 1. เลขท้าย 2 ตัว (2 ตัวล่าง)
    df_bottom2 = calculate_2digit_scores(
        df, args.target_date, target_col="bottom2",
        w_day=args.w_day, w_seasonal=args.w_seasonal,
        w_overall=args.w_overall, w_recent=args.w_recent
    )

    # 2. เลขท้ายรางวัลที่ 1 สองตัว (2 ตัวบน)
    df_top2 = calculate_2digit_scores(
        df, args.target_date, target_col="top2",
        w_day=args.w_day, w_seasonal=args.w_seasonal,
        w_overall=args.w_overall, w_recent=args.w_recent
    )

    # 3. เลขท้ายรางวัลที่ 1 สามตัว (3 ตัวบน)
    top2_cands = list(df_top2["number"].head(5))
    df_top3 = calculate_top3_first_prize(history, target_day, target_md, top2_cands, top_k=args.top_n)

    # 4. รางวัล 3 ตัว (เลขหน้า 3 ตัว & เลขท้าย 3 ตัว)
    df_front3 = score_multivalue_3digit(history["front_three_digits"], history_day["front_three_digits"], history_sea["front_three_digits"], top_k=args.top_n)
    df_last3 = score_multivalue_3digit(history["last_three_digits"], history_day["last_three_digits"], history_sea["last_three_digits"], top_k=args.top_n)

    # 5. รางวัลที่ 1 (6 หลัก)
    df_first_prize = calculate_first_prize_6digit(history, target_day, target_md, df_top3, top_k=args.top_n)

    # Print results cleanly
    print("\n=======================================================")
    print(" 1. สรุปชุดตัวเลข รางวัลที่ 1 (6 หลัก) ")
    print("=======================================================")
    print(df_first_prize[["number", "composite_score", "front3", "back3", "notes"]].to_string(index=False))

    print("\n=======================================================")
    print(" 2. เลขท้ายรางวัลที่ 1 สามตัว (3 ตัวบน) ")
    print("=======================================================")
    print(df_top3[["number", "composite_score", "day_freq", "seasonal_freq", "overall_freq", "tail_2digit"]].to_string(index=False))

    print("\n=======================================================")
    print(" 3. เลขท้ายรางวัลที่ 1 สองตัว (2 ตัวบน) ")
    print("=======================================================")
    print(df_top2[["number", "composite_score", "day_freq", "seasonal_freq", "overall_freq", "digit_sum", "parity"]].head(args.top_n).to_string(index=False))

    print("\n=======================================================")
    print(" 4. รางวัลเลขหน้า 3 ตัว (หมุน 2 ครั้ง) ")
    print("=======================================================")
    print(df_front3[["number", "composite_score", "day_freq", "seasonal_freq", "overall_freq"]].to_string(index=False))

    print("\n=======================================================")
    print(" 5. รางวัลเลขท้าย 3 ตัว (หมุน 2 ครั้ง) ")
    print("=======================================================")
    print(df_last3[["number", "composite_score", "day_freq", "seasonal_freq", "overall_freq"]].to_string(index=False))

    print("\n=======================================================")
    print(" 6. รางวัลเลขท้าย 2 ตัว (2 ตัวล่าง) ")
    print("=======================================================")
    print(df_bottom2[["number", "composite_score", "day_freq", "seasonal_freq", "overall_freq", "digit_sum", "parity"]].head(args.top_n).to_string(index=False))

    # Save CSV
    output_filename = args.output if args.output else f"thai_lottery_predictions_{args.target_date.replace('-', '')}.csv"
    output_dir = os.path.dirname(os.path.abspath(output_filename))
    os.makedirs(output_dir, exist_ok=True)

    export_rows = []
    for _, r in df_first_prize.iterrows():
        export_rows.append({"category": "รางวัลที่ 1 (6 หลัก)", "number": r["number"], "score": r["composite_score"], "details": r["notes"]})
    for _, r in df_top3.iterrows():
        export_rows.append({"category": "เลขท้ายรางวัลที่ 1 3 ตัว (3 ตัวบน)", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']}"})
    for _, r in df_top2.head(args.top_n).iterrows():
        export_rows.append({"category": "เลขท้ายรางวัลที่ 1 2 ตัว (2 ตัวบน)", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']} แต้ม:{r['digit_sum']} ({r['parity']})"})
    for _, r in df_front3.iterrows():
        export_rows.append({"category": "รางวัลเลขหน้า 3 ตัว", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']}"})
    for _, r in df_last3.iterrows():
        export_rows.append({"category": "รางวัลเลขท้าย 3 ตัว", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']}"})
    for _, r in df_bottom2.head(args.top_n).iterrows():
        export_rows.append({"category": "รางวัลเลขท้าย 2 ตัว (2 ตัวล่าง)", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']} แต้ม:{r['digit_sum']} ({r['parity']})"})

    pd.DataFrame(export_rows).to_csv(output_filename, index=False, encoding="utf-8-sig")
    print(f"\nAll prize predictions saved successfully to: {output_filename}")

if __name__ == "__main__":
    main()
