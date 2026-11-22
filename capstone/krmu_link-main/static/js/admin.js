// ── Theme toggle ─────────────────────────────────────────────────────────────
function setAdminTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}

function loadAdminTheme() {
    const stored = localStorage.getItem('theme');
    if (stored) { setAdminTheme(stored); return; }
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setAdminTheme(prefersDark ? 'dark' : 'light');
}

loadAdminTheme();
// ─────────────────────────────────────────────────────────────────────────────

let currentTicketId = null;
let cachedTickets   = [];
let sortDirection   = 'desc';

// ── Auth helpers ──────────────────────────────────────────────────────────────
function showAuthPrompt(message) {
    const overlay = document.getElementById('authOverlay');
    const msg     = document.getElementById('authMessage');
    const input   = document.getElementById('adminPasswordInput');
    if (overlay) overlay.classList.remove('hidden');
    if (msg)     msg.textContent = message || '';
    if (input)   { input.value = ''; input.focus(); }
}

function hideAuthPrompt() {
    const overlay = document.getElementById('authOverlay');
    const msg     = document.getElementById('authMessage');
    if (overlay) overlay.classList.add('hidden');
    if (msg)     msg.textContent = '';
}

async function submitAdminLogin() {
    const input   = document.getElementById('adminPasswordInput');
    const msg     = document.getElementById('authMessage');
    const password = input ? input.value.trim() : '';

    if (!password) {
        if (msg) msg.textContent = 'Please enter the admin password.';
        return;
    }

    if (msg) msg.textContent = 'Verifying…';

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });

        if (res.ok) {
            hideAuthPrompt();
            refreshAdminData();
        } else {
            if (msg) msg.textContent = 'Incorrect password. Please try again.';
            if (input) { input.value = ''; input.focus(); }
        }
    } catch (err) {
        console.error('Login error:', err);
        if (msg) msg.textContent = 'Network error. Is the server running?';
    }
}

async function checkAuth() {
    try {
        const res = await fetch('/api/check_auth', { credentials: 'same-origin' });
        if (res.ok) {
            hideAuthPrompt();
            refreshAdminData();
        } else {
            showAuthPrompt('Enter the admin password to continue.');
        }
    } catch (err) {
        console.error('Auth check error:', err);
        showAuthPrompt('Unable to reach the server. Please try again.');
    }
}

async function doLogout() {
    try {
        await fetch('/api/logout', { method: 'POST', credentials: 'same-origin' });
    } catch (err) {
        console.error('Logout error:', err);
    }
    // Clear local data and show login overlay
    cachedTickets = [];
    const tbody = document.getElementById('ticketsBody');
    if (tbody) tbody.innerHTML = '';
    showAuthPrompt('You have been logged out.');
}
// ─────────────────────────────────────────────────────────────────────────────

function updateSortButtonLabel() {
    const btn = document.getElementById('sortToggleBtn');
    if (btn) btn.textContent = sortDirection === 'asc' ? 'Ascending ↑' : 'Descending ↓';
}

function refreshAdminData() {
    fetchTickets();
    if (typeof fetchTechs === 'function') fetchTechs();
}

// ── Boot after DOM ready ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Auth overlay wiring
    const loginBtn    = document.getElementById('adminLoginBtn');
    const pwdInput    = document.getElementById('adminPasswordInput');
    if (loginBtn) loginBtn.addEventListener('click', submitAdminLogin);
    if (pwdInput)  pwdInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') submitAdminLogin();
    });

    // Sort controls
    const sortSelect    = document.getElementById('sortSelect');
    const sortToggleBtn = document.getElementById('sortToggleBtn');
    if (sortSelect)    sortSelect.addEventListener('change', renderTable);
    if (sortToggleBtn) sortToggleBtn.addEventListener('click', () => {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
        updateSortButtonLabel();
        renderTable();
    });

    // Other buttons
    const refreshBtn    = document.getElementById('refreshBtn');
    const closeModalBtn = document.getElementById('closeModal');
    const saveStatusBtn = document.getElementById('saveStatusBtn');
    const deleteBtn     = document.getElementById('deleteTicketBtn');
    const logoutBtn     = document.getElementById('logoutBtn');
    if (refreshBtn)    refreshBtn.addEventListener('click', refreshAdminData);
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
    if (saveStatusBtn) saveStatusBtn.addEventListener('click', updateStatus);
    if (deleteBtn)     deleteBtn.addEventListener('click', deleteTicket);
    if (logoutBtn)     logoutBtn.addEventListener('click', doLogout);

    // Theme toggle
    const themeBtn = document.getElementById('themeToggleBtn');
    if (themeBtn) themeBtn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        setAdminTheme(current === 'dark' ? 'light' : 'dark');
    });

    updateSortButtonLabel();

    // Overlay is visible by default (from HTML) — check if session is already valid
    checkAuth();
});
// ─────────────────────────────────────────────────────────────────────────────

async function fetchTickets() {
    try {
        const res = await fetch('/api/tickets', { credentials: 'same-origin' });
        if (res.ok) {
            cachedTickets = await res.json();
            renderTable();
        } else if (res.status === 401) {
            showAuthPrompt('Session expired. Please log in again.');
        }
    } catch (err) {
        console.error('fetchTickets error:', err);
    }
}

