from flask import Flask, render_template_string, request, jsonify, make_response
from datetime import datetime, timedelta
import requests
import pytz
import json

app = Flask(__name__)

# Config ฐานข้อมูล Upstash ของคุณ
REDIS_URL = "https://helping-egret-126070.upstash.io"
REDIS_TOKEN = "gQAAAAAAAex2AAIgcDJhNDlkZThkNGI5OTc0YTQxYjUzMjU4MTcyNTRhZWM1MQ"
BKK_TZ = pytz.timezone('Asia/Bangkok')

def get_bkk_now():
    return datetime.now(pytz.utc).astimezone(BKK_TZ)

# ฟังก์ชันดึงข้อมูลจากฐานข้อมูลออนไลน์
def load_data():
    default_data = {"active_spawns": {}, "in_phase": {}}
    try:
        headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
        response = requests.get(f"{REDIS_URL}/get/tosm_boss_db", headers=headers, timeout=5)
        
        if response.status_code == 200:
            res_json = response.json()
            result = res_json.get("result")
            
            if result:
                if isinstance(result, str):
                    try:
                        data = json.loads(result)
                    except:
                        data = json.loads(result)
                else:
                    data = result
                
                return {
                    "active_spawns": data.get("active_spawns", {}),
                    "in_phase": data.get("in_phase", {})
                }
        else:
            print(f"⚠️ Upstash Error Code: {response.status_code}")
    except Exception as e:
        print(f"❌ โโหลดข้อมูลล้มเหลว: {e}")
    return default_data

# ฟังก์ชันเซฟข้อมูลไปที่ฐานข้อมูลออนไลน์
def save_data(data):
    try:
        headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
        payload = json.dumps(data)
        
        response = requests.post(f"{REDIS_URL}/set/tosm_boss_db", headers=headers, data=payload, timeout=5)
        if response.status_code == 200:
            print("✅ บันทึกข้อมูลลง Upstash สำเร็จ!")
        else:
            print(f"❌ เซฟไม่สำเร็จ Code: {response.status_code}")
    except Exception as e:
        print(f"❌ บันทึกข้อมูลออนไลน์ล้มเหลว: {e}")

def update_boss_statuses():
    boss_db = load_data()
    now = get_bkk_now()
    has_change = False

    for key, t_str in list(boss_db["active_spawns"].items()):
        try:
            target_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
            if now >= target_time:
                boss_db["in_phase"][key] = t_str
                boss_db["active_spawns"].pop(key, None)
                has_change = True
        except: continue

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

