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
        print(f"❌ โหลดข้อมูลล้มเหลว: {e}")
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
            if now >= (spawn_time + timedelta(minutes=90)):
                boss_db["in_phase"].pop(key, None)
                has_change = True
        except: continue

    # 🛠️ ป้องกันบั๊กรีเฟรชรัว: จะบันทึกเมื่อโครงสร้างข้อมูลเปลี่ยนจริง ๆ เท่านั้น
    if has_change:
        save_data(boss_db)
    return boss_db

# HTML UI - ปรับสัดส่วน Layout ใหม่ตามคำขอ
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TOSM Boss Tracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212 !important; color: #e0e0e0 !important; font-family: sans-serif !important; font-size: 13px !important; }
        
        .boss-card { background-color: #1e1e1e !important; border: 1px solid #333 !important; color: #fff !important; padding: 8px 10px !important; margin-bottom: 5px !important; border-radius: 6px !important; }
        .in-phase-bg { border-left: 5px solid #ff4757 !important; }
        .upcoming-bg { border-left: 5px solid #2ed573 !important; }
        
        /* 🛠️ ปรับโครงสร้าง Column ใหม่ */
        .col-boss-info { width: 38% !important; min-width: 100px; flex-shrink: 0; }
        .col-boss-center { width: 32% !important; text-align: left !important; flex-shrink: 0; display: flex; align-items: center; }
        .col-boss-action { width: 30% !important; display: flex; justify-content: flex-end; align-items: center; gap: 6px; flex-shrink: 0; }
        
        .boss-title { font-size: 13px !important; font-weight: bold; }
        .time-text { font-size: 13px !important; font-weight: bold; }
        .countdown-text { font-size: 13px !important; font-weight: bold !important; color: #2ed573 !important; white-space: nowrap; }
        
        .form-control-sm, .form-select-sm { font-size: 13px !important; padding: 4px 8px !important; height: 30px !important; }
        .btn-custom-sm { font-size: 12px !important; padding: 4px 10px !important; height: 28px !important; line-height: 1.2 !important; font-weight: bold !important; }
        .btn-delete { padding: 4px 8px !important; height: 28px !important; font-size: 12px !important; }
        
        h2 { font-size: 18px !important; margin: 0 !important; font-weight: bold !important; }
        h4 { font-size: 14px !important; margin-top: 12px !important; margin-bottom: 6px !important; font-weight: bold !important; }
        .badge-phase { font-size: 11px !important; padding: 4px 8px !important; font-weight: bold; }
    </style>
</head>
<body class="container-fluid px-2 py-2" style="max-width: 600px !important;">
    
    <div class="d-flex justify-content-between align-items-center mb-2 gap-2">
        <h2 class="text-warning">⚔️ TOSM BOSS</h2>
        <div class="d-flex gap-1 align-items-center">
            <span class="text-muted" style="font-size: 11px;">เรียง:</span>
            <select id="sortSelector" class="form-select form-select-sm bg-dark text-white border-secondary" onchange="changeSortOrder(this.value)" style="width: auto;">
                <option value="time" {% if current_sort == 'time' %}selected{% endif %}>🕒 เวลาเกิด</option>
                <option value="level" {% if current_sort == 'level' %}selected{% endif %}>⚔️ เลเวลบอส</option>
            </select>
        </div>
    </div>
    
    <div class="boss-card p-2 mb-3">
        <form id="addBossForm" onsubmit="submitAddForm(event)" class="row g-1">
            <div class="col-3"><input type="text" id="boss_id" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="เลขบอส" required></div>
            <div class="col-3"><input type="number" id="ch" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="แนล" required></div>
            <div class="col-3"><input type="text" id="time_input" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="นาที (-5)"></div>
            <div class="col-3"><button type="submit" class="btn btn-warning btn-custom-sm w-100">➕ บันทึก</button></div>
        </form>
    </div>

    <h4 class="text-danger">🚨 เข้าเฟสแล้ว (In Phase)</h4>
    <div class="d-flex flex-column gap-1 mb-3">
        {% for item in in_phase_list_sorted %}
        <div class="boss-card in-phase-bg d-flex align-items-center m-0">
            <div class="col-boss-info">
                <span class="text-danger boss-title">🔥 บอส {{ item.boss_id }} [Ch.{{ item.ch }}]</span>
            </div>
            
            <div class="col-boss-center">
                <span class="badge bg-danger badge-phase">เข้าเฟส {{ item.minutes_passed }} น.</span>
            </div>
            
            <div class="col-boss-action">
                <button onclick="killBoss('{{ item.boss_id }}', '{{ item.ch }}')" class="btn btn-success btn-custom-sm">ใส่เวลาใหม่</button>
                <button onclick="runApi('/delete/{{ item.boss_id }}/{{ item.ch }}')" class="btn btn-outline-danger btn-custom-sm btn-delete">🗑️</button>
            </div>
        </div>
        {% else %}
        <p class="text-muted ps-1 m-0">ไม่มีบอสในเฟส...</p>
        {% endfor %}
    </div>

    <h4 class="text-success">⏳ กำลังรอเกิด (Upcoming)</h4>
    <div class="d-flex flex-column gap-1">
        {% for item in active_spawns_sorted %}
        <div class="boss-card upcoming-bg d-flex align-items-center m-0">
            <div class="col-boss-info">
                <span class="text-success boss-title">⏳ บอส {{ item.boss_id }} [Ch.{{ item.ch }}]</span>
            </div>
            
            <div class="col-boss-center">
                <span class="text-warning time-text">{{ item.t_str[11:16] }}</span>
            </div>
            
            <div class="col-boss-action">
                <div class="countdown-text m-0" data-target-time="{{ item.iso_time }}">คำนวณ...</div>
                <button onclick="runApi('/delete/{{ item.boss_id }}/{{ item.ch }}')" class="btn btn-outline-danger btn-custom-sm btn-delete">🗑️</button>
            </div>
        </div>
        {% else %}
        <p class="text-muted ps-1 m-0">ไม่มีบอสรอเกิด...</p>
        {% endfor %}
    </div>

    <div class="modal fade" id="killModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm" style="max-width: 280px;">
            <div class="modal-content bg-dark text-white border-secondary">
                <div class="modal-body p-3">
                    <input type="hidden" id="modal-boss-id">
                    <input type="hidden" id="modal-ch">
                    <div class="mb-3">
                        <label class="form-label mb-1" style="font-size: 12px;">ใส่เวลาเกิดรอบถัดไป (นาที)</label>
                        <input type="text" id="modal-time-input" class="form-control bg-secondary text-white border-0" placeholder="ว่าง=ตอนนี้, หรือใส่ -5, 1.30" onkeydown="handleModalKeyDown(event)" style="font-size: 13px; height: 34px;">
                    </div>
                    <div class="d-flex justify-content-end gap-2">
                        <button type="button" class="btn btn-secondary btn-custom-sm" data-bs-dismiss="modal">ยกเลิก</button>
                        <button type="button" onclick="submitKill()" class="btn btn-success btn-custom-sm">ยืนยัน</button>
                    </div>
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
            const timeInput = document.getElementById('modal-time-input');
            timeInput.value = "";
            killModal.show();
            setTimeout(() => { timeInput.focus(); }, 300);
        }

        function handleModalKeyDown(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                submitKill();
            }
        }

        function changeSortOrder(val) {
            document.cookie = "boss_sort_order=" + val + "; path=/; max-age=31536000";
            window.location.reload();
        }

        function runApi(url) {
            fetch(url).then(() => { window.location.reload(); }).catch(() => { window.location.reload(); });
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
            }).then(() => { window.location.reload(); });
        }

        function submitKill() {
            const bossId = document.getElementById('modal-boss-id').value;
            const ch = document.getElementById('modal-ch').value;
            const timeInput = document.getElementById('modal-time-input').value;
            killModal.hide();
            runApi(`/kill/${bossId}/${ch}?time_input=${timeInput}`);
        }

        function updateCountdowns() {
            const now = new Date().getTime();
            const elements = document.querySelectorAll('[data-target-time]');

            elements.forEach(el => {
                const targetIso = el.getAttribute('data-target-time');
                const targetTime = new Date(targetIso).getTime();
                const diff = targetTime - now;

                if (diff <= 0) {
                    el.innerHTML = "💥 เกิดแล้ว!";
                    el.style.color = "#ff4757";
                } else {
                    const hours = Math.floor(diff / (1000 * 60 * 60));
                    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

                    const displayMinutes = String(minutes).padStart(2, '0');
                    const displaySeconds = String(seconds).padStart(2, '0');

                    if (hours > 0) {
                        el.innerHTML = `⏱️ ${hours}:${displayMinutes}:${displaySeconds}`;
                    } else {
                        el.innerHTML = `⏱️ ${displayMinutes}:${displaySeconds}`;
                    }
                }
            });
        }

        setInterval(updateCountdowns, 1000);
        updateCountdowns();
        
        // 🛠️ ปรับเวลาออโต้รีเฟรชหน้าเว็บเป็นทุก 45 วินาที เพื่อลดโอกาสชนกันขณะกดปุ่มเวลาใหม่
        setInterval(() => { window.location.reload(); }, 45000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    boss_db = update_boss_statuses()
    now = get_bkk_now()
    sort_by = request.cookies.get('boss_sort_order', 'time')
    
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
    
    upcoming_list = []
    for key, t_str in boss_db["active_spawns"].items():
        if '-' not in str(key): continue
        boss_id, ch = key.split('-', 1)
        try:
            spawn_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
            iso_time = spawn_time.isoformat()
        except:
            spawn_time = now
            iso_time = now.isoformat()
        
        try: boss_level = int(boss_id)
        except: boss_level = -1
            
        upcoming_list.append({
            "boss_id": boss_id,
            "boss_level": boss_level,
            "ch": ch,
            "t_str": t_str,
            "spawn_time_obj": spawn_time,
            "iso_time": iso_time
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