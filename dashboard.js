/**
 * Smart GreenHouse Dashboard with Actuator Control
 * Real-time IoT sensor visualization + Actuator monitoring
 */

// ============================================
// CONFIGURATION - UPDATE THIS WITH YOUR API URL
// ============================================
const API_BASE_URL =
  "https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod";

// ============================================
// Global State
// ============================================
let sensorChart = null;
let currentGreenhouseId = "greenhouse-01";
let refreshInterval = null;

// Alert thresholds (match Lambda settings)
const THRESHOLDS = {
  temperature: { min: 15, max: 35 },
  humidity: { min: 40, max: 85 },
  soil_moisture: { min: 30, max: 80 },
  light_intensity: { min: 100, max: 1000 },
};

// ============================================
// API Functions
// ============================================
async function apiCall(endpoint, params = {}) {
  const url = new URL(`${API_BASE_URL}${endpoint}`);
  Object.keys(params).forEach((key) =>
    url.searchParams.append(key, params[key])
  );

  try {
    console.log(`API Call: ${endpoint}`, params);
    const response = await fetch(url);
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`API Error: ${endpoint} returned ${response.status}`, errorText);
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }
    const data = await response.json();
    console.log(`API Response: ${endpoint}`, data);
    return data;
  } catch (error) {
    console.error(`API Error (${endpoint}):`, error);
    updateConnectionStatus(false);
    throw error;
  }
}

async function getLatestReading() {
  return apiCall("/latest", { greenhouse_id: currentGreenhouseId });
}

async function getHistory(hours = 6) {
  return apiCall("/history", { greenhouse_id: currentGreenhouseId, hours });
}

async function getStats(hours = 24) {
  return apiCall("/stats", { greenhouse_id: currentGreenhouseId, hours });
}

async function getAlerts(limit = 10) {
  return apiCall("/alerts", { greenhouse_id: currentGreenhouseId, limit });
}

async function getGreenhouses() {
  return apiCall("/greenhouses");
}

async function getActuatorStatus() {
  return apiCall("/actuators/status", { greenhouse_id: currentGreenhouseId });
}

async function getActuatorHistory(hours = 24) {
  return apiCall("/actuators/history", {
    greenhouse_id: currentGreenhouseId,
    hours,
  });
}

async function manualControlActuator(actuator, state, speed = null) {
  const url = `${API_BASE_URL}/actuators/manual?greenhouse_id=${currentGreenhouseId}`;
  const body = {
    actuator,
    state,
    ...(speed && { speed }),
  };

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Manual control error:", error);
    throw error;
  }
}

async function getThresholds() {
  return apiCall("/actuators/thresholds");
}

async function updateThresholds(thresholds) {
  const url = `${API_BASE_URL}/actuators/thresholds`;
  
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(thresholds),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Threshold update error:", error);
    throw error;
  }
}

// ============================================
// UI Update Functions - Sensors
// ============================================
function updateCurrentReadings(data) {
  console.log("Updating current readings with data:", data);
  
  if (!data) {
    console.error("No data provided to updateCurrentReadings");
    return;
  }
  
  if (!data.sensors) {
    console.error("No sensors data in response:", data);
    return;
  }

  const sensors = data.sensors;

  updateCard("temp", sensors.temperature?.value, "°C", THRESHOLDS.temperature);
  updateCard("humidity", sensors.humidity?.value, "%", THRESHOLDS.humidity);
  updateCard("soil", sensors.soil_moisture?.value, "%", THRESHOLDS.soil_moisture);
  updateCard("light", sensors.light_intensity?.value, " lux", THRESHOLDS.light_intensity);

  if (data.timestamp) {
    const timestamp = new Date(data.timestamp);
    document.getElementById("last-updated").textContent = `Last updated: ${timestamp.toLocaleTimeString()}`;
  }
}

