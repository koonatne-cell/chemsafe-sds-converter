# -*- coding: utf-8 -*-
"""
fill_template.py - วางค่าที่ดึงมา (และแปลไทยแล้ว) ลงบน Template.pdf แล้วเซฟไฟล์ใหม่

ต่อยอดจาก prototype เดิม เพิ่ม:
  1. ฝังฟอนต์ไทย (Tahoma) เพราะ Helvetica ของ reportlab แสดงภาษาไทยไม่ได้
  2. วางรูปภาพ 2 ช่อง (รูปสลากสารเคมี / รูปภาชนะบรรจุสารเคมี)
  3. ตัดบรรทัดแบบภาษาไทย (ไม่ตัดกลางคำ เช่น "นาที" ไม่กลายเป็น "นา" + "ที") ด้วย pythainlp
  4. คำนวณพื้นที่ว่างจริงของแต่ละช่อง (จากช่องถัดไป) แล้วลดขนาดฟอนต์อัตโนมัติถ้าข้อความยาวเกิน
     กันไม่ให้ข้อความล้นไปทับช่องถัดไป
  5. ช่อง "จัดทำโดย" / "อนุมัติโดย" (ชื่อ-สกุล, ตำแหน่ง)
  6. สัญลักษณ์ GHS (pictogram) ที่ผู้ใช้ติ๊กเลือก วางในกล่องสี่เหลี่ยมมุมซ้ายบน

วิธี: สร้างชั้น "overlay" ด้วย reportlab แล้ววางทับเทมเพลตด้วย pypdf
พิกัด reportlab นับจากมุมล่างซ้าย  ->  y = ความสูงหน้า - top(จาก pdfplumber)
"""
import io
import os
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter
from pythainlp.tokenize import word_tokenize
from reportlab.pdfbase.pdfmetrics import stringWidth

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_W, PAGE_H = 595.32, 841.92   # ขนาดหน้าเทมเพลต (points)

# ---------- ฟอนต์ไทย ----------
# ใช้ Noto Sans Thai (ฟรี, สัญญาอนุญาต SIL Open Font License เผยแพร่ในโค้ด public ได้ถูกกฎหมาย)
# ต่างจาก Tahoma ที่เป็นฟอนต์ลิขสิทธิ์ของ Microsoft ห้ามแจกจ่ายต่อในซอร์สโค้ด public
FONT_REGULAR_PATH = os.path.join(HERE, "assets", "fonts", "NotoSansThai-Regular.ttf")
FONT_BOLD_PATH = os.path.join(HERE, "assets", "fonts", "NotoSansThai-Bold.ttf")
FONT_REGULAR = "THFont"
FONT_BOLD = "THFont-Bold"

_fonts_registered = False


def register_thai_fonts():
    """ลงทะเบียนฟอนต์ไทยกับ reportlab (ทำครั้งเดียวพอ)"""
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, FONT_REGULAR_PATH))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, FONT_BOLD_PATH))
    _fonts_registered = True


def Y(top):
    """แปลงพิกัด top (จากด้านบน) เป็น y ของ reportlab (จากด้านล่าง)"""
    return PAGE_H - top

# แถบเหลือง (ชื่อสารเคมี ตัวใหญ่) และแถบแดง (Signal Word) บนหัวฟอร์ม
# หาตำแหน่งจริงจาก Template.pdf ด้วย pdfplumber (สี่เหลี่ยมพื้นสีที่ x0=125.5-472.7)
# วางกึ่งกลางแถบ (drawCentredString) เพราะเป็นข้อความเด่นตรงกลาง ไม่ใช่ "ป้าย: ค่า" แบบช่องอื่น
HEADER_BAR_X_CENTER = (125.5 + 472.7) / 2  # 299.1
HEADER_BAR_MAX_WIDTH = 472.7 - 125.5 - 12  # เผื่อขอบซ้ายขวาเล็กน้อย
HEADER = {
    "display_name": {"top_center": (158.8 + 181.7) / 2, "size": 16},
    "signal_word":  {"top_center": (181.6 + 200.2) / 2, "size": 13},
}

