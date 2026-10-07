"use strict";
if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("/service-worker.js").catch(() => {});
}
const connectionStatus = document.getElementById("connection-status");
const originalDisabledState = new WeakMap();
function updateConnectivity() {
  if (connectionStatus) {
    connectionStatus.hidden = navigator.onLine;
    connectionStatus.textContent = "Sem conexão. Operações de estoque, aceite e pagamentos precisam de confirmação do servidor. Dados não são sincronizados offline.";
  }
  for (const form of document.forms) {
    if ((form.getAttribute("method") || "get").toLowerCase() === "post") {
      for (const button of form.querySelectorAll("button[type=submit],button:not([type]),input[type=submit]")) {
        if (!originalDisabledState.has(button)) originalDisabledState.set(button, button.disabled);
        button.disabled = !navigator.onLine || originalDisabledState.get(button);
      }
    }
  }
}
window.addEventListener("online", updateConnectivity);
window.addEventListener("offline", updateConnectivity);
updateConnectivity();
for (const element of document.querySelectorAll(".timer[data-start]")) {
  const elapsed = Math.max(0, Date.parse(element.dataset.now) - Date.parse(element.dataset.start));
  const initial = performance.now();
  const render = () => {
    const seconds = Math.floor((elapsed + performance.now() - initial) / 1000);
    element.textContent = `${Math.floor(seconds / 3600)}h ${Math.floor(seconds / 60) % 60}min ${seconds % 60}s`;
  };
  render(); setInterval(render, 1000);
}
