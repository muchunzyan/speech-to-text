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
const modelInput = document.querySelector("#model-profile");
const modelPicker = document.querySelector("#model-picker");
const modelPickerButton = document.querySelector("#model-picker-button");
const modelPickerMenu = document.querySelector("#model-picker-menu");
const modelPickerTitle = document.querySelector("#model-picker-title");
const modelPickerName = document.querySelector("#model-picker-name");
const modelPickerBadges = document.querySelector("#model-picker-badges");
const modelDescription = document.querySelector("#model-description");
const modelDevice = document.querySelector("#model-device");
const modelRequirements = document.querySelector("#model-requirements");
const modelAdvice = document.querySelector("#model-advice");
const modelSize = document.querySelector("#model-size");
const modelEngine = document.querySelector("#model-engine");
const modelCachePath = document.querySelector("#model-cache-path");
const deleteModelButton = document.querySelector("#delete-model-button");
const deleteModelLabel = document.querySelector("#delete-model-label");
const languageInput = document.querySelector("#language");
const languagePicker = document.querySelector("#language-picker");
const languagePickerButton = document.querySelector("#language-picker-button");
const languagePickerMenu = document.querySelector("#language-picker-menu");
const languagePickerTitle = document.querySelector("#language-picker-title");
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
  modelPickerButton.disabled = locked;
  languagePickerButton.disabled = locked;
  modelPickerMenu.querySelectorAll("button").forEach((button) => {
    button.disabled = locked;
  });
  languagePickerMenu.querySelectorAll("button").forEach((button) => {
    button.disabled = locked;
  });
  if (locked) {
    closeModelPicker();
    closeLanguagePicker();
  }
}

function createBadge(text, className = "") {
  const badge = document.createElement("span");
  badge.className = `badge ${className}`.trim();
  badge.textContent = text;
  return badge;
}

function updateModelDescription() {
  const model = modelStatuses.get(modelInput.value);
  if (!model) return;
  modelPickerTitle.textContent = model.title;
  modelPickerName.textContent = model.model_name;
  modelPickerBadges.replaceChildren();
  if (model.recommended) {
    modelPickerBadges.appendChild(createBadge("Рекомендуется", "recommended"));
  }
  modelPickerBadges.appendChild(
    createBadge(model.downloaded ? "Скачана" : "Не скачана", model.downloaded ? "downloaded" : ""),
  );
  modelDescription.textContent = model?.description || "";
  modelRequirements.textContent = model.requirements;
  modelAdvice.textContent = model?.suitability_message || "";
  modelAdvice.className = `model-advice ${model?.suitability || ""}`;
  modelSize.textContent = `Модель ${model.size_hint}`;
  modelEngine.textContent = model.engine_title;
  deleteModelButton.classList.toggle("hidden", !model?.downloaded);
  modelPickerMenu.querySelectorAll(".model-option").forEach((option) => {
    const selected = option.dataset.key === model.key;
    option.classList.toggle("selected", selected);
    option.setAttribute("aria-selected", String(selected));
  });
}

function closeModelPicker({ restoreFocus = false } = {}) {
  modelPickerMenu.classList.add("hidden");
  modelPickerButton.setAttribute("aria-expanded", "false");
  modelPicker.classList.remove("open");
  if (restoreFocus) modelPickerButton.focus();
}

function openModelPicker() {
  if (modelPickerButton.disabled) return;
  modelPickerMenu.classList.remove("hidden");
  modelPickerButton.setAttribute("aria-expanded", "true");
  modelPicker.classList.add("open");
}

function closeLanguagePicker({ restoreFocus = false } = {}) {
  languagePickerMenu.classList.add("hidden");
  languagePickerButton.setAttribute("aria-expanded", "false");
  languagePicker.classList.remove("open");
  if (restoreFocus) languagePickerButton.focus();
}

function openLanguagePicker() {
  if (languagePickerButton.disabled) return;
  languagePickerMenu.classList.remove("hidden");
  languagePickerButton.setAttribute("aria-expanded", "true");
  languagePicker.classList.add("open");
}

function selectLanguage(value, { close = true } = {}) {
  const option = languagePickerMenu.querySelector(`[data-value="${value}"]`);
  if (!option) return;
  languageInput.value = value;
  languagePickerTitle.textContent = option.textContent;
  languagePickerMenu.querySelectorAll(".language-option").forEach((item) => {
    const selected = item.dataset.value === value;
    item.classList.toggle("selected", selected);
    item.setAttribute("aria-selected", String(selected));
  });
  if (close) closeLanguagePicker({ restoreFocus: true });
}

function selectModel(key, { close = true } = {}) {
  if (!modelStatuses.has(key)) return;
  modelInput.value = key;
  updateModelDescription();
  if (close) closeModelPicker({ restoreFocus: true });
}

