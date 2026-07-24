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


def translate_fields(data, keys):
    """แปลหลายฟิลด์พร้อมกัน รับ dict ข้อมูล + list ของ key ที่ต้องการแปล คืน dict ใหม่
    ถ้าค่าของ key นั้นเป็น list (เช่น hazard_statements ของหน้าฉลาก) แปลทีละข้อความในลิสต์"""
    translated = dict(data)
    for k in keys:
        val = data.get(k, "")
        if isinstance(val, list):
            translated[k] = [translate_text(v) for v in val]
        else:
            translated[k] = translate_text(val)
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
