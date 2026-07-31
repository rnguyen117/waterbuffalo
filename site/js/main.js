(function () {
  "use strict";

  var toggle = document.querySelector(".nav-toggle");
  var mobileNav = document.getElementById("mobile-nav");

  if (toggle && mobileNav) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      toggle.setAttribute("aria-label", open ? "Open menu" : "Close menu");
      mobileNav.hidden = open;
      mobileNav.classList.toggle("is-open", !open);
    });

    mobileNav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "Open menu");
        mobileNav.hidden = true;
        mobileNav.classList.remove("is-open");
      });
    });
  }

  // Close the desktop Services dropdown when clicking outside it.
  document.querySelectorAll(".nav-dropdown").forEach(function (dd) {
    document.addEventListener("click", function (e) {
      if (dd.open && !dd.contains(e.target)) dd.removeAttribute("open");
    });
  });

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revealEls = document.querySelectorAll(".reveal");

  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealEls.forEach(function (el) { el.classList.add("is-visible"); });
  } else {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -60px 0px" }
    );
    revealEls.forEach(function (el) { observer.observe(el); });
  }

  var form = document.querySelector(".contact-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = form.querySelector("button");
      var original = btn.textContent;
      var fields = form.querySelectorAll("input, select, textarea");
      var data = new FormData(form);
      var endpoint = form.action.replace("formsubmit.co/", "formsubmit.co/ajax/");

      btn.textContent = "Sending…";
      btn.disabled = true;
      fields.forEach(function (f) { f.disabled = true; });

      fetch(endpoint, {
        method: "POST",
        headers: { Accept: "application/json" },
        body: data,
      })
        .then(function (res) {
          if (!res.ok) throw new Error("Request failed");
          return res.json();
        })
        .then(function (json) {
          if (json && json.success === "false") throw new Error(json.message || "Request failed");
          btn.textContent = "Thanks — we'll be in touch";
          form.reset();
          setTimeout(function () {
            btn.textContent = original;
            btn.disabled = false;
            fields.forEach(function (f) { f.disabled = false; });
          }, 5000);
        })
        .catch(function () {
          btn.textContent = "Something went wrong — please try again";
          btn.disabled = false;
          fields.forEach(function (f) { f.disabled = false; });
          setTimeout(function () { btn.textContent = original; }, 5000);
        });
    });
  }
})();