# HTML UI ตัดปุ่มรีเซ็ตออกแล้ว เหลือเฉพาะตัวเลือกการจัดเรียง
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
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-center mb-4 gap-3">
        <h2 class="text-warning m-0">⚔️ TOSM BOSS TRACKER ⚔️</h2>
        
        <div class="d-flex gap-2 align-items-center">
            <span class="text-muted small">จัดเรียง:</span>
            <select id="sortSelector" class="form-select form-select-sm bg-dark text-white border-secondary" onchange="changeSortOrder(this.value)" style="width: auto;">
                <option value="time" {% if current_sort == 'time' %}selected{% endif %}>🕒 เรียงตามเวลาเกิด</option>
                <option value="level" {% if current_sort == 'level' %}selected{% endif %}>⚔️ เรียงตามเลเวลบอส (มาก->น้อย)</option>
            </select>
        </div>
    </div>
    
    <div class="card p-3 mb-4">
        <h5>➕ บันทึกบอสใหม่</h5>
        <form id="addBossForm" onsubmit="submitAddForm(event)" class="row g-2">
            <div class="col-4"><input type="text" id="boss_id" class="form-control bg-dark text-white" placeholder="เลขบอส (95)" required></div>
            <div class="col-4"><input type="number" id="ch" class="form-control bg-dark text-white" placeholder="แนล (1)" required></div>
            <div class="col-4"><input type="text" id="time_input" class="form-control bg-dark text-white" placeholder="นาที เช่น -5"></div>
            <div class="col-12"><button type="submit" class="btn btn-warning w-100 fw-bold">บันทึกข้อมูล</button></div>
        </form>
    </div>

    <h4 class="text-danger mb-3">🚨 เข้าเฟสแล้ว (In Phase) - {% if current_sort == 'level' %}เรียงเลเวลมากไปน้อย{% else %}เรียงตามเวลาเกิดก่อน{% endif %}</h4>
    <div class="row row-cols-1 row-cols-md-2 g-3 mb-4">
        {% for item in in_phase_list_sorted %}
        <div class="col">
            <div class="card p-3 in-phase-bg">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="text-danger m-0">🔥 บอส {{ item.boss_id }} [Ch.{{ item.ch }}]</h5>
                        <div class="mt-1">
                            <span class="badge bg-danger">เข้าเฟสมาแล้ว {{ item.minutes_passed }} นาที</span>
                        </div>
                        <small class="text-muted d-block mt-1">เวลาเกิด: {{ item.t_str[11:16] }} น.</small>
                    </div>
                    <div>
                        <button onclick="killBoss('{{ item.boss_id }}', '{{ item.ch }}')" class="btn btn-sm btn-success">⚔️ ตายแล้ว</button>
                        <button onclick="runApi('/delete/{{ item.boss_id }}/{{ item.ch }}')" class="btn btn-sm btn-outline-danger">🗑️</button>
                    </div>
                </div>
            </div>
        </div>
        {% else %}
        <p class="text-muted ps-2">ไม่มีบอสในเฟส...</p>
        {% endfor %}
    </div>

    <h4 class="text-success mb-3">⏳ กำลังรอเกิด (Upcoming) - {% if current_sort == 'level' %}เรียงเลเวลมากไปน้อย{% else %}เรียงตามเวลาเกิดใกล้สุด{% endif %}</h4>
    <div class="row row-cols-1 row-cols-md-2 g-3">
        {% for item in active_spawns_sorted %}
        <div class="col">
            <div class="card p-3 upcoming-bg">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="text-success m-0">⏳ บอส {{ item.boss_id }} [Ch.{{ item.ch }}]</h5>
                        <small class="text-light">รอบถัดไป: <b class="text-warning">{{ item.t_str[11:16] }} น.</b></small>
                    </div>
                    <div>
                        <button onclick="runApi('/delete/{{ item.boss_id }}/{{ item.ch }}')" class="btn btn-sm btn-outline-danger">🗑️</button>
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

        function changeSortOrder(val) {
            document.cookie = "boss_sort_order=" + val + "; path=/; max-age=31536000";
            window.location.reload();
        }

        function runApi(url) {
            fetch(url)
            .then(() => { window.location.reload(); })
            .catch(() => { window.location.reload(); });
        }

        function submitAddForm(event) {
            event.preventDefault();
            const b_id = document.getElementById('boss_id').value;
            const ch_id = document.getElementById('ch').value;
            const t_in = document.getElementById('time_input').value;

            fetch('/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: `boss_id=${b_id}&ch=${ch_id}&time_input=${t_in}`
            })
            .then(() => { window.location.reload(); })
            .catch(() => { window.location.reload(); });
        }

        function submitKill() {
            const bossId = document.getElementById('modal-boss-id').value;
            const ch = document.getElementById('modal-ch').value;
            const timeInput = document.getElementById('modal-time-input').value;
            killModal.hide();
            runApi(`/kill/${bossId}/${ch}?time_input=${timeInput}`);
        }

        setInterval(() => { window.location.reload(); }, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    boss_db = update_boss_statuses()
    now = get_bkk_now()
    
    sort_by = request.cookies.get('boss_sort_order', 'time')
    
    # 1. จัดการข้อมูลบอสในเฟส (In Phase)
    in_phase_list = []
    for key, t_str in boss_db["in_phase"].items():
        if '-' not in str(key): continue
        boss_id, ch = key.split('-', 1)
        try:
            spawn_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
            diff = now - spawn_time
            minutes_passed = int(diff.total_seconds() // 60)
            if minutes_passed < 0: minutes_passed = 0
        except:
            spawn_time = now
            minutes_passed = 0
            
        try: boss_level = int(boss_id)
        except: boss_level = -1
            
        in_phase_list.append({
            "boss_id": boss_id,
            "boss_level": boss_level,
            "ch": ch,
            "t_str": t_str,
            "spawn_time_obj": spawn_time,
            "minutes_passed": minutes_passed
        })
    
    if sort_by == 'level':
        in_phase_list_sorted = sorted(in_phase_list, key=lambda x: (-x["boss_level"], x["spawn_time_obj"]))
    else:
        in_phase_list_sorted = sorted(in_phase_list, key=lambda x: x["spawn_time_obj"])
    
    # 2. จัดการข้อมูลบอสรอเกิด (Upcoming)
    upcoming_list = []
    for key, t_str in boss_db["active_spawns"].items():
        if '-' not in str(key): continue
        boss_id, ch = key.split('-', 1)
        try:
            spawn_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
        except:
            spawn_time = now
        
        try: boss_level = int(boss_id)
        except: boss_level = -1
            
        upcoming_list.append({
            "boss_id": boss_id,
            "boss_level": boss_level,
            "ch": ch,
            "t_str": t_str,
            "spawn_time_obj": spawn_time
        })
        
    if sort_by == 'level':
        active_spawns_sorted = sorted(upcoming_list, key=lambda x: (-x["boss_level"], x["spawn_time_obj"]))
    else:
        active_spawns_sorted = sorted(upcoming_list, key=lambda x: x["spawn_time_obj"])
    
    return render_template_string(
        HTML_TEMPLATE, 
        in_phase_list_sorted=in_phase_list_sorted, 
        active_spawns_sorted=active_spawns_sorted,
        current_sort=sort_by
    )

@app.route('/add', methods=['POST'])
def add_boss():
    try:
        boss_db = load_data()
        boss_id = request.form.get('boss_id').strip()
        ch = request.form.get('ch').strip()
        time_input = request.form.get('time_input', '').strip()
        
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
    except: pass
    return jsonify({"status": "success"})

@app.route('/kill/<boss_id>/<ch>')
def kill_boss(boss_id, ch):
    try:
        boss_db = load_data()
        key = f"{boss_id}-{ch}"
        boss_db["in_phase"].pop(key, None)
        
        time_input = request.args.get('time_input', '').strip()
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
    except: pass
    return jsonify({"status": "success"})

@app.route('/delete/<boss_id>/<ch>')
def delete_boss(boss_id, ch):
    try:
        boss_db = load_data()
        key = f"{boss_id}-{ch}"
        boss_db["active_spawns"].pop(key, None)
        boss_db["in_phase"].pop(key, None)
        save_data(boss_db)
    except: pass
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)