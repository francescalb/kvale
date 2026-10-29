/* Installable and offline app, and the user guide (chunk 7). Plain JS, so it
   works before Python has started.

   - Registers sw.js. When a new version is waiting, shows #update-toast;
     "Reload" lets the new worker take over and reloads the page.
   - Once the app is ready, sends the worker the CDN files the page loaded
     (PyScript, Pyodide, fonts) so they are cached for offline use, and sets
     window.kvaleOffline = "ready" (read by the browser tests).
   - Shows #install-app when the browser offers to install (beforeinstallprompt).
   - #help-open opens the guide (guide/<language>.html) in #help-dialog.

   The texts are data-i18n elements in index.html, translated by Python. */
(function () {
  "use strict";
  var GUIDE_LANGUAGES = ["nb", "en", "it"];

  // Pyodide loads many files; keep every entry so all of them can be cached.
  if (window.performance && performance.setResourceTimingBufferSize) {
    performance.setResourceTimingBufferSize(2000);
  }

  function byId(id) { return document.getElementById(id); }

  function whenAppReady(callback) {
    if (window.kvaleReady === true) { callback(); return; }
    var timer = setInterval(function () {
      if (window.kvaleReady === true) { clearInterval(timer); callback(); }
    }, 500);
  }

  function ask(worker, message) {
    return new Promise(function (resolve) {
      var channel = new MessageChannel();
      channel.port1.onmessage = function (event) { resolve(event.data); };
      worker.postMessage(message, [channel.port2]);
    });
  }

  // Service worker and updates -----------------------------------------

  var reloading = false;

  function showUpdate(registration) {
    var toast = byId("update-toast");
    if (!toast || !registration.waiting) return;
    toast.hidden = false;
    byId("update-reload").onclick = function () {
      reloading = true;
      if (registration.waiting) registration.waiting.postMessage({ type: "skip-waiting" });
    };
  }

  function watchUpdates(registration) {
    if (registration.waiting && navigator.serviceWorker.controller) showUpdate(registration);
    registration.addEventListener("updatefound", function () {
      var worker = registration.installing;
      if (!worker) return;
      worker.addEventListener("statechange", function () {
        // With no controller this is the first install, not an update.
        if (worker.state === "installed" && navigator.serviceWorker.controller) showUpdate(registration);
      });
    });
    navigator.serviceWorker.addEventListener("controllerchange", function () {
      if (reloading) window.location.reload();
    });
    // Look for a new version now and then, and when the tab comes back.
    setInterval(function () { registration.update().catch(function () {}); }, 60 * 60 * 1000);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") registration.update().catch(function () {});
    });
  }

  function warmCache() {
    navigator.serviceWorker.ready.then(function (registration) {
      var urls = performance.getEntriesByType("resource").map(function (entry) { return entry.name; });
      return ask(registration.active, { type: "warm", urls: urls });
    }).then(function () {
      window.kvaleOffline = "ready";
    }).catch(function () {});
  }

  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").then(function (registration) {
        window.kvaleServiceWorker = registration;
        watchUpdates(registration);
        whenAppReady(warmCache);
      }).catch(function () {});
    });
  }

  // Install button --------------------------------------------------------

  var installPrompt = null;
  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    installPrompt = event;
    var button = byId("install-app");
    if (button) button.hidden = false;
  });
  window.addEventListener("appinstalled", function () {
    installPrompt = null;
    var button = byId("install-app");
    if (button) button.hidden = true;
  });

  // Guide -------------------------------------------------------------------

  function guideUrl() {
    var lang = document.documentElement.lang;
    return "guide/" + (GUIDE_LANGUAGES.indexOf(lang) >= 0 ? lang : "nb") + ".html";
  }

  function openGuide() {
    var dialog = byId("help-dialog");
    var frame = byId("help-frame");
    var url = guideUrl();
    if (frame.getAttribute("src") !== url) frame.setAttribute("src", url);
    byId("help-newtab").setAttribute("href", url);
    if (!dialog.open) dialog.showModal();
  }

  document.addEventListener("DOMContentLoaded", function () {
    byId("help-open").addEventListener("click", openGuide);
    byId("install-app").addEventListener("click", function () {
      if (!installPrompt) return;
      installPrompt.prompt();
      installPrompt.userChoice.finally(function () {
        installPrompt = null;
        byId("install-app").hidden = true;
      });
    });
    byId("help-dialog").addEventListener("click", function (event) {
      if (event.target === event.currentTarget) event.currentTarget.close();  // the backdrop
    });
  });
})();
