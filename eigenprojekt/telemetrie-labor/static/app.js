// Telemetrie-Labor: die ganze Oberfläche. Eine Seite, die je nach Adresse (#/...) etwas anderes zeigt.
//   #/                 Sitzungen und Upload
//   #/sitzung/<id>     Runden einer Sitzung
//   #/vergleich/<a>/<b> zwei Runden übereinander (Karte, Kurven, Abschnitte)
//   #/bestenliste      schnellste Runde pro Strecke und Auto
//   #/info             wie das Labor gebaut ist

'use strict';

// ---------- Hilfen ----------
const app = document.getElementById('app');
// Zustand vom Server: Login nötig? Darf dieser Browser hochladen?
let STATUS = { login_noetig: false, darf_aendern: false, max_mb: 1500 };
// Alle Diagramme der aktuellen Seite (zum Aufräumen und für die Größe).
let diagramme = [];

// Text sicher in HTML einsetzen: <, >, & und " werden unschädlich.
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// Sekunden als Rundenzeit: 79.03 -> "1:19.030".
const zeit = s => s == null ? '–' : `${Math.floor(s / 60)}:${(s % 60).toFixed(3).padStart(6, '0')}`;
// Differenz mit Vorzeichen: +0.214 / -0.051.
const diff = s => (s >= 0 ? '+' : '−') + Math.abs(s).toFixed(3);
// Daten vom Server holen (JSON).
async function api(url, opt) {
  const r = await fetch(url, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.meldung || `Fehler ${r.status}`);
  return j;
}

