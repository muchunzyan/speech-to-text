const form = document.querySelector("#transcription-form");
const fileInput = document.querySelector("#media-file");
const dropZone = document.querySelector("#drop-zone");
const fileTitle = document.querySelector("#file-title");
const fileSubtitle = document.querySelector("#file-subtitle");
const submitButton = document.querySelector("#submit-button");
const statusPanel = document.querySelector("#status-panel");
const statusTitle = document.querySelector("#status-title");
const statusMessage = document.querySelector("#status-message");
const progressBar = document.querySelector("#progress-bar");
const progressTrack = document.querySelector("#progress-track");
const progressLabel = document.querySelector("#progress-label");
const errorMessage = document.querySelector("#error-message");
const resultPanel = document.querySelector("#result-panel");
const resultText = document.querySelector("#result-text");
const resultDuration = document.querySelector("#result-duration");
const downloads = document.querySelector("#downloads");
const copyButton = document.querySelector("#copy-button");
const cancelButton = document.querySelector("#cancel-button");
const modelSelect = document.querySelector("#model-profile");
const modelDescription = document.querySelector("#model-description");
const modelSize = document.querySelector("#model-size");
const modelCachePath = document.querySelector("#model-cache-path");
const deleteModelButton = document.querySelector("#delete-model-button");
let activeJobId = null;
let modelStatuses = new Map();

const stageTitles = {
  uploading: "Загрузка файла",
  queued: "В очереди",
  preparing: "Подготовка аудио",
  downloading_model: "Скачивание модели",
  loading_model: "Загрузка модели в память",
  transcribing: "Распознавание речи",
  exporting: "Сохранение результата",
  completed: "Готово",
  failed: "Ошибка",
  cancelling: "Отмена",
  cancelled: "Отменено",
};

function setFormLocked(locked) {
  dropZone.classList.toggle("locked", locked);
  dropZone.classList.remove("dragging");
  form.querySelectorAll("input, select, textarea").forEach((control) => {
    control.disabled = locked;
  });
  submitButton.disabled = locked;
  deleteModelButton.disabled = locked;
}

function updateModelDescription() {
  const model = modelStatuses.get(modelSelect.value);
  modelDescription.textContent = model?.description || "";
  modelSize.textContent = model ? `Размер: ${model.size_hint}` : "";
  deleteModelButton.classList.toggle("hidden", !model?.downloaded);
}

async function refreshModelStatuses() {
  try {
    const response = await fetch("/api/models", { cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    modelStatuses = new Map(payload.models.map((model) => [model.key, model]));
    const cacheParts = payload.cache_directory.split("/").filter(Boolean);
    modelCachePath.textContent = `Хранилище: ${cacheParts.at(-1) || "models"}/`;
    modelCachePath.title = payload.cache_directory;
    const selected = modelSelect.value;
    modelSelect.replaceChildren();
    payload.models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model.key;
      option.textContent = `${model.title} (${model.model_name}, ${model.downloaded ? "скачана" : "не скачана"})`;
      modelSelect.appendChild(option);
    });
    modelSelect.value = selected;
    updateModelDescription();
  } catch (_) {
    // Status refresh is helpful but should not interrupt the main workflow.
  }
}

function showSelectedFile(file) {
  if (!file) return;
  fileTitle.textContent = file.name;
  fileSubtitle.textContent = `${(file.size / 1024 / 1024).toFixed(1)} МБ`;
}

