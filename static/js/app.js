/**
 * Gustul Cărților — Main Client Script & HTMX Integration
 * Follows strict HTML/HTMX contract from specs/001-reading-diary-mvp/contracts/routes.md
 */

(function () {
  'use strict';

  // --- Toast Notification System ---
  function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.setAttribute('aria-live', 'polite');

    const iconSpan = document.createElement('span');
    iconSpan.className = 'toast-icon';
    if (type === 'success') {
      iconSpan.textContent = '✓';
    } else if (type === 'error') {
      iconSpan.textContent = '✕';
    } else if (type === 'warning') {
      iconSpan.textContent = '⚠';
    } else {
      iconSpan.textContent = 'ℹ';
    }

    const textSpan = document.createElement('span');
    textSpan.className = 'toast-message';
    textSpan.textContent = message;

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'toast-close';
    closeBtn.setAttribute('aria-label', 'Închide notificarea');
    closeBtn.innerHTML = '&times;';
    closeBtn.addEventListener('click', () => {
      toast.remove();
    });

    toast.appendChild(iconSpan);
    toast.appendChild(textSpan);
    toast.appendChild(closeBtn);
    container.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => {
        if (toast.isConnected) {
          toast.remove();
        }
      }, duration);
    }
  }

  // Expose showToast globally for templates / direct scripts
  window.showToast = showToast;

  // --- Mobile Navigation Toggle ---
  document.addEventListener('DOMContentLoaded', function () {
    const navToggle = document.getElementById('nav-toggle');
    const navMenu = document.getElementById('nav-menu');
    if (navToggle && navMenu) {
      navToggle.addEventListener('click', function () {
        const isOpen = navMenu.classList.toggle('open');
        navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });
    }
  });

  // --- HTMX Contract Implementation ---
  document.addEventListener('DOMContentLoaded', function () {
    // 1. HTMX beforeSwap: Allow swapping ONLY for 422 Unprocessable Entity (inline validation errors)
    // Never allow swapping for 401, 403, 404, 409, 429, 503
    document.body.addEventListener('htmx:beforeSwap', function (evt) {
      const status = evt.detail.xhr ? evt.detail.xhr.status : 0;
      if (status === 422) {
        // Swap inline field validation errors into the form
        evt.detail.shouldSwap = true;
        evt.detail.isError = false;
      }
    });

    // 2. HTMX responseError: Handling HTTP error codes
    document.body.addEventListener('htmx:responseError', function (evt) {
      const xhr = evt.detail.xhr;
      const status = xhr ? xhr.status : 0;

      if (status === 401) {
        // Session expired or unauthenticated
        const redirectUrl = xhr.getResponseHeader('HX-Redirect');
        if (redirectUrl) {
          window.location.href = redirectUrl;
        } else {
          window.location.href = '/cont/intrare/';
        }
        return;
      }

      if (status === 403) {
        showToast('Acțiune nepermisă.', 'error');
        return;
      }

      if (status === 404) {
        showToast('Resursa cerută nu a fost găsită.', 'error');
        return;
      }

      if (status === 409) {
        showToast('Nu s-a salvat — cererea a fost deja procesată.', 'warning');
        return;
      }

      if (status === 429) {
        showToast('Prea multe încercări. Vă rugăm să așteptați.', 'warning');
        return;
      }

      if (status === 503) {
        showToast('Baza de date este ocupată. Nu s-a salvat — încercați din nou.', 'error');
        return;
      }

      // Default fallback for any unhandled 4xx / 5xx (except 422 which swapped)
      if (status !== 422) {
        showToast('Nu s-a salvat — încercați din nou.', 'error');
      }
    });

    // 3. HTMX sendError: Network offline or failure
    document.body.addEventListener('htmx:sendError', function () {
      showToast('Eroare de conexiune. Nu s-a salvat.', 'error');
    });

    // 4. Committed Success: Triggered ONLY on 2xx with response header "HX-Trigger: saved"
    document.body.addEventListener('saved', function () {
      showToast('Progresul a fost salvat cu succes!', 'success');
      // The server partial itself supplies the next request_id UUID; no client-side global rotation.
    });
  });
})();
