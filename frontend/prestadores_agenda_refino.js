(function prestAgendaRefinoInit() {
  if (window.__prestAgendaRefinoApplied) return;
  window.__prestAgendaRefinoApplied = true;
  // O patch canônico da aba Apresentação controla os combos de cor.
  // O refino não deve mais construir renderizador próprio.
  window.__prestAgendaApresentacaoPatchApplied = true;
  const VISUALIZACAO_CAMPOS = [
    "Número do paciente",
    "Número do prontuário",
    "Nome do paciente",
    "Matrícula",
    "Convênio",
    "Tabela",
    "Fone 1",
    "Fone 2",
    "Fone 3",
    "Sala",
  ];
  const VISUALIZACAO_PADRAO = [
    "Número do paciente",
    "Nome do paciente",
    "Fone 1",
    "Fone 2",
    "Sala",
  ];

  function setText(node, text) {
    if (node) node.textContent = text;
  }

  function normalizeText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function setBySelector(root, selector, text) {
    const el = (root || document).querySelector(selector);
    if (el) el.textContent = text;
  }

  function applyVisualFitEscala() {
    if (document.getElementById("prest-agenda-refino-style")) return;
    const style = document.createElement("style");
    style.id = "prest-agenda-refino-style";
    style.textContent = [
      "#prest-agenda-backdrop .prest-agenda-modal{width:min(458px,94vw)!important}",
      "#prest-agenda-backdrop .modal-header{padding:6px 10px!important;min-height:30px!important}",
      "#prest-agenda-backdrop .modal-header .modal-title{font:700 12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop .modal-close{width:22px!important;height:22px!important;border-radius:11px!important}",
      "#prest-agenda-backdrop .prest-agenda-body{padding:7px 9px 8px!important}",
      "#prest-agenda-backdrop .prest-agenda-tabs{gap:2px;margin-bottom:6px!important}",
      "#prest-agenda-backdrop .prest-agenda-tab{height:23px!important;padding:0 8px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop .prest-agenda-pane{padding:6px!important;min-height:206px!important}",
      "#prest-agenda-backdrop .prest-agenda-layout{grid-template-columns:206px 170px!important;gap:6px!important;align-items:start!important;justify-content:start!important}",
      "#prest-agenda-backdrop .prest-agenda-group{padding:6px!important}",
      "#prest-agenda-backdrop .prest-agenda-group h4{margin:0 0 4px!important;font:700 12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop .prest-agenda-fields{grid-template-columns:max-content 52px!important;gap:5px 6px!important;justify-content:start!important}",
      "#prest-agenda-backdrop .prest-agenda-fields input,#prest-agenda-backdrop .prest-agenda-fields select{width:52px!important;height:20px!important;padding:0 3px!important}",
      "#prest-agenda-backdrop .prest-agenda-mini{gap:4px!important;justify-content:start!important}",
      "#prest-agenda-backdrop .prest-agenda-mini label{white-space:nowrap!important;line-height:1.1!important}",
      "#prest-agenda-backdrop .prest-agenda-mini input{width:38px!important;height:20px!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-group:first-child .prest-agenda-mini{grid-template-columns:38px max-content!important;align-items:center!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-group:first-child .prest-agenda-mini span:first-child{display:none!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-group:first-child .prest-agenda-mini input{grid-column:1!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-group:first-child .prest-agenda-mini span:last-child{grid-column:2!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-group:last-child .prest-agenda-mini{grid-template-columns:38px max-content!important;row-gap:2px!important;align-items:center!important;margin-bottom:4px!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-group:last-child .prest-agenda-mini label{grid-column:1 / -1!important;margin:0!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-group:last-child .prest-agenda-mini input{grid-column:1!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-group:last-child .prest-agenda-mini span{grid-column:2!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-group{width:100%!important;box-sizing:border-box!important}",
      "#prest-agenda-backdrop .prest-agenda-layout > div:last-child .prest-agenda-mini{width:100%!important}",
      "#prest-agenda-backdrop .prest-agenda-actions{padding-top:5px!important;gap:7px!important}",
      "#prest-agenda-backdrop .prest-agenda-actions .materiais-btn{min-width:70px!important;height:24px!important;padding:0 9px!important;font:12px Tahoma,sans-serif!important;border-radius:2px!important;border:1px solid #b9b9b9!important;background:#efefef!important;box-shadow:none!important}",
      "#prest-agenda-backdrop .prest-agenda-actions .materiais-btn img{display:none!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-toolbar{gap:6px!important;margin-bottom:6px!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-toolbar .materiais-btn{height:24px!important;min-width:86px!important;padding:0 8px!important;border-radius:2px!important;border:1px solid #b9b9b9!important;background:#efefef!important;box-shadow:none!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid{min-height:168px!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid{overflow:hidden!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid table{width:100%!important;table-layout:fixed!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid th,#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid td{height:20px!important;padding:2px 5px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid th:nth-child(1),#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid td:nth-child(1){width:42%!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid th:nth-child(2),#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid td:nth-child(2){width:14%!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid th:nth-child(3),#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid td:nth-child(3){width:22%!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid th:nth-child(4),#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid td:nth-child(4){width:11%!important}",
      "#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid th:nth-child(5),#prest-agenda-backdrop [data-tab='bloqueios'] .prest-agenda-block-grid td:nth-child(5){width:11%!important}",
      "#prest-agenda-bloqueio-backdrop .prest-agenda-block-modal{width:min(540px,94vw)!important}",
      "#prest-agenda-bloqueio-backdrop .modal-body{padding:8px 10px 6px!important}",
      "#prest-agenda-bloqueio-backdrop .prest-agenda-block-row{display:grid!important;grid-template-columns:120px 180px 180px!important;gap:8px!important;align-items:end!important}",
      "#prest-agenda-bloqueio-backdrop .prest-agenda-block-row .prest-agenda-block-field{min-width:0!important}",
      "#prest-agenda-bloqueio-backdrop #prest-agenda-bloqueio-dia{width:100%!important}",
      "#prest-agenda-bloqueio-backdrop #prest-agenda-bloqueio-vigencia-inicio,#prest-agenda-bloqueio-backdrop #prest-agenda-bloqueio-vigencia-fim{width:100%!important}",
      "#prest-agenda-bloqueio-backdrop #prest-agenda-bloqueio-inicio,#prest-agenda-bloqueio-backdrop #prest-agenda-bloqueio-final{width:100%!important}",
      "#prest-agenda-bloqueio-backdrop .prest-agenda-block-field textarea{height:82px!important}",
      "#prest-agenda-bloqueio-backdrop .modal-actions{padding-top:6px!important;gap:8px!important}",
      "#prest-agenda-bloqueio-backdrop .modal-actions .btn,#prest-agenda-bloqueio-backdrop .modal-actions .btn-primary{min-width:74px!important;height:26px!important;border-radius:2px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres{grid-template-columns:1fr 146px!important;gap:8px!important;align-items:start!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-box{padding:8px!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-pane{overflow:visible!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-box{overflow:visible!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-box h4{margin:0 0 6px!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field{grid-template-columns:max-content 24px 1fr!important;gap:6px!important;align-items:center!important;margin-bottom:6px!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field label{grid-column:1!important;white-space:nowrap!important;line-height:1.1!important;margin:0!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field .prest-agenda-apres-swatch{grid-column:2!important;width:22px!important;height:14px!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field select{grid-column:3!important;height:22px!important;padding:0 4px!important;font:12px Tahoma,sans-serif!important;min-width:102px!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-combo{grid-column:3!important;position:relative!important;width:154px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-combo-btn{width:154px!important;height:22px!important;border:1px solid #8fa7c0!important;background:#fff!important;display:grid!important;grid-template-columns:20px 1fr 16px!important;align-items:center!important;padding:0 4px!important;cursor:pointer!important;box-sizing:border-box!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-combo .easy-color-swatch{width:14px!important;height:10px!important;border:1px solid #222!important;display:inline-block!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-combo .easy-color-label{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;text-align:left!important;padding-left:4px!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-combo .easy-color-arrow{font-size:10px!important;line-height:1!important;text-align:center!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-combo .easy-color-list{position:absolute!important;left:0!important;top:21px!important;width:154px!important;max-height:none!important;overflow:visible!important;background:#fff!important;border:1px solid #8fa7c0!important;z-index:12000!important;box-sizing:border-box!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-combo .easy-color-item{height:16px!important;display:grid!important;grid-template-columns:20px 1fr!important;align-items:center!important;gap:4px!important;padding:0 4px!important;cursor:pointer!important;box-sizing:border-box!important;line-height:1!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-combo .easy-color-item:hover{background:#d9e8fb!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-combo .easy-color-item.active{background:#0078d7!important;color:#fff!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] #prest-agenda-apres-fonte{height:24px!important;min-width:94px!important;padding:0 8px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-preview{height:30px!important;margin-bottom:6px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-modal{width:min(560px,94vw)!important;max-width:min(560px,94vw)!important}",
      "#prest-agenda-fonte-backdrop .modal-header{padding:6px 10px!important;min-height:30px!important}",
      "#prest-agenda-fonte-backdrop .modal-title{font:700 12px Tahoma,sans-serif!important}",
      "#prest-agenda-fonte-backdrop .modal-body{padding:8px 10px 8px!important;gap:8px!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-top{grid-template-columns:minmax(0,1.15fr) minmax(0,.75fr) 56px 74px!important;gap:6px!important;align-items:start!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-top > div{min-width:0!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-col{gap:3px!important;min-width:0!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-col label{font:12px Tahoma,sans-serif!important;margin:0!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-col input{height:22px!important;padding:0 5px!important;min-width:0!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-col select{height:138px!important;padding:1px 3px!important;line-height:1.15!important;width:100%!important;min-width:0!important;overflow-x:hidden!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-col option{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-top > div:last-child{padding-top:20px!important;gap:6px!important;min-width:0!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-top > div:last-child .btn,#prest-agenda-fonte-backdrop .prest-agenda-font-top > div:last-child .btn-primary{min-width:66px!important;height:24px!important;padding:0 8px!important;border-radius:3px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-bottom{grid-template-columns:170px 1fr!important;gap:10px!important;align-items:start!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-box{padding:8px!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-box h5{margin:0 0 6px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-effect{margin:5px 0!important;gap:6px!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color{margin-top:6px!important;gap:6px!important}",
      "#prest-agenda-fonte-backdrop #prest-agenda-fonte-sample{height:84px!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-script{margin-top:8px!important;gap:4px!important}",
      "#prest-agenda-fonte-backdrop #prest-agenda-fonte-script{height:24px!important;padding:0 6px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop .prest-agenda-modal:has(.prest-agenda-tab.active[data-tab='visualizacao']){width:min(388px,94vw)!important}",
      "#prest-agenda-backdrop .prest-agenda-modal:has(.prest-agenda-tab.active[data-tab='visualizacao']) .prest-agenda-body{padding:8px 10px 8px!important}",
      "#prest-agenda-backdrop .prest-agenda-modal:has(.prest-agenda-tab.active[data-tab='visualizacao']) .prest-agenda-actions{padding-top:8px!important}",
      "#prest-agenda-backdrop .prest-agenda-modal:has(.prest-agenda-tab.active[data-tab='visualizacao']) .prest-agenda-actions .materiais-btn{min-width:74px!important;height:26px!important}",
      "#prest-agenda-backdrop .prest-agenda-pane[data-tab='visualizacao']{padding:4px!important;min-height:132px!important}",
      "#prest-agenda-backdrop .prest-agenda-pane[data-tab='visualizacao'] .prest-agenda-vis-wrap{border:1px solid #bfc9d6!important;background:#fff!important;padding:5px 7px!important;min-height:118px!important;box-sizing:border-box!important}",
      "#prest-agenda-backdrop .prest-agenda-pane[data-tab='visualizacao'] .prest-agenda-vis-title{display:block!important;margin:0 0 3px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop .prest-agenda-pane[data-tab='visualizacao'] .prest-agenda-vis-list{display:grid!important;grid-template-columns:1fr!important;gap:0!important;align-content:start!important}",
      "#prest-agenda-backdrop .prest-agenda-pane[data-tab='visualizacao'] .prest-agenda-vis-item{display:flex!important;align-items:center!important;gap:4px!important;margin:0!important;font:12px Tahoma,sans-serif!important;line-height:1!important;min-height:16px!important}",
      "#prest-agenda-backdrop .prest-agenda-pane[data-tab='visualizacao'] .prest-agenda-vis-item input{width:13px!important;height:13px!important;margin:0!important}",
      "#prest-agenda-backdrop .prest-agenda-pane[data-tab='visualizacao'] .prest-agenda-vis-item span{display:block!important}",
    ].join("");
    document.head.appendChild(style);
  }

  function normalizeAgendaPrincipal() {
    const backdrop = document.getElementById("prest-agenda-backdrop");
    if (!backdrop) return;

    const item = typeof prestSelecionado === "function" ? prestSelecionado() : null;
    const nome = String(item && item.nome ? item.nome : "").trim();
    const titulo = nome
      ? "Configura hor\u00e1rios de agendamento (" + nome + ")"
      : "Configura hor\u00e1rios de agendamento";
    setBySelector(backdrop, "#prest-agenda-title", titulo);

    const tabs = backdrop.querySelectorAll(".prest-agenda-tab");
    tabs.forEach((tab) => {
      const key = String(tab.dataset.tab || "").trim();
      if (key === "escala") setText(tab, "Escala");
      if (key === "bloqueios") setText(tab, "Bloqueios");
      if (key === "apresentacao") setText(tab, "Apresenta\u00e7\u00e3o");
      if (key === "visualizacao") setText(tab, "Visualiza\u00e7\u00e3o");
    });

    setBySelector(backdrop, "#prest-agenda-ok", "Ok");
    setBySelector(backdrop, "#prest-agenda-cancelar", "Cancela");
  }

  function normalizeEscalaPane() {
    const pane = document.querySelector('#prest-agenda-backdrop [data-tab="escala"]');
    if (!pane) return;

    const groups = pane.querySelectorAll(".prest-agenda-group h4");
    if (groups.length >= 1) setText(groups[0], "Manhã");
    if (groups.length >= 2) setText(groups[1], "Tarde");
    if (groups.length >= 3) setText(groups[2], "Duração do horário");
    if (groups.length >= 4) setText(groups[3], "Visualizar horários");

    const labels = pane.querySelectorAll("label");
    labels.forEach((lbl) => {
      const key = normalizeText(lbl.textContent);
      if (key.includes("horario inicial")) setText(lbl, "Horário inicial..........");
      if (key.includes("horario final")) setText(lbl, "Horário final............");
      if (key.includes("agenda da semana")) setText(lbl, "Agenda da semana:");
      if (key.includes("agenda do dia")) setText(lbl, "Agenda do dia:");
    });

    const spans = pane.querySelectorAll("span");
    spans.forEach((sp) => {
      const key = normalizeText(sp.textContent);
      if (key === "horarios") setText(sp, "horários");
      if (key === "minutos") setText(sp, "minutos");
    });
  }

  function normalizeBloqueiosPane() {
    const pane = document.querySelector('#prest-agenda-backdrop [data-tab="bloqueios"]');
    if (!pane) return;

    setBySelector(pane, "#prest-agenda-bloq-novo", "Novo bloqueio...");
    setBySelector(pane, "#prest-agenda-bloq-editar", "Altera...");
    setBySelector(pane, "#prest-agenda-bloq-excluir", "Elimina");

    const table = pane.querySelector(".prest-agenda-block-grid table");
    const headRow = table ? table.querySelector("thead tr") : null;
    const bodyRows = table ? table.querySelectorAll("tbody tr") : [];
    if (headRow) {
      const ths = headRow.querySelectorAll("th");
      if (ths.length === 4) {
        const thUn = document.createElement("th");
        thUn.textContent = "Unidade";
        headRow.insertBefore(thUn, ths[0]);
        bodyRows.forEach((tr) => {
          const td = document.createElement("td");
          td.textContent = "";
          tr.insertBefore(td, tr.firstElementChild || null);
        });
      }
      if (!table.querySelector("colgroup")) {
        const colgroup = document.createElement("colgroup");
        colgroup.innerHTML =
          '<col style="width:42%"><col style="width:14%"><col style="width:22%"><col style="width:11%"><col style="width:11%">';
        table.insertBefore(colgroup, table.firstChild);
      }
    }

    const th = pane.querySelectorAll("thead th");
    if (th.length >= 5) {
      setText(th[0], "Unidade");
      setText(th[1], "Dia");
      setText(th[2], "Vig\u00eancia");
      setText(th[3], "In\u00edcio");
      setText(th[4], "Final");
    }

    const b = document.getElementById("prest-agenda-bloqueio-backdrop");
    if (!b) return;
    setBySelector(b, "#prest-agenda-bloqueio-title", "Novo bloqueio");

    const labels = b.querySelectorAll("label");
    labels.forEach((lbl) => {
      const t = String(lbl.textContent || "").trim().toLowerCase();
      if (t.includes("unidade")) setText(lbl, "Unidade de atendimento:");
      if (t.includes("dia da semana")) setText(lbl, "Dia da semana:");
      if (t.includes("vig")) setText(lbl, "Per\u00edodo de vig\u00eancia:");
      if (t.includes("intervalo")) setText(lbl, "Intervalo de hor\u00e1rio:");
      if (t.includes("mensagem")) setText(lbl, "Mensagem de alerta:");
    });

    const spans = b.querySelectorAll("span");
    spans.forEach((sp) => {
      const v = String(sp.textContent || "").trim();
      if (v === "?s" || v === "\u00e0s") setText(sp, "\u00e0s");
    });

    const optUnidade = b.querySelectorAll("#prest-agenda-bloqueio-unidade option");
    optUnidade.forEach((o) => {
      const v = String(o.textContent || "");
      if (v.includes("Cl?nica")) setText(o, "Cl\u00ednica");
      if (v.includes("Consult?rio")) setText(o, v.replace(/Consult\?rio/g, "Consult\u00f3rio"));
    });

    const optDia = b.querySelectorAll("#prest-agenda-bloqueio-dia option");
    optDia.forEach((o) => {
      const v = String(o.textContent || "");
      if (v.includes("Ter?a")) setText(o, "Ter\u00e7a");
      if (v.includes("S?bado")) setText(o, "S\u00e1bado");
    });
  }

  function normalizeColorLabel(raw) {
    const base = String(raw || "");
    const key = base
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z ]/g, "")
      .toLowerCase()
      .trim();
    if (key.includes("azul") && key.includes("gua")) return "Azul \u00e1gua";
    if (key === "lils" || key === "lilas") return "Lil\u00e1s";
    if (key.includes("verde") && key.includes("limo")) return "Verde lim\u00e3o";
    const map = {
      amarelo: "Amarelo",
      azul: "Azul",
      "azul agua": "Azul \u00e1gua",
      "azul marinho": "Azul marinho",
      branco: "Branco",
      cinza: "Cinza",
      "cinza claro": "Cinza claro",
      "cinza escuro": "Cinza escuro",
      lilas: "Lil\u00e1s",
      marrom: "Marrom",
      prata: "Prata",
      preto: "Preto",
      roxo: "Roxo",
      verde: "Verde",
      "verde escuro": "Verde escuro",
      "verde limao": "Verde lim\u00e3o",
      "verde oliva": "Verde oliva",
      vermelho: "Vermelho",
    };
    return map[key] || String(raw || "").trim();
  }

  function colorFromLabel(label) {
    const key = String(label || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z ]/g, "")
      .toLowerCase()
      .trim();
    const colors = {
      amarelo: "#ffff00",
      azul: "#0000ff",
      "azul agua": "#00ffff",
      "azul marinho": "#000080",
      branco: "#ffffff",
      cinza: "#808080",
      "cinza claro": "#d3d3d3",
      "cinza escuro": "#696969",
      lilas: "#ff00ff",
      marrom: "#800000",
      prata: "#c0c0c0",
      preto: "#000000",
      roxo: "#800080",
      verde: "#008000",
      "verde escuro": "#006400",
      "verde limao": "#00ff00",
      "verde oliva": "#808000",
      vermelho: "#ff0000",
    };
    return colors[key] || "#ffffff";
  }

  function syncApresentacaoSwatch(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    const row = select.closest(".prest-agenda-apres-field");
    if (!(row instanceof HTMLElement)) return;
    const sw = row.querySelector(".prest-agenda-apres-swatch");
    const opt = select.selectedOptions && select.selectedOptions[0] ? select.selectedOptions[0] : null;
    if (sw instanceof HTMLElement) {
      sw.style.background = String(opt?.dataset?.easyColor || colorFromLabel(opt?.textContent));
    }
  }

  function normalizeApresentacaoPane() {
    const pane = document.querySelector('#prest-agenda-backdrop [data-tab="apresentacao"]');
    if (!pane) return;

    // Remove qualquer combo legado, evitando duplicidade/sobreposição.
    // O render canônico da aba Apresentação fica no patch dedicado.
    pane.querySelectorAll(".easy-color-combo").forEach((node) => node.remove());
    pane.querySelectorAll(".easy-force-combo").forEach((node) => node.remove());

    const h4 = pane.querySelectorAll("h4");
    h4.forEach((h) => {
      const t = String(h.textContent || "").toLowerCase();
      if (t.includes("cor")) setText(h, "Cor de fundo");
      if (t.includes("letra") || t.includes("fonte")) setText(h, "Tipo de letra (fonte)");
    });

    const labels = pane.querySelectorAll("label");
    labels.forEach((lbl) => {
      const t = String(lbl.textContent || "").toLowerCase();
      if (t.includes("particulares")) setText(lbl, "Pacientes particulares:");
      if (t.includes("conv")) setText(lbl, "Pacientes de conv\u00eanio:");
      if (t.includes("compromissos")) setText(lbl, "Compromissos:");
    });
    setBySelector(pane, 'label[for="prest-agenda-apres-particular"]', "Pacientes particulares:");
    setBySelector(pane, 'label[for="prest-agenda-apres-convenio"]', "Pacientes de conv\u00eanio:");
    setBySelector(pane, 'label[for="prest-agenda-apres-compromisso"]', "Compromissos:");

    setBySelector(pane, "#prest-agenda-apres-fonte", "Altera letra...");
    setBySelector(pane, "#prest-agenda-preview-particular", "Particular");
    setBySelector(pane, "#prest-agenda-preview-convenio", "Conv\u00eanio");
    setBySelector(pane, "#prest-agenda-preview-compromisso", "Compromisso");

    ["#prest-agenda-apres-particular", "#prest-agenda-apres-convenio", "#prest-agenda-apres-compromisso"].forEach((sel) => {
      const el = pane.querySelector(sel);
      if (!(el instanceof HTMLSelectElement)) return;
      [...el.options].forEach((opt) => {
        const fixed = normalizeColorLabel(opt.textContent);
        opt.textContent = fixed;
        opt.dataset.easyColor = colorFromLabel(fixed);
      });
      // Render custom desativado no refino; o patch canônico monta a UI final.
      el.classList.remove("hidden");
      el.dataset.easyComboReady = "0";
      syncApresentacaoSwatch(el);
    });
  }

  function closeAllEasyColorCombos(exceptRoot) {
    const roots = document.querySelectorAll('#prest-agenda-backdrop [data-tab="apresentacao"] .easy-color-combo');
    roots.forEach((root) => {
      if (exceptRoot && root === exceptRoot) return;
      const list = root.querySelector(".easy-color-list");
      if (list) list.classList.add("hidden");
      if (root instanceof HTMLElement) root.style.zIndex = "2200";
    });
  }

  function buildEasyColorCombo(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    return;
    const sibling = select.nextElementSibling;
    const hasComboSibling = sibling instanceof HTMLElement && sibling.classList.contains("easy-color-combo");
    if (select.dataset.easyComboReady === "1" && hasComboSibling) {
      syncEasyColorCombo(select);
      return;
    }
    if (select.dataset.easyComboReady === "1" && !hasComboSibling) {
      select.dataset.easyComboReady = "0";
    }
    select.dataset.easyComboReady = "1";

    const root = document.createElement("div");
    root.className = "easy-color-combo";
    root.innerHTML = [
      '<button type="button" class="easy-color-combo-btn">',
      '<span class="easy-color-swatch"></span>',
      '<span class="easy-color-label"></span>',
      '<span class="easy-color-arrow">\u25be</span>',
      "</button>",
      '<div class="easy-color-list hidden"></div>',
    ].join("");

    select.insertAdjacentElement("afterend", root);
    select.classList.add("hidden");

    const btn = root.querySelector(".easy-color-combo-btn");
    const list = root.querySelector(".easy-color-list");
    if (!(btn instanceof HTMLButtonElement) || !(list instanceof HTMLDivElement)) return;

    function renderList() {
      list.innerHTML = "";
      [...select.options].forEach((opt, idx) => {
        const item = document.createElement("div");
        item.className = "easy-color-item";
        if (idx === select.selectedIndex) item.classList.add("active");

        const sw = document.createElement("span");
        sw.className = "easy-color-swatch";
        sw.style.background = String(opt.dataset.easyColor || colorFromLabel(opt.textContent));

        const lb = document.createElement("span");
        lb.className = "easy-color-label";
        lb.textContent = String(opt.textContent || "");

        item.appendChild(sw);
        item.appendChild(lb);
        item.addEventListener("click", () => {
          select.selectedIndex = idx;
          select.dispatchEvent(new Event("change", { bubbles: true }));
          syncEasyColorCombo(select);
          closeAllEasyColorCombos();
        });
        list.appendChild(item);
      });
    }

    btn.addEventListener("click", () => {
      const willOpen = list.classList.contains("hidden");
      closeAllEasyColorCombos(willOpen ? root : null);
      list.classList.toggle("hidden", !willOpen);
      if (root instanceof HTMLElement) root.style.zIndex = willOpen ? "13000" : "2200";
    });

    select.addEventListener("change", () => {
      syncEasyColorCombo(select);
      renderList();
    });

    renderList();
    syncEasyColorCombo(select);
  }

  function syncEasyColorCombo(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    const root = select.nextElementSibling;
    if (!(root instanceof HTMLElement) || !root.classList.contains("easy-color-combo")) return;

    const opt = select.selectedOptions && select.selectedOptions[0] ? select.selectedOptions[0] : null;
    const sw = root.querySelector(".easy-color-combo-btn .easy-color-swatch");
    const lb = root.querySelector(".easy-color-combo-btn .easy-color-label");

    if (sw) sw.style.background = String(opt?.dataset?.easyColor || colorFromLabel(opt?.textContent));
    if (lb) lb.textContent = String(opt?.textContent || "");

    const items = root.querySelectorAll(".easy-color-item");
    items.forEach((it) => it.classList.remove("active"));
    items.forEach((it, idx) => {
      if (idx === select.selectedIndex) it.classList.add("active");
    });
  }

  function normalizeFonteModal() {
    const b = document.getElementById("prest-agenda-fonte-backdrop");
    if (!b) return;

    const title = b.querySelector(".modal-title");
    if (title) setText(title, "Fonte");

    const labels = b.querySelectorAll("label");
    labels.forEach((lbl) => {
      const t = String(lbl.textContent || "").trim().toLowerCase();
      if (t === "fonte:") setText(lbl, "Fonte:");
      if (t.includes("estilo")) setText(lbl, "Estilo da fonte:");
      if (t.includes("tamanho")) setText(lbl, "Tamanho:");
      if (t === "cor:" || t.includes("cor")) setText(lbl, "Cor:");
      if (t.includes("script")) setText(lbl, "Script:");
    });

    // Mantém a área de cor da janela Fonte como no estado anterior estável.
  }

  function normalizeVisualizacaoPane() {
    const pane = document.querySelector('#prest-agenda-backdrop [data-tab="visualizacao"]');
    if (!pane) return;
    if (!pane.dataset.visualizacaoEnhanced) {
      const existingTextarea = pane.querySelector("#prest-agenda-visualizacao");
      const hiddenTextarea = existingTextarea instanceof HTMLTextAreaElement ? existingTextarea : document.createElement("textarea");
      hiddenTextarea.id = "prest-agenda-visualizacao";
      hiddenTextarea.classList.add("hidden");

      pane.innerHTML = [
        '<div class="prest-agenda-vis-box">',
        '<label for="prest-agenda-visualizacao-lista" class="prest-agenda-vis-title">Dados a serem visualizados no agendamento:</label>',
        '<div id="prest-agenda-visualizacao-lista" class="prest-agenda-vis-lista"></div>',
        "</div>",
      ].join("");
      pane.appendChild(hiddenTextarea);

      const lista = pane.querySelector("#prest-agenda-visualizacao-lista");
      if (lista) {
        lista.innerHTML = VISUALIZACAO_CAMPOS.map(
          (campo) =>
            `<label class="prest-agenda-vis-item"><input type="checkbox" value="${campo}"><span>${campo}</span></label>`
        ).join("");
      }
      pane.dataset.visualizacaoEnhanced = "1";
    }

    const lbl = pane.querySelector(".prest-agenda-vis-title");
    if (lbl) setText(lbl, "Dados a serem visualizados no agendamento:");

    const textarea = pane.querySelector("#prest-agenda-visualizacao");
    if (window.prestCfg?.agenda) {
      window.prestCfg.agenda.visualizacao = textarea instanceof HTMLTextAreaElement ? textarea : null;
      window.prestCfg.agenda.visualizacaoChecks = [
        ...pane.querySelectorAll('.prest-agenda-vis-item input[type="checkbox"]'),
      ];
    }

    const item = typeof window.prestSelecionado === "function" ? window.prestSelecionado() : null;
    const camposSalvos = Array.isArray(item?.agenda_config?.visualizacao_campos)
      ? item.agenda_config.visualizacao_campos
      : VISUALIZACAO_PADRAO;
    const camposNormalizados = new Set(
      camposSalvos.map((campo) => normalizeText(campo)).filter(Boolean)
    );
    if (Array.isArray(window.prestCfg?.agenda?.visualizacaoChecks)) {
      window.prestCfg.agenda.visualizacaoChecks.forEach((chk) => {
        chk.checked = camposNormalizados.has(normalizeText(chk.value));
      });
    }
  }

  window.prestAgendaEnhanceVisualizacao = function prestAgendaEnhanceVisualizacaoRefinada() {
    normalizeVisualizacaoPane();
  };

  function runNormalize() {
    applyVisualFitEscala();
    normalizeAgendaPrincipal();
    normalizeEscalaPane();
    normalizeBloqueiosPane();
    normalizeApresentacaoPane();
    normalizeFonteModal();
    normalizeVisualizacaoPane();
  }

  const oldAgendaAbrir = window.prestAgendaAbrir;
  if (typeof oldAgendaAbrir === "function") {
    window.prestAgendaAbrir = function prestAgendaAbrirRefinado() {
      const ret = oldAgendaAbrir.apply(this, arguments);
      setTimeout(runNormalize, 0);
      setTimeout(runNormalize, 120);
      return ret;
    };
  }

  const oldEnsure = window.prestAgendaEnsureUI;
  if (typeof oldEnsure === "function") {
    window.prestAgendaEnsureUI = function prestAgendaEnsureUIRefinado() {
      const ret = oldEnsure.apply(this, arguments);
      setTimeout(runNormalize, 0);
      return ret;
    };
  }

  document.addEventListener("click", (ev) => {
    const target = ev.target;
    if (!(target instanceof Node) || !(target instanceof Element)) return;
    if (!target.closest('#prest-agenda-backdrop [data-tab="apresentacao"] .easy-color-combo') &&
        !target.closest('#prest-agenda-backdrop [data-tab="apresentacao"] .easy-color-dropdown')) {
      closeAllEasyColorCombos();
    }
    const tab = ev.target && ev.target.closest ? ev.target.closest(".prest-agenda-tab") : null;
    if (!tab) return;
    setTimeout(runNormalize, 0);
  });

  setTimeout(runNormalize, 0);
})();

