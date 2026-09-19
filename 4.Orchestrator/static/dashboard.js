(() => {
  const tbody = document.getElementById("tickets-body");
  const emptyState = document.getElementById("empty");
  const errorBox = document.getElementById("error");
  const refreshBtn = document.getElementById("refresh-btn");
  const operatorInput = document.getElementById("operator-id");

  operatorInput.value = localStorage.getItem("sahyog_operator_id") || "";
  operatorInput.addEventListener("change", () => {
    localStorage.setItem("sahyog_operator_id", operatorInput.value.trim());
  });

  refreshBtn.addEventListener("click", loadTickets);
  loadTickets();

  async function loadTickets() {
    hideError();
    refreshBtn.disabled = true;
    try {
      const response = await fetch("/api/tickets?limit=100");
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
      renderTickets(body.items || []);
    } catch (err) {
      showError("Could not load tickets: " + err.message);
      tbody.innerHTML = "";
      emptyState.style.display = "none";
    } finally {
      refreshBtn.disabled = false;
    }
  }

  function renderTickets(items) {
    tbody.innerHTML = "";
    emptyState.style.display = items.length ? "none" : "block";

    for (const ticket of items) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>#${ticket.ticket_id}</td>
        <td>${evidenceCell(ticket)}</td>
        <td class="stmt">${escapeHtml(ticket.problem_statement)}</td>
        <td>${escapeHtml(formatDomain(ticket.domain))}</td>
        <td>${severityBadge(ticket.severity)}</td>
        <td class="priority-score">${ticket.priority_score != null ? ticket.priority_score.toFixed(2) : "-"}</td>
        <td>${ticket.cluster_count}</td>
        <td>${trackBadge(ticket.suggested_track)}</td>
        <td class="actions">
          <button class="a${ticket.suggested_track === "track_a" ? " suggested" : ""}" data-decision="track_a" data-id="${ticket.ticket_id}">${ticket.suggested_track === "track_a" ? "✓ Confirm Track A" : "Track A"}</button>
          <button class="b${ticket.suggested_track === "track_b" ? " suggested" : ""}" data-decision="track_b" data-id="${ticket.ticket_id}">${ticket.suggested_track === "track_b" ? "✓ Confirm Track B" : "Track B"}</button>
          <button class="reject" data-decision="reject_merge" data-id="${ticket.ticket_id}">Reject/Merge</button>
        </td>
      `;
      tbody.appendChild(tr);
    }

    tbody.querySelectorAll("button[data-decision]").forEach((btn) => {
      btn.addEventListener("click", () => submitDecision(btn.dataset.id, btn.dataset.decision));
    });
  }

  async function submitDecision(ticketId, decision) {
    const operatorId = operatorInput.value.trim();
    if (!operatorId) {
      showError("Enter an operator ID before recording a decision.");
      return;
    }
    const notes = window.prompt(`Notes for ${decision.replace("_", " ")} on ticket #${ticketId} (optional):`, "") || undefined;

    hideError();
    try {
      const response = await fetch(`/api/tickets/${ticketId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, operator_id: operatorId, notes }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
      await loadTickets();
    } catch (err) {
      showError(`Decision failed for ticket #${ticketId}: ` + err.message);
    }
  }

  function evidenceCell(ticket) {
    const parts = [];
    if (ticket.report_photo_url) {
      parts.push(
        `<a href="${escapeHtml(ticket.report_photo_url)}" target="_blank" rel="noopener">` +
          `<img class="evidence-thumb" src="${escapeHtml(ticket.report_photo_url)}" alt="report photo" /></a>`
      );
    }
    if (ticket.report_audio_url) {
      parts.push(`<a class="evidence-audio" href="${escapeHtml(ticket.report_audio_url)}" target="_blank" rel="noopener">▶ audio</a>`);
    }
    return parts.length ? parts.join(" ") : "<span style=\"color:var(--muted-2)\">-</span>";
  }

  function formatDomain(domain) {
    if (!domain) return "-";
    return String(domain)
      .split("_")
      .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
      .join(" ");
  }

  const SEVERITY_BADGE = { 1: "routed", 2: "review_required", 3: "geo_required", 4: "geo_required" };
  function severityBadge(severity) {
    if (severity == null) return "-";
    const cls = SEVERITY_BADGE[Math.round(severity)] || "review_required";
    return `<span class="badge ${cls}">${escapeHtml(severity)}</span>`;
  }

  function trackBadge(track) {
    const label = { track_a: "Track A · Govt", track_b: "Track B · University", review_required: "Needs classification" }[track] || track;
    return `<span class="badge ${escapeHtml(track)}">${escapeHtml(label)}</span>`;
  }
  function showError(message) {
    errorBox.textContent = message;
    errorBox.style.display = "block";
  }
  function hideError() {
    errorBox.style.display = "none";
  }
  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
  }
})();
