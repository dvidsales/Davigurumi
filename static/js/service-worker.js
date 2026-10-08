"use strict";
const PUBLIC_CACHE = "davigurumi-public-v5";
const ASSETS = ["/static/css/app.css", "/static/js/app.js", "/static/icons/icon-192.png", "/static/icons/icon-512.png"];
self.addEventListener("install", event => event.waitUntil(caches.open(PUBLIC_CACHE).then(cache => cache.addAll(ASSETS))));
// No skipWaiting: updating the worker must not reload an unsaved form.
self.addEventListener("activate", event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("davigurumi-public-") && key !== PUBLIC_CACHE).map(key => caches.delete(key))))));
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || !ASSETS.includes(url.pathname)) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok && response.type === "basic") {
      const copy = response.clone();
      event.waitUntil(caches.open(PUBLIC_CACHE).then(cache => cache.put(event.request, copy)));
    }
    return response;
  }).catch(() => caches.match(event.request)));
});