// ---------- Login ----------
async function statusLaden() {
  STATUS = await api('/api/status');
  const knopf = document.getElementById('login');
  knopf.hidden = !STATUS.login_noetig;
  knopf.textContent = STATUS.darf_aendern ? 'Abmelden' : 'Anmelden';
}
document.getElementById('login').addEventListener('click', async () => {
  if (STATUS.darf_aendern) { await api('/api/logout', { method: 'POST' }); await statusLaden(); zeigen(); return; }
  document.getElementById('loginFenster').hidden = false;
  document.getElementById('loginPasswort').focus();
});
document.getElementById('loginAbbruch').addEventListener('click', () => document.getElementById('loginFenster').hidden = true);
document.getElementById('loginForm').addEventListener('submit', async e => {
  e.preventDefault();
  const fehler = document.getElementById('loginFehler');
  fehler.textContent = '';
  try {
    await api('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ passwort: document.getElementById('loginPasswort').value }) });
    document.getElementById('loginFenster').hidden = true;
    document.getElementById('loginPasswort').value = '';
    await statusLaden(); zeigen();
  } catch (err) { fehler.textContent = err.message; }
});

// ---------- Seitenwechsel ----------
async function zeigen() {
  diagramme.forEach(d => d.destroy()); diagramme = [];
  const teile = location.hash.replace(/^#\/?/, '').split('/');
  try {
    if (teile[0] === 'sitzung') await ansichtSitzung(+teile[1]);
    else if (teile[0] === 'vergleich') await ansichtVergleich(+teile[1], +(teile[2] || teile[1]));
    else if (teile[0] === 'bestenliste') await ansichtBestenliste();
    else if (teile[0] === 'info') await ansichtInfo();
    else await ansichtStart();
  } catch (err) { app.innerHTML = `<p class="fehler">${esc(err.message)}</p>`; }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', zeigen);

// ---------- Start: Upload und Sitzungen ----------
async function ansichtStart() {
  const liste = await api('/api/sitzungen');
  app.innerHTML = `
    <h1>Sitzungen</h1>
    <p class="leise">.ibt-Datei hochladen. Der Pi zerlegt sie in Runden, prüft jede Runde und speichert die Messkurven in SQLite.</p>
    <div class="karte upload" id="upload">
      ${STATUS.darf_aendern
        ? `<p><b>.ibt hierher ziehen</b> oder <button id="waehlen">Datei wählen</button></p>
           <p class="leise mono">Dokumente\\iRacing\\telemetry · bis ${STATUS.max_mb} MB</p>
           <input id="datei" type="file" accept=".ibt" hidden>
           <div class="balken" hidden><div></div></div><p id="uploadText" class="leise"></p>`
        : `<p class="leise">Zum Hochladen ${STATUS.login_noetig ? 'oben rechts anmelden' : 'die Seite direkt am Pi öffnen'}.</p>`}
    </div>
    <h2>${liste.length} Sitzungen</h2>
    ${liste.length ? `<div class="karte"><table>
      <tr><th>Gefahren</th><th>Strecke</th><th>Auto</th><th>Art</th><th>Runden</th><th>Beste Runde</th></tr>
      ${liste.map(s => `<tr class="klickbar" data-id="${s.id}">
        <td class="mono">${esc(s.datum)}</td><td>${esc(s.strecke)}${s.layout ? ` <span class="leise">${esc(s.layout)}</span>` : ''}</td>
        <td>${esc(s.auto)}</td><td><span class="marke">${esc(s.typ)}</span></td>
        <td class="mono">${s.gueltige || 0} / ${s.runden}</td><td class="mono">${zeit(s.beste)}</td></tr>`).join('')}
    </table></div>` : '<p class="leise">Noch nichts hochgeladen.</p>'}`;
  app.querySelectorAll('tr[data-id]').forEach(tr => tr.addEventListener('click', () => location.hash = `#/sitzung/${tr.dataset.id}`));
  if (STATUS.darf_aendern) uploadEinrichten();
}

// Upload mit Fortschrittsbalken (XMLHttpRequest meldet, wie viel schon übertragen ist).
function uploadEinrichten() {
  const feld = document.getElementById('upload'), eingabe = document.getElementById('datei');
  document.getElementById('waehlen').addEventListener('click', () => eingabe.click());
  eingabe.addEventListener('change', () => eingabe.files[0] && hochladen(eingabe.files[0]));
  feld.addEventListener('dragover', e => { e.preventDefault(); feld.classList.add('drueber'); });
  feld.addEventListener('dragleave', () => feld.classList.remove('drueber'));
  feld.addEventListener('drop', e => { e.preventDefault(); feld.classList.remove('drueber'); e.dataTransfer.files[0] && hochladen(e.dataTransfer.files[0]); });
}
function hochladen(datei) {
  const balken = app.querySelector('.balken'), fuellung = balken.firstElementChild, text = document.getElementById('uploadText');
  balken.hidden = false;
  const x = new XMLHttpRequest();
  x.open('POST', '/api/upload');
  // Datei als reinen Datenstrom schicken (schneller als ein Formular), den Namen im Kopf der Anfrage.
  x.setRequestHeader('Content-Type', 'application/octet-stream');
  x.setRequestHeader('X-Dateiname', encodeURIComponent(datei.name));
  const start = performance.now();
  x.upload.onprogress = e => {
    const p = e.loaded / e.total * 100;
    fuellung.style.width = p + '%';
    text.textContent = `Übertrage ${datei.name}: ${(e.loaded / 1048576).toFixed(0)} von ${(e.total / 1048576).toFixed(0)} MB`;
    if (p >= 100) text.textContent = 'Übertragen. Der Pi liest die Datei und zerlegt sie in Runden ...';
  };
  x.onload = () => {
    let j = {}; try { j = JSON.parse(x.responseText); } catch (e) {}
    if (x.status === 200 && j.ok) {
      text.textContent = `Fertig in ${((performance.now() - start) / 1000).toFixed(1)} s.`;
      location.hash = `#/sitzung/${j.sitzung}`;
    } else { text.innerHTML = `<span class="fehler">${esc(j.meldung || 'Upload fehlgeschlagen')}</span>`; }
  };
  x.onerror = () => text.innerHTML = '<span class="fehler">Verbindung abgebrochen.</span>';
  x.send(datei);
}

// ---------- Sitzung: Runden ----------
async function ansichtSitzung(id) {
  const s = await api(`/api/sitzung/${id}`);
  const gueltig = s.runden.filter(r => r.gueltig).sort((a, b) => a.zeit - b.zeit);
  const beste = gueltig[0];
  // Vorauswahl für den Vergleich: beste und zweitbeste gültige Runde.
  let wahl = gueltig.slice(0, 2).map(r => r.id);
  // Säulenhöhe: von der besten Runde bis 115 % davon (langsamere Runden werden gekappt).
  const unten = beste ? beste.zeit * 0.98 : 0, oben = beste ? beste.zeit * 1.15 : 1;
  const hoehe = z => Math.max(6, Math.min(100, (z - unten) / (oben - unten) * 100));
  app.innerHTML = `
    <p><a href="#/">← Sitzungen</a></p>
    <h1>${esc(s.strecke)} ${s.layout ? `<span class="leise">${esc(s.layout)}</span>` : ''}</h1>
    <p class="leise">${esc(s.auto)} · ${esc(s.typ)} · ${esc(s.datum)} · ${(s.laenge_m / 1000).toFixed(3)} km · Datei ${esc(s.datei)}</p>
    <div class="kacheln">
      <div class="kachel"><small>Runden</small><b>${s.runden.length}</b></div>
      <div class="kachel"><small>davon sauber</small><b>${gueltig.length}</b></div>
      <div class="kachel"><small>Beste Runde</small><b class="mono">${zeit(beste?.zeit)}</b></div>
      <div class="kachel"><small>Ø sauber</small><b class="mono">${zeit(gueltig.length ? gueltig.reduce((a, r) => a + r.zeit, 0) / gueltig.length : null)}</b></div>
      <div class="kachel"><small>Höchsttempo</small><b>${Math.max(...s.runden.map(r => r.vmax)).toFixed(0)} km/h</b></div>
    </div>
    <h2>Rundenzeiten <span class="leise">(klicken = für den Vergleich wählen, grün = beste, grau = ungültig)</span></h2>
    <div class="karte"><div class="saeulen">${s.runden.map(r => `<div class="saeule ${r.gueltig ? '' : 'ungueltig'} ${beste && r.id === beste.id ? 'beste' : ''}"
      data-id="${r.id}" style="height:${hoehe(r.zeit)}%" title="Runde ${r.nummer}: ${zeit(r.zeit)}${r.grund ? ' (' + esc(r.grund) + ')' : ''}"></div>`).join('')}</div></div>
    <div class="zeile" style="margin-top:12px">
      <button id="vergleichen">Gewählte Runden vergleichen</button><span id="wahlText" class="leise"></span>
      ${STATUS.darf_aendern ? '<button id="loeschen" class="gefahr klein" style="margin-left:auto">Sitzung löschen</button>' : ''}
    </div>
    <h2>Alle Runden</h2>
    <div class="karte"><table>
      <tr><th></th><th>Runde</th><th>Zeit</th><th>zur Besten</th><th>Höchsttempo</th><th>Sprit</th><th>Status</th></tr>
      ${s.runden.map(r => `<tr class="klickbar ${r.gueltig ? '' : 'ungueltig'} ${beste && r.id === beste.id ? 'beste' : ''}" data-id="${r.id}">
        <td><input type="checkbox" data-id="${r.id}"></td><td>${r.nummer}</td><td class="mono">${zeit(r.zeit)}</td>
        <td class="mono">${beste ? diff(r.zeit - beste.zeit) : ''}</td><td>${r.vmax.toFixed(0)} km/h</td>
        <td>${r.sprit > 0 ? r.sprit.toFixed(2) + ' l' : '–'}</td><td>${r.gueltig ? 'sauber' : `<span class="marke">${esc(r.grund)}</span>`}</td></tr>`).join('')}
    </table></div>`;
  // Auswahl anzeigen (Säulen umrahmen, Häkchen setzen, Text).
  const auffrischen = () => {
    app.querySelectorAll('.saeule').forEach(e => e.classList.toggle('gewaehlt', wahl.includes(+e.dataset.id)));
    app.querySelectorAll('input[type=checkbox]').forEach(e => e.checked = wahl.includes(+e.dataset.id));
    const n = id => s.runden.find(r => r.id === id);
    document.getElementById('wahlText').textContent = wahl.length
      ? wahl.map((id, i) => `${'AB'[i]}: Runde ${n(id).nummer} (${zeit(n(id).zeit)})`).join('  ·  ') : 'keine Runde gewählt';
    document.getElementById('vergleichen').disabled = !wahl.length;
  };
  // Klick wählt eine Runde. Höchstens zwei: die älteste Wahl fliegt raus.
  const umschalten = id => { wahl = wahl.includes(id) ? wahl.filter(x => x !== id) : [...wahl, id].slice(-2); auffrischen(); };
  app.querySelectorAll('.saeule, tr[data-id]').forEach(e => e.addEventListener('click', ev => { ev.preventDefault(); umschalten(+e.dataset.id); }));
  document.getElementById('vergleichen').addEventListener('click', () => location.hash = `#/vergleich/${wahl[0]}/${wahl[1] || wahl[0]}`);
  const loeschKnopf = document.getElementById('loeschen');
  if (loeschKnopf) loeschKnopf.addEventListener('click', async () => {
    if (!confirm('Sitzung mit allen Runden löschen?')) return;
    await api(`/api/sitzung/${id}`, { method: 'DELETE' }); location.hash = '#/';
  });
  auffrischen();
}

// ---------- Vergleich zweier Runden ----------
async function ansichtVergleich(idA, idB) {
  const [A, B] = await Promise.all([api(`/api/runde/${idA}`), api(`/api/runde/${idB}`)]);
  const allein = idA === idB;
  if (A.strecke !== B.strecke) throw new Error('Die beiden Runden sind auf verschiedenen Strecken gefahren.');
  const andere = await api(`/api/runden?strecke=${encodeURIComponent(A.strecke)}`);
  const n = A.kanaele.t.length;
  const km = Array.from({ length: n }, (_, i) => i / n * A.laenge_m / 1000);
  // Zeitabstand B minus A an jeder Stelle der Strecke (negativ = B ist dort schneller).
  const delta = A.kanaele.t.map((t, i) => B.kanaele.t[i] - t);
  // Abschnitte: Strecke in 10 gleich lange Stücke teilen und die Zeit pro Stück vergleichen.
  const tEnde = (R, i) => i >= n ? R.zeit : R.kanaele.t[i];
  const abschnitte = Array.from({ length: 10 }, (_, k) => {
    const s = k * n / 10, e = (k + 1) * n / 10;
    const dA = tEnde(A, e) - A.kanaele.t[s], dB = tEnde(B, e) - B.kanaele.t[s];
    const minA = Math.min(...A.kanaele.speed.slice(s, e)), minB = Math.min(...B.kanaele.speed.slice(s, e));
    return { k, s, e, d: dB - dA, minA, minB, von: km[s], bis: k === 9 ? A.laenge_m / 1000 : km[e] };
  });
  const schlimmster = abschnitte.reduce((m, a) => a.d > m.d ? a : m, abschnitte[0]);
  const bester = abschnitte.reduce((m, a) => a.d < m.d ? a : m, abschnitte[0]);
  const maxD = Math.max(...abschnitte.map(a => Math.abs(a.d)), 0.001);
  const titel = R => `Runde ${R.nummer} · <span class="mono">${zeit(R.zeit)}</span> · ${esc(R.auto)} · ${esc(R.datum)}`;

  app.innerHTML = `
    <p><a href="#/sitzung/${A.sitzung_id}">← Sitzung</a></p>
    <h1>${esc(A.strecke)}</h1>
    <div class="legende" style="margin:6px 0 4px">
      <span><i style="background:var(--a)"></i><b class="a">A</b> ${titel(A)}</span>
      ${allein ? '' : `<span><i style="background:var(--b)"></i><b class="b">B</b> ${titel(B)}</span>`}
    </div>
    <div class="zeile" style="margin:8px 0 14px"><span class="leise">B wählen:</span>
      <select id="wahlB">${andere.map(r => `<option value="${r.id}" ${r.id === idB ? 'selected' : ''}>${zeit(r.zeit)} · ${esc(r.auto)} · Runde ${r.nummer} · ${esc(r.datum)}</option>`).join('')}</select>
      <button id="tauschen" class="zweit klein">A ⇄ B</button></div>
    ${allein ? '' : `<div class="kacheln">
      <div class="kachel"><small>B gegenüber A</small><b class="mono ${B.zeit > A.zeit ? 'plus' : 'minus'}">${diff(B.zeit - A.zeit)} s</b></div>
      <div class="kachel"><small>B verliert am meisten</small><b>${schlimmster.d > 0 ? `${diff(schlimmster.d)} s` : '–'}</b><br><span class="leise">${schlimmster.d > 0 ? `km ${schlimmster.von.toFixed(1)} bis ${schlimmster.bis.toFixed(1)}` : ''}</span></div>
      <div class="kachel"><small>B gewinnt am meisten</small><b>${bester.d < 0 ? `${diff(bester.d)} s` : '–'}</b><br><span class="leise">${bester.d < 0 ? `km ${bester.von.toFixed(1)} bis ${bester.bis.toFixed(1)}` : ''}</span></div>
      <div class="kachel"><small>Höchsttempo A / B</small><b>${A.vmax.toFixed(0)} / ${B.vmax.toFixed(0)}</b></div>
    </div>`}
    <div class="vergleich" style="margin-top:14px">
      <div class="links">
        <div class="karte"><canvas id="karte"></canvas>
          <div class="legende" style="margin-top:8px"><span><i style="background:var(--bremse)"></i>Bremse</span><span><i style="background:var(--gas)"></i>Vollgas</span><span><i style="background:#c9a227"></i>Teilgas</span><span><i style="background:#4b5d73"></i>Rollen</span>${allein ? '' : '<span><i style="background:rgba(255,159,28,.5)"></i>größter Verlust</span>'}</div>
          <p class="ablesen" id="ablesen">Maus über die Diagramme bewegen.</p>
        </div>
        ${allein ? '' : `<div class="karte" style="margin-top:12px"><h3>Abschnitte (B gegenüber A)</h3><table class="abschnitte">
          ${abschnitte.map(a => `<tr><td class="mono">km ${a.von.toFixed(1)}–${a.bis.toFixed(1)}</td><td class="mono ${a.d > 0 ? 'plus' : 'minus'}">${diff(a.d)}</td>
            <td class="balkenzelle"><div class="dbalken" style="width:${Math.abs(a.d) / maxD * 100}%;background:${a.d > 0 ? 'var(--schlecht)' : 'var(--gut)'}"></div></td>
            <td class="leise mono">${a.minA.toFixed(0)} / ${a.minB.toFixed(0)}</td></tr>`).join('')}
          </table><p class="leise" style="font-size:12px">letzte Spalte: langsamstes Tempo im Abschnitt, A / B in km/h</p></div>`}
      </div>
      <div id="diagramme"></div>
    </div>`;
  document.getElementById('wahlB').addEventListener('change', e => location.hash = `#/vergleich/${idA}/${e.target.value}`);
  document.getElementById('tauschen').addEventListener('click', () => location.hash = `#/vergleich/${idB}/${idA}`);

  // Streckenkarte zeichnen.
  const karte = karteVorbereiten(document.getElementById('karte'), A, B, allein ? null : schlimmster);
  // Diagramme: jedes bekommt eine Liste von Linien.
  const C = getComputedStyle(document.documentElement);
  const fa = C.getPropertyValue('--a').trim(), fb = C.getPropertyValue('--b').trim();
  const linien = [
    ...(allein ? [] : [['Zeitabstand B − A (s)', [[delta, fb, 'Δ']], 150]]),
    ['Tempo (km/h)', [[A.kanaele.speed, fa, 'A'], ...(allein ? [] : [[B.kanaele.speed, fb, 'B']])], 200],
    ['Gas und Bremse (%)', [[A.kanaele.gas, '#2ee59d', 'Gas A'], [A.kanaele.bremse, '#ff4d5e', 'Bremse A'],
      ...(allein ? [] : [[B.kanaele.gas, '#2ee59d', 'Gas B', [5, 4]], [B.kanaele.bremse, '#ff4d5e', 'Bremse B', [5, 4]]])], 160],
    ['Gang', [[A.kanaele.gang, fa, 'A'], ...(allein ? [] : [[B.kanaele.gang, fb, 'B']])], 110],
    ['Lenkwinkel (Grad)', [[A.kanaele.lenkung, fa, 'A'], ...(allein ? [] : [[B.kanaele.lenkung, fb, 'B']])], 130],
  ];
  const ziel = document.getElementById('diagramme');
  const sync = uPlot.sync('labor');
  for (const [name, reihen, h] of linien) {
    const box = document.createElement('div'); box.className = 'diagramm';
    box.innerHTML = `<div class="titel">${name}</div>`; ziel.appendChild(box);
    const u = new uPlot({
      width: box.clientWidth - 20, height: h,
      cursor: { sync: { key: sync.key }, points: { show: false } },
      scales: { x: { time: false } },
      axes: [{ stroke: '#8494a8', grid: { stroke: '#1b2533' }, ticks: { stroke: '#1b2533' }, values: (u, v) => v.map(x => x.toFixed(1) + ' km') },
             { stroke: '#8494a8', grid: { stroke: '#1b2533' }, ticks: { stroke: '#1b2533' }, size: 50 }],
      series: [{}, ...reihen.map(([_, farbe, label, strich]) => ({ label, stroke: farbe, width: 1.6, dash: strich, points: { show: false } }))],
      hooks: { setCursor: [u => { if (u.cursor.idx != null) karte.markieren(u.cursor.idx); }] },
    }, [km, ...reihen.map(r => r[0])], box);
    diagramme.push(u);
  }
  // Fenstergröße geändert: Diagramme mitziehen.
  window.onresize = () => diagramme.forEach(u => u.setSize({ width: u.root.parentElement.clientWidth - 20, height: u.height }));
}

// Zeichnet die Strecke aus GPS-Punkten, eingefärbt nach Gas und Bremse von Runde A.
function karteVorbereiten(canvas, A, B, verlust) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth; canvas.width = w * dpr; canvas.height = w * dpr;
  const ctx = canvas.getContext('2d'); ctx.scale(dpr, dpr);
  const lat = A.kanaele.lat, lon = A.kanaele.lon, n = lat.length;
  // Längengrade werden zu den Polen hin enger: mit cos(Breite) ausgleichen, sonst wirkt die Strecke gestaucht.
  const k = Math.cos(lat[0] * Math.PI / 180);
  const xs = lon.map(v => v * k), ys = lat;
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const m = Math.max(maxX - minX, maxY - minY), rand = 24;
  const proj = (x, y) => [rand + (x - minX) / m * (w - 2 * rand) + ((m - (maxX - minX)) / m) * (w - 2 * rand) / 2,
                          rand + (maxY - y) / m * (w - 2 * rand) + ((m - (maxY - minY)) / m) * (w - 2 * rand) / 2];
  const punkt = (R, i) => proj(R.kanaele.lon[i] * k, R.kanaele.lat[i]);
  // Farbe je nach Fahrereingabe.
  const farbe = i => A.kanaele.bremse[i] > 5 ? '#ff4d5e' : A.kanaele.gas[i] > 95 ? '#2ee59d' : A.kanaele.gas[i] > 10 ? '#c9a227' : '#4b5d73';
  // Grundbild einmal zeichnen und merken, Markierungen kommen später darüber.
  const grund = document.createElement('canvas'); grund.width = canvas.width; grund.height = canvas.height;
  const g = grund.getContext('2d'); g.scale(dpr, dpr); g.lineCap = 'round';
  if (verlust && verlust.d > 0) {
    g.strokeStyle = 'rgba(255,159,28,.45)'; g.lineWidth = 16; g.beginPath();
    for (let i = verlust.s; i < Math.min(verlust.e + 1, n); i++) { const [x, y] = punkt(A, i); i === verlust.s ? g.moveTo(x, y) : g.lineTo(x, y); }
    g.stroke();
  }
  g.lineWidth = 4;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = punkt(A, i), [x2, y2] = punkt(A, (i + 1) % n);
    g.strokeStyle = farbe(i); g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.stroke();
  }
  // Start/Ziel markieren.
  const [sx, sy] = punkt(A, 0);
  g.fillStyle = '#fff'; g.beginPath(); g.arc(sx, sy, 5, 0, 7); g.fill();
  g.font = '12px system-ui'; g.fillText('Start/Ziel', sx + 8, sy - 8);
  ctx.drawImage(grund, 0, 0, w, w);
  const ablesen = document.getElementById('ablesen');
  return {
    // Position beider Autos an derselben Stelle der Strecke zeigen und Werte ausgeben.
    markieren(i) {
      ctx.clearRect(0, 0, w, w); ctx.drawImage(grund, 0, 0, w, w);
      for (const [R, f] of [[B, '#ff9f1c'], [A, '#3db8ff']]) {
        const [x, y] = punkt(R, i);
        ctx.fillStyle = f; ctx.strokeStyle = '#000'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, 7, 0, 7); ctx.fill(); ctx.stroke();
      }
      const kmStand = (i / n * A.laenge_m / 1000).toFixed(2);
      ablesen.innerHTML = `km ${kmStand} · <span class="a">A ${A.kanaele.speed[i].toFixed(0)} km/h, Gang ${A.kanaele.gang[i]}</span>` +
        (A.id === B.id ? '' : ` · <span class="b">B ${B.kanaele.speed[i].toFixed(0)} km/h, Gang ${B.kanaele.gang[i]}</span> · Abstand <b>${diff(B.kanaele.t[i] - A.kanaele.t[i])} s</b>`);
    },
  };
}

