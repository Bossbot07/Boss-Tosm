from flask import Flask, render_template_string, request, jsonify, make_response, redirect, url_for
from datetime import datetime, timedelta
import requests
import pytz
import json

app = Flask(__name__)

WEB_PASSWORD = "223"

REDIS_URL = "https://known-raptor-158847.upstash.io"
REDIS_TOKEN = "gQAAAAAAAmx_AAIgcDE1NzBhYTRkMTU3MDI0OGEzYjEzMmJiMjU0NTRkZDliMA"
BKK_TZ = pytz.timezone('Asia/Bangkok')

def get_bkk_now():
    return datetime.now(pytz.utc).astimezone(BKK_TZ)

def load_data():
    default_data = {"active_spawns": {}, "in_phase": {}, "dead_status": {}, "boss_phases": {}}
    try:
        headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
        response = requests.get(f"{REDIS_URL}/get/tosm_boss_db", headers=headers, timeout=5)
        if response.status_code == 200:
            res_json = response.json()
            result = res_json.get("result")
            if result:
                if isinstance(result, str):
                    try: data = json.loads(result)
                    except: data = json.loads(result)
                else: data = result
                return {
                    "active_spawns": data.get("active_spawns", {}),
                    "in_phase": data.get("in_phase", {}),
                    "dead_status": data.get("dead_status", {}),
                    "boss_phases": data.get("boss_phases", {})
                }
    except Exception as e:
        print(f"❌ โหลดข้อมูลล้มเหลว: {e}")
    return default_data

def save_data(data):
    try:
        headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
        payload = json.dumps(data)
        requests.post(f"{REDIS_URL}/set/tosm_boss_db", headers=headers, data=payload, timeout=5)
    except Exception as e:
        print(f"❌ บันทึกข้อมูลออนไลน์ล้มเหลว: {e}")

