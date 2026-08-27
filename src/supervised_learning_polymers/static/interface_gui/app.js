const state = {
  artifact: null,
  failureFilter: "all",
  metricFilter: "all",
  structureFilter: "all",
  structureQuery: "",
  structureRows: [],
  selectedStructureId: null,
  failureTriage: null,
  selectedFailureDomain: null,
  selectedFailureType: null,
  selectedFailureSampleId: null,
};

const nativeFetch = (window.__nativeFetch || window.fetch).bind(window);

const text = (value) => document.createTextNode(value);

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function clear(element) {
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

function field(label, value) {
  const row = document.createElement("div");
  row.className = "field";
  const key = document.createElement("span");
  key.className = "field-label";
  key.appendChild(text(label));
  const val = document.createElement("span");
  val.appendChild(text(value));
  row.append(key, val);
  return row;
}

function badge(value, className = "") {
  const span = document.createElement("span");
  span.className = className ? `badge ${className}` : "badge";
  span.appendChild(text(value));
  return span;
}

function smilesVariantField(variant) {
  const row = document.createElement("div");
  row.className = "field smiles-variant";
  row.dataset.state = variant.state;
  const key = document.createElement("span");
  key.className = "field-label";
  key.append(text(variant.label), badge(variant.state, `badge-${variant.state}`));
  const val = document.createElement("code");
  val.appendChild(text(variant.value || "n/a"));
  row.append(key, val);
  return row;
}

function renderList(id, rows) {
  const element = document.getElementById(id);
  clear(element);
  rows.forEach((row) => element.appendChild(row));
}

function renderTable(id, rows, renderRow) {
  const body = document.getElementById(id);
  clear(body);
  rows.forEach((row) => body.appendChild(renderRow(row)));
}

function cell(value, className = "") {
  const td = document.createElement("td");
  if (className) td.className = className;
  td.appendChild(text(value));
  return td;
}

function buttonCell(label, onClick) {
  const td = document.createElement("td");
  td.appendChild(actionButton(label, onClick));
  return td;
}

function actionButton(label, onClick, className = "link-button") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.appendChild(text(label));
  button.addEventListener("click", onClick);
  return button;
}

function statusChip(value) {
  const span = document.createElement("span");
  span.className = "status-chip";
  span.dataset.status = value;
  span.appendChild(text(statusLabel(value)));
  return span;
}

function statusLabel(value) {
  return value.replaceAll("_", " ");
}

function renderArtifact(artifact) {
  const run = artifact.run_metadata;
  const target = artifact.target_mode_summary;
  const manifest = artifact.manifest;
  const chemistry = artifact.chemistry_failure_summary;
  const geometry = artifact.geometry_summary;
  const results = artifact.result_summary;

  setText("run-title", run.display_name);
  setText("run-status", run.status);
  document.getElementById("run-status").dataset.status = run.status;

  renderList("target-mode", [
    field("Mode", target.mode),
    field("Selected", target.selected_targets.join(", ")),
    field("Order", target.sequential_order.length ? target.sequential_order.join(" -> ") : "n/a"),
    field("Description", target.description),
  ]);

  renderList("provenance", [
    field("Dataset", manifest.dataset.dataset_version),
    field("Chemistry", manifest.chemistry.config_id),
    field("Representation", manifest.representation.config_id),
    field("Split", manifest.split.config_id),
    field("Model", manifest.model.config_id),
    field("Reporting", manifest.reporting.config_id),
  ]);

  renderList("chemistry-summary", [
    field("Total", chemistry.total_records.toLocaleString()),
    field("Valid", chemistry.valid_records.toLocaleString()),
    field("Failed", chemistry.failed_records.toLocaleString()),
  ]);

  renderFailureFilter(chemistry.failure_groups);
  renderFailureRows();
  renderGeometrySummary(geometry);

  renderList(
    "run-progress",
    run.progress_steps.map((step) =>
      field(step.name, `${step.status} ${step.completed_units}/${step.total_units}`),
    ),
  );

  renderList(
    "artifact-paths",
    Object.entries(run.artifact_paths)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([name, path]) => field(name, path)),
  );

  renderMetricFilter(results.metric_metadata);
  renderMetricRows();
  renderMetricSummary();
  renderLeaderboardRows();
  loadFailureTriage();
  loadStructures();
}

