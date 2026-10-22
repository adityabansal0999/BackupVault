const API = (window.location.origin && window.location.origin.startsWith("http")) 
  ? window.location.origin 
  : "http://localhost:8000";

function formatSize(bytes) {
  if (bytes === null || bytes === undefined || isNaN(bytes)) return "-";
  if (bytes === 0) return "0 MB";
  const mb = (bytes / (1024 * 1024)).toFixed(1);
  return mb + " MB";
}

function formatWhen(s) {
  if (!s) return "-";
  try {
    const d = new Date(s);
    if (isNaN(d.getTime())) return String(s);
    const date = d.toLocaleDateString();
    const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return date + " " + time;
  } catch (e) {
    return String(s);
  }
}

function howCreated(by) {
  if (!by) return { label: "Scheduled", cls: "scheduled" };
  const v = String(by).toLowerCase();
  if (v.includes("sched") || v === "system") return { label: "Scheduled", cls: "scheduled" };
  if (v.includes("cli") || v.includes("manual") || v.includes("api")) return { label: "Manual", cls: "manual" };
  return { label: by, cls: "manual" };
}

function isManual(by) {
  const v = (by || "").toLowerCase();
  return v.includes("cli") || v.includes("manual") || v.includes("api");
}
function isScheduled(by) {
  const v = (by || "").toLowerCase();
  return v.includes("sched") || v === "system";
}

async function loadStatus() {
  try {
    const r = await fetch(API + "/api/status");
    if (!r.ok) return;
    const d = await r.json();
    if (!d) return;

    const lastFileEl = document.getElementById("lastFile");
    const lastMetaEl = document.getElementById("lastMeta");
    if (lastFileEl) lastFileEl.textContent = d.last_file || "No backups yet";
    if (lastMetaEl) {
      if (d.last_status && d.last_time) {
        lastMetaEl.textContent = d.last_status + " on " + formatWhen(d.last_time);
      } else if (d.last_status) {
        lastMetaEl.textContent = d.last_status;
      } else {
        lastMetaEl.textContent = "Waiting for first backup";
      }
    }

    const nextTimeEl = document.getElementById("nextTime");
    if (nextTimeEl) {
      if (d.next_run_at) {
        nextTimeEl.textContent = formatWhen(d.next_run_at);
      } else if (d.cron_expression) {
        nextTimeEl.textContent = "Cron: " + d.cron_expression;
      } else {
        nextTimeEl.textContent = "Daily at 02:00 AM";
      }
    }

    const totalStoreEl = document.getElementById("totalStore");
    const totalCountEl = document.getElementById("totalCount");
    if (totalStoreEl) totalStoreEl.textContent = formatSize(d.total_storage);
    if (totalCountEl) totalCountEl.textContent = (d.total != null) ? d.total + " successful backups" : "-";

    const successRateEl = document.getElementById("successRate");
    const healthMetaEl = document.getElementById("healthMeta");
    if (successRateEl) {
      if (d.success_rate != null) {
        const rate = Number(d.success_rate);
        successRateEl.textContent = (isNaN(rate) ? "100.0" : rate.toFixed(1)) + " %";
        if (healthMetaEl) {
          healthMetaEl.textContent = (rate >= 80 ? "Healthy" : "Needs attention") + " (" + (d.total || 0) + " backups)";
        }
      } else {
        successRateEl.textContent = "100.0 %";
        if (healthMetaEl) healthMetaEl.textContent = "System ready";
      }
    }
  } catch (e) {
    console.warn("Status load warning:", e);
  }
}

async function loadHistory() {
  const fromEl = document.getElementById("fromDate");
  const toEl = document.getElementById("toDate");
  const dbEl = document.getElementById("dbFilter");
  const typeEl = document.getElementById("typeFilter");

  const from = fromEl ? fromEl.value : "";
  const to = toEl ? toEl.value : "";
  const db = dbEl ? dbEl.value : "";
  const how = typeEl ? typeEl.value : "";

  let url = API + "/api/backups/history?limit=50&offset=0";
  if (from) url += "&date_from=" + encodeURIComponent(from);
  if (to) url += "&date_to=" + encodeURIComponent(to + " 23:59:59");

  const tbody = document.getElementById("historyBody");

  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();

    let items = (data && Array.isArray(data.items)) ? data.items : [];
    if (db) items = items.filter(function(x) { return x.database_name === db; });
    if (how === "manual") items = items.filter(function(x) { return isManual(x.created_by); });
    if (how === "scheduler") items = items.filter(function(x) { return isScheduled(x.created_by); });

    const totalInfoEl = document.getElementById("totalInfo");
    if (totalInfoEl) {
      const totalCount = data.total != null ? data.total : items.length;
      totalInfoEl.textContent = "Total " + totalCount + " - Storage " + formatSize(data.total_storage) + " - Showing " + items.length;
    }

    if (!tbody) return;
    tbody.innerHTML = "";

    const activity = [];
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="9" class="empty">No backups found matching this filter</td></tr>';
    } else {
      for (const row of items) {
        const tr = document.createElement("tr");
        const statusClass = row.status === "SUCCESS" ? "pass" : (row.status === "FAILED" ? "fail" : "pending");
        const verClass = row.verification_status === "PASS" ? "pass" : (row.verification_status === "FAIL" ? "fail" : "pending");
        const howInfo = howCreated(row.created_by);
        const backupId = row.backup_id;

        tr.innerHTML =
          "<td class='when'>" + formatWhen(row.created_at) + "</td>" +
          "<td><span class='db'>" + (escapeHtml(row.database_name) || "customer_db") + "</span></td>" +
          "<td class='file'>" + escapeHtml(row.file_name) + "</td>" +
          "<td>" + formatSize(row.file_size_bytes) + "</td>" +
          "<td><span class='badge " + howInfo.cls + "'>" + howInfo.label + "</span><div style='font-size:11px;color:#9A8C98;margin-top:3px'>by " + escapeHtml(row.created_by || "system") + "</div></td>" +
          "<td><span class='badge " + statusClass + "'>" + (row.status || "-") + "</span></td>" +
          "<td><span class='badge " + verClass + "'>" + (row.verification_status || "PENDING") + "</span></td>" +
          "<td><span class='path' title='" + escapeHtml(row.file_path) + "'>" + escapeHtml(row.file_path) + "</span></td>" +
          "<td><button class='actionBtn' id='btn-check-" + backupId + "' onclick='doVerify(" + backupId + ")'>Check</button></td>";
        tbody.appendChild(tr);
        activity.push(row);
      }
    }
    renderActivity(activity.slice(0, 6));
  } catch (e) {
    console.error("Error loading history:", e);
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="9" class="empty">Backend API disconnected. Ensure server is running on port 8000.</td></tr>';
    }
    renderActivity([]);
  }
}

