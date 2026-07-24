# -*- coding: utf-8 -*-
"""
database.py - จัดการฐานข้อมูล SQLite สำหรับ "ทะเบียนสารเคมี"
ใช้ sqlite3 มาตรฐานของ Python ไม่ต้องติดตั้ง library เพิ่ม ไม่ต้องตั้ง server แยก
เก็บทุกครั้งที่มีการ "สร้าง PDF" สำเร็จ ไว้เป็นประวัติให้ Admin ดู/แก้/ลบได้
"""
import os
import sqlite3
from datetime import datetime

# PROJECT_ROOT ต้องขึ้นไปอีก 1 ชั้นจากไฟล์นี้ เพราะย้ายเข้ามาอยู่ใน core/ แล้ว
# แต่โฟลเดอร์ data/ (runtime, ไม่ใช่โค้ด) ยังอยู่ที่รากโปรเจกต์เหมือนเดิม
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "chemsafe.db")


def get_connection():
    """เปิดการเชื่อมต่อฐานข้อมูล คืนแถวเป็น dict-like (sqlite3.Row) เพื่อใช้งานง่าย"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """สร้างตาราง records ถ้ายังไม่มี (เรียกตอนแอปเริ่มทำงาน)"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_name TEXT,
            cas TEXT,
            un TEXT,
            data_json TEXT NOT NULL,      -- ข้อมูลทุกฟิลด์ (แก้ไขแล้ว) เก็บเป็น JSON ก้อนเดียว
            output_filename TEXT,            -- ชื่อไฟล์ .xlsx ที่สร้างเสร็จ (อยู่ใน data/generated/)
            label_image_filename TEXT,    -- ชื่อไฟล์รูปสลากสารเคมี (อยู่ใน data/uploads/)
            container_image_filename TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def add_record(data, output_filename, label_image_filename=None, container_image_filename=None):
    """บันทึกทะเบียนสารเคมี 1 รายการ (output_filename คือไฟล์ .xlsx ที่สร้างเสร็จ) คืนค่า id ที่สร้าง"""
    import json
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO records
           (trade_name, cas, un, data_json, output_filename,
            label_image_filename, container_image_filename, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.get("trade_name", "-"),
            data.get("cas", "-"),
            data.get("un", "-"),
            json.dumps(data, ensure_ascii=False),
            output_filename,
            label_image_filename,
            container_image_filename,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def list_records():
    """คืนรายการทะเบียนสารเคมีทั้งหมด เรียงใหม่สุดก่อน"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM records ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_record(record_id):
    """คืนทะเบียนสารเคมี 1 รายการตาม id หรือ None ถ้าไม่เจอ"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_record(record_id, data):
    """แก้ไขข้อมูลของทะเบียนสารเคมี (ไม่แตะไฟล์ PDF/รูปเดิม)"""
    import json
    conn = get_connection()
    conn.execute(
        """UPDATE records SET trade_name=?, cas=?, un=?, data_json=? WHERE id=?""",
        (
            data.get("trade_name", "-"),
            data.get("cas", "-"),
            data.get("un", "-"),
            json.dumps(data, ensure_ascii=False),
            record_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_record(record_id):
    """ลบทะเบียนสารเคมี 1 รายการ (ไม่ลบไฟล์ PDF/รูปบนดิสก์ ให้ Admin ลบเองถ้าต้องการ)"""
    conn = get_connection()
    conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
