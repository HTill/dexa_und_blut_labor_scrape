const COLORS = {
  dexa:     '#1565c0',
  blutlabor: '#c62828',
  beide:    '#2e7d32',
};

const BADGE_LABELS = { dexa: 'DEXA', blutlabor: 'Blutlabor', beide: 'Beides' };
const BADGE_CLASSES = { dexa: 'badge-dexa', blutlabor: 'badge-blut', beide: 'badge-beide' };

let providers = [];
let markers = [];
let activeFilter = 'alle';

const map = L.map('map').setView([52.3759, 9.7320], 7);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 18,
}).addTo(map);

function createIcon(color) {
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
      width:14px;height:14px;border-radius:50%;
      background:${color};
      border:3px solid white;
      box-shadow:0 1px 4px rgba(0,0,0,0.3);
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

function renderMarkers() {
  markers.forEach(m => map.removeLayer(m));
  markers = [];

  const filtered = (activeFilter === 'alle'
      ? providers
      : providers.filter(p => p.category === activeFilter || p.category === 'beide'))
    .filter(p => p.coordinates.lat !== 0 || p.coordinates.lng !== 0);

  filtered.forEach(p => {
    const icon = createIcon(COLORS[p.category] || '#999');
    const marker = L.marker([p.coordinates.lat, p.coordinates.lng], { icon }).addTo(map);

    marker.on('click', () => showDetail(p));
    markers.push(marker);
  });

  updateStats(filtered);
}

function updateStats(visible) {
  const dexas = visible.filter(p => p.category === 'dexa' || p.category === 'beide').length;
  const bluts = visible.filter(p => p.category === 'blutlabor' || p.category === 'beide').length;
  document.getElementById('stats').textContent =
    `${visible.length} Anbieter · ${dexas} DEXA · ${bluts} Blutlabor`;
}

function showDetail(p) {
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');

  content.innerHTML = `
    <h2>${p.name}</h2>
    <span class="badge ${BADGE_CLASSES[p.category]}">${BADGE_LABELS[p.category]}</span>

    <div class="field"><strong>Adresse:</strong> ${p.address.street}<br>
      ${p.address.postal_code} ${p.address.city} · ${p.address.country}</div>

    ${p.services?.length ? `<div class="field"><strong>Leistungen:</strong> ${p.services.join(', ')}</div>` : ''}
    ${p.contact?.phone ? `<div class="field"><strong>Tel:</strong> <a href="tel:${p.contact.phone}">${p.contact.phone}</a></div>` : ''}
    ${p.contact?.website ? `<div class="field"><strong>Web:</strong> <a href="${p.contact.website}" target="_blank">${p.contact.website}</a></div>` : ''}
    ${p.self_payer !== undefined ? `<div class="field"><strong>Selbstzahler:</strong> ${p.self_payer ? 'Ja' : 'Nein'}</div>` : ''}
    ${p.prices ? `<div class="field"><strong>Preise:</strong> ${Object.entries(p.prices).map(([k,v]) => `${k}: ${v}`).join('<br>')}</div>` : ''}
    ${p.notes ? `<div class="field" style="margin-top:6px;color:#666;font-style:italic">${p.notes}</div>` : ''}
    ${!p.verified ? '<div class="field" style="margin-top:8px;color:#e65100;font-weight:600">⚠ Noch nicht verifiziert</div>' : ''}
  `;

  panel.classList.add('visible');
}

document.getElementById('detail-close').addEventListener('click', () => {
  document.getElementById('detail-panel').classList.remove('visible');
});

document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    renderMarkers();
  });
});

// Daten laden
fetch('data/providers.json')
  .then(res => res.json())
  .then(data => {
    providers = data;
    renderMarkers();
  })
  .catch(err => {
    console.error('Fehler beim Laden der Daten:', err);
    document.getElementById('stats').textContent = 'Fehler beim Laden der Daten. Bitte prüfe den Pfad zu providers.json.';
  });
