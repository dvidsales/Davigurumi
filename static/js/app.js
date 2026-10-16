"use strict";
document.documentElement.classList.add("js-ready");
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

// Route-aware navigation in desktop, mobile dialog and no-script fallback.
function markNavigation() {
  for (const navigation of document.querySelectorAll('[data-workspace-nav]')) {
    const links = [...navigation.querySelectorAll('a')];
    const match = links.filter(link => {
      const url = new URL(link.href);
      if (url.hash && url.hash !== location.hash) return false;
      return url.pathname === '/' ? location.pathname === '/' : location.pathname.startsWith(url.pathname);
    }).sort((a, b) => {
      const left = new URL(a.href), right = new URL(b.href);
      return right.pathname.length - left.pathname.length || right.hash.length - left.hash.length;
    })[0] || navigation.querySelector('a.active');
    for (const link of links) { link.classList.remove('active'); link.removeAttribute('aria-current'); }
    if (match) {
      match.classList.add('active'); match.setAttribute('aria-current', 'page');
      const group = match.closest('details'); if (group) group.open = true;
    }
  }
}
markNavigation();
window.addEventListener('hashchange', markNavigation);
const mobileMenu = document.getElementById('mobile-menu');
const menuTriggers = [...document.querySelectorAll('[data-menu-open]')];
if (mobileMenu) {
  const desktopViewport = window.matchMedia('(min-width: 1100px)');
  const closeMenu = () => mobileMenu.close();
  for (const trigger of menuTriggers) trigger.addEventListener('click', () => {
    if (!mobileMenu.open) mobileMenu.showModal();
    document.body.classList.add('menu-open');
    for (const control of menuTriggers) control.setAttribute('aria-expanded', 'true');
  });
  mobileMenu.querySelector('[data-menu-close]').addEventListener('click', closeMenu);
  mobileMenu.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...mobileMenu.querySelectorAll('a[href], button:not([disabled]), summary, [tabindex="0"]')]
      .filter(element => element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden');
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first?.focus();
    }
  });
  mobileMenu.addEventListener('close', () => {
    document.body.classList.remove('menu-open');
    for (const control of menuTriggers) control.setAttribute('aria-expanded', 'false');
  });
  mobileMenu.addEventListener('click', event => {
    const rect = mobileMenu.getBoundingClientRect();
    if (event.target === mobileMenu && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) closeMenu();
  });
  desktopViewport.addEventListener('change', event => {
    if (event.matches && mobileMenu.open) {
      closeMenu();
      document.querySelector('.sidebar a.active')?.focus({preventScroll: true});
    }
  });
}

// Keep real table headers and explicit roles when simple lists reflow into cards.
for (const table of document.querySelectorAll('.table-scroll table, .table-wrap table')) {
  const headers = [...table.querySelectorAll('thead tr:first-child > th')];
  const rows = [...table.querySelectorAll('tbody > tr')];
  if (headers.length < 2 || !rows.length || table.querySelector('thead tr:nth-child(2)') ||
      [...table.querySelectorAll('th,td')].some(cell => cell.colSpan > 1 || cell.rowSpan > 1) ||
      rows.some(row => row.children.length !== headers.length)) continue;
  table.classList.add('mobile-cards'); table.setAttribute('role', 'table');
  table.querySelector('thead').setAttribute('role', 'rowgroup');
  table.querySelector('thead tr').setAttribute('role', 'row');
  for (const header of headers) { header.scope = 'col'; header.setAttribute('role', 'columnheader'); }
  table.querySelector('tbody').setAttribute('role', 'rowgroup');
  for (const row of rows) {
    row.setAttribute('role', 'row');
    [...row.children].forEach((cell, index) => {
      cell.setAttribute('role', cell.tagName === 'TH' ? 'rowheader' : 'cell');
      if (cell.tagName === 'TH') cell.scope = 'row';
      const label = document.createElement('span'); label.className = 'cell-label';
      label.setAttribute('aria-hidden', 'true'); label.textContent = headers[index].textContent.trim();
      const value = document.createElement('div'); value.className = 'cell-value';
      value.append(...cell.childNodes); cell.append(label, value);
    });
  }
}

const pieceForm = document.querySelector('[data-piece-form]');
if (pieceForm) {
  const project = pieceForm.querySelector('[name=project]');
  const name = pieceForm.querySelector('[name=new_piece_name]');
  const description = pieceForm.querySelector('[name=description]');
  const manual = pieceForm.querySelector('[name=manual_price]');
  const calculated = pieceForm.querySelector('[name=use_calculated_price]');
  const preview = pieceForm.querySelector('[data-piece-preview]');
  const alternatives = pieceForm.querySelector('[data-piece-alternatives]');
  let controller;
  let manualEdited = Boolean(manual.value);
  manual.addEventListener('input', () => { manualEdited = true; calculated.value = ''; });
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
      if (!manualEdited) { manual.value = data.manual_price || data.calculated_price || ''; calculated.value = data.complete ? 'on' : ''; }
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

// Numeric keyboards without restricting pasted/localized decimal values.
for (const input of document.querySelectorAll('input[type=number]')) {
  if (!input.inputMode) input.inputMode = input.step && input.step !== '1' ? 'decimal' : 'numeric';
}

// Reserve the real bar height, including safe areas and enlarged text.
if ('ResizeObserver' in window) {
  const bottomBar = document.querySelector('.bottom-navigation');
  if (bottomBar) new ResizeObserver(entries => {
    const height = Math.ceil(entries[0].target.getBoundingClientRect().height);
    if (height > 0) document.documentElement.style.setProperty('--bottom-height', `${height}px`);
  }).observe(bottomBar);
}
