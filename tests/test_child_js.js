/**
 * Node.js executable test suite for static/js/child.js.
 * Verifies DOM-safe loading, single initialization, HTMX error handlers, and stepper functions.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const scriptCode = fs.readFileSync(path.join(__dirname, "../static/js/child.js"), "utf-8");

// Mock DOM environment simulating <head> execution where document.body is null
function createHeadEnv() {
  const listeners = new Map();
  const elements = new Map();

  const toastElement = {
    textContent: "",
    className: "",
    hidden: true,
    attributes: {},
    setAttribute(name, val) {
      this.attributes[name] = val;
    }
  };
  elements.set("child-toast", toastElement);

  const pageInputElement = {
    value: "5",
    attributes: { min: "0", max: "20" },
    getAttribute(name) {
      return this.attributes[name] || null;
    }
  };
  elements.set("page-input", pageInputElement);

  const doc = {
    body: null, // Critical: document.body is NULL when script evaluates in <head>
    addEventListener(event, handler) {
      if (!listeners.has(event)) {
        listeners.set(event, []);
      }
      listeners.get(event).push(handler);
    },
    dispatchEvent(event, detail) {
      const handlers = listeners.get(event) || [];
      handlers.forEach((h) => h({ detail }));
    },
    getElementById(id) {
      return elements.get(id) || null;
    }
  };

  const win = {
    location: { href: "" }
  };

  const context = {
    window: win,
    document: doc,
    clearTimeout: () => {},
    setTimeout: (cb) => { cb(); },
    parseInt: parseInt,
    Math: Math
  };

  vm.createContext(context);
  return { context, doc, win, toastElement, pageInputElement, listeners };
}

// Test 1: Script must evaluate in <head> without throwing TypeError
console.log("Running Test 1: DOM-safe execution in <head> (document.body === null)...");
const env1 = createHeadEnv();
assert.doesNotThrow(() => {
  vm.runInContext(scriptCode, env1.context);
}, "static/js/child.js threw an error during evaluation in <head>!");
console.log("✓ Test 1 passed: evaluated safely without TypeError.");

// Test 2: Double initialization guard
console.log("Running Test 2: Idempotent initialization guard...");
assert.strictEqual(env1.context.window.__GUSTUL_CHILD_HTMX_INITIALIZED, true);
const listenerCountBefore = Array.from(env1.listeners.values()).reduce((sum, arr) => sum + arr.length, 0);
vm.runInContext(scriptCode, env1.context);
const listenerCountAfter = Array.from(env1.listeners.values()).reduce((sum, arr) => sum + arr.length, 0);
assert.strictEqual(listenerCountBefore, listenerCountAfter, "Second execution registered duplicate listeners!");
console.log("✓ Test 2 passed: duplicate execution safely ignored.");

// Test 3: incrementPage stepper
console.log("Running Test 3: incrementPage stepper boundaries...");
assert.strictEqual(typeof env1.context.window.incrementPage, "function");
env1.context.window.incrementPage(3);
assert.strictEqual(env1.pageInputElement.value, 8);
env1.context.window.incrementPage(20);
assert.strictEqual(env1.pageInputElement.value, 20); // Clamped at max 20
env1.context.window.incrementPage(-50);
assert.strictEqual(env1.pageInputElement.value, 0); // Clamped at min 0
console.log("✓ Test 3 passed: incrementPage correctly clamps within [min, max].");

// Test 4: htmx:beforeSwap swap rules
console.log("Running Test 4: htmx:beforeSwap rules (422 allowed, others rejected)...");
const evt422 = { xhr: { status: 422 }, shouldSwap: false, isError: true };
env1.doc.dispatchEvent("htmx:beforeSwap", evt422);
assert.strictEqual(evt422.shouldSwap, true, "422 must set shouldSwap = true");
assert.strictEqual(evt422.isError, false, "422 must set isError = false");

const evt500 = { xhr: { status: 500 }, shouldSwap: false, isError: true };
env1.doc.dispatchEvent("htmx:beforeSwap", evt500);
assert.strictEqual(evt500.shouldSwap, false, "500 must NOT swap");
console.log("✓ Test 4 passed: beforeSwap allows inline swap only on 422.");

// Test 5: htmx:responseError toast messages and no false saves
console.log("Running Test 5: htmx:responseError error toast notifications...");
// 503 Busy
env1.doc.dispatchEvent("htmx:responseError", { xhr: { status: 503 } });
assert(env1.toastElement.textContent.includes("baza de date este ocupat"), "503 must show database busy message");
assert.strictEqual(env1.toastElement.attributes["role"], "alert");

// 409 Conflict
env1.doc.dispatchEvent("htmx:responseError", { xhr: { status: 409 } });
assert(env1.toastElement.textContent.includes("deja trimis"), "409 must show already sent message");

// 401 Redirect
env1.doc.dispatchEvent("htmx:responseError", {
  xhr: {
    status: 401,
    getResponseHeader: (h) => (h === "HX-Redirect" ? "/cont/autentificare/" : null)
  }
});
assert.strictEqual(env1.context.window.location.href, "/cont/autentificare/", "401 must follow HX-Redirect");
console.log("✓ Test 5 passed: responseError displays appropriate warnings without false saves.");

// Test 6: htmx:sendError network failure toast
console.log("Running Test 6: htmx:sendError offline toast...");
env1.doc.dispatchEvent("htmx:sendError", {});
assert(env1.toastElement.textContent.includes("nu ai conexiune"), "sendError must report offline status");
console.log("✓ Test 6 passed: sendError correctly warns about connection drops.");

// Test 7: saved event
console.log("Running Test 7: saved event confirms real backend write...");
env1.doc.dispatchEvent("saved", {});
assert(env1.toastElement.textContent.includes("Salvat cu succes"), "saved event must show success toast");
assert.strictEqual(env1.toastElement.attributes["role"], "status");
console.log("✓ Test 7 passed: saved event triggers success confirmation.");

console.log("\nALL 7 NODE.JS TESTS PASSED SUCCESSFULLY!");
