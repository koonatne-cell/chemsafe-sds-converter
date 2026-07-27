# -*- coding: utf-8 -*-
"""
label_template.py - สร้างฉลากสำหรับติดบนภาชนะบรรจุสารเคมี (secondary container label)

เดิมวาดข้อความไหลลงมาเรื่อยๆ (ไม่มีกรอบแบ่งหัวข้อ) แต่ผู้ใช้ส่งเทมเพลตอ้างอิงมา (PDF ที่มี 7 หัวข้อ
เรียงเป็นกล่องสี่เหลี่ยม: ชื่อผลิตภัณฑ์ / ชื่อสารเคมีอันตราย / สัญลักษณ์ GHS / คำสัญญาณ / ข้อความแสดง
อันตราย / ข้อความระวัง / ผู้ผลิต) เลยเปลี่ยนมาวาดเป็น "กล่องมีเส้นขอบ" ตามหัวข้อนั้นแทน สัดส่วนความสูง
ของแต่ละกล่องวัดมาจากไฟล์ต้นแบบจริง (ดู BOX_WEIGHTS ด้านล่าง)

ยังคงใช้ reportlab วาดขึ้นใหม่ทั้งหมด (ไม่ใช่ overlay ทับไฟล์ PDF ต้นแบบตรงๆ) เพราะต้องรองรับหลายขนาด/
แนว (เล็ก/กลาง/ใหญ่/A4/A5/A6/กำหนดเอง, แนวตั้ง/แนวนอน) การวาดขึ้นใหม่ตามสัดส่วนทำให้ปรับขนาดได้
อิสระกว่าการ overlay ทับไฟล์ที่ล็อกขนาดหน้าไว้ตายตัว
"""
import io
import os
import re
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

from pdf_gen.fill_template import (
    register_thai_fonts, FONT_REGULAR, FONT_BOLD,
    wrap_thai, PICTOGRAM_ICON_DIR, PICTOGRAM_ORDER,
)

# ใช้ขนาด "กลาง" แนวตั้ง (150mm สูง) เป็นฐานอ้างอิงคำนวณสัดส่วนฟอนต์/ไอคอน - อ้างอิงจาก "ความสูง"
# ไม่ใช่ความกว้าง เพราะเลย์เอาต์นี้เรียงกล่อง 7 อันซ้อนกันในแนวตั้ง ตัวจำกัดพื้นที่จริงคือความสูงที่มี
# ให้ 7 กล่องแบ่งกันเสมอ (ถ้าอิงความกว้างแทน ตอนเลือก "แนวนอน" ความกว้างจะเพิ่มขึ้นแต่ความสูงกลับ
# ลดลง ฟอนต์จะยิ่งใหญ่เกินพื้นที่แนวตั้งที่เหลือน้อยลงจริง ทำให้ล้นกล่องทั้งหน้า)
_BASE_HEIGHT_MM = 150
MARGIN_MM = 5
SIGNAL_COLOR = (0.75, 0.05, 0.05)  # สีแดงสำหรับคำสัญญาณ (Signal word) เหมือนฉลากเคมีทั่วไป

# รหัส Hazard/Precautionary statement ที่ขึ้นต้นบรรทัด (เช่น "H314", "P305+P351+P338")
# ใช้แยกส่วนรหัส (วาดตัวหนา) ออกจากข้อความบรรยาย (วาดตัวปกติ) ในบรรทัดเดียวกัน
_CODE_PREFIX_RE = re.compile(r"^([HP]\d{3}(?:\s*[/+]\s*[HP]?\d{3})*)[:\s]*(.*)$")

# 7 หัวข้อตามเทมเพลตอ้างอิงที่ผู้ใช้ส่งมา (เลขข้อ, ป้ายไทย, ป้ายอังกฤษ, น้ำหนักความสูงกล่อง)
# น้ำหนักวัดสัดส่วนจริงจากไฟล์ต้นแบบ (กล่องชื่อผลิตภัณฑ์เตี้ยสุด กล่องผู้ผลิตสูงสุดเพราะมีที่อยู่ยาว)
BOX_ITEMS = [
    ("1", "ชื่อผลิตภัณฑ์", "Product Name", 1.00),
    ("2", "ชื่อสารเคมีอันตราย", "Hazardous Substances", 1.35),
    ("3", "รูปสัญลักษณ์", "GHS Pictograms", 1.35),
    ("4", "คำสัญญาณ", "Signal Words", 1.35),
    ("5", "ข้อความแสดงอันตราย", "Hazard Statements", 1.40),
    ("6", "ข้อความระวัง", "Precautionary Statements", 1.40),
    ("7", "ผู้ผลิต", "Manufacturing", 1.51),
]