# ตำแหน่งช่องบรรทัดเดียว (x, top)  วางค่าเริ่มหลัง ":" นิดหน่อย
SHORT = {
    "trade_name": (52,  212),  "formula": (352, 211),
    "un":         (441, 211),  "cas":     (519, 211),
    "state":      (124, 226),  "color":   (233, 226),
    "odor":       (285, 226),  "boiling": (345, 226),
    "ph":         (433, 226),  # ต้องปิดขีด "-" ตัวอย่างของเทมเพลตก่อน (ดู SHORT_COVER)
    "flash":      (523, 226),
}
# ช่อง pH ในเทมเพลตมีขีด "-" พิมพ์ไว้เป็นค่าเริ่มต้นอยู่แล้ว (x0=430.3-432.4, top~225.6)
# ถ้ามีค่า pH จริงมากรอก ต้องปิดขีดเดิมด้วยสี่เหลี่ยมสีขาวก่อน ไม่งั้นจะซ้อนทับกัน
SHORT_COVER = {
    "ph": {"x0": 428, "x1": 436, "top": 220, "bottom": 234},
}
# ตำแหน่ง x ที่ป้ายของช่องถัดไป (ในแถวเดียวกัน) เริ่มพิมพ์จริงในเทมเพลต (วัดด้วย pdfplumber)
# ใช้จำกัดความกว้างของค่าที่วาง กันข้อความยาวทับป้ายช่องถัดไป (ป้ายเริ่มก่อนตำแหน่งค่าของช่องนั้นมาก)
# None = ไม่มีป้ายถัดไปในแถวนี้แล้ว (ช่องสุดท้ายของแถว) ใช้ขอบกระดาษแทน
_SHORT_NEXT_LABEL_X = {
    "trade_name": 208.0, "formula": 416.6, "un": 489.2, "cas": None,
    "state": 223.4, "color": 264.1, "odor": 315.1, "boiling": 416.6, "ph": 489.2, "flash": None,
}
# ตำแหน่งช่องข้อความยาว (x, top)  ต้องตัดบรรทัด (wrap)
BLOCK = {
    "usage":     (100, 240),  "reactivity": (100, 269),
    "fire":      (100, 300),
    "hz_eye":    (100, 330),  "hz_oral": (100, 345),
    "hz_skin":   (100, 360),  "hz_inhale":(100, 375),
    "fa_eye":    (100, 405),  "fa_oral": (100, 420),
    "fa_skin":   (100, 435),  "fa_inhale":(100, 450),
    "spill":     (100, 480),  "disposal":(100, 524),
    "storage":   (100, 577),
}
# ความกว้างจริงที่มีให้ค่าแต่ละช่องวางได้ (pt) วัดจากเส้นแบ่งจริงในเทมเพลต
# มีเส้นแบ่งแนวตั้งที่ x=360.7 กั้นกล่อง PPE/NFPA/legend/รูปภาชนะ ทางขวาไว้ยาวตั้งแต่ top=251.4 ถึง 722.8
# (เกือบทุกแถวยกเว้น usage ที่อยู่เหนือเส้นแบ่งนี้) แถวที่ชนเส้นแบ่งเลยต้องจำกัดความกว้างไม่ให้ทับ
_NARROW_DIVIDER_TOP = 251.4
_NARROW_DIVIDER_X = 360.7
BLOCK_MAX_WIDTH = {
    k: (_NARROW_DIVIDER_X - x - 5 if top >= _NARROW_DIVIDER_TOP else PAGE_W - 20 - x)
    for k, (x, top) in BLOCK.items()
}
# NFPA สี่เหลี่ยมข้าวหลามตัด (x_center, top_center) หาตำแหน่งจริงจาก Template.pdf ด้วย pdfplumber
# (วัดจาก path ของแต่ละสี่เหลี่ยมย่อยในรูปเพชรโดยตรง ไม่ใช่กะประมาณ)
NFPA = {
    "nfpa_fire":   (528.05, 299.1),   # บน (แดง)
    "nfpa_health": (510.1,  316.25),  # ซ้าย (น้ำเงิน)
    "nfpa_react":  (545.85, 316.25),  # ขวา (เหลือง)
}
# ช่องขาว (Special Hazard) ด้านล่างรูปเพชร - พื้นขาวจึงใช้ตัวหนังสือสีดำ (ไม่ใช่ขาวเหมือน 3 ช่องบน)
# และเป็นตัวอักษรย่อ (OXY/ACID/ALK/COR/W) ไม่ใช่ตัวเลขเดี่ยว เลยแยกวาดต่างหากจาก NFPA ด้านบน
NFPA_SPECIAL_X_CENTER, NFPA_SPECIAL_TOP_CENTER = 528.0, 333.4
# ช่อง "จัดทำโดย" / "อนุมัติโดย" (ชื่อ-สกุล, ตำแหน่ง) หาตำแหน่งจริงจาก Template.pdf ด้วย pdfplumber
# วางต่อท้ายป้าย "ชื่อ-สกุล" / "ตำแหน่ง" ที่มีอยู่แล้วในเทมเพลต ถ้าไม่กรอกค่า
# ป้ายเดิมของเทมเพลต (เช่น "(EHS Manager)") จะยังอยู่เหมือนเดิม เพราะเราวาดทับเฉพาะตอนมีค่าเท่านั้น
SIGNATURE = {
    "prepared_name":     (95,  762),  # จัดทำโดย - ชื่อ-สกุล
    "prepared_position": (95,  777),  # จัดทำโดย - ตำแหน่ง
    "approved_name":     (443, 762),  # อนุมัติโดย - ชื่อ-สกุล
    "approved_position": (444, 777),  # อนุมัติโดย - ตำแหน่ง
}
# ความกว้างจริงที่มีก่อนชนขอบกระดาษ/คอลัมน์ถัดไป (กันชื่อ-ตำแหน่งยาวๆ ทับข้อความอื่น)
SIGNATURE_MAX_WIDTH = {
    "prepared_name": 290, "prepared_position": 290,
    "approved_name": 145, "approved_position": 145,
}
# ฝั่ง "อนุมัติโดย" เทมเพลตมีข้อความตัวอย่างพิมพ์ไว้แล้ว เช่น "(______)" และ "(EHS Manager)"
# ถ้าผู้ใช้กรอกค่าเอง ต้องปิดข้อความเดิมด้วยสี่เหลี่ยมสีขาวก่อน ไม่งั้นจะซ้อนทับกันอ่านไม่ออก
SIGNATURE_COVER = {
    "approved_name":     {"x0": 440, "x1": 546, "top": 758, "bottom": 770},
    "approved_position": {"x0": 440, "x1": 546, "top": 773, "bottom": 786},
}