function updateCard(sensorId, value, unit, thresholds) {
  const valueEl = document.getElementById(`current-${sensorId}`);
  const statusEl = document.getElementById(`${sensorId}-status`);

  if (!valueEl || !statusEl) {
    console.error(`Card elements not found for sensor: ${sensorId}`);
    return;
  }

  if (value === undefined || value === null) {
    valueEl.textContent = "--";
    return;
  }

  valueEl.textContent = value.toFixed(1);

  statusEl.className = "card-status";
  if (value < thresholds.min || value > thresholds.max) {
    statusEl.classList.add("danger");
  } else if (value < thresholds.min * 1.1 || value > thresholds.max * 0.9) {
    statusEl.classList.add("warning");
  }
}

function updateStats(data) {
  console.log("Updating stats with data:", data);
  
  if (!data) {
    console.error("No data provided to updateStats");
    return;
  }

  document.getElementById("stat-readings").textContent = data.summary?.total_readings || "--";
  document.getElementById("stat-alerts").textContent = data.summary?.total_alerts || "0";
  document.getElementById("stat-avg-temp").textContent = data.temperature ? `${data.temperature.avg}°C` : "--°C";
  document.getElementById("stat-avg-humidity").textContent = data.humidity ? `${data.humidity.avg}%` : "--%";

  if (data.temperature) {
    document.getElementById("temp-range").textContent = `Min: ${data.temperature.min}°C | Max: ${data.temperature.max}°C`;
  }
  if (data.humidity) {
    document.getElementById("humidity-range").textContent = `Min: ${data.humidity.min}% | Max: ${data.humidity.max}%`;
  }
  if (data.soil_moisture) {
    document.getElementById("soil-range").textContent = `Min: ${data.soil_moisture.min}% | Max: ${data.soil_moisture.max}%`;
  }
  if (data.light_intensity) {
    document.getElementById("light-range").textContent = `Min: ${data.light_intensity.min} | Max: ${data.light_intensity.max} lux`;
  }
}

function updateAlertsList(data) {
  console.log("Updating alerts list with data:", data);
  const container = document.getElementById("alerts-list");

  if (!data || !data.alerts || data.alerts.length === 0) {
    container.innerHTML = '<p class="no-alerts">✅ No recent alerts - all systems normal!</p>';
    return;
  }

  const alertsHtml = data.alerts.slice(0, 8).map((alert) => {
      const isCritical = alert.severity === "CRITICAL";
      const icon = isCritical ? "🚨" : "⚠️";
      const time = new Date(alert.reading_timestamp).toLocaleTimeString();

      return `
        <div class="alert-item ${isCritical ? "" : "warning"}">
          <span class="alert-icon">${icon}</span>
          <span class="alert-text">
            <strong>${alert.alert_type.replace(/_/g, " ")}</strong><br>
            Value: ${alert.value}${alert.unit} (threshold: ${alert.threshold}${alert.unit})
          </span>
          <span class="alert-time">${time}</span>
        </div>
      `;
    }).join("");

  container.innerHTML = alertsHtml;
}

function updateConnectionStatus(connected) {
  const statusEl = document.getElementById("connection-status");
  if (connected) {
    statusEl.textContent = "🟢 Connected";
    statusEl.style.color = "#28a745";
  } else {
    statusEl.textContent = "🔴 Connection Error";
    statusEl.style.color = "#dc3545";
  }
}

// ============================================
// UI Update Functions - Actuators
// ============================================
function updateActuatorStatus(data) {
  console.log("Updating actuator status with data:", data);
  
  if (!data) {
    console.error("No data provided to updateActuatorStatus");
    return;
  }
  
  if (!data.actuators) {
    console.warn("No actuator data in response:", data);
    return;
  }

  const actuators = data.actuators;
  const thresholds = data.thresholds;

  const waterPump = actuators.find((a) => a.name === "water_pump");
  if (waterPump) {
    updateActuatorCard("water-pump", waterPump);
  } else {
    console.warn("water_pump not found in actuators");
  }

  const coolingFan = actuators.find((a) => a.name === "cooling_fan");
  if (coolingFan) {
    updateActuatorCard("cooling-fan", coolingFan);
  } else {
    console.warn("cooling_fan not found in actuators");
  }

  if (thresholds) {
    updateThresholdsDisplay(thresholds);
  } else {
    console.warn("No thresholds in actuator response");
  }
}

