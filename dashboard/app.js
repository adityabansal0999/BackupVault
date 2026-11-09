const API = "http://localhost:8000";

function formatSize(bytes) {
  if (bytes == null) return "-";
  if (bytes === 0) return "0 MiB";

  const mib = (bytes / (1024 * 1024)).toFixed(1);
  return mib + " MiB";
}

function formatWhen(s) {
  if (!s) return "-";
  const d = new Date(s);
  const date = d.toLocaleDateString();
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return date + " " + time;
}

function howCreated(by) {
  if (!by) return { label: "Scheduled", cls: "scheduled" };
  const v = by.toLowerCase();
  if (v.includes("sched")) return { label: "Scheduled", cls: "scheduled" };
  if (v.includes("cli") || v.includes("manual")) return { label: "Manual", cls: "manual" };
  if (v === "system") return { label: "Scheduled", cls: "scheduled" };
  return { label: by, cls: "manual" };
}

function isManual(by) {
  const v = (by || "").toLowerCase();
  return v.includes("cli") || v.includes("manual");
}
function isScheduled(by) {
  const v = (by || "").toLowerCase();
  return v.includes("sched") || v === "system";
}


async function loadStatus() {
  try {
    const r = await fetch(API + "/api/status");

    if (!r.ok) {
      throw new Error("Status API returned " + r.status);
    }

    const d = await r.json();

    if (!d) {
      throw new Error("Empty status response");
    }

    document.getElementById("lastFile").textContent =
      d.last_file || "No backups yet";

    document.getElementById("lastMeta").textContent =
      d.last_status
        ? d.last_status + " on " + formatWhen(d.last_time)
        : "Waiting for first backup";

    document.getElementById("totalStore").textContent =
      formatSize(d.total_storage);

    document.getElementById("totalCount").textContent =
      Number(d.total || 0) + " successful backups";

    document.getElementById("successRate").textContent =
      d.success_rate != null
        ? Number(d.success_rate).toFixed(1) + " %"
        : "-";

    const recentCount = Number(d.recent_count || 0);

    let healthText = "No backups available";

    if (d.success_rate != null) {
      healthText =
        (Number(d.success_rate) > 80
          ? "Healthy"
          : "Needs attention") +
        " - based on latest " + recentCount + " backups";
    }

    document.getElementById("healthMeta").textContent = healthText;

    document.getElementById("nextTime").textContent =
      d.next_run_at ? formatWhen(d.next_run_at) : "Not scheduled";

    document.getElementById("scheduleMeta").textContent =
      d.cron_expression
        ? "Cron: " + d.cron_expression
        : "No schedule configured";

  } catch (e) {
    console.error("Status loading failed:", e);
  }
}


async function loadHistory() {
  const from = document.getElementById("fromDate").value;
  const to = document.getElementById("toDate").value;
  const db = document.getElementById("dbFilter").value;
  const how = document.getElementById("typeFilter").value;

  let url = API + "/api/backups/history?limit=50&offset=0";

  if (from) {
    url += "&date_from=" + from;
  }

  if (to) {
    url += "&date_to=" + to + " 23:59:59";
  }

  try {
    const r = await fetch(url);
    const data = await r.json();

    if (!r.ok) {
      throw new Error("History API returned " + r.status);
    }

    let items = data.items;

    if (db) {
      items = items.filter(function (x) {
        return x.database_name === db;
      });
    }

    if (how === "manual") {
      items = items.filter(function (x) {
        return isManual(x.created_by);
      });
    }

    if (how === "scheduler") {
      items = items.filter(function (x) {
        return isScheduled(x.created_by);
      });
    }

    const totalLabel = (from || to)
      ? "Date-range records"
      : "Total records";

    document.getElementById("totalInfo").textContent =
      totalLabel + ": " + data.total +
      " | Matching loaded rows: " + items.length +
      " | Successful storage (date range): " +
      formatSize(data.total_storage);

    const tbody = document.getElementById("historyBody");
    tbody.innerHTML = "";

    const activity = [];

    if (!items.length) {
      tbody.innerHTML =
        '<tr><td colspan="9" class="empty">No backups for this filter</td></tr>';
    } else {
      for (const row of items) {
        const tr = document.createElement("tr");

        const statusClass =
          row.status === "SUCCESS"
            ? "pass"
            : row.status === "FAILED"
              ? "fail"
              : "pending";

        const verClass =
          row.verification_status === "PASS"
            ? "pass"
            : row.verification_status === "FAIL"
              ? "fail"
              : "pending";

        const howInfo = howCreated(row.created_by);

        tr.innerHTML =
          "<td class='when'>" + formatWhen(row.created_at) + "</td>" +
          "<td><span class='db'>" + (row.database_name || "customer_db") + "</span></td>" +
          "<td class='file'>" + row.file_name + "</td>" +
          "<td>" + formatSize(row.file_size_bytes) + "</td>" +
          "<td><span class='badge " + howInfo.cls + "'>" +
          howInfo.label + "</span><div style='font-size:11px;color:#9A8C98;margin-top:3px'>by " +
          (row.created_by || "system") + "</div></td>" +
          "<td><span class='badge " + statusClass + "'>" + row.status + "</span></td>" +
          "<td><span class='badge " + verClass + "'>" + row.verification_status + "</span></td>" +
          "<td><span class='path' title='" + row.file_path + "'>" + row.file_path + "</span></td>" +
          "<td><button class='actionBtn' onclick='doVerify(" + row.backup_id + ")'>Check</button></td>";

        tbody.appendChild(tr);
        activity.push(row);
      }
    }

    renderActivity(activity.slice(0, 6));

  } catch (e) {
    console.error("History loading failed:", e);

    document.getElementById("historyBody").innerHTML =
      '<tr><td colspan="9" class="empty">Unable to load backup history. Check whether the API is running.</td></tr>';

    renderActivity([]);
  }
}