# กรอบรูปภาพ 2 ช่อง หาตำแหน่งจริงจาก Template.pdf ด้วย pdfplumber
# (เส้นขอบกรอบอยู่ที่ top=610.7 ถึง top=722.0 แบ่งซ้าย/ขวาที่ x=360.7)
IMAGE_BOXES = {
    "label_image":     {"x0": 28,  "x1": 352, "top": 634, "bottom": 720},  # รูปสลากสารเคมี (ซ้าย)
    "container_image": {"x0": 369, "x1": 566, "top": 634, "bottom": 720},  # รูปภาชนะบรรจุสารเคมี (ขวา)
}

# กล่องสี่เหลี่ยมมุมซ้ายบน (เดิมว่างเปล่า) สำหรับวางสัญลักษณ์ GHS (pictogram) ที่ผู้ใช้ติ๊กเลือก
# หาตำแหน่งจริงจาก Template.pdf ด้วย pdfplumber (กรอบเส้นขอบ stroke จริง)
PICTOGRAM_BOX = {"x0": 31.4, "x1": 108.7, "top": 129.8, "bottom": 199.2}
PICTOGRAM_ICON_DIR = os.path.join(HERE, "assets", "ghs_icons")
PICTOGRAM_ORDER = [
    "explosive", "flammable", "oxidizer",
    "gas_cylinder", "corrosive", "toxic",
    "irritant", "health_hazard", "environment",
]

# ขอบเขตล่างสุดของพื้นที่ข้อมูล SHORT/BLOCK (เส้นขอบกรอบรูปภาพ) ใช้คำนวณพื้นที่ว่างของช่องสุดท้าย
DATA_AREA_BOTTOM = 610

# หาตำแหน่ง "top" ที่ไม่ซ้ำกันทั้งหมดของ SHORT+BLOCK เรียงจากบนลงล่าง
# ใช้คำนวณว่าแต่ละช่องมีพื้นที่ว่างแนวตั้งได้แค่ไหนก่อนจะชนช่องถัดไป (กันข้อความล้น)
_ALL_ROWS = {**SHORT, **BLOCK}
_UNIQUE_TOPS = sorted(set(top for _, top in _ALL_ROWS.values()))