function updateActuatorCard(cardId, actuator) {
  const stateEl = document.getElementById(`${cardId}-state`);
  const reasonEl = document.getElementById(`${cardId}-reason`);
  const updatedEl = document.getElementById(`${cardId}-updated`);
  const onBtn = document.getElementById(`${cardId}-on`);
  const offBtn = document.getElementById(`${cardId}-off`);

  if (!stateEl || !reasonEl || !updatedEl || !onBtn || !offBtn) {
    console.error(`Actuator card elements not found for: ${cardId}`);
    return;
  }

  const isOn = actuator.state === "ON";

  stateEl.textContent = actuator.state;
  stateEl.className = `actuator-state ${isOn ? "on" : "off"}`;
  stateEl.innerHTML = `
    <span class="state-indicator ${isOn ? "on" : "off"}"></span>
    ${actuator.state}${actuator.speed ? ` (${actuator.speed})` : ""}
  `;

  reasonEl.textContent = actuator.reason || "No recent activity";

  if (actuator.last_updated) {
    const time = new Date(actuator.last_updated).toLocaleTimeString();
    updatedEl.textContent = `Last updated: ${time}`;
  }

  onBtn.disabled = isOn;
  offBtn.disabled = !isOn;
}

function updateThresholdsDisplay(thresholds) {
  document.getElementById("soil-on-threshold").textContent = `${thresholds.soil_moisture.turn_on}%`;
  document.getElementById("soil-off-threshold").textContent = `${thresholds.soil_moisture.turn_off}%`;
  document.getElementById("temp-low-threshold").textContent = `${thresholds.temperature.turn_on_low}°C`;
  document.getElementById("temp-high-threshold").textContent = `${thresholds.temperature.turn_on_high}°C`;
  document.getElementById("temp-off-threshold").textContent = `${thresholds.temperature.turn_off}°C`;
}

function updateActuatorHistory(data) {
  console.log("Updating actuator history with data:", data);
  const container = document.getElementById("history-list");

  if (!data || !data.commands || data.commands.length === 0) {
    container.innerHTML = '<p class="no-alerts">No actuator commands in the last 24 hours</p>';
    return;
  }

  const historyHtml = data.commands.slice(0, 20).map((cmd) => {
      const time = new Date(cmd.timestamp).toLocaleTimeString();
      const date = new Date(cmd.timestamp).toLocaleDateString();
      const icon = cmd.actuator === "water_pump" ? "💧" : "🌬️";

      return `
        <div class="history-item">
          <div class="history-item-left">
            <span class="history-icon">${icon}</span>
            <div class="history-content">
              <div class="history-actuator">
                ${cmd.actuator.replace("_", " ")} → ${cmd.state}
                ${cmd.speed ? `(${cmd.speed})` : ""}
              </div>
              <div class="history-reason">${cmd.reason}</div>
            </div>
          </div>
          <div class="history-time">${time}<br>${date}</div>
        </div>
      `;
    }).join("");

  container.innerHTML = historyHtml;
}

