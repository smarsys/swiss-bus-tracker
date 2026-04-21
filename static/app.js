// Swiss Bus Tracker — Frontend

const STORAGE_KEY = "swiss-bus-tracker.favorites";
const REFRESH_INTERVAL = 30_000;
const MAX_RETRIES = 3;
const TZ = "Europe/Zurich";
const TIME_FMT = { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Zurich" };

// SVG icons
const ICON_CHECK = `<svg class="inline w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>`;
const ICON_CLOCK = `<svg class="inline w-4 h-4 text-stone-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" d="M12 6v6l4 2"/></svg>`;
const ICON_BUS = `<svg class="inline w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M4 16c0 .88.39 1.67 1 2.22V20c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h8v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1.78c.61-.55 1-1.34 1-2.22V6c0-3.5-3.58-4-8-4S4 2.5 4 6v10zm3.5 1c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm9 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1.5-6H6V6h12v5z"/></svg>`;
const ICON_TRAIN = `<svg class="inline w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2c-4 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h2.23l2-2H14l2 2h2v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-3.58-4-8-4zM7.5 17c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm3.5-6H6V6h5v5zm2 0V6h5v5h-5zm3.5 6c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>`;
const ICON_TRAM = `<svg class="inline w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M19 16.94V8.5c0-2.79-2.61-3.4-5.5-3.5l1.35-1.72c.31-.4.24-.98-.16-1.28-.4-.31-.98-.24-1.28.16L12 4.22l-1.41-2.06c-.31-.4-.88-.47-1.28-.16-.4.31-.47.88-.16 1.28L10.5 5C7.61 5.1 5 5.71 5 8.5v8.44c0 1.45 1.19 2.56 2.64 2.56h.86L7 21h2l1.5-1.5h3L15 21h2l-1.5-1.5h.86c1.45 0 2.64-1.11 2.64-2.56zM8.5 17c-.83 0-1.5-.67-1.5-1.5S7.67 14 8.5 14s1.5.67 1.5 1.5S9.33 17 8.5 17zm7 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm2.5-6H6V8h12v3z"/></svg>`;
const ICON_OTHER = `<svg class="inline w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" d="M12 8v4m0 4h.01"/></svg>`;

function getModeStyle(mode) {
    switch (mode) {
        case "bus": return { bg: "#FFCC00", text: "#000", icon: ICON_BUS };
        case "rail": return { bg: "#EB0000", text: "#fff", icon: ICON_TRAIN };
        case "tram": return { bg: "#0079C1", text: "#fff", icon: ICON_TRAM };
        case "metro": return { bg: "#0079C1", text: "#fff", icon: ICON_TRAM };
        default: return { bg: "#44403c", text: "#fff", icon: ICON_OTHER };
    }
}

const NOTIF_PERM_KEY = "swiss-bus-tracker.notif-enabled";
const ALERT_OPTIONS = [0, 2, 5, 10]; // 0 = disabled

// State
let favorites = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
let errorCounts = {};
let selectedStop = null;
let updateTimestamps = {};
let notifiedSet = new Set();
let notifEnabled = localStorage.getItem(NOTIF_PERM_KEY) === "true";
let lastDelays = {};

// DOM
const searchInput = document.getElementById("stop-search");
const dropdown = document.getElementById("search-dropdown");
const addFavForm = document.getElementById("add-fav-form");
const favStopName = document.getElementById("fav-stop-name");
const favStopRef = document.getElementById("fav-stop-ref");
const favLine = document.getElementById("fav-line");
const favDirection = document.getElementById("fav-direction");
const addFavBtn = document.getElementById("add-fav-btn");
const favAlert = document.getElementById("fav-alert");
const favoritesList = document.getElementById("favorites-list");
const emptyState = document.getElementById("empty-state");
const refreshAllBtn = document.getElementById("refresh-all-btn");
const notifBtn = document.getElementById("notif-btn");

// --- Search ---
let debounceTimer = null;
searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = searchInput.value.trim();
    if (q.length < 2) {
        dropdown.classList.add("hidden");
        return;
    }
    debounceTimer = setTimeout(() => fetchStops(q), 300);
});