function renderActivity(items) {
  const box = document.getElementById("activityList");
  if (!box) return;
  if (!items || !items.length) {
    box.innerHTML = '<div class="empty">No recent activity. Create a backup to see live events.</div>';
    return;
  }
  box.innerHTML = "";
  for (const row of items) {
    const dotClass = row.status === "SUCCESS" ? "ok" : (row.status === "FAILED" ? "bad" : "wait");
    const howInfo = howCreated(row.created_by);
    const div = document.createElement("div");
    div.className = "activityItem";
    div.innerHTML =
      "<span class='activityDot " + dotClass + "'></span>" +
      "<div class='activityText'>" +
      "<b>" + escapeHtml(row.file_name) + "</b> for <b>" + escapeHtml(row.database_name || "customer_db") + "</b> via <b>" + howInfo.label + "</b>" +
      "<small>" + formatWhen(row.created_at) + " &bull; " + formatSize(row.file_size_bytes) + " &bull; " + (row.status || "-") + " &bull; Integrity: " + (row.verification_status || "PENDING") + "</small>" +
      "</div>";
    box.appendChild(div);
  }
}

async function doVerify(id) {
  const box = document.getElementById("verifyResult");
  const btn = document.getElementById("btn-check-" + id);
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Checking...";
  }
  if (box) box.textContent = "Verifying backup #" + id + "... Checking SHA-256 and gzip integrity.";

  try {
    const r = await fetch(API + "/api/backups/" + id + "/verify", { method: "POST" });
    const d = await r.json();
    if (box) {
      if (d.result === "PASS") {
        box.innerHTML = "<b>Backup #" + id + "</b> &mdash; <span class='badge pass'>Healthy (PASS)</span><br><small>Exists: " + (d.file_exists ? "Yes" : "No") + " | Size: " + (d.file_size_ok ? "Valid" : "Empty") + " | Gzip: " + (d.gzip_valid ? "Valid" : "Corrupt") + " | Checksum: " + (d.checksum_match ? "Matches" : "Mismatched") + "</small>";
      } else {
        box.innerHTML = "<b>Backup #" + id + "</b> &mdash; <span class='badge fail'>Failed (FAIL)</span><br><small>Exists: " + (d.file_exists ? "Yes" : "No") + " | Gzip: " + (d.gzip_valid ? "Valid" : "Corrupt") + "</small>";
      }
    }
    await loadHistory();
    await loadStatus();
  } catch (e) {
    if (box) box.textContent = "Verification request failed: " + e.message;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Check";
    }
  }
}

async function triggerBackup() {
  const box = document.getElementById("verifyResult");
  const topBtn = document.querySelector(".topActions button");
  if (topBtn) {
    topBtn.disabled = true;
    topBtn.textContent = "Creating Backup...";
  }
  if (box) box.textContent = "Starting mysqldump stream & gzip compression...";

  try {
    const r = await fetch(API + "/api/backups", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ database_name: "customer_db", created_by: "manual" })
    });
    const d = await r.json();
    if (r.ok && d.status === "SUCCESS") {
      if (box) box.innerHTML = "<span class='badge pass'>Success</span> Created <b>" + escapeHtml(d.file_name) + "</b> (" + formatSize(d.size) + ")";
    } else {
      if (box) box.innerHTML = "<span class='badge fail'>Failed</span> " + escapeHtml(d.error || d.message || "Backup failed");
    }
    await loadHistory();
    await loadStatus();
  } catch (e) {
    if (box) box.textContent = "Trigger failed. Ensure backend server is running on port 8000.";
  } finally {
    if (topBtn) {
      topBtn.disabled = false;
      topBtn.textContent = "Create Backup Now";
    }
  }
}

function clearFilter() {
  const fromEl = document.getElementById("fromDate");
  const toEl = document.getElementById("toDate");
  const dbEl = document.getElementById("dbFilter");
  const typeEl = document.getElementById("typeFilter");
  if (fromEl) fromEl.value = "";
  if (toEl) toEl.value = "";
  if (dbEl) dbEl.value = "";
  if (typeEl) typeEl.value = "";
  loadHistory();
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

loadStatus();
loadHistory();
setInterval(loadStatus, 15000);