// ---------- Bestenliste ----------
async function ansichtBestenliste() {
  const liste = await api('/api/bestenliste');
  const strecken = [...new Set(liste.map(z => z.strecke))];
  app.innerHTML = `<h1>Bestenliste</h1><p class="leise">Schnellste saubere Runde pro Strecke und Auto.</p>
    ${strecken.map(st => {
      const z = liste.filter(x => x.strecke === st);
      return `<h2>${esc(st)}</h2><div class="karte"><table>
        <tr><th>#</th><th>Auto</th><th>Zeit</th><th>Abstand</th><th>saubere Runden</th><th></th></tr>
        ${z.map((x, i) => `<tr><td>${i + 1}</td><td>${esc(x.auto)}</td><td class="mono">${zeit(x.zeit)}</td>
          <td class="mono">${i ? diff(x.zeit - z[0].zeit) : ''}</td><td>${x.runden}</td>
          <td><a href="#/vergleich/${z[0].runde_id}/${x.runde_id}">${i ? 'mit der Bestzeit vergleichen' : 'ansehen'}</a></td></tr>`).join('')}
      </table></div>`;
    }).join('') || '<p class="leise">Noch keine sauberen Runden.</p>'}`;
}

// ---------- So funktioniert's ----------
async function ansichtInfo() {
  const st = await api('/api/statistik');
  app.innerHTML = `
    <h1>So funktioniert das Telemetrie-Labor</h1>
    <p class="leise">Ein Rennauto im Simulator ist ein cyber-physisches System: 60 Mal pro Sekunde misst iRacing Tempo, Pedale, Lenkung, GPS-Position und Sprit. Das Labor macht aus diesen Rohdaten verständliche Bilder.</p>
    <div class="kacheln" style="margin:14px 0">
      <div class="kachel"><small>Sitzungen</small><b>${st.sitzungen}</b></div>
      <div class="kachel"><small>Runden in der DB</small><b>${st.runden}</b></div>
      <div class="kachel"><small>gefahrene Strecke</small><b>${Math.round(st.km)} km</b></div>
    </div>
    <h2>Der Weg der Daten</h2>
    <div class="fluss">
      <div class="schritt"><b>1. iRacing</b>schreibt beim Fahren eine .ibt-Datei: 60 Messungen pro Sekunde, rund 290 Kanäle.</div><div class="pfeil">→</div>
      <div class="schritt"><b>2. Upload</b>im Browser. Flask nimmt die Datei an, nur nach Login.</div><div class="pfeil">→</div>
      <div class="schritt"><b>3. ibt_lesen.py</b>liest nur 15 Kanäle per numpy-memmap. 475 MB in Sekunden.</div><div class="pfeil">→</div>
      <div class="schritt"><b>4. Runden</b>Ziellinie finden, jede Runde prüfen (Box, Ausritt, Lücke) und auf 1000 Punkte umrechnen.</div><div class="pfeil">→</div>
      <div class="schritt"><b>5. SQLite</b>speichert Runden und komprimierte Kurven. Die .ibt wird gelöscht.</div><div class="pfeil">→</div>
      <div class="schritt"><b>6. Browser</b>holt JSON über die REST-API, zeichnet Karte (Canvas) und Kurven (uPlot).</div>
    </div>
    <h2>Aufbau einer .ibt-Datei</h2>
    <div class="bytes mono">
      <div style="flex:1;background:#1d3b57">Kopf<br>112 B</div><div style="flex:1;background:#1d4a3a">Datei-Kopf<br>32 B</div>
      <div style="flex:3;background:#3b2f57">Variablenliste<br>290 × 144 B</div><div style="flex:3;background:#57412a">Session-Infos (YAML)<br>Strecke, Auto, alle Fahrer</div>
      <div style="flex:8;background:#2a3a4d">Messwerte: ein Datensatz alle 1/60 s, je ~1100 Byte</div>
    </div>
    <p class="leise">Die Variablenliste sagt für jeden Kanal, an welchem Byte im Datensatz er steht und welchen Typ er hat (float, double, int, bool). Damit baut numpy eine Maske über die ganze Datei und liest nur diese Spalten.</p>
    <h2>Wie genau ist das?</h2>
    <p>Die Rundenzeit rechnet das Labor selbst: Zeitpunkt, an dem der Streckenanteil von 100 % auf 0 % springt, zwischen zwei Messungen interpoliert. Gegenprobe mit dem Wert, den iRacing selbst meldet: höchstens 1 ms Abweichung.</p>
    <h2>Datenschutz und Sicherheit</h2>
    <p>Die Session-Infos jeder .ibt enthalten Namen und Kunden-IDs aller Fahrer der Session. Das Labor liest daraus nur Strecke, Länge, Art der Session und das eigene Auto. Die .ibt-Datei wird nach dem Auswerten gelöscht.</p>
    <p>Ansehen darf jeder im Netz, Hochladen und Löschen nur nach Login. Das Passwort steht nicht im Code: In <code>.env.password</code> liegt nur ein PBKDF2-Hash, die Datei hat Rechte 600 und ist per <code>.gitignore</code> und Commit-Wächter vom öffentlichen GitHub-Repo ausgeschlossen. Ohne gesetztes Passwort geht Hochladen nur direkt am Pi.</p>
    <h2>Technik</h2>
    <p class="leise">Raspberry Pi 400 · Python 3.9 · numpy · Flask · SQLite (WAL) · uPlot · Canvas · systemd-Dienst · erreichbar im WLAN und über Tailscale</p>`;
}

// ---------- Start ----------
statusLaden().then(zeigen).catch(zeigen);
