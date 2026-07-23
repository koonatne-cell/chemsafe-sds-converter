# -*- coding: utf-8 -*-
"""
label_template.py - สร้างฉลากสำหรับติดบนภาชนะบรรจุสารเคมี (secondary container label)

ต่างจาก fill_template.py (ที่วางค่าทับ Template.pdf ของบริษัทที่มีอยู่แล้ว) ฉลากนี้วาดขึ้นใหม่ทั้งหมด
ด้วย reportlab เพราะไม่มีเทมเพลตกระดาษตายตัว ขนาดหน้ากระดาษ = ขนาดฉลากที่เลือกจริงๆ (ไม่ใช่ A4)
เพื่อให้พิมพ์ด้วยเครื่องพิมพ์สติกเกอร์ที่ตัดกระดาษตามขนาดได้พอดีทันที

โครงฉลากอ้างอิงตามหัวข้อที่กฎหมาย GHS กำหนด + จัดหน้าให้ใกล้เคียงฉลากเคมีทั่วไปที่ใช้งานจริง:
  แถวบน:    ชื่อผลิตภัณฑ์ (ตัวใหญ่ กึ่งกลาง) + บรรทัดเล็ก CAS/UN No ใต้ชื่อ
  แถวสอง:   สัญลักษณ์ GHS (ซ้าย) + คำสัญญาณตัวหนาสีแดง (ขวา) อยู่แถวเดียวกัน
  ถัดไป:    Hazard statement / Precautionary statement - แต่ละข้อขึ้นบรรทัดใหม่
            รหัส (เช่น H314:) แสดงตัวหนา ตามด้วยข้อความปกติในบรรทัดเดียวกัน ไม่มีหัวข้อ/บูลเล็ตคั่น
  ท้ายฉลาก: ชื่อบริษัท (ตัวหนา) + ที่อยู่ + เบอร์ฉุกเฉิน

ฟอนต์ไทย/ฟังก์ชันตัดบรรทัด/วางรูปสัญลักษณ์ GHS ใช้ตัวเดียวกับ fill_template.py (ผ่านการทดสอบแล้ว
ว่าตัดบรรทัดภาษาไทย+อังกฤษได้ถูกต้อง ไม่จำเป็นต้องเขียนใหม่)
"""
import io
import os
import re
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

from fill_template import (
    register_thai_fonts, FONT_REGULAR, FONT_BOLD,
    wrap_thai, PICTOGRAM_ICON_DIR, PICTOGRAM_ORDER,
)

# ใช้ขนาด "กลาง" (100mm กว้าง) เป็นฐานอ้างอิงคำนวณสัดส่วนฟอนต์/ไอคอน ให้ขนาดอื่นย่อ/ขยายตามสัดส่วนจริง
_BASE_WIDTH_MM = 100
MARGIN_MM = 4
SIGNAL_COLOR = (0.75, 0.05, 0.05)  # สีแดงสำหรับคำสัญญาณ (Signal word) เหมือนฉลากเคมีทั่วไป

# รหัส Hazard/Precautionary statement ที่ขึ้นต้นบรรทัด (เช่น "H314", "P305+P351+P338")
# ใช้แยกส่วนรหัส (วาดตัวหนา) ออกจากข้อความบรรยาย (วาดตัวปกติ) ในบรรทัดเดียวกัน
_CODE_PREFIX_RE = re.compile(r"^([HP]\d{3}(?:\s*[/+]\s*[HP]?\d{3})*)[:\s]*(.*)$")


def _scale_for(width_mm):
    return width_mm / _BASE_WIDTH_MM


def _draw_statement(c, text, x, y_top, max_width, font_size, line_gap=1.5):
    """
    วาดข้อความ Hazard/Precautionary statement 1 ข้อ ขึ้นบรรทัดใหม่ ไม่มีบูลเล็ต/หัวข้อ
    ถ้าขึ้นต้นด้วยรหัส (H226, P305+P351+P338 ฯลฯ) วาดส่วนรหัส+โคลอนเป็นตัวหนา
    ตามด้วยข้อความบรรยายตัวปกติในบรรทัดเดียวกัน (บรรทัดต่อไปวาดตัวปกติทั้งหมด)
    คืน y ตำแหน่งถัดจากบรรทัดสุดท้าย
    """
    text = (text or "").strip()
    if not text or text == "-":
        return y_top

    m = _CODE_PREFIX_RE.match(text)
    prefix = ""
    if m and m.group(1):
        code = re.sub(r"\s+", "", m.group(1))
        rest = m.group(2).strip()
        prefix = code + ": "
        full = prefix + rest if rest else code + ":"
    else:
        full = text

    lines = wrap_thai(full, max_width, font_size=font_size)
    line_height = font_size + line_gap
    y = y_top
    for i, ln in enumerate(lines):
        code_part = prefix.strip()
        if i == 0 and prefix and ln.startswith(code_part):
            rest_part = ln[len(code_part):].strip()
            c.setFont(FONT_BOLD, font_size)
            c.drawString(x, y, code_part)
            code_w = stringWidth(code_part + " ", FONT_BOLD, font_size)
            c.setFont(FONT_REGULAR, font_size)
            c.drawString(x + code_w, y, rest_part)
        else:
            c.setFont(FONT_REGULAR, font_size)
            c.drawString(x, y, ln)
        y -= line_height
    return y