async function fetchStops(q) {
    try {
        const resp = await fetch(`/api/stops/search?q=${encodeURIComponent(q)}&limit=8`);
        if (!resp.ok) return;
        const stops = await resp.json();
        renderDropdown(stops);
    } catch (e) {
        console.error("Search error:", e);
    }
}

function renderDropdown(stops) {
    if (stops.length === 0) {
        dropdown.classList.add("hidden");
        return;
    }
    dropdown.innerHTML = stops.map(s => `
        <div class="dropdown-item px-4 py-2.5 cursor-pointer text-sm border-b border-stone-100 last:border-0"
             data-ref="${s.stop_ref}" data-name="${escapeHtml(s.name)}">
            <span class="font-medium text-stone-800">${escapeHtml(s.name)}</span>
            ${s.locality ? `<span class="text-stone-400 ml-1">(${escapeHtml(s.locality)})</span>` : ""}
        </div>
    `).join("");
    dropdown.classList.remove("hidden");

    dropdown.querySelectorAll(".dropdown-item").forEach(item => {
        item.addEventListener("click", () => {
            selectedStop = { stopRef: item.dataset.ref, name: item.dataset.name };
            searchInput.value = item.dataset.name;
            dropdown.classList.add("hidden");
            showAddForm(selectedStop);
        });
    });
}

function showAddForm(stop) {
    favStopName.value = stop.name;
    favStopRef.value = stop.stopRef;
    favLine.value = "";
    favDirection.value = "";
    addFavForm.classList.remove("hidden");
}

document.addEventListener("click", (e) => {
    if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.add("hidden");
    }
});

// --- Favorites ---
addFavBtn.addEventListener("click", () => {
    if (!favStopRef.value) return;
    const fav = {
        id: crypto.randomUUID(),
        stopRef: favStopRef.value,
        stopName: favStopName.value,
        line: favLine.value.trim() || null,
        direction: favDirection.value.trim() || null,
        alertMin: parseInt(favAlert.value) || 0,
        createdAt: new Date().toISOString(),
    };
    favorites.push(fav);
    saveFavorites();
    addFavForm.classList.add("hidden");
    searchInput.value = "";
    renderFavorites();
    fetchDepartures(fav);
});

function saveFavorites() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
}

function removeFavorite(id) {
    favorites = favorites.filter(f => f.id !== id);
    delete updateTimestamps[id];
    saveFavorites();
    renderFavorites();
}

function renderFavorites() {
    emptyState.classList.toggle("hidden", favorites.length > 0);
    favoritesList.innerHTML = favorites.map(fav => `
        <div class="bg-white rounded-xl shadow-sm overflow-hidden" id="fav-${fav.id}">
            <div class="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
                <div class="flex items-center gap-2 flex-1 min-w-0">
                    <span class="font-semibold text-stone-800 truncate">${escapeHtml(fav.stopName)}</span>
                    ${fav.line ? `<span class="px-2 py-0.5 bg-amber-100 text-amber-800 rounded text-xs font-bold">${escapeHtml(fav.line)}</span>` : ""}
                    ${fav.direction ? `<span class="text-stone-400 text-xs truncate">\u2192 ${escapeHtml(fav.direction)}</span>` : ""}
                    ${fav.alertMin ? `<span class="px-1.5 py-0.5 bg-blue-50 text-blue-500 rounded text-xs">\uD83D\uDD14 ${fav.alertMin}min</span>` : ""}
                </div>
                <button onclick="removeFavorite('${fav.id}')" class="text-stone-300 hover:text-rose-500 ml-2 text-lg leading-none transition" title="Supprimer">&times;</button>
            </div>
            <div class="departures-list px-4 py-2" id="deps-${fav.id}">
                <div class="flex items-center justify-center py-4 text-stone-300">
                    <span class="spinner mr-2"></span> Chargement\u2026
                </div>
            </div>
            <div class="px-4 py-2 border-t border-stone-100 text-xs text-stone-400 flex items-center gap-2" id="footer-${fav.id}">
                <span class="update-time">\u2014</span>
            </div>
        </div>
    `).join("");
}

