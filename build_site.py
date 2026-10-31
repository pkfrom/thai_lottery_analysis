import os
import sys
import json
import shutil
from datetime import datetime
import pandas as pd

from lottery_prediction_model import (
    fetch_or_load_dataset,
    prepare_dataframe,
    calculate_2digit_scores,
    score_multivalue_3digit,
    calculate_top3_first_prize,
    calculate_first_prize_6digit,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

THAI_MONTHS = [
    "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
]

THAI_DAYS = {
    "Monday": "วันจันทร์",
    "Tuesday": "วันอังคาร",
    "Wednesday": "วันพุธ",
    "Thursday": "วันพฤหัสบดี",
    "Friday": "วันศุกร์",
    "Saturday": "วันเสาร์",
    "Sunday": "วันอาทิตย์",
}

def format_thai_date(dt):
    day = dt.day
    month = THAI_MONTHS[dt.month]
    year = dt.year + 543
    english_day = dt.strftime("%A")
    day_name = THAI_DAYS.get(english_day, english_day)
    return f"{day_name}ที่ {day} {month} {year}"

def get_next_draw_date(last_dt):
    y, m, d = last_dt.year, last_dt.month, last_dt.day
    if d < 15:
        next_d = 17 if m == 1 else 16
        return datetime(y, m, next_d)
    else:
        if m == 12:
            return datetime(y + 1, 1, 17)
        next_m = m + 1
        next_d = 2 if next_m == 5 else 1
        return datetime(y, next_m, next_d)

def evaluate_past_draw(df):
    last_row = df.iloc[-1]
    target_dt = last_row["draw_date"]
    target_date_str = target_dt.strftime("%Y-%m-%d")
    target_date_th = format_thai_date(target_dt)
    target_day = target_dt.strftime("%A")
    target_md = target_dt.strftime("%m-%d")

    history = df[df["draw_date"] < target_date_str].copy()
    history_day = history[history["day_name"] == target_day]
    history_sea = history[history["month_day"] == target_md]

    actual_fp = last_row["first_prize"]
    actual_top3 = last_row["first_prize"][-3:]
    actual_top2 = last_row["first_prize"][-2:]
    actual_bottom2 = last_row["bottom2"]
    actual_front3 = [x.strip() for x in str(last_row["front_three_digits"]).split(";") if x.strip()]
    actual_last3 = [x.strip() for x in str(last_row["last_three_digits"]).split(";") if x.strip()]

    df_b2 = calculate_2digit_scores(df, target_date_str, target_col="bottom2")
    df_t2 = calculate_2digit_scores(df, target_date_str, target_col="top2")

    b2_match = df_b2[df_b2["number"] == actual_bottom2]
    b2_rank = int(b2_match.index[0] + 1) if len(b2_match) > 0 else 999
    b2_score = float(b2_match["composite_score"].values[0]) if len(b2_match) > 0 else 0.0

    t2_match = df_t2[df_t2["number"] == actual_top2]
    t2_rank = int(t2_match.index[0] + 1) if len(t2_match) > 0 else 999
    t2_score = float(t2_match["composite_score"].values[0]) if len(t2_match) > 0 else 0.0

    top2_cands = list(df_t2["number"].head(5))
    df_t3 = calculate_top3_first_prize(history, target_day, target_md, top2_cands, top_k=50)
    t3_match = df_t3[df_t3["number"] == actual_top3]
    t3_rank = int(t3_match.index[0] + 1) if len(t3_match) > 0 else None

    df_fp = calculate_first_prize_6digit(history, target_day, target_md, df_t3, top_k=10)
    top_pred_fp = df_fp.iloc[0]["number"] if len(df_fp) > 0 else "-"

    return {
        "date_str": target_date_str,
        "date_th": target_date_th,
        "first_prize": {
            "actual": actual_fp,
            "predicted_top1": top_pred_fp,
        },
        "top3": {
            "actual": actual_top3,
            "rank": t3_rank if t3_rank else "นอก Top 50",
        },
        "top2": {
            "actual": actual_top2,
            "rank": t2_rank,
            "score": t2_score,
            "in_top3": t2_rank <= 3,
        },
        "bottom2": {
            "actual": actual_bottom2,
            "rank": b2_rank,
            "score": b2_score,
            "in_top3": b2_rank <= 3,
        },
        "front3": {
            "actual": actual_front3
        },
        "last3": {
            "actual": actual_last3
        }
    }

def get_past_history_log(df, n_draws=5):
    records = []
    start_idx = max(0, len(df) - n_draws)
    for idx in range(start_idx, len(df)):
        row = df.iloc[idx]
        dt = row["draw_date"]
        dt_str = dt.strftime("%Y-%m-%d")
        dt_th = f"{dt.day} {THAI_MONTHS[dt.month]} {dt.year + 543}"

        act_b2 = row["bottom2"]
        act_t2 = row["top2"]

        df_b2 = calculate_2digit_scores(df, dt_str, target_col="bottom2")
        df_t2 = calculate_2digit_scores(df, dt_str, target_col="top2")

        b2_rank = int(df_b2[df_b2["number"] == act_b2].index[0] + 1)
        t2_rank = int(df_t2[df_t2["number"] == act_t2].index[0] + 1)

        records.append({
            "draw_date": dt_str,
            "draw_date_th": dt_th,
            "first_prize": row["first_prize"],
            "top2_actual": act_t2,
            "top2_rank": t2_rank,
            "bottom2_actual": act_b2,
            "bottom2_rank": b2_rank,
        })
    return records

def get_cold_numbers(df, target_date_str):
    df_b2 = calculate_2digit_scores(df, target_date_str, target_col="bottom2")
    df_t2 = calculate_2digit_scores(df, target_date_str, target_col="top2")

    cold_b2 = df_b2.sort_values(by=["draws_since_last_seen", "overall_freq"], ascending=[False, True]).head(3)
    cold_t2 = df_t2.sort_values(by=["draws_since_last_seen", "overall_freq"], ascending=[False, True]).head(3)

    return {
        "bottom2": cold_b2[["number", "draws_since_last_seen", "overall_freq"]].to_dict(orient="records"),
        "top2": cold_t2[["number", "draws_since_last_seen", "overall_freq"]].to_dict(orient="records"),
    }

def get_one_year_hit_rate(df, n_draws=24):
    hits_b2 = 0
    hits_t2 = 0
    start_idx = max(0, len(df) - n_draws)
    eval_draws = len(df) - start_idx

    for idx in range(start_idx, len(df)):
        row = df.iloc[idx]
        dt = row["draw_date"].strftime("%Y-%m-%d")
        act_b2 = row["bottom2"]
        act_t2 = row["top2"]

        p_b2 = set(calculate_2digit_scores(df, dt, target_col="bottom2").head(3)["number"])
        p_t2 = set(calculate_2digit_scores(df, dt, target_col="top2").head(3)["number"])

        if act_b2 in p_b2:
            hits_b2 += 1
        if act_t2 in p_t2:
            hits_t2 += 1

    return {
        "eval_draws": eval_draws,
        "bottom2_hits": hits_b2,
        "bottom2_pct": round((hits_b2 / eval_draws) * 100.0, 1) if eval_draws > 0 else 0.0,
        "top2_hits": hits_t2,
        "top2_pct": round((hits_t2 / eval_draws) * 100.0, 1) if eval_draws > 0 else 0.0,
        "random_baseline_pct": 3.0
    }

def generate_html(data):
    target_date_str = data["target_date"]
    target_date_th = data["target_date_th"]
    last_update = data["last_update"]
    total_draws = data["total_draws"]
    history_start = data["history_start"]
    history_end = data["history_end"]
    past_eval = data.get("past_evaluation", {})
    history_log = data.get("history_log", [])
    cold_numbers = data.get("cold_numbers", {})
    hit_rate = data.get("hit_rate_1year", {})

    fp = data.get("first_prize", [])
    top3 = data.get("top3", [])
    top2 = data.get("top2", [])
    bottom2 = data.get("bottom2", [])
    front3 = data.get("front3", [])
    last3 = data.get("last3", [])

    # Plain text summary for 1-click copy
    summary_text = f"""🎰 ผลวิเคราะห์สถิติหวยรัฐบาลไทย
งวด: {target_date_th}
-----------------------
🏆 รางวัลที่ 1: {', '.join([x['number'] for x in fp])}
🎯 3 ตัวบน: {', '.join([x['number'] for x in top3])}
🎯 2 ตัวบน: {', '.join([x['number'] for x in top2])}
🎲 2 ตัวล่าง: {', '.join([x['number'] for x in bottom2])}
📦 เลขหน้า 3 ตัว: {', '.join([x['number'] for x in front3])}
📦 เลขท้าย 3 ตัว: {', '.join([x['number'] for x in last3])}
-----------------------
ดูตารางเต็ม: https://pkfrom.github.io/thai_lottery_analysis/"""

    def make_table_rows(items, number_color="text-white", has_tail=False):
        rows = ""
        for idx, item in enumerate(items, 1):
            badge_color = "bg-amber-500/20 text-amber-300 border-amber-500/30" if idx == 1 else "bg-slate-800 text-slate-400 border-slate-700"
            tail_badge = f"<span class='ml-2 text-xs px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800'>ชน 2 ตัวบน {item.get('tail_2digit','')}</span>" if (has_tail and item.get('tail_2digit')) else ""
            rows += f"""
            <tr class="border-b border-slate-800/80 hover:bg-slate-800/30 transition">
                <td class="py-3 px-4 text-center"><span class="px-2 py-0.5 rounded text-xs border {badge_color} font-semibold">#{idx}</span></td>
                <td class="py-3 px-4 font-mono font-bold text-xl {number_color}">
                    {item['number']} {tail_badge}
                </td>
                <td class="py-3 px-4 text-center font-mono text-emerald-400 font-semibold">{item.get('composite_score', '-')}</td>
                <td class="py-3 px-4 text-center text-slate-300">{item.get('day_freq', '-')}</td>
                <td class="py-3 px-4 text-center text-slate-300">{item.get('seasonal_freq', '-')}</td>
                <td class="py-3 px-4 text-center text-slate-300">{item.get('overall_freq', '-')}</td>
                <td class="py-3 px-4 text-right">
                    <button onclick="copyNum('{item['number']}', this)" class="px-2.5 py-1 rounded text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition">📋 คัดลอก</button>
                </td>
            </tr>
            """
        return rows

    def make_history_rows(items):
        rows = ""
        for item in items:
            t2_badge = f"<span class='px-2 py-0.5 rounded text-xs bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold'>อันดับ {item['top2_rank']}</span>" if item['top2_rank'] <= 3 else (f"<span class='px-2 py-0.5 rounded text-xs bg-cyan-950 text-cyan-300 border border-cyan-800'>อันดับ {item['top2_rank']}</span>" if item['top2_rank'] <= 20 else f"<span class='px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-400'>อันดับ {item['top2_rank']}</span>")
            b2_badge = f"<span class='px-2 py-0.5 rounded text-xs bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold'>อันดับ {item['bottom2_rank']}</span>" if item['bottom2_rank'] <= 3 else (f"<span class='px-2 py-0.5 rounded text-xs bg-cyan-950 text-cyan-300 border border-cyan-800'>อันดับ {item['bottom2_rank']}</span>" if item['bottom2_rank'] <= 20 else f"<span class='px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-400'>อันดับ {item['bottom2_rank']}</span>")

            rows += f"""
            <tr class="border-b border-slate-800/80 hover:bg-slate-800/30 transition">
                <td class="py-3 px-4 font-medium text-slate-300">{item['draw_date_th']}</td>
                <td class="py-3 px-4 font-mono font-bold text-slate-200">{item['first_prize']}</td>
                <td class="py-3 px-4 font-mono font-bold text-cyan-300">{item['top2_actual']} {t2_badge}</td>
                <td class="py-3 px-4 font-mono font-bold text-emerald-300">{item['bottom2_actual']} {b2_badge}</td>
            </tr>
            """
        return rows

    html_content = f"""<!DOCTYPE html>
<html lang="th" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>สถิติหวยรัฐบาลไทย - สรุปเลขเด่นงวด {target_date_th}</title>
    <meta name="description" content="สรุปตัวเลขสถิติเด่นอันดับ 1-3 รางวัลที่ 1, 3 ตัวบน, 2 ตัวบน, 2 ตัวล่าง พร้อมระบบตรวจผลย้อนหลัง">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🎰</text></svg>">
    
    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://pkfrom.github.io/thai_lottery_analysis/">
    <meta property="og:title" content="สถิติหวยรัฐบาลไทย - สรุปเลขเด่นงวด {target_date_th}">
    <meta property="og:description" content="สรุปตัวเลขสถิติเด่นอันดับ 1-3 ครบทุกรางวัล พร้อมปุ่มคัดลอกและตรวจผลย้อนหลัง">
    <meta property="og:site_name" content="Thai Lottery Statistical Analysis">
    <meta name="twitter:card" content="summary">

    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Prompt:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    
    <style>
        body {{
            font-family: 'Prompt', sans-serif;
            background-color: #080c14;
            color: #f1f5f9;
        }}
        .font-num {{
            font-family: 'Chakra Petch', monospace;
        }}
        .card-surface {{
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(148, 163, 184, 0.12);
            backdrop-filter: blur(16px);
        }}
        .card-surface:hover {{
            border-color: rgba(148, 163, 184, 0.25);
        }}
    </style>
</head>
<body class="min-h-screen flex flex-col selection:bg-amber-500/30 selection:text-amber-200">

    <!-- Top Navigation -->
    <header class="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
        <div class="max-w-6xl mx-auto px-4 py-3 flex justify-between items-center">
            <div class="flex items-center space-x-3">
                <span class="text-2xl">🎰</span>
                <div>
                    <h1 class="text-base font-bold text-white flex items-center gap-2">
                        สถิติหวยรัฐบาลไทย
                        <span class="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800">Auto</span>
                    </h1>
                </div>
            </div>
            <div class="flex items-center space-x-2 text-xs">
                <button onclick="copySummary()" id="copy-summary-btn" class="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition flex items-center gap-1.5 shadow-sm">
                    📋 คัดลอกเลขทั้งหมด
                </button>
                <a href="https://github.com/pkfrom/thai_lottery_analysis" target="_blank" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition hidden sm:inline-flex items-center gap-1">
                    GitHub
                </a>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-6xl mx-auto px-4 py-6 flex-grow space-y-6">

        <!-- Banner งวดถัดไป (Clean & Focused) -->
        <section class="card-surface rounded-2xl p-6 sm:p-8 relative overflow-hidden text-center sm:text-left flex flex-col sm:flex-row justify-between items-center gap-6">
            <div>
                <span class="text-xs uppercase tracking-wider font-semibold text-amber-400 bg-amber-950/80 px-3 py-1 rounded-full border border-amber-800/50">
                    เลขเด่นงวดถัดไป • คัดเฉพาะอันดับ 1–3
                </span>
                <h2 class="text-3xl sm:text-4xl font-extrabold text-white mt-3 font-num tracking-tight">
                    {target_date_th}
                </h2>
                <p class="text-xs text-slate-400 mt-2">
                    วิเคราะห์จากสถิติสลากกินแบ่งรัฐบาล {total_draws} งวด ({history_start} ถึง {history_end})
                </p>
            </div>
            <div class="text-center sm:text-right text-xs text-slate-400 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                <div class="text-slate-500 text-[11px]">สถานะข้อมูล</div>
                <div class="font-semibold text-emerald-400 mt-0.5">เชื่อมต่อผลรางวัลล่าสุดแล้ว</div>
                <div class="text-[10px] text-slate-500 mt-1">{last_update}</div>
            </div>
        </section>

        <!-- Segmented Tab Navigation -->
        <div class="flex p-1 bg-slate-900/90 rounded-xl border border-slate-800 max-w-md mx-auto text-xs sm:text-sm">
            <button onclick="switchTab('summary')" id="tab-btn-summary" class="tab-btn flex-1 py-2 text-center font-bold rounded-lg transition bg-amber-500 text-slate-950 shadow-sm">
                🎯 สรุปเลขเด่น
            </button>
            <button onclick="switchTab('stats')" id="tab-btn-stats" class="tab-btn flex-1 py-2 text-center font-medium rounded-lg transition text-slate-400 hover:text-white">
                📊 เจาะลึกสถิติ
            </button>
            <button onclick="switchTab('past')" id="tab-btn-past" class="tab-btn flex-1 py-2 text-center font-medium rounded-lg transition text-slate-400 hover:text-white">
                🔍 ตรวจผลย้อนหลัง
            </button>
        </div>

        <!-- ======================================================== -->
        <!-- TAB 1: สรุปเลขเด่น (Clean, Scannable, High UX)            -->
        <!-- ======================================================== -->
        <div id="tab-summary" class="tab-content space-y-6">

            <div class="grid grid-cols-1 md:grid-cols-2 gap-5">

                <!-- การ์ด 1: รางวัลที่ 1 (6 หลัก) -->
                <div class="card-surface rounded-2xl p-6 border-t-4 border-amber-500 space-y-4">
                    <div class="flex justify-between items-center">
                        <h3 class="text-base font-bold text-white flex items-center gap-2">
                            <span>🏆</span> รางวัลที่ 1 (6 หลัก)
                        </h3>
                        <span class="text-xs text-amber-400 font-medium">Top 3</span>
                    </div>

                    <!-- อันดับ 1 (ใหญ่เด่น) -->
                    <div class="p-4 rounded-xl bg-gradient-to-r from-amber-950/40 to-slate-900/60 border border-amber-500/30 flex justify-between items-center">
                        <div>
                            <div class="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">อันดับ 1 (เด่นที่สุด)</div>
                            <div class="font-num text-3xl font-extrabold text-amber-300 tracking-wider mt-1">{fp[0]['number'] if len(fp) > 0 else '-'}</div>
                            <div class="text-xs text-slate-400 mt-1 font-mono">{fp[0]['notes'] if len(fp) > 0 else ''}</div>
                        </div>
                        <button onclick="copyNum('{fp[0]['number'] if len(fp) > 0 else ''}', this)" class="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-semibold transition">
                            📋 คัดลอก
                        </button>
                    </div>

                    <!-- อันดับ 2 & 3 -->
                    <div class="grid grid-cols-2 gap-3 pt-1">
                        <div class="p-3 rounded-xl bg-slate-900/50 border border-slate-800 flex justify-between items-center">
                            <div>
                                <span class="text-[10px] text-slate-400">อันดับ 2</span>
                                <div class="font-num text-lg font-bold text-slate-200">{fp[1]['number'] if len(fp) > 1 else '-'}</div>
                            </div>
                            <button onclick="copyNum('{fp[1]['number'] if len(fp) > 1 else ''}', this)" class="text-xs text-slate-400 hover:text-white p-1">📋</button>
                        </div>
                        <div class="p-3 rounded-xl bg-slate-900/50 border border-slate-800 flex justify-between items-center">
                            <div>
                                <span class="text-[10px] text-slate-400">อันดับ 3</span>
                                <div class="font-num text-lg font-bold text-slate-200">{fp[2]['number'] if len(fp) > 2 else '-'}</div>
                            </div>
                            <button onclick="copyNum('{fp[2]['number'] if len(fp) > 2 else ''}', this)" class="text-xs text-slate-400 hover:text-white p-1">📋</button>
                        </div>
                    </div>
                </div>

                <!-- การ์ด 2: 2 ตัวล่าง (เลขท้าย 2 ตัว) -->
                <div class="card-surface rounded-2xl p-6 border-t-4 border-emerald-500 space-y-4">
                    <div class="flex justify-between items-center">
                        <h3 class="text-base font-bold text-white flex items-center gap-2">
                            <span>🎲</span> 2 ตัวล่าง (เลขท้าย 2 ตัว)
                        </h3>
                        <span class="text-xs text-emerald-400 font-medium">Top 3</span>
                    </div>

                    <!-- อันดับ 1 (ใหญ่เด่น) -->
                    <div class="p-4 rounded-xl bg-gradient-to-r from-emerald-950/40 to-slate-900/60 border border-emerald-500/30 flex justify-between items-center">
                        <div>
                            <div class="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">อันดับ 1 (เด่นที่สุด)</div>
                            <div class="font-num text-4xl font-extrabold text-emerald-300 tracking-wider mt-1">{bottom2[0]['number'] if len(bottom2) > 0 else '-'}</div>
                            <div class="text-xs text-slate-400 mt-1">สถิติออกวันอาทิตย์ {bottom2[0]['day_freq']} ครั้ง • รวม {bottom2[0]['overall_freq']} ครั้ง</div>
                        </div>
                        <button onclick="copyNum('{bottom2[0]['number'] if len(bottom2) > 0 else ''}', this)" class="px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-xs font-semibold transition">
                            📋 คัดลอก
                        </button>
                    </div>

                    <!-- อันดับ 2 & 3 -->
                    <div class="grid grid-cols-2 gap-3 pt-1">
                        <div class="p-3 rounded-xl bg-slate-900/50 border border-slate-800 flex justify-between items-center">
                            <div>
                                <span class="text-[10px] text-slate-400">อันดับ 2</span>
                                <div class="font-num text-xl font-bold text-slate-200">{bottom2[1]['number'] if len(bottom2) > 1 else '-'}</div>
                            </div>
                            <button onclick="copyNum('{bottom2[1]['number'] if len(bottom2) > 1 else ''}', this)" class="text-xs text-slate-400 hover:text-white p-1">📋</button>
                        </div>
                        <div class="p-3 rounded-xl bg-slate-900/50 border border-slate-800 flex justify-between items-center">
                            <div>
                                <span class="text-[10px] text-slate-400">อันดับ 3</span>
                                <div class="font-num text-xl font-bold text-slate-200">{bottom2[2]['number'] if len(bottom2) > 2 else '-'}</div>
                            </div>
                            <button onclick="copyNum('{bottom2[2]['number'] if len(bottom2) > 2 else ''}', this)" class="text-xs text-slate-400 hover:text-white p-1">📋</button>
                        </div>
                    </div>
                </div>

                <!-- การ์ด 3: 2 ตัวบน & 3 ตัวบน (ท้ายรางวัลที่ 1) -->
                <div class="card-surface rounded-2xl p-6 border-t-4 border-cyan-500 space-y-4">
                    <div class="flex justify-between items-center">
                        <h3 class="text-base font-bold text-white flex items-center gap-2">
                            <span>🎯</span> 2 ตัวบน และ 3 ตัวบน
                        </h3>
                        <span class="text-xs text-cyan-400 font-medium">ท้ายรางวัลที่ 1</span>
                    </div>

                    <!-- 2 ตัวบน (Top 3 เรียงแนวนอน สบายตา) -->
                    <div class="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
                        <div class="text-xs font-semibold text-cyan-400 mb-2">เลข 2 ตัวบน เด่น:</div>
                        <div class="grid grid-cols-3 gap-2 text-center">
                            <div class="p-2 rounded-lg bg-cyan-950/40 border border-cyan-800/40">
                                <span class="text-[10px] text-cyan-400 font-bold">#1</span>
                                <div class="font-num text-2xl font-bold text-cyan-300">{top2[0]['number'] if len(top2) > 0 else '-'}</div>
                                <button onclick="copyNum('{top2[0]['number'] if len(top2) > 0 else ''}', this)" class="text-[10px] text-slate-400 hover:text-white mt-1">คัดลอก</button>
                            </div>
                            <div class="p-2 rounded-lg bg-slate-900 border border-slate-800">
                                <span class="text-[10px] text-slate-400">#2</span>
                                <div class="font-num text-2xl font-bold text-slate-200">{top2[1]['number'] if len(top2) > 1 else '-'}</div>
                                <button onclick="copyNum('{top2[1]['number'] if len(top2) > 1 else ''}', this)" class="text-[10px] text-slate-400 hover:text-white mt-1">คัดลอก</button>
                            </div>
                            <div class="p-2 rounded-lg bg-slate-900 border border-slate-800">
                                <span class="text-[10px] text-slate-400">#3</span>
                                <div class="font-num text-2xl font-bold text-slate-200">{top2[2]['number'] if len(top2) > 2 else '-'}</div>
                                <button onclick="copyNum('{top2[2]['number'] if len(top2) > 2 else ''}', this)" class="text-[10px] text-slate-400 hover:text-white mt-1">คัดลอก</button>
                            </div>
                        </div>
                    </div>

                    <!-- 3 ตัวบน (Top 3) -->
                    <div class="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
                        <div class="text-xs font-semibold text-purple-400 mb-2">เลข 3 ตัวบน เด่น:</div>
                        <div class="grid grid-cols-3 gap-2 text-center">
                            <div class="p-2 rounded-lg bg-purple-950/40 border border-purple-800/40">
                                <span class="text-[10px] text-purple-400 font-bold">#1</span>
                                <div class="font-num text-xl font-bold text-purple-300">{top3[0]['number'] if len(top3) > 0 else '-'}</div>
                                <button onclick="copyNum('{top3[0]['number'] if len(top3) > 0 else ''}', this)" class="text-[10px] text-slate-400 hover:text-white mt-1">คัดลอก</button>
                            </div>
                            <div class="p-2 rounded-lg bg-slate-900 border border-slate-800">
                                <span class="text-[10px] text-slate-400">#2</span>
                                <div class="font-num text-xl font-bold text-slate-200">{top3[1]['number'] if len(top3) > 1 else '-'}</div>
                                <button onclick="copyNum('{top3[1]['number'] if len(top3) > 1 else ''}', this)" class="text-[10px] text-slate-400 hover:text-white mt-1">คัดลอก</button>
                            </div>
                            <div class="p-2 rounded-lg bg-slate-900 border border-slate-800">
                                <span class="text-[10px] text-slate-400">#3</span>
                                <div class="font-num text-xl font-bold text-slate-200">{top3[2]['number'] if len(top3) > 2 else '-'}</div>
                                <button onclick="copyNum('{top3[2]['number'] if len(top3) > 2 else ''}', this)" class="text-[10px] text-slate-400 hover:text-white mt-1">คัดลอก</button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- การ์ด 4: เลขหน้า 3 ตัว & เลขท้าย 3 ตัว -->
                <div class="card-surface rounded-2xl p-6 border-t-4 border-indigo-500 space-y-4">
                    <div class="flex justify-between items-center">
                        <h3 class="text-base font-bold text-white flex items-center gap-2">
                            <span>📦</span> เลขหน้า 3 ตัว & เลขท้าย 3 ตัว
                        </h3>
                        <span class="text-xs text-indigo-400 font-medium">หมุนอย่างละ 2 ครั้ง</span>
                    </div>

                    <!-- เลขหน้า 3 ตัว -->
                    <div class="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
                        <div class="text-xs font-semibold text-slate-300 mb-2">เลขหน้า 3 ตัว (อันดับ 1–3):</div>
                        <div class="flex items-center justify-between">
                            <div class="flex space-x-2">
                                {' '.join([f"<span class='font-num text-lg font-bold px-2.5 py-1 rounded-lg bg-slate-800 text-indigo-300'>{x['number']}</span>" for x in front3])}
                            </div>
                            <button onclick="copyNum('{', '.join([x['number'] for x in front3])}', this)" class="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition">📋 คัดลอกทั้งชุด</button>
                        </div>
                    </div>

                    <!-- เลขท้าย 3 ตัว -->
                    <div class="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
                        <div class="text-xs font-semibold text-slate-300 mb-2">เลขท้าย 3 ตัว (อันดับ 1–3):</div>
                        <div class="flex items-center justify-between">
                            <div class="flex space-x-2">
                                {' '.join([f"<span class='font-num text-lg font-bold px-2.5 py-1 rounded-lg bg-slate-800 text-emerald-300'>{x['number']}</span>" for x in last3])}
                            </div>
                            <button onclick="copyNum('{', '.join([x['number'] for x in last3])}', this)" class="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition">📋 คัดลอกทั้งชุด</button>
                        </div>
                    </div>
                </div>

            </div>

        </div>

        <!-- ======================================================== -->
        <!-- TAB 2: เจาะลึกสถิติ (Statistical Tables & Cold Numbers)  -->
        <!-- ======================================================== -->
        <div id="tab-stats" class="tab-content hidden space-y-6">

            <!-- ตารางสถิติ Top 3 ทุกรางวัล -->
            <div class="card-surface rounded-2xl overflow-hidden">
                <div class="p-5 border-b border-slate-800">
                    <h3 class="font-bold text-base text-white">ตารางวิเคราะห์สถิติความถี่รายรางวัล (อันดับ 1–3)</h3>
                    <p class="text-xs text-slate-400 mt-1">แสดงความถี่ตรงวันในสัปดาห์ (วันอาทิตย์), ตรงงวด 1 พ.ย., และสถิติรวม 16 ปี</p>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-xs sm:text-sm">
                        <thead class="bg-slate-900 text-slate-400 uppercase border-b border-slate-800">
                            <tr>
                                <th class="py-2.5 px-4 text-center">อันดับ</th>
                                <th class="py-2.5 px-4">ตัวเลข</th>
                                <th class="py-2.5 px-4 text-center">คะแนนโมเดล</th>
                                <th class="py-2.5 px-4 text-center">ตรงวัน</th>
                                <th class="py-2.5 px-4 text-center">ตรงงวด</th>
                                <th class="py-2.5 px-4 text-center">สถิติรวม</th>
                                <th class="py-2.5 px-4 text-right">การจัดการ</th>
                            </tr>
                        </thead>
                        <tbody>
                            <!-- หมวด 2 ตัวล่าง -->
                            <tr class="bg-slate-900/90 font-bold text-xs text-emerald-400"><td colspan="7" class="py-2 px-4">หมวด: เลขท้าย 2 ตัว (2 ตัวล่าง)</td></tr>
                            {make_table_rows(bottom2, "text-emerald-400")}

                            <!-- หมวด 2 ตัวบน -->
                            <tr class="bg-slate-900/90 font-bold text-xs text-cyan-400"><td colspan="7" class="py-2 px-4">หมวด: 2 ตัวบน (ท้ายรางวัลที่ 1)</td></tr>
                            {make_table_rows(top2, "text-cyan-400")}

                            <!-- หมวด 3 ตัวบน -->
                            <tr class="bg-slate-900/90 font-bold text-xs text-purple-400"><td colspan="7" class="py-2 px-4">หมวด: 3 ตัวบน (ท้ายรางวัลที่ 1)</td></tr>
                            {make_table_rows(top3, "text-purple-300", has_tail=True)}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- กล่องเลขดับ & ความแม่นยำ -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                <!-- เลขดับ (Cold Numbers) -->
                <div class="card-surface rounded-2xl p-5 space-y-3">
                    <h4 class="text-sm font-bold text-white flex items-center gap-2">
                        <span>🧊</span> เลขดับ / ไม่มานานที่สุด (Cold Numbers)
                    </h4>
                    <p class="text-xs text-slate-400">ตัวเลขที่ไม่เคยออกหรือทิ้งช่วงการออกรางวัลยาวนานที่สุดในรอบ 16 ปี</p>
                    
                    <div class="space-y-2 pt-1 text-xs">
                        <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                            <div>
                                <span class="text-slate-400">2 ตัวล่าง ไม่มานานสุด:</span>
                                <span class="font-num text-base font-bold text-sky-400 ml-2">{', '.join([x['number'] for x in cold_numbers.get('bottom2', [])])}</span>
                            </div>
                            <span class="text-[11px] text-slate-500">397 งวด</span>
                        </div>
                        <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                            <div>
                                <span class="text-slate-400">2 ตัวบน ไม่มานานสุด:</span>
                                <span class="font-num text-base font-bold text-sky-400 ml-2">{', '.join([x['number'] for x in cold_numbers.get('top2', [])])}</span>
                            </div>
                            <span class="text-[11px] text-slate-500">397 งวด</span>
                        </div>
                    </div>
                </div>

                <!-- KPI ความแม่นยำ 1 ปี -->
                <div class="card-surface rounded-2xl p-5 space-y-3">
                    <h4 class="text-sm font-bold text-white flex items-center gap-2">
                        <span>🎯</span> ความแม่นยำสะสมกลุ่ม Top 3 (1 ปีย้อนหลัง)
                    </h4>
                    <p class="text-xs text-slate-400">ทดสอบ Walk-Forward บน {hit_rate.get('eval_draws', 24)} งวดล่าสุดโดยไม่รั่วไหลของข้อมูล</p>

                    <div class="space-y-2 pt-1 text-xs">
                        <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                            <span class="text-slate-300">2 ตัวล่าง (เข้า Top 3):</span>
                            <span class="font-mono font-bold text-emerald-400 text-sm">{hit_rate.get('bottom2_hits', 0)}/{hit_rate.get('eval_draws', 24)} ({hit_rate.get('bottom2_pct', 0)}%)</span>
                        </div>
                        <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                            <span class="text-slate-300">2 ตัวบน (เข้า Top 3):</span>
                            <span class="font-mono font-bold text-cyan-400 text-sm">{hit_rate.get('top2_hits', 0)}/{hit_rate.get('eval_draws', 24)} ({hit_rate.get('top2_pct', 0)}%)</span>
                        </div>
                        <div class="text-[11px] text-slate-500 text-right">
                            *เกณฑ์สุ่มเดาปกติทางทฤษฎี (Baseline) = 3.0%
                        </div>
                    </div>
                </div>
            </div>

        </div>

        <!-- ======================================================== -->
        <!-- TAB 3: ตรวจผลย้อนหลัง (Past Draw Comparison)             -->
        <!-- ======================================================== -->
        <div id="tab-past" class="tab-content hidden space-y-6">

            <!-- งวดล่าสุด 16 ต.ค. 69 -->
            <div class="card-surface rounded-2xl p-6 space-y-4">
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-slate-800 pb-4">
                    <div>
                        <h3 class="text-lg font-bold text-white flex items-center gap-2">
                            <span>🔍</span> ผลออกจริง vs ตัวเลขที่โมเดลเก็งไว้
                        </h3>
                        <p class="text-xs text-slate-400 mt-0.5">งวดประจำวันที่ {past_eval.get('date_th', '-')}</p>
                    </div>
                    <span class="text-xs px-2.5 py-1 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">งวดที่ผ่านมา</span>
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                    <div class="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                        <span class="text-xs text-slate-400">รางวัลที่ 1 ออกจริง</span>
                        <div class="font-num text-xl font-bold text-white mt-1">{past_eval.get('first_prize', {}).get('actual', '-')}</div>
                        <div class="text-[11px] text-amber-400/80 mt-1">เก็ง #1: {past_eval.get('first_prize', {}).get('predicted_top1', '-')}</div>
                    </div>
                    <div class="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                        <span class="text-xs text-slate-400">3 ตัวบน ออกจริง</span>
                        <div class="font-num text-xl font-bold text-purple-400 mt-1">{past_eval.get('top3', {}).get('actual', '-')}</div>
                        <div class="text-[11px] text-slate-400 mt-1">อันดับโมเดล: {past_eval.get('top3', {}).get('rank', '-')}</div>
                    </div>
                    <div class="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                        <span class="text-xs text-slate-400">2 ตัวบน ออกจริง</span>
                        <div class="font-num text-xl font-bold text-cyan-400 mt-1">{past_eval.get('top2', {}).get('actual', '-')}</div>
                        <div class="text-[11px] text-slate-400 mt-1">อันดับโมเดล: {past_eval.get('top2', {}).get('rank', '-')}</div>
                    </div>
                    <div class="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                        <span class="text-xs text-slate-400">2 ตัวล่าง ออกจริง</span>
                        <div class="font-num text-xl font-bold text-emerald-400 mt-1">{past_eval.get('bottom2', {}).get('actual', '-')}</div>
                        <div class="text-[11px] text-slate-400 mt-1">อันดับโมเดล: {past_eval.get('bottom2', {}).get('rank', '-')}</div>
                    </div>
                </div>
            </div>

            <!-- ประวัติ 5 งวดย้อนหลัง -->
            <div class="card-surface rounded-2xl overflow-hidden">
                <div class="p-5 border-b border-slate-800">
                    <h4 class="text-sm font-bold text-white">บันทึกความแม่นยำ 5 งวดย้อนหลัง (Walk-Forward Log)</h4>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-xs sm:text-sm">
                        <thead class="bg-slate-900 text-slate-400 uppercase border-b border-slate-800">
                            <tr>
                                <th class="py-2.5 px-4">งวดวันที่</th>
                                <th class="py-2.5 px-4">รางวัลที่ 1 ออกจริง</th>
                                <th class="py-2.5 px-4">2 ตัวบน ออกจริง (อันดับโมเดล)</th>
                                <th class="py-2.5 px-4">2 ตัวล่าง ออกจริง (อันดับโมเดล)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {make_history_rows(history_log)}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>

        <!-- Disclaimer -->
        <section class="p-4 rounded-xl bg-slate-900/40 border border-slate-800 text-[11px] text-slate-500 space-y-1 text-center sm:text-left">
            <p><strong>คำชี้แจง:</strong> การออกสลากกินแบ่งรัฐบาลเป็นการสุ่มอิสระตามกลศาสตร์กายภาพ (โอกาสออก 1% เท่ากันทุกหมายเลข) ข้อมูลชุดนี้จัดทำขึ้นเพื่อการศึกษาทางสถิติย้อนหลังเท่านั้น ไม่สามารถการันตีผลรางวัลได้</p>
        </section>

    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800/80 bg-slate-950 py-5 text-center text-xs text-slate-500">
        <div class="max-w-6xl mx-auto px-4 space-y-1">
            <p>Thai Lottery Statistical Analysis &copy; 2026 | Open Source on GitHub</p>
            <p class="text-[11px]">ข้อมูลจาก <a href="https://github.com/huayreview/thai-lottery-results" target="_blank" class="text-slate-400 hover:text-white underline">huayreview/thai-lottery-results</a></p>
        </div>
    </footer>

    <!-- Tab & Copy Scripts -->
    <script>
        const fullSummaryText = `{summary_text}`;

        function switchTab(tabId) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(btn => {{
                btn.className = "tab-btn flex-1 py-2 text-center font-medium rounded-lg transition text-slate-400 hover:text-white";
            }});
            document.getElementById('tab-' + tabId).classList.remove('hidden');
            const activeBtn = document.getElementById('tab-btn-' + tabId);
            activeBtn.className = "tab-btn flex-1 py-2 text-center font-bold rounded-lg transition bg-amber-500 text-slate-950 shadow-sm";
        }}

        function copyNum(text, btn) {{
            if (!text || text === '-') return;
            navigator.clipboard.writeText(text).then(function() {{
                var orig = btn.innerHTML;
                btn.innerHTML = '✓ คัดลอกแล้ว';
                btn.classList.add('text-emerald-400');
                setTimeout(function() {{
                    btn.innerHTML = orig;
                    btn.classList.remove('text-emerald-400');
                }}, 1500);
            }}).catch(function(err) {{
                console.error('Copy failed: ', err);
            }});
        }}

        function copySummary() {{
            navigator.clipboard.writeText(fullSummaryText).then(function() {{
                const btn = document.getElementById('copy-summary-btn');
                const orig = btn.innerHTML;
                btn.innerHTML = '✓ คัดลอกแล้ว!';
                btn.classList.remove('bg-amber-500', 'text-slate-950');
                btn.classList.add('bg-emerald-500', 'text-white');
                setTimeout(function() {{
                    btn.innerHTML = orig;
                    btn.classList.remove('bg-emerald-500', 'text-white');
                    btn.classList.add('bg-amber-500', 'text-slate-950');
                }}, 2000);
            }});
        }}
    </script>

</body>
</html>
"""
    return html_content

def build():
    print("Building site with distilled, high-readability ProMax UI/UX...")
    raw_df = fetch_or_load_dataset()
    df = prepare_dataframe(raw_df)

    latest_draw_date = df["draw_date"].max()
    target_dt = get_next_draw_date(latest_draw_date)
    target_date_str = target_dt.strftime("%Y-%m-%d")
    target_date_th = format_thai_date(target_dt)

    past_evaluation = evaluate_past_draw(df)
    history_log = get_past_history_log(df, n_draws=5)
    cold_numbers = get_cold_numbers(df, target_date_str)
    hit_rate_1year = get_one_year_hit_rate(df, n_draws=24)

    history = df[df["draw_date"] < target_date_str].copy()
    target_day = target_dt.strftime("%A")
    target_md = target_dt.strftime("%m-%d")

    history_day = history[history["day_name"] == target_day]
    history_sea = history[history["month_day"] == target_md]

    df_bottom2 = calculate_2digit_scores(df, target_date_str, target_col="bottom2").head(3)
    df_top2 = calculate_2digit_scores(df, target_date_str, target_col="top2").head(3)
    
    top2_cands = list(df_top2["number"].head(3))
    df_top3 = calculate_top3_first_prize(history, target_day, target_md, top2_cands, top_k=3)
    df_front3 = score_multivalue_3digit(history["front_three_digits"], history_day["front_three_digits"], history_sea["front_three_digits"], top_k=3)
    df_last3 = score_multivalue_3digit(history["last_three_digits"], history_day["last_three_digits"], history_sea["last_three_digits"], top_k=3)
    df_first_prize = calculate_first_prize_6digit(history, target_day, target_md, df_top3, top_k=3)

    data_payload = {
        "target_date": target_date_str,
        "target_date_th": target_date_th,
        "last_update": f"{latest_draw_date.strftime('%Y-%m-%d')} (คำนวณล่าสุด: {datetime.now().strftime('%Y-%m-%d %H:%M')} ICT)",
        "total_draws": len(history),
        "history_start": history["draw_date"].min().strftime("%Y-%m-%d"),
        "history_end": history["draw_date"].max().strftime("%Y-%m-%d"),
        "past_evaluation": past_evaluation,
        "history_log": history_log,
        "cold_numbers": cold_numbers,
        "hit_rate_1year": hit_rate_1year,
        "first_prize": df_first_prize.to_dict(orient="records"),
        "top3": df_top3.to_dict(orient="records"),
        "top2": df_top2.to_dict(orient="records"),
        "bottom2": df_bottom2.to_dict(orient="records"),
        "front3": df_front3.to_dict(orient="records"),
        "last3": df_last3.to_dict(orient="records"),
    }

    os.makedirs("docs", exist_ok=True)

    with open("predictions.json", "w", encoding="utf-8") as f:
        json.dump(data_payload, f, ensure_ascii=False, indent=2)
    with open(os.path.join("docs", "predictions.json"), "w", encoding="utf-8") as f:
        json.dump(data_payload, f, ensure_ascii=False, indent=2)

    html = generate_html(data_payload)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join("docs", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    export_rows = []
    for r in data_payload["first_prize"]:
        export_rows.append({"category": "รางวัลที่ 1 (6 หลัก)", "number": r["number"], "score": r["composite_score"], "details": r["notes"]})
    for r in data_payload["top3"]:
        export_rows.append({"category": "เลขท้ายรางวัลที่ 1 3 ตัว (3 ตัวบน)", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']}"})
    for r in data_payload["top2"]:
        export_rows.append({"category": "เลขท้ายรางวัลที่ 1 2 ตัว (2 ตัวบน)", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']} แต้ม:{r['digit_sum']} ({r['parity']})"})
    for r in data_payload["front3"]:
        export_rows.append({"category": "รางวัลเลขหน้า 3 ตัว", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']}"})
    for r in data_payload["last3"]:
        export_rows.append({"category": "รางวัลเลขท้าย 3 ตัว", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']}"})
    for r in data_payload["bottom2"]:
        export_rows.append({"category": "รางวัลเลขท้าย 2 ตัว (2 ตัวล่าง)", "number": r["number"], "score": r["composite_score"], "details": f"ตรงวัน:{r['day_freq']} ตรงงวด:{r['seasonal_freq']} รวม:{r['overall_freq']} แต้ม:{r['digit_sum']} ({r['parity']})"})

    df_csv = pd.DataFrame(export_rows)
    df_csv.to_csv("thai_lottery_predictions.csv", index=False, encoding="utf-8-sig")
    df_csv.to_csv(os.path.join("docs", "thai_lottery_predictions.csv"), index=False, encoding="utf-8-sig")

    print("Build complete! Clean UI/UX generated.")

if __name__ == "__main__":
    build()
