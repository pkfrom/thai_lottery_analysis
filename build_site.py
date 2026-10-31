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

def generate_html(data):
    target_date_str = data["target_date"]
    target_date_th = data["target_date_th"]
    last_update = data["last_update"]
    total_draws = data["total_draws"]
    history_start = data["history_start"]
    history_end = data["history_end"]

    fp_top = data["first_prize"][0] if data["first_prize"] else {}
    top3_top = data["top3"][0] if data["top3"] else {}
    top2_top = data["top2"][0] if data["top2"] else {}
    bottom2_top = data["bottom2"][0] if data["bottom2"] else {}

    def make_rows_fp(items):
        rows = ""
        for idx, item in enumerate(items, 1):
            rows += f"""
            <tr class="border-b border-slate-700/50 hover:bg-slate-800/40 transition">
                <td class="py-3 px-4 text-center font-bold text-slate-400">{idx}</td>
                <td class="py-3 px-4 font-mono font-bold text-xl text-amber-400 tracking-wider">{item['number']}</td>
                <td class="py-3 px-4 text-emerald-400 font-semibold">{item['composite_score']}</td>
                <td class="py-3 px-4 text-slate-300 font-mono text-sm">{item['notes']}</td>
            </tr>
            """
        return rows

    def make_rows_3digit(items):
        rows = ""
        for idx, item in enumerate(items, 1):
            tail_badge = f"<span class='ml-2 px-2 py-0.5 text-xs rounded bg-purple-900/60 text-purple-300 border border-purple-700/50'>ชน 2 ตัวบน {item.get('tail_2digit','')}</span>" if item.get('tail_2digit') else ""
            rows += f"""
            <tr class="border-b border-slate-700/50 hover:bg-slate-800/40 transition">
                <td class="py-3 px-4 text-center font-bold text-slate-400">{idx}</td>
                <td class="py-3 px-4 font-mono font-bold text-xl text-amber-300">{item['number']}{tail_badge}</td>
                <td class="py-3 px-4 text-emerald-400 font-semibold">{item['composite_score']}</td>
                <td class="py-3 px-4 text-slate-300 text-center">{item['day_freq']} ครั้ง</td>
                <td class="py-3 px-4 text-slate-300 text-center">{item['seasonal_freq']} ครั้ง</td>
                <td class="py-3 px-4 text-slate-300 text-center">{item['overall_freq']} ครั้ง</td>
            </tr>
            """
        return rows

    def make_rows_2digit(items):
        rows = ""
        for idx, item in enumerate(items, 1):
            rows += f"""
            <tr class="border-b border-slate-700/50 hover:bg-slate-800/40 transition">
                <td class="py-3 px-4 text-center font-bold text-slate-400">{idx}</td>
                <td class="py-3 px-4 font-mono font-bold text-2xl text-cyan-400 tracking-wider">{item['number']}</td>
                <td class="py-3 px-4 text-emerald-400 font-semibold">{item['composite_score']}</td>
                <td class="py-3 px-4 text-slate-300 text-center">{item['day_freq']} ครั้ง</td>
                <td class="py-3 px-4 text-slate-300 text-center">{item['seasonal_freq']} ครั้ง</td>
                <td class="py-3 px-4 text-slate-300 text-center">{item['overall_freq']} ครั้ง</td>
                <td class="py-3 px-4 text-slate-400 text-center">{item['digit_sum']} แต้ม</td>
                <td class="py-3 px-4 text-slate-400 text-center"><span class="px-2 py-0.5 rounded text-xs bg-slate-800 border border-slate-700">{item['parity']}</span></td>
            </tr>
            """
        return rows

    html_content = f"""<!DOCTYPE html>
<html lang="th" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ผลวิเคราะห์สถิติหวยรัฐบาลไทย - งวด {target_date_th}</title>
    <meta name="description" content="ชุดวิเคราะห์สถิติผลสลากกินแบ่งรัฐบาลไทยย้อนหลัง พร้อมแบบจำลองคะแนนถ่วงน้ำหนักหลายมิติและระบบอัปเดตอัตโนมัติ">
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Sarabun:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Sarabun', sans-serif;
            background-color: #0b0f19;
            color: #f1f5f9;
        }}
        .font-num {{
            font-family: 'Chakra Petch', monospace;
        }}
        .glow-card {{
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(148, 163, 184, 0.15);
            backdrop-filter: blur(12px);
        }}
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Top Navigation -->
    <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 py-4 flex flex-wrap justify-between items-center gap-4">
            <div class="flex items-center space-x-3">
                <span class="text-2xl">🎰</span>
                <div>
                    <h1 class="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                        สถิติหวยรัฐบาลไทย
                        <span class="text-xs font-normal px-2.5 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800">Auto-Update</span>
                    </h1>
                    <p class="text-xs text-slate-400">โมเดลวิเคราะห์ความน่าจะเป็นเชิงประจักษ์ 16+ ปี</p>
                </div>
            </div>
            <div class="flex items-center space-x-3 text-xs">
                <a href="https://github.com/pkfrom/thai_lottery_analysis" target="_blank" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center gap-1.5">
                    <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
                    GitHub Repo
                </a>
                <a href="predictions.json" target="_blank" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition">
                    JSON API
                </a>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl mx-auto px-4 py-8 flex-grow space-y-8">

        <!-- Banner งวดถัดไป -->
        <section class="glow-card rounded-2xl p-6 sm:p-8 relative overflow-hidden">
            <div class="absolute -right-10 -bottom-10 w-64 h-64 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
                <div>
                    <span class="text-xs uppercase tracking-widest font-bold text-amber-400 bg-amber-950/60 px-3 py-1 rounded-md border border-amber-800/60">
                        วิเคราะห์ผลสถิติงวดถัดไป
                    </span>
                    <h2 class="text-3xl sm:text-4xl font-extrabold text-white mt-3 font-num tracking-tight">
                        {target_date_th}
                    </h2>
                    <p class="text-slate-400 text-sm mt-2">
                        ประมวลผลจากข้อมูลสลากกินแบ่งรัฐบาลไทยย้อนหลังทั้งหมด <strong class="text-slate-200">{total_draws} งวด</strong> ({history_start} ถึง {history_end})
                    </p>
                </div>
                <div class="text-right flex md:flex-col items-center md:items-end justify-between border-t md:border-t-0 border-slate-800 pt-4 md:pt-0">
                    <span class="text-xs text-slate-400">อัปเดตข้อมูลล่าสุด</span>
                    <span class="text-sm font-mono text-emerald-400 font-semibold">{last_update}</span>
                </div>
            </div>
        </section>

        <!-- Highlight Grid -->
        <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <!-- ไฮไลท์ รางวัลที่ 1 -->
            <div class="glow-card rounded-xl p-5 border-l-4 border-amber-500">
                <span class="text-xs font-semibold text-slate-400">รางวัลที่ 1 (เด่นอันดับ 1)</span>
                <div class="text-3xl font-bold font-num text-amber-400 mt-2 tracking-wider">
                    {fp_top.get('number', '-')}
                </div>
                <div class="text-xs text-slate-400 mt-2">
                    {fp_top.get('notes', '-')}
                </div>
            </div>

            <!-- ไฮไลท์ 3 ตัวบน -->
            <div class="glow-card rounded-xl p-5 border-l-4 border-purple-500">
                <span class="text-xs font-semibold text-slate-400">3 ตัวบน (ท้ายรางวัลที่ 1)</span>
                <div class="text-3xl font-bold font-num text-purple-400 mt-2 tracking-wider">
                    {top3_top.get('number', '-')}
                </div>
                <div class="text-xs text-slate-400 mt-2">
                    คะแนน {top3_top.get('composite_score', '-')} | ตรงวัน {top3_top.get('day_freq', 0)} ครั้ง
                </div>
            </div>

            <!-- ไฮไลท์ 2 ตัวบน -->
            <div class="glow-card rounded-xl p-5 border-l-4 border-cyan-500">
                <span class="text-xs font-semibold text-slate-400">2 ตัวบน (ท้ายรางวัลที่ 1)</span>
                <div class="text-3xl font-bold font-num text-cyan-400 mt-2 tracking-wider">
                    {top2_top.get('number', '-')}
                </div>
                <div class="text-xs text-slate-400 mt-2">
                    คะแนน {top2_top.get('composite_score', '-')} | ตรงวัน {top2_top.get('day_freq', 0)} ครั้ง
                </div>
            </div>

            <!-- ไฮไลท์ 2 ตัวล่าง -->
            <div class="glow-card rounded-xl p-5 border-l-4 border-emerald-500">
                <span class="text-xs font-semibold text-slate-400">เลขท้าย 2 ตัว (2 ตัวล่าง)</span>
                <div class="text-3xl font-bold font-num text-emerald-400 mt-2 tracking-wider">
                    {bottom2_top.get('number', '-')}
                </div>
                <div class="text-xs text-slate-400 mt-2">
                    คะแนน {bottom2_top.get('composite_score', '-')} | สถิติรวม {bottom2_top.get('overall_freq', 0)} ครั้ง
                </div>
            </div>
        </section>

        <!-- ตารางรายละเอียด -->
        <div class="space-y-8">

            <!-- รางวัลที่ 1 (6 หลัก) -->
            <section class="glow-card rounded-xl overflow-hidden">
                <div class="p-5 border-b border-slate-800 flex justify-between items-center">
                    <div>
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <span>🏆</span> รางวัลที่ 1 (ชุดตัวเลข 6 หลักเด่น)
                        </h3>
                        <p class="text-xs text-slate-400 mt-0.5">สังเคราะห์จากความถี่ตามหลัก + 3 ตัวหน้าเด่น + 3 ตัวท้ายเด่น</p>
                    </div>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-sm">
                        <thead class="bg-slate-900/60 text-slate-400 text-xs uppercase border-b border-slate-800">
                            <tr>
                                <th class="py-3 px-4 text-center">อันดับ</th>
                                <th class="py-3 px-4">หมายเลข 6 หลัก</th>
                                <th class="py-3 px-4">คะแนนโมเดล</th>
                                <th class="py-3 px-4">องค์ประกอบ (หน้า + ท้าย)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {make_rows_fp(data['first_prize'])}
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- เลข 3 ตัวบน และ 2 ตัวบน -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <!-- 3 ตัวบน -->
                <section class="glow-card rounded-xl overflow-hidden">
                    <div class="p-5 border-b border-slate-800">
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <span>🎯</span> เลขท้ายรางวัลที่ 1 สามตัว (3 ตัวบน)
                        </h3>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse text-sm">
                            <thead class="bg-slate-900/60 text-slate-400 text-xs uppercase border-b border-slate-800">
                                <tr>
                                    <th class="py-3 px-4 text-center">อันดับ</th>
                                    <th class="py-3 px-4">ตัวเลข</th>
                                    <th class="py-3 px-4">คะแนน</th>
                                    <th class="py-3 px-4 text-center">ตรงวัน</th>
                                    <th class="py-3 px-4 text-center">ตรงงวด</th>
                                    <th class="py-3 px-4 text-center">รวม</th>
                                </tr>
                            </thead>
                            <tbody>
                                {make_rows_3digit(data['top3'])}
                            </tbody>
                        </table>
                    </div>
                </section>

                <!-- 2 ตัวบน -->
                <section class="glow-card rounded-xl overflow-hidden">
                    <div class="p-5 border-b border-slate-800">
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <span>🎯</span> เลขท้ายรางวัลที่ 1 สองตัว (2 ตัวบน)
                        </h3>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse text-sm">
                            <thead class="bg-slate-900/60 text-slate-400 text-xs uppercase border-b border-slate-800">
                                <tr>
                                    <th class="py-3 px-4 text-center">อันดับ</th>
                                    <th class="py-3 px-4">ตัวเลข</th>
                                    <th class="py-3 px-4">คะแนน</th>
                                    <th class="py-3 px-4 text-center">ตรงวัน</th>
                                    <th class="py-3 px-4 text-center">ตรงงวด</th>
                                    <th class="py-3 px-4 text-center">รวม</th>
                                    <th class="py-3 px-4 text-center">แต้ม</th>
                                    <th class="py-3 px-4 text-center">คู่/คี่</th>
                                </tr>
                            </thead>
                            <tbody>
                                {make_rows_2digit(data['top2'])}
                            </tbody>
                        </table>
                    </div>
                </section>
            </div>

            <!-- เลข 2 ตัวล่าง -->
            <section class="glow-card rounded-xl overflow-hidden">
                <div class="p-5 border-b border-slate-800">
                    <h3 class="font-bold text-lg text-white flex items-center gap-2">
                        <span>🎲</span> เลขท้าย 2 ตัว (2 ตัวล่าง)
                    </h3>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-sm">
                        <thead class="bg-slate-900/60 text-slate-400 text-xs uppercase border-b border-slate-800">
                            <tr>
                                <th class="py-3 px-4 text-center">อันดับ</th>
                                <th class="py-3 px-4">ตัวเลข</th>
                                <th class="py-3 px-4">คะแนน</th>
                                <th class="py-3 px-4 text-center">ตรงวัน</th>
                                <th class="py-3 px-4 text-center">ตรงงวด</th>
                                <th class="py-3 px-4 text-center">สถิติรวม</th>
                                <th class="py-3 px-4 text-center">แต้ม</th>
                                <th class="py-3 px-4 text-center">คู่/คี่</th>
                            </tr>
                        </thead>
                        <tbody>
                            {make_rows_2digit(data['bottom2'])}
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- รางวัล 3 ตัว (หน้า/ท้าย) -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <!-- เลขหน้า 3 ตัว -->
                <section class="glow-card rounded-xl overflow-hidden">
                    <div class="p-5 border-b border-slate-800">
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <span>📦</span> รางวัลเลขหน้า 3 ตัว (หมุน 2 ครั้ง)
                        </h3>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse text-sm">
                            <thead class="bg-slate-900/60 text-slate-400 text-xs uppercase border-b border-slate-800">
                                <tr>
                                    <th class="py-3 px-4 text-center">อันดับ</th>
                                    <th class="py-3 px-4">ตัวเลข</th>
                                    <th class="py-3 px-4">คะแนน</th>
                                    <th class="py-3 px-4 text-center">ตรงวัน</th>
                                    <th class="py-3 px-4 text-center">ตรงงวด</th>
                                    <th class="py-3 px-4 text-center">รวม</th>
                                </tr>
                            </thead>
                            <tbody>
                                {make_rows_3digit(data['front3'])}
                            </tbody>
                        </table>
                    </div>
                </section>

                <!-- เลขท้าย 3 ตัว -->
                <section class="glow-card rounded-xl overflow-hidden">
                    <div class="p-5 border-b border-slate-800">
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <span>📦</span> รางวัลเลขท้าย 3 ตัว (หมุน 2 ครั้ง)
                        </h3>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse text-sm">
                            <thead class="bg-slate-900/60 text-slate-400 text-xs uppercase border-b border-slate-800">
                                <tr>
                                    <th class="py-3 px-4 text-center">อันดับ</th>
                                    <th class="py-3 px-4">ตัวเลข</th>
                                    <th class="py-3 px-4">คะแนน</th>
                                    <th class="py-3 px-4 text-center">ตรงวัน</th>
                                    <th class="py-3 px-4 text-center">ตรงงวด</th>
                                    <th class="py-3 px-4 text-center">รวม</th>
                                </tr>
                            </thead>
                            <tbody>
                                {make_rows_3digit(data['last3'])}
                            </tbody>
                        </table>
                    </div>
                </section>
            </div>

        </div>

        <!-- ข้อจำกัดเชิงสถิติ (Disclaimer) -->
        <section class="p-5 rounded-xl bg-slate-900/50 border border-slate-800 text-xs text-slate-400 space-y-2">
            <h4 class="font-bold text-slate-300 text-sm flex items-center gap-1.5">
                <span>⚠️</span> ข้อชี้แจงทางสถิติและความน่าจะเป็น (Statistical Disclaimer)
            </h4>
            <p>
                1. <strong>หลักการสุ่มอิสระ (Independent Trials):</strong> การออกรางวัลสลากกินแบ่งรัฐบาลแต่ละงวดเป็นอิสระต่อกันโดยสมบูรณ์ตามหลักกลศาสตร์กายภาพ ตัวเลข 00–99 ทุกตัวมีโอกาสออกเท่ากัน 1% เสมอ
            </p>
            <p>
                2. <strong>วัตถุประสงค์:</strong> ระบบนี้จัดทำขึ้นเพื่อการวิเคราะห์โครงสร้างข้อมูลในอดีต (Empirical Exploratory Analysis) และเพื่อการศึกษาทางสถิติเท่านั้น ไม่สามารถการันตีผลลัพธ์ในอนาคตได้
            </p>
        </section>

    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800 bg-slate-950/80 py-6 text-center text-xs text-slate-500">
        <div class="max-w-7xl mx-auto px-4 space-y-2">
            <p>Thai Lottery Statistical Analysis Engine &copy; 2026 | Open Source on GitHub</p>
            <p>ขับเคลื่อนด้วยชุดข้อมูล <a href="https://github.com/huayreview/thai-lottery-results" target="_blank" class="text-slate-400 hover:text-white underline">huayreview/thai-lottery-results</a></p>
        </div>
    </footer>

</body>
</html>
"""
    return html_content

