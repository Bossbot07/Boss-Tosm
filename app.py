from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime, timedelta
import requests
import pytz
import json

app = Flask(__name__)

# Config ฐานข้อมูล Upstash Redis
REDIS_URL = "https://helping-egret-126070.upstash.io"
REDIS_TOKEN = "gQAAAAAAAex2AAIgcDJhNDlkZThkNGI5OTc0YTQxYjUzMjU4MTcyNTRhZWM1MQ"
BKK_TZ = pytz.timezone('Asia/Bangkok')

def get_bkk_now():
    return datetime.now(pytz.utc).astimezone(BKK_TZ)

def load_data():
    default_data = {"active_spawns": {}, "in_phase": {}}
    try:
        headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
        response = requests.get(f"{REDIS_URL}/get/tosm_boss_db", headers=headers, timeout=5)
        
        if response.status_code == 200:
            res_json = response.json()
            result = res_json.get("result")
            
            if not result:
                return default_data
                
            data = result
            for _ in range(5):
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        break
                else:
                    break
                    
            if not isinstance(data, dict):
                return default_data
                
            clean_active = {}
            clean_in_phase = {}
            
            active = data.get("active_spawns", {})
            if isinstance(active, dict):
                for k, v in active.items():
                    if '-' in str(k): clean_active[str(k)] = str(v)
                    
            in_p = data.get("in_phase", {})
            if isinstance(in_p, dict):
                for k, v in in_p.items():
                    if '-' in str(k): clean_in_phase[str(k)] = str(v)
                    
            return {
                "active_spawns": clean_active,
                "in_phase": clean_in_phase
            }
    except Exception as e:
        print(f"❌ โหลดข้อมูลล้มเหลว: {e}")
    return default_data

