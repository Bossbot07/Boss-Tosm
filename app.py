from flask import Flask, render_template_string, request, jsonify, make_response, redirect, url_for
from datetime import datetime, timedelta
import requests
import pytz
import json

app = Flask(__name__)

# 🔑 ตั้งค่ารหัสผ่านเข้าเว็บตรงนี้ครับ
WEB_PASSWORD = "778"

# Config ฐานข้อมูล Upstash ของคุณ
REDIS_URL = "https://helping-egret-126070.upstash.io"
REDIS_TOKEN = "gQAAAAAAAex2AAIgcDJhNDlkZThkNGI5OTc0YTQxYjUzMjU4MTcyNTRhZWM1MQ"
BKK_TZ = pytz.timezone('Asia/Bangkok')

def get_bkk_now():
    return datetime.now(pytz.utc).astimezone(BKK_TZ)

def load_data():
    default_data = {"active_spawns": {}, "in_phase": {}, "dead_status": {}, "online_users": {}}
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
                    "online_users": data.get("online_users", {})
                }
        else:
            print(f"⚠️ Upstash Error Code: {response.status_code}")
    except Exception as e:
        print(f"❌ โหลดข้อมูลล้มเหลว: {e}")
    return default_data

def save_data(data):
    try:
        headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
        payload = json.dumps(data)
        response = requests.post(f"{REDIS_URL}/set/tosm_boss_db", headers=headers, data=payload, timeout=5)
    except Exception as e:
        print(f"❌ บันทึกข้อมูลออนไลน์ล้มเหลว: {e}")

