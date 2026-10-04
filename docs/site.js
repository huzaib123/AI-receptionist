// Shared page script: WhatsApp links, live clock and footer year.
// Kept in a file (not inline) so the Content-Security-Policy can forbid inline scripts.
(function(){
  // Pre-fill WhatsApp messages, mentioning the visitor's business if the link was personalised.
  var biz = (new URLSearchParams(location.search).get("name") || "").slice(0,60);
  [].forEach.call(document.querySelectorAll("[data-wa]"), function(a){
    var msg = a.getAttribute("data-msg") || "Hi Huzaib, I saw the Aura demo and I'd like to know more.";
    if (biz) msg += " (" + biz + ")";
    a.href = "https://wa.me/60168149934?text=" + encodeURIComponent(msg);
    a.target = "_blank"; a.rel = "noopener";
  });

  // The signboard's live clock makes "open 24 hours" concrete.
  var el = document.getElementById("clock");
  function tick(){
    if (!el) return;
    var t = new Date().toLocaleTimeString("en-MY",{timeZone:"Asia/Kuala_Lumpur",hour:"numeric",minute:"2-digit"});
    el.innerHTML = "It's <strong>" + t + "</strong> in Subang Jaya. Your receptionist is answering.";
  }
  tick(); setInterval(tick, 30000);
  var yr = document.getElementById("yr");
  if (yr) yr.textContent = new Date().getFullYear();
})();
