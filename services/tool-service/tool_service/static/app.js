"use strict";
const $ = id => document.getElementById(id);
let credential = "", tools = [], timer = null, waitingFor = null, pendingSubmission = null;
let epoch = 0, shown = 20, polling = false, submitting = false;
const message = (text, error = false) => { $("status").textContent = text; $("status").className = error ? "error" : ""; };

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {...options.headers, Authorization: `Bearer ${credential}`}});
  if (!response.ok) {
    let error;
    try { error = await response.json(); } catch { error = {message: `Request failed (${response.status})`}; }
    throw new Error(error.message || `Request failed (${response.status})`);
  }
  return response;
}

function updateTool() {
  const tool = tools.find(t => t.name === $("tool").value);
  $("tool-detail").textContent = tool ? tool.description + (tool.available ? "" : ` Unavailable: ${tool.repair}`) : "";
  $("download").disabled = !credential || !tool?.available || Boolean(waitingFor) || submitting;
  $("example").disabled = !credential || !tool;
}

async function downloadJob(job) {
  const response = await api(`/api/jobs/${job.id}/download`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = `${job.tool}-${job.id}.wav`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function renderJobs(jobs, total) {
  $("jobs").replaceChildren();
  for (const job of jobs) {
    const item = document.createElement("li"), label = document.createElement("span"), details = document.createElement("small");
    label.textContent = `${job.tool} · ${job.state}`;
    details.textContent = `${new Date(job.created_at).toLocaleString()} · ${job.id}` + (job.error ? ` · ${job.error.message}` : "");
    label.append(details); item.append(label);
    if (job.state === "succeeded") {
      const button = document.createElement("button"); button.textContent = "Download WAV"; button.className = "secondary";
      button.onclick = async () => { button.disabled = true; try { await downloadJob(job); } catch (error) { message(error.message, true); } finally { button.disabled = false; } };
      item.append(button);
    }
    $("jobs").append(item);
  }
  $("more").hidden = jobs.length >= total;
}

async function refresh() {
  if (!credential || polling) return;
  polling = true;
  const currentEpoch = epoch;
  try {
    let jobs = [], total = 0;
    for (let offset = 0; offset < shown; offset += 100) {
      const page = await (await api(`/api/jobs?limit=${Math.min(100, shown-offset)}&offset=${offset}`)).json();
      jobs.push(...page.jobs); total = page.total;
      if (jobs.length >= total) break;
    }
    if (currentEpoch !== epoch) return;
    renderJobs(jobs, total);
    if (waitingFor) {
      const job = jobs.find(j => j.id === waitingFor) || await (await api(`/api/jobs/${waitingFor}`)).json();
      if (currentEpoch !== epoch) return;
      message(`${job.tool}: ${job.state}`);
      if (job.state === "succeeded") {
        waitingFor = null; updateTool();
        await downloadJob(job); message("Your WAV is ready. You can download it again from Recent jobs.");
      } else if (["failed", "interrupted"].includes(job.state)) {
        waitingFor = null; updateTool(); message(job.error?.message || job.state, true);
      }
    }
  } catch (error) { if (currentEpoch === epoch) message(error.message, true); }
  finally { polling = false; }
}

$("connect").onclick = async () => {
  credential = $("key").value; $("key").value = ""; epoch++;
  $("connect").disabled = true; message("Checking tools…");
  try {
    tools = (await (await api("/api/tools")).json()).tools;
    $("tool").replaceChildren(...tools.map(tool => { const option = document.createElement("option"); option.value = tool.name; option.textContent = tool.name + (tool.available ? "" : " (unavailable)"); return option; }));
    $("tool").disabled = false; $("refresh").disabled = false; $("disconnect").disabled = false;
    if (!$("text").value) $("text").value = tools[0]?.example || "";
    updateTool(); message("Connected. Jobs are processed one at a time.");
    clearInterval(timer); timer = setInterval(refresh, 2000); await refresh();
  } catch (error) { credential = ""; message(error.message, true); $("connect").disabled = false; }
};
$("disconnect").onclick = () => {
  epoch++; credential = ""; waitingFor = null; pendingSubmission = null; submitting = false; clearInterval(timer);
  $("connect").disabled = false; $("disconnect").disabled = true; $("refresh").disabled = true;
  $("tool").disabled = true; $("jobs").replaceChildren(); $("more").hidden = true;
  updateTool(); message("Disconnected. Accepted jobs continue running.");
};
$("tool").onchange = updateTool;
$("example").onclick = () => { $("text").value = tools.find(t => t.name === $("tool").value)?.example || ""; };
$("refresh").onclick = refresh;
$("more").onclick = () => { shown += 20; refresh(); };
$("download").onclick = async () => {
  if (submitting) return;
  const currentEpoch = epoch;
  const tool = $("tool").value, text = $("text").value;
  if (new TextEncoder().encode(text).length > 1048576) return message("Text exceeds 1 MiB.", true);
  const signature = JSON.stringify([tool, text]);
  if (!pendingSubmission || pendingSubmission.signature !== signature) {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    pendingSubmission = {signature, key: Array.from(bytes, x => x.toString(16).padStart(2,"0")).join("")};
  }
  submitting = true; updateTool(); message("Validating and submitting…");
  try {
    const job = await (await api(`/api/tools/${encodeURIComponent(tool)}`, {method:"POST", headers:{"Content-Type":"application/json", "Idempotency-Key":pendingSubmission.key}, body:JSON.stringify({text})})).json();
    if (currentEpoch !== epoch) return;
    pendingSubmission = null; waitingFor = job.id; message(`${tool}: ${job.state}`); await refresh();
  } catch (error) { if (currentEpoch === epoch) message(`${error.message} Retry keeps the same submission ID.`, true); }
  finally { if (currentEpoch === epoch) { submitting = false; updateTool(); } }
};
