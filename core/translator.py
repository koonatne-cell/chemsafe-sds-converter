# -*- coding: utf-8 -*-
"""
translator.py - แปลข้อความอังกฤษ -> ไทย

ตอนนี้ใช้ deep-translator (ฟรี ไม่ต้องขอ API key) เพื่อให้เริ่มใช้งานได้ทันที
ในอนาคตถ้ามี Google Cloud Translation API key แล้ว ให้เปลี่ยนไปใช้ฟังก์ชัน
translate_with_google_cloud() แทน (โครงเตรียมไว้ให้ด้านล่าง) โดยไม่ต้องแก้ main.py เลย
เพราะ main.py เรียกผ่านฟังก์ชัน translate_text() / translate_fields() เท่านั้น
"""
import os
from deep_translator import GoogleTranslator

# อ่านค่าจาก environment variable (ตั้งค่าใน .env) ไม่ hardcode คีย์ในโค้ด
GOOGLE_TRANSLATE_API_KEY = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "")


def translate_text(text, source="en", target="th"):
    """แปลข้อความ 1 ก้อน คืนค่าเดิมถ้าแปลไม่ได้หรือค่าว่าง/ไม่มีความหมาย"""
    if not text or text.strip() in ("-", ""):
        return text
    try:
        result = GoogleTranslator(source=source, target=target).translate(text)
        return result if result else text
    except Exception:
        # ถ้าแปลไม่สำเร็จ (เช่น อินเทอร์เน็ตหลุด) ให้คืนค่าเดิมไว้ก่อน ไม่ทำให้แอปพัง
        return text


def _safe_translated(original, candidate):
    """คืนค่าแปลถ้าใช้ได้จริง (ไม่ว่างเปล่า) ไม่งั้นคืนค่าเดิม กันกรณี GoogleTranslator คืนค่าว่าง/
    เว้นวรรคล้วนโดยไม่ throw exception (เช่นโดน rate-limit จาก IP ของ hosting แล้ว Google ตอบกลับ
    หน้า error/captcha แทนคำแปลจริง - translate_text() เช็คแค่ผลลัพธ์ว่าง("")ตรงๆ ไม่ครอบคลุมกรณีนี้)
    ถ้าต้นฉบับเองว่างอยู่แล้วตั้งแต่แรก ก็ไม่ต้องเช็ค (ไม่มีอะไรให้เสียหาย)"""
    if original and str(original).strip() and not (candidate and str(candidate).strip()):
        return original
    return candidate


def translate_fields(data, keys, source="en", target="th"):
    """แปลหลายฟิลด์พร้อมกัน รับ dict ข้อมูล + list ของ key ที่ต้องการแปล คืน dict ใหม่
    ถ้าค่าของ key นั้นเป็น list (เช่น hazard_statements ของหน้าฉลาก) แปลทีละข้อความในลิสต์
    ทุกค่าที่แปลแล้วผ่าน _safe_translated() ก่อนเสมอ กันข้อมูลที่ผู้ใช้กรอก/ดึงมาแล้วหายไปเฉยๆ
    ถ้าการแปลล้มเหลวแบบเงียบๆ (ไม่ throw exception แต่คืนค่าว่าง)
    source/target สลับได้ (เช่น "th"->"en" ตอนผู้ใช้กด "แปลเป็นอังกฤษ" ย้อนกลับ)"""
    translated = dict(data)
    for k in keys:
        val = data.get(k, "")
        if isinstance(val, list):
            translated[k] = [_safe_translated(v, translate_text(v, source=source, target=target)) for v in val]
        else:
            translated[k] = _safe_translated(val, translate_text(val, source=source, target=target))
    return translated


def translate_with_google_cloud(text, source="en", target="th"):
    """
    ทางเลือกสำหรับอนาคต: เรียก Google Cloud Translation API v2 (REST) ด้วย API key จริง
    ต้องตั้ง GOOGLE_TRANSLATE_API_KEY ใน .env ก่อนใช้งาน
    """
    import requests
    if not GOOGLE_TRANSLATE_API_KEY:
        raise RuntimeError("ยังไม่ได้ตั้งค่า GOOGLE_TRANSLATE_API_KEY ใน .env")
    url = "https://translation.googleapis.com/language/translate/v2"
    params = {
        "q": text,
        "source": source,
        "target": target,
        "key": GOOGLE_TRANSLATE_API_KEY,
    }
    resp = requests.post(url, data=params, timeout=10)
    resp.raise_for_status()
    return resp.json()["data"]["translations"][0]["translatedText"]
