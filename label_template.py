# -*- coding: utf-8 -*-
"""
label_template.py - สร้างฉลากสำหรับติดบนภาชนะบรรจุสารเคมี (secondary container label)

ต่างจาก fill_template.py (ที่วางค่าทับ Template.pdf ของบริษัทที่มีอยู่แล้ว) ฉลากนี้วาดขึ้นใหม่ทั้งหมด
ด้วย reportlab เพราะไม่มีเทมเพลตกระดาษตายตัว ขนาดหน้ากระดาษ = ขนาดฉลากที่เลือกจริงๆ (ไม่ใช่ A4)
เพื่อให้พิมพ์ด้วยเครื่องพิมพ์สติกเกอร์ที่ตัดกระดาษตามขนาดได้พอดีทันที

โครงฉลากอ้างอิงตามหัวข้อที่กฎหมาย GHS กำหนด (ดูตัวอย่าง SAMPLE LABEL):
  a) Product identifier      b) Supplier identification
  c) Hazard pictograms       d) Signal word
  e) Hazard statement(s)     f) Precautionary statement(s)
  g) Supplemental information (ถ้ามี)

ฟอนต์ไทย/ฟังก์ชันตัดบรรทัด/วางรูปสัญลักษณ์ GHS ใช้ตัวเดียวกับ fill_template.py (ผ่านการทดสอบแล้ว
ว่าตัดบรรทัดภาษาไทย+อังกฤษได้ถูกต้อง ไม่จำเป็นต้องเขียนใหม่)
"""
import io
import os
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

from fill_template import (
    register_thai_fonts, FONT_REGULAR, FONT_BOLD,
    wrap_thai, draw_image_in_box, PICTOGRAM_ICON_DIR, PICTOGRAM_ORDER,
)

# ใช้ขนาด "กลาง" (100mm กว้าง) เป็นฐานอ้างอิงคำนวณสัดส่วนฟอนต์/ไอคอน ให้ขนาดอื่นย่อ/ขยายตามสัดส่วนจริง
_BASE_WIDTH_MM = 100
MARGIN_MM = 4


def _scale_for(width_mm):
    return width_mm / _BASE_WIDTH_MM


def _fit_single_line(val, max_width, base_size, min_size, font=FONT_BOLD):
    """ลดฟอนต์จนพอดีความกว้าง (pt) ถ้าเล็กสุดแล้วยังไม่พอ ตัดข้อความแล้วใส่ '…'"""
    size = base_size
    while size >= min_size:
        if stringWidth(val, font, size) <= max_width:
            return size, val
        size -= 0.5
    text = val
    while len(text) > 1 and stringWidth(text + "…", font, min_size) > max_width:
        text = text[:-1]
    return min_size, text.rstrip() + "…"


def _draw_wrapped(c, text, x, y_top, max_width, font_size, font=FONT_REGULAR, line_gap=1.3, bullet=False):
    """วาดข้อความตัดบรรทัด (ใช้ wrap_thai เดิม) เริ่มจาก y_top ไล่ลงมา คืน y ตำแหน่งถัดจากบรรทัดสุดท้าย"""
    text = (text or "").strip()
    if not text or text == "-":
        return y_top
    indent = font_size * 0.9 if bullet else 0
    lines = wrap_thai(text, max_width - indent, font_size=font_size)
    c.setFont(font, font_size)
    line_height = font_size + line_gap
    y = y_top
    for i, ln in enumerate(lines):
        prefix = "• " if (bullet and i == 0) else ("  " if bullet else "")
        c.drawString(x + indent, y, prefix + ln if i == 0 else ln)
        y -= line_height
    return y


