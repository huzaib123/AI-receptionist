// Aura — motion layer: scroll reveals, hero entrance, header and progress bar,
// gentle parallax, price count-up and eased anchor scrolling. Skipped entirely
// for visitors who prefer reduced motion. Kept in a file so the CSP can forbid
// inline scripts.
(function(){
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var top = document.querySelector(".top");
  var bar = document.createElement("div"); bar.className = "progress"; bar.setAttribute("aria-hidden","true");
  document.body.appendChild(bar);

  // Header shadow and reading progress (cheap, so kept even with reduced motion).
  var ticking = false;
  function onScroll(){
    if (ticking) return; ticking = true;
    requestAnimationFrame(function(){
      var y = scrollY, max = document.documentElement.scrollHeight - innerHeight;
      if (top) top.classList.toggle("scrolled", y > 8);
      bar.style.transform = "scaleX(" + (max > 0 ? Math.min(1, y / max) : 0) + ")";
      if (sign && !reduce && fine) sign.style.transform = "translate3d(0," + Math.min(y * 0.12, 60) + "px,0)";
      ticking = false;
    });
  }
  var sign = document.querySelector(".hero .sign");
  var fine = matchMedia("(hover:hover) and (pointer:fine)").matches;
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  if (reduce) return;

  document.documentElement.classList.add("motion");

  // Split the headline into words so it can rise one word at a time.
  function splitWords(el){
    var words = el.textContent.trim().split(/\s+/);
    el.textContent = "";
    words.forEach(function(w, i){
      var s = document.createElement("span"); s.className = "w"; s.style.setProperty("--i", i); s.textContent = w;
      el.appendChild(s); if (i < words.length - 1) el.appendChild(document.createTextNode(" "));
    });
  }
  var h1 = document.getElementById("headline"), pill = document.getElementById("pill");
  if (h1) {
    splitWords(h1);
    // The demo rewrites the headline when a business tab is picked: replay a short swap.
    var swapping = false;
    new MutationObserver(function(){
      if (swapping) return; swapping = true;
      [h1, pill].forEach(function(el){ if(!el) return; el.classList.remove("swap"); void el.offsetWidth; el.classList.add("swap"); });
      swapping = false;
    }).observe(h1, { childList: true, characterData: true, subtree: true });
  }

  // Scroll reveals, staggered within each group.
  function mark(sel, kind, step){
    document.querySelectorAll(sel).forEach(function(group){
      var kids = group.matches("[data-group]") ? group.children : [group];
      [].forEach.call(kids, function(el, i){
        el.setAttribute("data-reveal", kind || "");
        el.style.setProperty("--d", ((step || 0) * i) + "s");
      });
    });
  }
  document.querySelectorAll(".asks,.steps,.board,.creds,.promise,.faq").forEach(function(g){ g.setAttribute("data-group",""); });
  mark(".sec h2");
  mark(".sec .intro");
  mark(".asks", "left", 0.08);
  mark(".steps", "", 0.12);
  mark(".board", "", 0.1);
  mark(".me-card", "left");
  mark(".owner .say");
  mark(".creds", "pop", 0.08);
  mark(".promise", "right", 0.06);
  mark(".faq", "", 0.06);
  mark(".contact");

  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if (!e.isIntersecting) return;
      e.target.classList.add("in");
      io.unobserve(e.target);
      if (e.target.querySelector && e.target.querySelector(".price")) countUp(e.target.querySelector(".price"));
    });
  }, { rootMargin: "0px 0px -10% 0px", threshold: 0.12 });
  document.querySelectorAll("[data-reveal]").forEach(function(el){ io.observe(el); });

  // Prices count up from zero the first time they appear.
  function countUp(el){
    var node = el.firstChild; if (!node || node.nodeType !== 3) return;
    var m = node.nodeValue.match(/([\d,]+)/); if (!m) return;
    var target = parseInt(m[1].replace(/,/g,""), 10), start = null, prefix = node.nodeValue.slice(0, m.index), suffix = node.nodeValue.slice(m.index + m[1].length);
    function frame(t){
      if (!start) start = t;
      var p = Math.min(1, (t - start) / 900), eased = 1 - Math.pow(1 - p, 3);
      node.nodeValue = prefix + Math.round(target * eased).toLocaleString("en-MY") + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // Eased scrolling for in-page links, landing just below the sticky header.
  function easeTo(y){
    var from = scrollY, dist = y - from, dur = Math.min(1100, 400 + Math.abs(dist) * 0.35), t0 = null;
    document.documentElement.style.scrollBehavior = "auto";
    function step(t){
      if (!t0) t0 = t;
      var p = Math.min(1, (t - t0) / dur), e = p < .5 ? 4*p*p*p : 1 - Math.pow(-2*p + 2, 3) / 2;
      scrollTo(0, from + dist * e);
      if (p < 1) requestAnimationFrame(step); else document.documentElement.style.scrollBehavior = "";
    }
    requestAnimationFrame(step);
  }
  document.addEventListener("click", function(ev){
    var a = ev.target.closest && ev.target.closest('a[href^="#"]');
    if (!a || a.getAttribute("href").length < 2) return;
    var target = document.getElementById(a.getAttribute("href").slice(1));
    if (!target) return;
    ev.preventDefault();
    easeTo(target.getBoundingClientRect().top + scrollY - (top ? top.offsetHeight + 12 : 0));
    history.pushState(null, "", a.getAttribute("href"));
  });
})();