def save_data(data):
    try:
        headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
        payload = json.dumps(data)
        response = requests.post(f"{REDIS_URL}/set/tosm_boss_db", headers=headers, data=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ บันทึกข้อมูลล้มเหลว: {e}")
        return False

def update_boss_statuses():
    try:
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
            except: 
                boss_db["active_spawns"].pop(key, None)
                has_change = True

        for key, t_str in list(boss_db["in_phase"].items()):
            try:
                spawn_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
                if now >= (spawn_time + timedelta(minutes=30)):
                    boss_db["in_phase"].pop(key, None)
                    has_change = True
            except: 
                boss_db["in_phase"].pop(key, None)
                has_change = True

        if has_change:
            save_data(boss_db)
        return boss_db
    except Exception as e:
        print(f"❌ update_boss_statuses พัง: {e}")
        return {"active_spawns": {}, "in_phase": {}}

# HTML UI ธีมมืด ดำ-แดง-เขียว จัดกลุ่มบอสเรียบร้อย
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚔️ TOSM BOSS TRACKER ⚔️</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: sans-serif; padding-bottom: 60px; }
        .main-title { text-align: center; color: #ffca28; font-weight: bold; margin-top: 15px; margin-bottom: 20px; }
        .card-custom { background-color: #1e1e1e; border: 1px solid #333; border-radius: 8px; color: #fff; }
        .section-title { font-size: 1.2rem; font-weight: bold; margin-top: 25px; margin-bottom: 15px; }
        .boss-group-wrapper { background-color: #181818; border: 1px solid #2d2d2d; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .sub-card-inphase { background-color: #241414; border: 1px solid #4a1c1c; border-radius: 6px; padding: 12px; }
        .sub-card-upcoming { background-color: #142418; border: 1px solid #1c4a24; border-radius: 6px; padding: 12px; }
        .form-input { background-color: #1a1a1a; border: 1px solid #444; color: #fff; text-align: center; }
        .form-input:focus { background-color: #222; border-color: #ffca28; color: #fff; box-shadow: none; }
    </style>
</head>
<body class="container">

    <div class="d-flex justify-content-between align-items-center mb-2">
        <h2 class="main-title my-0">⚔️ TOSM BOSS TRACKER ⚔️</h2>
        <a href="/reset_db" onclick="return confirm('ต้องการล้างฐานข้อมูล รีเซ็ตข้อมูลบอสทั้งหมดใช่ไหม?')" class="btn btn-sm btn-outline-danger">⚙️ รีเซ็ตระบบ</a>
    </div>

    <div class="card-custom p-3 mb-4">
        <h5 class="text-warning mb-3">➕ บันทึกบอสใหม่</h5>
        <form action="/add" method="POST" class="row g-2">
            <div class="col-4"><input type="text" name="boss_id" class="form-control form-input" placeholder="เลขบอส เช่น 95" required></div>
            <div class="col-4"><input type="number" name="ch" class="form-control form-input" placeholder="Ch. เช่น 1" required></div>
            <div class="col-4"><input type="text" name="time_input" class="form-control form-input" placeholder="นาที เช่น -5"></div>
            <div class="col-12 mt-2"><button type="submit" class="btn btn-warning w-100 fw-bold">บันทึกข้อมูล</button></div>
        </form>
    </div>

    <div class="section-title text-danger">🚨 เข้าเฟสแล้ว (In Phase) - เรียงตามเวลาเกิดก่อน</div>
    <div class="row row-cols-1 g-2">
        {% for group in in_phase_groups %}
        <div class="col">
            <div class="boss-group-wrapper" style="border-top: 3px solid #ff4757;">
                <h5 class="text-warning mb-3">🔥 กลุ่มบอส {{ group.boss_id }}</h5>
                <div class="row row-cols-1 row-cols-md-2 g-2">
                    {% for item in group.items %}
                    <div class="col">
                        <div class="sub-card-inphase d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="m-0" style="color: #ff6b6b;">บอส {{ group.boss_id }} [Ch.{{ item.ch }}]</h6>
                                <span class="badge bg-danger my-1">เข้าเฟสมาแล้ว {{ item.minutes_passed }} นาที</span>
                                <small class="text-muted d-block">เวลาเกิด: {{ item.time_hm }} น.</small>
                            </div>
                            <div class="d-flex gap-1">
                                <button onclick="killBoss('{{ group.boss_id }}', '{{ item.ch }}')" class="btn btn-sm btn-success fw-bold">⚔️ ตายแล้ว</button>
                                <a href="/delete/{{ group.boss_id }}/{{ item.ch }}" class="btn btn-sm btn-dark text-danger border-secondary">🗑️</a>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% else %}
        <p class="text-muted ps-2">ไม่มีบอสในเฟส...</p>
        {% endfor %}
    </div>

    <div class="section-title text-success">⏳ กำลังรอเกิด (Upcoming) - เรียงตามเวลาเกิดใกล้สุด</div>
    <div class="row row-cols-1 g-2">
        {% for group in upcoming_groups %}
        <div class="col">
            <div class="boss-group-wrapper" style="border-top: 3px solid #2ed573;">
                <h5 class="text-warning mb-3">⏳ กลุ่มบอส {{ group.boss_id }}</h5>
                <div class="row row-cols-1 row-cols-md-2 g-2">
                    {% for item in group.items %}
                    <div class="col">
                        <div class="sub-card-upcoming d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="m-0" style="color: #2ed573;">บอส {{ group.boss_id }} [Ch.{{ item.ch }}]</h6>
                                <div class="text-light mt-1" style="font-size: 0.9rem;">รอบถัดไป: <b class="text-warning">{{ item.time_hm }} น.</b></div>
                            </div>
                            <div>
                                <a href="/delete/{{ group.boss_id }}/{{ item.ch }}" class="btn btn-sm btn-dark text-danger border-secondary">🗑️</a>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% else %}
        <p class="text-muted ps-2">ไม่มีบอสรอเกิด...</p>
        {% endfor %}
    </div>

    <div class="modal fade" id="killModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content bg-dark text-white border-secondary">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title text-warning">⚔️ บันทึกรอบเกิดถัดไป</h5>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="modal-boss-id">
                    <input type="hidden" id="modal-ch">
                    <div class="mb-3">
                        <label class="form-label text-light">เวลาเกิดรอบถัดไป (นาที)</label>
                        <input type="text" id="modal-time-input" class="form-control form-input" placeholder="ปล่อยว่าง = ตอนนี้, หรือใส่ -5, 1.30">
                    </div>
                </div>
                <div class="modal-footer border-secondary">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">ยกเลิก</button>
                    <button type="button" onclick="submitKill()" class="btn btn-success fw-bold">ยืนยัน</button>
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
    in_phase_groups_sorted = []
    upcoming_groups_sorted = []
    try:
        boss_db = update_boss_statuses()
        now = get_bkk_now()
        
        in_phase_dict = {}
        if boss_db and isinstance(boss_db.get("in_phase"), dict):
            for key, t_str in boss_db["in_phase"].items():
                if '-' not in str(key): continue
                try:
                    boss_id, ch = str(key).split('-', 1)
                    spawn_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
                    diff = now - spawn_time
                    minutes_passed = int(diff.total_seconds() // 60)
                    if minutes_passed < 0: minutes_passed = 0
                    time_hm = t_str[11:16]
                except: continue
                item = {"ch": ch, "time_hm": time_hm, "spawn_time_obj": spawn_time, "minutes_passed": minutes_passed}
                if boss_id not in in_phase_dict: in_phase_dict[boss_id] = []
                in_phase_dict[boss_id].append(item)
            
        in_phase_groups = []
        for b_id, items in in_phase_dict.items():
            sorted_items = sorted(items, key=lambda x: x["spawn_time_obj"])
            in_phase_groups.append({"boss_id": b_id, "items": sorted_items, "min_time": sorted_items[0]["spawn_time_obj"]})
        in_phase_groups_sorted = sorted(in_phase_groups, key=lambda x: x["min_time"])

        upcoming_dict = {}
        if boss_db and isinstance(boss_db.get("active_spawns"), dict):
            for key, t_str in boss_db["active_spawns"].items():
                if '-' not in str(key): continue
                try:
                    boss_id, ch = str(key).split('-', 1)
                    spawn_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
                    time_hm = t_str[11:16]
                except: continue
                item = {"ch": ch, "time_hm": time_hm, "spawn_time_obj": spawn_time}
                if boss_id not in upcoming_dict: upcoming_dict[boss_id] = []
                upcoming_dict[boss_id].append(item)
            
        upcoming_groups = []
        for b_id, items in upcoming_dict.items():
            sorted_items = sorted(items, key=lambda x: x["spawn_time_obj"])
            upcoming_groups.append({"boss_id": b_id, "items": sorted_items, "min_time": sorted_items[0]["spawn_time_obj"]})
        upcoming_groups_sorted = sorted(upcoming_groups, key=lambda x: x["min_time"])
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดรันหน้าแรก: {e}")
        
    return render_template_string(HTML_TEMPLATE, in_phase_groups=in_phase_groups_sorted, upcoming_groups=upcoming_groups_sorted)

@app.route('/reset_db')
def reset_db():
    empty_data = {"active_spawns": {}, "in_phase": {}}
    save_data(empty_data)
    return redirect(url_for('index')) # บังคับ Redirect ไปหน้าแรกแทน script

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
    return redirect(url_for('index')) # บังคับ Redirect ไปหน้าแรกแทน script

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
    return redirect(url_for('index')) # บังคับ Redirect ไปหน้าแรกแทน script

@app.route('/delete/<boss_id>/<ch>')
def delete_boss(boss_id, ch):
    try:
        boss_db = load_data()
        key = f"{boss_id}-{ch}"
        boss_db["active_spawns"].pop(key, None)
        boss_db["in_phase"].pop(key, None)
        save_data(boss_db)
    except: pass
    return redirect(url_for('index')) # บังคับ Redirect ไปหน้าแรกแทน script

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)