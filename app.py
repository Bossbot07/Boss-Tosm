from flask import Flask, render_template_string, jsonify, request
from datetime import datetime, timedelta
import pytz
import json
import os

app = Flask(__name__)
DATA_FILE = "boss_data.json"
BKK_TZ = pytz.timezone('Asia/Bangkok')

def get_bkk_now():
    return datetime.now(pytz.utc).astimezone(BKK_TZ)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    "active_spawns": data.get("active_spawns", {}),
                    "in_phase": data.get("in_phase", {})
                }
        except:
            pass
    return {"active_spawns": {}, "in_phase": {}}

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ บันทึกไฟล์ไม่ได้: {e}")

def update_boss_statuses():
    boss_db = load_data()
    now = get_bkk_now()
    has_change = False

    # 1. เช็คบอสรอเกิด -> ย้ายไป In Phase
    for key, t_str in list(boss_db["active_spawns"].items()):
        try:
            target_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
            if now >= target_time:
                boss_db["in_phase"][key] = t_str
                boss_db["active_spawns"].pop(key, None)
                has_change = True
        except: continue

    # 2. เช็คบอสในเฟส -> ถ้าเกิน 30 นาทีให้ลบออกอัตโนมัติ
    for key, t_str in list(boss_db["in_phase"].items()):
        try:
            spawn_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
            if now >= (spawn_time + timedelta(minutes=30)):
                boss_db["in_phase"].pop(key, None)
                has_change = True
        except: continue

    if has_change:
        save_data(boss_db)
    return boss_db

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TOSM Boss Tracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: sans-serif; }
        .card { background-color: #1e1e1e; border: 1px solid #333; color: #fff; }
        .in-phase-bg { border-left: 5px solid #ff4757; }
        .upcoming-bg { border-left: 5px solid #2ed573; }
    </style>
</head>
<body class="container py-4">
    <h2 class="text-center mb-4 text-warning">⚔️ TOSM BOSS TRACKER ⚔️</h2>
    
    <div class="card p-3 mb-4">
        <h5>➕ บันทึกบอสใหม่</h5>
        <form action="/add" method="POST" class="row g-2">
            <div class="col-4"><input type="text" name="boss_id" class="form-control bg-dark text-white" placeholder="เลขบอส (95)" required></div>
            <div class="col-4"><input type="number" name="ch" class="form-control bg-dark text-white" placeholder="แนล (1)" required></div>
            <div class="col-4"><input type="text" name="time_input" class="form-control bg-dark text-white" placeholder="นาที เช่น -5"></div>
            <div class="col-12"><button type="submit" class="btn btn-warning w-100">บันทึกข้อมูล</button></div>
        </form>
    </div>

    <h4 class="text-danger mb-3">🚨 เข้าเฟสแล้ว (In Phase)</h4>
    <div class="row row-cols-1 row-cols-md-2 g-3 mb-4">
        {% for key, t_str in data.in_phase.items() %}
        {% set boss_id, ch = key.split('-') %}
        <div class="col">
            <div class="card p-3 in-phase-bg">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="text-danger m-0">🔥 บอส {{ boss_id }} [Ch.{{ ch }}]</h5>
                        <small class="text-muted">เวลาเกิด: {{ t_str[11:16] }} น.</small>
                    </div>
                    <div>
                        <button onclick="killBoss('{{ boss_id }}', '{{ ch }}')" class="btn btn-sm btn-success">⚔️ ตายแล้ว</button>
                        <a href="/delete/{{ boss_id }}/{{ ch }}" class="btn btn-sm btn-outline-danger">🗑️</a>
                    </div>
                </div>
            </div>
        </div>
        {% else %}
        <p class="text-muted ps-2">ไม่มีบอสในเฟส...</p>
        {% endfor %}
    </div>

    <h4 class="text-success mb-3">⏳ กำลังรอเกิด (Upcoming)</h4>
    <div class="row row-cols-1 row-cols-md-2 g-3">
        {% for key, t_str in active_spawns_sorted %}
        {% set boss_id, ch = key.split('-') %}
        <div class="col">
            <div class="card p-3 upcoming-bg">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="text-success m-0">⏳ บอส {{ boss_id }} [Ch.{{ ch }}]</h5>
                        <small class="text-light">รอบถัดไป: <b class="text-warning">{{ t_str[11:16] }} น.</b></small>
                    </div>
                    <div>
                        <a href="/delete/{{ boss_id }}/{{ ch }}" class="btn btn-sm btn-outline-danger">🗑️</a>
                    </div>
                </div>
            </div>
        </div>
        {% else %}
        <p class="text-muted ps-2">ไม่มีบอสรอเกิด...</p>
        {% endfor %}
    </div>

    <div class="modal fade" id="killModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content bg-dark text-white">
                <div class="modal-header"><h5>⚔️ บันทึกบอสตาย</h5></div>
                <div class="modal-body">
                    <input type="hidden" id="modal-boss-id">
                    <input type="hidden" id="modal-ch">
                    <div class="mb-3">
                        <label class="form-label">เวลาเกิดรอบถัดไป (นาที)</label>
                        <input type="text" id="modal-time-input" class="form-control bg-secondary text-white" placeholder="ปล่อยว่าง = ตอนนี้, หรือใส่ -5, 1.30">
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">ยกเลิก</button>
                    <button type="button" onclick="submitKill()" class="btn btn-success">ยืนยัน</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const killModal = new bootstrap.Modal(document.getElementById('killModal'));
        function killBoss(bossId, ch) {
            document.getElementById('modal-boss-id').value = bossId;
            document.getElementById('modal-ch').value = ch;
            document.getElementById('modal-time-input').value = "";
            killModal.show();
        }
        function submitKill() {
            const bossId = document.getElementById('modal-boss-id').value;
            const ch = document.getElementById('modal-ch').value;
            const timeInput = document.getElementById('modal-time-input').value;
            window.location.href = `/kill/${bossId}/${ch}?time_input=${timeInput}`;
        }
        setInterval(() => { window.location.reload(); }, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    boss_db = update_boss_statuses()
    sorted_active = sorted(boss_db["active_spawns"].items(), key=lambda x: x[1])
    return render_template_string(HTML_TEMPLATE, data=boss_db, active_spawns_sorted=sorted_active)

@app.route('/add', methods=['POST'])
def add_boss():
    boss_db = load_data()
    boss_id = request.form.get('boss_id')
    ch = request.form.get('ch')
    time_input = request.form.get('time_input', '')
    
    key = f"{boss_id}-{ch}"
    boss_db["active_spawns"].pop(key, None)
    boss_db["in_phase"].pop(key, None)
    
    base_min = 0
    if time_input:
        try:
            is_neg = time_input.startswith("-")
            clean = time_input.lstrip("-")
            if "." in clean:
                h, m = map(int, clean.split("."))
                base_min = (h * 60) + m
            else: base_min = int(clean)
            if is_neg: base_min = -base_min
        except: pass
        
    spawn_time = get_bkk_now() + timedelta(minutes=base_min)
    boss_db["active_spawns"][key] = spawn_time.strftime('%Y-%m-%d %H:%M:%S')
    save_data(boss_db)
    return '<script>window.location.href="/";</script>'

@app.route('/kill/<boss_id>/<ch>')
def kill_boss(boss_id, ch):
    boss_db = load_data()
    key = f"{boss_id}-{ch}"
    boss_db["in_phase"].pop(key, None)
    
    time_input = request.args.get('time_input', '')
    base_min = 0
    if time_input:
        try:
            is_neg = time_input.startswith("-")
            clean = time_input.lstrip("-")
            if "." in clean:
                h, m = map(int, clean.split("."))
                base_min = (h * 60) + m
            else: base_min = int(clean)
            if is_neg: base_min = -base_min
        except: pass
        
    spawn_time = get_bkk_now() + timedelta(minutes=base_min)
    boss_db["active_spawns"][key] = spawn_time.strftime('%Y-%m-%d %H:%M:%S')
    save_data(boss_db)
    return '<script>window.location.href="/";</script>'

@app.route('/delete/<boss_id>/<ch>')
def delete_boss(boss_id, ch):
    boss_db = load_data()
    key = f"{boss_id}-{ch}"
    boss_db["active_spawns"].pop(key, None)
    boss_db["in_phase"].pop(key, None)
    save_data(boss_db)
    return '<script>window.location.href="/";</script>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)