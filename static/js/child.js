/**
 * Gustul Cărților — Child UI & HTMX Controller (static/js/child.js)
 * Owner: Denis (Antigravity)
 * Scope: Child mode HTMX error/toast handling, 422 inline swap, progressive enhancement
 */

(function () {
  "use strict";

  if (window.__GUSTUL_CHILD_HTMX_INITIALIZED) {
    return;
  }
  window.__GUSTUL_CHILD_HTMX_INITIALIZED = true;

  // Accessible toast announcement helper
  function showToast(message, type) {
    const toast = document.getElementById("child-toast");
    if (!toast) return;

    toast.textContent = message;
    toast.className = "child-toast " + (type === "success" ? "toast-success" : "toast-error");
    toast.hidden = false;
    toast.setAttribute("role", type === "success" ? "status" : "alert");
    toast.setAttribute("aria-live", "polite");

    if (window.__childToastTimeout) {
      clearTimeout(window.__childToastTimeout);
    }
    window.__childToastTimeout = setTimeout(() => {
      toast.hidden = true;
    }, 4000);
  }

  // HTMX Event: beforeSwap
  // Rule: Swap ONLY on 2xx and 422 (to render inline validation errors).
  // Reject 401, 403, 404, 409, 429, 500, 503.
  document.addEventListener("htmx:beforeSwap", function (evt) {
    const status = evt.detail && evt.detail.xhr ? evt.detail.xhr.status : 0;
    if (status === 422 && evt.detail) {
      evt.detail.shouldSwap = true;
      evt.detail.isError = false;
    }
  });

  // HTMX Event: responseError
  document.addEventListener("htmx:responseError", function (evt) {
    const xhr = evt.detail ? evt.detail.xhr : null;
    const status = xhr ? xhr.status : 0;

    if (status === 401) {
      const redirectUrl = (xhr.getResponseHeader && xhr.getResponseHeader("HX-Redirect")) || "/cont/intrare/";
      window.location.href = redirectUrl;
      return;
    }

    if (status === 403) {
      showToast("Acces restricționat în modul copil.", "error");
      return;
    }

    if (status === 409) {
      showToast("Nu s-a salvat — cererea a fost deja trimisă.", "error");
      return;
    }

    if (status === 503) {
      showToast("Nu s-a salvat — baza de date este ocupată. Reîncearcă.", "error");
      return;
    }

    showToast("Nu s-a salvat — încearcă din nou.", "error");
  });

  // HTMX Event: sendError (Network offline or connection dropped)
  document.addEventListener("htmx:sendError", function () {
    showToast("Nu s-a salvat — nu ai conexiune la internet.", "error");
  });

  // HTMX Trigger: saved (Confirmed transaction from backend)
  // Attached to document rather than document.body so script evaluates safely even when loaded in <head>.
  document.addEventListener("saved", function () {
    showToast("Salvat cu succes! ✓", "success");
  });

  // Export stepper function globally for child reading interface
  window.incrementPage = function (delta) {
    const input = document.getElementById("page-input");
    if (input) {
      const max = parseInt(input.getAttribute("max") || "9999", 10);
      const min = parseInt(input.getAttribute("min") || "0", 10);
      const current = parseInt(input.value || "0", 10);
      const next = Math.min(max, Math.max(min, current + delta));
      input.value = next;
    }
  };
})();
