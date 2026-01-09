// Histogram visualization for camera feed
// API_BASE is already defined in app.js

let histogramUpdateInterval = null;

function drawHistogram(histData) {
    const canvas = document.getElementById('histogramCanvas');
    if (!canvas) {
        console.error('Canvas not found!');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error('Could not get canvas context!');
        return;
    }
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Validate data
    if (!histData || !histData.r || !histData.g || !histData.b) {
        console.error('Invalid histogram data:', histData);
        return;
    }
    
    if (histData.r.length !== 256 || histData.g.length !== 256 || histData.b.length !== 256) {
        console.error('Invalid histogram length');
        return;
    }
    
    const width = canvas.width;
    const height = canvas.height;
    const binWidth = width / 256;
    
    // Find max value for scaling
    let maxVal = 0;
    for (let i = 0; i < 256; i++) {
        maxVal = Math.max(maxVal, histData.r[i], histData.g[i], histData.b[i]);
    }
    
    if (maxVal === 0) {
        console.warn('Histogram is empty (max value is 0)');
        return;
    }
    
    // Draw RED channel
    ctx.globalAlpha = 0.7;
    ctx.lineWidth = 1;
    ctx.strokeStyle = '#ff0000';
    ctx.beginPath();
    for (let i = 0; i < 256; i++) {
        const x = i * binWidth;
        const y = height - (histData.r[i] / maxVal * height);
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    }
    ctx.stroke();
    
    // Draw GREEN channel
    ctx.strokeStyle = '#00ff00';
    ctx.beginPath();
    for (let i = 0; i < 256; i++) {
        const x = i * binWidth;
        const y = height - (histData.g[i] / maxVal * height);
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    }
    ctx.stroke();
    
    // Draw BLUE channel
    ctx.strokeStyle = '#0099ff';
    ctx.beginPath();
    for (let i = 0; i < 256; i++) {
        const x = i * binWidth;
        const y = height - (histData.b[i] / maxVal * height);
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    }
    ctx.stroke();
    
    ctx.globalAlpha = 1.0;
}

function updateHistogram() {
    fetch(`${API_BASE}/histogram`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                console.error('Histogram error:', data.error);
                return;
            }
            if (data.histogram) {
                drawHistogram(data.histogram);
            }
        })
        .catch(err => console.error('Histogram fetch error:', err));
}

function startHistogramUpdates() {
    console.log('Starting histogram updates...');
    updateHistogram();
    if (histogramUpdateInterval) {
        clearInterval(histogramUpdateInterval);
    }
    histogramUpdateInterval = setInterval(updateHistogram, 200);
}

function stopHistogramUpdates() {
    console.log('Stopping histogram updates...');
    if (histogramUpdateInterval) {
        clearInterval(histogramUpdateInterval);
        histogramUpdateInterval = null;
    }
}

// Slider event handlers
document.getElementById('minSlider').addEventListener('input', (e) => {
    const value = e.target.value;
    document.getElementById('minValue').textContent = value;
    fetch(`${API_BASE}/histogram/min/${value}`, { method: 'POST' });
});

document.getElementById('maxSlider').addEventListener('input', (e) => {
    const value = e.target.value;
    document.getElementById('maxValue').textContent = value;
    fetch(`${API_BASE}/histogram/max/${value}`, { method: 'POST' });
});

console.log('histogram.js loaded successfully');