# แผนที่ top -> รายชื่อ key ที่อยู่แถวนั้น (ใช้เช็คว่าแถวถัดไปว่างหรือไม่)
_TOP_TO_KEYS = {}
for _k, (_x, _top) in _ALL_ROWS.items():
    _TOP_TO_KEYS.setdefault(_top, []).append(_k)


def _is_empty(data, key):
    val = (data.get(key) or "").strip()
    return val in ("", "-")


def _available_height(top, data=None):
    """
    คืนพื้นที่ว่างแนวตั้ง (pt) ก่อนจะถึงแถวถัดไป (หรือขอบเขตล่างสุดถ้าเป็นแถวสุดท้าย)

    หลายช่อง (เช่น ทางตา/ทางปาก/ทางผิวหนัง/ทางการหายใจ) อยู่ใน "กล่องรวม" เดียวกันของเทมเพลต
    ไม่มีเส้นแบ่งแถวจริงๆ ถ้าแถวถัดไปไม่มีข้อมูล (ว่างเปล่าหรือ "-") ให้ขยายพื้นที่ยืมมาใช้ได้
    (พบบ่อยมาก เช่น hz_oral/hz_inhale แทบไม่มีข้อมูลจาก SDS เกือบทุกครั้ง)
    """
    idx = _UNIQUE_TOPS.index(top)
    boundary = DATA_AREA_BOTTOM
    while idx + 1 < len(_UNIQUE_TOPS):
        next_top = _UNIQUE_TOPS[idx + 1]
        keys_at_next = _TOP_TO_KEYS.get(next_top, [])
        if data is not None and keys_at_next and all(_is_empty(data, k) for k in keys_at_next):
            idx += 1  # แถวถัดไปว่างทั้งหมด ยืมพื้นที่ต่อไปได้
            continue
        boundary = next_top
        break
    return max(boundary - top - 2, 8)  # กันพื้นที่ขั้นต่ำไว้ 8pt เผื่อบรรทัดเดียว


# ช่องบรรทัดเดียว (SHORT) หลายช่องอยู่ "แถวเดียวกัน" ติดกันตามแนวนอน (เช่น สี/กลิ่น/จุดเดือด)
# คำนวณความกว้างจริงที่มีก่อนจะชนช่องถัดไปทางขวา กันข้อความยาวทับป้ายช่องถัดไป
# สำคัญ: ต้องวัดถึงจุดที่ "ป้าย" ของช่องถัดไปเริ่มพิมพ์ (_SHORT_NEXT_LABEL_X) ไม่ใช่ตำแหน่งค่า
# เพราะป้ายจะเริ่มก่อนตำแหน่งค่าของช่องนั้นเสมอ (เช่น ป้าย "จุดเดือด" อยู่ก่อนตำแหน่งค่าของมันเองเยอะ)
PAGE_RIGHT_MARGIN = 590
_SHORT_MAX_WIDTH = {}
for _k, (_x, _top) in SHORT.items():
    _boundary = _SHORT_NEXT_LABEL_X.get(_k)
    if _boundary is None:
        _boundary = PAGE_RIGHT_MARGIN
    _SHORT_MAX_WIDTH[_k] = max(_boundary - _x - 6, 20)


def _fit_single_line(val, max_width, base_size=7, min_size=5.5):
    """
    หาขนาดฟอนต์ + ข้อความ 1 บรรทัด ที่พอดีกับความกว้างจริง (max_width) โดยวัดความกว้างจริง
    ด้วย stringWidth (ไม่ใช่การนับตัวอักษรเดา) ลดฟอนต์ก่อน ถ้ายังไม่พอค่อยตัดข้อความแล้วใส่ "…"
    """
    size = base_size
    while size >= min_size:
        if stringWidth(val, FONT_REGULAR, size) <= max_width:
            return size, val
        size -= 0.5
    # เล็กสุดแล้วยังไม่พอ ตัดตัวอักษรออกทีละตัวจนกว่าจะพอดี (คำนวณความกว้างจริงทุกครั้ง)
    text = val
    while len(text) > 1 and stringWidth(text + "…", FONT_REGULAR, min_size) > max_width:
        text = text[:-1]
    return min_size, text.rstrip() + "…"