function renderGeometrySummary(geometry) {
  if (!geometry) {
    renderList("geometry-summary", [field("Status", "Not available")]);
    renderTable("geometry-failure-rows", [], (group) => group);
    return;
  }

  renderList("geometry-summary", [
    field("Inputs", geometry.total_chemistry_valid_records.toLocaleString()),
    field("Success", geometry.successful_records.toLocaleString()),
    field("Failed", geometry.failed_records.toLocaleString()),
    field("Coverage", `${(geometry.coverage_fraction * 100).toFixed(2)}%`),
  ]);

  renderTable("geometry-failure-rows", geometry.failure_groups, (group) => {
    const tr = document.createElement("tr");
    tr.append(
      buttonCell(group.failure_type, () => openFailureGroup("geometry", group.failure_type)),
      cell(group.count, "num"),
      failureExamplesCell(group.example_sample_ids, "geometry", group.failure_type),
      cell(group.recommended_action),
    );
    return tr;
  });
}

function renderLeaderboardRows() {
  const results = state.artifact.result_summary;
  const entries = results.leaderboard.filter(
    (entry) => state.metricFilter === "all" || entry.primary_metric === state.metricFilter,
  );
  renderTable("leaderboard-rows", entries, (entry) => {
    const tr = document.createElement("tr");
    tr.append(
      cell(entry.rank, "num"),
      cell(entry.run_id),
      cell(entry.model_family),
      cell(entry.target_mode),
      cell(
        Number(entry.primary_score).toLocaleString(undefined, { maximumSignificantDigits: 4 }),
        "num",
      ),
    );
    return tr;
  });
}

function renderMetricFilter(metadataRows) {
  const select = document.getElementById("metric-filter");
  const current = select.value;
  clear(select);
  const all = document.createElement("option");
  all.value = "all";
  all.appendChild(text("All metrics"));
  select.appendChild(all);
  metadataRows.forEach((metadata) => {
    const option = document.createElement("option");
    option.value = metadata.metric;
    option.appendChild(text(metadata.display_name));
    select.appendChild(option);
  });
  select.value = [...select.options].some((option) => option.value === current) ? current : "all";
}

function renderMetricRows() {
  const results = state.artifact.result_summary;
  const metrics = results.metrics.filter(
    (metric) => state.metricFilter === "all" || metric.metric === state.metricFilter,
  );
  renderTable("metric-rows", metrics, (metric) => {
    const tr = document.createElement("tr");
    tr.append(
      cell(metric.target || metric.scope),
      cell(metric.split),
      cell(metric.metric),
      cell(metric.scope),
      cell(Number(metric.value).toLocaleString(undefined, { maximumSignificantDigits: 4 }), "num"),
    );
    return tr;
  });
}

function renderMetricSummary() {
  const results = state.artifact.result_summary;
  const metadataRows = results.metric_metadata.filter(
    (metadata) => state.metricFilter === "all" || metadata.metric === state.metricFilter,
  );
  renderList(
    "metric-summary",
    metadataRows.map((metadata) => {
      const weightDetails = metadata.target_weights.length
        ? ` Weights: ${metadata.target_weights
            .map((weight) => `${weight.target}=${weight.weight}`)
            .join(", ")}.`
        : "";
      return field(metadata.display_name, `${metadata.description}${weightDetails}`);
    }),
  );
}

function renderFailureFilter(groups) {
  const select = document.getElementById("failure-filter");
  const current = select.value;
  clear(select);
  const all = document.createElement("option");
  all.value = "all";
  all.appendChild(text("All failures"));
  select.appendChild(all);
  groups.forEach((group) => {
    const option = document.createElement("option");
    option.value = group.failure_type;
    option.appendChild(text(group.failure_type));
    select.appendChild(option);
  });
  select.value = [...select.options].some((option) => option.value === current) ? current : "all";
}