async function fetchDepartures(fav) {
    const container = document.getElementById(`deps-${fav.id}`);
    const footer = document.getElementById(`footer-${fav.id}`);
    if (!container) return;

    const footerTime = footer?.querySelector(".update-time");

    let url = `/api/departures?stopRef=${encodeURIComponent(fav.stopRef)}&num_results=10`;
    if (fav.line) url += `&line=${encodeURIComponent(fav.line)}`;
    if (fav.direction) url += `&direction=${encodeURIComponent(fav.direction)}`;

    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const deps = await resp.json();
        errorCounts[fav.id] = 0;
        renderDepartures(container, deps);
        updateTimestamps[fav.id] = Date.now();
        if (footerTime) footerTime.textContent = `Mis \u00e0 jour il y a 0s`;
        checkNotifications(fav, deps);
    } catch (e) {
        errorCounts[fav.id] = (errorCounts[fav.id] || 0) + 1;
        if (errorCounts[fav.id] >= MAX_RETRIES) {
            container.innerHTML = `<div class="py-3 text-center text-rose-400 text-sm">Erreur de chargement \u2014 v\u00e9rifiez la connexion</div>`;
        }
    }
}

function renderDepartures(container, deps) {
    if (deps.length === 0) {
        container.innerHTML = `<div class="py-3 text-center text-stone-400 text-sm">Aucun d\u00e9part pr\u00e9vu</div>`;
        return;
    }

    container.innerHTML = deps.map(d => {
        const scheduled = new Date(d.scheduled_time);
        const estimated = d.estimated_time ? new Date(d.estimated_time) : null;
        const timeStr = (estimated || scheduled).toLocaleTimeString("fr-CH", TIME_FMT);
        const scheduledStr = scheduled.toLocaleTimeString("fr-CH", TIME_FMT);
        const showCrossed = estimated && scheduledStr !== timeStr;
        const passed = d.already_passed;

        let badgeHtml;
        if (d.status === "cancelled") {
            badgeHtml = `<span class="px-2 py-0.5 rounded bg-slate-700 text-white text-xs font-medium">annul\u00e9</span>`;
        } else if (passed) {
            badgeHtml = `<span class="px-2 py-0.5 rounded bg-stone-200 text-stone-400 text-xs font-medium italic">pass\u00e9</span>`;
        } else if (d.status === "scheduled") {
            badgeHtml = `<span class="inline-flex items-center gap-1 text-stone-400" title="Horaire planifi\u00e9, pas de donn\u00e9es temps r\u00e9el pour cette ligne">${ICON_CLOCK}</span>`;
        } else if (d.delay_minutes <= 1) {
            badgeHtml = `<span class="px-2 py-0.5 rounded bg-emerald-500 text-white text-xs font-medium inline-flex items-center gap-1">${ICON_CHECK} \u00e0 l'heure</span>`;
        } else if (d.delay_minutes <= 5) {
            badgeHtml = `<span class="px-2 py-0.5 rounded bg-amber-500 text-white text-xs font-medium">+${d.delay_minutes} min</span>`;
        } else {
            badgeHtml = `<span class="px-2 py-0.5 rounded bg-rose-600 text-white text-xs font-bold">+${d.delay_minutes} min</span>`;
        }

        const ms = getModeStyle(d.mode);
        const rowClass = passed ? "departure-passed" : d.status === "cancelled" ? "departure-cancelled" : "";

        return `
        <div class="flex items-center gap-3 py-2.5 border-b border-stone-50 last:border-0 ${rowClass}">
            <div class="line-badge flex items-center gap-1.5 px-2 py-1.5 rounded-lg font-bold font-mono text-sm" style="background:${ms.bg};color:${ms.text};min-width:48px;min-height:32px">
                <span class="opacity-70">${ms.icon}</span>
                ${escapeHtml(d.line)}
            </div>
            <div class="flex-1 min-w-0">
                <div class="text-sm text-stone-700 truncate dep-destination">${escapeHtml(d.destination)}</div>
                <div class="flex items-baseline gap-2 dep-time">
                    ${showCrossed ? `<span class="text-xs text-stone-400 scheduled-crossed">${scheduledStr}</span>` : ""}
                    <span class="text-lg font-bold text-stone-800">${timeStr}</span>
                </div>
            </div>
            ${badgeHtml}
        </div>`;
    }).join("");

    container.classList.remove("deps-fade-in");
    void container.offsetWidth;
    container.classList.add("deps-fade-in");
}