def build_label_pdf(data, size_key, size_presets, out_path):
    """
    สร้างฉลากภาชนะบรรจุ 1 หน้า ขนาดตาม size_key (ต้องตรงกับ key ใน size_presets)
    size_presets: list ของ (key, label, width_mm, height_mm) เหมือนใน fields.LABEL_SIZE_PRESETS
    data: dict ข้อมูลฉลาก (product_name, cas, signal_word, pictograms, hazard_statements,
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
    y = height_pt - margin

    # กรอบขอบฉลาก (เส้นบาง ช่วยให้เห็นขอบตัดชัดตอนพิมพ์)
    c.setLineWidth(0.75)
    c.rect(margin * 0.4, margin * 0.4, width_pt - margin * 0.8, height_pt - margin * 0.8, stroke=1, fill=0)

    # a) Product identifier - ชื่อผลิตภัณฑ์ ตัวใหญ่สุดบนฉลาก อยู่กึ่งกลางด้านบน
    product_name = (data.get("product_name") or "-").strip()
    if product_name and product_name != "-":
        base_size = max(9, 15 * scale)
        lines = wrap_thai(product_name, content_w, font_size=base_size)
        c.setFont(FONT_BOLD, base_size)
        line_height = base_size + 2
        for ln in lines:
            y -= line_height
            c.drawCentredString(width_pt / 2, y, ln)
        y -= 4 * scale

    # CAS No (ถ้ามี) แสดงเล็กๆ ใต้ชื่อผลิตภัณฑ์
    cas = (data.get("cas") or "").strip()
    if cas and cas != "-":
        cas_size = max(6, 8 * scale)
        c.setFont(FONT_REGULAR, cas_size)
        c.drawCentredString(width_pt / 2, y - cas_size, f"CAS No: {cas}")
        y -= cas_size + 6

    y -= 4

    # c) Hazard pictograms - แถวไอคอนกึ่งกลาง
    selected = [k for k in PICTOGRAM_ORDER if k in (data.get("pictograms") or [])]
    if selected:
        icon_size = max(28, 42 * scale)
        gap = 6 * scale
        n = len(selected)
        row_w = n * icon_size + (n - 1) * gap
        start_x = (width_pt - row_w) / 2
        top = height_pt - y  # แปลงเป็นระบบ top (จากบน) ให้ตรงกับ draw_image_in_box
        for i, key in enumerate(selected):
            icon_path = os.path.join(PICTOGRAM_ICON_DIR, f"{key}.png")
            box = {
                "x0": start_x + i * (icon_size + gap),
                "x1": start_x + i * (icon_size + gap) + icon_size,
                "top": top,
                "bottom": top + icon_size,
            }
            # draw_image_in_box ใช้ระบบพิกัด reportlab เดิม (Y() คำนวณจาก PAGE_H ของ fill_template)
            # ในไฟล์นี้หน้ากระดาษคนละขนาด เลยวาดรูปเองตรงๆ แทนเรียก draw_image_in_box
            if os.path.exists(icon_path):
                c.drawImage(icon_path, box["x0"], y - icon_size, width=icon_size, height=icon_size,
                            preserveAspectRatio=True, mask="auto")
        y -= icon_size + 8 * scale

    # d) Signal word - ตัวหนา กึ่งกลาง
    signal_word = (data.get("signal_word") or "").strip()
    if signal_word and signal_word != "-":
        sig_size = max(10, 13 * scale)
        c.setFont(FONT_BOLD, sig_size)
        y -= sig_size
        c.drawCentredString(width_pt / 2, y, signal_word)
        y -= 8 * scale

    body_size = max(6.5, 8 * scale)
    x_left = margin

    # e) Hazard statements - รายการ ข้อความละบรรทัด (bullet)
    hazard_statements = data.get("hazard_statements") or []
    if hazard_statements:
        c.setFont(FONT_BOLD, body_size)
        y -= body_size
        c.drawString(x_left, y, "อันตราย / Hazard statements:")
        y -= body_size + 2
        for stmt in hazard_statements:
            y = _draw_wrapped(c, stmt, x_left, y, content_w, body_size, bullet=True)
        y -= 4

    # f) Precautionary statements
    precautionary_statements = data.get("precautionary_statements") or []
    if precautionary_statements:
        c.setFont(FONT_BOLD, body_size)
        y -= body_size
        c.drawString(x_left, y, "ข้อควรระวัง / Precautionary statements:")
        y -= body_size + 2
        for stmt in precautionary_statements:
            y = _draw_wrapped(c, stmt, x_left, y, content_w, body_size, bullet=True)
        y -= 4

    # g) Supplemental information (ถ้ามี) - ผู้ใช้พิมพ์เองได้ ไม่ได้ดึงอัตโนมัติจาก SDS
    supplemental = (data.get("supplemental_info") or "").strip()
    if supplemental and supplemental != "-":
        y -= body_size
        c.setFont(FONT_BOLD, body_size)
        c.drawString(x_left, y, "ข้อมูลเพิ่มเติม:")
        y -= body_size + 2
        y = _draw_wrapped(c, supplemental, x_left, y, content_w, body_size)
        y -= 4

    # b) Supplier identification - ท้ายฉลาก ตัวเล็ก
    footer_size = max(5.5, 7 * scale)
    footer_lines = []
    supplier_name = (data.get("supplier_name") or "").strip()
    supplier_address = (data.get("supplier_address") or "").strip()
    emergency_phone = (data.get("emergency_phone") or "").strip()
    if supplier_name and supplier_name != "-":
        footer_lines.append(supplier_name)
    if supplier_address and supplier_address != "-":
        footer_lines.append(supplier_address)
    if emergency_phone and emergency_phone != "-":
        footer_lines.append(f"โทรฉุกเฉิน / Emergency: {emergency_phone}")

    if footer_lines:
        footer_y = margin * 0.4 + 6
        c.setFont(FONT_REGULAR, footer_size)
        # วางจากล่างขึ้นบน (บรรทัดสุดท้ายอยู่ล่างสุด) กันชนกรอบล่าง
        for i, ln in enumerate(reversed(footer_lines)):
            wrapped = wrap_thai(ln, content_w, font_size=footer_size)
            for j, wl in enumerate(reversed(wrapped)):
                c.drawCentredString(width_pt / 2, footer_y + (i * len(wrapped) + j) * (footer_size + 1.5), wl)

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
        "product_name": "โซดาไฟเหลว 32% (Sodium Hydroxide Solution)",
        "cas": "1310-73-2",
        "signal_word": "อันตราย (Danger)",
        "pictograms": ["corrosive"],
        "hazard_statements": ["H314 Causes severe skin burns and eye damage."],
        "precautionary_statements": [
            "P280 Wear protective gloves/eye protection.",
            "P305+P351+P338 IF IN EYES: Rinse cautiously with water for several minutes.",
        ],
        "supplier_name": "Pringles Chonburi Factory",
        "supplier_address": "123 หมู่ 4 ต.บ่อวิน อ.ศรีราชา จ.ชลบุรี 20230",
        "emergency_phone": "088-053-8789",
        "supplemental_info": "",
    }
    fill_label(sample, "medium", LABEL_SIZE_PRESETS, "data/generated/test_label.pdf")
    print("saved test_label.pdf")