def build_label_pdf(data, size_key, size_presets, out_path):
    """
    สร้างฉลากภาชนะบรรจุ 1 หน้า ขนาดตาม size_key (ต้องตรงกับ key ใน size_presets)
    size_presets: list ของ (key, label, width_mm, height_mm) เหมือนใน fields.LABEL_SIZE_PRESETS
    data: dict ข้อมูลฉลาก (product_name, cas, un, signal_word, pictograms, hazard_statements,
          precautionary_statements, supplier_name, supplier_address, emergency_phone, supplemental_info)
    """
    register_thai_fonts()

    preset = next((p for p in size_presets if p[0] == size_key), size_presets[0])
    _, _, width_mm, height_mm = preset
    scale = _scale_for(width_mm)

    width_pt, height_pt = width_mm * mm, height_mm * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width_pt, height_pt))

    margin = MARGIN_MM * mm
    content_w = width_pt - 2 * margin
    x_left = margin
    y = height_pt - margin

    # กรอบขอบฉลาก (เส้นบาง ช่วยให้เห็นขอบตัดชัดตอนพิมพ์)
    c.setLineWidth(0.75)
    c.rect(margin * 0.4, margin * 0.4, width_pt - margin * 0.8, height_pt - margin * 0.8, stroke=1, fill=0)

    # ชื่อผลิตภัณฑ์ - ตัวใหญ่สุดบนฉลาก กึ่งกลาง (ตัวพิมพ์ใหญ่ทั้งหมดเหมือนฉลากเคมีทั่วไป
    # ไม่กระทบภาษาไทยเพราะ .upper() ไม่มีผลกับอักษรไทย)
    product_name = (data.get("product_name") or "-").strip()
    if product_name and product_name != "-":
        base_size = max(9, 15 * scale)
        lines = wrap_thai(product_name.upper(), content_w, font_size=base_size)
        c.setFont(FONT_BOLD, base_size)
        line_height = base_size + 2
        for ln in lines:
            y -= line_height
            c.drawCentredString(width_pt / 2, y, ln)

    # บรรทัดเล็ก CAS No / UN No รวมกัน ใต้ชื่อผลิตภัณฑ์
    cas = (data.get("cas") or "").strip()
    un = (data.get("un") or "").strip()
    id_parts = []
    if cas and cas != "-":
        id_parts.append(f"CAS {cas}")
    if un and un != "-":
        id_parts.append(f"UN {un}")
    if id_parts:
        id_size = max(6, 7.5 * scale)
        c.setFont(FONT_REGULAR, id_size)
        c.drawCentredString(width_pt / 2, y - id_size - 2, "  |  ".join(id_parts))
        y -= id_size + 8
    else:
        y -= 4

    # "Contains: ..." - รายชื่อสารเคมีอันตราย (จากตารางส่วนผสม Section 3 ถ้ามี) หนึ่งใน 6 องค์ประกอบ
    # ที่ GHS กำหนดให้ต้องมีบนฉลาก แยกจากชื่อผลิตภัณฑ์เพราะผลิตภัณฑ์อาจเป็นของผสมหลายสาร
    hazardous_substances = [s.strip() for s in (data.get("hazardous_substances") or []) if s and s.strip()]
    if hazardous_substances:
        contains_size = max(6, 7.5 * scale)
        contains_text = "Contains: " + ", ".join(hazardous_substances)
        lines = wrap_thai(contains_text, content_w, font_size=contains_size)
        c.setFont(FONT_REGULAR, contains_size)
        line_height = contains_size + 1.5
        for ln in lines:
            y -= line_height
            c.drawCentredString(width_pt / 2, y, ln)
        y -= 4

    y -= 4 * scale

    # แถวเดียวกัน: สัญลักษณ์ GHS (ซ้าย) + คำสัญญาณตัวหนาสีแดง (ขวา)
    selected = [k for k in PICTOGRAM_ORDER if k in (data.get("pictograms") or [])]
    signal_word = (data.get("signal_word") or "").strip()
    has_signal = signal_word and signal_word != "-"

    icon_size = max(26, 38 * scale)
    row_top_y = y

    if selected:
        gap = 4 * scale
        n = len(selected)
        icons_w = n * icon_size + (n - 1) * gap
        sig_size = max(11, 15 * scale) if has_signal else 0
        sig_w = stringWidth(signal_word.upper(), FONT_BOLD, sig_size) if has_signal else 0
        total_w = icons_w + (16 if has_signal else 0) + sig_w
        start_x = max(x_left, (width_pt - total_w) / 2)

        for i, key in enumerate(selected):
            icon_path = os.path.join(PICTOGRAM_ICON_DIR, f"{key}.png")
            icon_x = start_x + i * (icon_size + gap)
            if os.path.exists(icon_path):
                c.drawImage(icon_path, icon_x, row_top_y - icon_size, width=icon_size, height=icon_size,
                            preserveAspectRatio=True, mask="auto")
        if has_signal:
            c.setFont(FONT_BOLD, sig_size)
            c.setFillColorRGB(*SIGNAL_COLOR)
            sig_x = start_x + icons_w + 16
            sig_y = row_top_y - icon_size / 2 - sig_size * 0.35
            c.drawString(sig_x, sig_y, signal_word.upper())
            c.setFillColorRGB(0, 0, 0)
        y -= icon_size + 10 * scale
    elif has_signal:
        sig_size = max(11, 15 * scale)
        c.setFont(FONT_BOLD, sig_size)
        c.setFillColorRGB(*SIGNAL_COLOR)
        y -= sig_size
        c.drawCentredString(width_pt / 2, y, signal_word.upper())
        c.setFillColorRGB(0, 0, 0)
        y -= 10 * scale

    body_size = max(6.5, 8 * scale)

    # Hazard statements - แต่ละข้อขึ้นบรรทัดใหม่ ไม่มีหัวข้อ/บูลเล็ต (รหัสตัวหนา + ข้อความปกติ)
    for stmt in (data.get("hazard_statements") or []):
        y = _draw_statement(c, stmt, x_left, y, content_w, body_size)
    if data.get("hazard_statements"):
        y -= 3

    # Precautionary statements
    for stmt in (data.get("precautionary_statements") or []):
        y = _draw_statement(c, stmt, x_left, y, content_w, body_size)
    if data.get("precautionary_statements"):
        y -= 3

    # Supplemental information (ถ้ามี) - ผู้ใช้พิมพ์เองได้ ไม่ได้ดึงอัตโนมัติจาก SDS
    supplemental = (data.get("supplemental_info") or "").strip()
    if supplemental and supplemental != "-":
        lines = wrap_thai(supplemental, content_w, font_size=body_size)
        c.setFont(FONT_REGULAR, body_size)
        line_height = body_size + 1.5
        for ln in lines:
            c.drawString(x_left, y, ln)
            y -= line_height

    # ท้ายฉลาก - ข้อมูลผู้ผลิต/ผู้จำหน่าย (ชื่อบริษัทตัวหนา ตามด้วยที่อยู่/เบอร์ฉุกเฉินตัวปกติ)
    footer_size = max(5.5, 7 * scale)
    supplier_name = (data.get("supplier_name") or "").strip()
    supplier_address = (data.get("supplier_address") or "").strip()
    emergency_phone = (data.get("emergency_phone") or "").strip()

    footer_entries = []  # (text, bold?)
    if supplier_name and supplier_name != "-":
        footer_entries.append((supplier_name.upper(), True))
    if supplier_address and supplier_address != "-":
        footer_entries.append((supplier_address, False))
    if emergency_phone and emergency_phone != "-":
        footer_entries.append((f"Emergency: {emergency_phone}", False))

    if footer_entries:
        # คำนวณจำนวนบรรทัดทั้งหมดก่อน (รวม wrap) แล้ววางจากล่างขึ้นบน กันชนกรอบล่าง
        wrapped_all = []
        for text, bold in footer_entries:
            font = FONT_BOLD if bold else FONT_REGULAR
            for wl in wrap_thai(text, content_w, font_size=footer_size):
                wrapped_all.append((wl, font))
        footer_y = margin * 0.4 + 6
        line_h = footer_size + 1.5
        for i, (wl, font) in enumerate(reversed(wrapped_all)):
            c.setFont(font, footer_size)
            c.drawCentredString(width_pt / 2, footer_y + i * line_h, wl)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def fill_label(data, size_key, size_presets, out_path):
    """สร้างไฟล์ PDF ฉลาก แล้วเซฟลง out_path"""
    buf = build_label_pdf(data, size_key, size_presets, out_path)
    with open(out_path, "wb") as f:
        f.write(buf.read())
    return out_path


if __name__ == "__main__":
    from fields import LABEL_SIZE_PRESETS
    sample = {
        "product_name": "Sodium Hydroxide 50%",
        "cas": "1310-73-2",
        "un": "1824",
        "signal_word": "Danger",
        "pictograms": ["corrosive", "toxic"],
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
        "supplier_address": "",
        "emergency_phone": "1-800-555-CHEM",
        "supplemental_info": "",
    }
    fill_label(sample, "medium", LABEL_SIZE_PRESETS, "data/generated/test_label.pdf")
    print("saved test_label.pdf")