function renderActivity(items) {
  const box = document.getElementById("activityList");
  if (!items.length) {
    box.innerHTML = '<div class="empty">No recent activity. Create a backup to see it here</div>';
    return;
  }
  box.innerHTML = "";
  for (const row of items) {
    const dotClass = row.status === "SUCCESS" ? "ok" : row.status === "FAILED" ? "bad" : "wait";
    const howInfo = howCreated(row.created_by);
    const div = document.createElement("div");
    div.className = "activityItem";
    div.innerHTML =
      "<span class='activityDot " + dotClass + "'></span>" +
      "<div class='activityText'>" +
      "<b>" + row.file_name + "</b> created for <b>" + (row.database_name || "customer_db") + "</b> via <b>" + howInfo.label + "</b>" +
      "<small>" + formatWhen(row.created_at) + " - " + formatSize(row.file_size_bytes) + " - " + row.status + " - by " + (row.created_by || "system") + " - Integrity " + (row.verification_status || "PENDING") + "</small>" +
      "</div>";
    box.appendChild(div);
  }
}

async function doVerify(id) {
  const box = document.getElementById("verifyResult");
  box.textContent = "Checking " + id + "...";
  try {
    const r = await fetch(API + "/api/backups/" + id + "/verify", { method: "POST" });
    const d = await r.json();
    if (d.result === "PASS") {
      box.innerHTML = "Backup " + id + " <span class='badge pass'>Healthy</span> - file exists " + d.file_exists + " size ok " + d.file_size_ok + " gzip ok " + d.gzip_valid + " checksum " + d.checksum_match;
    } else {
      box.innerHTML = "Backup " + id + " <span class='badge fail'>Failed</span> - file exists " + d.file_exists + " size ok " + d.file_size_ok + " gzip ok " + d.gzip_valid;
    }
    await loadHistory();
    await loadStatus();
  } catch (e) {
    box.textContent = "Check failed: " + e;
  }
}

async function triggerBackup() {
  const box = document.getElementById("verifyResult");
  box.textContent = "Creating backup...";
  try {
    const r = await fetch(API + "/api/backups", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ database_name: "customer_db", created_by: "manual" }) });
    const d = await r.json();
    box.textContent = "Created " + d.file_name + " with " + d.status;
    await loadHistory();
    await loadStatus();
    setTimeout(function() { loadHistory(); loadStatus(); }, 800);
  } catch (e) {
    box.textContent = "Create failed. Is the backend running";
  }
}

function clearFilter() {
  document.getElementById("fromDate").value = "";
  document.getElementById("toDate").value = "";
  document.getElementById("dbFilter").value = "";
  document.getElementById("typeFilter").value = "";
  loadHistory();
}

loadStatus();
loadHistory();

setInterval(function () {
  loadStatus();
  loadHistory();
}, 15000);