// ============================================
// Actuator Control Functions
// ============================================
async function controlActuator(actuator, state, buttonId) {
  const btn = document.getElementById(buttonId);
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "⏳ Loading...";

  try {
    const result = await manualControlActuator(actuator, state);

    if (result.success) {
      console.log(`✅ ${result.message}`);
      setTimeout(async () => {
        await refreshActuators();
      }, 1000);
    } else {
      alert(`Error: ${result.error || "Failed to control actuator"}`);
    }
  } catch (error) {
    console.error("Control error:", error);
    alert(`Failed to control actuator: ${error.message}`);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

// ============================================
// Threshold Edit Functions
// ============================================
let isEditingThresholds = false;
let originalThresholdValues = {};

function toggleThresholdEdit() {
  isEditingThresholds = !isEditingThresholds;
  
  const editBtn = document.getElementById('edit-thresholds-btn');
  const actions = document.getElementById('threshold-edit-actions');
  
  // Get all span and input elements
  const spans = ['soil-on-threshold', 'soil-off-threshold', 'temp-low-threshold', 'temp-high-threshold', 'temp-off-threshold'];
  const inputs = ['soil-on-input', 'soil-off-input', 'temp-low-input', 'temp-high-input', 'temp-off-input'];
  
  if (isEditingThresholds) {
    // Switch to edit mode
    editBtn.textContent = '🔒 Cancel Edit';
    editBtn.className = 'btn-off';
    actions.style.display = 'block';
    
    // Store original values and show inputs
    spans.forEach((spanId, i) => {
      const span = document.getElementById(spanId);
      const input = document.getElementById(inputs[i]);
      
      const value = parseFloat(span.textContent);
      originalThresholdValues[spanId] = value;
      
      input.value = value;
      span.style.display = 'none';
      input.style.display = 'inline-block';
    });
  } else {
    // Cancel edit mode
    cancelThresholdEdit();
  }
}

function cancelThresholdEdit() {
  isEditingThresholds = false;
  
  const editBtn = document.getElementById('edit-thresholds-btn');
  const actions = document.getElementById('threshold-edit-actions');
  
  editBtn.textContent = '✏️ Edit Thresholds';
  editBtn.className = 'btn-on';
  actions.style.display = 'none';
  
  // Restore original values and hide inputs
  const spans = ['soil-on-threshold', 'soil-off-threshold', 'temp-low-threshold', 'temp-high-threshold', 'temp-off-threshold'];
  const inputs = ['soil-on-input', 'soil-off-input', 'temp-low-input', 'temp-high-input', 'temp-off-input'];
  
  spans.forEach((spanId, i) => {
    const span = document.getElementById(spanId);
    const input = document.getElementById(inputs[i]);
    
    span.style.display = 'inline';
    input.style.display = 'none';
  });
}

async function saveThresholds() {
  const soilOn = parseFloat(document.getElementById('soil-on-input').value);
  const soilOff = parseFloat(document.getElementById('soil-off-input').value);
  const tempLow = parseFloat(document.getElementById('temp-low-input').value);
  const tempHigh = parseFloat(document.getElementById('temp-high-input').value);
  const tempOff = parseFloat(document.getElementById('temp-off-input').value);
  
  // Validation
  if (soilOff <= soilOn) {
    alert('❌ Validation Error: Soil moisture "Turn OFF" must be greater than "Turn ON"');
    return;
  }
  
  if (tempHigh <= tempLow) {
    alert('❌ Validation Error: Temperature "Fan HIGH" must be greater than "Fan LOW"');
    return;
  }
  
  if (tempLow <= tempOff) {
    alert('❌ Validation Error: Temperature "Fan LOW" must be greater than "Turn OFF"');
    return;
  }
  
  const newThresholds = {
    soil_moisture: {
      turn_on: soilOn,
      turn_off: soilOff
    },
    temperature: {
      turn_on_low: tempLow,
      turn_on_high: tempHigh,
      turn_off: tempOff
    }
  };
  
  try {
    const result = await updateThresholds(newThresholds);
    
    if (result.success) {
      console.log('✅ Thresholds updated:', result.thresholds);
      
      // Update display
      document.getElementById('soil-on-threshold').textContent = `${soilOn}%`;
      document.getElementById('soil-off-threshold').textContent = `${soilOff}%`;
      document.getElementById('temp-low-threshold').textContent = `${tempLow}°C`;
      document.getElementById('temp-high-threshold').textContent = `${tempHigh}°C`;
      document.getElementById('temp-off-threshold').textContent = `${tempOff}°C`;
      
      cancelThresholdEdit();
      
      alert('✅ Thresholds updated successfully!\n\nNew automation rules will apply to future actuator decisions.');
    } else {
      alert(`❌ Error: ${result.error || 'Failed to update thresholds'}`);
    }
  } catch (error) {
    console.error('Failed to save thresholds:', error);
    alert(`❌ Failed to save thresholds: ${error.message}`);
  }
}

window.controlActuator = controlActuator;
window.refreshData = refreshData;
window.updateCharts = updateCharts;
window.toggleThresholdEdit = toggleThresholdEdit;
window.cancelThresholdEdit = cancelThresholdEdit;
window.saveThresholds = saveThresholds;

// ============================================
// Chart Functions
// ============================================
function initChart() {
  const ctx = document.getElementById("sensor-chart").getContext("2d");

  sensorChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Temperature (°C)",
          data: [],
          borderColor: "#ff6b6b",
          backgroundColor: "rgba(255, 107, 107, 0.1)",
          tension: 0.3,
          fill: true,
          yAxisID: "y",
        },
        {
          label: "Humidity (%)",
          data: [],
          borderColor: "#4dabf7",
          backgroundColor: "rgba(77, 171, 247, 0.1)",
          tension: 0.3,
          fill: true,
          yAxisID: "y1",
        },
        {
          label: "Soil Moisture (%)",
          data: [],
          borderColor: "#8b5a2b",
          backgroundColor: "rgba(139, 90, 43, 0.1)",
          tension: 0.3,
          fill: true,
          yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top", labels: { usePointStyle: true, padding: 20 } },
        tooltip: { backgroundColor: "rgba(0, 0, 0, 0.8)", padding: 12 },
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } },
        y: {
          type: "linear",
          display: true,
          position: "left",
          title: { display: true, text: "Temperature (°C)" },
          grid: { color: "rgba(0, 0, 0, 0.05)" },
        },
        y1: {
          type: "linear",
          display: true,
          position: "right",
          title: { display: true, text: "Percentage (%)" },
          grid: { drawOnChartArea: false },
          min: 0,
          max: 100,
        },
      },
    },
  });
}