def update_boss_statuses():
    boss_db = load_data()
    now = get_bkk_now()
    has_change = False

    # 1. ย้ายบอสเข้าเฟส
    for key, t_str in list(boss_db["active_spawns"].items()):
        try:
            naive_time = datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
            target_time = BKK_TZ.localize(naive_time)
            if now >= target_time:
                boss_db["in_phase"][key] = t_str
                boss_db["active_spawns"].pop(key, None)
                has_change = True
        except: continue

    # 2. ลบบอสในเฟสที่เกิน 90 นาที
    for key, t_str in list(boss_db["in_phase"].items()):
        try:
            naive_time = datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
            spawn_time = BKK_TZ.localize(naive_time)
            if now >= (spawn_time + timedelta(minutes=90)):
                boss_db["in_phase"].pop(key, None)
                boss_db["dead_status"].pop(key, None)
                has_change = True
        except: continue

    # 3. เคลียร์ User ที่ขาดการเชื่อมต่อ (Timeout 5 วินาที)
    for user, last_ping_str in list(boss_db.get("online_users", {}).items()):
        try:
            lp_time = BKK_TZ.localize(datetime.strptime(last_ping_str, '%Y-%m-%d %H:%M:%S'))
            if now >= (lp_time + timedelta(seconds=5)):
                boss_db["online_users"].pop(user, None)
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
        body { background-color: #121212 !important; color: #e0e0e0 !important; font-family: sans-serif; }
        .login-box { max-width: 360px; margin: 100px auto 0px; background-color: #1e1e1e; padding: 25px; border-radius: 10px; border: 1px solid #333; box-shadow: 0px 4px 15px rgba(0,0,0,0.5); }
    </style>
</head>
<body class="container px-3">
    <div class="login-box text-center">
        <h3 class="text-warning mb-4">⚔️ TOSM BOSS TRACKER</h3>
        {% if error %}
        <div class="alert alert-danger py-2" style="font-size: 14px;">❌ รหัสผ่านไม่ถูกต้องครับ</div>
        {% endif %}
        <form method="POST" action="/login">
            <div class="mb-3 text-start">
                <label class="form-label text-muted mb-1" style="font-size:13px;">ชื่อผู้ใช้งาน (แสดงในระบบตี้)</label>
                <input type="text" name="username" class="form-control bg-dark text-white border-secondary text-center fw-bold text-warning" placeholder="พิมพ์ชื่อเล่นของคุณ..." required autofocus>
            </div>
            <div class="mb-3 text-start">
                <label class="form-label text-muted mb-1" style="font-size:13px;">รหัสผ่านเข้าเว็บ</label>
                <input type="password" name="pwd" class="form-control bg-dark text-white border-secondary text-center" placeholder="ใส่รหัสผ่านเพื่อเข้าใช้งาน" required>
            </div>
            <button type="submit" class="btn btn-warning w-100 fw-bold mt-2">🔓 เข้าสู่ระบบ</button>
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
        body { background-color: #121212 !important; color: #e0e0e0 !important; font-family: sans-serif !important; font-size: 15px !important; }
        .main-container { max-width: 680px !important; margin: 0 auto; }
        
        .boss-card { background-color: #1e1e1e !important; border: 1px solid #333 !important; color: #fff !important; padding: 12px 14px !important; margin-bottom: 7px !important; border-radius: 8px !important; }
        .in-phase-bg { border-left: 6px solid #ff4757 !important; }
        .upcoming-bg { border-left: 6px solid #2ed573 !important; }
        .boss-dead-bg { background-color: #181818 !important; border: 1px dashed #444 !important; opacity: 0.65 !important; border-left: 6px solid #6c757d !important; }
        
        .col-boss-info { width: 38% !important; min-width: 120px; flex-shrink: 0; }
        .col-boss-center { width: 30% !important; text-align: left !important; flex-shrink: 0; display: flex; align-items: center; }
        .col-boss-action { width: 32% !important; display: flex; justify-content: flex-end; align-items: center; gap: 6px; flex-shrink: 0; }
        
        .boss-title { font-size: 16px !important; font-weight: bold; }
        .time-text { font-size: 16px !important; font-weight: bold; }
        .countdown-text { font-size: 15px !important; font-weight: bold !important; color: #2ed573 !important; white-space: nowrap; }
        
        .form-control-sm, .form-select-sm { font-size: 14px !important; padding: 6px 10px !important; height: 38px !important; }
        .btn-custom-sm { font-size: 14px !important; padding: 6px 10px !important; height: 34px !important; line-height: 1.2 !important; font-weight: bold !important; border-radius: 6px !important; }
        .btn-delete { padding: 6px 10px !important; height: 34px !important; font-size: 14px !important; border-radius: 6px !important; }
        
        h2 { font-size: 22px !important; margin: 0 !important; font-weight: bold !important; }
        h4 { font-size: 16px !important; margin-top: 16px !important; margin-bottom: 8px !important; font-weight: bold !important; }
        .badge-phase { font-size: 13px !important; padding: 5px 8px !important; font-weight: bold; border-radius: 6px !important; }
        
        .modal { z-index: 99999 !important; background-color: rgba(0,0,0,0.6) !important; }
        .panel-box { background-color: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px solid #2d2d2d; margin-bottom: 10px; }
        .red-badge-item { display: inline-flex; align-items: center; background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 20px; font-size: 13px; font-weight: bold; margin-right: 5px; margin-bottom: 5px; }
        .red-badge-delete { background: none; border: none; color: white; font-weight: bold; margin-left: 6px; cursor: pointer; padding: 0; font-size: 12px; }
    </style>
</head>
<body class="container-fluid px-2 py-2">
    <div class="main-container">
        
        <div class="d-flex justify-content-between align-items-center mb-2 gap-2">
            <h2 class="text-warning">⚔️ TOSM BOSS</h2>
            <div class="d-flex gap-2 align-items-center flex-wrap justify-content-end">
                <div style="font-size:13px;" class="text-end me-1">
                    <span class="text-info fw-bold">👤 {{ current_user }}</span>
                    <span class="text-muted mx-1">|</span>
                    <span class="text-success fw-bold">🟢 Online: 
                        {% for user in online_users %}
                            {% if user != current_user %}
                                <span class="badge bg-dark border border-success text-success ms-1" style="font-size: 11px; padding: 3px 6px;">{{ user }}</span>
                            {% endif %}
                        {% else %}
                            <span class="text-muted" style="font-size: 11px;">ไม่มีคนอื่น</span>
                        {% endfor %}
                    </span>
                </div>
                <select id="sortSelector" class="form-select form-select-sm bg-dark text-white border-secondary" onchange="changeSortOrder(this.value)" style="width: auto;">
                    <option value="time" {% if current_sort == 'time' %}selected{% endif %}>🕒 เวลาเกิด</option>
                    <option value="level" {% if current_sort == 'level' %}selected{% endif %}>⚔️ เลเวลบอส</option>
                </select>
                <a href="/logout" class="btn btn-outline-secondary btn-custom-sm py-1 px-2" style="font-size:12px !important; height:auto !important;">🔒 ออก ({{ current_user }})</a>
            </div>
        </div>

        <div class="panel-box">
            <div class="d-flex flex-wrap align-items-center gap-2">
                <button class="btn btn-outline-light btn-custom-sm flex-grow-1" id="btn-filter-all" onclick="setMode('all')">👁️ ทั้งหมด</button>
                <button class="btn btn-outline-light btn-custom-sm flex-grow-1" id="btn-filter-under100" onclick="setMode('under100')">📉 เลเวล ≤ 100</button>
                <button class="btn btn-outline-danger btn-custom-sm flex-grow-1" id="btn-filter-redcard" onclick="setMode('redcard')">🔴 เฉพาะการ์ดแดง</button>
            </div>
            <div class="d-flex align-items-center gap-2 mt-2 pt-2 border-top border-secondary">
                <span class="text-info fw-bold" style="font-size: 14px; white-space: nowrap;">🎯 เลเวล:</span>
                <input type="number" id="levelFilterInput" class="form-control form-control-sm bg-dark text-warning border-info fw-bold text-center" placeholder="พิมพ์กรองเลเวลที่ต้องการ..." oninput="handleMinLevelInput(this.value)">
                <span class="text-muted fw-bold" style="font-size: 14px;">+</span>
            </div>
        </div>

        <div class="panel-box">
            <div class="d-flex align-items-center gap-2 mb-2">
                <span class="text-danger fw-bold" style="font-size: 14px; white-space: nowrap;">📌 เพิ่มกลุ่มการ์ดแดง:</span>
                <input type="number" id="redCardInput" class="form-control form-control-sm bg-dark text-white border-danger text-center" placeholder="เลเวล เช่น 120" style="max-width: 120px;">
                <button onclick="addRedCard()" class="btn btn-danger btn-custom-sm">➕ เพิ่ม</button>
            </div>
            <div id="redCardListContainer" class="d-flex flex-wrap pt-1"></div>
        </div>
        
        <div class="boss-card p-2 mb-3">
            <form id="addBossForm" onsubmit="submitAddForm(event)" class="row g-2">
                <div class="col-3"><input type="text" id="boss_id" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="เลขบอส" required></div>
                <div class="col-3"><input type="number" id="ch" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="แนล" required></div>
                <div class="col-3"><input type="text" id="time_input" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="นาที (-5)"></div>
                <div class="col-3"><button type="submit" class="btn btn-warning btn-custom-sm w-100" style="height: 38px !important;">➕ บันทึก</button></div>
            </form>
        </div>

        <h4 class="text-danger">🚨 เข้าเฟสแล้ว (In Phase)</h4>
        <div class="d-flex flex-column gap-1 mb-4" id="in-phase-container">
            {% for item in in_phase_list_sorted %}
            <div class="boss-card {% if item.is_dead %}boss-dead-bg{% else %}in-phase-bg{% endif %} d-flex align-items-center m-0 boss-item-row" data-boss-level="{{ item.boss_level }}">
                <div class="col-boss-info">
                    <span class="{% if item.is_dead %}text-secondary text-decoration-line-through{% else %}text-danger{% endif %} boss-title">
                        {% if item.is_dead %}💀 บอส {{ item.boss_id }} [Ch.{{ item.ch }}]{% else %}🔥 บอส {{ item.boss_id }} [Ch.{{ item.ch }}]{% endif %}
                    </span>
                </div>
                <div class="col-boss-center">
                    {% if item.is_dead %}
                    <span class="badge bg-secondary badge-phase" style="font-size:11px !important;">💀 ตายโดย: {{ item.dead_by }}</span>
                    {% else %}
                    <span class="badge bg-danger badge-phase">เข้าเฟส {{ item.minutes_passed }} น.</span>
                    {% endif %}
                </div>
                <div class="col-boss-action">
                    <button onclick="killBoss('{{ item.boss_id }}', '{{ item.ch }}')" class="btn btn-success btn-custom-sm">ใส่เวลาใหม่</button>
                    {% if item.is_dead %}
                    <button onclick="runApi('/toggle_dead/{{ item.boss_id }}/{{ item.ch }}')" class="btn btn-outline-warning btn-custom-sm">🔄</button>
                    {% else %}
                    <button onclick="runApi('/toggle_dead/{{ item.boss_id }}/{{ item.ch }}')" class="btn btn-outline-secondary btn-custom-sm fw-bold" style="color: #bbb;">💀 Dead</button>
                    {% endif %}
                    <button onclick="runApi('/delete/{{ item.boss_id }}/{{ item.ch }}')" class="btn btn-outline-danger btn-custom-sm btn-delete">🗑️</button>
                </div>
            </div>
            {% else %}
            <p class="text-muted ps-1 m-0 empty-text-notice" style="font-size: 14px;">ไม่มีบอสในเฟส...</p>
            {% endfor %}
            <p class="text-muted ps-1 m-0 d-none filter-empty-notice" style="font-size: 14px;">ไม่มีบอสที่ตรงกับเงื่อนไขตัวกรอง...</p>
        </div>

        <h4 class="text-success">⏳ กำลังรอเกิด (Upcoming)</h4>
        <div class="d-flex flex-column gap-1" id="upcoming-container">
            {% for item in active_spawns_sorted %}
            <div class="boss-card upcoming-bg d-flex align-items-center m-0 boss-item-row" data-boss-level="{{ item.boss_level }}">
                <div class="col-boss-info"><span class="text-success boss-title">⏳ บอส {{ item.boss_id }} [Ch.{{ item.ch }}]</span></div>
                <div class="col-boss-center"><span class="text-warning time-text">{{ item.t_str[11:16] }}</span></div>
                <div class="col-boss-action">
                    <div class="countdown-text m-0" data-target-time="{{ item.iso_time }}">คำนวณ...</div>
                    <button onclick="runApi('/delete/{{ item.boss_id }}/{{ item.ch }}')" class="btn btn-outline-danger btn-custom-sm btn-delete">🗑️</button>
                </div>
            </div>
            {% else %}
            <p class="text-muted ps-1 m-0 empty-text-notice" style="font-size: 14px;">ไม่มีบอสรอเกิด...</p>
            {% endfor %}
            <p class="text-muted ps-1 m-0 d-none filter-empty-notice" style="font-size: 14px;">ไม่มีบอสที่ตรงกับเงื่อนไขตัวกรอง...</p>
        </div>

    </div>

    <div class="modal fade" id="killModal" tabindex="-1" data-bs-backdrop="false" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm" style="max-width: 320px;">
            <div class="modal-content bg-dark text-white border-secondary" style="border: 1px solid #555 !important;">
                <div class="modal-body p-3">
                    <input type="hidden" id="modal-boss-id"><input type="hidden" id="modal-ch">
                    <div class="mb-3">
                        <label class="form-label mb-2" style="font-size: 14px; font-weight: bold;">ใส่เวลาเกิดรอบถัดไป (นาที)</label>
                        <input type="text" id="modal-time-input" class="form-control bg-secondary text-white border-0" placeholder="ว่าง=ตอนนี้, หรือใส่ -5, 1.30" onkeydown="handleModalKeyDown(event)" style="font-size: 15px; height: 42px;">
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

        function sendOnlinePing() {
            fetch('/api/ping').catch(() => {});
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
            if (!lvl || lvl <= 0) return alert('กรุณากรอกเลเวลบอสที่ถูกต้องครับ');
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
            if (redCards.length === 0) { container.innerHTML = '<span class="text-muted" style="font-size: 13px;">ไม่มีเลเวลการ์ดแดงในรายการ...</span>'; return; }
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

                if (passMode && passMinLevel) { row.classList.remove('d-none'); row.classList.add('d-flex'); }
                else { row.classList.remove('d-flex'); row.classList.add('d-none'); }
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

        window.addEventListener('DOMContentLoaded', () => {
            loadRedCards();
            const savedMode = getCookie('tosm_filter_mode') || 'all';
            const savedMinLvl = parseInt(getCookie('tosm_min_level_val')) || 0;
            if(savedMinLvl > 0) { document.getElementById('levelFilterInput').value = savedMinLvl; minLevelFilter = savedMinLvl; }
            setMode(savedMode);
            
            sendOnlinePing();
            setInterval(sendOnlinePing, 2000); 
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

        function updateCountdowns() {
            const now = new Date().getTime();
            const elements = document.querySelectorAll('[data-target-time]');
            let needReload = false;
            
            elements.forEach(el => {
                const targetIso = el.getAttribute('data-target-time');
                const targetTime = new Date(targetIso).getTime();
                const diff = targetTime - now;
                
                if (diff <= 0) { 
                    el.innerHTML = "💥 เกิดแล้ว!"; 
                    el.style.color = "#ff4757"; 
                    needReload = true; 
                } else {
                    const hours = Math.floor(diff / (1000 * 60 * 60));
                    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((diff % (1000 * 60)) / 1000);
                    
                    const displayMinutes = minutes; 
                    const displaySeconds = String(seconds).padStart(2, '0');
                    if (hours > 0) {
                        const paddedMinutes = String(minutes).padStart(2, '0');
                        el.innerHTML = `⏱️ ${hours}:${paddedMinutes}:${displaySeconds}`;
                    } else {
                        el.innerHTML = `⏱️ ${displayMinutes}:${displaySeconds}`;
                    }
                }
            });
            
            if (needReload) { 
                window.location.reload(); 
            }
        }

        setInterval(updateCountdowns, 1000); updateCountdowns();
        setInterval(() => { window.location.reload(); }, 45000);
    </script>
</body>
</html>
"""

def is_authenticated():
    return request.cookies.get("tosm_auth") == WEB_PASSWORD

def get_current_user():
    return request.cookies.get("tosm_user", "Unknown")

@app.route('/api/ping')
def api_ping():
    if not is_authenticated(): return jsonify({"status": "unauthorized"}), 401
    try:
        boss_db = load_data()
        user = get_current_user()
        if "online_users" not in boss_db:
            boss_db["online_users"] = {}
        boss_db["online_users"][user] = get_bkk_now().strftime('%Y-%m-%d %H:%M:%S')
        save_data(boss_db)
    except: pass
    return jsonify({"status": "pong"})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        pwd = request.form.get('pwd', '')
        username = request.form.get('username', '').strip() or "Player"
        if pwd == WEB_PASSWORD:
            response = make_response(redirect(url_for('index')))
            response.set_cookie('tosm_auth', WEB_PASSWORD, max_age=30*24*60*60, path='/')
            response.set_cookie('tosm_user', username, max_age=30*24*60*60, path='/')
            return response
        return render_template_string(LOGIN_TEMPLATE, error=True)
    return render_template_string(LOGIN_TEMPLATE, error=False)

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('login')))
    response.delete_cookie('tosm_auth', path='/')
    response.delete_cookie('tosm_user', path='/')
    return response

@app.route('/')
def index():
    if not is_authenticated():
        return redirect(url_for('login'))
        
    boss_db = update_boss_statuses()
    now = get_bkk_now()
    sort_by = request.cookies.get('boss_sort_order', 'time')
    current_user = get_current_user()
    
    online_users = list(boss_db.get("online_users", {}).keys())
    
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
            spawn_time = now; minutes_passed = 0
            
        try: boss_level = int(boss_id)
        except: boss_level = -1
            
        dead_val = boss_db.get("dead_status", {}).get(key, False)
        is_dead = False
        dead_by = "Unknown"
        if dead_val:
            is_dead = True
            dead_by = dead_val if isinstance(dead_val, str) else "ตี้เรา"
            
        in_phase_list.append({
            "boss_id": boss_id, "boss_level": boss_level, "ch": ch, "t_str": t_str,
            "spawn_time_obj": spawn_time, "minutes_passed": minutes_passed,
            "is_dead": is_dead, "dead_by": dead_by
        })
    
    if sort_by == 'level':
        in_phase_list_sorted = sorted(in_phase_list, key=lambda x: (x["is_dead"], -x["boss_level"], x["spawn_time_obj"]))
    else:
        in_phase_list_sorted = sorted(in_phase_list, key=lambda x: (x["is_dead"], x["spawn_time_obj"]))
    
    upcoming_list = []
    for key, t_str in boss_db["active_spawns"].items():
        if '-' not in str(key): continue
        boss_id, ch = key.split('-', 1)
        try:
            spawn_time = BKK_TZ.localize(datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S'))
            iso_time = spawn_time.strftime('%Y-%m-%dT%H:%M:%S')
        except:
            spawn_time = now; iso_time = now.strftime('%Y-%m-%dT%H:%M:%S')
        
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
        active_spawns_sorted=active_spawns_sorted, current_sort=sort_by,
        current_user=current_user, online_users=online_users
    )

@app.route('/toggle_dead/<boss_id>/<ch>')
def toggle_dead(boss_id, ch):
    if not is_authenticated(): return jsonify({"status": "unauthorized"}), 401
    try:
        boss_db = load_data()
        key = f"{boss_id}-{ch}"
        user = get_current_user()
        
        if key in boss_db.get("dead_status", {}):
            boss_db["dead_status"].pop(key, None)
        else:
            if "dead_status" not in boss_db:
                boss_db["dead_status"] = {}
            boss_db["dead_status"][key] = user
            
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
        save_data(boss_db)
    except: pass
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)