def wrap_thai(text, max_width, font_size=7):
    """
    ตัดบรรทัดข้อความให้กว้างไม่เกิน `max_width` (pt) จริงๆ (วัดด้วย stringWidth ไม่ใช่นับตัวอักษรเดา)
    ใช้ pythainlp ตัดคำภาษาไทยก่อน แล้วค่อยรวมเป็นบรรทัด กันไม่ให้ตัดกลางคำ
    (ภาษาไทยไม่มีเว้นวรรคระหว่างคำ ถ้าใช้ textwrap ธรรมดาจะตัดกลางคำ เช่น "นาที" กลายเป็น "นา"+"ที")
    เน้นใช้ความกว้างที่มีให้เต็มที่ก่อนตัดบรรทัด (บรรทัดยาวดีกว่าตัดถี่ๆ)
    """
    text = text.strip()
    if not text:
        return []
    tokens = word_tokenize(text, engine="newmm", keep_whitespace=True)
    lines = []
    current = ""
    for tok in tokens:
        candidate = current + tok
        if not current or stringWidth(candidate, FONT_REGULAR, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current.strip())
            current = tok
        # คำเดี่ยวที่ยาวเกิน max_width เอง (เช่น URL หรือคำอังกฤษยาวๆ) ตัดตามตัวอักษรตรงๆ
        while stringWidth(current, FONT_REGULAR, font_size) > max_width and len(current) > 1:
            cut = len(current)
            while cut > 1 and stringWidth(current[:cut], FONT_REGULAR, font_size) > max_width:
                cut -= 1
            lines.append(current[:cut])
            current = current[cut:]
    if current.strip():
        lines.append(current.strip())
    return lines


