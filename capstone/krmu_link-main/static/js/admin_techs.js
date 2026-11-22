let editingTechId = null;

document.addEventListener('DOMContentLoaded', () => {
    const saveBtn = document.getElementById('saveTechBtn');
    const cancelBtn = document.getElementById('cancelTechBtn');
    saveBtn.addEventListener('click', saveTech);
    cancelBtn.addEventListener('click', resetTechForm);
    fetchTechs();
});

async function fetchTechs() {
    const res = await fetch('/api/techs');
    if (res.status === 401) return; // admin auth will be handled by admin.js
    if (res.ok) {
        const list = await res.json();
        renderTechs(list);
    }
}

function renderTechs(list) {
    const body = document.getElementById('techsBody');
    body.innerHTML = '';
    list.forEach(t => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${t.category}</td>
            <td>${t.email}</td>
            <td>
                <button onclick="editTech('${t.id}')">Edit</button>
                <button onclick="removeTech('${t.id}')">Delete</button>
            </td>`;
        body.appendChild(tr);
    });
}

function resetTechForm() {
    editingTechId = null;
    document.getElementById('techCategory').value = '';
    document.getElementById('techEmail').value = '';
}

function editTech(id) {
    // fetch single tech from server list
    fetch('/api/techs').then(r => r.json()).then(list => {
        const t = list.find(x => x.id === id);
        if (!t) return;
        editingTechId = id;
        document.getElementById('techCategory').value = t.category;
        document.getElementById('techEmail').value = t.email;
    });
}

async function saveTech() {
    const category = document.getElementById('techCategory').value.trim();
    const email = document.getElementById('techEmail').value.trim();
    if (!category || !email) return alert('Provide both category and email');

    if (editingTechId) {
        const res = await fetch(`/api/techs/${editingTechId}`, {
            method: 'PUT', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({category, email})
        });
        if (res.ok) { resetTechForm(); fetchTechs(); }
        else alert('Failed to update');
    } else {
        const res = await fetch('/api/techs', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({category, email})
        });
        if (res.ok) { resetTechForm(); fetchTechs(); }
        else alert('Failed to add');
    }
}

async function removeTech(id) {
    if (!confirm('Remove this technician?')) return;
    const res = await fetch(`/api/techs/${id}`, {method: 'DELETE'});
    if (res.ok) fetchTechs(); else alert('Failed to delete');
}