def _scale_for(height_mm):
    return height_mm / _BASE_HEIGHT_MM


def _split_statement(text):
    """แยกข้อความ Hazard/Precautionary 1 ข้อ ออกเป็น (รหัสตัวหนา+colon, ข้อความที่เหลือ) ถ้ามีรหัส
    (H226, P305+P351+P338 ฯลฯ) นำหน้า คืน (None, text) ถ้าไม่มีรหัส (ข้อความบรรยายล้วนๆ)"""
    text = (text or "").strip()
    if not text or text == "-":
        return None, ""
    m = _CODE_PREFIX_RE.match(text)
    if m and m.group(1):
        code = re.sub(r"\s+", "", m.group(1))
        rest = m.group(2).strip()
        return code + ": ", rest
    return None, text


def _fit_paragraph(text, box_w, box_h, base_size, min_size=5, line_gap=1.8):
    """ลดฟอนต์จนข้อความ (ตัดบรรทัดแล้ว) พอดีกับกล่อง คืน (font_size, line_height, lines)
    ถ้าเล็กสุดแล้วยังไม่พอ ตัดบรรทัดส่วนเกินออกแล้วใส่ '…' ท้ายบรรทัดสุดท้าย"""
    # ความสูงที่ใช้จริง = ระยะขยับลงจากขอบบนของบรรทัดแรก (size) + (จำนวนบรรทัด-1) x line_h
    # (บรรทัดแรกกินพื้นที่แค่ "size" ไม่ใช่ "line_h" เพราะยังไม่มีช่องว่างระหว่างบรรทัดมาก่อนหน้า)
    size = base_size
    lines, line_h = [], base_size + line_gap
    while size >= min_size:
        lines = wrap_thai(text, box_w, font_size=size)
        line_h = size + line_gap
        used_h = size + max(0, len(lines) - 1) * line_h
        if used_h <= box_h:
            return size, line_h, lines
        size -= 0.5
    max_lines = max(1, int((box_h - min_size) // line_h) + 1)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip() + "…"
    return min_size, line_h, lines


def _fit_statement_list(statements, box_w, box_h, base_size, min_size=5, line_gap=1.8):
    """หาขนาดฟอนต์ที่ใหญ่สุดที่ทำให้รายการข้อความทั้งหมด (รวมกัน) พอดีความสูงกล่อง"""
    size = base_size
    while size >= min_size:
        total = 0
        for stmt in statements:
            _, rest = _split_statement(stmt)
            code, _ = _split_statement(stmt)
            full = (code + rest) if code else rest
            if full:
                total += len(wrap_thai(full, box_w, font_size=size))
        line_h = size + line_gap
        used_h = size + max(0, total - 1) * line_h
        if used_h <= box_h:
            return size
        size -= 0.5
    return min_size


def _draw_statements_in_box(c, statements, x, y_top, box_w, box_h, page_h, base_size):
    """วาดรายการ Hazard/Precautionary statement ในกล่อง (รหัสตัวหนา+colon นำหน้าข้อความปกติ)
    หยุดวาดถ้าเกินความสูงกล่อง (กันข้อความล้นทับกล่องถัดไป) คืนตำแหน่ง y ของบรรทัดสุดท้ายที่วาดจริง
    (ไม่ใช่ตำแหน่งบรรทัดถัดไปที่ยังไม่ได้วาด กันนับพื้นที่เกินจริงตอนคำนวณกล่องถัดไป)"""
    statements = [s for s in (statements or []) if (s or "").strip() and s.strip() != "-"]
    if not statements or box_h < 5:
        # ไม่มีที่เหลือพอจะวาดสักบรรทัดเลย (box_h ติดลบ/เกือบศูนย์) ข้ามไปเงียบๆ ดีกว่าฝืนวาด
        # แล้วล้นออกนอกกล่อง (พบตอนฉลากขนาดเล็กมากที่ชื่อสารกินพื้นที่จนไม่เหลือให้ CAS/UN)
        return y_top
    size = _fit_statement_list(statements, box_w, box_h, base_size)
    line_h = size + 1.8
    y = y_top + size  # ตำแหน่งบรรทัดถัดไปที่ "จะ" วาด (ยังไม่ได้วาดจริง)
    last_drawn_y = y
    bottom = y_top + box_h
    for stmt in statements:
        code, rest = _split_statement(stmt)
        full = (code + rest) if code else rest
        lines = wrap_thai(full, box_w, font_size=size)
        for i, ln in enumerate(lines):
            if y > bottom:
                return last_drawn_y
            if i == 0 and code and ln.startswith(code.strip()):
                code_txt = code.strip()
                rest_txt = ln[len(code_txt):].strip()
                c.setFont(FONT_BOLD, size)
                c.drawString(x, page_h - y, code_txt)
                code_w = stringWidth(code_txt + " ", FONT_BOLD, size)
                c.setFont(FONT_REGULAR, size)
                c.drawString(x + code_w, page_h - y, rest_txt)
            else:
                c.setFont(FONT_REGULAR, size)
                c.drawString(x, page_h - y, ln)
            last_drawn_y = y
            y += line_h
    return last_drawn_y


def _draw_paragraph_in_box(c, text, x, y_top, box_w, box_h, page_h, base_size,
                            center=False, bold=False, color=None, upper=False):
    """วาดข้อความยาว 1 ก้อน (ตัดบรรทัดอัตโนมัติ) ให้พอดีกล่อง คืนตำแหน่ง y ของบรรทัดสุดท้ายที่วาดจริง
    บวกช่องว่างเล็กน้อย (ไม่ใช่ y_top+size+n*line_h ที่จะเกินพื้นที่จริงไปหนึ่ง line_h เสมอ)"""
    text = (text or "").strip()
    if not text or text == "-" or box_h < 5:
        # box_h < 5: ไม่มีที่เหลือพอจะวาดสักบรรทัดเลย ข้ามไปเงียบๆ ดีกว่าฝืนวาดแล้วล้นออกนอกกล่อง
        return y_top
    if upper:
        text = text.upper()
    size, line_h, lines = _fit_paragraph(text, box_w, box_h, base_size)
    c.setFont(FONT_BOLD if bold else FONT_REGULAR, size)
    if color:
        c.setFillColorRGB(*color)
    y = y_top + size
    cx = x + box_w / 2
    for ln in lines:
        if center:
            c.drawCentredString(cx, page_h - y, ln)
        else:
            c.drawString(x, page_h - y, ln)
        last_drawn_y = y
        y += line_h
    y = last_drawn_y + line_h * 0.35  # ช่องว่างเล็กน้อยก่อนเนื้อหาถัดไป (ถ้ามี) ไม่ใช่เต็ม line_h
    if color:
        c.setFillColorRGB(0, 0, 0)
    return y


def _draw_pictograms_in_box(c, pictogram_keys, x, y_top, box_w, box_h, page_h):
    """วาดไอคอน GHS เรียงแถวเดียว กึ่งกลางทั้งแนวนอน/แนวตั้งของกล่อง"""
    keys = [k for k in PICTOGRAM_ORDER if k in (pictogram_keys or [])]
    if not keys:
        return
    n = len(keys)
    gap = box_w * 0.02
    max_icon_w = (box_w - (n - 1) * gap) / n
    icon_size = min(box_h * 0.9, max_icon_w)
    row_w = n * icon_size + (n - 1) * gap
    start_x = x + (box_w - row_w) / 2
    icon_top = y_top + (box_h - icon_size) / 2
    for i, key in enumerate(keys):
        icon_path = os.path.join(PICTOGRAM_ICON_DIR, f"{key}.png")
        if os.path.exists(icon_path):
            icon_x = start_x + i * (icon_size + gap)
            c.drawImage(icon_path, icon_x, page_h - icon_top - icon_size, width=icon_size, height=icon_size,
                        preserveAspectRatio=True, mask="auto")


def build_label_pdf(data, size_key, size_presets, out_path, orientation="portrait"):
    """
    สร้างฉลากภาชนะบรรจุ 1 หน้า ขนาดตาม size_key (ต้องตรงกับ key ใน size_presets) เป็นกล่อง 7 หัวข้อ
    ตามเทมเพลตอ้างอิงที่ผู้ใช้ส่งมา (ดู BOX_ITEMS)
    size_presets: list ของ (key, label, width_mm, height_mm) เหมือนใน fields.LABEL_SIZE_PRESETS
    data: dict ข้อมูลฉลาก (product_name, cas, un, signal_word, pictograms, hazardous_substances,
          hazard_statements, precautionary_statements, supplier_name, supplier_address,
          emergency_phone, custom_width_mm/custom_height_mm ถ้า size_key="custom")
    orientation: "portrait" (แนวตั้ง, ค่าเริ่มต้น) หรือ "landscape" (แนวนอน - สลับกว้าง/สูง)
    """
    register_thai_fonts()

    preset = next((p for p in size_presets if p[0] == size_key), size_presets[0])
    _, _, width_mm, height_mm = preset
    if width_mm is None or height_mm is None:
        # "custom" ไม่มีขนาดตายตัวใน preset - ผู้ใช้กรอกกว้าง/สูงเองมาใน data
        # ถ้ากรอกไม่ใช่ตัวเลข (หรือว่างไว้) fallback เป็นขนาด "กลาง" กันสร้าง PDF พังไปเลย
        try:
            width_mm = float(data.get("custom_width_mm") or 100)
        except (TypeError, ValueError):
            width_mm = 100
        try:
            height_mm = float(data.get("custom_height_mm") or 150)
        except (TypeError, ValueError):
            height_mm = 150
        width_mm = max(20, width_mm)
        height_mm = max(20, height_mm)
    if orientation == "landscape":
        width_mm, height_mm = height_mm, width_mm
    scale = _scale_for(height_mm)

    width_pt, height_pt = width_mm * mm, height_mm * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width_pt, height_pt))

    margin = MARGIN_MM * mm
    box_x = margin
    box_w = width_pt - 2 * margin
    inner_pad = 3 * scale

    # เส้นขอบรอบนอกทั้งหน้า (เหมือนเทมเพลตอ้างอิง)
    c.setLineWidth(0.75)
    c.rect(margin * 0.4, margin * 0.4, width_pt - margin * 0.8, height_pt - margin * 0.8, stroke=1, fill=0)

    label_size = max(6.5, 8.5 * scale)
    label_line_h = label_size + 6 * scale
    gap_after_box = 6 * scale

    total_weight = sum(w for *_, w in BOX_ITEMS)
    fixed_overhead = len(BOX_ITEMS) * (label_line_h + gap_after_box)
    available_h = height_pt - 2 * margin
    box_total_h = max(available_h - fixed_overhead, available_h * 0.3)

    body_size = max(6, 8 * scale)
    y = margin  # ระยะจากขอบบนของหน้า (เพิ่มขึ้นเรื่อยๆ ตอนวาดลงมา)

    for num, label_th, label_en, weight in BOX_ITEMS:
        # ป้ายหัวข้อ "N.ป้ายไทย (English)" เหนือกล่อง
        c.setFont(FONT_BOLD, label_size)
        c.drawString(box_x, height_pt - y - label_size, f"{num}.{label_th} ({label_en})")
        y += label_line_h

        this_box_h = box_total_h * (weight / total_weight)
        c.setLineWidth(0.75)
        c.rect(box_x, height_pt - y - this_box_h, box_w, this_box_h, stroke=1, fill=0)

        inner_x = box_x + inner_pad
        inner_y = y + inner_pad
        inner_w = box_w - 2 * inner_pad
        inner_h = this_box_h - 2 * inner_pad

        if num == "1":
            # ชื่อผลิตภัณฑ์ (ตัวใหญ่ ตัวหนา กึ่งกลาง) + บรรทัดเล็ก CAS/UN ใต้ชื่อ
            # จองพื้นที่ CAS/UN ไว้ก่อนเป็นสัดส่วนคงที่ (ไม่ใช่แบ่ง 68/32 แล้วปล่อยให้ชื่อผลิตภัณฑ์ใช้
            # เกินจำเป็น เพราะชื่อสั้นๆ พอดีกับฟอนต์ใหญ่สุดในบรรทัดเดียวอยู่แล้ว ไม่ยอมลดขนาดลงเอง
            # ทำให้ก่อนหน้านี้ไม่เหลือที่ให้ CAS/UN เลยจนถูกข้ามไปเงียบๆ)
            cas = (data.get("cas") or "").strip()
            un = (data.get("un") or "").strip()
            id_parts = ([f"CAS {cas}"] if cas and cas != "-" else []) + ([f"UN {un}"] if un and un != "-" else [])
            id_size = max(6, 7 * scale)
            cas_reserved_h = (id_size + 3) if id_parts else 0
            name_h = max(inner_h * 0.5, inner_h - cas_reserved_h)
            ny = _draw_paragraph_in_box(c, data.get("product_name"), inner_x, inner_y, inner_w, name_h,
                                        height_pt, max(9, 13 * scale), center=True, bold=True, upper=True)
            if id_parts:
                _draw_paragraph_in_box(c, "  |  ".join(id_parts), inner_x, ny, inner_w,
                                       inner_h - (ny - inner_y), height_pt, id_size, center=True)
        elif num == "2":
            substances = [s.strip() for s in (data.get("hazardous_substances") or []) if s and s.strip()]
            _draw_paragraph_in_box(c, ", ".join(substances), inner_x, inner_y, inner_w, inner_h,
                                   height_pt, body_size)
        elif num == "3":
            _draw_pictograms_in_box(c, data.get("pictograms"), inner_x, inner_y, inner_w, inner_h, height_pt)
        elif num == "4":
            _draw_paragraph_in_box(c, data.get("signal_word"), inner_x, inner_y, inner_w, inner_h, height_pt,
                                   max(9, 13 * scale), center=True, bold=True, color=SIGNAL_COLOR, upper=True)
        elif num == "5":
            _draw_statements_in_box(c, data.get("hazard_statements"), inner_x, inner_y, inner_w, inner_h,
                                    height_pt, body_size)
        elif num == "6":
            _draw_statements_in_box(c, data.get("precautionary_statements"), inner_x, inner_y, inner_w, inner_h,
                                    height_pt, body_size)
        elif num == "7":
            supplier_name = (data.get("supplier_name") or "").strip()
            supplier_address = (data.get("supplier_address") or "").strip()
            emergency_phone = (data.get("emergency_phone") or "").strip()
            ny = inner_y
            if supplier_name and supplier_name != "-":
                ny = _draw_paragraph_in_box(c, supplier_name, inner_x, ny, inner_w, inner_h - (ny - inner_y),
                                            height_pt, max(7, 9 * scale), bold=True)
            if supplier_address and supplier_address != "-":
                ny = _draw_paragraph_in_box(c, supplier_address, inner_x, ny, inner_w, inner_h - (ny - inner_y),
                                            height_pt, body_size)
            if emergency_phone and emergency_phone != "-":
                _draw_paragraph_in_box(c, f"Emergency: {emergency_phone}", inner_x, ny, inner_w,
                                       inner_h - (ny - inner_y), height_pt, body_size)

        y += this_box_h + gap_after_box

    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def fill_label(data, size_key, size_presets, out_path, orientation="portrait"):
    """สร้างไฟล์ PDF ฉลาก แล้วเซฟลง out_path"""
    buf = build_label_pdf(data, size_key, size_presets, out_path, orientation=orientation)
    with open(out_path, "wb") as f:
        f.write(buf.read())
    return out_path


