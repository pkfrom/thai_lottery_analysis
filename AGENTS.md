# AGENTS.md — Agent & Developer Guide

เอกสารแนะนำสำหรับ AI Agents และนักพัฒนาสำหรับโปรเจ็ค `thai_lottery_analysis`

---

## 1. ขอบเขตและเป้าหมายของโปรเจ็ค (Scope & Purpose)

โปรเจ็คนี้ใช้สำหรับวิเคราะห์สถิติผลการออกรางวัลสลากกินแบ่งรัฐบาลไทย (ปี 2553–ปัจจุบัน) ด้วยโมเดลคะแนนถ่วงน้ำหนักหลายมิติ (Multi-Factor Weighted Scoring)
และสร้างเว็บไซต์ **GitHub Pages** อัปเดตผลงวดถัดไปพร้อมเปรียบเทียบผลจริงงวดล่าสุดโดยอัตโนมัติ

---

## 2. โครงสร้างไฟล์หลัก (Repository Layout)

```
thai_lottery_analysis/
├── .github/workflows/
│   └── update_and_deploy.yml   # CI/CD ตั้งเวลารันและ Deploy Pages
├── data/
│   └── thai-lottery-results.csv # แคชข้อมูลผลหวยย้อนหลัง
├── docs/                       # ไฟล์ Static Web สำหรับ GitHub Pages
│   ├── index.html
│   ├── predictions.json
│   └── thai_lottery_predictions.csv
├── build_site.py               # สคริปต์ประมวลผลและสร้างเว็บ/JSON/CSV
├── lottery_prediction_model.py # Core model engine & CLI
├── index.html                  # Root web page mirror
├── predictions.json            # ผลการทำนายและสถิติรูปแบบ JSON
├── thai_lottery_predictions.csv# ผลสรุปตัวเลขรูปแบบ CSV
├── requirements.txt            # Python dependencies (pandas, numpy)
├── README.md                   # เอกสารผู้ใช้งาน
└── AGENTS.md                   # คู่มือสำหรับ Agent (ไฟล์นี้)
```

---

## 3. กฎและข้อกำหนดสำคัญ (Critical Invariants)

1. **แสดงผลเฉพาะอันดับ 1–3 (Top 1–3 Only)**:
   * ทุกประเภทรางวัล (รางวัลที่ 1, 3 ตัวบน, 2 ตัวบน, เลขหน้า 3 ตัว, เลขท้าย 3 ตัว, 2 ตัวล่าง) ให้แสดงผลและ Export เฉพาะ **อันดับ 1 ถึง 3 เท่านั้น**
2. **ห้ามเกิด Data Leakage**:
   * การคำนวณสถิติเพื่อทำนายหรือประเมินงวด `target_date` ใดๆ ต้องกรองเฉพาะข้อมูล `draw_date < target_date` โดยเด็ดขาด
3. **Resilience & Offline Fallback**:
   * การดึงข้อมูลออนไลน์จาก GitHub Raw (`huayreview/thai-lottery-results`) ต้องมี Timeout และถ้าเชื่อมต่อไม่ได้ ต้องสลับมาใช้ Local Cache ใน `data/thai-lottery-results.csv` เสมอ
4. **ความสอดคล้องของ Web Artifacts**:
   * เมื่อรัน `build_site.py` ต้องอัปเดตทั้งในรูท (`index.html`, `predictions.json`, `thai_lottery_predictions.csv`) และใน `docs/` ให้ตรงกันเสมอ

---

## 4. คำสั่งสำคัญในการทำงาน (Command Reference)

### สร้างหน้าเว็บและข้อมูลผลวิเคราะห์ล่าสุด (Next Draw + Past Evaluation)
```bash
python build_site.py
```

### รันโมเดลผ่าน CLI (แสดง Top 1–3)
```bash
python lottery_prediction_model.py
```

### รัน Walk-Forward Backtesting ทดสอบความแม่นยำ 30 งวดย้อนหลัง
```bash
python lottery_prediction_model.py --backtest
```

---

## 5. ประเภทรางวัลที่ประมวลผล (Prize Taxonomy)

| รางวัล | คอลัมน์ที่ใช้วิเคราะห์ | จำนวนตัวเลขที่แสดง |
|---|---|---|
| รางวัลที่ 1 (6 หลัก) | `first_prize` (สังเคราะห์ 3 ตัวหน้า + 3 ตัวท้าย) | อันดับ 1–3 |
| เลขท้ายรางวัลที่ 1 3 ตัว (3 ตัวบน) | `first_prize[-3:]` รวมกับ 2 ตัวบนเด่น | อันดับ 1–3 |
| เลขท้ายรางวัลที่ 1 2 ตัว (2 ตัวบน) | `first_prize[-2:]` | อันดับ 1–3 |
| รางวัลเลขหน้า 3 ตัว | `front_three_digits` (หมุน 2 ครั้ง) | อันดับ 1–3 |
| รางวัลเลขท้าย 3 ตัว | `last_three_digits` (หมุน 2 ครั้ง) | อันดับ 1–3 |
| รางวัลเลขท้าย 2 ตัว (2 ตัวล่าง) | `last_two_digits` | อันดับ 1–3 |
