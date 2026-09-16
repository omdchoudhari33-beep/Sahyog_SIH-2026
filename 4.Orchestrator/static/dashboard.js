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
        <td>${ticket.ticket_id}</td>
        <td class="stmt">${escapeHtml(ticket.problem_statement)}</td>
        <td>${escapeHtml(ticket.domain || "-")}</td>
        <td>${escapeHtml(String(ticket.severity ?? "-"))}</td>
        <td>${ticket.priority_score != null ? ticket.priority_score.toFixed(2) : "-"}</td>
        <td>${ticket.cluster_count}</td>
        <td>${escapeHtml(trackLabel(ticket.suggested_track))}</td>
        <td class="actions">
          <button class="a" data-decision="track_a" data-id="${ticket.ticket_id}">Track A</button>
          <button class="b" data-decision="track_b" data-id="${ticket.ticket_id}">Track B</button>
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

  function trackLabel(track) {
    return { track_a: "Track A - Govt", track_b: "Track B - University", review_required: "Needs classification" }[track] || track;
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
