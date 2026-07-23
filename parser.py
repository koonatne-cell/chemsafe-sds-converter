# -*- coding: utf-8 -*-
"""
parser.py - ดึงข้อมูลเฉพาะฟิลด์จากไฟล์ SDS (Safety Data Sheet, เป็น PDF ที่มีตัวอักษรอ่านได้)

SDS แต่ละยี่ห้อ/ผู้ผลิตใช้คำที่ต่างกันสำหรับหัวข้อเดียวกัน (เช่น "Trade name:" vs "Product name:")
ถึงจะเรียงตาม section เดียวกันตามมาตรฐาน GHS ก็ตาม ฟิลด์แต่ละอันเลยลองจับหลาย pattern
เรียงจากที่เจอบ่อยสุดไปหายาก ใช้ pattern แรกที่เจอ ถ้าไม่เจอเลยคืนค่า default ("-")
"""
import re
import pdfplumber


def read_all_text(pdf_path):
    """อ่านตัวอักษรทั้งหมดจากทุกหน้าของ PDF รวมเป็นก้อนเดียว"""
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)



# วลีที่แปลว่า "ไม่มีข้อมูล" ในภาษาของ SDS ถ้าค่าที่ดึงได้ขึ้นต้นด้วยวลีพวกนี้ (ไม่สนตัวพิมพ์เล็ก-ใหญ่)
# ให้ถือว่าไม่มีข้อมูลจริงๆ คืนค่า "-" แทน ไม่ใช่ก็อปข้อความ "No data available" มาใส่ในฟอร์มตรงๆ
# (คำไทยเลือกเฉพาะวลีที่ชัดเจนว่า "ไม่มีข้อมูล" เท่านั้น ไม่ใช่ "ไม่มี" เฉยๆ เพราะ "ไม่มี" เดี่ยวๆ
# อาจเป็นคำตอบจริงที่มีความหมาย เช่น "กลิ่น: ไม่มี" หมายถึงไม่มีกลิ่น ไม่ใช่ไม่มีข้อมูล)
_NO_DATA_PREFIXES = (
    "no data available", "no data", "not applicable", "not determined",
    "not established", "no special", "not available",
    "void", "n/a", "na", "none",
    "ไม่มีข้อมูล", "ไม่พบข้อมูล", "ไม่มีข้อกำหนดพิเศษ", "ไม่ระบุ", "ไม่ได้กำหนด", "ไม่เกี่ยวข้อง",
)


def _clean(val):
    """
    รวมช่องว่าง/ขึ้นบรรทัดใหม่ภายในค่าให้เหลือแค่ช่องว่างเดียว (กันรอยหยักจากการ wrap หลายบรรทัด/ย่อหน้า)
    แล้วกรองค่าที่บอกว่า 'ไม่มีข้อมูล' (No data available, Not applicable, ฯลฯ) คืน None ถ้าใช้ไม่ได้
    """
    val = re.sub(r"\s+", " ", val).strip()
    low = val.lower().rstrip(".")
    if low in ("", "-"):
        return None
    if any(low.startswith(p) for p in _NO_DATA_PREFIXES):
        return None
    return val


def grab(text, patterns, default="-"):
    """
    หาข้อความตาม pattern (regex) หนึ่งอันหรือหลายอัน (list) ลองทีละอันตามลำดับ
    คืนค่าที่เจอครั้งแรก ถ้าไม่เจอเลยคืนค่า default
    """
    if isinstance(patterns, str):
        patterns = [patterns]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            val = _clean(m.group(1))
            if val is not None:
                return val
    return default