if __name__ == "__main__":
    # รันจากรากโปรเจกต์ด้วย: python -m pdf_gen.label_template (import แบบ package ต้องใช้ -m)
    from core.fields import LABEL_SIZE_PRESETS
    sample = {
        "product_name": "Sodium Hydroxide 50%",
        "cas": "1310-73-2",
        "un": "1824",
        "signal_word": "Danger",
        "pictograms": ["corrosive", "toxic"],
        "hazardous_substances": ["Sodium hydroxide", "Water"],
        "hazard_statements": [
            "H314 Causes severe skin burns and eye damage.",
            "H318 Causes serious eye damage.",
        ],
        "precautionary_statements": [
            "P260/P280 Do not breathe mist/vapours. Wear PPE (gloves/clothing/eye/face protection).",
            "P301+P310+P330+P338 IF SWALLOWED: Rinse mouth. No vomiting. IF IN EYES: Rinse continuously. "
            "Seek emergency medical aid immediately.",
        ],
        "supplier_name": "Apex Chemical Corp.",
        "supplier_address": "123 Industrial Estate, Chonburi 20000",
        "emergency_phone": "1-800-555-CHEM",
    }
    fill_label(sample, "medium", LABEL_SIZE_PRESETS, "data/generated/test_label.pdf")
    print("saved test_label.pdf")
