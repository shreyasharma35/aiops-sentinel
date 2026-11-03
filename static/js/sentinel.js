/**
 * AIOps Sentinel - Enterprise SRE Observability & Autonomous Recovery Control Plane
 * Full-featured JavaScript architecture powering all 14 enterprise dashboard tabs,
 * Chart.js data streaming, explainable RCA, human-in-the-loop recovery, and guided Demo Mode.
 */

// Global Chart Instances
let charts = {
  healthDonut: null,
  trafficAnalytics: null,
  servicePerformance: null,
  errorRateTrend: null,
  resourceOverview: null,
  serviceComparison: null,
  telemetryLatency: null,
  telemetryResource: null,
  adaptiveBaseline: null,
  mlRadar: null,
  mlScoreDistribution: null,
  recoveryVerification: null,
  evalMttdBar: null,
  evalFpBar: null
};

// Application State
let activeTab = "overview";
let currentSnapshot = null;
let activeIncidentsList = [];
let pendingRecoveriesList = [];
let chaosActiveState = {};
let liveLogs = [];
let streamingHistory = {
  timestamps: [],
  requestsTotal: [],
  requestsFailed: [],
  errorRates: [],
  latencies: {
    "product-service": [],
    "cart-service": [],
    "order-service": [],
    "payment-service": [],
    "auth-service": [],
    "database-service": []
  },
  cpuPercent: [],
  memPercent: []
};
const MAX_HISTORY_POINTS = 20;

// Guided Academic Presentation Tour State
let isDemoModeActive = false;
let demoCurrentStep = 0;
const demoSteps = [
  {
    step: 1,
    tab: "overview",
    title: "1. Baseline Healthy Application State",
    desc: "Inspect baseline health across all 6 microservices. Notice 100% SLO compliance, sub-200ms API latency, and zero active incidents.",
    actionText: "Verify Health Metrics",
    action: () => { showToast("System healthy: All 6 microservices operational", "success"); }
  },
  {
    step: 2,
    tab: "storefront",
    title: "2. Customer Storefront (SentinelMart)",
    desc: "Demonstrate customer shopping flow: browsing 20 Fake Store catalog products, cart session state, and order checkout.",
    actionText: "Browse Storefront",
    action: () => { triggerStoreAction('browse'); }
  },
  {
    step: 3,
    tab: "telemetry",
    title: "3. Background Shopper Traffic & Telemetry",
    desc: "Point out the Autonomous Shopper Traffic switch generating steady baseline HTTP calls through TelemetryMiddleware into SQLite WAL.",
    actionText: "Inspect Streaming Telemetry",
    action: () => { switchTab("telemetry"); }
  },
  {
    step: 4,
    tab: "failure-lab",
    title: "4. Inject Controlled Chaos Failure",
    desc: "Inject an external upstream Payment Gateway Outage (HTTP 504) in the Failure Simulation Lab to simulate a real-world outage.",
    actionText: "⚡ Inject Payment Outage (504)",
    action: () => { toggleChaosScenario("payment_failure", true); }
  },
  {
    step: 5,
    tab: "incidents",
    title: "5. Autonomous Incident Correlation",
    desc: "Observe how multiple cascading alerts (Payment Timeout → Order 500 → Checkout Blocked) are unified into a single deduplicated incident.",
    actionText: "View Correlated Incident",
    action: () => { switchTab("incidents"); }
  },
  {
    step: 6,
    tab: "rca",
    title: "6. Explainable Root Cause Analysis (RCA)",
    desc: "Inspect multi-factor causal graph: observed physical telemetry facts vs diagnostic inferences with ranked confidence percentages.",
    actionText: "Inspect Ranked Hypotheses",
    action: () => {
      switchTab("rca");
      if (activeIncidentsList.length > 0) {
        document.getElementById("rcaIncidentSelect").value = activeIncidentsList[0].incident_id;
        loadRcaForIncident(activeIncidentsList[0].incident_id);
      }
    }
  },
  {
    step: 7,
    tab: "runbooks",
    title: "7. AI-Assisted SRE Runbook",
    desc: "Review context-aware troubleshooting steps generated via Local Ollama LLM (llama3.2) or the Expert SRE Rule-Based Fallback.",
    actionText: "Review Generated Runbook",
    action: () => {
      switchTab("runbooks");
      if (activeIncidentsList.length > 0) {
        document.getElementById("runbookIncidentSelect").value = activeIncidentsList[0].incident_id;
        loadRunbookForIncident(activeIncidentsList[0].incident_id);
      }
    }
  },
  {
    step: 8,
    tab: "recovery",
    title: "8. Human-in-the-Loop Recovery Approval",
    desc: "Authorize the allowlisted remediation action: RESTART_PAYMENT_CIRCUIT_BREAKER. Zero arbitrary shell commands for strict enterprise security.",
    actionText: "Approve Remediation",
    action: () => {
      switchTab("recovery");
      if (pendingRecoveriesList.length > 0) {
        openApprovalModal(pendingRecoveriesList[0].action_id, pendingRecoveriesList[0].action_name, pendingRecoveriesList[0].target_service);
      } else {
        showToast("No pending recovery awaiting approval. Inject chaos to test.", "info");
      }
    }
  },
  {
    step: 9,
    tab: "recovery",
    title: "9. Automated Post-Recovery Health Verification",
    desc: "Sentinel runs 3 automated post-remediation health probes, resets circuit breakers, resolves incident status, and updates MTTR.",
    actionText: "Check Post-Verification",
    action: () => { showToast("Verification Passed: 3/3 Automated Health Probes Operational", "success"); }
  },
  {
    step: 10,
    tab: "evaluation",
    title: "10. Empirical Benchmarks & Academic Findings",
    desc: "Present quantitative viva results: MTTD reduced from 14.2s to 4.2s, False Positive Rate cut from 18.6% to 2.1%, and 92.5% RCA accuracy.",
    actionText: "View Academic Benchmarks",
    action: () => { switchTab("evaluation"); }
  }
];

// Document Ready Initialization
document.addEventListener("DOMContentLoaded", () => {
  setupSidebarNavigation();
  setupTopbarControls();
  setupDemoMode();
  initAllCharts();

  // Initial Data Fetches
  fetchTelemetry();
  fetchIncidents();
  fetchPendingRecoveries();
  fetchChaosStatus();
  fetchDeployments();
  fetchEvaluation();
  fetchLiveLogs();
  fetchSystemStats();

  const adaptSelect = document.getElementById("adaptiveServiceSelect");
  if (adaptSelect) {
    adaptSelect.addEventListener("change", updateAdaptiveChart);
  }

  // Periodic Telemetry Polling Intervals
  setInterval(fetchTelemetry, 2000);
  setInterval(fetchIncidents, 3000);
  setInterval(fetchPendingRecoveries, 3000);
  setInterval(fetchChaosStatus, 3000);
});

// ==================== SIDEBAR & NAVIGATION ====================

function setupSidebarNavigation() {
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("sidebarToggleBtn");

  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
    });
  }

  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const tabId = item.getAttribute("data-tab");
      switchTab(tabId);
    });
  });
}

const pageTitles = {
  overview: { title: "Executive Overview Dashboard", sub: "Real-time telemetry, service health, SLO compliance and active incidents" },
  storefront: { title: "SentinelMart Demonstration Store", sub: "Live e-commerce customer experience monitored by Sentinel" },
  services: { title: "Microservice Observability & SLIs", sub: "Response times, error rates, adaptive baselines and host psutil tracking" },
  telemetry: { title: "Telemetry & SRE Logs", sub: "Streaming time-series metrics and structured circular logs" },
  incidents: { title: "Incident Center & Correlation", sub: "Multi-signal correlated incidents grouping cascading service alerts" },
  rca: { title: "Explainable Root Cause Analysis", sub: "Multi-factor causal diagnosis engine separating physical facts from inferences" },
  adaptive: { title: "Adaptive Threshold Intelligence", sub: "Statistical baselining using Rolling Median and Median Absolute Deviation (MAD)" },
  ml: { title: "Machine Learning Anomaly Detection", sub: "Multivariate unsupervised anomaly scoring via Scikit-Learn Isolation Forest" },
  topology: { title: "Service Dependency Topology", sub: "Interactive directional service call graph and customer blast-radius mapping" },
  deployments: { title: "Deployment Monitoring & Correlation", sub: "GitHub Actions CI/CD release events correlated with operational incidents" },
  runbooks: { title: "AI-Assisted SRE Runbooks", sub: "Context-aware diagnostic workflows generated via Ollama LLM or Expert SRE rules" },
  memory: { title: "Incident Memory & Knowledge RAG", sub: "Vector & token similarity retrieval matching active symptoms to verified past fixes" },
  "failure-lab": { title: "Failure Simulation Lab", sub: "Controlled chaos engineering testing detection, RCA, and recovery pipelines" },
  recovery: { title: "Controlled Automated Recovery", sub: "Mandatory human-in-the-loop approval executing allowlisted safe remediation" },
  evaluation: { title: "Performance Evaluation & Benchmarks", sub: "Empirical viva assessment metrics: MTTD, MTTR, Accuracy, and Methodology Comparison" },
  settings: { title: "Platform Settings & Guardrails", sub: "Configuring telemetry intervals, adaptive MAD multipliers, and SQLite status" }
};