def update_boss_statuses():
    boss_db = load_data()
    now = get_bkk_now()
    has_change = False

    for key, t_str in list(boss_db["active_spawns"].items()):
        try:
            naive_time = datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
            target_time = BKK_TZ.localize(naive_time)
            if now >= target_time:
                boss_db["in_phase"][key] = t_str
                boss_db["active_spawns"].pop(key, None)
                has_change = True
        except: continue

    for key, t_str in list(boss_db["in_phase"].items()):
        try:
            naive_time = datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
            spawn_time = BKK_TZ.localize(naive_time)
            if now >= (spawn_time + timedelta(minutes=120)):
                boss_db["in_phase"].pop(key, None)
                boss_db["dead_status"].pop(key, None)
                boss_db.get("boss_phases", {}).pop(key, None)
                has_change = True
        except: continue

    if has_change:
        save_data(boss_db)
    return boss_db

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TOSM Boss Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0b0f19 !important; color: #e0e0e0 !important; font-family: sans-serif; }
        .login-box { max-width: 360px; margin: 100px auto 0px; background-color: #121826; padding: 25px; border-radius: 12px; border: 1px solid #10b981; box-shadow: 0px 4px 15px rgba(0,0,0,0.5); }
    </style>
</head>
<body class="container px-3">
    <div class="login-box text-center">
        <h3 class="text-success mb-4">⚔️ TOSM BOSS TRACKER</h3>
        {% if error %}
        <div class="alert alert-danger py-2" style="font-size: 14px;">❌ รหัสผ่านไม่ถูกต้องครับ</div>
        {% endif %}
        <form method="POST" action="/login">
            <div class="mb-3">
                <input type="password" name="pwd" class="form-control bg-dark text-white border-secondary text-center" placeholder="ใส่รหัสผ่านเพื่อเข้าใช้งาน" required autofocus>
            </div>
            <button type="submit" class="btn btn-success w-100 fw-bold">🔓 เข้าสู่ระบบ</button>
        </form>
    </div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TOSM Boss Tracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0b0f19 !important; color: #e0e0e0 !important; font-family: system-ui, -apple-system, sans-serif !important; font-size: 15px !important; }
        .main-container { max-width: 520px !important; margin: 0 auto; }
        
        /* Widget Style ในภาพ */
        .boss-card-inphase {
            background-color: #0d1322 !important;
            border: 2px solid #10b981 !important;
            border-radius: 18px !important;
            padding: 14px 18px !important;
            margin-bottom: 12px !important;
            position: relative;
        }

        .boss-card-upcoming {
            background-color: #111827 !important;
            border: 1px solid #1f2937 !important;
            border-radius: 12px !important;
            padding: 10px 14px !important;
            margin-bottom: 8px !important;
        }

        .pill-badge {
            border: 1.5px solid #10b981;
            color: #ffffff;
            font-weight: 800;
            border-radius: 50px;
            padding: 2px 14px;
            font-size: 14px;
            display: inline-block;
        }

        .phase-display {
            font-size: 20px;
            font-weight: 800;
            color: #38bdf8;
            border: 2px solid #0284c7;
            border-radius: 50px;
            padding: 2px 14px;
            cursor: pointer;
            background: #082f49;
            user-select: none;
        }
        .phase-display:hover { background: #0c4a6e; }

        .btn-plus-two {
            border: 1px solid #334155;
            background-color: #1e293b;
            color: #ffffff;
            border-radius: 50px;
            padding: 3px 12px;
            font-size: 14px;
            font-weight: 700;
        }
        .btn-plus-two:hover { background-color: #334155; }

        .elapsed-timer {
            font-size: 26px;
            font-weight: 800;
            color: #a7f3d0;
            font-family: monospace;
            letter-spacing: -0.5px;
        }

        .btn-reset-time {
            border: 1px solid #334155;
            background: #1e293b;
            color: #94a3b8;
            border-radius: 50%;
            width: 28px;
            height: 28px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            padding: 0;
            font-size: 12px;
        }
        .btn-reset-time:hover { color: #fff; background: #334155; }

        .form-control-sm, .form-select-sm { font-size: 13px !important; padding: 4px 8px !important; height: 34px !important; }
        .btn-custom-sm { font-size: 13px !important; padding: 4px 8px !important; height: 34px !important; line-height: 1.2 !important; font-weight: bold !important; border-radius: 8px !important; }

        .panel-box { background-color: #111827; padding: 10px; border-radius: 12px; border: 1px solid #1f2937; margin-bottom: 10px; }
        .red-badge-item { display: inline-flex; align-items: center; background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-right: 5px; margin-bottom: 5px; }
        .red-badge-delete { background: none; border: none; color: white; font-weight: bold; margin-left: 6px; cursor: pointer; padding: 0; }
        
        .close-btn { position: absolute; top: 12px; right: 14px; color: #64748b; cursor: pointer; font-size: 14px; }
        .close-btn:hover { color: #ef4444; }
    </style>
</head>
<body class="container-fluid px-2 py-2">
    <div class="main-container">
        <div class="d-flex justify-content-between align-items-center mb-2">
            <h3 class="text-success fw-bold m-0">⚔️ TOSM BOSS</h3>
            <div class="d-flex gap-2 align-items-center">
                <select id="sortSelector" class="form-select form-select-sm bg-dark text-white border-secondary" onchange="changeSortOrder(this.value)">
                    <option value="time" {% if current_sort == 'time' %}selected{% endif %}>🕒 เวลาเกิด</option>
                    <option value="level" {% if current_sort == 'level' %}selected{% endif %}>⚔️ เลเวลบอส</option>
                </select>
                <a href="/logout" class="btn btn-outline-secondary btn-custom-sm py-1 px-2" style="font-size:12px !important;">🔒 ออก</a>
            </div>
        </div>

        <div class="panel-box">
            <div class="d-flex flex-wrap align-items-center gap-2">
                <button class="btn btn-outline-light btn-custom-sm flex-grow-1" id="btn-filter-all" onclick="setMode('all')">👁️ ทั้งหมด</button>
                <button class="btn btn-outline-light btn-custom-sm flex-grow-1" id="btn-filter-under100" onclick="setMode('under100')">📉 เลเวล ≤ 100</button>
                <button class="btn btn-outline-danger btn-custom-sm flex-grow-1" id="btn-filter-redcard" onclick="setMode('redcard')">🔴 การ์ดแดง</button>
            </div>
            <div class="d-flex align-items-center gap-2 mt-2 pt-2 border-top border-secondary">
                <span class="text-info fw-bold" style="font-size: 13px;">🎯 กรองเลเวลขั้นต่ำ:</span>
                <input type="number" id="levelFilterInput" class="form-control form-control-sm bg-dark text-warning border-info fw-bold text-center" placeholder="ใส่เลเวล..." oninput="handleMinLevelInput(this.value)">
            </div>
        </div>

        <div class="panel-box">
            <div class="d-flex align-items-center gap-2">
                <span class="text-danger fw-bold" style="font-size: 13px; white-space: nowrap;">📌 เพิ่มการ์ดแดง:</span>
                <input type="number" id="redCardInput" class="form-control form-control-sm bg-dark text-white border-danger text-center" placeholder="เลเวล">
                <button onclick="addRedCard()" class="btn btn-danger btn-custom-sm">➕ เพิ่ม</button>
            </div>
            <div id="redCardListContainer" class="d-flex flex-wrap pt-2"></div>
        </div>
        
        <div class="panel-box">
            <form id="addBossForm" onsubmit="submitAddForm(event)" class="row g-2">
                <div class="col-3"><input type="text" id="boss_id" class="form-control form-control-sm bg-dark text-white border-secondary text-center" placeholder="เลเวล" required></div>
                <div class="col-3"><input type="number" id="ch" class="form-control form-control-sm bg-dark text-white border-secondary text-center" placeholder="Ch." required></div>
                <div class="col-3"><input type="text" id="time_input" class="form-control form-control-sm bg-dark text-white border-secondary text-center" placeholder="-5 หรือ 1.30"></div>
                <div class="col-3"><button type="submit" class="btn btn-success btn-custom-sm w-100">➕ เพิ่ม</button></div>
            </form>
        </div>

        <h5 class="text-danger fw-bold mt-3 mb-2">🚨 เข้าเฟสแล้ว (In Phase)</h5>
        <div class="d-flex flex-column" id="in-phase-container">
            {% for item in in_phase_list_sorted %}
            <div class="boss-card-inphase boss-item-row" data-boss-level="{{ item.boss_level }}">
                <span class="close-btn" onclick="runApi('/delete/{{ item.boss_id }}/{{ item.ch }}')">✕</span>
                
                <div class="d-flex align-items-center gap-2 mb-3">
                    <span class="pill-badge">LV.{{ item.boss_id }}</span>
                    <span class="pill-badge">CH.{{ item.ch }}</span>
                </div>

                <div class="d-flex align-items-center gap-2 mb-3">
                    <span class="text-secondary fw-bold" style="font-size: 14px;">Phase :</span>
                    <span class="phase-display" onclick="cyclePhase('{{ item.boss_id }}', '{{ item.ch }}', {{ item.phase_val }})">
                        {{ item.phase_main }}<span style="font-size: 16px;">.{{ item.phase_sub }}</span>
                    </span>
                    <button class="btn-plus-two" onclick="addPhaseVal('{{ item.boss_id }}', '{{ item.ch }}', 0.2)">+.2</button>
                    
                    <div class="ms-auto">
                        <button onclick="killBoss('{{ item.boss_id }}', '{{ item.ch }}')" class="btn btn-success btn-custom-sm">เวลาใหม่</button>
                    </div>
                </div>

                <div class="d-flex align-items-center gap-2">
                    <span class="elapsed-timer" data-spawn-iso="{{ item.iso_time }}">+00:00</span>
                    <button class="btn-reset-time" title="รีเซ็ตเวลา" onclick="killBossDirect('{{ item.boss_id }}', '{{ item.ch }}')">↺</button>
                </div>
            </div>
            {% else %}
            <p class="text-muted ps-1 m-0 empty-text-notice" style="font-size: 14px;">ไม่มีบอสในเฟส...</p>
            {% endfor %}
            <p class="text-muted ps-1 m-0 d-none filter-empty-notice" style="font-size: 14px;">ไม่มีบอสตรงตามตัวกรอง...</p>
        </div>

        <h5 class="text-success fw-bold mt-4 mb-2">⏳ กำลังรอเกิด (Upcoming)</h5>
        <div class="d-flex flex-column" id="upcoming-container">
            {% for item in active_spawns_sorted %}
            <div class="boss-card-upcoming d-flex align-items-center justify-content-between boss-item-row" data-boss-level="{{ item.boss_level }}">
                <div>
                    <span class="text-success fw-bold me-2">LV.{{ item.boss_id }} [Ch.{{ item.ch }}]</span>
                    <span class="text-warning fw-bold" style="font-size: 13px;">{{ item.t_str[11:16] }}</span>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <span class="text-info fw-bold" data-target-time="{{ item.iso_time }}" style="font-size: 14px;">คำนวณ...</span>
                    <button onclick="runApi('/delete/{{ item.boss_id }}/{{ item.ch }}')" class="btn btn-outline-danger btn-custom-sm py-0 px-2" style="height:28px !important;">🗑️</button>
                </div>
            </div>
            {% else %}
            <p class="text-muted ps-1 m-0 empty-text-notice" style="font-size: 14px;">ไม่มีบอสรอเกิด...</p>
            {% endfor %}
            <p class="text-muted ps-1 m-0 d-none filter-empty-notice" style="font-size: 14px;">ไม่มีบอสตรงตามตัวกรอง...</p>
        </div>
    </div>

    <div class="modal fade" id="killModal" tabindex="-1" data-bs-backdrop="false" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm" style="max-width: 320px;">
            <div class="modal-content bg-dark text-white border-secondary">
                <div class="modal-body p-3">
                    <input type="hidden" id="modal-boss-id"><input type="hidden" id="modal-ch">
                    <div class="mb-3">
                        <label class="form-label mb-2" style="font-size: 14px; font-weight: bold;">ใส่เวลาเกิดรอบถัดไป (นาที)</label>
                        <input type="text" id="modal-time-input" class="form-control bg-secondary text-white border-0 text-center" placeholder="ว่าง=ตอนนี้, หรือใส่ -5, 1.30" onkeydown="handleModalKeyDown(event)" style="font-size: 15px; height: 42px;">
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
        const killModalElement = document.getElementById('killModal');
        const killModal = new bootstrap.Modal(killModalElement);
        let currentMode = "all", minLevelFilter = 0, redCards = [];

        function getCookie(name) {
            let value = "; " + document.cookie;
            let parts = value.split("; " + name + "=");
            if (parts.length == 2) return parts.pop().split(";").shift();
            return null;
        }

        function loadRedCards() {
            const saved = getCookie('tosm_red_cards');
            if (saved) { try { redCards = JSON.parse(decodeURIComponent(saved)); } catch(e) { redCards = []; } }
            renderRedCards();
        }

        function saveRedCards() { document.cookie = "tosm_red_cards=" + encodeURIComponent(JSON.stringify(redCards)) + "; path=/; max-age=31536000"; }

        function addRedCard() {
            const input = document.getElementById('redCardInput');
            const lvl = parseInt(input.value);
            if (!lvl || lvl <= 0) return alert('กรุณากรอกเลเวลบอสที่ถูกต้อง');
            if (!redCards.includes(lvl)) {
                redCards.push(lvl); redCards.sort((a, b) => b - a);
                saveRedCards(); renderRedCards(); applyAllFilters();
            }
            input.value = "";
        }

        function deleteRedCard(lvl) {
            redCards = redCards.filter(item => item !== lvl);
            saveRedCards(); renderRedCards(); applyAllFilters();
        }

        function renderRedCards() {
            const container = document.getElementById('redCardListContainer');
            container.innerHTML = "";
            if (redCards.length === 0) { container.innerHTML = '<span class="text-muted" style="font-size: 12px;">ไม่มีรายการการ์ดแดง...</span>'; return; }
            redCards.forEach(lvl => {
                const badge = document.createElement('span'); badge.className = 'red-badge-item';
                badge.innerHTML = `Lv.${lvl} <button class="red-badge-delete" onclick="deleteRedCard(${lvl})">×</button>`;
                container.appendChild(badge);
            });
        }

        function setMode(mode) {
            currentMode = mode; document.cookie = "tosm_filter_mode=" + mode + "; path=/; max-age=31536000";
            document.getElementById('btn-filter-all').className = 'btn btn-custom-sm flex-grow-1 ' + (mode === 'all' ? 'btn-info text-dark' : 'btn-outline-light');
            document.getElementById('btn-filter-under100').className = 'btn btn-custom-sm flex-grow-1 ' + (mode === 'under100' ? 'btn-info text-dark' : 'btn-outline-light');
            document.getElementById('btn-filter-redcard').className = 'btn btn-custom-sm flex-grow-1 ' + (mode === 'redcard' ? 'btn-danger' : 'btn-outline-danger');
            applyAllFilters();
        }

        function handleMinLevelInput(val) {
            minLevelFilter = parseInt(val) || 0; document.cookie = "tosm_min_level_val=" + minLevelFilter + "; path=/; max-age=31536000";
            applyAllFilters();
        }

        function applyAllFilters() {
            const rows = document.querySelectorAll('.boss-item-row');
            rows.forEach(row => {
                const lvl = parseInt(row.getAttribute('data-boss-level')) || 0;
                let passMode = false;
                if (currentMode === 'all') passMode = true;
                else if (currentMode === 'under100') { if (lvl <= 100) passMode = true; }
                else if (currentMode === 'redcard') { if (redCards.includes(lvl)) passMode = true; }

                let passMinLevel = true;
                if (minLevelFilter > 0 && lvl < minLevelFilter) passMinLevel = false;

                if (passMode && passMinLevel) { row.classList.remove('d-none'); }
                else { row.classList.add('d-none'); }
            });
            checkContainerEmpty('in-phase-container'); checkContainerEmpty('upcoming-container');
        }

        function checkContainerEmpty(containerId) {
            const container = document.getElementById(containerId); if(!container) return;
            const visibleRows = container.querySelectorAll('.boss-item-row:not(.d-none)');
            const emptyNotice = container.querySelector('.empty-text-notice');
            const filterNotice = container.querySelector('.filter-empty-notice');
            if(visibleRows.length === 0) {
                if(emptyNotice && container.querySelectorAll('.boss-item-row').length === 0) {
                    emptyNotice.classList.remove('d-none'); if(filterNotice) filterNotice.classList.add('d-none');
                } else {
                    if(emptyNotice) emptyNotice.classList.add('d-none'); if(filterNotice) filterNotice.classList.remove('d-none');
                }
            } else { if(emptyNotice) emptyNotice.classList.add('d-none'); if(filterNotice) filterNotice.classList.add('d-none'); }
        }

        function cyclePhase(bossId, ch, currentVal) {
            let nextVal = Math.round((currentVal + 1.0) * 10) / 10;
            if (nextVal > 4.8) nextVal = 1.0;
            runApi(`/set_phase/${bossId}/${ch}?phase=${nextVal}`);
        }

        function addPhaseVal(bossId, ch, delta) {
            runApi(`/add_phase/${bossId}/${ch}?delta=${delta}`);
        }

        function killBossDirect(bossId, ch) {
            runApi(`/kill/${bossId}/${ch}?time_input=0`);
        }

        window.addEventListener('DOMContentLoaded', () => {
            loadRedCards();
            const savedMode = getCookie('tosm_filter_mode') || 'all';
            const savedMinLvl = parseInt(getCookie('tosm_min_level_val')) || 0;
            if(savedMinLvl > 0) { document.getElementById('levelFilterInput').value = savedMinLvl; minLevelFilter = savedMinLvl; }
            setMode(savedMode);
        });

        document.getElementById('redCardInput').addEventListener('keydown', function(e) { if (e.key === 'Enter') { e.preventDefault(); addRedCard(); } });
        function killBoss(bossId, ch) { document.getElementById('modal-boss-id').value = bossId; document.getElementById('modal-ch').value = ch; document.getElementById('modal-time-input').value = ""; killModal.show(); }
        killModalElement.addEventListener('shown.bs.modal', function () { document.getElementById('modal-time-input').focus(); });
        function handleModalKeyDown(event) { if (event.key === 'Enter') { event.preventDefault(); submitKill(); } }
        function changeSortOrder(val) { document.cookie = "boss_sort_order=" + val + "; path=/; max-age=31536000"; window.location.reload(); }
        function runApi(url) { fetch(url).then(() => { window.location.reload(); }).catch(() => { window.location.reload(); }); }

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
            killModal.hide(); runApi(`/kill/${bossId}/${ch}?time_input=${timeInput}`);
        }

        function updateTimers() {
            const now = new Date().getTime();
            
            // เดินหน้า +MM:SS
            document.querySelectorAll('[data-spawn-iso]').forEach(el => {
                const spawnIso = el.getAttribute('data-spawn-iso');
                const spawnTime = new Date(spawnIso).getTime();
                const diff = now - spawnTime;
                if (diff >= 0) {
                    const totalSec = Math.floor(diff / 1000);
                    const mins = String(Math.floor(totalSec / 60)).padStart(2, '0');
                    const secs = String(totalSec % 60).padStart(2, '0');
                    el.innerHTML = `+${mins}:${secs}`;
                } else {
                    el.innerHTML = `+00:00`;
                }
            });

            // ถอยหลัง Upcoming
            document.querySelectorAll('[data-target-time]').forEach(el => {
                const targetIso = el.getAttribute('data-target-time');
                const targetTime = new Date(targetIso).getTime();
                const diff = targetTime - now;
                if (diff <= 0) { el.innerHTML = "💥 เกิดแล้ว!"; el.style.color = "#ff4757"; }
                else {
                    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((diff % (1000 * 60)) / 1000);
                    el.innerHTML = `⏱️ ${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
                }
            });
        }

        setInterval(updateTimers, 1000); updateTimers();
        setInterval(() => { window.location.reload(); }, 45000);
    </script>
</body>
</html>
"""

def is_authenticated():
    return request.cookies.get("tosm_auth") == WEB_PASSWORD

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        pwd = request.form.get('pwd', '')
        if pwd == WEB_PASSWORD:
            response = make_response(redirect(url_for('index')))
            response.set_cookie('tosm_auth', WEB_PASSWORD, max_age=30*24*60*60, path='/')
            return response
        return render_template_string(LOGIN_TEMPLATE, error=True)
    return render_template_string(LOGIN_TEMPLATE, error=False)

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('login')))
    response.delete_cookie('tosm_auth', path='/')
    return response

@app.route('/')
def index():
    if not is_authenticated():
        return redirect(url_for('login'))

    boss_db = update_boss_statuses()
    now = get_bkk_now()
    sort_by = request.cookies.get('boss_sort_order', 'time')
    boss_phases = boss_db.get("boss_phases", {})

    in_phase_list = []
    for key, t_str in boss_db["in_phase"].items():
        if '-' not in str(key): continue
        boss_id, ch = key.split('-', 1)
        try:
            spawn_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
            iso_time = spawn_time.isoformat()
        except:
            spawn_time = now; iso_time = now.isoformat()

        try: boss_level = int(boss_id)
        except: boss_level = -1

        phase_val = round(float(boss_phases.get(key, 1.0)), 1)
        phase_str = f"{phase_val:.1f}"
        phase_main, phase_sub = phase_str.split('.')

        in_phase_list.append({
            "boss_id": boss_id, "boss_level": boss_level, "ch": ch, "t_str": t_str,
            "spawn_time_obj": spawn_time, "iso_time": iso_time,
            "phase_val": phase_val, "phase_main": phase_main, "phase_sub": phase_sub
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
            spawn_time = now; iso_time = now.isoformat()

        try: boss_level = int(boss_id)
        except: boss_level = -1

        upcoming_list.append({
            "boss_id": boss_id, "boss_level": boss_level, "ch": ch, "t_str": t_str,
            "spawn_time_obj": spawn_time, "iso_time": iso_time
        })

    if sort_by == 'level': active_spawns_sorted = sorted(upcoming_list, key=lambda x: (-x["boss_level"], x["spawn_time_obj"]))
    else: active_spawns_sorted = sorted(upcoming_list, key=lambda x: x["spawn_time_obj"])

    return render_template_string(
        HTML_TEMPLATE, in_phase_list_sorted=in_phase_list_sorted, 
        active_spawns_sorted=active_spawns_sorted, current_sort=sort_by
    )

@app.route('/set_phase/<boss_id>/<ch>')
def set_phase(boss_id, ch):
    if not is_authenticated(): return jsonify({"status": "unauthorized"}), 401
    try:
        boss_db = load_data()
        key = f"{boss_id}-{ch}"
        phase_val = float(request.args.get('phase', 1.0))
        
        if "boss_phases" not in boss_db:
            boss_db["boss_phases"] = {}
            
        boss_db["boss_phases"][key] = round(phase_val, 1)
        save_data(boss_db)
    except: pass
    return jsonify({"status": "success"})

@app.route('/add_phase/<boss_id>/<ch>')
def add_phase(boss_id, ch):
    if not is_authenticated(): return jsonify({"status": "unauthorized"}), 401
    try:
        boss_db = load_data()
        key = f"{boss_id}-{ch}"
        delta = float(request.args.get('delta', 0.2))
        
        if "boss_phases" not in boss_db:
            boss_db["boss_phases"] = {}
            
        curr_val = float(boss_db["boss_phases"].get(key, 1.0))
        boss_db["boss_phases"][key] = round(curr_val + delta, 1)
        save_data(boss_db)
    except: pass
    return jsonify({"status": "success"})

@app.route('/add', methods=['POST'])
def add_boss():
    if not is_authenticated(): return jsonify({"status": "unauthorized"}), 401
    try:
        boss_db = load_data()
        boss_id = request.form.get('boss_id').strip()
        ch = request.form.get('ch').strip()
        time_input = request.form.get('time_input', '').strip()

        key = f"{boss_id}-{ch}"
        boss_db["active_spawns"].pop(key, None)
        boss_db["in_phase"].pop(key, None)
        boss_db["dead_status"].pop(key, None)
        if "boss_phases" in boss_db:
            boss_db["boss_phases"].pop(key, None)

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
    if not is_authenticated(): return jsonify({"status": "unauthorized"}), 401
    try:
        boss_db = load_data()
        key = f"{boss_id}-{ch}"
        boss_db["in_phase"].pop(key, None)
        boss_db["dead_status"].pop(key, None)
        if "boss_phases" in boss_db:
            boss_db["boss_phases"].pop(key, None)

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
    if not is_authenticated(): return jsonify({"status": "unauthorized"}), 401
    try:
        boss_db = load_data()
        key = f"{boss_id}-{ch}"
        boss_db["active_spawns"].pop(key, None)
        boss_db["in_phase"].pop(key, None)
        boss_db["dead_status"].pop(key, None)
        if "boss_phases" in boss_db:
            boss_db["boss_phases"].pop(key, None)
        save_data(boss_db)
    except: pass
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)