(function(){
  function previewText(secao){
    switch(String(secao||"")){
      case "enunciados": return "Enunciado";
      case "campos_edicao": return "Campo";
      case "botoes_funcao": return "Botao de funcao";
      case "outros_botoes": return 'Botao "Radio"';
      case "itens_lista": return "Item 1";
      default: return "AaBbYyZz";
    }
  }

  function toDialogValue(style){
    const ref=style||{};
    return{
      family:String(ref.fonte_nome||"Tahoma"),
      size:Number(ref.fonte_tamanho||12)||12,
      styleId:typeof window.easyFontNormalizeStyleId==="function"?window.easyFontNormalizeStyleId(ref.fonte_estilo):String(ref.fonte_estilo||"normal"),
      color:String(ref.cor_texto||"#000000"),
      strike:!!ref.riscado,
      underline:!!ref.sublinhado,
      script:String(ref.script||"Ocidental"),
    };
  }

  function fromDialogValue(base,valor){
    const ref=(typeof window.prefAmbEstiloPadrao==="function"?window.prefAmbEstiloPadrao():{})||{};
    return{
      ...ref,
      ...(base||{}),
      fonte_nome:String(valor?.family||ref.fonte_nome||"Tahoma"),
      fonte_tamanho:Number(valor?.size||ref.fonte_tamanho||12)||12,
      fonte_estilo:typeof window.easyFontNormalizeStyleId==="function"?window.easyFontNormalizeStyleId(valor?.styleId):String(valor?.styleId||ref.fonte_estilo||"normal"),
      cor_texto:String(valor?.color||ref.cor_texto||"#000000").toLowerCase(),
      riscado:!!valor?.strike,
      sublinhado:!!valor?.underline,
      script:String(valor?.script||ref.script||"Ocidental"),
    };
  }

  function ensureStyle(){
    if(document.getElementById("pref-ambiente-patch-style"))return;
    const style=document.createElement("style");
    style.id="pref-ambiente-patch-style";
    style.textContent=[
      "#config-preferencias-backdrop .pref-amb-controls{display:none!important}",
      "#config-preferencias-backdrop .pref-amb-choice label{display:inline-flex!important;align-items:center!important;gap:4px!important}",
      "#config-preferencias-backdrop .pref-amb-choice label span{display:inline-block!important}",
      "#config-preferencias-backdrop .pref-amb-example{min-height:162px!important}",
      "#config-preferencias-backdrop .pref-amb-toolbar:last-child{justify-content:flex-end!important;margin-top:8px!important}"
    ].join("");
    document.head.appendChild(style);
  }

  function ensurePreviewLabels(){
    if(!window.prefCfg?.backdrop)return;
    const labels=window.prefCfg.backdrop.querySelectorAll(".pref-amb-choice label");
    if(labels[0]){
      let span=labels[0].querySelector("span");
      if(!span){
        span=document.createElement("span");
        const text=Array.from(labels[0].childNodes).filter(node=>node.nodeType===Node.TEXT_NODE).map(node=>node.textContent||"").join(" ")||' Botao "Radio"';
        Array.from(labels[0].childNodes).forEach(node=>{if(node.nodeType===Node.TEXT_NODE)node.textContent=""});
        span.textContent=String(text).trim();
        labels[0].appendChild(span);
      }
      window.prefCfg.ambRadioLabel=span;
    }
    if(labels[1]){
      let span=labels[1].querySelector("span");
      if(!span){
        span=document.createElement("span");
        const text=Array.from(labels[1].childNodes).filter(node=>node.nodeType===Node.TEXT_NODE).map(node=>node.textContent||"").join(" ")||" Caixa de checagem";
        Array.from(labels[1].childNodes).forEach(node=>{if(node.nodeType===Node.TEXT_NODE)node.textContent=""});
        span.textContent=String(text).trim();
        labels[1].appendChild(span);
      }
      window.prefCfg.ambCheckLabel=span;
    }
  }

  function bindAlterarButton(){
    if(!window.prefCfg?.btnAmbienteAlterar)return;
    const oldBtn=window.prefCfg.btnAmbienteAlterar;
    if(oldBtn.dataset.prefAmbPatched==="1")return;
    const novo=oldBtn.cloneNode(true);
    novo.dataset.prefAmbPatched="1";
    oldBtn.parentNode.replaceChild(novo,oldBtn);
    window.prefCfg.btnAmbienteAlterar=novo;
    novo.addEventListener("click",function(ev){
      ev.preventDefault();
      ev.stopPropagation();
      const secao=typeof window.prefAmbienteSecaoAtiva==="function"?window.prefAmbienteSecaoAtiva():"enunciados";
      const atual=typeof window.prefAmbienteEstiloAtual==="function"?window.prefAmbienteEstiloAtual():{};
      if(typeof window.easyFontAbrir!=="function")return;
      window.easyFontAbrir({
        initialValue:toDialogValue(atual),
        previewText:previewText(secao),
        onSave:function(valor){
          const secoes=typeof window.prefAmbienteSecoesAtuais==="function"?window.prefAmbienteSecoesAtuais():{};
          secoes[secao]=fromDialogValue(secoes[secao],valor);
          window.prefCfg.ambienteValues={...(window.prefCfg.ambienteValues||{}),secao_ativa:secao,secoes};
          if(typeof window.prefSincronizarUI==="function")window.prefSincronizarUI();
        }
      });
    });
  }

  function patchUI(){
    if(!window.prefCfg?.backdrop)return;
    ensureStyle();
    ensurePreviewLabels();
    bindAlterarButton();
  }

  if(typeof prefEnsureUI==="function"){
    const originalPrefEnsureUI=prefEnsureUI;
    prefEnsureUI=function(){
      originalPrefEnsureUI();
      patchUI();
    };
    window.prefEnsureUI=prefEnsureUI;
  }

  if(typeof prefSincronizarUI==="function"){
    const originalPrefSincronizarUI=prefSincronizarUI;
    prefSincronizarUI=function(){
      originalPrefSincronizarUI();
      patchUI();
      if(typeof window.prefAplicarPreviewAmbiente==="function")window.prefAplicarPreviewAmbiente();
    };
    window.prefSincronizarUI=prefSincronizarUI;
  }

  prefColetarPayloadAmbiente=window.prefColetarPayloadAmbiente=function(){
    if(!window.prefCfg)return null;
    const ctx=typeof window.prefContextoAtual==="function"?window.prefContextoAtual():{};
    return{
      user_id:Number(ctx.userId||0)||undefined,
      secao_ativa:typeof window.prefAmbienteSecaoAtiva==="function"?window.prefAmbienteSecaoAtiva():"enunciados",
      secoes:typeof window.prefAmbienteSecoesAtuais==="function"?window.prefAmbienteSecoesAtuais():{},
    };
  };
})();
