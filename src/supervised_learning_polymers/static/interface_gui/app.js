const state = {
  artifact: null,
  failureFilter: "all",
  metricFilter: "all",
};

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

function renderArtifact(artifact) {
  const run = artifact.run_metadata;
  const target = artifact.target_mode_summary;
  const manifest = artifact.manifest;
  const chemistry = artifact.chemistry_failure_summary;
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
      cell(group.failure_type),
      cell(group.count, "num"),
      cell(group.example_sample_ids.join(", ") || "n/a"),
      cell(group.recommended_action),
    );
    return tr;
  });
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

fetch("/api/artifact")
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
