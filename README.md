# Thai Lottery Statistical Analysis & Prediction Package

ชุดโปรแกรมวิเคราะห์สถิติหวยรัฐบาลไทย เชื่อมต่อฐานข้อมูลจริง [huayreview/thai-lottery-results](https://github.com/huayreview/thai-lottery-results) ครอบคลุมการวิเคราะห์ครบทุกประเภทรางวัล พร้อมระบบสร้างเว็บ **GitHub Pages** และอัปเดตผลวิเคราะห์งวดถัดไปให้อัตโนมัติ

🌐 **Live Website (GitHub Pages):** [https://pkfrom.github.io/thai_lottery_analysis/](https://pkfrom.github.io/thai_lottery_analysis/)

---

## ฟีเจอร์หลัก (Features)

* **วิเคราะห์ครบทุกรางวัล**:
  * 🏆 รางวัลที่ 1 (6 หลัก)
  * 🎯 เลขท้ายรางวัลที่ 1 สามตัว (3 ตัวบน)
  * 🎯 เลขท้ายรางวัลที่ 1 สองตัว (2 ตัวบน)
  * 📦 รางวัลเลขหน้า 3 ตัว (หมุน 2 ครั้ง)
  * 📦 รางวัลเลขท้าย 3 ตัว (หมุน 2 ครั้ง)
  * 🎲 รางวัลเลขท้าย 2 ตัว (2 ตัวล่าง)
* **Auto Next-Draw Prediction**: คำนวณหางวดถัดไปจากประวัติล่าสุดโดยอัตโนมัติ
* **GitHub Pages & Actions**: มี Workflow อัปเดตข้อมูลและ Deploy อัตโนมัติทุกวันและทุกงวดหวยออก
* **REST / JSON API Ready**: ส่งออกไฟล์ `predictions.json` สำหรับนำไปต่อยอด

---

## ไฟล์ในโปรเจ็ค

1. [`build_site.py`](build_site.py): สคริปต์หลักสำหรับสร้างเว็บเพจ `index.html`, `docs/`, `predictions.json`
2. [`lottery_prediction_model.py`](lottery_prediction_model.py): โมเดลคำนวณคะแนนถ่วงน้ำหนักและ CLI Engine
3. [`.github/workflows/update_and_deploy.yml`](.github/workflows/update_and_deploy.yml): GitHub Actions ตั้งเวลาอัปเดตอัตโนมัติ
4. [`docs/`](docs/): โฟลเดอร์หน้าเว็บ GitHub Pages (`index.html`, `predictions.json`, `thai_lottery_predictions.csv`)
5. [`lottery_analysis_report.md`](lottery_analysis_report.md): รายงานวิเคราะห์สถิติและข้อจำกัดเชิงความน่าจะเป็น
6. [`requirements.txt`](requirements.txt): รายการไลบรารี (`pandas`, `numpy`)

---

## การติดตั้งและการใช้งาน

### 1. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 2. รันสร้างหน้าเว็บ GitHub Pages (งวดถัดไปอัตโนมัติ)
```bash
python build_site.py
```

### 3. รันโมเดลผ่าน CLI
```bash
# ดึงข้อมูล online ล่าสุดอัตโนมัติ
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
   * **Source**: เลือก **GitHub Actions** (หรือเลือก Deploy from a branch: `main` / `docs`)
3. ระบบจะทำงานและ Deploy เว็บไซต์อัตโนมัติทุกครั้งที่มี Commit หรือถึงรอบเวลากลางคืน/วันหวยออก