def _fit_lines(val, avail_height, max_width, base_size=7, min_size=4.5):
    """
    หาขนาดฟอนต์ + บรรทัดที่ตัดแล้ว ที่พอดีกับพื้นที่ว่าง (avail_height) และความกว้างจริง (max_width)
    ลดขนาดฟอนต์ทีละ 0.5pt จนกว่าจะพอดี ถ้ายังไม่พอดีที่ขนาดเล็กสุด จะตัดบรรทัดที่เกินออกและใส่ "…" ต่อท้าย
    คืนค่า (font_size, line_height, lines)
    """
    size = base_size
    lines = []
    line_height = size + 1.3
    while size >= min_size:
        lines = wrap_thai(val, max_width, font_size=size)
        line_height = size + 1.3
        if len(lines) * line_height <= avail_height:
            return size, line_height, lines
        size -= 0.5
    # ถึงขนาดเล็กสุดแล้วยังไม่พอ ตัดจำนวนบรรทัดให้พอดีพื้นที่ แล้วใส่ "…" ท้ายบรรทัดสุดท้าย
    max_lines = max(1, int(avail_height // line_height))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip() + "…"
    return min_size, line_height, lines


BLOCK_TOP_PAD = 2.5  # ขยับบรรทัดแรกลงมาเล็กน้อย กันข้อความชิดเส้นขอบบนของแถวเกินไป


def draw_text(c, val, avail_height, max_width, size=7, single_line=False):
    """เขียนข้อความลงตำแหน่งที่ translate ไว้แล้ว (จุดเริ่ม 0,0) พอดีกับพื้นที่ว่าง/ความกว้างจริงที่มี"""
    if not val or val == "-":
        return
    if single_line:
        # ช่องบรรทัดเดียว (เช่น ชื่อสาร, CAS No, ชื่อผู้จัดทำ) ไม่ยอมให้ขึ้นบรรทัดใหม่
        font_size, text = _fit_single_line(val, max_width, base_size=size)
        c.setFont(FONT_REGULAR, font_size)
        c.drawString(0, 0, text)
        return
    font_size, line_height, lines = _fit_lines(val, avail_height - BLOCK_TOP_PAD, max_width, base_size=size)
    c.setFont(FONT_REGULAR, font_size)
    for i, ln in enumerate(lines):
        c.drawString(0, -BLOCK_TOP_PAD - i * line_height, ln)


def draw_header_bar(c, val, top_center, base_size):
    """เขียนข้อความกึ่งกลางแถบเหลือง/แดงบนหัวฟอร์ม (ชื่อสารตัวใหญ่ / Signal Word)"""
    val = (val or "").strip()
    if not val or val == "-":
        return
    size, text = _fit_single_line(val, HEADER_BAR_MAX_WIDTH, base_size=base_size, min_size=7)
    c.setFont(FONT_BOLD, size)
    y = Y(top_center) - size * 0.35
    c.drawCentredString(HEADER_BAR_X_CENTER, y, text)


def draw_image_in_box(c, image_path, box):
    """วางรูปภาพให้พอดีกรอบ (box) แบบรักษาสัดส่วน (aspect ratio) และอยู่กึ่งกลาง"""
    if not image_path or not os.path.exists(image_path):
        return
    try:
        img = ImageReader(image_path)
        iw, ih = img.getSize()
    except Exception:
        return  # ไฟล์รูปเสียหรืออ่านไม่ได้ ข้ามไปเฉยๆ ไม่ทำให้สร้าง PDF พัง

    box_w = box["x1"] - box["x0"]
    box_h = box["bottom"] - box["top"]
    scale = min(box_w / iw, box_h / ih)
    draw_w, draw_h = iw * scale, ih * scale
    # จัดกึ่งกลางในกรอบ
    x = box["x0"] + (box_w - draw_w) / 2
    top_y = box["top"] + (box_h - draw_h) / 2
    y = Y(top_y) - draw_h
    c.drawImage(image_path, x, y, width=draw_w, height=draw_h,
                preserveAspectRatio=True, mask="auto")


def draw_pictograms(c, selected_keys):
    """
    วางสัญลักษณ์ GHS ที่เลือกไว้ในกล่องมุมซ้ายบน (PICTOGRAM_BOX)
    ถ้ามีหลายอัน จัดเรียงเป็นตาราง (grid) แบ่งพื้นที่กล่องเท่าๆ กัน เรียงตามลำดับมาตรฐานเสมอ
    (ไม่ใช่ตามลำดับที่ผู้ใช้ติ๊ก) เพื่อให้หน้าตาเหมือนกันทุกครั้ง
    """
    keys = [k for k in PICTOGRAM_ORDER if k in (selected_keys or [])]
    if not keys:
        return
    n = len(keys)
    cols = 1 if n == 1 else 2 if n <= 4 else 3
    rows = -(-n // cols)  # ceil division

    box_w = PICTOGRAM_BOX["x1"] - PICTOGRAM_BOX["x0"]
    box_h = PICTOGRAM_BOX["bottom"] - PICTOGRAM_BOX["top"]
    cell_w = box_w / cols
    cell_h = box_h / rows

    for i, key in enumerate(keys):
        icon_path = os.path.join(PICTOGRAM_ICON_DIR, f"{key}.png")
        row, col = divmod(i, cols)
        cell = {
            "x0": PICTOGRAM_BOX["x0"] + col * cell_w,
            "x1": PICTOGRAM_BOX["x0"] + (col + 1) * cell_w,
            "top": PICTOGRAM_BOX["top"] + row * cell_h,
            "bottom": PICTOGRAM_BOX["top"] + (row + 1) * cell_h,
        }
        draw_image_in_box(c, icon_path, cell)


def _cover_box(c, box):
    """วาดสี่เหลี่ยมสีขาวปิดข้อความตัวอย่างเดิมของเทมเพลต (เช่น '-' หรือ '(EHS Manager)')"""
    c.saveState()
    c.setFillColorRGB(1, 1, 1)
    c.rect(box["x0"], Y(box["bottom"]), box["x1"] - box["x0"],
           box["bottom"] - box["top"], fill=1, stroke=0)
    c.restoreState()


def build_overlay(data, label_image_path=None, container_image_path=None):
    register_thai_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    # แถบเหลือง (ชื่อสารเคมี ตัวใหญ่) / แถบแดง (Signal Word) บนหัวฟอร์ม
    draw_header_bar(c, data.get("display_name", ""), HEADER["display_name"]["top_center"], HEADER["display_name"]["size"])
    draw_header_bar(c, data.get("signal_word", ""), HEADER["signal_word"]["top_center"], HEADER["signal_word"]["size"])
    # ช่องบรรทัดเดียว (บังคับบรรทัดเดียวเสมอ กันล้นไปทับแถวถัดไปที่ติดกันมาก)
    for k, (x, top) in SHORT.items():
        val = (data.get(k) or "").strip()
        if val and val != "-" and k in SHORT_COVER:
            # เช่นช่อง pH เทมเพลตมีขีด "-" พิมพ์ไว้แล้ว ต้องปิดก่อนถ้ามีค่าจริงมาแทน
            _cover_box(c, SHORT_COVER[k])
        c.saveState(); c.translate(x, Y(top))
        draw_text(c, data.get(k, ""), _available_height(top, data), size=7,
                  single_line=True, max_width=_SHORT_MAX_WIDTH.get(k))
        c.restoreState()
    # ช่องข้อความยาว (ตัดบรรทัดแบบไทย + ลดฟอนต์อัตโนมัติถ้าจำเป็น)
    for k, (x, top) in BLOCK.items():
        c.saveState(); c.translate(x, Y(top))
        draw_text(c, data.get(k, ""), _available_height(top, data), BLOCK_MAX_WIDTH.get(k), size=7)
        c.restoreState()
    # ช่องจัดทำโดย/อนุมัติโดย (บรรทัดเดียว)
    for k, (x, top) in SIGNATURE.items():
        val = (data.get(k) or "").strip()
        if val and val != "-" and k in SIGNATURE_COVER:
            # ปิดข้อความตัวอย่างเดิมของเทมเพลตก่อน (เฉพาะตอนมีค่าจริงมาแทน)
            _cover_box(c, SIGNATURE_COVER[k])
        c.saveState(); c.translate(x, Y(top))
        draw_text(c, data.get(k, ""), 12, size=7, single_line=True,
                  max_width=SIGNATURE_MAX_WIDTH.get(k))
        c.restoreState()
    # NFPA เลขเดี่ยว วางกึ่งกลางสี่เหลี่ยมย่อยแต่ละสี ใช้สีขาวเพราะพื้นหลังเป็นสีเข้ม (แดง/น้ำเงิน)
    NFPA_SIZE = 11
    c.setFont(FONT_BOLD, NFPA_SIZE)
    c.setFillColorRGB(1, 1, 1)
    for k, (x_center, top_center) in NFPA.items():
        v = (data.get(k) or "").strip()
        if v:
            c.drawCentredString(x_center, Y(top_center) - NFPA_SIZE * 0.35, v)
    c.setFillColorRGB(0, 0, 0)
    # ช่องขาว (Special Hazard) - ตัวหนังสือสีดำ เพราะพื้นหลังเป็นสีขาว
    special_v = (data.get("nfpa_special") or "").strip()
    if special_v:
        special_size = 9
        c.setFont(FONT_BOLD, special_size)
        c.drawCentredString(NFPA_SPECIAL_X_CENTER, Y(NFPA_SPECIAL_TOP_CENTER) - special_size * 0.35, special_v)
    # รูปภาพ 2 ช่อง
    draw_image_in_box(c, label_image_path, IMAGE_BOXES["label_image"])
    draw_image_in_box(c, container_image_path, IMAGE_BOXES["container_image"])
    # สัญลักษณ์ GHS ที่ผู้ใช้ติ๊กเลือก (กล่องมุมซ้ายบน)
    draw_pictograms(c, data.get("pictograms"))
    c.showPage(); c.save(); buf.seek(0)
    return buf


def fill_from_data(data, template_path, out_path,
                    label_image_path=None, container_image_path=None):
    """รับ data dict ที่แก้ไขแล้วจาก UI + รูป (ถ้ามี) วางลงเทมเพลตแล้วเซฟไฟล์ PDF ใหม่"""
    overlay = PdfReader(build_overlay(data, label_image_path, container_image_path))
    base = PdfReader(template_path)
    writer = PdfWriter()
    page = base.pages[0]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)
    with open(out_path, "wb") as f:
        writer.write(f)
    return out_path


if __name__ == "__main__":
    from parser import parse_sds
    data = parse_sds("getpdf_sample.pdf")
    fill_from_data(data, "assets/Template.pdf", "data/generated/test_output.pdf")
    print("saved test_output.pdf")
