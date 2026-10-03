/*
 * Cookie consent. The site sets no tracking cookies by default. If a visitor
 * accepts, window.auraConsent === "accepted" and an "aura:consent" event fires,
 * so optional analytics can be loaded only then.
 */
(function () {
  var KEY = "aura_cookie_consent";
  function get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function set(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }

  var box = document.createElement("div");
  box.className = "consent";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-labelledby", "consent-title");
  box.innerHTML =
    '<h2 id="consent-title">Cookies on this site</h2>' +
    '<p>We only use what the site needs to work. With your OK, we would also use privacy-friendly analytics to see which pages are useful. You can change this any time from the footer. <a href="privacy.html#cookies">Read the cookie policy</a>.</p>' +
    '<div class="row">' +
      '<button type="button" class="btn plain small" data-v="rejected">Reject</button>' +
      '<button type="button" class="btn small" data-v="accepted">Accept</button>' +
    '</div>';

  function apply(v) {
    window.auraConsent = v;
    document.dispatchEvent(new CustomEvent("aura:consent", { detail: v }));
  }
  function open() { box.classList.add("show"); box.querySelector("[data-v=rejected]").focus(); }

  box.addEventListener("click", function (e) {
    var v = e.target && e.target.getAttribute("data-v");
    if (!v) return;
    set(v); apply(v);
    box.classList.remove("show");
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.body.appendChild(box);
    var v = get();
    if (v) apply(v); else box.classList.add("show");
    [].forEach.call(document.querySelectorAll("[data-cookie-settings]"), function (b) {
      b.addEventListener("click", open);
    });
  });
})();