# ขอบเขตที่ควร "หยุดจับ" ค่าไว้ ใช้สร้าง pattern แบบมาตรฐานผ่าน line()/block() ด้านล่าง
# LINE: หยุดที่ช่องว่างยาว 2 ตัวขึ้นไป (มักหมายถึงคอลัมน์ถัดไปในตาราง เช่น "Product AT USE DILUTION")
#       หรือขึ้นบรรทัดใหม่ หรือจบข้อความ - ใช้กับค่าสั้นๆ บรรทัดเดียว (เช่น pH, สี, กลิ่น)
# BLOCK: หยุดที่บรรทัดว่าง, บรรทัดที่ขึ้นต้นด้วยสัญลักษณ์บูลเล็ต (· • เป็นหัวข้อย่อยใหม่ พบบ่อยมากใน SDS
#        หลายฉบับที่แต่ละหัวข้อมีแค่บรรทัดเดียวไม่มีบรรทัดว่างคั่น), บรรทัดที่ดูเหมือนหัวข้อใหม่ (ขึ้นต้นด้วย
#        ตัวใหญ่ภาษาอังกฤษ หรือตัวอักษรไทย แล้วตามด้วย ":") หรือจบข้อความ - ใช้กับค่าที่อาจยาวจน wrap
#        หลายบรรทัด (เช่น วิธีกำจัด) สำคัญ: ต้องรองรับ SDS ภาษาไทยด้วย เพราะภาษาไทยไม่มีตัวพิมพ์ใหญ่-เล็ก
#        แบบอังกฤษ [A-Z] จึงจับไม่ได้ ต้องเช็คช่วง unicode ไทย (฀-๿) แยกต่างหาก
_LINE_END = r"(?=\s{2,}|\n|\Z)"
_BLOCK_END = (
    r"(?=\n[ \t]*\n"
    r"|\n\s*[·•]"
    r"|\n\s*(?:SECTION|ส่วนที่)\s*\d+"
    r"|\n\s*[A-Z][A-Za-z][A-Za-z /,\-]{2,40}\s*:"
    r"|\n\s*[฀-๿][฀-๿ /]{0,40}\s*:"
    r"|\Z)"
)


def line(label):
    """สร้าง pattern จับค่าบรรทัดเดียวหลังป้าย `label` หยุดที่ช่องว่างยาว (คอลัมน์ถัดไป) หรือขึ้นบรรทัดใหม่"""
    return label + r"\s*:\s*([^\n]+?)" + _LINE_END


def block(label):
    """สร้าง pattern จับค่าที่อาจยาวหลายบรรทัดหลังป้าย `label` หยุดที่บรรทัดว่างหรือเจอป้ายใหม่"""
    return label + r"\s*:\s*(.+?)" + _BLOCK_END


def extract_section(text, section_num, next_section_num=None):
    """
    ตัดข้อความมาเฉพาะช่วง "SECTION N" (หรือ "ส่วนที่ N" สำหรับ SDS ภาษาไทย) จนถึงก่อนหัวข้อถัดไป
    (SDS มาตรฐาน 16 หัวข้อมักขึ้นต้นแบบนี้ทั้งฉบับอังกฤษและไทย)
    คืน None ถ้าหาหัวข้อนี้ไม่เจอ (ใช้บอกว่าควร fallback ไปค้นทั้งไฟล์แทน)

    สำคัญ: ทำแบบนี้เพราะหลาย section ใช้ป้ายย่อยชื่อเดียวกัน (เช่น "Eyes:"/"ทางตา" ทั้งใน Section 4
    (การปฐมพยาบาล) และ Section 11 (พิษวิทยา) ความหมายคนละเรื่องกัน ถ้าค้นทั้งไฟล์เฉยๆ อาจไปจับข้อความ
    จาก section ผิดมาใส่ผิดช่องได้
    """
    next_num = next_section_num or (section_num + 1)
    pattern = rf"(?:SECTION|ส่วนที่)\s*{section_num}\b.*?(?=(?:SECTION|ส่วนที่)\s*{next_num}\b|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(0) if m else None