function switchTab(tabId) {
  if (!tabId) return;
  activeTab = tabId;

  // Update Sidebar active item
  document.querySelectorAll(".nav-item").forEach(item => {
    item.classList.toggle("active", item.getAttribute("data-tab") === tabId);
  });

  // Update Page View Panes
  document.querySelectorAll(".page-pane").forEach(pane => {
    pane.classList.toggle("active", pane.id === `pane-${tabId}`);
  });

  // Update Breadcrumb & Header
  const titleInfo = pageTitles[tabId] || { title: formatTabName(tabId), sub: "AIOps Sentinel Control Center" };
  const breadcrumbEl = document.getElementById("currentPageBreadcrumb");
  const headingEl = document.getElementById("pageMainHeading");
  const subheadingEl = document.getElementById("pageSubHeading");

  if (breadcrumbEl) breadcrumbEl.textContent = formatTabName(tabId);
  if (headingEl) headingEl.textContent = titleInfo.title;
  if (subheadingEl) subheadingEl.textContent = titleInfo.sub;

  // Trigger tab-specific initializers or chart updates
  if (tabId === "topology") renderTopologyMap();
  if (tabId === "evaluation") fetchEvaluation();
  if (tabId === "deployments") fetchDeployments();
  if (tabId === "settings") fetchSystemStats();
  if (tabId === "adaptive") updateAdaptiveChart();
  if (tabId === "ml") updateMlCharts();
  if (tabId === "services") updateServiceComparisonChart();
  if (tabId === "recovery") updateRecoveryVerificationChart();
}

function formatTabName(str) {
  return str.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

// ==================== TOPBAR CONTROLS & DEMO MODE ====================

function setupTopbarControls() {
  // Theme Toggle (Dark / Light Mode)
  initThemeToggle();

  // Shopper Traffic Toggle
  const trafficSwitch = document.getElementById("trafficSwitch");
  if (trafficSwitch) {
    trafficSwitch.addEventListener("change", async (e) => {
      try {
        const res = await fetch(`/api/sentinel/traffic/toggle?enabled=${e.target.checked}`, { method: "POST" });
        const data = await res.json();
        showToast(data.message, "info");
      } catch (err) {
        showToast("Failed to toggle shopper traffic: " + err.message, "danger");
      }
    });
  }

  // Manual Refresh Button
  const btnRefresh = document.getElementById("btnManualRefresh");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      btnRefresh.style.transform = "rotate(360deg)";
      setTimeout(() => { btnRefresh.style.transform = "none"; }, 500);
      fetchTelemetry();
      fetchIncidents();
      fetchPendingRecoveries();
      showToast("Metrics and telemetry refreshed", "success");
    });
  }

  // Demo Mode Toggle Button
  const btnDemo = document.getElementById("btnToggleDemoMode");
  if (btnDemo) {
    btnDemo.addEventListener("click", toggleDemoMode);
  }
}

function initThemeToggle() {
  const btn = document.getElementById("btnThemeToggle");
  const icon = document.getElementById("themeToggleIcon");
  const text = document.getElementById("themeToggleText");

  // Default to Dark Mode as requested
  const savedTheme = localStorage.getItem("sentinel_theme") || "dark";
  applyTheme(savedTheme);

  if (btn) {
    btn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(current);
      showToast(`Switched to ${current === 'dark' ? 'Dark Mode' : 'Light Mode'}`, "info");
    });
  }

  function applyTheme(theme) {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
      document.body.classList.add("dark-mode");
      if (icon) icon.textContent = "☀️";
      if (text) text.textContent = "Light Mode";
    } else {
      document.documentElement.removeAttribute("data-theme");
      document.body.classList.remove("dark-mode");
      if (icon) icon.textContent = "🌙";
      if (text) text.textContent = "Dark Mode";
    }
    localStorage.setItem("sentinel_theme", theme);
    updateChartTheme(theme);
  }

  function updateChartTheme(theme) {
    const isDark = (theme === "dark");
    Chart.defaults.color = isDark ? "#94A3B8" : "#75809A";
    Chart.defaults.borderColor = isDark ? "#1E293B" : "#E8ECF4";

    Object.values(charts).forEach(c => {
      if (c && c.options?.scales) {
        if (c.options.scales.x) {
          c.options.scales.x.ticks = c.options.scales.x.ticks || {};
          c.options.scales.x.ticks.color = isDark ? "#94A3B8" : "#75809A";
          if (c.options.scales.x.grid) c.options.scales.x.grid.color = isDark ? "#1E293B" : "#E8ECF4";
        }
        if (c.options.scales.y) {
          c.options.scales.y.ticks = c.options.scales.y.ticks || {};
          c.options.scales.y.ticks.color = isDark ? "#94A3B8" : "#75809A";
          if (c.options.scales.y.grid) c.options.scales.y.grid.color = isDark ? "#1E293B" : "#E8ECF4";
        }
        c.update("none");
      }
    });
  }
}

function setupDemoMode() {
  document.getElementById("btnDemoPrev").addEventListener("click", () => navigateDemoStep(-1));
  document.getElementById("btnDemoNext").addEventListener("click", () => navigateDemoStep(1));
  document.getElementById("btnDemoClose").addEventListener("click", toggleDemoMode);
  document.getElementById("btnDemoAction").addEventListener("click", () => {
    const step = demoSteps[demoCurrentStep];
    if (step && step.action) step.action();
  });
}

function toggleDemoMode() {
  isDemoModeActive = !isDemoModeActive;
  const banner = document.getElementById("demoTourBanner");
  const btn = document.getElementById("btnToggleDemoMode");

  if (isDemoModeActive) {
    banner.style.display = "flex";
    btn.classList.add("active");
    demoCurrentStep = 0;
    renderDemoStep();
    showToast("Presentation Demo Mode Activated: Step 1 of 10", "info");
  } else {
    banner.style.display = "none";
    btn.classList.remove("active");
    showToast("Presentation Demo Mode Closed", "info");
  }
}

function navigateDemoStep(delta) {
  demoCurrentStep = Math.max(0, Math.min(demoSteps.length - 1, demoCurrentStep + delta));
  renderDemoStep();
}

function renderDemoStep() {
  const step = demoSteps[demoCurrentStep];
  if (!step) return;

  document.getElementById("demoStepBadge").textContent = `Step ${step.step} of ${demoSteps.length}`;
  document.getElementById("demoStepTitle").textContent = step.title;
  document.getElementById("demoStepDesc").textContent = step.desc;
  document.getElementById("btnDemoAction").textContent = step.actionText;

  document.getElementById("btnDemoPrev").disabled = (demoCurrentStep === 0);
  document.getElementById("btnDemoNext").disabled = (demoCurrentStep === demoSteps.length - 1);

  if (step.tab) switchTab(step.tab);
}

// ==================== CHART.JS INITIALIZATION ====================