function closeModal() {
    const modal = document.getElementById('detailModal');
    if (modal) modal.classList.add('hidden');
    document.body.classList.remove('modal-open');
}

function getSortedTickets() {
    const list      = [...cachedTickets];
    const sortSel   = document.getElementById('sortSelect');
    const key       = sortSel ? sortSel.value : 'newest';
    const direction = sortDirection === 'asc' ? 1 : -1;

    if (key === 'category') {
        list.sort((a, b) => (a.category || '').localeCompare(b.category || '') * direction);
        return list;
    }
    if (key === 'date') {
        list.sort((a, b) => (getTicketDateValue(a) - getTicketDateValue(b)) * direction);
        return list;
    }
    if (key === 'priority') {
        list.sort((a, b) => (getPriorityRank(b.priority) - getPriorityRank(a.priority)) * direction);
        return list;
    }
    // default: newest first
    list.sort((a, b) => getTicketDateValue(b) - getTicketDateValue(a));
    return list;
}

function getTicketDateValue(ticket) {
    if (ticket.timestamp) return Number(ticket.timestamp) * 1000;
    if (!ticket.date)     return 0;
    const d = new Date(ticket.date);
    return isNaN(d.getTime()) ? 0 : d.getTime();
}

function getPriorityRank(priority) {
    const map = { urgent: 4, high: 3, medium: 2, low: 1 };
    return map[(priority || '').toLowerCase()] || 0;
}

function renderTable() {
    const tbody = document.getElementById('ticketsBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    getSortedTickets().forEach(ticket => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${ticket.ticket_id}</td>
            <td>${ticket.full_name  || '—'}</td>
            <td>${ticket.category   || '—'}</td>
            <td>${ticket.priority   || '—'}</td>
            <td>${ticket.location   || '—'}</td>
            <td>${formatIssueDate(ticket.date)}</td>
            <td>${ticket.status}</td>
            <td><button class="view-btn" onclick="openModal('${ticket.ticket_id}')">Inspect</button></td>
        `;
        tbody.appendChild(tr);
    });
}

function formatIssueDate(value) {
    if (!value) return '—';
    const d = new Date(value);
    if (isNaN(d.getTime())) return value;
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function openModal(id) {
    const ticket = cachedTickets.find(t => t.ticket_id === id);
    if (!ticket) return;

    currentTicketId = id;
    document.getElementById('modalTicketId').textContent  = ticket.ticket_id;
    document.getElementById('mName').textContent          = ticket.full_name  || '—';
    document.getElementById('mEmail').textContent         = ticket.email      || '—';
    document.getElementById('mPhone').textContent         = ticket.phone      || '—';
    document.getElementById('mCategory').textContent      = ticket.category   || '—';
    document.getElementById('mPriority').textContent      = ticket.priority   || '—';
    document.getElementById('mLocation').textContent      = ticket.location   || '—';
    document.getElementById('mFloor').textContent         = ticket.floor      || '—';
    document.getElementById('mRoom').textContent          = ticket.room       || '—';
    document.getElementById('mDate').textContent          = formatIssueDate(ticket.date);
    document.getElementById('mDescription').textContent   = ticket.description || '—';
    document.getElementById('statusSelect').value         = ticket.status;

    const imgEl = document.getElementById('mImage');
    imgEl.src = ticket.image || '';
    imgEl.alt = ticket.image ? 'User uploaded image' : 'No Image Provided';

    const qrEl = document.getElementById('mQrCode');
    qrEl.src = ticket.qr_code ? `data:image/png;base64,${ticket.qr_code}` : '';

    const deleteBtn = document.getElementById('deleteTicketBtn');
    if (deleteBtn) {
        deleteBtn.classList.toggle('hidden',
            ticket.status !== 'Completed' && ticket.status !== 'Cancelled');
    }

    document.getElementById('detailModal').classList.remove('hidden');
    document.body.classList.add('modal-open');
}

async function updateStatus() {
    const newStatus = document.getElementById('statusSelect').value;
    try {
        const res = await fetch(`/api/tickets/${currentTicketId}/status`, {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        if (res.ok) {
            closeModal();
            fetchTickets();
        } else if (res.status === 401) {
            showAuthPrompt('Session expired. Please log in again.');
        } else {
            alert('Failed to update status.');
        }
    } catch (err) {
        console.error('updateStatus error:', err);
        alert('Network error while updating status.');
    }
}

async function deleteTicket() {
    if (!confirm('Are you sure you want to permanently purge this ticket from the database?')) return;
    try {
        const res = await fetch(`/api/tickets/${currentTicketId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        if (res.ok) {
            closeModal();
            fetchTickets();
        } else if (res.status === 401) {
            showAuthPrompt('Session expired. Please log in again.');
        } else {
            alert('Failed to delete ticket.');
        }
    } catch (err) {
        console.error('deleteTicket error:', err);
        alert('Network error while deleting ticket.');
    }
}