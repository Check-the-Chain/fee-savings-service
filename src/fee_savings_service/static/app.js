const form = document.getElementById("lookup-form");
const addressInput = document.getElementById("address");
const windowInput = document.getElementById("window");
const submitButton = document.getElementById("submit-button");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const estimatedSavingsEl = document.getElementById("estimated-savings");
const estimationModeEl = document.getElementById("estimation-mode");
const resolvedAddressEl = document.getElementById("resolved-address");
const estimateTableBody = document.getElementById("estimate-table-body");

function fmtUsd(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function fmtVol(value) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function fmtRate(value) {
  const num = Number(value || 0);
  return (num * 100).toFixed(4) + "%";
}

function isSupportedWindow(value) {
  return ["1d", "7d", "30d", "all"].includes(value);
}

function syncUrl(address, windowValue) {
  const params = new URLSearchParams(window.location.search);

  if (address) {
    params.set("address", address);
  } else {
    params.delete("address");
  }

  if (isSupportedWindow(windowValue)) {
    params.set("window", windowValue);
  } else {
    params.delete("window");
  }

  const query = params.toString();
  const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState({}, "", nextUrl);
}

function syncUrlFromInputs() {
  syncUrl(addressInput.value.trim(), windowInput.value);
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", Boolean(isError));
}

function sectionRow(label) {
  const tr = document.createElement("tr");
  tr.className = "section-row";
  tr.innerHTML = `<td colspan="2">${label}</td>`;
  return tr;
}

function dataRow(label, value) {
  const tr = document.createElement("tr");
  tr.innerHTML = `<td>${label}</td><td>${value}</td>`;
  return tr;
}

function renderEstimate(s) {
  estimateTableBody.innerHTML = "";
  const frag = document.createDocumentFragment();

  frag.appendChild(sectionRow("Volume"));
  frag.appendChild(dataRow("Requested perp volume", "$" + fmtVol(s.requested_perp_volume)));

  frag.appendChild(sectionRow("Rates"));
  frag.appendChild(dataRow("Blended perp rate", fmtRate(s.recent_blended_perp_rate)));
  frag.appendChild(dataRow("Perp taker rate", fmtRate(s.current_rates.perp_taker_rate)));
  frag.appendChild(dataRow("Perp maker rate", fmtRate(s.current_rates.perp_maker_rate)));

  frag.appendChild(sectionRow("Methodology"));
  frag.appendChild(dataRow("Fee assumption", s.fee_assumption));
  frag.appendChild(dataRow("Coverage", s.coverage_note));

  estimateTableBody.appendChild(frag);
}

async function fetchSummary(payload) {
  const response = await fetch("/v1/hyperliquid/savings-estimate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : "Request failed";
    throw new Error(detail);
  }
  return data;
}

async function submitLookup(event) {
  if (event) {
    event.preventDefault();
  }

  const address = addressInput.value.trim();
  const windowValue = windowInput.value;

  resultsEl.classList.add("hidden");
  submitButton.disabled = true;
  setStatus("Loading...");

  try {
    const summary = await fetchSummary({ address, window: windowValue });
    syncUrl(address, windowValue);

    estimatedSavingsEl.textContent = fmtUsd(summary.estimated_savings);
    estimationModeEl.textContent =
      summary.estimation_mode === "exact_from_fill_fees"
        ? "Based on exact fill fees"
        : summary.estimation_mode === "estimate_from_user_fees_daily_breakdown"
          ? "Estimated from daily volume and current rates"
        : "Based on portfolio volume & blended rate";
    resolvedAddressEl.textContent =
      summary.address.slice(0, 6) + "..." + summary.address.slice(-4);
    renderEstimate(summary);
    resultsEl.classList.remove("hidden");
    setStatus("");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Request failed";
    setStatus(message, true);
  } finally {
    submitButton.disabled = false;
  }
}

form.addEventListener("submit", submitLookup);
addressInput.addEventListener("input", syncUrlFromInputs);
windowInput.addEventListener("change", syncUrlFromInputs);

const params = new URLSearchParams(window.location.search);
const prefillAddress = params.get("address");
const prefillWindow = params.get("window");
if (prefillAddress) {
  addressInput.value = prefillAddress;
}
if (prefillWindow && isSupportedWindow(prefillWindow)) {
  windowInput.value = prefillWindow;
}

if (prefillAddress && prefillWindow && isSupportedWindow(prefillWindow)) {
  submitLookup();
}

syncUrlFromInputs();
