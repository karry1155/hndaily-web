(() => {
  const app = document.querySelector("[data-gold-review]");
  if (!app) return;

  const STORAGE_KEY = `hnhot-gold-review:${app.dataset.benchmarkId}`;
  const queue = app.querySelector("[data-queue-list]");
  const sourcePanel = app.querySelector("[data-source-panel]");
  const editorPanel = app.querySelector("[data-editor-panel]");
  const search = app.querySelector("[data-queue-search]");
  const saveState = app.querySelector("[data-save-state]");
  let dataset = null;
  let rows = [];
  let activeId = null;
  let filter = "selected";
  let lastRepoSignature = null;

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  const splitValues = (value) => String(value || "").split(/[，,]/).map((row) => row.trim()).filter(Boolean);
  const joinValues = (value) => Array.isArray(value) ? value.join("、") : "";
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const same = (left, right) => JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
  const hasValue = (value) => Array.isArray(value)
    ? value.length > 0
    : value !== null && value !== undefined && String(value).trim() !== "";

  function mergeObjectRows(repositoryRows, localRows, keyOf) {
    const merged = new Map();
    (repositoryRows || []).forEach((value) => merged.set(keyOf(value), clone(value)));
    (localRows || []).forEach((value) => {
      const key = keyOf(value);
      const repositoryValue = merged.get(key) || {};
      merged.set(key, Object.fromEntries(
        [...new Set([...Object.keys(repositoryValue), ...Object.keys(value)])]
          .map((field) => [field, hasValue(value[field])
            ? value[field]
            : (repositoryValue[field] ?? "")])
      ));
    });
    return [...merged.values()];
  }

  function mergeChangedExpected(repository, local, base) {
    const result = clone(repository);
    const changed = (field) => !same(local?.[field], base?.[field]);
    if (changed("primary_subjects")) {
      result.primary_subjects = mergeObjectRows(
        repository.primary_subjects, local.primary_subjects, (value) => value.name
      );
    }
    if (changed("background_mentions")) {
      result.background_mentions = [...new Set([
        ...(repository.background_mentions || []), ...(local.background_mentions || []),
      ])];
    }
    if (changed("locations")) {
      result.locations = mergeObjectRows(
        repository.locations, local.locations, (value) => value.location_id
      );
    }
    if (changed("named_events")) {
      result.named_events = mergeObjectRows(
        repository.named_events, local.named_events, (value) => value.name
      );
    }
    if (changed("projects")) {
      result.projects = mergeObjectRows(
        repository.projects, local.projects, (value) => value.name
      );
    }
    if (changed("facts")) {
      result.facts = mergeObjectRows(
        repository.facts,
        local.facts,
        (value) => `${value.occurred_on}|${value.action}|${value.object}`
      );
    }
    if (changed("notes")) {
      const localNotes = String(local.notes || "").trim();
      const repositoryNotes = String(repository.notes || "").trim();
      result.notes = localNotes && repositoryNotes && localNotes !== repositoryNotes
        ? `${localNotes}\n\n系统补充：${repositoryNotes}`
        : localNotes || repositoryNotes;
    }
    return result;
  }

  function persistLocal() {
    const payload = Object.fromEntries(rows.map((row) => [row.item_id, {
      selected: row.selected,
      review_status: row.review_status,
      expected: row.expected,
      base_expected: row.repository_expected,
    }]));
    localStorage.setItem(STORAGE_KEY, JSON.stringify({schema_version: 2, rows: payload}));
    const signature = dataset ? JSON.stringify(exportPayload()) : null;
    saveState.textContent = lastRepoSignature && signature === lastRepoSignature
      ? "已保存到项目"
      : "修改已自动保存在本浏览器";
  }

  function restoreLocal() {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch (_) { saved = null; }
    if (!saved || typeof saved !== "object") return;
    const legacy = saved.schema_version !== 2 || !saved.rows;
    const savedRows = legacy ? saved : saved.rows;
    rows.forEach((row) => {
      const value = savedRows[row.item_id];
      if (!value) return;
      row.selected = row.required || row.selected || Boolean(value.selected);
      row.review_status = row.review_status === "reviewed" || value.review_status === "reviewed"
        ? "reviewed"
        : "draft";
      if (value.expected && typeof value.expected === "object") {
        const base = legacy ? row.initial_expected : value.base_expected;
        row.expected = mergeChangedExpected(row.repository_expected, value.expected, base || {});
      }
    });
  }

  function exportPayload() {
    const selected = rows.filter((row) => row.selected).map((row) => ({
      item_id: row.item_id,
      candidate_id: row.candidate_id,
      published_date: row.published_date,
      page_number: row.page_number,
      page_name: row.page_name,
      page_sequence: row.page_sequence,
      title: row.title,
      source_fingerprint: row.source_fingerprint,
      required: row.required,
      review_status: row.review_status,
      expected: row.expected,
    }));
    const reviewedCount = selected.filter((row) => row.review_status === "reviewed").length;
    return {
      schema_version: 1,
      benchmark_id: dataset.benchmark_id,
      status: reviewedCount === selected.length ? "approved" : "draft",
      source_dates: dataset.source_dates,
      target_count: selected.length,
      reviewed_count: reviewedCount,
      items: selected,
    };
  }

  function currentRows() {
    const term = search.value.trim().toLocaleLowerCase("zh-CN");
    return rows.filter((row) => {
      if (filter === "selected" && !row.selected) return false;
      if (filter === "draft" && (!row.selected || row.review_status === "reviewed")) return false;
      if (!term) return true;
      return [row.candidate_id, row.title, row.content, row.page_name]
        .join("\n").toLocaleLowerCase("zh-CN").includes(term);
    });
  }

  function renderProgress() {
    const selected = rows.filter((row) => row.selected);
    const reviewed = selected.filter((row) => row.review_status === "reviewed");
    const required = rows.filter((row) => row.required);
    const requiredReviewed = required.filter((row) => row.review_status === "reviewed");
    app.querySelector("[data-progress-reviewed]").textContent = reviewed.length;
    app.querySelector("[data-progress-selected]").textContent = selected.length;
    app.querySelector("[data-progress-required]").textContent = `${requiredReviewed.length} / ${required.length}`;
    app.querySelector("[data-progress-bar]").style.width = `${selected.length ? reviewed.length / selected.length * 100 : 0}%`;
  }

  function renderQueue() {
    const visible = currentRows();
    const groups = new Map();
    visible.forEach((row) => {
      if (!groups.has(row.published_date)) groups.set(row.published_date, []);
      groups.get(row.published_date).push(row);
    });
    queue.innerHTML = [...groups.entries()].map(([date, items]) => `
      <div class="queue-date">${escapeHtml(date)} · ${items.length} 条</div>
      ${items.map((row) => `
        <button type="button" class="queue-item ${row.item_id === activeId ? "active" : ""} ${row.review_status === "reviewed" ? "reviewed" : ""} ${row.required ? "required" : ""}" data-open-item="${escapeHtml(row.item_id)}">
          <span class="queue-id">${escapeHtml(row.candidate_id)}</span>
          <span class="queue-copy"><strong>${escapeHtml(row.title)}</strong><span>${escapeHtml(row.page_name)} · 第 ${row.page_sequence} 条${row.selected ? " · 已选" : ""}</span></span>
          <span class="status-dot" aria-hidden="true"></span>
        </button>`).join("")}
    `).join("") || '<div class="empty-panel">没有符合当前条件的文章。</div>';
  }

  function tagList(rows, fallback = "暂无") {
    if (!Array.isArray(rows) || !rows.length) return `<span class="tag">${fallback}</span>`;
    return rows.map((row) => `<span class="tag">${escapeHtml(row.name || row.location_id || row.topic_id || row)}</span>`).join("");
  }

  function renderSource(row) {
    const relation = row.current.event_relation || {};
    sourcePanel.innerHTML = `
      <header class="source-header">
        <div class="source-meta"><strong>${escapeHtml(row.candidate_id)}</strong><span>${escapeHtml(row.published_date)}</span><span>${escapeHtml(row.page_name)} · ${escapeHtml(row.page_number)}版</span><a href="${escapeHtml(row.detail_path)}" target="_blank">打开站内详情 ↗</a></div>
        <h2>${escapeHtml(row.title)}</h2>
      </header>
      <section class="source-block">
        <header><h3>当前结构化结果</h3><span>${escapeHtml(row.current.scope || "未分类")}</span></header>
        <div class="current-card"><p>${escapeHtml(row.current.ai_summary || "暂无摘要")}</p>
          <div class="tag-row">${tagList(row.current.subjects)}${tagList(row.current.locations)}${tagList(row.current.topics)}</div>
          <div class="tag-row"><span class="tag">事件：${escapeHtml(relation.relation || "none")}${relation.event_name ? ` · ${escapeHtml(relation.event_name)}` : ""}</span></div>
        </div>
        ${row.candidates.events.length === 0 ? '<div class="candidate-warning">当前 event_candidates 为空。基准预期仍可录入原文明示的新活动。</div>' : ""}
      </section>
      <section class="source-block">
        <header><h3>海南地点候选</h3><span>${row.candidates.locations.length} 个</span></header>
        <div class="tag-row">${tagList(row.candidates.locations, "没有命中海南行政区")}</div>
      </section>
      <section class="source-block">
        <header><h3>海南日报原文</h3><a href="${escapeHtml(row.original_url)}" target="_blank">报社原文 ↗</a></header>
        <div class="source-content">${escapeHtml(row.content)}</div>
      </section>`;
  }

  function subjectRows(values) {
    return (values.length ? values : [{name: "", type: "person", role: ""}]).map((value, index) => `
      <div class="edit-row subject-row" data-subject-row>
        <input value="${escapeHtml(value.name)}" placeholder="姓名/机构" data-subject-field="name">
        <select data-subject-field="type">${["person", "government", "organization", "company"].map((type) => `<option value="${type}" ${value.type === type ? "selected" : ""}>${type}</option>`).join("")}</select>
        <input value="${escapeHtml(value.role)}" placeholder="本篇身份" data-subject-field="role">
        <button type="button" class="remove-row" data-remove-subject="${index}" aria-label="删除主体">×</button>
      </div>`).join("");
  }

  function eventRows(values) {
    return values.map((value, index) => `
      <div class="edit-row event-row" data-event-row>
        <input value="${escapeHtml(value.name)}" placeholder="本次活动名称" data-event-field="name">
        <select data-event-field="kind"><option value="event_occurrence" ${value.kind === "event_occurrence" ? "selected" : ""}>本届/本次活动</option><option value="event_series" ${value.kind === "event_series" ? "selected" : ""}>活动系列</option><option value="incident" ${value.kind === "incident" ? "selected" : ""}>持续事件</option></select>
        <input value="${escapeHtml(value.series_name)}" placeholder="所属活动系列" data-event-field="series_name">
        <button type="button" class="remove-row" data-remove-event="${index}" aria-label="删除活动">×</button>
      </div>`).join("");
  }

  function projectRows(values) {
    return values.map((value, index) => `
      <div class="edit-row project-row" data-project-row><input value="${escapeHtml(value.name)}" placeholder="项目规范名称" data-project-field="name"><button type="button" class="remove-row" data-remove-project="${index}" aria-label="删除项目">×</button></div>`).join("");
  }

  function factRows(values) {
    return values.map((value, index) => `
      <div class="edit-row fact-row" data-fact-row>
        <input type="date" value="${escapeHtml(value.occurred_on)}" data-fact-field="occurred_on">
        <input value="${escapeHtml(joinValues(value.actors))}" placeholder="行动者，逗号分隔" data-fact-field="actors">
        <input value="${escapeHtml(value.action)}" placeholder="做了什么" data-fact-field="action">
        <button type="button" class="remove-row" data-remove-fact="${index}" aria-label="删除事实">×</button>
        <input class="wide" value="${escapeHtml(value.object)}" placeholder="行动对象/事项" data-fact-field="object">
        <input class="wide" value="${escapeHtml(joinValues(value.locations))}" placeholder="发生地点，逗号分隔" data-fact-field="locations">
        <textarea class="wide" placeholder="供人物或项目页面使用的一句话事实" data-fact-field="summary">${escapeHtml(value.summary)}</textarea>
      </div>`).join("");
  }

  function renderEditor(row) {
    const selectedLocations = new Set(row.expected.locations.map((item) => item.location_id));
    editorPanel.innerHTML = `
      <div class="editor-top"><h2>预期结果</h2><label class="sample-toggle"><input type="checkbox" data-selected ${row.selected ? "checked" : ""} ${row.required ? "disabled" : ""}>纳入基准${row.required ? "（强制）" : ""}</label></div>
      <div class="review-state"><button type="button" data-review-state="draft" class="${row.review_status === "draft" ? "active" : ""}">继续整理</button><button type="button" data-review-state="reviewed" class="${row.review_status === "reviewed" ? "active" : ""}">确认完成</button></div>
      <section class="field-section"><header><h3>主要行动主体</h3><span>不会因背景提及进入人物轨迹</span></header><p class="field-help">只填写在本篇中实施、宣布、致辞、调研或直接承担行动的人与机构。</p><div class="row-list" data-subject-list>${subjectRows(row.expected.primary_subjects)}</div><button type="button" class="add-row" data-add-subject>＋ 添加主体</button></section>
      <section class="field-section"><header><h3>背景提及</h3><span>逗号分隔</span></header><p class="field-help">原文出现但不应形成本文人物行动节点的名字。</p><input value="${escapeHtml(joinValues(row.expected.background_mentions))}" data-background placeholder="例如：习近平"></section>
      <section class="field-section"><header><h3>海南行政区</h3><span>来自候选表</span></header><div class="check-grid">${row.candidates.locations.map((item) => `<label class="check-chip"><input type="checkbox" data-location-id="${escapeHtml(item.location_id)}" data-location-name="${escapeHtml(item.name)}" ${selectedLocations.has(item.location_id) ? "checked" : ""}><span>${escapeHtml(item.name)}</span></label>`).join("") || '<span class="tag">没有海南地点候选</span>'}</div></section>
      <section class="field-section"><header><h3>命名活动 / 事件</h3><span>允许候选外的新活动</span></header><p class="field-help">区分具体届次和长期活动系列，例如“2026年欢乐节”与“海南国际旅游岛欢乐节”。</p><div class="row-list" data-event-list>${eventRows(row.expected.named_events)}</div><button type="button" class="add-row" data-add-event>＋ 添加活动</button></section>
      <section class="field-section"><header><h3>长期项目</h3><span>可持续积累</span></header><div class="row-list" data-project-list>${projectRows(row.expected.projects)}</div><button type="button" class="add-row" data-add-project>＋ 添加项目</button></section>
      <section class="field-section"><header><h3>人物 / 项目事实</h3><span>一条报道可有多条</span></header><p class="field-help">填写实际发生日期，不要只使用报纸出版日期。</p><div class="row-list" data-fact-list>${factRows(row.expected.facts)}</div><button type="button" class="add-row" data-add-fact>＋ 添加事实</button></section>
      <section class="field-section"><header><h3>审核备注</h3></header><textarea data-notes placeholder="记录为什么这样判断，便于转成提示词规则">${escapeHtml(row.expected.notes)}</textarea></section>
      <div class="nav-buttons"><button type="button" data-prev>← 上一条</button><button type="button" data-next>下一条 →</button></div>`;
  }

  function activeRow() { return rows.find((row) => row.item_id === activeId); }

  function collectEditor() {
    const row = activeRow();
    if (!row || !editorPanel.children.length) return;
    row.expected.primary_subjects = [...editorPanel.querySelectorAll("[data-subject-row]")].map((element) => ({
      name: element.querySelector('[data-subject-field="name"]').value.trim(),
      type: element.querySelector('[data-subject-field="type"]').value,
      role: element.querySelector('[data-subject-field="role"]').value.trim(),
    })).filter((item) => item.name);
    row.expected.background_mentions = splitValues(editorPanel.querySelector("[data-background]").value);
    row.expected.locations = [...editorPanel.querySelectorAll("[data-location-id]:checked")].map((element) => ({location_id: element.dataset.locationId, name: element.dataset.locationName}));
    row.expected.named_events = [...editorPanel.querySelectorAll("[data-event-row]")].map((element) => ({
      name: element.querySelector('[data-event-field="name"]').value.trim(),
      kind: element.querySelector('[data-event-field="kind"]').value,
      series_name: element.querySelector('[data-event-field="series_name"]').value.trim(),
    })).filter((item) => item.name);
    row.expected.projects = [...editorPanel.querySelectorAll("[data-project-row]")].map((element) => ({name: element.querySelector('[data-project-field="name"]').value.trim()})).filter((item) => item.name);
    row.expected.facts = [...editorPanel.querySelectorAll("[data-fact-row]")].map((element) => ({
      occurred_on: element.querySelector('[data-fact-field="occurred_on"]').value,
      actors: splitValues(element.querySelector('[data-fact-field="actors"]').value),
      action: element.querySelector('[data-fact-field="action"]').value.trim(),
      object: element.querySelector('[data-fact-field="object"]').value.trim(),
      locations: splitValues(element.querySelector('[data-fact-field="locations"]').value),
      summary: element.querySelector('[data-fact-field="summary"]').value.trim(),
    })).filter((item) => item.action || item.summary);
    row.expected.notes = editorPanel.querySelector("[data-notes]").value.trim();
    persistLocal();
  }

  function openRow(itemId) {
    collectEditor();
    activeId = itemId;
    const row = activeRow();
    if (!row) return;
    renderQueue(); renderSource(row); renderEditor(row); renderProgress();
  }

  function move(offset) {
    collectEditor();
    const visible = currentRows();
    const index = visible.findIndex((row) => row.item_id === activeId);
    const next = visible[index + offset];
    if (next) openRow(next.item_id);
  }

  queue.addEventListener("click", (event) => {
    const button = event.target.closest("[data-open-item]");
    if (button) openRow(button.dataset.openItem);
  });
  search.addEventListener("input", renderQueue);
  app.querySelector("[data-queue-filter]").addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    filter = button.dataset.filter;
    app.querySelectorAll("[data-filter]").forEach((item) => item.classList.toggle("active", item === button));
    renderQueue();
  });

  editorPanel.addEventListener("input", () => { collectEditor(); renderProgress(); });
  editorPanel.addEventListener("click", (event) => {
    const row = activeRow();
    if (!row) return;
    if (event.target.closest("[data-review-state]")) {
      collectEditor();
      row.review_status = event.target.closest("[data-review-state]").dataset.reviewState;
      persistLocal(); renderEditor(row); renderQueue(); renderProgress();
    } else if (event.target.closest("[data-add-subject]")) {
      collectEditor(); row.expected.primary_subjects.push({name:"",type:"person",role:""}); renderEditor(row);
    } else if (event.target.closest("[data-add-event]")) {
      collectEditor(); row.expected.named_events.push({name:"",kind:"event_occurrence",series_name:""}); renderEditor(row);
    } else if (event.target.closest("[data-add-project]")) {
      collectEditor(); row.expected.projects.push({name:""}); renderEditor(row);
    } else if (event.target.closest("[data-add-fact]")) {
      collectEditor(); row.expected.facts.push({occurred_on:row.published_date,actors:[],action:"",object:"",locations:[],summary:""}); renderEditor(row);
    } else if (event.target.closest("[data-remove-subject]")) {
      collectEditor(); row.expected.primary_subjects.splice(Number(event.target.closest("[data-remove-subject]").dataset.removeSubject),1); renderEditor(row);
    } else if (event.target.closest("[data-remove-event]")) {
      collectEditor(); row.expected.named_events.splice(Number(event.target.closest("[data-remove-event]").dataset.removeEvent),1); renderEditor(row);
    } else if (event.target.closest("[data-remove-project]")) {
      collectEditor(); row.expected.projects.splice(Number(event.target.closest("[data-remove-project]").dataset.removeProject),1); renderEditor(row);
    } else if (event.target.closest("[data-remove-fact]")) {
      collectEditor(); row.expected.facts.splice(Number(event.target.closest("[data-remove-fact]").dataset.removeFact),1); renderEditor(row);
    } else if (event.target.closest("[data-prev]")) move(-1);
    else if (event.target.closest("[data-next]")) move(1);
  });
  editorPanel.addEventListener("change", (event) => {
    const row = activeRow();
    if (event.target.matches("[data-selected]") && row) {
      row.selected = row.required ? true : event.target.checked;
      persistLocal(); renderQueue(); renderProgress();
    }
  });

  app.querySelector("[data-export]").addEventListener("click", () => {
    collectEditor();
    const blob = new Blob([JSON.stringify(exportPayload(), null, 2) + "\n"], {type:"application/json"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob); link.download = `${dataset.benchmark_id}.json`; link.click();
    URL.revokeObjectURL(link.href);
  });
  app.querySelector("[data-import]").addEventListener("click", () => app.querySelector("[data-import-file]").click());
  app.querySelector("[data-import-file]").addEventListener("change", async (event) => {
    const file = event.target.files[0]; if (!file) return;
    try {
      const payload = JSON.parse(await file.text());
      if (payload.benchmark_id !== dataset.benchmark_id || !Array.isArray(payload.items)) throw new Error("基准文件不匹配");
      const imported = new Map(payload.items.map((row) => [row.item_id, row]));
      rows.forEach((row) => {
        const value = imported.get(row.item_id);
        row.selected = row.required || Boolean(value);
        if (value) { row.review_status = value.review_status; row.expected = value.expected; }
      });
      persistLocal(); openRow(activeId); saveState.textContent = `已导入 ${payload.items.length} 条基准`;
    } catch (error) { saveState.textContent = `导入失败：${error.message}`; }
    event.target.value = "";
  });
  app.querySelector("[data-save-repo]").addEventListener("click", async () => {
    collectEditor();
    saveState.textContent = "正在保存……";
    try {
      const response = await fetch("/api/evaluation-gold", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(exportPayload())});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      lastRepoSignature = JSON.stringify(exportPayload());
      saveState.textContent = `已保存：${result.path}`;
    } catch (error) { saveState.textContent = `保存失败：${error.message}`; }
  });

  fetch(window.HNHOT_GOLD_DATA_URL).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }).then((value) => {
    dataset = value; rows = clone(value.items);
    rows.forEach((row) => { row.repository_expected = clone(row.expected); });
    lastRepoSignature = JSON.stringify(exportPayload());
    restoreLocal();
    persistLocal();
    const firstRequired = rows.find((row) => row.required) || rows.find((row) => row.selected) || rows[0];
    activeId = firstRequired?.item_id || null;
    renderQueue(); renderProgress(); if (firstRequired) { renderSource(firstRequired); renderEditor(firstRequired); }
  }).catch((error) => { sourcePanel.innerHTML = `<div class="empty-panel">审核数据加载失败：${escapeHtml(error.message)}</div>`; });
})();
