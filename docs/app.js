(async () => {
  const d = await (await fetch("data.json")).json();
  document.getElementById("version").textContent = "Assessment " + d.assessment_version;
  const tabs = document.getElementById("company-tabs");
  const overview = document.getElementById("company-overview");
  const lists = document.getElementById("case-lists");
  const drawer = document.getElementById("case-detail");
  const inner = document.getElementById("case-detail-inner");

  const DIM_LABELS = {
    business_exposure: "Business exposure",
    policy_process_status: "Policy process status",
    intervention_type: "Intervention type",
    time_horizon: "Time horizon",
    evidence_confidence: "Evidence confidence",
    coverage: "Coverage"
  };
  const esc = s => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const money = v => "$" + (v/1e9).toFixed(1) + "B";

  function badges(c) {
    const warn = c.dimensions.coverage !== "Sufficient";
    return `<div class="badges">
      <span class="badge k">${esc(c.dimensions.business_exposure)} exposure</span>
      <span class="badge k">${esc(c.dimensions.policy_process_status)}</span>
      ${c.dimensions.intervention_type.map(t=>`<span class="badge">${esc(t)}</span>`).join("")}
      <span class="badge">${esc(c.dimensions.time_horizon)}</span>
      <span class="badge">confidence: ${esc(c.dimensions.evidence_confidence)}</span>
      <span class="badge ${warn?"warn":""}">coverage: ${esc(c.dimensions.coverage)}</span>
      ${c.review.status==="approved"
        ? `<span class="badge ok">reviewed &middot; v${esc(c.assessment_version)}</span>`
        : `<span class="badge pend">needs 2nd review</span>`}
    </div>`;
  }

  function renderCompany(cid) {
    const co = d.companies.find(x => x.company_id === cid);
    const cases = d.cases.filter(c => c.company_id === cid);
    overview.innerHTML = `<div class="ov">
      <h2>${esc(co.name)}</h2><span class="tick">${esc(co.ticker)} &middot; CIK ${esc(co.cik)}</span>
      <span class="rev">FY2025 consolidated revenue ${money(co.fy2025_consolidated_revenue_usd)}<br>
      <small>${esc(co.revenue_source)}</small></span>
      <span class="struct">${esc(co.structure)}</span>
    </div>`;
    const cur = cases.filter(c=>c.list==="current"), em = cases.filter(c=>c.list==="emerging");
    const card = c => `<div class="case-card" data-case="${c.case_id}">
      <h4>${esc(c.title)}</h4>
      <div class="mech">${esc(c.policy_mechanism)}</div>
      ${badges(c)}
      <div class="cardfoot"><span>${c.evidence.length} evidence spans</span>${c.advocacy_note?'<span class="badge" style="background:#f3e8fd;color:#6b21a8;border-color:#e2ccf7">advocacy</span>':''}<span class="go">evidence trail &rarr;</span></div>
    </div>`;
    const chg = (d.changes?d.changes.items:[]).filter(x=>x.company_id===cid);
    const cands = (d.candidates?d.candidates.items:[]).filter(x=>x.company_id===cid);
    const candCard = x => `<div class="cand-card">
      <div class="cand-head"><span class="badge cand-badge">unreviewed candidate</span>
        <span class="badge">confidence: ${esc(x.confidence)}</span>
        ${x.issue_hints.map(h=>`<span class="badge">${esc(h)}</span>`).join("")}</div>
      <blockquote>${esc(x.span.exact_text)}</blockquote>
      <div class="meta">${esc(x.span.doc_label)} &middot; <a href="${esc(x.span.source_url)}" target="_blank" rel="noopener">official source &rarr;</a> &middot; sha256 ${esc((x.span.sha256||"").slice(0,12))}&hellip;</div>
    </div>`;
    const chgCard = x => `<div class="change-card">
      <span class="cls">${esc(x.classification)}</span>
      <span class="badge ctype-badge">${esc(x.change_type.replace(/_/g," "))}</span>
      <div class="note">${esc(x.note)}</div>
      <span class="prev">previous filing: ${esc(x.previous_state)} (structural diff)</span>
      <blockquote>${esc(x.current_span.exact_text)}</blockquote>
      <div class="meta">${esc(x.current_span.doc_label)} &middot; filed ${esc(x.current_span.publication_date)} &middot; <a href="${esc(x.current_span.source_url)}" target="_blank" rel="noopener">official source &rarr;</a></div>
    </div>`;
    lists.innerHTML =
      `<h3 class="listhead">Current exposures</h3>` + cur.map(card).join("") +
      `<h3 class="listhead">Emerging</h3>` + em.map(card).join("") +
      (chg.length ? `<h3 class="listhead">Changes since previous review <span style="font-weight:400;text-transform:none;letter-spacing:0">(${esc(d.changes.change_window)})</span></h3>` +
        (d.boilerplate && d.boilerplate.companies[cid] ? `<div class="boiler">Boilerplate check: ${(d.boilerplate.companies[cid].carryover_share*100).toFixed(0)}% of FY2024 risk-factor sentences carried into FY2025 (${d.boilerplate.companies[cid].carried_over}/${d.boilerplate.companies[cid].sentences_fy2024}). ${esc(d.boilerplate.note)}</div>` : "") +
        chg.map(chgCard).join("") : "") +
      (cands.length ? `<h3 class="listhead">Candidate queue <span class="cand-sub">machine-surfaced &middot; unreviewed &middot; not findings</span></h3>` +
        `<div class="cand-note">${esc(d.candidates.note)} Extractor: ${esc(d.candidates.extractor)}. Review workflow in REVIEW.md.</div>` +
        cands.map(candCard).join("") : "");
    lists.querySelectorAll(".case-card").forEach(el =>
      el.onclick = () => openCase(el.dataset.case));
    [...tabs.children].forEach(b => b.classList.toggle("active", b.dataset.cid === cid));
  }

  function openCase(id) {
    const c = d.cases.find(x => x.case_id === id);
    const dims = Object.entries(DIM_LABELS).map(([k,label]) => {
      const v = c.dimensions[k];
      return `<div class="dim"><b>${label}</b>${esc(Array.isArray(v)?v.join(" + "):v)}</div>`;
    }).join("");
    inner.innerHTML = `
      <button class="close" onclick="document.getElementById('case-detail').classList.add('hidden')">&times;</button>
      <h2>${esc(c.title)}</h2>
      <div style="font-size:13px;color:var(--mut)">${esc(c.issue_family)} &middot; ${esc(c.jurisdiction.name)} &middot; authority: ${esc(c.authority)}</div>
      <div class="dimtable">${dims}</div>
      <div class="rationale"><b>Why these categories:</b> ${esc(c.rationale)}</div>

      <h5 class="sec">Mechanism chain (direct vs. inferred)</h5>
      <ul class="chain">${c.mechanism_chain.map(s =>
        `<li><span class="ctype ${s.type}">${s.type}</span>${esc(s.text)}</li>`).join("")}</ul>

      <h5 class="sec">Policy events</h5>
      <ul class="events">${c.events.map(e =>
        `<li><span class="d">${esc(e.date)}</span> &mdash; ${esc(e.description)}</li>`).join("")}</ul>

      <h5 class="sec">Financial linkage</h5>
      <div style="font-size:13.5px"><b>Ladder level: ${esc(c.financial_linkage.level)}.</b> ${esc(c.financial_linkage.detail)}
      <div class="gaps" style="margin-top:6px"><b>Gap:</b> ${esc(c.financial_linkage.gap)}</div></div>

      <h5 class="sec">Coverage gaps (shown, not hidden)</h5>
      <div class="gaps"><ul>${c.gaps.map(g=>`<li>${esc(g)}</li>`).join("")}</ul></div>

      ${c.advocacy_note?`<div class="advocacy"><b>Tier C caution:</b> ${esc(c.advocacy_note)}</div>`:""}

      <h5 class="sec">Evidence trail &mdash; exact spans from immutable snapshots</h5>
      ${c.evidence.map(e => `<div class="ev">
        <blockquote>&ldquo;${esc(e.exact_text)}&rdquo;${e.truncated?" <small>(span truncated for display)</small>":""}</blockquote>
        <div class="meta">
          <span class="tier ${e.tier}">Tier ${e.tier}</span>
          <span class="role">${esc(e.role)}</span>
          <span>${esc(e.doc_label)} (${esc(e.location)})</span>
          <span>published ${esc(e.publication_date)} &middot; retrieved ${esc(e.retrieved_at||"")}</span>
          <a href="${esc(e.source_url)}" target="_blank" rel="noopener">official source &rarr;</a>
        </div>
        <div class="meta"><span class="hash">sha256 ${esc((e.sha256||"").slice(0,16))}&hellip;</span>
        <span>supports: ${e.supports.map(esc).join(", ")}</span></div>
      </div>`).join("")}
      <h5 class="sec">Review &amp; version</h5>
      <div class="reviewbox ${c.review.status==="approved"?"ok":"pend"}">
        <b>${c.review.status==="approved"?"Approved":"Pending second review"}</b> &middot; assessment v${esc(c.assessment_version)}
        ${c.review.consequential?" &middot; consequential case (second reviewer required by REVIEW.md)":""}
        <ul>${c.review.reviewers.map(r=>`<li>${esc(r.id)} (${esc(r.role)}) - ${esc(r.reviewed_at)}: ${esc(r.notes)}</li>`).join("")}</ul>
        <div class="hist">${c.review.history.map(h=>`<div>${esc(h.at)} &middot; ${esc(h.reviewer)} &middot; ${esc(h.action)} - ${esc(h.reason)}</div>`).join("")}</div>
      </div>
      <p style="font-size:12px;color:var(--mut);margin-top:14px">This assessment deliberately has no single score. Each dimension above can be traced to the spans below it.</p>
    `;
    drawer.classList.remove("hidden");
  }

  drawer.onclick = e => { if (e.target === drawer) drawer.classList.add("hidden"); };

  d.companies.forEach(co => {
    const b = document.createElement("button");
    b.textContent = co.name.replace(/,.*/,"");
    b.dataset.cid = co.company_id;
    b.onclick = () => renderCompany(co.company_id);
    tabs.appendChild(b);
  });
  const pb = document.createElement("button");
  pb.textContent = "Portfolio";
  pb.dataset.cid = "__portfolio";
  pb.onclick = renderPortfolio;
  tabs.appendChild(pb);

  function renderPortfolio() {
    [...tabs.children].forEach(b => b.classList.toggle("active", b.dataset.cid === "__portfolio"));
    const EXP = ["Core","Meaningful","Limited","Unknown"];
    const byCo = d.companies.map(co => {
      const cs = d.cases.filter(c => c.company_id === co.company_id);
      return {co, cs};
    });
    overview.innerHTML = `<div class="ov"><h2>Portfolio view</h2>
      <span class="struct">All exposure cases across companies. Cross-sector comparison is contextual, not a ranking - coverage and disclosure incentives differ by company (paper: coverage bias).</span></div>`;
    const maxN = Math.max(...byCo.map(x => x.cs.length));
    const bars = byCo.map(({co, cs}) => {
      const seg = EXP.map(e => {
        const n = cs.filter(c => c.dimensions.business_exposure === e).length;
        return n ? `<span class="seg seg-${e.toLowerCase()}" style="flex:${n}" title="${e}: ${n}">${n} ${e.toLowerCase()}</span>` : "";
      }).join("");
      return `<div class="bar-row"><span class="bar-label">${esc(co.name.replace(/,.*/,""))}</span>
        <div class="bar" style="flex:${cs.length};max-width:${cs.length/maxN*70+20}%">${seg}</div>
        <span class="bar-n">${cs.length} cases</span></div>`;
    }).join("");
    const row = c => {
      const co = d.companies.find(x => x.company_id === c.company_id);
      return `<tr data-case="${c.case_id}">
        <td>${esc(co.name.replace(/,.*/,""))}</td>
        <td class="ttl">${esc(c.title)}</td>
        <td><b>${esc(c.dimensions.business_exposure)}</b></td>
        <td>${esc(c.dimensions.policy_process_status)}</td>
        <td>${esc(Array.isArray(c.dimensions.intervention_type)?c.dimensions.intervention_type.join(" + "):c.dimensions.intervention_type)}</td>
        <td>${esc(c.dimensions.evidence_confidence)}</td>
        <td>${c.review.status==="approved"?"reviewed v"+esc(c.assessment_version):"needs 2nd review"}</td>
        <td>${c.evidence.length}</td></tr>`;
    };
    lists.innerHTML = `<h3 class="listhead">Exposure distribution by company</h3><div class="bars">${bars}</div>
      <h3 class="listhead">All cases</h3>
      <table class="port"><tr><th>company</th><th>case</th><th>exposure</th><th>process</th><th>intervention</th><th>confidence</th><th>review</th><th>spans</th></tr>
      ${d.cases.map(row).join("")}</table>
      <p style="font-size:12px;color:var(--mut)">Click any row for the full evidence trail. Cases with coverage gaps say so on their own page.</p>`;
    lists.querySelectorAll("tr[data-case]").forEach(el => el.onclick = () => openCase(el.dataset.case));
  }

  document.getElementById("methodology").innerHTML = `
    <h3>Method (from the design paper)</h3>
    <div class="cols">
      <div><b>Design principles in force here</b><ul>
        <li>Evidence before synthesis - every claim anchors to an exact quoted span, machine-verified verbatim against the hashed raw snapshot at build time.</li>
        <li>Categorical dimensions, no composite scores.</li>
        <li>Direct vs. inferred mechanism steps are labeled.</li>
        <li>Coverage gaps are displayed, not smoothed over.</li>
        <li>Financial linkage follows the evidence ladder; unallocatable exposure is labeled Unknown.</li>
      </ul></div>
      <div><b>Source registry (this build)</b><ul>
        ${d.source_registry.map(s=>`<li><b>${esc(s.source)}</b> - Tier ${s.tier}, ${esc(s.access)}, ${esc(s.cadence)}</li>`).join("")}
      </ul>
      ${d.freshness?`<details><summary>Source health &amp; coverage (Stage 5 monitoring)</summary>
        <div style="font-size:12.5px;margin-top:6px">
        Checked ${esc(d.freshness.checked_at)}: ${d.freshness.documents} snapshots, ${d.freshness.hash_verified} hash-verified, ${d.freshness.hash_failures} failures, ${d.freshness.stale.length} stale.
        <table class="covtable"><tr><th>company</th>${Object.keys(d.freshness.coverage[Object.keys(d.freshness.coverage)[0]]).map(c=>`<th>${esc(c.replace("_"," "))}</th>`).join("")}</tr>
        ${Object.entries(d.freshness.coverage).map(([co,row])=>`<tr><td>${esc(co)}</td>${Object.values(row).map(v=>`<td class="${v?"cov-y":"cov-n"}">${v?"retrieved":"not retrieved"}</td>`).join("")}</tr>`).join("")}
        </table>
        <div style="color:var(--mut);margin-top:6px">${esc(d.freshness.coverage_note)}</div>
        </div></details>`:""}
      <details><summary>Dimension vocabularies</summary><ul>
        ${Object.entries(d.dimension_legend).map(([k,v])=>`<li><b>${esc(DIM_LABELS[k]||k)}:</b> ${v.map(esc).join(" | ")}</li>`).join("")}
      </ul></details></div>
    </div>`;

  renderCompany(d.companies[0].company_id);
})();