# แถวในตารางส่วนประกอบ (Section 3) รูปแบบ "ชื่อสาร   เลข CAS   ความเข้มข้น (%)" คั่นด้วยช่องว่างยาว
# เช่น "Phosphoric acid          7664-38-2      30 - 60"
_CAS_TABLE_ROW = re.compile(
    r"^(?P<name>.{2,60}?)\s{2,}(?P<cas>\d{2,7}-\d{2}-\d)\s{2,}(?P<conc>[\d.]+(?:\s*-\s*[\d.]+)?)\s*%?\s*$",
    re.MULTILINE,
)


def parse_cas_from_composition_table(text):
    """
    หาเลข CAS จากตาราง "ส่วนประกอบ" ใน Section 3 (Composition/Information on Ingredients)
    ถ้ามีสารเคมีหลายตัวในตาราง (เป็นส่วนผสม) เลือกเลข CAS ของสารที่มี "Concentration (%)" สูงสุด
    (ใช้ค่าบนสุดของช่วง เช่น "30 - 60" ใช้ 60) เพราะถือเป็นสารหลักของผลิตภัณฑ์
    คืน None ถ้าหาตารางแบบนี้ไม่เจอ (ให้ผู้เรียก fallback ไปใช้ pattern "CAS No:" ปกติแทน)
    """
    section3 = extract_section(text, 3)
    if not section3:
        return None
    best_score, best_cas = None, None
    for m in _CAS_TABLE_ROW.finditer(section3):
        nums = [float(x) for x in re.findall(r"[\d.]+", m.group("conc"))]
        if not nums:
            continue
        score = max(nums)
        if best_score is None or score > best_score:
            best_score, best_cas = score, m.group("cas")
    return best_cas


def grab_near(text, keyword, patterns, window=300):
    """
    หาค่าเฉพาะในช่วงข้อความ `window` ตัวอักษรถัดจากคำว่า `keyword` (ไม่ใช่ค้นทั้งไฟล์)
    ใช้กับข้อมูลที่คำค้นหาสั้นและกำกวม (เช่น "Health") ซึ่งอาจไปเจอที่อื่นในเอกสารที่ไม่เกี่ยวข้อง
    คืน None ถ้าไม่เจอ keyword เลย หรือหาในช่วงนั้นไม่เจอ (ให้ผู้เรียก fallback เอง)
    """
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return None
    return grab(text[idx: idx + window], patterns, default=None)


def grab_scoped(full_text, section_text, patterns, default="-"):
    """
    หาค่าใน section_text (ข้อความเฉพาะ section ที่เกี่ยวข้อง) ก่อน ถ้าไม่มี section_text
    (หา section ไม่เจอ) หรือหาในนั้นไม่เจอ ให้ fallback ไปหาทั้งไฟล์แทน (กันตกกรณี SDS ที่ไม่มีหัว "SECTION N")
    """
    if section_text:
        val = grab(section_text, patterns, default=None)
        if val is not None:
            return val
    return grab(full_text, patterns, default=default)


# รายชื่อฟิลด์ทั้งหมดที่ระบบต้องใช้ (ตรงกับช่องใน Template.pdf / Template.xlsx)
FIELD_KEYS = [
    "display_name", "signal_word",
    "trade_name", "formula", "un", "cas", "usage",
    "state", "color", "odor", "boiling", "ph", "flash",
    "fa_eye", "fa_oral", "fa_skin", "fa_inhale",
    "hz_eye", "hz_skin", "hz_oral", "hz_inhale",
    "fire", "reactivity", "spill", "disposal", "storage",
    "nfpa_health", "nfpa_fire", "nfpa_react",
    "pictograms",
]

