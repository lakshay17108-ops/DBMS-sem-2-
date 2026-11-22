const form = document.getElementById('ticketForm');
const fileInput = document.getElementById('imageUpload');
const submitBtn = document.getElementById('submitBtn');
const receiptPanel = document.getElementById('receiptPanel');
const themeToggle = document.getElementById('themeToggle');

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    if (themeToggle) {
        themeToggle.classList.toggle('active', theme === 'dark');
        themeToggle.querySelector('.toggle__icon').textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}

function loadTheme() {
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme) {
        setTheme(storedTheme);
        return;
    }
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setTheme(prefersDark ? 'dark' : 'light');
}

if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        setTheme(currentTheme === 'dark' ? 'light' : 'dark');
    });
}

loadTheme();

// Function to convert uploaded file to Base64 String using a Promise
function toBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    let base64Image = null;
    if (fileInput.files.length > 0) {
        try {
            base64Image = await toBase64(fileInput.files[0]);
        } catch (err) {
            alert('Failed to process image');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Ticket';
            return;
        }
    }

    // determine selected block and room
    const selectedBlockBtn = document.querySelector('.block-btn.selected');
    const block = selectedBlockBtn ? selectedBlockBtn.dataset.block : '';
    const room = document.getElementById('roomInput') ? document.getElementById('roomInput').value.trim() : '';
    const locationStr = block ? `${block} Block${room ? ' - ' + room : ''}` : room;

    const payload = {
        fullName: document.getElementById('fullName').value,
        email: document.getElementById('email').value,
        phone: document.getElementById('phone').value,
        category: document.getElementById('category').value,
        priority: document.getElementById('priority').value,
        block: block,
        floor: document.getElementById('floorInput').value,
        room: room,
        date: document.getElementById('dateInput').value,
        location: locationStr,
        description: document.getElementById('description').value,
        image: base64Image
    };

    const apiBase = window.location.protocol === 'file:' || window.location.origin === 'null'
        ? 'http://127.0.0.1:5500'
        : window.location.origin;
    const submitUrl = `${apiBase}/api/submit`;

    console.log('Submitting ticket to', submitUrl);

    try {
        const response = await fetch(submitUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        let data;
        try {
            data = await response.json();
        } catch (parseError) {
            const text = await response.text();
            console.error('Response parse failed:', parseError, text);
            throw new Error(`Server returned non-JSON response (${response.status}): ${text}`);
        }

        console.log('Submit response:', response.status, data);

        if (response.ok && data.success) {
            form.classList.add('hidden');
            receiptPanel.classList.remove('hidden');
            document.getElementById('displayTicketId').textContent = data.ticket_id;
            document.getElementById('qrCodeImg').src = data.qr_code;
        } else {
            const msg = data?.message || 'Submission failed';
            alert(`Submission failed: ${msg}`);
        }
    } catch (err) {
        console.error('Submit error:', err);
        alert(`Server error occurred: ${err.message}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Ticket';
    }
});

// block button selection handling
document.querySelectorAll('.block-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.block-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
    });
});