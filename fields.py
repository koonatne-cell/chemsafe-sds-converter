# -*- coding: utf-8 -*-
"""
fields.py - รายชื่อฟิลด์ทั้งหมด จัดกลุ่มพร้อมป้ายภาษาไทย
ใช้ร่วมกันทั้งฝั่ง backend (main.py) และส่งไปให้ frontend สร้างฟอร์ม
"""

# ช่อง "จัดทำโดย" / "อนุมัติโดย" แสดงเป็น section แยกต่างหาก (ก่อนขั้นตอนเลือกไฟล์ SDS)
# ไม่ได้ดึงมาจาก SDS และไม่ต้องแปลไทย ผู้ใช้กรอกเอง
SIGNATURE_FIELDS = [
    ("prepared_name", "จัดทำโดย - ชื่อ-สกุล"),
    ("prepared_position", "จัดทำโดย - ตำแหน่ง"),
    ("approved_name", "อนุมัติโดย - ชื่อ-สกุล"),
    ("approved_position", "อนุมัติโดย - ตำแหน่ง"),
]

# สัญลักษณ์ GHS ทั้ง 9 ชนิด (key, ป้ายไทย) เรียงตามตารางมาตรฐาน
# ผู้ใช้ติ๊กเลือกเองในฟอร์ม (ระบบจะติ๊กให้อัตโนมัติเท่าที่ตรวจจับได้จากข้อความ SDS Section 2 ก่อน)
PICTOGRAM_FIELDS = [
    ("explosive", "วัตถุระเบิด"),
    ("flammable", "สารไวไฟ"),
    ("oxidizer", "สารออกซิไดซ์"),
    ("gas_cylinder", "ก๊าซบรรจุภายใต้ความดัน"),
    ("corrosive", "สารกัดกร่อน"),
    ("toxic", "พิษเฉียบพลัน"),
    ("irritant", "ระวัง (สารระคายเคือง)"),
    ("health_hazard", "อันตรายต่อสุขภาพ"),
    ("environment", "อันตรายต่อสิ่งแวดล้อม"),
]

# (key, ป้ายไทย, ต้องแปลไทยไหม)
FIELD_GROUPS = [
    ("ข้อมูลระบุสาร", [
        ("display_name", "ชื่อสารเคมี (แถบเหลืองบนหัวฟอร์ม ตัวใหญ่)", False),
        ("signal_word", "Signal Word (แถบแดงบนหัวฟอร์ม เช่น อันตราย/คำเตือน)", True),
        ("trade_name", "ชื่อสารเคมี / ชื่อการค้า", True),
        ("formula", "สูตรทางเคมี", False),
        ("un", "UN No", False),
        ("cas", "CAS No", False),
        ("usage", "การใช้งาน", True),
    ]),
    ("คุณสมบัติ (Section 9)", [
        ("state", "สถานะ", True), ("color", "สี", True), ("odor", "กลิ่น", True),
        ("boiling", "จุดเดือด", False), ("ph", "pH", False), ("flash", "จุดวาบไฟ", False),
    ]),
    ("อันตราย / ปฏิกิริยา / ดับเพลิง", [
        ("reactivity", "การเกิดปฏิกิริยา (Section 10)", True),
        ("fire", "การดับเพลิง (Section 5)", True),
        ("hz_eye", "อันตรายต่อสุขภาพ - ทางตา (Section 11)", True),
        ("hz_skin", "อันตรายต่อสุขภาพ - ทางผิวหนัง (Section 11)", True),
        ("hz_oral", "อันตรายต่อสุขภาพ - ทางปาก", True),
        ("hz_inhale", "อันตรายต่อสุขภาพ - ทางการหายใจ", True),
    ]),
    ("การปฐมพยาบาล (Section 4)", [
        ("fa_eye", "ทางตา", True), ("fa_oral", "ทางปาก", True),
        ("fa_skin", "ทางผิวหนัง", True), ("fa_inhale", "ทางการหายใจ", True),
    ]),
    ("จัดการ / เก็บรักษา", [
        ("spill", "กรณีหกรั่วไหล (Section 6)", True),
        ("disposal", "การกำจัด (Section 13)", True),
        ("storage", "การเก็บรักษา (Section 7)", True),
    ]),
    ("ดัชนี NFPA (Section 2)", [
        ("nfpa_health", "สุขภาพ (0-4)", False),
        ("nfpa_fire", "ไวไฟ (0-4)", False),
        ("nfpa_react", "ปฏิกิริยา (0-4)", False),
    ]),
]

# ช่องสีขาว (Special Hazard) ในรูปเพชร NFPA ปกติเลือกได้แค่อย่างเดียว (หรือไม่มีเลย) จึงใช้ dropdown
# แทน checkbox/textarea แบบช่องอื่น ระบบเดาให้เบื้องต้นจากสัญลักษณ์ GHS ที่ตรวจเจอ (oxidizer->OXY,
# corrosive->COR) แต่ต้องตรวจสอบเองเสมอ เพราะ SDS ไม่ได้ระบุตรงๆ ว่าเลือกอะไร
NFPA_SPECIAL_OPTIONS = [
    ("", "(ไม่มี)"),
    ("OXY", "OXY - ออกซิไดเซอร์ (Oxidizer)"),
    ("ACID", "ACID - กรด"),
    ("ALK", "ALK - ด่าง (Alkali)"),
    ("COR", "COR - กัดกร่อน (Corrosive)"),
    ("W", "W - ห้ามใช้น้ำ (Use NO water)"),
]

# รายชื่อ key ทั้งหมดที่ควรแปลเป็นไทย (ใช้ตอนกดปุ่ม "แปลเป็นไทย")
TRANSLATABLE_KEYS = [
    key for _, fields in FIELD_GROUPS for key, _, translatable in fields if translatable
]

# รายชื่อ key ทั้งหมด (ตามลำดับ) ใช้ตรวจว่า data ที่ส่งมาครบไหม
ALL_KEYS = ([key for _, fields in FIELD_GROUPS for key, _, _ in fields]
            + [key for key, _ in SIGNATURE_FIELDS]
            + ["nfpa_special"])
