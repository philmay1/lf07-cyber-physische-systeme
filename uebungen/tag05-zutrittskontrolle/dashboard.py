#!/usr/bin/env python3
"""Live-Dashboard der Zutrittskontrolle (Flask).

Start auf dem Pi:  python3 dashboard.py
Aufruf im Browser: http://<IP-des-Pi>:5000  (im Heimnetz oder über Tailscale, auch am Handy)

Zeigt live den Zustand (bereit / gesperrt mit Countdown), die Fehlversuche und das
Protokoll. Ein Admin kann mit seiner PIN die Sperre aus der Ferne aufheben.
Das Dashboard liest dieselbe zutritt.db wie das Keypad-Programm.
"""
import time

from flask import Flask, jsonify, request

import zutritt_db as db

app = Flask(__name__)


@app.route("/api/status")   # Flask 1.1 auf dem Pi kennt noch kein @app.get
def api_status():
    con = db.verbinden()
    s = db.status(con)
    s["max"] = db.MAX_FEHLVERSUCHE
    s["versuche"] = [{
        "zeit": time.strftime("%H:%M:%S", time.localtime(v["zeit"])),
        "erfolg": bool(v["erfolg"]),
        "name": v["name"] or "",
        "hinweis": v["hinweis"] or ""} for v in db.letzte_versuche(con, 12)]
    return jsonify(s)


@app.route("/api/entsperren", methods=["POST"])
def api_entsperren():
    con = db.verbinden()
    pin = str((request.get_json(silent=True) or {}).get("pin", ""))
    b = db.pin_pruefen(con, pin) if pin.isdigit() else None
    if not b or b["rolle"] != "admin":
        with con:
            con.execute("INSERT INTO versuche (zeit, erfolg, hinweis) VALUES (?, 0, ?)",
                        (time.time(), "Dashboard: falsche Admin-PIN"))
        time.sleep(1)                                  # bremst Durchprobieren
        return jsonify(ok=False, meldung="Admin-PIN falsch"), 403
    db.entsperren(con, f"{b['name']} (Dashboard)")
    return jsonify(ok=True, meldung="Entsperrt")


@app.route("/")
def seite():
    return SEITE


SEITE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SENTINEL Zutritt</title>
<style>
:root{--bg:#0f1115;--karte:#181b22;--text:#e8eaf0;--leise:#8a90a0;--gruen:#2fbf71;--rot:#e5484d;--gelb:#f5b83d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.4 system-ui,sans-serif;padding:16px}
main{max-width:720px;margin:0 auto;display:grid;gap:16px}
h1{font-size:15px;letter-spacing:.12em;color:var(--leise);margin:4px 0 0;font-weight:600}
.karte{background:var(--karte);border-radius:16px;padding:20px}
#zustand{display:flex;align-items:center;gap:20px}
#ring{width:110px;height:110px;border-radius:50%;display:grid;place-items:center;font-size:44px;
 border:6px solid var(--gruen);transition:border-color .3s,box-shadow .3s;flex:none}
.gesperrt #ring{border-color:var(--rot);box-shadow:0 0 40px #e5484d55;animation:puls 1s infinite alternate}
@keyframes puls{to{box-shadow:0 0 10px #e5484d22}}
#titel{font-size:28px;font-weight:700}#unter{color:var(--leise)}
.punkte{display:flex;gap:8px;margin-top:10px}.punkt{width:14px;height:14px;border-radius:50%;background:#2a2f3a}
.punkt.an{background:var(--gelb)}
table{width:100%;border-collapse:collapse;font-size:14px}td{padding:7px 4px;border-top:1px solid #252a33}
td:first-child{color:var(--leise);font-variant-numeric:tabular-nums;width:80px}
.ok{color:var(--gruen)}.fehler{color:var(--rot)}
form{display:flex;gap:8px}input{flex:1;min-width:0;background:#0f1115;border:1px solid #2a2f3a;color:var(--text);
 border-radius:10px;padding:10px;font-size:16px}button{background:var(--gruen);border:0;border-radius:10px;padding:10px 16px;
 font-weight:700;color:#06210f;cursor:pointer}#meldung{color:var(--leise);font-size:14px;margin-top:8px;min-height:1em}
</style></head><body><main>
<h1>SENTINEL · ZUTRITTSKONTROLLE</h1>
<section class="karte" id="zustand"><div id="ring">🔓</div>
 <div><div id="titel">Bereit</div><div id="unter">PIN am Keypad eingeben</div>
 <div class="punkte" id="punkte"></div></div></section>
<section class="karte"><table id="log"></table></section>
<section class="karte"><form id="frm"><input id="pin" type="password" inputmode="numeric"
 autocomplete="off" placeholder="Admin-PIN zum Entsperren"><button>Entsperren</button></form>
 <div id="meldung"></div></section>
</main><script>
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
async function laden(){
 try{const s=await (await fetch('/api/status')).json();
  document.body.classList.toggle('gesperrt',s.gesperrt);
  $('ring').textContent=s.gesperrt?'🔒':'🔓';
  if(s.gesperrt){const r=Math.ceil(s.rest);$('titel').textContent='GESPERRT';
   $('unter').textContent='noch '+Math.floor(r/60)+':'+String(r%60).padStart(2,'0')+' min · Sperrstufe '+s.sperr_stufe}
  else{$('titel').textContent='Bereit';$('unter').textContent='PIN am Keypad eingeben'}
  $('punkte').innerHTML=Array.from({length:s.max},(_,i)=>'<span class="punkt'+(i<s.fehlversuche?' an':'')+'"></span>').join('');
  $('log').innerHTML=s.versuche.map(v=>'<tr><td>'+v.zeit+'</td><td class="'+(v.erfolg?'ok':'fehler')+'">'+
   (v.erfolg?'✔':'✖')+'</td><td>'+esc(v.name)+'</td><td>'+esc(v.hinweis)+'</td></tr>').join('')||'<tr><td>Noch keine Versuche</td></tr>';
 }catch(e){$('unter').textContent='keine Verbindung zum Pi'}}
$('frm').onsubmit=async e=>{e.preventDefault();
 const r=await fetch('/api/entsperren',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:$('pin').value})});
 $('meldung').textContent=(await r.json()).meldung;$('pin').value='';laden()};
laden();setInterval(laden,1000);
</script></body></html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
