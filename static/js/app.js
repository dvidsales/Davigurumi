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

const pieceForm = document.querySelector('[data-piece-form]');
if (pieceForm) {
  const project = pieceForm.querySelector('[name=project]');
  const name = pieceForm.querySelector('[name=new_piece_name]');
  const description = pieceForm.querySelector('[name=description]');
  const manual = pieceForm.querySelector('[name=manual_price]');
  const preview = pieceForm.querySelector('[data-piece-preview]');
  const alternatives = pieceForm.querySelector('[data-piece-alternatives]');
  let controller;
  let manualEdited = Boolean(manual.value);
  manual.addEventListener('input', () => { manualEdited = true; });
  async function suggest(changedProject = false) {
    if (controller) controller.abort();
    name.closest('.field').hidden = Boolean(project.value) && !name.value;
    if (!project.value) {
      if (changedProject) { manual.value = ''; description.value = ''; manualEdited = false; }
      alternatives.hidden = true;
      preview.textContent = 'Informe o nome e o preço total da nova peça. A ficha de custos pode ser completada depois.';
      return;
    }
    controller = new AbortController();
    if (changedProject) { name.value = ''; name.closest('.field').hidden = true; manualEdited = false; }
    const url = new URL(pieceForm.dataset.suggestionBase.replace('00000000-0000-0000-0000-000000000000', project.value), location.origin);
    for (const field of pieceForm.elements) {
      if (['quantity','discount','fixed_discount'].includes(field.name) || field.name.startsWith('alternative_')) url.searchParams.set(field.name, field.value || '0');
    }
    try {
      const response = await fetch(url, {signal:controller.signal, headers:{'Accept':'application/json'}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível carregar a sugestão.');
      if (changedProject || !description.value) description.value = data.description;
      if (!manualEdited) manual.value = data.manual_price || data.calculated_price || '';
      preview.textContent = data.complete ? `Preço calculado para esta quantidade: R$ ${data.calculated_price.replace('.', ',')}. Confira ou informe um preço manual.` : (data.manual_price ? 'Preço manual sugerido com base no último orçamento e na quantidade atual. Confira; os custos ainda estão incompletos.' : 'Custos ainda incompletos. Informe um preço manual total para este item.');
      alternatives.hidden = !data.has_alternatives;
      const link = new URL(location.href); link.searchParams.set('project', project.value); alternatives.href = link;
    } catch (error) {
      if (error.name !== 'AbortError') preview.textContent = error.message;
    }
  }
  project.addEventListener('change', () => suggest(true));
  for (const field of pieceForm.elements) {
    if (['quantity','discount','fixed_discount'].includes(field.name) || field.name.startsWith('alternative_')) field.addEventListener('change', () => suggest());
  }
  suggest();
}