# คำ/รหัสที่มักเจอใน Section 2 (Hazards identification) ของ SDS ที่บ่งบอกว่าควรมีสัญลักษณ์ GHS ชนิดนั้น
# ใช้เดาเบื้องต้นให้เท่านั้น ผู้ใช้ต้องตรวจ/ติ๊กเลือกเองในฟอร์มอีกครั้งก่อนสร้าง PDF เสมอ
PICTOGRAM_KEYWORDS = {
    "explosive": [r"\bGHS0?1\b", r"\bexplosive\b", r"self-?reactive", r"วัตถุระเบิด", r"สารระเบิด"],
    "flammable": [r"\bGHS0?2\b", r"\bflammable\b", r"\bpyrophoric\b", r"สารไวไฟ", r"ไวไฟ"],
    "oxidizer": [r"\bGHS0?3\b", r"\boxidi[sz]ing\b", r"\boxidi[sz]er\b", r"สารออกซิไดซ์", r"ออกซิไดซ์"],
    "gas_cylinder": [r"\bGHS0?4\b", r"gas(?:es)? under pressure", r"compressed gas", r"ก๊าซภายใต้ความดัน"],
    "corrosive": [r"\bGHS0?5\b", r"skin corrosion", r"\bcorrosive\b", r"serious eye damage",
                  r"สารกัดกร่อน", r"กัดกร่อน"],
    "toxic": [r"\bGHS0?6\b", r"acute toxicity", r"\bfatal if\b", r"\btoxic if\b", r"พิษเฉียบพลัน", r"เป็นพิษ"],
    "irritant": [r"\bGHS0?7\b", r"skin irritation", r"eye irritation", r"\birritant\b",
                 r"สารระคายเคือง", r"ระคายเคือง"],
    "health_hazard": [r"\bGHS0?8\b", r"carcinogen", r"respiratory sensiti[sz]", r"reproductive toxicity",
                       r"specific target organ", r"aspiration hazard", r"สารก่อมะเร็ง", r"อันตรายต่อสุขภาพ"],
    "environment": [r"\bGHS0?9\b", r"aquatic (?:acute|chronic)", r"hazardous to the aquatic environment",
                     r"อันตรายต่อสิ่งแวดล้อม", r"เป็นพิษต่อสิ่งมีชีวิตในน้ำ"],
}


# รหัส Hazard Statement (H-code, เช่น H226) / Precautionary Statement (P-code, เช่น P210)
# มักอยู่ในรูปแบบ "รหัส + ข้อความ" หนึ่งบรรทัดต่อหนึ่งข้อ ใน Section 2 (Hazard identification)
# จับทั้งบรรทัดที่มีรหัสไว้ตรงๆ (ไม่แยกรหัส/ข้อความออกจากกัน) เพราะฉลากต้องแสดงคู่กันเสมออยู่แล้ว
_H_CODE_LINE = re.compile(r"\bH[2-4]\d{2}\b[^\n]*", re.MULTILINE)
_P_CODE_LINE = re.compile(r"\bP[1-5]\d{2}(?:\s*\+\s*P[1-5]\d{2})*\b[^\n]*", re.MULTILINE)


def _extract_code_lines(text, pattern):
    """หาแต่ละบรรทัดที่มีรหัส H/P-code ใน Section 2 ก่อน (fallback ทั้งไฟล์ถ้าหา section ไม่เจอ)
    คืน list ของบรรทัดเรียงตามที่เจอ ไม่เอาบรรทัดซ้ำ"""
    section2 = extract_section(text, 2) or text
    seen = []
    for m in pattern.finditer(section2):
        val = _clean(m.group(0))
        if val and val not in seen:
            seen.append(val)
    return seen


def extract_hazard_statements(text):
    """ดึงรายการ Hazard Statement (H-code) พร้อมข้อความ เช่น ['H226 Flammable liquid and vapour.']"""
    return _extract_code_lines(text, _H_CODE_LINE)


def extract_precautionary_statements(text):
    """ดึงรายการ Precautionary Statement (P-code) พร้อมข้อความ เช่น ['P210 Keep away from heat.']"""
    return _extract_code_lines(text, _P_CODE_LINE)


def _raw_block(text, label):
    """เหมือน block() แต่คืนข้อความดิบ (ไม่ผ่าน _clean ที่รวมทุกบรรทัดเป็นบรรทัดเดียว)
    ใช้ตอนต้องแยกบรรทัดเอง เช่น แยกชื่อบริษัท/ที่อยู่ที่อยู่ในก้อนเดียวกันแต่คนละบรรทัด"""
    pattern = label + r"\s*:\s*(.+?)" + _BLOCK_END
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(1) if m else None


