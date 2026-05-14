const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadSection = document.getElementById('upload-section');
const uploadProgress = document.getElementById('upload-progress');
const reviewSection = document.getElementById('review-section');
const formsContainer = document.getElementById('forms-container');
const btnGenerate = document.getElementById('btn-generate');
const downloadSection = document.getElementById('download-section');
const downloadLinkContainer = document.getElementById('download-link-container');
const btnRestart = document.getElementById('btn-restart');

let globalConsumersData = [];

// Handle Drag & Drop
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files);
    }
});
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFiles(e.target.files);
    }
});

async function handleFiles(files) {
    if (files.length > 2) {
        alert("Please upload 1 or 2 bills maximum.");
        return;
    }

    dropZone.classList.add('hidden');
    uploadProgress.classList.remove('hidden');

    try {
        globalConsumersData = [];
        for (let i = 0; i < files.length; i++) {
            const formData = new FormData();
            formData.append('file', files[i]);
            
            const response = await fetch('/api/extract', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Extraction failed');
            }

            const data = await response.json();
            globalConsumersData.push(data);
        }

        renderForms();
        uploadSection.classList.add('hidden');
        reviewSection.classList.remove('hidden');
    } catch (error) {
        alert("Error during extraction: " + error.message);
        dropZone.classList.remove('hidden');
        uploadProgress.classList.add('hidden');
    }
}

function renderForms() {
    formsContainer.innerHTML = '';
    
    globalConsumersData.forEach((consumer, index) => {
        const formDiv = document.createElement('div');
        formDiv.className = 'consumer-form fade-in';
        
        let warningsHtml = '';
        if (consumer._warnings && consumer._warnings.length > 0) {
            warningsHtml = `
            <div class="warning-box">
                <strong>⚠️ AI Validation Warnings</strong>
                <ul>
                    ${consumer._warnings.map(w => `<li>${w}</li>`).join('')}
                </ul>
            </div>`;
        }

        formDiv.innerHTML = `
            <h3>Consumer ${index + 1}</h3>
            ${warningsHtml}
            <div class="form-grid">
                <div class="form-group">
                    <label>Consumer Name</label>
                    <input type="text" id="name-${index}" value="${consumer.consumer_name || ''}">
                </div>
                <div class="form-group">
                    <label>Consumer Number</label>
                    <input type="text" id="number-${index}" value="${consumer.consumer_number || ''}">
                </div>
                <div class="form-group">
                    <label>Connection Type</label>
                    <input type="text" id="type-${index}" value="${consumer.connection_type || ''}">
                </div>
                <div class="form-group">
                    <label>Sanctioned Load</label>
                    <input type="text" id="load-${index}" value="${consumer.sanctioned_load || ''}">
                </div>
                <div class="form-group">
                    <label>Fixed Charges (₹)</label>
                    <input type="number" id="fixed-${index}" value="${consumer.fixed_charges || 0}" step="0.01">
                </div>
                <div class="form-group">
                    <label>Bill Amount (₹)</label>
                    <input type="number" id="amount-${index}" value="${consumer.bill_amount || 0}" step="0.01">
                </div>
            </div>
            <h4 style="margin-top: 1rem; margin-bottom: 0.5rem; font-size:0.9rem; color:#64748b;">Monthly Units</h4>
            <div class="form-grid" style="grid-template-columns: repeat(6, 1fr);" id="months-${index}">
            </div>
        `;
        formsContainer.appendChild(formDiv);

        const monthsContainer = document.getElementById(`months-${index}`);
        // Create 12 inputs for months
        const history = consumer.monthly_consumption || [];
        for (let i = 0; i < 12; i++) {
            const entry = history[i] || { month: `Month ${i+1}`, units: 0 };
            const mGroup = document.createElement('div');
            mGroup.className = 'form-group';
            mGroup.innerHTML = `
                <label style="font-size:0.75rem;">${entry.month}</label>
                <input type="number" class="month-unit" data-consumer="${index}" data-month-name="${entry.month}" value="${entry.units !== null ? entry.units : 0}">
            `;
            monthsContainer.appendChild(mGroup);
        }
    });
}

btnGenerate.addEventListener('click', async () => {
    // Gather updated data
    const payload = [];
    
    globalConsumersData.forEach((original, index) => {
        const cData = {
            consumer_name: document.getElementById(`name-${index}`).value,
            consumer_number: document.getElementById(`number-${index}`).value,
            connection_type: document.getElementById(`type-${index}`).value,
            sanctioned_load: document.getElementById(`load-${index}`).value,
            fixed_charges: parseFloat(document.getElementById(`fixed-${index}`).value) || 0,
            bill_amount: parseFloat(document.getElementById(`amount-${index}`).value) || 0,
            monthly_consumption: []
        };
        
        const monthInputs = document.querySelectorAll(`#months-${index} .month-unit`);
        monthInputs.forEach(input => {
            cData.monthly_consumption.push({
                month: input.getAttribute('data-month-name'),
                units: parseInt(input.value) || 0
            });
        });
        
        payload.push(cData);
    });

    const originalText = btnGenerate.innerHTML;
    btnGenerate.innerHTML = '<div class="spinner" style="width:20px;height:20px;border-width:2px;margin:0;"></div> Generating & Downloading...';
    btnGenerate.disabled = true;

    try {
        const formData = new URLSearchParams();
        formData.append('payload', JSON.stringify({ consumers: payload }));

        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || 'Failed to generate Excel');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'Energybae_Customer_Proposal.xlsx';
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        setTimeout(() => {
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }, 100);

        // Show success state
        reviewSection.classList.add('hidden');
        downloadSection.classList.remove('hidden');
        
        // Hide the secondary download link
        downloadLinkContainer.innerHTML = '';

    } catch (error) {
        alert("Failed to generate Excel: " + error.message);
    } finally {
        btnGenerate.innerHTML = originalText;
        btnGenerate.disabled = false;
    }
});

btnRestart.addEventListener('click', () => {
    globalConsumersData = [];
    fileInput.value = '';
    dropZone.classList.remove('hidden');
    uploadProgress.classList.add('hidden');
    downloadSection.classList.add('hidden');
    uploadSection.classList.remove('hidden');
});