// --- Refresh ---
refreshAllBtn.addEventListener("click", refreshAll);

function refreshAll() {
    favorites.forEach(fav => fetchDepartures(fav));
}

// Auto-refresh
setInterval(refreshAll, REFRESH_INTERVAL);

// Update "il y a Xs" footers every second
setInterval(() => {
    for (const fav of favorites) {
        const ts = updateTimestamps[fav.id];
        if (!ts) continue;
        const footer = document.getElementById(`footer-${fav.id}`);
        const el = footer?.querySelector(".update-time");
        if (el) {
            const secs = Math.round((Date.now() - ts) / 1000);
            el.textContent = `Mis \u00e0 jour il y a ${secs}s`;
        }
    }
}, 1000);

// --- Notifications ---
function initNotifButton() {
    if (!("Notification" in window)) return;
    notifBtn.classList.remove("hidden");
    updateNotifButton();
    notifBtn.addEventListener("click", async () => {
        if (Notification.permission === "default") {
            const perm = await Notification.requestPermission();
            notifEnabled = perm === "granted";
        } else {
            notifEnabled = !notifEnabled;
        }
        localStorage.setItem(NOTIF_PERM_KEY, notifEnabled);
        updateNotifButton();
    });
}

function updateNotifButton() {
    if (Notification.permission === "granted" && notifEnabled) {
        notifBtn.textContent = "\uD83D\uDD14";
        notifBtn.classList.remove("bg-stone-100", "text-stone-500");
        notifBtn.classList.add("bg-blue-100", "text-blue-600");
        notifBtn.title = "Notifications activ\u00e9es";
    } else {
        notifBtn.textContent = "\uD83D\uDD15";
        notifBtn.classList.remove("bg-blue-100", "text-blue-600");
        notifBtn.classList.add("bg-stone-100", "text-stone-500");
        notifBtn.title = "Activer les notifications";
    }
}

function checkNotifications(fav, deps) {
    if (!notifEnabled || Notification.permission !== "granted") return;
    const now = Date.now();

    // Find next non-passed departure
    const next = deps.find(d => !d.already_passed && d.status !== "cancelled");
    if (!next) return;

    const depTime = new Date(next.estimated_time || next.scheduled_time).getTime();
    const minsUntil = (depTime - now) / 60000;
    const notifKey = `${fav.stopRef}:${next.scheduled_time}`;

    // Alert X min before
    if (fav.alertMin && fav.alertMin > 0) {
        const lo = fav.alertMin - 0.5;
        const hi = fav.alertMin + 0.5;
        if (minsUntil >= lo && minsUntil <= hi && !notifiedSet.has(notifKey)) {
            notifiedSet.add(notifKey);
            const heureLocale = new Date(depTime).toLocaleTimeString("fr-CH", TIME_FMT);
            new Notification(`\uD83D\uDE8C Ligne ${next.line} \u2192 ${next.destination}`, {
                body: `D\u00e9part de ${fav.stopName} dans ${Math.round(minsUntil)} min (${heureLocale})`,
                tag: notifKey,
                icon: "/static/icon-192.png",
                badge: "/static/icon-192.png",
                requireInteraction: false,
            });
        }
    }

    // Big delay alert (>10 min increase between refreshes)
    const delayKey = `${fav.id}:${next.scheduled_time}`;
    const prevDelay = lastDelays[delayKey];
    if (prevDelay !== undefined && next.delay_minutes - prevDelay >= 10 && !notifiedSet.has(`delay:${delayKey}`)) {
        notifiedSet.add(`delay:${delayKey}`);
        new Notification(`\u26A0\uFE0F Retard important : +${next.delay_minutes} min`, {
            body: `Ligne ${next.line} \u2192 ${next.destination} depuis ${fav.stopName}`,
            tag: `delay:${delayKey}`,
            icon: "/static/icon-192.png",
            requireInteraction: false,
        });
    }
    lastDelays[delayKey] = next.delay_minutes;
}

initNotifButton();

// --- Init ---
function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
}

renderFavorites();
refreshAll();

// PWA Service Worker
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}