def extract_supplier_info(text):
    """ดึงข้อมูลผู้ผลิต/ผู้จำหน่าย + เบอร์โทรฉุกเฉิน จาก Section 1 (สำหรับฉลากภาชนะบรรจุ)"""
    section1 = extract_section(text, 1) or text
    name = grab(section1, [
        line(r"Company"), line(r"Company [Nn]ame"),
        line(r"Supplier"), line(r"Manufacturer"),
        line(r"ชื่อบริษัท"), line(r"ผู้ผลิต"), line(r"ผู้จำหน่าย"),
    ])
    address = grab(section1, [
        block(r"Address"), block(r"Street [Aa]ddress"),
        block(r"ที่อยู่"),
    ])
    # SDS หลายฉบับไม่มีป้าย "Address:" แยกต่างหาก แต่ที่อยู่ต่อท้ายชื่อบริษัททันทีคนละบรรทัด
    # ใต้ป้าย "Manufacturer/Supplier:" เดียวกัน เลยลองแยกบรรทัดเอาบรรทัดแรกเป็นชื่อ ที่เหลือเป็นที่อยู่
    if name == "-" or address == "-":
        raw = (_raw_block(section1, r"Manufacturer\s*/\s*Supplier")
               or _raw_block(section1, r"Supplier")
               or _raw_block(section1, r"Manufacturer")
               or _raw_block(section1, r"ผู้ผลิต")
               or _raw_block(section1, r"ผู้จำหน่าย"))
        if raw:
            lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
            if name == "-" and lines:
                name = lines[0]
            if address == "-" and len(lines) > 1:
                address = " ".join(lines[1:])
    return {
        "supplier_name": name,
        "supplier_address": address,
        "emergency_phone": grab(section1, [
            line(r"Emergency [Tt]elephone(?: [Nn]umber)?"),
            line(r"Emergency [Pp]hone"),
            line(r"เบอร์โทรฉุกเฉิน"), line(r"โทรศัพท์ฉุกเฉิน"),
        ]),
    }


def detect_pictograms(text):
    """
    เดาสัญลักษณ์ GHS ที่น่าจะเกี่ยวข้อง จากคำ/รหัสที่เจอใน SDS (ส่วนมากอยู่ Section 2)
    คืน list ของ key ตามลำดับใน PICTOGRAM_KEYWORDS แค่ที่เจอ pattern จริง
    """
    found = []
    for key, patterns in PICTOGRAM_KEYWORDS.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            found.append(key)
    return found


