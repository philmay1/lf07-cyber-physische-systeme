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
// Farbe aus dem Design holen (style.css, Variable --name). So passen Karte und Diagramme zum gewählten Thema.
const farbe = name => getComputedStyle(document.documentElement).getPropertyValue('--' + name).trim();
// Seitenkopf: kleine Rubrik in Akzentfarbe, großer Titel, Unterzeile.
const seitenkopf = (rubrik, titel, unter) =>
  `<p class="rubrik">${rubrik}</p><h1>${titel}</h1>${unter ? `<p class="leise">${unter}</p>` : ''}`;
// Zwischenüberschrift mit Kapitelnummer: abschnitt('02', 'Rundenzeiten').
const abschnitt = (nr, titel, zusatz) => `<h2><span class="nr">${nr}</span>${titel}${zusatz ? ` <span class="leise">${zusatz}</span>` : ''}</h2>`;
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

// ---------- Statusleiste: der Pi meldet sich ----------
// Holt alle 10 Sekunden CPU-Temperatur, Last, Speicher und Laufzeit vom Pi (/api/system).
// Das ist der Blick des Admins: Läuft der Server, wie warm ist er, wie voll ist die Platte?
async function statusleiste() {
  const leiste = document.getElementById('status');
  try {
    const s = await api('/api/system');
    const tage = Math.floor(s.laufzeit_s / 86400), std = Math.floor(s.laufzeit_s % 86400 / 3600);
    const teil = (name, wert) => wert == null ? '' : `<span>${name} <b>${wert}</b></span>`;
    leiste.innerHTML = `<span class="an"><b>Pi online</b></span>` +
      teil('CPU', s.cpu_temp == null ? null : s.cpu_temp.toFixed(1) + ' °C') +
      teil('Last', s.last == null ? null : s.last.toFixed(2)) +
      teil('RAM', s.ram_prozent == null ? null : s.ram_prozent + ' %') +
      teil('Laufzeit', s.laufzeit_s == null ? null : `${tage} d ${std} h`) +
      teil('Datenbank', (s.db_mb ?? 0).toFixed(1) + ' MB') +
      teil('SD frei', s.frei_gb == null ? null : s.frei_gb.toFixed(1) + ' GB') +
      teil('Dienst', 'telemetrie-labor :' + s.port);
  } catch (e) {
    leiste.innerHTML = '<span><b style="color:var(--schlecht)">Pi nicht erreichbar</b></span>';
  }
}