function renderModelOptions(models) {
  modelPickerMenu.replaceChildren();
  models.forEach((model) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = `model-option ${model.suitability}`;
    option.dataset.key = model.key;
    option.setAttribute("role", "option");

    const copy = document.createElement("span");
    copy.className = "model-option-copy";
    const title = document.createElement("strong");
    title.textContent = model.title;
    const name = document.createElement("small");
    name.textContent = model.model_name;
    copy.append(title, name);

    const badges = document.createElement("span");
    badges.className = "model-option-badges";
    if (model.recommended) badges.appendChild(createBadge("Для этого ПК", "recommended"));
    if (model.suitability === "demanding") {
      badges.appendChild(createBadge("Может быть медленно", "warning"));
    }
    badges.appendChild(
      createBadge(model.downloaded ? "Скачана" : model.size_hint, model.downloaded ? "downloaded" : ""),
    );
    option.append(copy, badges);
    option.addEventListener("click", () => selectModel(model.key));
    modelPickerMenu.appendChild(option);
  });
}

async function refreshModelStatuses() {
  try {
    const response = await fetch("/api/models", { cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    modelDevice.textContent = `Устройство: ${payload.device_summary}`;
    modelStatuses = new Map(payload.models.map((model) => [model.key, model]));
    const cacheParts = payload.cache_directory.split(/[\\/]/).filter(Boolean);
    modelCachePath.textContent = `Хранилище: ${cacheParts.at(-1) || "models"}/`;
    modelCachePath.title = payload.cache_directory;
    const selected = modelStatuses.has(modelInput.value)
      ? modelInput.value
      : payload.models.find((model) => model.recommended)?.key || "balanced";
    renderModelOptions(payload.models);
    modelInput.value = selected;
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

modelPickerButton.addEventListener("click", () => {
  if (modelPickerMenu.classList.contains("hidden")) openModelPicker();
  else closeModelPicker();
});
modelPickerButton.addEventListener("keydown", (event) => {
  if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
  event.preventDefault();
  openModelPicker();
  const options = [...modelPickerMenu.querySelectorAll(".model-option")];
  const selectedIndex = options.findIndex((option) => option.dataset.key === modelInput.value);
  const target = event.key === "ArrowUp" ? options.at(selectedIndex - 1) : options[selectedIndex + 1];
  (target || options[selectedIndex] || options[0])?.focus();
});
modelPickerMenu.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.preventDefault();
    closeModelPicker({ restoreFocus: true });
    return;
  }
  if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
  event.preventDefault();
  const options = [...modelPickerMenu.querySelectorAll(".model-option")];
  const index = options.indexOf(document.activeElement);
  const nextIndex = event.key === "ArrowDown"
    ? Math.min(index + 1, options.length - 1)
    : Math.max(index - 1, 0);
  options[nextIndex]?.focus();
});
languagePickerButton.addEventListener("click", () => {
  if (languagePickerMenu.classList.contains("hidden")) openLanguagePicker();
  else closeLanguagePicker();
});
languagePickerButton.addEventListener("keydown", (event) => {
  if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
  event.preventDefault();
  openLanguagePicker();
  const options = [...languagePickerMenu.querySelectorAll(".language-option")];
  const selectedIndex = options.findIndex((option) => option.dataset.value === languageInput.value);
  const target = event.key === "ArrowUp" ? options.at(selectedIndex - 1) : options[selectedIndex + 1];
  (target || options[selectedIndex] || options[0])?.focus();
});
languagePickerMenu.addEventListener("click", (event) => {
  const option = event.target.closest(".language-option");
  if (option) selectLanguage(option.dataset.value);
});
languagePickerMenu.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.preventDefault();
    closeLanguagePicker({ restoreFocus: true });
    return;
  }
  if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
  event.preventDefault();
  const options = [...languagePickerMenu.querySelectorAll(".language-option")];
  const index = options.indexOf(document.activeElement);
  const nextIndex = event.key === "ArrowDown"
    ? Math.min(index + 1, options.length - 1)
    : Math.max(index - 1, 0);
  options[nextIndex]?.focus();
});
document.addEventListener("click", (event) => {
  if (!modelPicker.contains(event.target)) closeModelPicker();
  if (!languagePicker.contains(event.target)) closeLanguagePicker();
});
deleteModelButton.addEventListener("click", async () => {
  const model = modelStatuses.get(modelInput.value);
  if (!model?.downloaded) return;
  if (!window.confirm(`Удалить ${model.model_name}? При следующем использовании её придётся скачать заново.`)) return;
  deleteModelButton.disabled = true;
  deleteModelLabel.textContent = "Удаляем…";
  try {
    const response = await fetch(`/api/models/${model.key}`, { method: "DELETE" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Не удалось удалить модель");
    await refreshModelStatuses();
  } catch (error) {
    window.alert(error.message);
  } finally {
    deleteModelButton.disabled = false;
    deleteModelLabel.textContent = "Удалить модель";
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
  const selectedModel = modelStatuses.get(modelInput.value);
  if (selectedModel?.suitability === "demanding") {
    const confirmed = window.confirm(
      `${selectedModel.suitability_message}\n\n${selectedModel.requirements}\n\nВсё равно запустить транскрибацию?`,
    );
    if (!confirmed) return;
  }
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
