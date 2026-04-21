// Swiss Bus Tracker — Frontend

const STORAGE_KEY = "swiss-bus-tracker.favorites";
const REFRESH_INTERVAL = 30_000;
const MAX_RETRIES = 3;

// State
let favorites = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
let errorCounts = {};
let selectedStop = null;

// DOM
const searchInput = document.getElementById("stop-search");
const dropdown = document.getElementById("search-dropdown");
const addFavForm = document.getElementById("add-fav-form");
const favStopName = document.getElementById("fav-stop-name");
const favStopRef = document.getElementById("fav-stop-ref");
const favLine = document.getElementById("fav-line");
const favDirection = document.getElementById("fav-direction");
const addFavBtn = document.getElementById("add-fav-btn");
const favoritesList = document.getElementById("favorites-list");
const emptyState = document.getElementById("empty-state");
const refreshAllBtn = document.getElementById("refresh-all-btn");

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

// Close dropdown on outside click
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
                    ${fav.direction ? `<span class="text-stone-400 text-xs truncate">→ ${escapeHtml(fav.direction)}</span>` : ""}
                </div>
                <button onclick="removeFavorite('${fav.id}')" class="text-stone-300 hover:text-rose-500 ml-2 text-lg transition">&times;</button>
            </div>
            <div class="departures-list px-4 py-2" id="deps-${fav.id}">
                <div class="flex items-center justify-center py-4 text-stone-300">
                    <span class="spinner mr-2"></span> Chargement…
                </div>
            </div>
            <div class="px-4 py-2 border-t border-stone-100 text-xs text-stone-400 flex items-center gap-2" id="footer-${fav.id}">
                <span class="update-time">—</span>
            </div>
        </div>
    `).join("");
}

async function fetchDepartures(fav) {
    const container = document.getElementById(`deps-${fav.id}`);
    const footer = document.getElementById(`footer-${fav.id}`);
    if (!container) return;

    // Show spinner in footer
    const footerTime = footer?.querySelector(".update-time");

    let url = `/api/departures?stopRef=${encodeURIComponent(fav.stopRef)}&num_results=5`;
    if (fav.line) url += `&line=${encodeURIComponent(fav.line)}`;
    if (fav.direction) url += `&direction=${encodeURIComponent(fav.direction)}`;

    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const deps = await resp.json();
        errorCounts[fav.id] = 0;
        renderDepartures(container, deps);
        if (footerTime) footerTime.textContent = `Mis à jour à ${new Date().toLocaleTimeString("fr-CH")}`;
    } catch (e) {
        errorCounts[fav.id] = (errorCounts[fav.id] || 0) + 1;
        if (errorCounts[fav.id] >= MAX_RETRIES) {
            container.innerHTML = `<div class="py-3 text-center text-rose-400 text-sm">Erreur de chargement — vérifiez la connexion</div>`;
        }
    }
}

function renderDepartures(container, deps) {
    if (deps.length === 0) {
        container.innerHTML = `<div class="py-3 text-center text-stone-400 text-sm">Aucun départ prévu</div>`;
        return;
    }

    container.innerHTML = deps.map(d => {
        const scheduled = new Date(d.scheduled_time);
        const estimated = d.estimated_time ? new Date(d.estimated_time) : null;
        const timeStr = (estimated || scheduled).toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit" });
        const scheduledStr = scheduled.toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit" });
        const showCrossed = estimated && scheduledStr !== timeStr;
        const passed = d.already_passed;

        let badgeColor, badgeText;
        if (d.status === "cancelled") {
            badgeColor = "bg-stone-200 text-stone-500";
            badgeText = "annulé";
        } else if (passed) {
            badgeColor = "bg-stone-100 text-stone-400";
            badgeText = "passé";
        } else if (d.delay_minutes <= 1) {
            badgeColor = "bg-emerald-100 text-emerald-700";
            badgeText = "à l'heure";
        } else if (d.delay_minutes <= 5) {
            badgeColor = "bg-amber-100 text-amber-700";
            badgeText = `+${d.delay_minutes} min`;
        } else {
            badgeColor = "bg-rose-100 text-rose-700";
            badgeText = `+${d.delay_minutes} min`;
        }

        const lineBg = d.mode === "bus" ? "bg-amber-400" : d.mode === "rail" ? "bg-blue-500" : "bg-stone-500";
        const rowClass = passed ? "departure-passed" : "";

        return `
        <div class="flex items-center gap-3 py-2.5 border-b border-stone-50 last:border-0 ${rowClass}">
            <div class="line-badge px-2 py-1 rounded-lg text-white text-sm font-bold ${lineBg}">
                ${escapeHtml(d.line)}
            </div>
            <div class="flex-1 min-w-0">
                <div class="text-sm text-stone-700 truncate">${escapeHtml(d.destination)}</div>
                <div class="flex items-baseline gap-2">
                    ${showCrossed ? `<span class="text-xs text-stone-400 scheduled-crossed">${scheduledStr}</span>` : ""}
                    <span class="text-lg font-bold text-stone-800">${timeStr}</span>
                </div>
            </div>
            <span class="px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${badgeColor}">${badgeText}</span>
        </div>`;
    }).join("");
}

// --- Refresh ---
refreshAllBtn.addEventListener("click", refreshAll);

function refreshAll() {
    favorites.forEach(fav => fetchDepartures(fav));
}

// Auto-refresh
setInterval(refreshAll, REFRESH_INTERVAL);

// --- Init ---
function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
}

renderFavorites();
refreshAll();