def parse_sds(pdf_path):
    """ดึงฟิลด์ทั้งหมดที่ Template ต้องการ จากไฟล์ SDS คืนเป็น dict"""
    t = read_all_text(pdf_path)
    d = {}

    # ตัดมาเฉพาะช่วง Section 4 (การปฐมพยาบาล) และ Section 11 (พิษวิทยา) ไว้ก่อน
    # กันป้ายย่อยชื่อเดียวกัน (Eyes/Skin/Ingestion/Inhalation) ในคนละ section ปนกัน
    section4 = extract_section(t, 4)
    section11 = extract_section(t, 11)

    # หมายเหตุ: field สั้น (บรรทัดเดียว เช่น pH, สี, กลิ่น) ใช้ line() - หยุดจับที่ช่องว่างยาว (คอลัมน์ถัดไป)
    # field ยาว (อาจ wrap หลายบรรทัด เช่น วิธีกำจัด, การปฐมพยาบาล) ใช้ block() - จับข้ามบรรทัดได้จนกว่าจะเจอ
    # บรรทัดว่างหรือหัวข้อใหม่ ทั้งสองแบบยอมให้มีช่องว่างก่อน ":" ได้เสมอ (SDS หลายฉบับจัดหน้าแบบตาราง
    # มีช่องว่าง/แท็บคั่นระหว่างชื่อหัวข้อกับ ":" เยอะ เช่น "Flash point          :   value")
    d["trade_name"] = grab(t, [
        line(r"Trade name"),
        line(r"Product name"),
        line(r"Product Name"),
        line(r"Material name"),
        line(r"ชื่อทางการค้า"), line(r"ชื่อผลิตภัณฑ์"), line(r"ชื่อสินค้า"),
    ])
    d["display_name"] = d["trade_name"]  # ค่าเริ่มต้น: ใช้ชื่อเดียวกับ trade_name (แก้แยกได้ในฟอร์ม)
    d["signal_word"] = grab(t, [
        line(r"Signal [Ww]ord"),
        line(r"คำสัญญาณ"),
    ])
    # ถ้า Section 3 มีตารางส่วนประกอบหลายสาร ให้เลือกเลข CAS ของสารที่ Concentration (%) สูงสุดก่อน
    # (ถือเป็นสารหลักของผลิตภัณฑ์) ถ้าไม่มีตารางแบบนี้ (สารเดี่ยว) ค่อย fallback ไปหา "CAS No:" ปกติ
    d["cas"] = parse_cas_from_composition_table(t) or grab(t, [
        r"CAS Number\s*:\s*\n?\s*([\d\-]+)",
        r"CAS[\-\s]?No\.?\s*:\s*\n?\s*([\d\-]+)",
        r"CAS Registry Number\s*:\s*\n?\s*([\d\-]+)",
        r"(?:เลขทะเบียน|หมายเลข)\s*CAS\s*:\s*\n?\s*([\d\-]+)",
    ])
    d["un"] = grab(t, [
        r"UN[- ]Number.*?\n.*?IATA\s+([^\n]+?)" + _LINE_END,
        line(r"UN[\-\s]?Number"),
        line(r"UN[\-\s]?No\.?"),
        line(r"(?:เลข|หมายเลข)\s*UN"),
    ])
    d["formula"] = grab(t, [
        line(r"Chemical formula"),
        line(r"Formula"),
        line(r"สูตรทางเคมี"), line(r"สูตรโมเลกุล"),
    ])
    d["usage"] = grab(t, [
        r"Application of the substance / the mixture\s*(.+?)" + _BLOCK_END,
        block(r"Recommended use"),
        block(r"Product use"),
        block(r"Uses of the [Ss]ubstance.*?"),
        block(r"(?:ลักษณะ|วัตถุประสงค์)?การใช้งาน"),
    ])
    d["state"] = grab(t, [
        line(r"Form"),
        line(r"Physical [Ss]tate"),
        line(r"Appearance"),
        line(r"สถานะ"), line(r"ลักษณะทางกายภาพ"),
    ])
    d["color"] = grab(t, [line(r"Colou?r"), line(r"สี")])
    d["odor"] = grab(t, [line(r"Odou?r"), line(r"กลิ่น")])
    d["boiling"] = grab(t, [
        line(r"Boiling point/Boiling range"),
        line(r"Boiling [Pp]oint,?\s*(?:initial boiling point\s*)?(?:and\s*)?(?:boiling\s*)?(?:range)?"),
        line(r"จุดเดือด"),
    ])
    d["ph"] = grab(t, [
        line(r"pH[\-\s]?value"),
        line(r"pH"),
        line(r"ความเป็นกรด[\-\s]?ด่าง"),
    ])
    d["flash"] = grab(t, [line(r"Flash [Pp]oint"), line(r"จุดวาบไฟ")])
    # Section 4 (การปฐมพยาบาล) - ค้นในช่วง Section 4 ก่อน กันไปจับ Section 11 (พิษวิทยา) ผิด
    # ป้ายเปล่าๆ อย่าง "Eyes:"/"Skin:"/"Ingestion:"/"Inhalation:" ต้องยึดให้อยู่ต้นบรรทัดเท่านั้น
    # (ไม่งั้น "After inhalation:" จะโดนจับซ้อนเพราะมีคำว่า "inhalation:" อยู่ข้างในเป็น substring)
    d["fa_eye"] = grab_scoped(t, section4, [
        block(r"After eye contact"),
        block(r"Eye [Cc]ontact"),
        block(r"If in eyes"),
        block(r"(?:^|\n)\s*Eyes"),
        block(r"(?:^|\n)\s*ทางตา"),
    ])
    d["fa_oral"] = grab_scoped(t, section4, [
        block(r"After swallowing"),
        block(r"If [Ss]wallowed"),
        block(r"(?:^|\n)\s*Ingestion"),
        block(r"(?:^|\n)\s*ทางปาก"), block(r"(?:กรณี)?การกลืนกิน"),
    ])
    d["fa_skin"] = grab_scoped(t, section4, [
        block(r"After skin contact"),
        block(r"Skin [Cc]ontact"),
        block(r"If on skin"),
        block(r"(?:^|\n)\s*Skin"),
        block(r"(?:^|\n)\s*ทางผิวหนัง"),
    ])
    d["fa_inhale"] = grab_scoped(t, section4, [
        block(r"After inhalation"),
        block(r"If [Ii]nhaled"),
        block(r"(?:^|\n)\s*Inhalation"),
        block(r"(?:^|\n)\s*ทางการหายใจ"), block(r"การหายใจเข้าไป"), block(r"การสูดดม"),
    ])
    # Section 11 (พิษวิทยา) - ค้นในช่วง Section 11 ก่อน กันไปจับ Section 4 (ปฐมพยาบาล) ผิด
    d["hz_eye"] = grab_scoped(t, section11, [
        block(r"on the eye"),
        block(r"Eye [Ii]rritation"),
        block(r"(?:^|\n)\s*Eyes"),
        block(r"(?:^|\n)\s*ทางตา"),
    ])
    d["hz_skin"] = grab_scoped(t, section11, [
        block(r"on the skin"),
        block(r"Skin [Ii]rritation"),
        block(r"(?:^|\n)\s*Skin"),
        block(r"(?:^|\n)\s*ทางผิวหนัง"),
    ])
    d["hz_oral"] = grab_scoped(t, section11, [
        block(r"(?:^|\n)\s*Ingestion"),
        block(r"(?:^|\n)\s*ทางปาก"),
    ])
    d["hz_inhale"] = grab_scoped(t, section11, [
        block(r"(?:^|\n)\s*Inhalation"),
        block(r"(?:^|\n)\s*ทางการหายใจ"), block(r"การสูดดม"),
    ])
    d["fire"] = grab(t, [
        block(r"Suitable extinguishing agents"),
        block(r"Suitable extinguishing media"),
        block(r"Extinguishing media"),
        block(r"(?:วิธี)?การดับเพลิง"), block(r"สารดับเพลิงที่เหมาะสม"),
    ])
    d["reactivity"] = grab(t, [
        r"Possibility of hazardous reactions\s*(.+?)" + _BLOCK_END,
        block(r"Hazardous reactions"),
        block(r"Chemical stability"),
        block(r"การเกิดปฏิกิริยา"), block(r"ความเสถียรทางเคมี"), block(r"โอกาสเกิดปฏิกิริยาอันตราย"),
    ])
    # Section 6 (การจัดการเมื่อรั่วไหล) - "Methods for cleaning up" คือสิ่งที่ตรงกับ "กรณีหกรั่วไหล" ที่สุด
    # ถ้าไม่เจอค่อย fallback ไปที่ "Environmental precautions" (ยังพอเกี่ยวข้องแต่ไม่ตรงเป๊ะ)
    d["spill"] = grab(t, [
        block(r"Methods and material for containment and cleaning up"),
        block(r"Methods for [Cc]leaning up"),
        block(r"Methods for containment"),
        block(r"Environmental precautions"),
        block(r"วิธีปฏิบัติเมื่อ(?:มี)?การหกรั่วไหล"), block(r"(?:กรณี|การจัดการเมื่อ)สารหกรั่วไหล"),
    ])
    d["disposal"] = grab(t, [
        block(r"Recommendation"),
        block(r"Disposal methods"),
        block(r"Waste treatment methods"),
        block(r"(?:วิธี|คำแนะนำ)?การกำจัด"),
    ])
    d["storage"] = grab(t, [
        block(r"Requirements to be met by storerooms and receptacles"),
        block(r"Storage conditions"),
        block(r"Conditions for safe storage"),
        block(r"การเก็บรักษา"), block(r"สภาวะการเก็บรักษาที่ปลอดภัย"),
    ])
    # ดัชนี NFPA มักอยู่ในรูปไดอะแกรมเพชร ไม่ใช่ข้อความเรียงกันแบบปกติ - pdfplumber อาจดึงตัวเลข/ป้าย
    # ออกมาสลับตำแหน่งกับข้อความส่วนอื่นของเอกสาร (เช่น ตาราง HMIS ที่อยู่ใกล้กัน) ถ้าค้นทั้งไฟล์เฉยๆ
    # เสี่ยงไปจับเลขผิดจุดมาก จึงจำกัดให้ค้นเฉพาะในช่วงข้อความถัดจากคำว่า "NFPA" ก่อน (window)
    # และรับเฉพาะเลข 0-4 เท่านั้น (ตามสเกลจริงของ NFPA) ถ้าหาไม่เจอค่อย fallback ไปค้นทั้งไฟล์
    NFPA_WINDOW = 300
    d["nfpa_health"] = (
        grab_near(t, "NFPA", [r"Health\s*[:=]?\s*([0-4])"], window=NFPA_WINDOW)
        or grab(t, [r"Health\s*=\s*([0-4])", r"Health\s*[:\-]\s*([0-4])"], default="")
    )
    d["nfpa_fire"] = (
        grab_near(t, "NFPA", [r"Flammability\s*[:=]?\s*([0-4])", r"Fire\s*[:=]?\s*([0-4])"], window=NFPA_WINDOW)
        or grab(t, [r"Fire\s*=\s*([0-4])", r"Fire\s*[:\-]\s*([0-4])"], default="")
    )
    d["nfpa_react"] = (
        grab_near(t, "NFPA", [r"Instability\s*[:=]?\s*([0-4])", r"Reactivity\s*[:=]?\s*([0-4])"], window=NFPA_WINDOW)
        or grab(t, [r"Reactivity\s*=\s*([0-4])", r"Reactivity\s*[:\-]\s*([0-4])"], default="")
    )
    d["pictograms"] = detect_pictograms(t)
    # สำหรับหน้า "ฉลากภาชนะบรรจุ" (label.html) - Hazard/Precautionary statement + ข้อมูลผู้ผลิต
    # ถ้าดึงไม่ครบ ผู้ใช้แก้ไข/พิมพ์เพิ่มเองในฟอร์มได้ (ไม่บังคับต้องดึงได้ 100%)
    d["hazard_statements"] = extract_hazard_statements(t)
    d["precautionary_statements"] = extract_precautionary_statements(t)
    d.update(extract_supplier_info(t))
    # ช่องขาว (Special Hazard) ในรูปเพชร NFPA เดาเบื้องต้นจากสัญลักษณ์ GHS ที่ตรวจเจอ (เลือกได้แค่อย่างเดียว
    # จึงหยุดที่ตัวแรกที่ตรงเงื่อนไข) SDS ไม่ได้ระบุค่านี้ตรงๆ ต้องตรวจสอบเองในฟอร์มเสมอ
    if "oxidizer" in d["pictograms"]:
        d["nfpa_special"] = "OXY"
    elif "corrosive" in d["pictograms"]:
        d["nfpa_special"] = "COR"
    else:
        d["nfpa_special"] = ""
    return d


if __name__ == "__main__":
    import json
    print(json.dumps(parse_sds("getpdf_sample.pdf"), indent=2, ensure_ascii=False))
