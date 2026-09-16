(() => {
  const errorBox = document.getElementById("error");

  function showError(message) {
    errorBox.textContent = message;
    errorBox.style.display = "block";
  }
  function hideError() {
    errorBox.style.display = "none";
  }

  async function api(path, { method = "GET", body } = {}) {
    const opts = { method };
    if (body) {
      opts.body = JSON.stringify(body);
      opts.headers = { "Content-Type": "application/json" };
    }
    // No credentials are attached manually - the browser already holds the
    // HTTP Basic credentials it used to load this page (same origin, same
    // realm), and resends them automatically on every same-origin fetch.
    const response = await fetch(path, opts);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  function escapeText(value) {
    return String(value ?? "");
  }

  // --- Tabs ---
  const tabs = document.querySelectorAll(".tabs button");
  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabs.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`panel-${btn.dataset.panel}`).classList.add("active");
      loadPanel(btn.dataset.panel);
    });
  });

  async function loadPanel(name) {
    hideError();
    try {
      if (name === "track-a") await loadTrackA();
      else if (name === "track-b") await loadTrackB();
      else if (name === "industry") await loadIndustry();
      else if (name === "lifecycle") await loadLifecycle();
      else if (name === "transparency") await loadTransparency();
    } catch (err) {
      showError(err.message);
    }
  }

  async function loadTrackA() {
    const rows = await api("/api/admin/track-a");
    const body = document.getElementById("track-a-body");
    body.innerHTML = rows.length
      ? rows.map((d) => `<tr><td>${d.ticket_id}</td><td>${escapeText(d.channel)}</td><td>${escapeText(d.status)}</td><td>${escapeText(d.correlation_code)}</td><td>${new Date(d.sent_at).toLocaleString()}</td></tr>`).join("")
      : `<tr><td colspan="5" style="text-align:center;color:var(--muted)">No dispatches yet.</td></tr>`;
  }

  async function loadTrackB() {
    const rows = await api("/api/admin/track-b/pending");
    const body = document.getElementById("track-b-body");
    body.innerHTML = rows.length
      ? rows.map((p) => `
        <tr>
          <td>${p.id}</td><td>${escapeText(p.title)}</td><td>${escapeText((p.summary || "").slice(0, 80))}</td><td>${p.requested_budget ?? "-"}</td>
          <td>
            <input class="officer-id" placeholder="your id" data-id="${p.id}">
            <button onclick="window.__decideProposal(${p.id}, 'approved')">Approve</button>
            <button onclick="window.__decideProposal(${p.id}, 'rejected')">Reject</button>
            <button onclick="window.__decideProposal(${p.id}, 'revision_requested')">Revise</button>
          </td>
        </tr>`).join("")
      : `<tr><td colspan="5" style="text-align:center;color:var(--muted)">No proposals pending review.</td></tr>`;
  }

  window.__decideProposal = async (proposalId, decision) => {
    const input = document.querySelector(`.officer-id[data-id="${proposalId}"]`);
    const nodal_officer_id = (input && input.value) || "admin-portal";
    try {
      await api(`/api/admin/track-b/${proposalId}/decide`, { method: "POST", body: { decision, nodal_officer_id } });
      loadTrackB();
    } catch (err) {
      showError(err.message);
    }
  };

  async function loadIndustry() {
    const rows = await api("/api/admin/industry/ledgers");
    const body = document.getElementById("industry-body");
    body.innerHTML = rows.length
      ? rows.map((l) => `
        <tr>
          <td>${l.id}</td><td>${l.proposal_id}</td><td>${l.currency} ${l.total_committed_amount}</td><td>${escapeText(l.status)}</td>
          <td>
            <input class="release-amount" type="number" step="0.01" placeholder="amount" data-id="${l.id}">
            <button onclick="window.__releaseFunds(${l.id})">Release</button>
          </td>
        </tr>`).join("")
      : `<tr><td colspan="5" style="text-align:center;color:var(--muted)">No fund ledgers yet.</td></tr>`;
  }

  window.__releaseFunds = async (ledgerId) => {
    const input = document.querySelector(`.release-amount[data-id="${ledgerId}"]`);
    const amount = input && input.value;
    if (!amount) return showError("Enter an amount to release.");
    try {
      await api(`/api/admin/industry/ledgers/${ledgerId}/release`, { method: "POST", body: { amount, released_by: "admin-portal" } });
      loadIndustry();
    } catch (err) {
      showError(err.message);
    }
  };

  async function loadLifecycle() {
    const rows = await api("/api/admin/lifecycle/pending");
    const body = document.getElementById("lifecycle-body");
    body.innerHTML = rows.length
      ? rows.map((r) => `
        <tr>
          <td>${r.ticket_id}</td><td>${r.proposal_id}</td><td>${new Date(r.created_at).toLocaleString()}</td>
          <td>
            <button onclick="window.__disposition(${r.ticket_id}, ${r.proposal_id}, 'handover')">Handover to ULB</button>
            <button onclick="window.__disposition(${r.ticket_id}, ${r.proposal_id}, 'spinout')">Spin out</button>
          </td>
        </tr>`).join("")
      : `<tr><td colspan="4" style="text-align:center;color:var(--muted)">Nothing pending disposition.</td></tr>`;
  }

  window.__disposition = async (ticketId, proposalId, disposition) => {
    const body = { proposal_id: proposalId, disposition };
    if (disposition === "spinout") {
      const startup_name = prompt("Startup name:");
      if (!startup_name) return;
      body.startup_name = startup_name;
    }
    try {
      await api(`/api/admin/lifecycle/${ticketId}/disposition`, { method: "POST", body });
      loadLifecycle();
    } catch (err) {
      showError(err.message);
    }
  };

  async function loadTransparency() {
    const data = await api("/api/admin/transparency");
    const stats = document.getElementById("transparency-stats");
    stats.innerHTML = `
      <div class="stat"><b>${data.hei_participation.active_heis}</b>Active HEIs</div>
      <div class="stat"><b>${data.industry_engagement.active_partners}</b>Active partners</div>
      <div class="stat"><b>${data.completion_rate.pilots_passed}</b>Pilots passed</div>
      <div class="stat"><b>${data.outcomes.handovers}</b>Handovers</div>
      <div class="stat"><b>${data.outcomes.spinouts}</b>Spin-outs</div>
      <div class="stat"><b>${data.outcomes.track_a_resolved}</b>Track A resolved</div>
    `;
    const body = document.getElementById("heatmap-body");
    body.innerHTML = data.district_domain_heatmap.length
      ? data.district_domain_heatmap.map((r) => `<tr><td>${escapeText(r.district)}</td><td>${escapeText(r.domain)}</td><td>${r.ticket_count}</td></tr>`).join("")
      : `<tr><td colspan="3" style="text-align:center;color:var(--muted)">No data yet.</td></tr>`;
  }

  loadPanel("track-a");
})();