// ---------- Seitenwechsel ----------
async function zeigen() {
  diagramme.forEach(d => d.destroy()); diagramme = [];
  const teile = location.hash.replace(/^#\/?/, '').split('/');
  // Menüpunkt der aktuellen Seite hervorheben (Sitzung und Vergleich zählen zu "Sitzungen").
  const seite = ['bestenliste', 'info'].includes(teile[0]) ? teile[0] : '';
  document.querySelectorAll('.menue a').forEach(a => a.classList.toggle('aktiv', a.dataset.seite === seite));
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
  // Schnellste Runde je Strecke finden: die steht in der Liste lila.
  const rekord = {};
  liste.forEach(s => { if (s.beste != null && !(rekord[s.strecke] <= s.beste)) rekord[s.strecke] = s.beste; });
  app.innerHTML = `
    ${seitenkopf('Daten-Eingang', 'Sitzungen', 'iRacing-Datei hochladen. Der Pi zerlegt sie in Runden, prüft jede Runde und speichert die Messkurven in der Datenbank.')}
    ${abschnitt('01', 'Upload')}
    <div class="upload" id="upload">
      ${STATUS.darf_aendern
        ? `<p><b>.ibt-Datei hierher ziehen</b> oder <button id="waehlen" class="klein">Datei wählen</button></p>
           <p class="leise mono">Dokumente\\iRacing\\telemetry · bis ${STATUS.max_mb} MB</p>
           <input id="datei" type="file" accept=".ibt" hidden>
           <div class="balken" hidden><div></div></div><p id="uploadText" class="leise"></p>`
        : `<p class="leise">Zum Hochladen ${STATUS.login_noetig ? 'oben rechts anmelden' : 'die Seite direkt am Pi öffnen'}.</p>`}
    </div>
    ${abschnitt('02', 'Gespeicherte Sitzungen', `${liste.length} Stück · lila = Streckenrekord im Labor`)}
    ${liste.length ? `<div class="karte"><table>
      <tr><th>Gefahren</th><th>Strecke</th><th>Auto</th><th>Art</th><th>Runden sauber / alle</th><th>Beste Runde</th></tr>
      ${liste.map(s => `<tr class="klickbar" data-id="${s.id}">
        <td class="mono">${esc(s.datum)}</td><td>${esc(s.strecke)}${s.layout ? ` <span class="leise">${esc(s.layout)}</span>` : ''}</td>
        <td>${esc(s.auto)}</td><td><span class="marke ${/race|rennen/i.test(s.typ) ? 'rennen' : ''}">${esc(s.typ)}</span></td>
        <td class="mono">${s.gueltige || 0} / ${s.runden}</td>
        <td class="mono ${s.beste != null && s.beste === rekord[s.strecke] ? 'lila' : ''}">${zeit(s.beste)}</td></tr>`).join('')}
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
    ${seitenkopf(`Sitzung ${s.id} · ${esc(s.typ)}`, `${esc(s.strecke)} ${s.layout ? `<span class="leise">${esc(s.layout)}</span>` : ''}`,
      `${esc(s.auto)} · ${esc(s.datum)} · ${(s.laenge_m / 1000).toFixed(3)} km · Datei ${esc(s.datei)}`)}
    <div class="kacheln" style="margin-top:18px">
      <div class="kachel"><small>Runden</small><b>${s.runden.length}</b></div>
      <div class="kachel"><small>davon sauber</small><b>${gueltig.length}</b></div>
      <div class="kachel"><small>Beste Runde</small><b class="lila">${zeit(beste?.zeit)}</b></div>
      <div class="kachel"><small>Ø sauber</small><b>${zeit(gueltig.length ? gueltig.reduce((a, r) => a + r.zeit, 0) / gueltig.length : null)}</b></div>
      <div class="kachel"><small>Höchsttempo</small><b>${Math.max(...s.runden.map(r => r.vmax)).toFixed(0)} km/h</b></div>
    </div>
    ${abschnitt('01', 'Rundenzeiten', 'klicken = für den Vergleich wählen')}
    <div class="karte"><div class="saeulen">${s.runden.map(r => `<div class="saeule ${r.gueltig ? '' : 'ungueltig'} ${beste && r.id === beste.id ? 'beste' : ''}"
      data-id="${r.id}" style="height:${hoehe(r.zeit)}%" title="Runde ${r.nummer}: ${zeit(r.zeit)}${r.grund ? ' (' + esc(r.grund) + ')' : ''}"></div>`).join('')}</div>
      <p class="hinweis">Jede Säule ist eine Runde. Je höher, desto langsamer. Lila = schnellste Runde, grau = ungültig (Box, Ausritt, Lücke).</p></div>
    <div class="zeile" style="margin-top:12px">
      <button id="vergleichen">Gewählte Runden vergleichen</button><span id="wahlText" class="leise mono"></span>
      ${STATUS.darf_aendern ? '<button id="loeschen" class="gefahr klein" style="margin-left:auto">Sitzung löschen</button>' : ''}
    </div>
    ${abschnitt('02', 'Alle Runden')}
    <div class="karte"><table>
      <tr><th></th><th>Runde</th><th>Zeit</th><th>zur Besten</th><th>Höchsttempo</th><th>Sprit</th><th>Status</th></tr>
      ${s.runden.map(r => `<tr class="klickbar ${r.gueltig ? '' : 'ungueltig'} ${beste && r.id === beste.id ? 'beste' : ''}" data-id="${r.id}">
        <td><input type="checkbox" data-id="${r.id}"></td><td class="mono">${r.nummer}</td><td class="mono">${zeit(r.zeit)}</td>
        <td class="mono">${beste ? diff(r.zeit - beste.zeit) : ''}</td><td class="mono">${r.vmax.toFixed(0)} km/h</td>
        <td class="mono">${r.sprit > 0 ? r.sprit.toFixed(2) + ' l' : '–'}</td><td>${r.gueltig ? 'sauber' : `<span class="marke">${esc(r.grund)}</span>`}</td></tr>`).join('')}
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
    ${seitenkopf('Rundenvergleich', esc(A.strecke))}
    <div class="legende" style="margin:6px 0 4px">
      <span><i style="background:var(--a)"></i><b class="a">A</b> ${titel(A)}</span>
      ${allein ? '' : `<span><i style="background:var(--b)"></i><b class="b">B</b> ${titel(B)}</span>`}
    </div>
    <div class="zeile" style="margin:10px 0 16px"><span class="leise">B wählen:</span>
      <select id="wahlB">${andere.map(r => `<option value="${r.id}" ${r.id === idB ? 'selected' : ''}>${zeit(r.zeit)} · ${esc(r.auto)} · Runde ${r.nummer} · ${esc(r.datum)}</option>`).join('')}</select>
      <button id="tauschen" class="zweit klein">A ⇄ B</button></div>
    ${allein ? '' : `<div class="kacheln">
      <div class="kachel"><small>B gegenüber A</small><b class="${B.zeit > A.zeit ? 'plus' : 'minus'}">${diff(B.zeit - A.zeit)} s</b></div>
      <div class="kachel"><small>B verliert am meisten</small><b>${schlimmster.d > 0 ? `${diff(schlimmster.d)} s` : '–'}</b><br><span class="leise mono">${schlimmster.d > 0 ? `km ${schlimmster.von.toFixed(1)} bis ${schlimmster.bis.toFixed(1)}` : ''}</span></div>
      <div class="kachel"><small>B gewinnt am meisten</small><b>${bester.d < 0 ? `${diff(bester.d)} s` : '–'}</b><br><span class="leise mono">${bester.d < 0 ? `km ${bester.von.toFixed(1)} bis ${bester.bis.toFixed(1)}` : ''}</span></div>
      <div class="kachel"><small>Höchsttempo A / B</small><b>${A.vmax.toFixed(0)} / ${B.vmax.toFixed(0)}</b></div>
    </div>`}
    <div class="vergleich" style="margin-top:16px">
      <div class="links">
        <div class="karte"><h3>Streckenkarte aus GPS</h3><canvas id="karte"></canvas>
          <div class="legende" style="margin-top:8px"><span><i style="background:var(--bremse)"></i>Bremse</span><span><i style="background:var(--gas)"></i>Vollgas</span><span><i style="background:var(--teilgas)"></i>Teilgas</span><span><i style="background:var(--rollen)"></i>Rollen</span>${allein ? '' : '<span><i style="background:var(--verlust)"></i>größter Verlust</span>'}</div>
          <p class="ablesen" id="ablesen">Maus über die Diagramme bewegen: die Punkte zeigen, wo A und B gerade sind.</p>
        </div>
        ${allein ? '' : `<div class="karte" style="margin-top:12px"><h3>Abschnitte: B gegenüber A</h3><table class="abschnitte">
          ${abschnitte.map(a => `<tr><td class="mono">km ${a.von.toFixed(1)}–${a.bis.toFixed(1)}</td><td class="mono ${a.d > 0 ? 'plus' : 'minus'}">${diff(a.d)}</td>
            <td class="balkenzelle"><div class="dbalken" style="width:${Math.abs(a.d) / maxD * 100}%;background:${a.d > 0 ? 'var(--schlecht)' : 'var(--gut)'}"></div></td>
            <td class="leise mono">${a.minA.toFixed(0)} / ${a.minB.toFixed(0)}</td></tr>`).join('')}
          </table><p class="hinweis">Rot = B verliert dort Zeit, grün = B ist schneller. Rechts: langsamstes Tempo im Abschnitt, A / B in km/h.</p></div>`}
      </div>
      <div id="diagramme"></div>
    </div>`;
  document.getElementById('wahlB').addEventListener('change', e => location.hash = `#/vergleich/${idA}/${e.target.value}`);
  document.getElementById('tauschen').addEventListener('click', () => location.hash = `#/vergleich/${idB}/${idA}`);

  // Streckenkarte zeichnen.
  const karte = karteVorbereiten(document.getElementById('karte'), A, B, allein ? null : schlimmster);
  // Diagramme: Titel, Linien [Daten, Farbe, Name, Strichmuster], Höhe in Pixeln, Lesehilfe.
  const fa = farbe('a'), fb = farbe('b'), fgas = farbe('gas'), fbremse = farbe('bremse');
  const linien = [
    ...(allein ? [] : [['Zeitabstand B − A (s)', [[delta, fb, 'Δ']], 150,
      'Steigt die Linie, verliert B dort Zeit. Fällt sie, holt B auf. Der Wert am Ende ist der Abstand im Ziel.']]),
    ['Tempo (km/h)', [[A.kanaele.speed, fa, 'A'], ...(allein ? [] : [[B.kanaele.speed, fb, 'B']])], 200,
      'Die Täler sind die Kurven. Je tiefer das Tal, desto langsamer die Kurve.'],
    ['Gas und Bremse (%)', [[A.kanaele.gas, fgas, 'Gas A'], [A.kanaele.bremse, fbremse, 'Bremse A'],
      ...(allein ? [] : [[B.kanaele.gas, fgas, 'Gas B', [5, 4]], [B.kanaele.bremse, fbremse, 'Bremse B', [5, 4]]])], 160,
      'Durchgezogen = A, gestrichelt = B. Wer später bremst und früher Gas gibt, ist schneller.'],
    ['Gang', [[A.kanaele.gang, fa, 'A'], ...(allein ? [] : [[B.kanaele.gang, fb, 'B']])], 110, ''],
    ['Lenkwinkel (Grad)', [[A.kanaele.lenkung, fa, 'A'], ...(allein ? [] : [[B.kanaele.lenkung, fb, 'B']])], 130,
      'Ausschlag nach oben = links, nach unten = rechts. Ruhige Linie = ruhiges Auto.'],
  ];
  const ziel = document.getElementById('diagramme');
  const sync = uPlot.sync('labor');
  // Achsen in den Farben und der Zahlenschrift des Themas.
  const achse = { stroke: farbe('achse'), grid: { stroke: farbe('gitter') }, ticks: { stroke: farbe('gitter') }, font: '12px "JetBrains Mono", monospace' };
  for (const [name, reihen, h, lesehilfe] of linien) {
    const box = document.createElement('div'); box.className = 'diagramm';
    box.innerHTML = `<div class="titel">${name}</div>`; ziel.appendChild(box);
    const u = new uPlot({
      width: box.clientWidth - 24, height: h,
      cursor: { sync: { key: sync.key }, points: { show: false } },
      scales: { x: { time: false } },
      axes: [{ ...achse, values: (u, v) => v.map(x => x.toFixed(1) + ' km') }, { ...achse, size: 54 }],
      series: [{}, ...reihen.map(([_, f, label, strich]) => ({ label, stroke: f, width: 1.6, dash: strich, points: { show: false } }))],
      hooks: { setCursor: [u => { if (u.cursor.idx != null) karte.markieren(u.cursor.idx); }] },
    }, [km, ...reihen.map(r => r[0])], box);
    if (lesehilfe) box.insertAdjacentHTML('beforeend', `<p class="hinweis">${lesehilfe}</p>`);
    diagramme.push(u);
  }
  // Fenstergröße geändert: Diagramme mitziehen.
  window.onresize = () => diagramme.forEach(u => u.setSize({ width: u.root.parentElement.clientWidth - 24, height: u.height }));
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
  // Farben aus dem Thema holen (einmal, nicht bei jedem Punkt).
  const F = { bremse: farbe('bremse'), gas: farbe('gas'), teilgas: farbe('teilgas'), rollen: farbe('rollen'),
              verlust: farbe('verlust'), text: farbe('text'), bg: farbe('bg'), a: farbe('a'), b: farbe('b') };
  // Farbe je nach Fahrereingabe: Bremse vor Vollgas vor Teilgas, sonst Rollen.
  const farbeBei = i => A.kanaele.bremse[i] > 5 ? F.bremse : A.kanaele.gas[i] > 95 ? F.gas : A.kanaele.gas[i] > 10 ? F.teilgas : F.rollen;
  // Grundbild einmal zeichnen und merken, Markierungen kommen später darüber.
  const grund = document.createElement('canvas'); grund.width = canvas.width; grund.height = canvas.height;
  const g = grund.getContext('2d'); g.scale(dpr, dpr); g.lineCap = 'round';
  if (verlust && verlust.d > 0) {
    g.strokeStyle = F.verlust; g.lineWidth = 18; g.beginPath();
    for (let i = verlust.s; i < Math.min(verlust.e + 1, n); i++) { const [x, y] = punkt(A, i); i === verlust.s ? g.moveTo(x, y) : g.lineTo(x, y); }
    g.stroke();
  }
  g.lineWidth = 4;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = punkt(A, i), [x2, y2] = punkt(A, (i + 1) % n);
    g.strokeStyle = farbeBei(i); g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.stroke();
  }
  // Start/Ziel markieren.
  const [sx, sy] = punkt(A, 0);
  g.fillStyle = F.text; g.fillRect(sx - 5, sy - 5, 10, 10);
  g.font = '600 12px "JetBrains Mono", monospace'; g.fillText('START/ZIEL', sx + 10, sy - 8);
  ctx.drawImage(grund, 0, 0, w, w);
  const ablesen = document.getElementById('ablesen');
  return {
    // Position beider Autos an derselben Stelle der Strecke zeigen und Werte ausgeben.
    markieren(i) {
      ctx.clearRect(0, 0, w, w); ctx.drawImage(grund, 0, 0, w, w);
      for (const [R, f] of [[B, F.b], [A, F.a]]) {
        const [x, y] = punkt(R, i);
        ctx.fillStyle = f; ctx.strokeStyle = F.bg; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, 7, 0, 7); ctx.fill(); ctx.stroke();
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
  app.innerHTML = `${seitenkopf('Zeitenliste', 'Bestenliste', 'Schnellste saubere Runde pro Strecke und Auto. Ein Klick vergleicht sie mit der Bestzeit.')}
    ${strecken.map((st, nr) => {
      const z = liste.filter(x => x.strecke === st);
      return `${abschnitt(String(nr + 1).padStart(2, '0'), esc(st))}<div class="karte"><table>
        <tr><th>Pos</th><th>Auto</th><th>Zeit</th><th>Abstand</th><th>saubere Runden</th><th></th></tr>
        ${z.map((x, i) => `<tr${i ? '' : ' class="beste"'}><td class="pos">P${i + 1}</td><td>${esc(x.auto)}</td><td class="mono">${zeit(x.zeit)}</td>
          <td class="mono">${i ? diff(x.zeit - z[0].zeit) : ''}</td><td class="mono">${x.runden}</td>
          <td><a href="#/vergleich/${z[0].runde_id}/${x.runde_id}">${i ? 'mit Bestzeit vergleichen →' : 'ansehen →'}</a></td></tr>`).join('')}
      </table></div>`;
    }).join('') || '<p class="leise">Noch keine sauberen Runden.</p>'}`;
}

// ---------- So funktioniert's ----------
async function ansichtInfo() {
  const st = await api('/api/statistik');
  // Stationen des Datenwegs. Die Marke unten zeigt, welches LF07-Thema dahintersteckt.
  const schritte = [
    ['iRacing', 'schreibt beim Fahren eine .ibt-Datei: 60 Messungen pro Sekunde, rund 290 Kanäle.', 'Sensorik'],
    ['Upload', 'im Browser über das Netz. Flask nimmt die Datei an, nur nach Login.', 'Netzwerk'],
    ['ibt_lesen.py', 'liest nur 15 Kanäle per numpy-memmap. 475 MB in Sekunden.', 'Verarbeitung'],
    ['Runden', 'Ziellinie finden, jede Runde prüfen (Box, Ausritt, Lücke), auf 1000 Punkte umrechnen.', 'Auswertung'],
    ['SQLite', 'speichert Runden und komprimierte Kurven. Die .ibt wird gelöscht.', 'Datenbank'],
    ['Browser', 'holt JSON über die REST-API, zeichnet Karte (Canvas) und Kurven (uPlot).', 'Visualisierung'],
  ];
  app.innerHTML = `
    ${seitenkopf('Technik', 'So funktioniert das Labor', 'Ein Rennauto im Simulator ist ein cyber-physisches System: 60 Mal pro Sekunde misst iRacing Tempo, Pedale, Lenkung, GPS-Position und Sprit. Das Labor macht aus diesen Rohdaten Bilder, die man sofort versteht.')}
    <div class="kacheln" style="margin:18px 0">
      <div class="kachel"><small>Sitzungen</small><b>${st.sitzungen}</b></div>
      <div class="kachel"><small>Runden in der DB</small><b>${st.runden}</b></div>
      <div class="kachel"><small>gefahrene Strecke</small><b>${Math.round(st.km)} km</b></div>
    </div>
    ${abschnitt('01', 'Der Weg der Daten')}
    <div class="fluss">${schritte.map(([t, text, lf], i) => `<div class="schritt"><span class="nr">STATION ${i + 1}</span><b>${t}</b>${text}<br><span class="marke lf">${lf}</span></div>`).join('')}</div>
    ${abschnitt('02', 'Aufbau einer .ibt-Datei')}
    <div class="bytes mono">
      <div style="flex:1;background:var(--byte1)">Kopf<br>112 B</div><div style="flex:1;background:var(--byte2)">Datei-Kopf<br>32 B</div>
      <div style="flex:3;background:var(--byte3)">Variablenliste<br>290 × 144 B</div><div style="flex:3;background:var(--byte4)">Session-Infos (YAML)<br>Strecke, Auto, alle Fahrer</div>
      <div style="flex:8;background:var(--byte5)">Messwerte: ein Datensatz alle 1/60 s, je ~1100 Byte</div>
    </div>
    <p class="leise">Die Variablenliste sagt für jeden Kanal, an welchem Byte im Datensatz er steht und welchen Typ er hat (float, double, int, bool). Damit baut numpy eine Maske über die ganze Datei und liest nur diese Spalten.</p>
    ${abschnitt('03', 'Wie genau ist das?')}
    <p>Die Rundenzeit rechnet das Labor selbst: Zeitpunkt, an dem der Streckenanteil von 100 % auf 0 % springt, zwischen zwei Messungen interpoliert. Gegenprobe mit dem Wert, den iRacing selbst meldet: höchstens 1 ms Abweichung.</p>
    ${abschnitt('04', 'Datenschutz und Sicherheit')}
    <p>Die Session-Infos jeder .ibt enthalten Namen und Kunden-IDs aller Fahrer der Session. Das Labor liest daraus nur Strecke, Länge, Art der Session und das eigene Auto. Die .ibt-Datei wird nach dem Auswerten gelöscht.</p>
    <p>Ansehen darf jeder im Netz, Hochladen und Löschen nur nach Login. Das Passwort steht nicht im Code: In <code>.env.password</code> liegt nur ein PBKDF2-Hash, die Datei hat Rechte 600 und ist per <code>.gitignore</code> und Commit-Wächter vom öffentlichen GitHub-Repo ausgeschlossen. Ohne gesetztes Passwort geht Hochladen nur direkt am Pi.</p>
    ${abschnitt('05', 'Betrieb')}
    <p>Das Labor läuft als systemd-Dienst und startet nach einem Neustart des Pi von selbst. Die Statusleiste oben zeigt live, wie es dem Pi geht: CPU-Temperatur, Last, Arbeitsspeicher, Laufzeit, Größe der Datenbank und freier Platz auf der SD-Karte.</p>
    <p class="leise mono">Raspberry Pi 400 · Python 3.9 · numpy · Flask · SQLite (WAL) · uPlot · Canvas · systemd · WLAN und Tailscale</p>`;
}

// ---------- Design-Vorschau: Thema umschalten, ohne die aktuelle Seite zu verlieren ----------
document.querySelectorAll('#themawahl a').forEach(a => {
  a.classList.toggle('aktiv', a.dataset.thema === document.documentElement.dataset.thema);
  a.addEventListener('click', e => {
    e.preventDefault();
    try { localStorage.setItem('thema', a.dataset.thema); } catch (err) {}
    location.href = `?thema=${a.dataset.thema}${location.hash}`;
  });
});

// ---------- Start ----------
statusLaden().then(zeigen).catch(zeigen);
statusleiste();
setInterval(statusleiste, 10000);
