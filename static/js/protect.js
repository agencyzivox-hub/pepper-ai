/**
 * Pepper AI — Content Protection
 * Disables right-click, view-source shortcuts, copy, and developer tools access.
 */
(function () {
  'use strict';

  // ── Disable right-click context menu ─────────────────────
  document.addEventListener('contextmenu', function (e) {
    e.preventDefault();
    return false;
  });

  // ── Disable keyboard shortcuts ────────────────────────────
  document.addEventListener('keydown', function (e) {
    const key  = e.key  || '';
    const code = e.code || '';
    const ctrl = e.ctrlKey || e.metaKey;
    const shift= e.shiftKey;

    // Ctrl+U — View Source
    if (ctrl && (key === 'u' || key === 'U')) { e.preventDefault(); return false; }

    // Ctrl+S — Save page
    if (ctrl && (key === 's' || key === 'S')) { e.preventDefault(); return false; }

    // Ctrl+Shift+I — Dev Tools (Chrome/Firefox)
    if (ctrl && shift && (key === 'i' || key === 'I')) { e.preventDefault(); return false; }

    // Ctrl+Shift+J — Dev Tools Console (Chrome)
    if (ctrl && shift && (key === 'j' || key === 'J')) { e.preventDefault(); return false; }

    // Ctrl+Shift+C — Dev Tools Inspector
    if (ctrl && shift && (key === 'c' || key === 'C')) { e.preventDefault(); return false; }

    // Ctrl+Shift+K — Dev Tools (Firefox)
    if (ctrl && shift && (key === 'k' || key === 'K')) { e.preventDefault(); return false; }

    // F12 — Dev Tools
    if (key === 'F12' || code === 'F12') { e.preventDefault(); return false; }

    // Ctrl+A — Select All (on protected areas)
    if (ctrl && (key === 'a' || key === 'A')) {
      // Allow in input fields and textareas
      const tag = document.activeElement && document.activeElement.tagName;
      if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
        e.preventDefault(); return false;
      }
    }

    // Ctrl+P — Print
    if (ctrl && (key === 'p' || key === 'P')) { e.preventDefault(); return false; }

    // Ctrl+C — Copy (block on non-input elements)
    if (ctrl && (key === 'c' || key === 'C')) {
      const tag = document.activeElement && document.activeElement.tagName;
      if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
        // Allow copying from form fields, block page content copy
        e.preventDefault(); return false;
      }
    }
  });

  // ── Disable drag on images ────────────────────────────────
  document.addEventListener('dragstart', function (e) {
    if (e.target.tagName === 'IMG') {
      e.preventDefault();
    }
  });

  // ── DevTools detection via size change ───────────────────
  // (basic heuristic — not 100% but deters casual users)
  const devtools = { open: false };
  const threshold = 200;

  function checkDevtools() {
    if (
      window.outerWidth - window.innerWidth > threshold ||
      window.outerHeight - window.innerHeight > threshold
    ) {
      if (!devtools.open) {
        devtools.open = true;
        // Optionally redirect or warn
        // window.location.href = '/';
      }
    } else {
      devtools.open = false;
    }
  }

  window.addEventListener('resize', checkDevtools);

  // ── Disable text selection on non-editable elements ──────
  // (allow selection in form inputs/textareas)
  document.addEventListener('selectstart', function (e) {
    const tag = e.target && e.target.tagName;
    if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
      e.preventDefault();
      return false;
    }
  });

  // ── Block copy events ─────────────────────────────────────
  document.addEventListener('copy', function (e) {
    const tag = document.activeElement && document.activeElement.tagName;
    if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
      e.preventDefault();
      return false;
    }
  });

  // ── Block cut events ──────────────────────────────────────
  document.addEventListener('cut', function (e) {
    const tag = document.activeElement && document.activeElement.tagName;
    if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
      e.preventDefault();
      return false;
    }
  });

})();
