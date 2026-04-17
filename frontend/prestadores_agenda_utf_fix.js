(function prestAgendaUtfFixInit() {
  if (window.__prestAgendaUtfFixApplied) return;
  window.__prestAgendaUtfFixApplied = true;

  function fixTextValue(text) {
    var t = String(text || "");
    return t
      .replace(/conv[\?\uFFFD]nio/gi, function (m) {
        return m.charAt(0) === "C" ? "Conv\u00eanio" : "conv\u00eanio";
      })
      .replace(/Convênio/g, "Conv\u00eanio")
      .replace(/convênio/g, "conv\u00eanio")
      .replace(/Convênio/g, "Conv\u00eanio")
      .replace(/convênio/g, "conv\u00eanio")
      .replace(/Obl[\?\uFFFD]quo/g, "Obl\u00edquo")
      .replace(/Oblíquo/g, "Obl\u00edquo")
      .replace(/Cl[\?\uFFFD]nica/g, "Cl\u00ednica")
      .replace(/Clínica/g, "Cl\u00ednica");
  }

  function fixTree(root) {
    if (!(root instanceof HTMLElement)) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var node = walker.nextNode();
    while (node) {
      var original = String(node.nodeValue || "");
      var fixed = fixTextValue(original);
      if (fixed !== original) node.nodeValue = fixed;
      node = walker.nextNode();
    }
  }

  function fixAgendaTexts() {
    var backdrop = document.getElementById("prest-agenda-backdrop");
    if (backdrop instanceof HTMLElement) {
      fixTree(backdrop);
      var pane = backdrop.querySelector("[data-tab='apresentacao']");
      if (pane instanceof HTMLElement) {
        var labels = pane.querySelectorAll("label");
        labels.forEach(function (lbl) {
          if (/pacientes de conv/i.test(String(lbl.textContent || ""))) {
            lbl.textContent = "Pacientes de conv\u00eanio:";
          }
        });
      }
    }

    var fonte = document.getElementById("prest-agenda-fonte-backdrop");
    if (fonte instanceof HTMLElement) fixTree(fonte);
  }

  function startObserver() {
    var body = document.body;
    if (!(body instanceof HTMLElement)) return;
    var pending = false;
    var mo = new MutationObserver(function () {
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        fixAgendaTexts();
      });
    });
    mo.observe(body, { childList: true, subtree: true });
  }

  fixAgendaTexts();
  startObserver();
})();