modelSelect.addEventListener("change", updateModelDescription);
deleteModelButton.addEventListener("click", async () => {
  const model = modelStatuses.get(modelSelect.value);
  if (!model?.downloaded) return;
  if (!window.confirm(`Удалить ${model.model_name}? При следующем использовании её придётся скачать заново.`)) return;
  deleteModelButton.disabled = true;
  deleteModelButton.textContent = "Удаляем…";
  try {
    const response = await fetch(`/api/models/${model.key}`, { method: "DELETE" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Не удалось удалить модель");
    await refreshModelStatuses();
  } catch (error) {
    window.alert(error.message);
  } finally {
    deleteModelButton.disabled = false;
    deleteModelButton.textContent = "Удалить модель";
  }
});
refreshModelStatuses();
fileInput.addEventListener("change", () => showSelectedFile(fileInput.files[0]));
["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    if (!fileInput.disabled) dropZone.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
});
dropZone.addEventListener("drop", (event) => {
  if (fileInput.disabled) return;
  const files = event.dataTransfer.files;
  if (files.length) {
    fileInput.files = files;
    showSelectedFile(files[0]);
  }
});

function updateProgress(percent, title, message, indeterminate = false) {
  const safePercent = Math.max(0, Math.min(100, percent || 0));
  progressBar.style.width = `${safePercent}%`;
  progressTrack.classList.toggle("indeterminate", indeterminate);
  progressLabel.textContent = indeterminate ? "идёт…" : `${safePercent}%`;
  statusTitle.textContent = title;
  statusMessage.textContent = message || "";
}

function finishInteraction(buttonText) {
  activeJobId = null;
  setFormLocked(false);
  cancelButton.classList.add("hidden");
  cancelButton.disabled = false;
  submitButton.textContent = buttonText;
}

function showError(message) {
  errorMessage.textContent = typeof message === "string" ? message : JSON.stringify(message);
  errorMessage.classList.remove("hidden");
  finishInteraction("Попробовать снова");
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(seconds || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainingSeconds = total % 60;
  const parts = [];
  if (hours) parts.push(`${hours} ч`);
  if (minutes) parts.push(`${minutes} мин`);
  if (remainingSeconds || parts.length === 0) parts.push(`${remainingSeconds} сек`);
  return parts.join(" ");
}

function renderResult(job) {
  resultText.value = job.text || "";
  resultDuration.textContent = `Обработка заняла ${formatDuration(job.elapsed_seconds)}`;
  downloads.replaceChildren();
  const labels = { txt: "TXT", md: "Markdown", json: "JSON", srt: "SRT" };
  Object.entries(job.downloads || {}).forEach(([kind, url]) => {
    const link = document.createElement("a");
    link.href = url;
    link.textContent = `Скачать ${labels[kind] || kind.toUpperCase()}`;
    downloads.appendChild(link);
  });
  resultPanel.classList.remove("hidden");
  finishInteraction("Транскрибировать другой файл");
  refreshModelStatuses();
}

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
    if (!response.ok) throw new Error("Не удалось получить состояние задания");
    const job = await response.json();
    updateProgress(
      job.progress,
      stageTitles[job.stage] || "Обработка",
      job.message,
      Boolean(job.indeterminate),
    );
    cancelButton.classList.toggle("hidden", !job.can_cancel);
    if (job.status === "completed") {
      renderResult(job);
      return;
    }
    if (job.status === "failed") {
      showError(job.error || "Неизвестная ошибка");
      return;
    }
    if (job.status === "cancelled") {
      finishInteraction("Начать транскрибацию");
      refreshModelStatuses();
      return;
    }
    window.setTimeout(() => pollJob(jobId), 1000);
  } catch (error) {
    showError(error.message);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!fileInput.files.length) return;
  const formData = new FormData(form);
  setFormLocked(true);
  submitButton.textContent = "Загружаем…";
  statusPanel.classList.remove("hidden");
  resultPanel.classList.add("hidden");
  errorMessage.classList.add("hidden");
  cancelButton.classList.remove("hidden");
  cancelButton.disabled = true;
  updateProgress(0, "Загрузка файла", "Передаём файл локальному процессу");

  const request = new XMLHttpRequest();
  request.open("POST", "/api/jobs");
  request.upload.addEventListener("progress", (progressEvent) => {
    if (!progressEvent.lengthComputable) return;
    const percent = Math.round((progressEvent.loaded / progressEvent.total) * 5);
    updateProgress(percent, "Загрузка файла", "Передаём файл локальному процессу");
  });
  request.addEventListener("load", () => {
    let payload = {};
    try { payload = JSON.parse(request.responseText); } catch (_) { /* handled below */ }
    if (request.status < 200 || request.status >= 300) {
      showError(payload.detail || "Не удалось создать задание");
      return;
    }
    activeJobId = payload.id;
    cancelButton.disabled = false;
    pollJob(payload.id);
  });
  request.addEventListener("error", () => showError("Ошибка локального соединения"));
  request.send(formData);
});

cancelButton.addEventListener("click", async () => {
  if (!activeJobId) return;
  cancelButton.disabled = true;
  updateProgress(40, "Отмена", "Останавливаем обработку…", true);
  try {
    const response = await fetch(`/api/jobs/${activeJobId}/cancel`, { method: "POST" });
    if (!response.ok) throw new Error("Не удалось отменить задание");
  } catch (error) {
    showError(error.message);
  }
});

copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(resultText.value);
  copyButton.textContent = "Скопировано";
  window.setTimeout(() => { copyButton.textContent = "Копировать"; }, 1400);
});