function renderFailureRows() {
  const groups = state.artifact.chemistry_failure_summary.failure_groups.filter(
    (group) => state.failureFilter === "all" || group.failure_type === state.failureFilter,
  );
  renderTable("failure-rows", groups, (group) => {
    const tr = document.createElement("tr");
    tr.append(
      buttonCell(group.failure_type, () => openFailureGroup("chemistry", group.failure_type)),
      cell(group.count, "num"),
      failureExamplesCell(group.example_sample_ids, "chemistry", group.failure_type),
      cell(group.recommended_action),
    );
    return tr;
  });
}

function loadFailureTriage() {
  nativeFetch("/api/structure-failures")
    .then((response) => {
      if (!response.ok) throw new Error(`Failure triage request failed: ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      state.failureTriage = payload;
      const firstGroup = payload.groups[0];
      if (firstGroup && !state.selectedFailureType) {
        state.selectedFailureDomain = firstGroup.domain;
        state.selectedFailureType = firstGroup.failure_type;
      }
      renderFailureTriage();
    })
    .catch((error) => {
      renderList("triage-detail-panel", [field("Status", error.message)]);
      renderTable("triage-group-rows", [], (group) => group);
      renderTable("triage-example-rows", [], (example) => example);
    });
}

function openFailureGroup(domain, failureType, sampleId = null) {
  state.selectedFailureDomain = domain;
  state.selectedFailureType = failureType;
  state.selectedFailureSampleId = sampleId;
  renderFailureTriage();

  const group = selectedFailureGroup();
  if (group) {
    state.structureFilter = group.structure_filter;
    document.getElementById("structure-filter").value = group.structure_filter;
  }
  state.structureQuery = sampleId || "";
  document.getElementById("structure-search").value = state.structureQuery;
  loadStructures();
  document.getElementById("structure-browser").scrollIntoView({ block: "start" });
}

function selectedFailureGroup() {
  if (!state.failureTriage || !state.selectedFailureType) return null;
  return state.failureTriage.groups.find(
    (group) =>
      group.domain === state.selectedFailureDomain
      && group.failure_type === state.selectedFailureType,
  );
}

function selectedFailureExamples() {
  if (!state.failureTriage || !state.selectedFailureType) return [];
  return state.failureTriage.examples.filter(
    (example) =>
      example.domain === state.selectedFailureDomain
      && example.failure_type === state.selectedFailureType,
  );
}

function selectedFailureExample() {
  const examples = selectedFailureExamples();
  if (state.selectedFailureSampleId) {
    return examples.find((example) => example.sample_id === state.selectedFailureSampleId) || examples[0];
  }
  return examples[0] || null;
}

function renderFailureTriage() {
  if (!state.failureTriage) {
    renderList("triage-detail-panel", [field("Status", "Loading failure triage")]);
    return;
  }

  renderTriagePatternGuide();
  renderTable("triage-group-rows", state.failureTriage.groups, (group) => {
    const tr = document.createElement("tr");
    if (
      group.domain === state.selectedFailureDomain
      && group.failure_type === state.selectedFailureType
    ) {
      tr.className = "selected-row";
    }
    tr.append(
      buttonCell(
        `${group.domain}: ${group.failure_type}`,
        () => openFailureGroup(group.domain, group.failure_type),
      ),
      cell(group.count, "num"),
      failureExamplesCell(group.example_sample_ids, group.domain, group.failure_type),
      cell(group.recommended_action),
    );
    return tr;
  });

  const examples = selectedFailureExamples();
  renderTable("triage-example-rows", examples, (example) => {
    const tr = document.createElement("tr");
    if (example.sample_id === state.selectedFailureSampleId) tr.className = "selected-row";
    tr.append(
      buttonCell(
        example.sample_id,
        () => openFailureGroup(example.domain, example.failure_type, example.sample_id),
      ),
      cell(example.stage),
      cell(example.method || "n/a"),
      cell(example.structure_detail_available ? "structure record" : "failure file only"),
    );
    return tr;
  });

  const example = selectedFailureExample();
  if (!example) {
    renderList("triage-detail-panel", [field("Status", "Select a failure group")]);
    return;
  }

  const detailRows = [
    field("Sample", example.sample_id),
    field("Domain", example.domain),
    field("Failure", example.failure_type),
    field("Stage", example.stage),
    field("Method", example.method || "n/a"),
    field("Message", example.message),
    field("Action", example.recommended_action),
    field("Raw", example.raw_smiles || "n/a"),
    field("Canonical", example.canonical_smiles || "n/a"),
    field("Standardized", example.standardized_smiles || "n/a"),
    field("Capped", example.capped_smiles || "n/a"),
    field("Selected input", example.selected_input_smiles || "n/a"),
    field("Input representation", example.selected_input_representation || "n/a"),
    field("Attachment points", example.attachment_points.length ? example.attachment_points.join(", ") : "none"),
    field("Runtime", example.runtime_seconds === null ? "n/a" : `${example.runtime_seconds}s`),
    field("Source", example.structure_detail_available ? "failure file + structure record" : "failure file"),
  ];
  example.fallback_provenance.forEach((fallback) => {
    detailRows.push(
      field(
        `Fallback ${fallback.method_name}`,
        `${fallback.status}: ${fallback.reason}`,
      ),
    );
  });
  renderList("triage-detail-panel", detailRows);
}

function renderTriagePatternGuide() {
  const guide = document.getElementById("triage-pattern-guide");
  clear(guide);
  const observedTypes = new Set(state.failureTriage.groups.map((group) => group.failure_type));
  state.failureTriage.pattern_reference.forEach((failureType) => {
    guide.appendChild(badge(failureType, observedTypes.has(failureType) ? "badge-selected" : "badge-missing"));
  });
}

function failureExamplesCell(sampleIds, domain, failureType) {
  const td = document.createElement("td");
  if (!sampleIds.length) {
    td.appendChild(text("n/a"));
    return td;
  }
  const list = document.createElement("div");
  list.className = "example-links";
  sampleIds.forEach((sampleId) => {
    list.appendChild(actionButton(sampleId, () => openFailureGroup(domain, failureType, sampleId)));
  });
  td.appendChild(list);
  return td;
}

function structureQueryString() {
  const params = new URLSearchParams();
  if (state.structureQuery.trim()) params.set("query", state.structureQuery.trim());
  if (state.structureFilter !== "all") params.set("status", state.structureFilter);
  const query = params.toString();
  return query ? `?${query}` : "";
}

function setStructureState(message, mode = "info") {
  const element = document.getElementById("structure-state");
  element.textContent = message;
  element.dataset.state = mode;
}

function loadStructures() {
  setStructureState("Loading structures");
  nativeFetch(`/api/structures${structureQueryString()}`)
    .then((response) => {
      if (!response.ok) throw new Error(`Structure request failed: ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      state.structureRows = payload.records;
      renderStructureRows(payload.records);
      if (!payload.records.length) {
        setStructureState("No structures match the current search and status filter", "empty");
        renderEmptyStructureDetail();
        return;
      }
      setStructureState(
        `${payload.returned_records.toLocaleString()} of ${payload.total_records.toLocaleString()} structures`,
      );
      const selected = payload.records.find(
        (record) => record.sample_id === state.selectedStructureId,
      );
      selectStructure((selected || payload.records[0]).sample_id);
    })
    .catch((error) => {
      setStructureState(error.message, "error");
      renderStructureRows([]);
      renderEmptyStructureDetail();
    });
}

function renderStructureRows(records) {
  renderTable("structure-rows", records, (record) => {
    const tr = document.createElement("tr");
    if (record.sample_id === state.selectedStructureId) tr.className = "selected-row";
    tr.append(
      buttonCell(record.sample_id, () => selectStructure(record.sample_id)),
      cell(statusLabel(record.chemistry_status)),
      cell(statusLabel(record.geometry_status)),
      cell(record.display_smiles || "n/a", "smiles-cell"),
    );
    return tr;
  });
}

function selectStructure(sampleId) {
  state.selectedStructureId = sampleId;
  nativeFetch(`/api/structures/${encodeURIComponent(sampleId)}`)
    .then((response) => {
      if (!response.ok) throw new Error(`Structure detail failed: ${response.status}`);
      return response.json();
    })
    .then((detail) => renderStructureDetail(detail))
    .catch((error) => {
      setStructureState(error.message, "error");
      renderEmptyStructureDetail();
    });
}

function renderStructureDetail(detail) {
  setText("structure-selected-title", detail.sample_id);
  const selectedStatus = document.getElementById("structure-selected-status");
  selectedStatus.textContent = statusLabel(detail.geometry.status);
  selectedStatus.dataset.status = detail.geometry.status;

  renderList("structure-smiles-panel", [
    ...detail.smiles.variants.map((variant) => smilesVariantField(variant)),
    field(
      "Attachment points",
      detail.smiles.attachment_points.length ? detail.smiles.attachment_points.join(", ") : "none",
    ),
  ]);
  renderDepictionPanel(detail);
  renderConformerPanel(detail);

  const statusRows = [
    field("Chemistry", detail.chemistry_status),
    field("Geometry", statusLabel(detail.geometry.status)),
    field("2D", statusLabel(detail.depiction.status)),
  ];
  if (detail.geometry.method) {
    statusRows.push(
      field("Method", detail.geometry.method.method_name || "n/a"),
      field("Embedding", detail.geometry.method.embedding_status || "n/a"),
      field("Optimization", detail.geometry.method.optimization_status || "n/a"),
    );
  }
  if (detail.geometry.timing) {
    statusRows.push(field("Runtime", `${detail.geometry.timing.runtime_seconds}s`));
  }
  if (detail.geometry.failure) {
    statusRows.push(
      field("Failure", detail.geometry.failure.failure_type),
      field("Stage", detail.geometry.failure.stage),
      field("Message", detail.geometry.failure.message),
      field("Action", detail.geometry.failure.recommended_action),
    );
  } else if (detail.chemistry_failure) {
    statusRows.push(
      field("Failure", detail.chemistry_failure.failure_type),
      field("Stage", detail.chemistry_failure.stage),
      field("Message", detail.chemistry_failure.message),
    );
  }
  detail.geometry.fallback_provenance.forEach((fallback) => {
    statusRows.push(
      field(
        `Fallback ${fallback.method_name}`,
        `${fallback.status}: ${fallback.reason}`,
      ),
    );
  });
  renderList("structure-status-panel", statusRows);

  renderList("structure-provenance-panel", [
    field("Chemistry config", detail.provenance.chemistry_config_id),
    field("Geometry config", detail.provenance.geometry_config_id || "n/a"),
    field("Chemistry records", detail.provenance.chemistry_records_path || "n/a"),
    field("Geometry records", detail.provenance.geometry_records_path || "n/a"),
  ]);

  renderList("structure-panel-states", [
    field("SMILES", detail.chemistry_status === "valid" ? "available" : "failed upstream"),
    field("2D", statusLabel(detail.depiction.status)),
    field(
      "3D",
      detail.geometry.status === "success" ? "SDF payload available" : statusLabel(detail.geometry.status),
    ),
    field("Graph", "not yet generated"),
  ]);

  renderStructureRows(state.structureRows);
}

function renderConformerPanel(detail) {
  const panel = document.getElementById("structure-3d-panel");
  clear(panel);
  if (detail.geometry.status !== "success" || !detail.geometry.sdf_text) {
    const rows = [
      field("Status", statusLabel(detail.geometry.status)),
    ];
    if (detail.geometry.failure) {
      rows.push(
        field("Failure", detail.geometry.failure.failure_type),
        field("Stage", detail.geometry.failure.stage),
        field("Method", detail.geometry.failure.method),
        field("Message", detail.geometry.failure.message),
        field("Action", detail.geometry.failure.recommended_action),
      );
    }
    if (detail.geometry.timing) {
      rows.push(field("Runtime", `${detail.geometry.timing.runtime_seconds}s`));
    }
    if (!detail.geometry.failure) {
      rows.push(field("SDF", "unavailable"));
      rows.push(field("Action", geometryUnavailableAction(detail.geometry.status)));
    }
    rows.forEach((row) => panel.appendChild(row));
    return;
  }

  const threeDmol = window.$3Dmol || window["3Dmol"];
  if (!threeDmol) {
    panel.appendChild(field("Status", "3Dmol asset unavailable"));
    return;
  }

  const viewerElement = document.createElement("div");
  viewerElement.className = "molecule-viewer";
  viewerElement.setAttribute("aria-label", `3D conformer for ${detail.sample_id}`);
  panel.appendChild(viewerElement);

  const viewer = threeDmol.createViewer(viewerElement, {
    backgroundColor: "white",
  });
  viewer.addModel(detail.geometry.sdf_text, "sdf");
  viewer.setStyle({}, { stick: { radius: 0.14 }, sphere: { scale: 0.22 } });
  viewer.zoomTo();
  viewer.render();
}

function geometryUnavailableAction(status) {
  if (status === "not_generated") {
    return "Generate geometry artifacts for this sample to view a 3D conformer.";
  }
  if (status === "artifact_missing") {
    return "Resolve the geometry records artifact path for this run.";
  }
  if (status === "chemistry_failed") {
    return "Fix the upstream chemistry record before geometry can be generated.";
  }
  return "Inspect upstream artifact provenance for this sample.";
}

function renderDepictionPanel(detail) {
  const panel = document.getElementById("structure-2d-panel");
  clear(panel);
  if (detail.depiction.status !== "available") {
    const rows = [
      field("Status", statusLabel(detail.depiction.status)),
      field("Action", detail.depiction.failure?.recommended_action || "Inspect upstream artifacts"),
    ];
    if (detail.depiction.failure) {
      rows.splice(1, 0, field("Message", detail.depiction.failure.message));
    }
    rows.forEach((row) => panel.appendChild(row));
    return;
  }

  const image = document.createElement("img");
  image.alt = `2D structure for ${detail.sample_id}`;
  image.src = detail.depiction.payload_ref;
  image.addEventListener("error", () => {
    clear(panel);
    panel.appendChild(field("Status", "render failed"));
    panel.appendChild(field("Action", "Inspect the selected SMILES representation for depiction"));
  });
  panel.appendChild(image);
}

function renderEmptyStructureDetail() {
  setText("structure-selected-title", "No sample selected");
  const selectedStatus = document.getElementById("structure-selected-status");
  selectedStatus.textContent = "Unavailable";
  selectedStatus.dataset.status = "unavailable";
  renderList("structure-smiles-panel", [field("Status", "No selected structure")]);
  renderList("structure-2d-panel", [field("Status", "No selected structure")]);
  renderList("structure-3d-panel", [field("Status", "No selected structure")]);
  renderList("structure-status-panel", [field("Status", "No selected structure")]);
  renderList("structure-provenance-panel", [
    field("Chemistry records", state.artifact?.run_metadata.artifact_paths.chemistry_records || "n/a"),
    field("Geometry records", state.artifact?.run_metadata.artifact_paths.geometry_records || "n/a"),
  ]);
  renderList("structure-panel-states", [
    field("SMILES", "unavailable"),
    field("2D", "unavailable"),
    field("3D", "unavailable"),
    field("Graph", "unavailable"),
  ]);
}

document.getElementById("failure-filter").addEventListener("change", (event) => {
  state.failureFilter = event.target.value;
  renderFailureRows();
});

document.getElementById("metric-filter").addEventListener("change", (event) => {
  state.metricFilter = event.target.value;
  renderMetricRows();
  renderMetricSummary();
  renderLeaderboardRows();
});

document.getElementById("structure-search").addEventListener("input", (event) => {
  state.structureQuery = event.target.value;
  loadStructures();
});

document.getElementById("structure-filter").addEventListener("change", (event) => {
  state.structureFilter = event.target.value;
  loadStructures();
});

nativeFetch("/api/artifact")
  .then((response) => {
    if (!response.ok) throw new Error(`Artifact request failed: ${response.status}`);
    return response.json();
  })
  .then((artifact) => {
    state.artifact = artifact;
    renderArtifact(artifact);
  })
  .catch((error) => {
    setText("run-title", "Artifact unavailable");
    setText("run-status", error.message);
  });