def build():
    print("Building site and generating next draw predictions...")
    raw_df = fetch_or_load_dataset()
    df = prepare_dataframe(raw_df)

    latest_draw_date = df["draw_date"].max()
    target_dt = get_next_draw_date(latest_draw_date)
    target_date_str = target_dt.strftime("%Y-%m-%d")
    target_date_th = format_thai_date(target_dt)

    print(f"Latest record in dataset: {latest_draw_date.strftime('%Y-%m-%d')}")
    print(f"Next Target Draw: {target_date_str} ({target_date_th})")

    history = df[df["draw_date"] < target_date_str].copy()
    target_day = target_dt.strftime("%A")
    target_md = target_dt.strftime("%m-%d")

    history_day = history[history["day_name"] == target_day]
    history_sea = history[history["month_day"] == target_md]

    # Calculate predictions
    df_bottom2 = calculate_2digit_scores(df, target_date_str, target_col="bottom2")
    df_top2 = calculate_2digit_scores(df, target_date_str, target_col="top2")
    
    top2_cands = list(df_top2["number"].head(5))
    df_top3 = calculate_top3_first_prize(history, target_day, target_md, top2_cands, top_k=10)
    df_front3 = score_multivalue_3digit(history["front_three_digits"], history_day["front_three_digits"], history_sea["front_three_digits"], top_k=10)
    df_last3 = score_multivalue_3digit(history["last_three_digits"], history_day["last_three_digits"], history_sea["last_three_digits"], top_k=10)
    df_first_prize = calculate_first_prize_6digit(history, target_day, target_md, df_top3, top_k=10)

    data_payload = {
        "target_date": target_date_str,
        "target_date_th": target_date_th,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC+7"),
        "total_draws": len(history),
        "history_start": history["draw_date"].min().strftime("%Y-%m-%d"),
        "history_end": history["draw_date"].max().strftime("%Y-%m-%d"),
        "first_prize": df_first_prize.to_dict(orient="records"),
        "top3": df_top3.to_dict(orient="records"),
        "top2": df_top2.head(10).to_dict(orient="records"),
        "bottom2": df_bottom2.head(10).to_dict(orient="records"),
        "front3": df_front3.to_dict(orient="records"),
        "last3": df_last3.to_dict(orient="records"),
    }

    # Ensure output directories
    os.makedirs("docs", exist_ok=True)

    # 1. Save JSON
    with open("predictions.json", "w", encoding="utf-8") as f:
        json.dump(data_payload, f, ensure_ascii=False, indent=2)
    with open(os.path.join("docs", "predictions.json"), "w", encoding="utf-8") as f:
        json.dump(data_payload, f, ensure_ascii=False, indent=2)

    # 2. Save HTML
    html = generate_html(data_payload)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join("docs", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # 3. Save CSV
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

    print("Build complete! Generated:")
    print(" - index.html & docs/index.html")
    print(" - predictions.json & docs/predictions.json")
    print(" - thai_lottery_predictions.csv & docs/thai_lottery_predictions.csv")

if __name__ == "__main__":
    build()