function updateChartData(historyData) {
  if (!sensorChart || !historyData || !historyData.readings) return;

  const readings = historyData.readings;
  const maxPoints = 100;
  const step = Math.max(1, Math.floor(readings.length / maxPoints));
  const sampledReadings = readings.filter((_, i) => i % step === 0);

  const labels = sampledReadings.map((r) => {
    const date = new Date(r.timestamp);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  });

  const temperatures = sampledReadings.map((r) => r.sensors?.temperature?.value);
  const humidities = sampledReadings.map((r) => r.sensors?.humidity?.value);
  const soilMoistures = sampledReadings.map((r) => r.sensors?.soil_moisture?.value);

  sensorChart.data.labels = labels;
  sensorChart.data.datasets[0].data = temperatures;
  sensorChart.data.datasets[1].data = humidities;
  sensorChart.data.datasets[2].data = soilMoistures;
  sensorChart.update("none");
}

async function updateCharts() {
  const hours = parseInt(document.getElementById("chart-hours").value);
  try {
    const historyData = await getHistory(hours);
    updateChartData(historyData);
  } catch (error) {
    console.error("Failed to update charts:", error);
  }
}

// ============================================
// Main Refresh Functions
// ============================================
async function refreshData() {
  const btn = document.getElementById("refresh-btn");
  btn.textContent = "⏳ Loading...";
  btn.disabled = true;

  try {
    console.log("Fetching data from API...");
    
    // Fetch core sensor data (required)
    const [latest, stats, alerts] = await Promise.all([
      getLatestReading(),
      getStats(24),
      getAlerts(10),
    ]);

    console.log("API data received:", { latest, stats, alerts });

    updateCurrentReadings(latest);
    updateStats(stats);
    updateAlertsList(alerts);
    await updateCharts();

    // Try to fetch actuator data (optional - may not be implemented)
    try {
      const [actuatorStatus, actuatorHistory] = await Promise.all([
        getActuatorStatus(),
        getActuatorHistory(24),
      ]);
      
      console.log("Actuator data received:", { actuatorStatus, actuatorHistory });
      updateActuatorStatus(actuatorStatus);
      updateActuatorHistory(actuatorHistory);
    } catch (actuatorError) {
      console.log("⚠️ Actuator endpoints not available:", actuatorError.message);
      // Hide actuator sections if API not available
      hideActuatorSections();
    }

    updateConnectionStatus(true);
    console.log("✅ Dashboard updated successfully");
  } catch (error) {
    console.error("❌ Refresh failed:", error);
    updateConnectionStatus(false);
    alert(`Failed to load data: ${error.message}\n\nCheck the browser console for details.`);
  } finally {
    btn.textContent = "🔄 Refresh";
    btn.disabled = false;
  }
}

