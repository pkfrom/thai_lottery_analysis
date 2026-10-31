# Thai Lottery Statistical Analysis & Prediction Package

ชุดโปรแกรมวิเคราะห์สถิติหวยรัฐบาลไทย เชื่อมต่อฐานข้อมูลจริง [huayreview/thai-lottery-results](https://github.com/huayreview/thai-lottery-results) ครอบคลุมการวิเคราะห์ครบทุกประเภทรางวัล คัดเลือกเฉพาะ **อันดับ 1–3** พร้อมระบบ **GitHub Pages** อัปเดตผลงวดถัดไปและเปรียบเทียบผลจริงงวดล่าสุดให้อัตโนมัติ

🌐 **Live Website (GitHub Pages):** [https://pkfrom.github.io/thai_lottery_analysis/](https://pkfrom.github.io/thai_lottery_analysis/)

---

## ฟีเจอร์หลัก (Features)

* **คัดกรองเฉพาะอันดับ 1–3 (Top 3 Focus)**: แสดงเฉพาะตัวเลขที่มีคะแนนสถิติสูงสุด 3 อันดับแรกในแต่ละรางวัล
* **ปุ่มคัดลอกเลขทันที (1-Click Copy)**: สะดวกสำหรับผู้ใช้มือถือ คัดลอกตัวเลขเข้าคลิปบอร์ดได้ในคลิกเดียว
* **รองรับการแชร์โซเชียล (Social Sharing / Open Graph)**: มีพรีวิวเมื่อแชร์ลิงก์ลง LINE และ Facebook พร้อมไอคอน Favicon
* **สถิติเลขดับ / ไม่มานานสุด (Cold Numbers)**: สรุปเลข 2 ตัวบนและ 2 ตัวล่างที่สถิติในอดีตไม่เคยออกหรือทิ้งช่วงนานที่สุด
* **Scoreboard ความแม่นยำ 1 ปี (Walk-Forward KPI)**: แสดงอัตรา Hit Rate ของกลุ่ม Top 3 ในรอบ 24 งวดล่าสุดเพื่อความโปร่งใส
* **ตรวจผลย้อนหลัง (Past Draw Verification)**: เปรียบเทียบผลวิเคราะห์กับผลรางวัลที่ออกจริงในงวดล่าสุด
* **วิเคราะห์ครบทุกรางวัล**:
  * 🏆 รางวัลที่ 1 (6 หลัก)
  * 🎯 เลขท้ายรางวัลที่ 1 สามตัว (3 ตัวบน)
  * 🎯 เลขท้ายรางวัลที่ 1 สองตัว (2 ตัวบน)
  * 📦 รางวัลเลขหน้า 3 ตัว (หมุน 2 ครั้ง)
  * 📦 รางวัลเลขท้าย 3 ตัว (หมุน 2 ครั้ง)
  * 🎲 รางวัลเลขท้าย 2 ตัว (2 ตัวล่าง)
* **Auto Next-Draw Prediction**: คำนวณหางวดถัดไปจากประวัติล่าสุดโดยอัตโนมัติ
* **Clean CI / GitHub Actions**: มี Workflow อัปเดตข้อมูลและ Deploy อัตโนมัติ โดยจะ Commit เฉพาะเมื่องวดหวยมีผลใหม่เท่านั้น

---

## ไฟล์ในโปรเจ็ค

1. [`build_site.py`](build_site.py): สคริปต์หลักสำหรับสร้างเว็บเพจ `index.html`, `docs/`, `predictions.json`
2. [`lottery_prediction_model.py`](lottery_prediction_model.py): โมเดลคำนวณคะแนนถ่วงน้ำหนักและ CLI Engine
3. [`.github/workflows/update_and_deploy.yml`](.github/workflows/update_and_deploy.yml): GitHub Actions ตั้งเวลาอัปเดตอัตโนมัติ
4. [`AGENTS.md`](AGENTS.md): คู่มือและข้อกำหนดทางเทคนิคสำหรับ AI Agents และนักพัฒนา
5. [`docs/`](docs/): โฟลเดอร์หน้าเว็บ GitHub Pages (`index.html`, `predictions.json`, `thai_lottery_predictions.csv`)
6. [`lottery_analysis_report.md`](lottery_analysis_report.md): รายงานวิเคราะห์สถิติและข้อจำกัดเชิงความน่าจะเป็น
7. [`requirements.txt`](requirements.txt): รายการไลบรารี (`pandas`, `numpy`)

---

## การติดตั้งและการใช้งาน

### 1. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 2. รันสร้างหน้าเว็บ GitHub Pages (งวดถัดไปอัตโนมัติ อันดับ 1–3)
```bash
python build_site.py
```

### 3. รันโมเดลผ่าน CLI
```bash
# ดึงข้อมูล online ล่าสุดอัตโนมัติ แสดงอันดับ 1-3
python lottery_prediction_model.py

# กำหนดงวดเป้าหมาย
python lottery_prediction_model.py --target-date 2026-11-01

# ทดสอบโมเดลย้อนหลัง 30 งวด
python lottery_prediction_model.py --backtest
```

---

## การตั้งค่า GitHub Pages

1. ไปที่แท็บ **Settings** > **Pages** ใน GitHub Repository
2. ในส่วน **Build and deployment**:
   * **Source**: เลือก **GitHub Actions**
3. ระบบจะทำงานและ Deploy เว็บไซต์อัตโนมัติทุกครั้งที่มี Commit หรือถึงรอบเวลากลางคืน/วันหวยออก