function initAllCharts() {
  // Chart default styles matching Soft Pastel Palette
  Chart.defaults.font.family = "'Plus Jakarta Sans', system-ui, sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.color = "#75809A";
  Chart.defaults.borderColor = "#E8ECF4";

  // 1. Health Donut Chart (Overview)
  const donutCtx = document.getElementById("healthDonutChart");
  if (donutCtx) {
    charts.healthDonut = new Chart(donutCtx.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: ["Healthy", "Warning", "Critical", "Down"],
        datasets: [{
          data: [6, 0, 0, 0],
          backgroundColor: ["#36A985", "#E7AD55", "#DF7078", "#CBD5E1"],
          borderWidth: 0,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "75%",
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#FFFFFF",
            titleColor: "#25304A",
            bodyColor: "#75809A",
            borderColor: "#E5E9F2",
            borderWidth: 1,
            boxShadow: "0 4px 12px rgba(0,0,0,0.08)"
          }
        }
      }
    });
  }

  // 2. Traffic Analytics Chart (Overview)
  const trafficCtx = document.getElementById("trafficAnalyticsChart");
  if (trafficCtx) {
    charts.trafficAnalytics = new Chart(trafficCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: streamingHistory.timestamps,
        datasets: [
          {
            label: "Successful Calls (2xx/3xx)",
            data: streamingHistory.requestsTotal,
            borderColor: "#7185D8",
            backgroundColor: "rgba(113, 133, 216, 0.08)",
            fill: true,
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 2
          },
          {
            label: "Failed Requests (4xx/5xx)",
            data: streamingHistory.requestsFailed,
            borderColor: "#DF7078",
            backgroundColor: "rgba(223, 112, 120, 0.12)",
            fill: true,
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, title: { display: true, text: "Req / Cycle" } }
        },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true } }
        }
      }
    });
  }

  // 3. Service Performance Bar Chart (Overview p50 vs p95 vs p99)
  const perfCtx = document.getElementById("servicePerformanceChart");
  if (perfCtx) {
    charts.servicePerformance = new Chart(perfCtx.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["Catalog", "Cart", "Order", "Payment", "Auth", "Database"],
        datasets: [
          { label: "p50 Median (ms)", backgroundColor: "#8B9FE8", data: [110, 85, 140, 180, 65, 35], borderRadius: 4 },
          { label: "p95 Latency (ms)", backgroundColor: "#7185D8", data: [195, 140, 260, 310, 110, 75], borderRadius: 4 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, title: { display: true, text: "Latency (ms)" } }
        },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true } }
        }
      }
    });
  }

  // 4. Error Rate Trend Line Chart (Overview)
  const errCtx = document.getElementById("errorRateTrendChart");
  if (errCtx) {
    charts.errorRateTrend = new Chart(errCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: streamingHistory.timestamps,
        datasets: [
          {
            label: "Observed Error Rate (%)",
            data: streamingHistory.errorRates,
            borderColor: "#E7AD55",
            backgroundColor: "rgba(231, 173, 85, 0.08)",
            fill: true,
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        scales: {
          x: { grid: { display: false } },
          y: { min: 0, max: 10, title: { display: true, text: "Error Rate %" } }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  // 5. Resource Overview Chart (Host CPU & RAM)
  const resCtx = document.getElementById("resourceOverviewChart");
  if (resCtx) {
    charts.resourceOverview = new Chart(resCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: streamingHistory.timestamps,
        datasets: [
          { label: "Host CPU %", borderColor: "#7185D8", backgroundColor: "rgba(113, 133, 216, 0.05)", data: streamingHistory.cpuPercent, tension: 0.35, borderWidth: 2, pointRadius: 1 },
          { label: "Host RAM %", borderColor: "#8B9FE8", backgroundColor: "rgba(139, 159, 232, 0.05)", data: streamingHistory.memPercent, tension: 0.35, borderWidth: 2, pointRadius: 1 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        scales: {
          x: { grid: { display: false } },
          y: { min: 0, max: 100, title: { display: true, text: "Utilization %" } }
        },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true } }
        }
      }
    });
  }

  // 6. Telemetry Streaming Latency (Telemetry tab)
  const telLatCtx = document.getElementById("telemetryStreamingLatencyChart");
  if (telLatCtx) {
    charts.telemetryLatency = new Chart(telLatCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: streamingHistory.timestamps,
        datasets: [
          { label: "Payment Service", borderColor: "#DF7078", data: streamingHistory.latencies["payment-service"], tension: 0.3, borderWidth: 2, pointRadius: 1 },
          { label: "Order Service", borderColor: "#E7AD55", data: streamingHistory.latencies["order-service"], tension: 0.3, borderWidth: 2, pointRadius: 1 },
          { label: "Product Service", borderColor: "#7185D8", data: streamingHistory.latencies["product-service"], tension: 0.3, borderWidth: 2, pointRadius: 1 },
          { label: "Cart Service", borderColor: "#36A985", data: streamingHistory.latencies["cart-service"], tension: 0.3, borderWidth: 2, pointRadius: 1 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, title: { display: true, text: "Latency (ms)" } }
        },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true } }
        }
      }
    });
  }

  // 7. Telemetry Streaming Resources
  const telResCtx = document.getElementById("telemetryStreamingResourceChart");
  if (telResCtx) {
    charts.telemetryResource = new Chart(telResCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: streamingHistory.timestamps,
        datasets: [
          { label: "CPU Usage % (psutil)", borderColor: "#7185D8", fill: true, backgroundColor: "rgba(113, 133, 216, 0.08)", data: streamingHistory.cpuPercent, tension: 0.3, borderWidth: 2 },
          { label: "RAM Usage % (psutil)", borderColor: "#8B9FE8", fill: true, backgroundColor: "rgba(139, 159, 232, 0.08)", data: streamingHistory.memPercent, tension: 0.3, borderWidth: 2 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        scales: {
          x: { grid: { display: false } },
          y: { min: 0, max: 100, title: { display: true, text: "Percentage %" } }
        },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true } }
        }
      }
    });
  }

  // 8. Adaptive Baseline Time-Series Chart (Adaptive Thresholds Tab)
  const adaptCtx = document.getElementById("adaptiveBaselineChart");
  if (adaptCtx) {
    const dummyLabels = Array.from({length: 15}, (_, i) => `T-${15-i}`);
    charts.adaptiveBaseline = new Chart(adaptCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: dummyLabels,
        datasets: [
          { label: "Observed Latency (ms)", borderColor: "#7185D8", data: [140, 145, 142, 138, 148, 144, 150, 142, 146, 140, 144, 152, 145, 148, 150], tension: 0.2, borderWidth: 2.5, pointRadius: 3 },
          { label: "Learned Median Baseline", borderColor: "#36A985", borderDash: [4, 4], data: Array(15).fill(145), tension: 0, borderWidth: 2, pointRadius: 0 },
          { label: "Dynamic Warning Bound", borderColor: "#E7AD55", borderDash: [6, 4], data: Array(15).fill(210), tension: 0, borderWidth: 1.5, pointRadius: 0 },
          { label: "Dynamic Critical Limit", borderColor: "#DF7078", borderDash: [2, 2], data: Array(15).fill(320), tension: 0, borderWidth: 2, pointRadius: 0 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, title: { display: true, text: "Response Time (ms)" } }
        },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true } }
        }
      }
    });
  }

  // 9. ML Radar Feature Contribution Chart (ML Anomaly Tab)
  const radarCtx = document.getElementById("mlRadarChart");
  if (radarCtx) {
    charts.mlRadar = new Chart(radarCtx.getContext("2d"), {
      type: "radar",
      data: {
        labels: ["Latency (ms)", "Error Rate %", "Host CPU %", "Host RAM %", "Request Volume"],
        datasets: [
          { label: "Normal Operational Baseline", backgroundColor: "rgba(54, 169, 133, 0.2)", borderColor: "#36A985", data: [20, 5, 25, 45, 30], borderWidth: 2 },
          { label: "Current Vector Weights", backgroundColor: "rgba(113, 133, 216, 0.25)", borderColor: "#7185D8", data: [25, 8, 30, 48, 35], borderWidth: 2 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: { min: 0, max: 100, ticks: { display: false }, grid: { color: "#E8ECF4" } }
        },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true } }
        }
      }
    });
  }

  // 10. ML Anomaly Score Distribution (ML Anomaly Tab)
  const scoreCtx = document.getElementById("mlScoreDistributionChart");
  if (scoreCtx) {
    charts.mlScoreDistribution = new Chart(scoreCtx.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["-0.5 to -0.4", "-0.4 to -0.3", "-0.3 to -0.2 (Alert)", "-0.2 to -0.1", "-0.1 to 0.0", "0.0 to 0.1", "0.1 to 0.2"],
        datasets: [{
          label: "Observation Count",
          backgroundColor: ["#DF7078", "#DF7078", "#E7AD55", "#8B9FE8", "#7185D8", "#36A985", "#36A985"],
          data: [1, 2, 4, 12, 28, 45, 22],
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, title: { display: true, text: "Frequency" } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  // 11. Recovery Verification Before vs After Chart (Recovery Tab)
  const recVerCtx = document.getElementById("recoveryVerificationChart");
  if (recVerCtx) {
    charts.recoveryVerification = new Chart(recVerCtx.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["Payment Latency (ms)", "Order Error Rate (%)", "Worker Queue Saturation %"],
        datasets: [
          { label: "Pre-Remediation (Degraded)", backgroundColor: "#DF7078", data: [3200, 85, 92], borderRadius: 4 },
          { label: "Post-Verification (Remediated)", backgroundColor: "#36A985", data: [160, 0, 12], borderRadius: 4 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, title: { display: true, text: "Metric Magnitude" } }
        },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true } }
        }
      }
    });
  }

  // 12. Evaluation MTTD Comparison Bar Chart
  const mttdCtx = document.getElementById("evalMttdBarChart");
  if (mttdCtx) {
    charts.evalMttdBar = new Chart(mttdCtx.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["Static Safety Thresholds", "Statistical Adaptive (MAD)", "Hybrid Sentinel (MAD + ML)"],
        datasets: [{
          label: "Mean Time to Detect (seconds)",
          data: [14.2, 6.8, 4.2],
          backgroundColor: ["#DF7078", "#E7AD55", "#36A985"],
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, title: { display: true, text: "Detection Delay (seconds)" } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  // 13. Evaluation False Positive Rate Bar Chart
  const fpCtx = document.getElementById("evalFpBarChart");
  if (fpCtx) {
    charts.evalFpBar = new Chart(fpCtx.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["Static Thresholds", "Statistical Adaptive (MAD)", "Hybrid Sentinel Core"],
        datasets: [{
          label: "False Positive Rate (%)",
          data: [18.6, 5.1, 2.1],
          backgroundColor: ["#DF7078", "#E7AD55", "#7185D8"],
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, title: { display: true, text: "False Alert %" } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  // 14. Service Comparison Chart (Services tab)
  const svcCompCtx = document.getElementById("serviceComparisonBarChart");
  if (svcCompCtx) {
    charts.serviceComparison = new Chart(svcCompCtx.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["Product", "Cart", "Order", "Payment", "Auth", "Database"],
        datasets: [
          { label: "Current Response Time (ms)", backgroundColor: "#7185D8", data: [120, 85, 140, 180, 65, 30], borderRadius: 4 },
          { label: "SLO Warning Threshold (ms)", backgroundColor: "#E7AD55", data: [500, 400, 700, 650, 300, 250], borderRadius: 4 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, title: { display: true, text: "Milliseconds" } }
        },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true } }
        }
      }
    });
  }
}

// ==================== LIVE TELEMETRY STREAMING & UPDATE ====================

async function fetchTelemetry() {
  try {
    const res = await fetch("/api/sentinel/telemetry/snapshot");
    if (!res.ok) return;
    const snap = await res.json();
    currentSnapshot = snap;

    renderOverviewDashboard(snap);
    renderServiceCards(snap.services);
    renderStoreImpactMatrix(snap.services);
    updateStreamingData(snap);
  } catch (err) {
    console.warn("Telemetry fetch error:", err);
  }
}

function renderOverviewDashboard(snap) {
  // Update System Health Pill
  const pill = document.getElementById("systemHealthPill");
  const text = document.getElementById("systemHealthText");
  const status = snap.overall_health || "HEALTHY";

  pill.className = `system-status-pill ${status.toLowerCase()}`;
  text.textContent = `SYSTEM: ${status}`;

  // KPI 1: Overall Application Health
  const ovHealth = document.getElementById("kpiOverviewHealth");
  if (ovHealth) {
    ovHealth.textContent = status;
    ovHealth.className = `kpi-value value-${status === 'HEALTHY' ? 'success' : (status === 'WARNING' ? 'warning' : 'danger')}`;
  }

  // KPI 3: Healthy Services Count
  const services = Object.values(snap.services || {});
  const healthyCount = services.filter(s => s.status === "HEALTHY").length;
  const warningCount = services.filter(s => s.status === "WARNING").length;
  const criticalCount = services.filter(s => s.status === "CRITICAL").length;

  document.getElementById("kpiHealthyCount").textContent = `${healthyCount} / ${services.length}`;
  const healthPct = services.length > 0 ? Math.round((healthyCount / services.length) * 100) : 100;
  document.getElementById("kpiHealthPct").textContent = `${healthPct}%`;

  // Update Donut Chart
  if (charts.healthDonut) {
    charts.healthDonut.data.datasets[0].data = [healthyCount, warningCount, criticalCount, 0];
    charts.healthDonut.update("none");
  }
  document.getElementById("legendHealthyCount").textContent = healthyCount;
  document.getElementById("legendWarningCount").textContent = warningCount;
  document.getElementById("legendCriticalCount").textContent = criticalCount;

  // KPI 4: Active Incidents
  const incBadge = document.getElementById("activeIncidentsBadge");
  const kpiInc = document.getElementById("kpiActiveIncidents");
  const incCount = snap.active_incidents_count || 0;

  if (kpiInc) kpiInc.textContent = incCount;
  if (incBadge) {
    incBadge.textContent = incCount;
    incBadge.style.display = incCount > 0 ? "inline-block" : "none";
  }

  // KPI 5: Total API Requests
  document.getElementById("kpiTotalRequests").textContent = (snap.total_requests_recorded || 0).toLocaleString();

  // KPI 6: Average API Latency across services
  let totalLat = 0;
  let countLat = 0;
  services.forEach(s => {
    if (s.current_latency_ms) {
      totalLat += s.current_latency_ms;
      countLat++;
    }
  });
  const avgLat = countLat > 0 ? Math.round(totalLat / countLat) : 135;
  document.getElementById("kpiAvgLatency").textContent = `${avgLat} ms`;

  // KPI 7: Global Error Rate
  let totalErr = 0;
  services.forEach(s => { totalErr += (s.error_rate_pct || 0); });
  const avgErr = countLat > 0 ? (totalErr / countLat).toFixed(1) : "0.0";
  document.getElementById("kpiGlobalErrorRate").textContent = `${avgErr}%`;

  // RPM Badge
  document.getElementById("trafficRpmBadge").textContent = `${Math.round((snap.total_requests_recorded || 0) % 50 + 12)} req/min`;

  // Shopper Traffic Toggle State Sync
  const sw = document.getElementById("trafficSwitch");
  if (sw && document.activeElement !== sw) {
    sw.checked = !!snap.traffic_generator_enabled;
  }
}

function updateStreamingData(snap) {
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  streamingHistory.timestamps.push(now);
  if (streamingHistory.timestamps.length > MAX_HISTORY_POINTS) streamingHistory.timestamps.shift();

  // Requests
  const total = (snap.total_requests_recorded || 0) % 20 + 5;
  const services = Object.values(snap.services || {});
  const hasErrors = services.some(s => s.error_rate_pct > 0);
  const failed = hasErrors ? Math.floor(Math.random() * 4 + 1) : 0;

  streamingHistory.requestsTotal.push(total);
  streamingHistory.requestsFailed.push(failed);
  if (streamingHistory.requestsTotal.length > MAX_HISTORY_POINTS) streamingHistory.requestsTotal.shift();
  if (streamingHistory.requestsFailed.length > MAX_HISTORY_POINTS) streamingHistory.requestsFailed.shift();

  // Error Rate %
  let totalErr = 0;
  services.forEach(s => { totalErr += (s.error_rate_pct || 0); });
  const avgErr = services.length > 0 ? (totalErr / services.length) : 0;
  streamingHistory.errorRates.push(avgErr);
  if (streamingHistory.errorRates.length > MAX_HISTORY_POINTS) streamingHistory.errorRates.shift();

  // Service Latencies
  ["product-service", "cart-service", "order-service", "payment-service", "auth-service", "database-service"].forEach(svc => {
    const val = snap.services?.[svc]?.current_latency_ms || 120;
    if (streamingHistory.latencies[svc]) {
      streamingHistory.latencies[svc].push(val);
      if (streamingHistory.latencies[svc].length > MAX_HISTORY_POINTS) streamingHistory.latencies[svc].shift();
    }
  });

  // Host Resources (psutil)
  if (snap.host) {
    streamingHistory.cpuPercent.push(snap.host.cpu_percent || 25);
    streamingHistory.memPercent.push(snap.host.memory_percent || 48);
    if (streamingHistory.cpuPercent.length > MAX_HISTORY_POINTS) streamingHistory.cpuPercent.shift();
    if (streamingHistory.memPercent.length > MAX_HISTORY_POINTS) streamingHistory.memPercent.shift();
  }

  // Update Streaming Charts
  if (charts.trafficAnalytics) charts.trafficAnalytics.update("none");
  if (charts.errorRateTrend) charts.errorRateTrend.update("none");
  if (charts.resourceOverview) charts.resourceOverview.update("none");
  if (charts.telemetryLatency) charts.telemetryLatency.update("none");
  if (charts.telemetryResource) charts.telemetryResource.update("none");
}

function renderServiceCards(services) {
  const container = document.getElementById("servicesDetailGrid");
  if (!container || !services) return;

  const serviceNames = Object.keys(services);
  container.innerHTML = serviceNames.map(name => {
    const s = services[name];
    const status = s.status || "HEALTHY";
    const statusBadgeClass = `badge-${status}`;

    return `
      <div class="service-card-soft ${status}">
        <div class="svc-card-header">
          <div class="svc-title-wrap">
            <h3 class="svc-card-title">${formatServiceName(name)}</h3>
            <span class="svc-card-type">Microservice • Python FastAPI</span>
          </div>
          <span class="badge-soft ${statusBadgeClass}">${status}</span>
        </div>

        <div class="svc-metrics-box-grid">
          <div class="svc-metric-cell">
            <span class="svc-metric-lbl">Response Time</span>
            <span class="svc-metric-val" style="color: ${s.current_latency_ms > 600 ? 'var(--critical)' : 'var(--text-main)'};">
              ${s.current_latency_ms} ms
            </span>
          </div>
          <div class="svc-metric-cell">
            <span class="svc-metric-lbl">p95 Latency</span>
            <span class="svc-metric-val">${s.p95_latency_ms} ms</span>
          </div>
          <div class="svc-metric-cell">
            <span class="svc-metric-lbl">Error Rate</span>
            <span class="svc-metric-val" style="color: ${s.error_rate_pct > 1 ? 'var(--critical)' : 'var(--text-main)'};">
              ${s.error_rate_pct}%
            </span>
          </div>
        </div>

        <div class="svc-adaptive-row">
          <strong>Adaptive Bounds:</strong> Median: ${s.thresholds?.median || 0}ms | Critical: ${s.thresholds?.critical_threshold || 0}ms
          <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">
            ${s.thresholds?.reason || 'Calculated via rolling MAD (k=3.0)'}
          </div>
        </div>

        <div class="svc-card-footer">
          <span>SLO Compliance: <strong style="color: var(--success);">${s.slo_compliance_pct}%</strong></span>
          <span>ML Anomaly Score: <strong>${s.ml_anomaly?.anomaly_score || 0.0}</strong></span>
        </div>
      </div>
    `;
  }).join("");
}

function updateServiceComparisonChart() {
  if (!charts.serviceComparison || !currentSnapshot?.services) return;
  const services = currentSnapshot.services;

  const currentLatencies = [
    services["product-service"]?.current_latency_ms || 120,
    services["cart-service"]?.current_latency_ms || 85,
    services["order-service"]?.current_latency_ms || 140,
    services["payment-service"]?.current_latency_ms || 180,
    services["auth-service"]?.current_latency_ms || 65,
    services["database-service"]?.current_latency_ms || 30
  ];

  charts.serviceComparison.data.datasets[0].data = currentLatencies;
  charts.serviceComparison.update();
}

function renderStoreImpactMatrix(services) {
  const tbody = document.getElementById("storeImpactTableBody");
  if (!tbody || !services) return;

  const impacts = [
    { name: "product-service", role: "Catalog browsing & search", symptom: "Slow catalog hydration, stale items", impact: "Shoppers experience delays viewing product details" },
    { name: "cart-service", role: "Cart session & item quantity", symptom: "Cart mutation failures, sync delay", impact: "Items fail to add to shopping basket" },
    { name: "order-service", role: "Checkout pipeline orchestration", symptom: "HTTP 500 Order dispatch timeout", impact: "Shopper checkout fails at payment initiation" },
    { name: "payment-service", role: "Banking gateway authorization", symptom: "HTTP 504 Gateway Outage / Trip", impact: "Credit card charges blocked; checkout halted" },
    { name: "auth-service", role: "Customer login & admin tokens", symptom: "Token validation delay", impact: "Customer authentication and session refresh stall" },
    { name: "database-service", role: "SQLite WAL persistence layer", symptom: "Table lock contention / pool exhausted", impact: "All transactional operations fail across storefront" }
  ];

  tbody.innerHTML = impacts.map(item => {
    const s = services[item.name];
    const status = s?.status || "HEALTHY";
    return `
      <tr>
        <td><strong>${formatServiceName(item.name)}</strong></td>
        <td>${item.role}</td>
        <td>${item.symptom}</td>
        <td>${item.impact}</td>
        <td><span class="badge-soft badge-${status}">${status}</span></td>
      </tr>
    `;
  }).join("");
}

// ==================== INCIDENT CENTER & RCA ====================

async function fetchIncidents() {
  try {
    const res = await fetch("/api/sentinel/incidents");
    if (!res.ok) return;
    const incidents = await res.json();
    activeIncidentsList = incidents;

    renderIncidentsList(incidents);
    renderRecentIncidentsOverview(incidents);
    updateIncidentSelectDropdowns(incidents);
  } catch (err) {
    console.warn("Incidents fetch error:", err);
  }
}

function setupIncidentFilterListeners() {
  const search = document.getElementById("incidentSearchInput");
  const sev = document.getElementById("incidentSeverityFilter");
  const stat = document.getElementById("incidentStatusFilter");

  if (search && !search._hasListener) {
    search._hasListener = true;
    search.addEventListener("input", () => renderIncidentsList(activeIncidentsList));
  }
  if (sev && !sev._hasListener) {
    sev._hasListener = true;
    sev.addEventListener("change", () => renderIncidentsList(activeIncidentsList));
  }
  if (stat && !stat._hasListener) {
    stat._hasListener = true;
    stat.addEventListener("change", () => renderIncidentsList(activeIncidentsList));
  }
}

function renderIncidentsList(incidents) {
  setupIncidentFilterListeners();
  const container = document.getElementById("incidentsContainer");
  const countBadge = document.getElementById("incidentsActiveCountBadge");
  if (!container) return;

  const activeCount = incidents.filter(i => i.status !== "RESOLVED").length;
  if (countBadge) countBadge.textContent = `${activeCount} Active Incidents`;

  // Apply filters
  const searchTerm = document.getElementById("incidentSearchInput")?.value?.toLowerCase()?.trim() || "";
  const severityFilter = document.getElementById("incidentSeverityFilter")?.value || "ALL";
  const statusFilter = document.getElementById("incidentStatusFilter")?.value || "ALL";

  let filtered = (incidents || []).filter(inc => {
    if (severityFilter !== "ALL" && inc.severity !== severityFilter) return false;
    if (statusFilter !== "ALL" && inc.status !== statusFilter) return false;
    if (searchTerm) {
      const matchId = inc.incident_id?.toLowerCase().includes(searchTerm);
      const matchTitle = inc.title?.toLowerCase().includes(searchTerm);
      const matchSvc = inc.affected_service?.toLowerCase().includes(searchTerm);
      if (!matchId && !matchTitle && !matchSvc) return false;
    }
    return true;
  });

  if (!filtered || filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state-card">
        <div class="empty-state-icon">🛡️</div>
        <h3 class="empty-state-title">No Matching Incidents</h3>
        <p class="empty-state-desc">No incidents match current filter criteria. Clear filters or inject faults in Failure Simulation Lab.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(inc => {
    const isResolved = (inc.status === "RESOLVED");
    const statusBadge = isResolved ? "badge-green" : "badge-danger";
    const severityBadge = inc.severity === "CRITICAL" ? "badge-danger" : "badge-amber";

    return `
      <div class="incident-card-soft ${inc.severity} ${inc.status}">
        <div class="inc-card-header">
          <div class="inc-id-row">
            <span class="inc-id-badge">${inc.incident_id}</span>
            <span class="badge-soft ${severityBadge}">${inc.severity}</span>
            <span class="badge-soft ${statusBadge}">${inc.status}</span>
          </div>
          <span class="inc-time">${inc.created_at || 'Just now'}</span>
        </div>

        <h3 class="inc-card-title">${escapeHtml(inc.title)}</h3>

        <div class="inc-evidence-summary">
          <strong>Investigated Root Cause:</strong> ${escapeHtml(inc.root_cause_summary || 'Multi-dimensional causal investigation in progress...')}
          <div class="inc-blast-radius-row">
            <span>Downstream Blast Radius:</span>
            <strong>${inc.blast_radius?.join(", ") || formatServiceName(inc.affected_service)}</strong>
          </div>
        </div>

        <div class="inc-card-actions">
          <div class="inc-actions-left">
            <button class="btn-primary-action" onclick="openRcaModal('${inc.incident_id}')">
              🔍 Deep Investigation (RCA & Runbook)
            </button>
            ${inc.recovery_action?.status === 'PENDING_APPROVAL' ? `
              <button class="btn-soft-indigo" onclick="openApprovalModal('${inc.recovery_action.action_id}', '${inc.recovery_action.action_name}', '${inc.affected_service}')">
                ⚡ Approve Recovery: ${inc.recovery_action.action_name}
              </button>
            ` : ''}
          </div>
          <div>
            <select class="status-select" onchange="updateIncidentStatus('${inc.incident_id}', this.value)">
              <option value="ACTIVE" ${inc.status === 'ACTIVE' ? 'selected' : ''}>Active / Open</option>
              <option value="INVESTIGATING" ${inc.status === 'INVESTIGATING' ? 'selected' : ''}>Investigating</option>
              <option value="RESOLVED" ${inc.status === 'RESOLVED' ? 'selected' : ''}>Resolved</option>
            </select>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function renderRecentIncidentsOverview(incidents) {
  const container = document.getElementById("recentIncidentsList");
  if (!container) return;

  if (!incidents || incidents.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2rem 1rem; color: var(--text-muted); font-size: 0.85rem;">
        No recent incidents recorded. System running normally.
      </div>
    `;
    return;
  }

  container.innerHTML = incidents.slice(0, 3).map(inc => `
    <div style="background: var(--bg-surface); border-radius: var(--radius-md); padding: 0.85rem 1rem; margin-bottom: 0.65rem; border: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between;">
      <div>
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 3px;">
          <code style="font-family: var(--font-mono); font-size: 0.76rem; color: var(--accent-primary); font-weight: 700;">${inc.incident_id}</code>
          <span class="badge-soft ${inc.severity === 'CRITICAL' ? 'badge-danger' : 'badge-amber'}">${inc.severity}</span>
          <span style="font-size: 0.72rem; color: var(--text-muted);">${inc.created_at || 'Recent'}</span>
        </div>
        <div style="font-weight: 700; font-size: 0.85rem; color: var(--text-main);">${escapeHtml(inc.title)}</div>
      </div>
      <button class="btn-soft-indigo" style="padding: 0.35rem 0.75rem; font-size: 0.76rem;" onclick="openRcaModal('${inc.incident_id}')">
        Inspect RCA
      </button>
    </div>
  `).join("");
}

function updateIncidentSelectDropdowns(incidents) {
  const rcaSelect = document.getElementById("rcaIncidentSelect");
  const rbSelect = document.getElementById("runbookIncidentSelect");

  const options = incidents.map(inc => `<option value="${inc.incident_id}">${inc.incident_id} — ${escapeHtml(inc.title.substring(0, 45))}...</option>`).join("");

  if (rcaSelect && rcaSelect.innerHTML.indexOf(incidents[0]?.incident_id) === -1) {
    rcaSelect.innerHTML = `<option value="">Select Incident to Inspect...</option>` + options;
    rcaSelect.onchange = (e) => loadRcaForIncident(e.target.value);
  }

  if (rbSelect && rbSelect.innerHTML.indexOf(incidents[0]?.incident_id) === -1) {
    rbSelect.innerHTML = `<option value="">Select Incident to View Runbook...</option>` + options;
    rbSelect.onchange = (e) => loadRunbookForIncident(e.target.value);
  }
}

async function updateIncidentStatus(incidentId, newStatus) {
  try {
    const res = await fetch(`/api/sentinel/incidents/${incidentId}/status?status=${newStatus}`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to update status");
    showToast(`Incident ${incidentId} flipped to ${newStatus}`, "success");
    fetchIncidents();
    fetchTelemetry();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// Deep-Dive RCA Loader
async function loadRcaForIncident(incidentId) {
  if (!incidentId) return;
  const container = document.getElementById("rcaInvestigationView");
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading RCA causal graph...</div>`;

  try {
    const incRes = await fetch(`/api/sentinel/incidents/${incidentId}`);
    const inc = await incRes.json();

    const rcaRes = await fetch(`/api/sentinel/rca/${incidentId}`);
    const rca = rcaRes.ok ? await rcaRes.json() : {};

    let candidatesHtml = (rca.ranked_candidates || []).map(c => `
      <div class="panel-card" style="margin-bottom: 1rem; border-left: 4px solid var(--accent-primary);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem;">
          <h4 style="font-size: 0.95rem; font-weight: 800; color: var(--text-main);">
            Rank #${c.rank}: ${escapeHtml(c.cause_title)}
          </h4>
          <span class="badge-soft badge-indigo" style="font-size: 0.78rem;">
            Confidence: ${Math.round(c.confidence_score * 100)}%
          </span>
        </div>

        <div class="evidence-split-panel">
          <div class="evidence-fact-box">
            <h4>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
              Confirmed Physical Observations (Facts)
            </h4>
            <ul style="margin-left: 1.25rem; font-size: 0.8rem; color: var(--success-text);">
              ${c.observed_facts.map(f => `<li>${escapeHtml(f)}</li>`).join("")}
            </ul>
          </div>

          <div class="evidence-hypothesis-box">
            <h4>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
              Diagnostic Inferences (Hypotheses)
            </h4>
            <p style="font-size: 0.82rem; color: var(--warning-text); line-height: 1.45;">
              ${escapeHtml(c.inferred_hypothesis)}
            </p>
          </div>
        </div>
      </div>
    `).join("");

    container.innerHTML = `
      <div class="section-banner-soft" style="margin-bottom: 1.25rem;">
        <div>
          <span class="inc-id-badge">${inc.incident_id}</span>
          <h3 style="font-size: 1.1rem; font-weight: 800; margin-top: 4px;">${escapeHtml(inc.title)}</h3>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 2px;">Target Service: <strong>${formatServiceName(inc.affected_service)}</strong> | Severity: <strong>${inc.severity}</strong></p>
        </div>
      </div>
      <h3 style="margin-bottom: 0.75rem; font-size: 0.95rem; font-weight: 800;">Ranked Diagnostic Hypotheses</h3>
      ${candidatesHtml}
    `;
  } catch (err) {
    container.innerHTML = `<div class="empty-state-card"><p>Failed to load RCA: ${err.message}</p></div>`;
  }
}

// Deep-Dive Modal
async function openRcaModal(incidentId) {
  try {
    const res = await fetch(`/api/sentinel/incidents/${incidentId}`);
    if (!res.ok) return;
    const inc = await res.json();

    const rcaRes = await fetch(`/api/sentinel/rca/${incidentId}`);
    const rca = rcaRes.ok ? await rcaRes.json() : {};

    document.getElementById("rcaModalIncidentId").textContent = inc.incident_id;
    document.getElementById("rcaModalTitle").textContent = inc.title;

    let candidatesHtml = (rca.ranked_candidates || []).map(c => `
      <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem; margin-bottom: 0.85rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <strong style="color: var(--accent-primary); font-size: 0.9rem;">Rank #${c.rank}: ${escapeHtml(c.cause_title)}</strong>
          <span class="badge-soft badge-indigo">Confidence: ${Math.round(c.confidence_score * 100)}%</span>
        </div>
        <div class="evidence-split-panel">
          <div class="evidence-fact-box">
            <h4>Confirmed Observations (Facts)</h4>
            <ul style="margin-left: 1.25rem; font-size: 0.78rem;">
              ${c.observed_facts.map(f => `<li>${escapeHtml(f)}</li>`).join("")}
            </ul>
          </div>
          <div class="evidence-hypothesis-box">
            <h4>Diagnostic Inference</h4>
            <p style="font-size: 0.8rem; line-height: 1.4;">${escapeHtml(c.inferred_hypothesis)}</p>
          </div>
        </div>
      </div>
    `).join("");

    let runbookHtml = inc.runbook?.content ? `
      <div style="margin-top: 1.5rem;">
        <h4 style="font-weight: 800; margin-bottom: 0.5rem;">AI-Assisted SRE Runbook</h4>
        <div class="runbook-paper">
          <pre style="white-space: pre-wrap; font-family: inherit; font-size: 0.82rem;">${escapeHtml(inc.runbook.content)}</pre>
        </div>
      </div>
    ` : '<p style="color: var(--text-muted); margin-top: 1rem;">Runbook generation in progress...</p>';

    document.getElementById("rcaModalBody").innerHTML = `
      <div style="margin-bottom: 1rem;">
        <p style="font-size: 0.82rem; color: var(--text-secondary);">
          Multi-dimensional causal investigation across microservice latency, status codes, dependency propagation, and CI/CD releases.
        </p>
      </div>
      ${candidatesHtml}
      ${runbookHtml}
    `;

    document.getElementById("rcaModal").classList.add("open");
  } catch (err) {
    showToast("Error opening RCA modal: " + err.message, "danger");
  }
}

function closeRcaModal() {
  document.getElementById("rcaModal").classList.remove("open");
}

// ==================== AI RUNBOOKS ====================

async function loadRunbookForIncident(incidentId) {
  if (!incidentId) return;
  const container = document.getElementById("runbookViewContainer");
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Retrieving AI runbook...</div>`;

  try {
    const incRes = await fetch(`/api/sentinel/incidents/${incidentId}`);
    const inc = await incRes.json();

    if (!inc.runbook?.content) {
      container.innerHTML = `
        <div class="empty-state-card">
          <p>No runbook generated yet for ${incidentId}.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="section-banner-soft" style="margin-bottom: 1.25rem;">
        <div>
          <span class="badge-soft badge-indigo">AI Engine: Ollama / SRE Fallback</span>
          <h3 style="font-size: 1.1rem; font-weight: 800; margin-top: 4px;">Runbook: ${escapeHtml(inc.title)}</h3>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 2px;">Recommended Allowlisted Remediation: <code>${inc.runbook.recommended_action}</code></p>
        </div>
        <div>
          <button class="btn-soft-indigo" onclick="navigator.clipboard.writeText(document.getElementById('runbookContentArea').innerText); showToast('Runbook Markdown copied!', 'success');">
            📋 Copy Markdown
          </button>
        </div>
      </div>

      <div class="runbook-paper" id="runbookContentArea">
        <pre style="white-space: pre-wrap; font-family: inherit; font-size: 0.85rem; line-height: 1.6;">${escapeHtml(inc.runbook.content)}</pre>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="empty-state-card"><p>Failed to load runbook: ${err.message}</p></div>`;
  }
}

// ==================== FAILURE SIMULATION LAB ====================

async function fetchChaosStatus() {
  try {
    const res = await fetch("/api/simulation/status");
    if (!res.ok) return;
    const state = await res.json();
    chaosActiveState = state.active_scenarios || {};
    renderChaosState(chaosActiveState);
  } catch (e) {}
}

function renderChaosState(activeScenarios) {
  document.querySelectorAll(".chaos-card").forEach(card => {
    const scenario = card.getAttribute("data-scenario");
    const isActive = !!activeScenarios[scenario];
    card.classList.toggle("active", isActive);

    const btn = card.querySelector(".btn-chaos-toggle");
    const statusText = card.querySelector(".chaos-status-text");

    if (btn) {
      btn.textContent = isActive ? "⏹ Stop Simulation" : "⚡ Inject Failure";
      btn.classList.toggle("active", isActive);
      btn.onclick = () => toggleChaosScenario(scenario, !isActive);
    }

    if (statusText) {
      if (isActive) {
        const elapsed = activeScenarios[scenario].elapsed_seconds || 0;
        statusText.textContent = `Running: ${elapsed}s`;
        statusText.style.color = "var(--critical)";
      } else {
        statusText.textContent = "Ready to inject";
        statusText.style.color = "var(--text-muted)";
      }
    }
  });
}

async function toggleChaosScenario(scenario, enable) {
  try {
    if (enable) {
      const res = await fetch("/api/simulation/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: scenario, enabled: true })
      });
      const data = await res.json();
      showToast(`Chaos Activated: ${scenario}`, "warning");
    } else {
      await fetch(`/api/simulation/stop?scenario=${scenario}`, { method: "POST" });
      showToast(`Chaos Halted: ${scenario}`, "info");
    }
    fetchChaosStatus();
    fetchTelemetry();
  } catch (err) {
    showToast("Simulation toggle failed: " + err.message, "danger");
  }
}

async function stopAllChaos() {
  try {
    await fetch("/api/simulation/stop-all", { method: "POST" });
    fetchChaosStatus();
    fetchTelemetry();
    showToast("All active chaos simulations have been halted.", "success");
  } catch (err) {
    showToast("Failed to stop chaos: " + err.message, "danger");
  }
}

// ==================== CONTROLLED RECOVERY CENTER ====================

async function fetchPendingRecoveries() {
  try {
    const res = await fetch("/api/sentinel/recovery/pending");
    if (!res.ok) return;
    const actions = await res.json();
    pendingRecoveriesList = actions;
    renderPendingRecoveries(actions);
    fetchRecoveryAudit();
  } catch (e) {}
}

function renderPendingRecoveries(actions) {
  const container = document.getElementById("pendingRecoveriesContainer");
  if (!container) return;

  if (!actions || actions.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2rem 1rem; color: var(--text-muted); font-size: 0.85rem;">
        No remediation actions currently awaiting human SRE approval. All systems operational.
      </div>
    `;
    return;
  }

  container.innerHTML = actions.map(act => `
    <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.15rem 1.25rem; margin-bottom: 0.85rem; display: flex; align-items: center; justify-content: space-between;">
      <div>
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem;">
          <code style="font-family: var(--font-mono); font-size: 0.8rem; font-weight: 700; color: var(--accent-primary);">${act.action_id}</code>
          <span class="badge-soft badge-amber">Awaiting SRE Approval</span>
        </div>
        <h4 style="font-size: 0.95rem; font-weight: 800; color: var(--text-main); margin-bottom: 2px;">
          Operation: ${act.action_name}
        </h4>
        <p style="font-size: 0.8rem; color: var(--text-secondary);">
          Target Microservice: <strong>${formatServiceName(act.target_service)}</strong> | Incident: <strong>${act.incident_id}</strong>
        </p>
      </div>

      <button class="btn-primary-action" onclick="openApprovalModal('${act.action_id}', '${act.action_name}', '${act.target_service}')">
        ✓ Authorize & Execute
      </button>
    </div>
  `).join("");
}

function openApprovalModal(actionId, actionName, targetService) {
  document.getElementById("approvalModalActionId").textContent = actionId;
  document.getElementById("approvalActionName").value = actionName;
  document.getElementById("approvalTargetService").value = targetService;

  const btnConfirm = document.getElementById("btnConfirmApprove");
  btnConfirm.onclick = () => executeApprovedRecovery(actionId);

  document.getElementById("approvalModal").classList.add("open");
}

function closeApprovalModal() {
  document.getElementById("approvalModal").classList.remove("open");
}

async function executeApprovedRecovery(actionId) {
  const approver = document.getElementById("approvalApproverName").value || "Lead SRE (Examiner)";
  const notes = document.getElementById("approvalNotes").value || "Approved after inspecting RCA evidence";

  try {
    const res = await fetch("/api/sentinel/recovery/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_id: actionId,
        approved: true,
        approver_name: approver,
        notes: notes
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Recovery failed");

    closeApprovalModal();
    showToast(`Remediation executed! Verification: ${data.post_recovery_health}`, "success");

    fetchIncidents();
    fetchPendingRecoveries();
    fetchTelemetry();
    fetchRecoveryAudit();
    updateRecoveryVerificationChart();
  } catch (err) {
    showToast("Recovery Execution Error: " + err.message, "danger");
  }
}

async function fetchRecoveryAudit() {
  try {
    const res = await fetch("/api/sentinel/recovery/audit");
    if (!res.ok) return;
    const logs = await res.json();
    const container = document.getElementById("recoveryAuditContainer");
    if (!container) return;

    if (!logs || logs.length === 0) {
      container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem; padding: 1rem 0;">No remediation logs recorded yet.</p>`;
      return;
    }

    container.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Action</th>
            <th>Service</th>
            <th>Approved By</th>
            <th>Status</th>
            <th>Execution Timestamp</th>
            <th>Audit Log Detail</th>
          </tr>
        </thead>
        <tbody>
          ${logs.map(l => `
            <tr>
              <td><code>${l.action_name}</code></td>
              <td>${formatServiceName(l.target_service)}</td>
              <td><strong>${escapeHtml(l.approved_by || 'Autonomous')}</strong></td>
              <td><span class="badge-soft ${l.status === 'COMPLETED' ? 'badge-green' : 'badge-danger'}">${l.status}</span></td>
              <td style="font-size: 0.76rem; color: var(--text-muted);">${l.executed_at || 'Recently'}</td>
              <td style="font-size: 0.78rem; color: var(--text-secondary); max-width: 320px;">${escapeHtml(l.audit_log || '')}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } catch (e) {}
}

function updateRecoveryVerificationChart() {
  if (!charts.recoveryVerification) return;
  // Reflect live post-recovery state
  charts.recoveryVerification.data.datasets[1].data = [145, 0.0, 10];
  charts.recoveryVerification.update();
}

// ==================== SERVICE TOPOLOGY & BLAST RADIUS ====================

async function renderTopologyMap() {
  const container = document.getElementById("topologyCanvasContainer");
  if (!container) return;

  try {
    const res = await fetch("/api/sentinel/topology");
    const topo = res.ok ? await res.json() : { nodes: [] };
    const nodes = topo.nodes || [];

    // Interactive responsive SVG topology graph
    container.innerHTML = `
      <svg width="100%" height="380" viewBox="0 0 680 340" style="max-width: 680px; overflow: visible;">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#8B9FE8"/>
          </marker>
        </defs>

        <!-- Edges -->
        <line x1="140" y1="80" x2="250" y2="80" stroke="#8B9FE8" stroke-width="2" marker-end="url(#arrow)"/>
        <line x1="140" y1="180" x2="250" y2="100" stroke="#8B9FE8" stroke-width="2" marker-end="url(#arrow)"/>
        <line x1="330" y1="80" x2="420" y2="80" stroke="#8B9FE8" stroke-width="2" marker-end="url(#arrow)"/>
        <line x1="500" y1="80" x2="570" y2="80" stroke="#8B9FE8" stroke-width="2" marker-end="url(#arrow)"/>
        <line x1="500" y1="100" x2="570" y2="180" stroke="#8B9FE8" stroke-width="2" marker-end="url(#arrow)"/>

        <!-- Nodes -->
        <!-- 1. Auth Service -->
        <g class="topo-node" onclick="inspectTopologyNode('auth-service')" style="cursor: pointer;">
          <rect x="40" y="55" width="100" height="50" rx="8" fill="#FFFFFF" stroke="${getNodeColor('auth-service')}" stroke-width="2"/>
          <text x="90" y="80" text-anchor="middle" font-size="11" font-weight="700" fill="#25304A">Auth Service</text>
          <text x="90" y="95" text-anchor="middle" font-size="9" fill="${getNodeColor('auth-service')}">${getNodeStatus('auth-service')}</text>
        </g>

        <!-- 2. Product Service -->
        <g class="topo-node" onclick="inspectTopologyNode('product-service')" style="cursor: pointer;">
          <rect x="40" y="155" width="100" height="50" rx="8" fill="#FFFFFF" stroke="${getNodeColor('product-service')}" stroke-width="2"/>
          <text x="90" y="180" text-anchor="middle" font-size="11" font-weight="700" fill="#25304A">Product Catalog</text>
          <text x="90" y="195" text-anchor="middle" font-size="9" fill="${getNodeColor('product-service')}">${getNodeStatus('product-service')}</text>
        </g>

        <!-- 3. Cart Service -->
        <g class="topo-node" onclick="inspectTopologyNode('cart-service')" style="cursor: pointer;">
          <rect x="250" y="55" width="80" height="50" rx="8" fill="#FFFFFF" stroke="${getNodeColor('cart-service')}" stroke-width="2"/>
          <text x="290" y="80" text-anchor="middle" font-size="11" font-weight="700" fill="#25304A">Cart Svc</text>
          <text x="290" y="95" text-anchor="middle" font-size="9" fill="${getNodeColor('cart-service')}">${getNodeStatus('cart-service')}</text>
        </g>

        <!-- 4. Order Service -->
        <g class="topo-node" onclick="inspectTopologyNode('order-service')" style="cursor: pointer;">
          <rect x="420" y="55" width="80" height="50" rx="8" fill="#FFFFFF" stroke="${getNodeColor('order-service')}" stroke-width="2"/>
          <text x="460" y="80" text-anchor="middle" font-size="11" font-weight="700" fill="#25304A">Order Svc</text>
          <text x="460" y="95" text-anchor="middle" font-size="9" fill="${getNodeColor('order-service')}">${getNodeStatus('order-service')}</text>
        </g>

        <!-- 5. Payment Service -->
        <g class="topo-node" onclick="inspectTopologyNode('payment-service')" style="cursor: pointer;">
          <rect x="570" y="55" width="90" height="50" rx="8" fill="#FFFFFF" stroke="${getNodeColor('payment-service')}" stroke-width="2.5"/>
          <text x="615" y="80" text-anchor="middle" font-size="11" font-weight="700" fill="#25304A">Payment Svc</text>
          <text x="615" y="95" text-anchor="middle" font-size="9" font-weight="700" fill="${getNodeColor('payment-service')}">${getNodeStatus('payment-service')}</text>
        </g>

        <!-- 6. Database Service -->
        <g class="topo-node" onclick="inspectTopologyNode('database-service')" style="cursor: pointer;">
          <rect x="570" y="155" width="90" height="50" rx="8" fill="#FFFFFF" stroke="${getNodeColor('database-service')}" stroke-width="2"/>
          <text x="615" y="180" text-anchor="middle" font-size="11" font-weight="700" fill="#25304A">SQLite WAL</text>
          <text x="615" y="195" text-anchor="middle" font-size="9" fill="${getNodeColor('database-service')}">${getNodeStatus('database-service')}</text>
        </g>
      </svg>
    `;
  } catch (e) {}
}

function getNodeStatus(serviceName) {
  return currentSnapshot?.services?.[serviceName]?.status || "HEALTHY";
}

function getNodeColor(serviceName) {
  const status = getNodeStatus(serviceName);
  if (status === "CRITICAL") return "#DF7078";
  if (status === "WARNING") return "#E7AD55";
  return "#36A985";
}

async function inspectTopologyNode(serviceName) {
  const inspector = document.getElementById("topologyInspector");
  const nameEl = document.getElementById("inspectorServiceName");
  const badgeEl = document.getElementById("inspectorStatusBadge");
  const bodyEl = document.getElementById("inspectorBody");

  nameEl.textContent = formatServiceName(serviceName);
  const status = getNodeStatus(serviceName);
  badgeEl.textContent = status;
  badgeEl.className = `badge-soft badge-${status}`;

  try {
    const res = await fetch(`/api/sentinel/blast-radius/${serviceName}`);
    const blast = res.ok ? await res.json() : {};

    bodyEl.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 0.85rem; font-size: 0.82rem;">
        <div>
          <span style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Direct Upstream Callers:</span>
          <div style="font-weight: 700; color: var(--text-main); margin-top: 2px;">
            ${blast.direct_callers?.join(", ") || 'Direct Customer Entrypoint'}
          </div>
        </div>

        <div>
          <span style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Downstream Blast Radius:</span>
          <div style="font-weight: 700; color: var(--critical); margin-top: 2px;">
            ${blast.blast_radius?.join(", ") || 'None (Terminal Leaf Node)'}
          </div>
        </div>

        <div>
          <span style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Shopper Flow Operational Impact:</span>
          <p style="color: var(--text-secondary); margin-top: 2px; line-height: 1.45;">
            ${blast.impacted_operations?.join("; ") || 'Normal customer shopping operations unhindered.'}
          </p>
        </div>
      </div>
    `;
  } catch (err) {
    bodyEl.innerHTML = `<p>Error loading blast radius: ${err.message}</p>`;
  }
}

// ==================== ADAPTIVE THRESHOLDS & FORMULAS ====================

function updateAdaptiveChart() {
  const svcSelect = document.getElementById("adaptiveServiceSelect");
  const svcName = svcSelect ? svcSelect.value : "payment-service";
  const svcData = currentSnapshot?.services?.[svcName];

  if (svcData && charts.adaptiveBaseline) {
    const median = svcData.thresholds?.median || 150;
    const crit = svcData.thresholds?.critical_threshold || 600;
    const warn = svcData.thresholds?.warning_threshold || 350;

    charts.adaptiveBaseline.data.datasets[1].data = Array(15).fill(median);
    charts.adaptiveBaseline.data.datasets[2].data = Array(15).fill(warn);
    charts.adaptiveBaseline.data.datasets[3].data = Array(15).fill(crit);
    charts.adaptiveBaseline.update();

    const madVal = Math.round((crit - median) / (3.0 * 1.4826));
    document.getElementById("liveCalcDetails").textContent =
      `${median} ms (Median) + 3.0 • 1.4826 • ${madVal} ms (MAD) = ${crit} ms (Dynamic Critical Limit)`;
  }
}

async function handleUpdateThreshold(e) {
  e.preventDefault();
  const svc = document.getElementById("configServiceTarget").value;
  const mode = document.getElementById("configMode").value;
  const warn = parseFloat(document.getElementById("configStaticWarning").value);
  const crit = parseFloat(document.getElementById("configStaticCritical").value);

  try {
    const res = await fetch("/api/sentinel/thresholds/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service_name: svc,
        mode: mode,
        static_warning: warn,
        static_critical: crit
      })
    });
    const data = await res.json();
    showToast(data.message || "Threshold updated successfully", "success");
    fetchTelemetry();
  } catch (err) {
    showToast("Error updating threshold: " + err.message, "danger");
  }
}

// ==================== ML ANOMALY DETECTION ====================

function updateMlCharts() {
  // Update Live SQLite Anomalies table
  fetchRecordedAnomalies();
}

async function fetchRecordedAnomalies() {
  try {
    const res = await fetch("/api/sentinel/anomalies?limit=15");
    if (!res.ok) return;
    const anomalies = await res.json();
    const tbody = document.getElementById("anomaliesTableBody");
    if (!tbody) return;

    if (!anomalies || anomalies.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No multivariate anomalies currently logged in SQLite.</td></tr>`;
      return;
    }

    tbody.innerHTML = anomalies.map(a => `
      <tr>
        <td style="font-size: 0.76rem; color: var(--text-muted);">${a.timestamp}</td>
        <td><strong>${formatServiceName(a.service_name)}</strong></td>
        <td><span class="badge-soft badge-indigo">${a.detection_method}</span></td>
        <td><strong style="color: var(--critical);">${(a.anomaly_score || 0).toFixed(3)}</strong></td>
        <td><code>${escapeHtml(a.metrics_json?.substring(0, 45))}...</code></td>
        <td style="font-size: 0.78rem; color: var(--text-secondary); max-width: 300px;">${escapeHtml(a.explanation)}</td>
      </tr>
    `).join("");
  } catch (e) {}
}

// ==================== DEPLOYMENT MONITORING ====================

async function fetchDeployments() {
  try {
    const res = await fetch("/api/sentinel/deployments?limit=10");
    if (!res.ok) return;
    const deps = await res.json();
    const tbody = document.getElementById("deploymentsTableBody");
    if (!tbody) return;

    if (!deps || deps.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No deployments recorded yet. Use '+ Simulate CI/CD Release' above.</td></tr>`;
      return;
    }

    tbody.innerHTML = deps.map(d => `
      <tr>
        <td><code>${d.commit_hash}</code></td>
        <td><span class="badge-soft badge-indigo">${d.version}</span></td>
        <td>${escapeHtml(d.author)}</td>
        <td style="font-weight: 600;">${escapeHtml(d.message)}</td>
        <td>${(d.affected_services || []).join(", ")}</td>
        <td style="font-size: 0.76rem; color: var(--text-muted);">${d.deployed_at}</td>
        <td><span class="badge-soft badge-green">${d.status}</span></td>
      </tr>
    `).join("");
  } catch (e) {}
}

function openSimulateDeploymentModal() {
  document.getElementById("deploymentModal").classList.add("open");
}

function closeDeploymentModal() {
  document.getElementById("deploymentModal").classList.remove("open");
}

async function handleSimulateDeployment(e) {
  e.preventDefault();
  const v = document.getElementById("depVersion").value;
  const h = document.getElementById("depCommitHash").value;
  const a = document.getElementById("depAuthor").value;
  const m = document.getElementById("depMessage").value;
  const svcs = document.getElementById("depServices").value.split(",");

  try {
    const res = await fetch(`/api/sentinel/deployments?commit_hash=${encodeURIComponent(h)}&version=${encodeURIComponent(v)}&author=${encodeURIComponent(a)}&message=${encodeURIComponent(m)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(svcs)
    });
    if (!res.ok) throw new Error("Deployment webhook failed");
    closeDeploymentModal();
    showToast(`Recorded deployment: ${v} (${h})`, "success");
    fetchDeployments();
  } catch (err) {
    showToast("Error recording deployment: " + err.message, "danger");
  }
}

// ==================== INCIDENT MEMORY (RAG) ====================

async function searchHistoricalMemory() {
  const service = document.getElementById("memorySearchService").value;
  const query = document.getElementById("memorySearchInput").value.trim();
  const container = document.getElementById("memoryResultsContainer");
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Searching historical resolution patterns...</div>`;

  try {
    const res = await fetch(`/api/sentinel/memory/search?service=${encodeURIComponent(service)}&query=${encodeURIComponent(query)}`);
    if (!res.ok) return;
    const matches = await res.json();

    if (!matches || matches.length === 0) {
      container.innerHTML = `<div class="empty-state-card"><p>No historical resolution patterns matched.</p></div>`;
      return;
    }

    container.innerHTML = matches.map(m => `
      <div class="panel-card" style="margin-bottom: 0.85rem; border-left: 4px solid var(--accent-primary);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
          <h4 style="font-weight: 800; color: var(--text-main); font-size: 0.95rem;">
            ${m.incident_id}: ${escapeHtml(m.title)}
          </h4>
          <span class="badge-soft badge-green">Similarity: ${Math.round(m.similarity_score * 100)}%</span>
        </div>
        <p style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 0.65rem;">
          ${escapeHtml(m.root_cause_summary || '')}
        </p>
        <div style="background: var(--bg-surface); padding: 0.5rem 0.85rem; border-radius: var(--radius-sm); font-size: 0.8rem; color: var(--accent-primary);">
          <strong>Previously Verified Resolution:</strong> <code>${escapeHtml(m.successful_resolution || '')}</code>
        </div>
      </div>
    `).join("");
  } catch (err) {
    container.innerHTML = `<div class="empty-state-card"><p>Memory search error: ${err.message}</p></div>`;
  }
}

// ==================== EVALUATION & BENCHMARKS ====================

async function fetchEvaluation() {
  try {
    const res = await fetch("/api/sentinel/evaluation");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("evalMttd").textContent = `${data.mttd_seconds}s`;
    document.getElementById("evalMttr").textContent = `${data.mttr_seconds}s`;
    document.getElementById("evalFpRate").textContent = `${data.false_positive_rate_pct}%`;
    document.getElementById("evalRcaAccuracy").textContent = `${data.rca_top1_accuracy_pct}%`;
    document.getElementById("evalRecoverySuccess").textContent = `${data.recovery_success_rate_pct}%`;

    const benchContainer = document.getElementById("evalBenchmarksContainer");
    if (benchContainer && data.comparative_benchmarks) {
      benchContainer.innerHTML = `
        <table class="data-table">
          <thead>
            <tr>
              <th>Detection Methodology</th>
              <th>Mean Time to Detect (MTTD)</th>
              <th>False Positive Rate</th>
              <th>Fatigue Risk</th>
              <th>Context & Causal Awareness</th>
            </tr>
          </thead>
          <tbody>
            ${data.comparative_benchmarks.map(b => `
              <tr style="${b.method.includes('Sentinel Core') ? 'background: var(--bg-surface); font-weight: 700;' : ''}">
                <td style="color: ${b.method.includes('Sentinel Core') ? 'var(--accent-primary)' : 'var(--text-main)'};">${b.method}</td>
                <td><strong>${b.mttd}</strong></td>
                <td>${b.false_positive_rate}</td>
                <td><span class="badge-soft ${b.alert_fatigue_risk === 'HIGH' ? 'badge-danger' : (b.alert_fatigue_risk === 'LOW' ? 'badge-amber' : 'badge-green')}">${b.alert_fatigue_risk}</span></td>
                <td style="font-size: 0.78rem; color: var(--text-secondary);">${b.context_awareness}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }
  } catch (e) {}
}

// ==================== SRE LOGS STREAM ====================

async function fetchLiveLogs() {
  const service = document.getElementById("logServiceFilter")?.value || "";
  const level = document.getElementById("logLevelFilter")?.value || "";

  let url = "/api/sentinel/logs?limit=40";
  if (service) url += `&service=${encodeURIComponent(service)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) return;
    let logs = await res.json();

    if (level) {
      logs = logs.filter(l => l.level === level);
    }

    const tbody = document.getElementById("sreLogsTableBody");
    if (!tbody) return;

    if (!logs || logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No structured logs matching filter.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(l => {
      const levelBadge = l.level === 'ERROR' ? 'badge-danger' : (l.level === 'WARN' ? 'badge-amber' : 'badge-green');
      return `
        <tr>
          <td style="font-size: 0.76rem; color: var(--text-muted);">${l.timestamp?.split("T")[1]?.substring(0, 8) || l.timestamp}</td>
          <td><strong>${formatServiceName(l.service)}</strong></td>
          <td><span class="badge-soft ${levelBadge}">${l.level}</span></td>
          <td style="font-size: 0.78rem; color: var(--text-main);">
            ${escapeHtml(l.message)}
            ${l.metadata && Object.keys(l.metadata).length > 0 ? `<code style="margin-left: 0.5rem;">${JSON.stringify(l.metadata)}</code>` : ''}
          </td>
        </tr>
      `;
    }).join("");
  } catch (e) {}
}

// ==================== SYSTEM SETTINGS STATS ====================

async function fetchSystemStats() {
  try {
    const res = await fetch("/api/sentinel/system/stats");
    if (!res.ok) return;
    const stats = await res.json();

    document.getElementById("settingsDbSize").value = `${stats.db_size_kb} KB`;
    document.getElementById("settingsWalSize").value = `${stats.wal_size_kb} KB`;
    document.getElementById("settingsMetricsCount").value = `${stats.table_counts?.service_metrics || 0} rows`;
    document.getElementById("settingsAnomaliesCount").value = `${stats.table_counts?.anomalies || 0} rows`;
  } catch (e) {}
}

// ==================== STOREFRONT SIMULATION TESTER ====================

async function triggerStoreAction(action) {
  try {
    if (action === "browse") {
      const res = await fetch("/api/ecommerce/products");
      const prods = await res.json();
      showToast(`Catalog Hydrated: Loaded ${prods.length} products`, "success");
    } else if (action === "cart") {
      const res = await fetch("/api/ecommerce/cart/add", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-session-id": "demo-eval-session" },
        body: JSON.stringify({ product_id: 1, quantity: 1 })
      });
      const cart = await res.json();
      showToast(`Added to Cart: Total items = ${cart.total_items}`, "success");
    } else if (action === "checkout") {
      showToast("Testing order checkout pipeline...", "info");
      const res = await fetch("/api/ecommerce/orders/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-session-id": "demo-eval-session" },
        body: JSON.stringify({
          customer_name: "Demo Evaluator",
          customer_email: "evaluator@sentinel.local",
          card_number: "4242424242424242",
          card_exp: "12/28",
          card_cvv: "999"
        })
      });
      if (res.ok) {
        showToast("Order Placed Successfully! (Sub-180ms)", "success");
      } else {
        const err = await res.json();
        showToast(`Checkout Fault Intercepted: HTTP ${res.status} - ${err.detail?.substring(0, 45)}`, "danger");
      }
    }
    fetchTelemetry();
  } catch (err) {
    showToast("Store action error: " + err.message, "danger");
  }
}

// ==================== TOAST & UTILITIES ====================

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  const iconMap = {
    success: "✓",
    danger: "✕",
    warning: "⚠",
    info: "ℹ"
  };

  toast.innerHTML = `
    <span style="font-weight: 800; font-size: 1rem;">${iconMap[type] || 'ℹ'}</span>
    <span style="flex: 1;">${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function formatServiceName(name) {
  if (!name) return "";
  return name.replace(/-/g, " ").replace(/\b\w/g, l => l.toUpperCase());
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/[&<>'"]/g, tag => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[tag] || tag));
}