function hideActuatorSections() {
  const actuatorSection = document.querySelector(".actuator-section");
  const thresholdPanel = document.querySelector(".threshold-panel");
  const historyPanel = document.querySelector(".history-panel");
  
  if (actuatorSection) {
    actuatorSection.style.display = "none";
    console.log("Hidden actuator section");
  }
  if (thresholdPanel) {
    thresholdPanel.style.display = "none";
    console.log("Hidden threshold panel");
  }
  if (historyPanel) {
    historyPanel.style.display = "none";
    console.log("Hidden history panel");
  }
}

async function refreshActuators() {
  try {
    const [actuatorStatus, actuatorHistory] = await Promise.all([
      getActuatorStatus(),
      getActuatorHistory(24),
    ]);

    updateActuatorStatus(actuatorStatus);
    updateActuatorHistory(actuatorHistory);
  } catch (error) {
    console.error("Failed to refresh actuators:", error);
    // Hide actuator sections if endpoints don't exist
    hideActuatorSections();
  }
}

async function loadGreenhouses() {
  try {
    const data = await getGreenhouses();
    const select = document.getElementById("greenhouse-select");

    if (data.greenhouses && data.greenhouses.length > 0) {
      select.innerHTML = data.greenhouses
        .map((id) => `<option value="${id}">${id}</option>`)
        .join("");
    }

    select.addEventListener("change", (e) => {
      currentGreenhouseId = e.target.value;
      refreshData();
    });
  } catch (error) {
    console.error("Failed to load greenhouses:", error);
  }
}

// ============================================
// Initialization
// ============================================
document.addEventListener("DOMContentLoaded", async () => {
  console.log("🌱 Smart GreenHouse Dashboard initializing...");
  console.log("API Base URL:", API_BASE_URL);

  if (API_BASE_URL === "YOUR_API_GATEWAY_URL_HERE") {
    alert("⚠️ Please update API_BASE_URL in dashboard.js with your API Gateway URL!");
    return;
  }

  try {
    initChart();
    console.log("✅ Chart initialized");
    
    await loadGreenhouses();
    console.log("✅ Greenhouses loaded");
    
    await refreshData();
    console.log("✅ Initial data loaded");

    refreshInterval = setInterval(refreshData, 30000);

    console.log("✅ Dashboard ready!");
    console.log("🤖 Automatic actuator control runs every 5 minutes via EventBridge");
  } catch (error) {
    console.error("❌ Dashboard initialization failed:", error);
    alert(`Dashboard failed to initialize: ${error.message}\n\nCheck browser console for details.`);
  }
});

window.addEventListener("beforeunload", () => {
  if (refreshInterval) clearInterval(refreshInterval);
});
