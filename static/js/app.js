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

// Exact resolved route URLs also cover namespaces in nested installations.
const navigation = document.querySelector('nav[aria-label="Navegação principal"]');
if (navigation) {
  const links = [...navigation.querySelectorAll('a')];
  const match = links.filter(link => {
    const path = new URL(link.href).pathname;
    return path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);
  }).sort((a,b) => new URL(b.href).pathname.length - new URL(a.href).pathname.length)[0];
  if (match) {
    for (const link of links) { link.classList.remove('active'); link.removeAttribute('aria-current'); }
    match.classList.add('active'); match.setAttribute('aria-current','page');
  } else {
    const active = navigation.querySelector('a.active');
    if(active) active.setAttribute('aria-current','page');
  }
}
