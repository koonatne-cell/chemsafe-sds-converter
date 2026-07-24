// app.js - จัดการฟอร์มฝั่งเว็บ (ไม่มี framework ใช้ JS ธรรมดา)

const parseBtn = document.getElementById("parseBtn");
const parseStatus = document.getElementById("parseStatus");
const translateBtn = document.getElementById("translateBtn");
const translateStatus = document.getElementById("translateStatus");
const generateBtn = document.getElementById("generateBtn");
const generateStatus = document.getElementById("generateStatus");
const downloadLink = document.getElementById("downloadLink");
const sdsForm = document.getElementById("sdsForm");

function setStatus(el, text, kind) {
    el.textContent = text;
    el.className = "status " + (kind || "");
}

// อ่านค่าปัจจุบันจากฟอร์มทั้งหมด คืนเป็น dict {key: value} (pictograms เป็น array แยกต่างหาก)
function collectFormData() {
    const data = {};
    const fields = sdsForm.querySelectorAll("textarea, input[type=text], select");
    fields.forEach((el) => { data[el.name] = el.value; });
    data.pictograms = Array.from(
        sdsForm.querySelectorAll("input[name=pictograms]:checked")
    ).map((el) => el.value);
    return data;
}

// เอา dict ข้อมูลไปใส่ในช่องฟอร์ม
// หมายเหตุ: ปิดการติ๊กสัญลักษณ์ GHS อัตโนมัติไว้ก่อน (เดาจากคำในไฟล์ยังไม่แม่นพอ) ให้ผู้ใช้ติ๊กเลือกเอง
// ทั้งหมด - ถ้าจะเปิดกลับมาทีหลัง ดึง data.pictograms ที่ backend ส่งมาแล้วก็อปมาติ๊กเหมือนฟิลด์อื่นได้เลย
function fillFormData(data) {
    Object.keys(data).forEach((key) => {
        if (key === "pictograms") return;
        const el = document.getElementById("f_" + key);
        if (el) el.value = data[key] ?? "";
    });
}

// ---------- ขั้นตอนที่ 1: ดึงข้อมูลจาก SDS ----------
parseBtn.addEventListener("click", async () => {
    const fileInput = document.getElementById("sdsFile");
    if (!fileInput.files.length) {
        setStatus(parseStatus, "กรุณาเลือกไฟล์ SDS (.pdf) ก่อน", "err");
        return;
    }
    setStatus(parseStatus, "กำลังดึงข้อมูล...", "busy");
    parseBtn.disabled = true;

    const formData = new FormData();
    formData.append("sds_file", fileInput.files[0]);

    try {
        const res = await fetch("/api/parse", { method: "POST", body: formData });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "ดึงข้อมูลไม่สำเร็จ");
        }
        const json = await res.json();
        fillFormData(json.data);
        setStatus(parseStatus, "ดึงข้อมูลสำเร็จ – ตรวจ/แก้ไขด้านล่างก่อนสร้าง PDF", "ok");
    } catch (ex) {
        setStatus(parseStatus, "ผิดพลาด: " + ex.message, "err");
    } finally {
        parseBtn.disabled = false;
    }
});

// ---------- ขั้นตอนที่ 2: แปลเป็นไทย ----------
translateBtn.addEventListener("click", async () => {
    setStatus(translateStatus, "กำลังแปล...", "busy");
    translateBtn.disabled = true;
    try {
        const data = collectFormData();
        const res = await fetch("/api/translate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ data }),
        });
        if (!res.ok) throw new Error("แปลไม่สำเร็จ");
        const json = await res.json();
        fillFormData(json.data);
        setStatus(translateStatus, "แปลเสร็จแล้ว – ตรวจคำแปลอีกครั้งก่อนสร้าง PDF", "ok");
    } catch (ex) {
        setStatus(translateStatus, "ผิดพลาด: " + ex.message, "err");
    } finally {
        translateBtn.disabled = false;
    }
});

// ---------- ขั้นตอนที่ 3: พรีวิวรูปภาพ ----------
function setupImagePreview(inputId, previewId) {
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);
    input.addEventListener("change", () => {
        if (input.files.length) {
            preview.src = URL.createObjectURL(input.files[0]);
            preview.classList.remove("hidden");
        } else {
            preview.classList.add("hidden");
        }
    });
}
setupImagePreview("labelImage", "labelImagePreview");
setupImagePreview("containerImage", "containerImagePreview");

// ---------- ขั้นตอนที่ 4: สร้าง + ดาวน์โหลด PDF ----------
generateBtn.addEventListener("click", async () => {
    setStatus(generateStatus, "กำลังสร้าง PDF...", "busy");
    generateBtn.disabled = true;
    downloadLink.classList.add("hidden");

    try {
        const data = collectFormData();
        const formData = new FormData();
        // ส่งเป็น Blob (ไฟล์) แทนข้อความล้วน กัน multipart decode ภาษาไทยผิดเป็น latin-1
        const dataBlob = new Blob([JSON.stringify(data)], { type: "application/json" });
        formData.append("data", dataBlob, "data.json");

        const labelFile = document.getElementById("labelImage").files[0];
        const containerFile = document.getElementById("containerImage").files[0];
        if (labelFile) formData.append("label_image", labelFile);
        if (containerFile) formData.append("container_image", containerFile);

        const res = await fetch("/api/generate", { method: "POST", body: formData });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "สร้าง PDF ไม่สำเร็จ");
        }
        const json = await res.json();
        downloadLink.href = json.download_url;
        downloadLink.classList.remove("hidden");
        setStatus(generateStatus, "สร้างเสร็จแล้ว กดปุ่ม \"ดาวน์โหลด PDF\" เพื่อบันทึกลงเครื่อง", "ok");
    } catch (ex) {
        setStatus(generateStatus, "ผิดพลาด: " + ex.message, "err");
    } finally {
        generateBtn.disabled = false;
    }
});
