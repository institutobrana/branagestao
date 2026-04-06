(function(){
  const STYLE_OPTIONS=[
    {id:"normal",label:"Regular",weight:"400",italic:false},
    {id:"italico",label:"Obliquo",weight:"400",italic:true},
    {id:"negrito",label:"Negrito",weight:"700",italic:false},
    {id:"negrito-italico",label:"Obliquo e negrito",weight:"700",italic:true},
  ];
  const SCRIPT_OPTIONS=[{id:"Ocidental",label:"Ocidental"}];
  const SIZE_OPTIONS=[8,9,10,11,12,...Array.from({length:31},(_,i)=>14+i*2)];
  const COLOR_PALETTE=[
    {value:"#000000",label:"Preto"},
    {value:"#800000",label:"Bordo"},
    {value:"#008000",label:"Verde"},
    {value:"#808000",label:"Verde-oliva"},
    {value:"#000080",label:"Azul-marinho"},
    {value:"#800080",label:"Roxo"},
    {value:"#008080",label:"Azul-petroleo"},
    {value:"#808080",label:"Cinza"},
    {value:"#c0c0c0",label:"Prateado"},
    {value:"#ff0000",label:"Vermelho"},
    {value:"#00ff00",label:"Verde-limao"},
    {value:"#ffff00",label:"Amarelo"},
    {value:"#0000ff",label:"Azul"},
    {value:"#ff00ff",label:"Fucsia"},
    {value:"#00ffff",label:"Azul-piscina"},
    {value:"#ffffff",label:"Branco"},
  ];
  const COLOR_BY_VALUE={};
  COLOR_PALETTE.forEach(item=>{COLOR_BY_VALUE[String(item.value||"").toLowerCase()]=item});
  let dlg=null;

  function normalizeStyleId(value){
    const raw=String(value||"").trim().toLowerCase();
    if(["negrito","bold","fsbold"].includes(raw))return"negrito";
    if(["italico","italic","obliquo","obl","fsitalic"].includes(raw))return"italico";
    if(["negrito-italico","italico-negrito","bolditalic","italicbold","obliquo e negrito","fsbolditalic","fsitalicbold"].includes(raw))return"negrito-italico";
    return"normal";
  }

  function defaultValue(){
    return{
      family:"MS Sans Serif",
      styleId:"normal",
      size:8,
      color:"#000000",
      strike:false,
      underline:false,
      script:"Ocidental",
    };
  }

  function currentStyle(styleId){
    return STYLE_OPTIONS.find(item=>item.id===normalizeStyleId(styleId))||STYLE_OPTIONS[0];
  }

  function uniqueSorted(values){
    const seen=new Set();
    const out=[];
    (Array.isArray(values)?values:[]).forEach(value=>{
      const text=String(value||"").trim();
      const key=text.toLowerCase();
      if(!text||seen.has(key))return;
      seen.add(key);
      out.push(text);
    });
    return out.sort((a,b)=>a.localeCompare(b,"pt-BR"));
  }

  function fallbackFonts(){
    return["MS Sans Serif","MS Serif","Arial","Tahoma","Verdana","Times New Roman","Courier New","Segoe UI"];
  }

  async function getSystemFonts(){
    if(Array.isArray(window.__easyFontSystemFontsCache)&&window.__easyFontSystemFontsCache.length){
      return window.__easyFontSystemFontsCache.slice();
    }
    let families=[];
    if(typeof window.queryLocalFonts==="function"){
      try{
        const fonts=await window.queryLocalFonts();
        families=uniqueSorted((fonts||[]).map(item=>item&&item.family?String(item.family):""));
      }catch{}
    }
    if(!families.length&&typeof window.cnfRelatorioFontesDisponiveis==="function"){
      try{families=uniqueSorted(window.cnfRelatorioFontesDisponiveis())}catch{}
    }
    if(!families.length)families=fallbackFonts();
    window.__easyFontSystemFontsCache=families.slice();
    return families;
  }

  function ensureStyle(){
    if(document.getElementById("easy-font-shared-style"))return;
    const style=document.createElement("style");
    style.id="easy-font-shared-style";
    style.textContent=[
      "#easy-font-backdrop .easy-font-modal{width:min(560px,94vw);background:#f5f5f3;border:1px solid #c8ced8;box-sizing:border-box}",
      "#easy-font-backdrop .modal-header{padding:6px 10px;min-height:30px}",
      "#easy-font-backdrop .modal-title{font:700 12px Tahoma,sans-serif}",
      "#easy-font-backdrop .easy-font-body{padding:8px 10px 8px;display:grid;gap:8px}",
      "#easy-font-backdrop .easy-font-top{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.75fr) 56px 74px;gap:6px;align-items:start}",
      "#easy-font-backdrop .easy-font-top>div{min-width:0}",
      "#easy-font-backdrop .easy-font-col{display:flex;flex-direction:column;gap:3px;min-width:0}",
      "#easy-font-backdrop .easy-font-col label{margin:0;font:12px Tahoma,sans-serif}",
      "#easy-font-backdrop .easy-font-col input{height:22px;border:1px solid #bfc9d6;padding:0 5px;min-width:0;font:12px Tahoma,sans-serif;box-sizing:border-box}",
      "#easy-font-backdrop .easy-font-col select{height:138px;border:1px solid #bfc9d6;padding:1px 3px;font:12px Tahoma,sans-serif;box-sizing:border-box;width:100%;min-width:0;overflow-x:hidden}",
      "#easy-font-backdrop .easy-font-col option{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
      "#easy-font-backdrop .easy-font-actions{display:flex;flex-direction:column;gap:6px;padding-top:20px}",
      "#easy-font-backdrop .easy-font-actions .materiais-btn{min-width:66px;height:24px;padding:0 8px;border-radius:3px;font:12px Tahoma,sans-serif;justify-content:center}",
      "#easy-font-backdrop .easy-font-bottom{display:grid;grid-template-columns:170px 1fr;gap:10px;align-items:start}",
      "#easy-font-backdrop .easy-font-box{border:1px solid #bfc9d6;background:#fff;padding:8px;box-sizing:border-box}",
      "#easy-font-backdrop .easy-font-box h5{margin:0 0 6px;font:12px Tahoma,sans-serif}",
      "#easy-font-backdrop .easy-font-effect{display:flex;align-items:center;gap:6px;margin:5px 0}",
      "#easy-font-backdrop .easy-font-effect input{margin:0}",
      "#easy-font-backdrop .easy-font-color{display:flex;align-items:center;gap:6px;margin-top:6px;position:relative}",
      "#easy-font-backdrop .easy-font-script{display:flex;flex-direction:column;gap:4px;margin-top:8px}",
      "#easy-font-backdrop .easy-font-script select{height:24px;border:1px solid #bfc9d6;padding:0 6px;font:12px Tahoma,sans-serif;box-sizing:border-box}",
      "#easy-font-backdrop .easy-font-preview{height:84px;border:1px solid #d8d8d8;background:#fff;display:flex;align-items:center;justify-content:center;font:12px Tahoma,sans-serif}",
      "#easy-font-backdrop .modal-actions{display:flex;justify-content:flex-end;gap:8px;padding-top:2px}",
      "#easy-font-backdrop .modal-actions .materiais-btn{min-width:74px;height:28px;padding:0 10px;border-radius:4px;font:12px Tahoma,sans-serif;justify-content:center}",
      "#easy-font-backdrop .easy-font-color-dropdown{position:relative;width:104px;font:12px Tahoma,sans-serif}",
      "#easy-font-backdrop .easy-font-color-btn{width:104px;height:22px;border:1px solid #8fa7c0;background:#fff;display:grid;grid-template-columns:20px 1fr 14px;align-items:center;padding:0 4px;box-sizing:border-box;cursor:pointer}",
      "#easy-font-backdrop .easy-font-color-swatch{width:14px;height:10px;border:1px solid #222;display:inline-block}",
      "#easy-font-backdrop .easy-font-color-label{text-align:left;padding-left:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
      "#easy-font-backdrop .easy-font-color-list{position:absolute;left:0;top:21px;width:104px;background:#fff;border:1px solid #8fa7c0;box-sizing:border-box;z-index:12050}",
      "#easy-font-backdrop .easy-font-color-item{height:16px;display:grid;grid-template-columns:20px 1fr;align-items:center;gap:4px;padding:0 4px;box-sizing:border-box;cursor:pointer;line-height:1}",
      "#easy-font-backdrop .easy-font-color-item:hover{background:#d9e8fb}",
      "#easy-font-backdrop .easy-font-color-item.active{background:#0078d7;color:#fff}",
      "#easy-font-backdrop .easy-font-color-hidden{display:none}",
      "#easy-font-backdrop #easy-font-color-swatch{display:none}",
      "#easy-font-backdrop #easy-font-color.easy-font-native-hidden{display:none;visibility:hidden;position:absolute;left:-9999px;top:-9999px;pointer-events:none}",
    ].join("");
    document.head.appendChild(style);
  }

  function ensurePalette(select){
    if(!(select instanceof HTMLSelectElement))return;
    const currentValue=String(select.value||"").trim().toLowerCase();
    const selected=COLOR_BY_VALUE[currentValue]||COLOR_PALETTE[0];
    select.innerHTML=COLOR_PALETTE.map(item=>`<option value="${item.value}">${item.label}</option>`).join("");
    select.value=selected.value;
  }

  function closeColorDropdowns(except){
    document.querySelectorAll("#easy-font-backdrop .easy-font-color-list").forEach(list=>{
      if(except&&list===except)return;
      list.classList.add("easy-font-color-hidden");
    });
  }

  function syncColorHeader(){
    if(!dlg?.colorRoot||!(dlg.color instanceof HTMLSelectElement))return;
    const option=dlg.color.selectedOptions&&dlg.color.selectedOptions[0]?dlg.color.selectedOptions[0]:null;
    const item=option?COLOR_BY_VALUE[String(option.value||"").toLowerCase()]:COLOR_PALETTE[0];
    const swatch=dlg.colorRoot.querySelector(".easy-font-color-btn .easy-font-color-swatch");
    const label=dlg.colorRoot.querySelector(".easy-font-color-btn .easy-font-color-label");
    if(swatch instanceof HTMLElement)swatch.style.background=item?.value||"#000000";
    if(label instanceof HTMLElement)label.textContent=item?.label||String(option?.textContent||"");
  }

  function renderColorList(){
    if(!dlg?.colorRoot)return;
    const list=dlg.colorRoot.querySelector(".easy-font-color-list");
    if(!(list instanceof HTMLElement))return;
    list.innerHTML="";
    COLOR_PALETTE.forEach(item=>{
      const row=document.createElement("div");
      const active=String(dlg.color.value||"").toLowerCase()===String(item.value||"").toLowerCase();
      row.className=`easy-font-color-item${active?" active":""}`;
      row.innerHTML=`<span class="easy-font-color-swatch" style="background:${item.value}"></span><span class="easy-font-color-label">${item.label}</span>`;
      row.addEventListener("click",()=>{
        dlg.color.value=item.value;
        dlg.color.dispatchEvent(new Event("change",{bubbles:true}));
        closeColorDropdowns();
      });
      list.appendChild(row);
    });
  }

  function renderFamilyOptions(list){
    if(!(dlg?.family instanceof HTMLSelectElement))return;
    dlg.family.innerHTML=(Array.isArray(list)?list:[]).map(name=>{
      const safe=String(name).replace(/"/g,"&quot;");
      return `<option value="${safe}" style="font-family:'${safe}'">${safe}</option>`;
    }).join("");
  }

  function filterFamilies(query){
    const base=Array.isArray(dlg?.allFamilies)?dlg.allFamilies:[];
    const q=String(query||"").trim().toLowerCase();
    if(!q)return base;
    return base.filter(name=>String(name).toLowerCase().includes(q));
  }

  async function refreshFamilies(){
    if(!(dlg?.family instanceof HTMLSelectElement))return;
    const current=String(dlg.state.family||dlg.family.value||"").trim();
    const families=await getSystemFonts();
    dlg.allFamilies=families.slice();
    renderFamilyOptions(families);
    const lowerCurrent=current.toLowerCase();
    const found=families.find(name=>String(name).toLowerCase()===lowerCurrent);
    dlg.state.family=found||families.find(name=>String(name).toLowerCase()==="ms sans serif")||families[0]||defaultValue().family;
    dlg.family.value=dlg.state.family;
    dlg.familyInput.value=dlg.state.family;
    dlg.sync&&dlg.sync();
  }

  function ensureUI(){
    if(dlg)return;
    ensureStyle();
    const backdrop=document.createElement("div");
    backdrop.id="easy-font-backdrop";
    backdrop.className="modal-backdrop hidden";
    backdrop.innerHTML=`<div class="modal easy-font-modal"><div class="modal-header"><div class="modal-title">Fonte</div></div><div class="easy-font-body modal-body"><div class="easy-font-top"><div class="easy-font-col"><label for="easy-font-family-input">Fonte:</label><input id="easy-font-family-input" type="text" readonly><select id="easy-font-family" size="8"></select></div><div class="easy-font-col"><label for="easy-font-style-input">Estilo da fonte:</label><input id="easy-font-style-input" type="text" readonly><select id="easy-font-style" size="8"></select></div><div class="easy-font-col"><label for="easy-font-size-input">Tamanho:</label><input id="easy-font-size-input" type="text" readonly><select id="easy-font-size" size="8"></select></div><div class="easy-font-actions"><button id="easy-font-ok-top" class="materiais-btn" type="button">OK</button><button id="easy-font-cancel-top" class="materiais-btn" type="button">Cancelar</button></div></div><div class="easy-font-bottom"><div class="easy-font-box"><h5>Efeitos</h5><label class="easy-font-effect"><input id="easy-font-strike" type="checkbox"><span>Riscado</span></label><label class="easy-font-effect"><input id="easy-font-underline" type="checkbox"><span>Sublinhado</span></label><div class="easy-font-color"><label for="easy-font-color">Cor:</label><span id="easy-font-color-swatch" class="easy-font-color-swatch"></span><select id="easy-font-color"></select></div></div><div><div class="easy-font-box"><h5>Exemplo</h5><div id="easy-font-preview" class="easy-font-preview">AaBbYyZz</div></div><div class="easy-font-script"><label for="easy-font-script">Script:</label><select id="easy-font-script"></select></div></div></div><div class="modal-actions"><button id="easy-font-ok" class="materiais-btn" type="button">Ok</button><button id="easy-font-cancel" class="materiais-btn" type="button">Cancelar</button></div></div></div>`;
    document.body.appendChild(backdrop);
    dlg={
      backdrop,
      modal:backdrop.querySelector(".easy-font-modal"),
      familyInput:backdrop.querySelector("#easy-font-family-input"),
      family:backdrop.querySelector("#easy-font-family"),
      styleInput:backdrop.querySelector("#easy-font-style-input"),
      style:backdrop.querySelector("#easy-font-style"),
      sizeInput:backdrop.querySelector("#easy-font-size-input"),
      size:backdrop.querySelector("#easy-font-size"),
      strike:backdrop.querySelector("#easy-font-strike"),
      underline:backdrop.querySelector("#easy-font-underline"),
      color:backdrop.querySelector("#easy-font-color"),
      preview:backdrop.querySelector("#easy-font-preview"),
      script:backdrop.querySelector("#easy-font-script"),
      ok:backdrop.querySelector("#easy-font-ok"),
      okTop:backdrop.querySelector("#easy-font-ok-top"),
      cancel:backdrop.querySelector("#easy-font-cancel"),
      cancelTop:backdrop.querySelector("#easy-font-cancel-top"),
      state:defaultValue(),
      sampleText:"AaBbYyZz",
      onSave:null,
      colorRoot:null,
      sync:null,
    };
    if(dlg.familyInput)dlg.familyInput.removeAttribute("readonly");
    if(dlg.sizeInput)dlg.sizeInput.removeAttribute("readonly");
    if(typeof window.ensureModalChrome==="function")window.ensureModalChrome(dlg.modal);

    dlg.style.innerHTML=STYLE_OPTIONS.map(item=>`<option value="${item.id}">${item.label}</option>`).join("");
    dlg.size.innerHTML=SIZE_OPTIONS.map(item=>`<option value="${item}">${item}</option>`).join("");
    dlg.script.innerHTML=SCRIPT_OPTIONS.map(item=>`<option value="${item.id}">${item.label}</option>`).join("");
    ensurePalette(dlg.color);

    const colorWrap=dlg.color.parentElement;
    if(colorWrap instanceof HTMLElement){
      const dropdown=document.createElement("div");
      dropdown.className="easy-font-color-dropdown";
      dropdown.innerHTML='<button type="button" class="easy-font-color-btn"><span class="easy-font-color-swatch"></span><span class="easy-font-color-label"></span><span>▼</span></button><div class="easy-font-color-list easy-font-color-hidden"></div>';
      colorWrap.appendChild(dropdown);
      dlg.colorRoot=dropdown;
      const btn=dropdown.querySelector(".easy-font-color-btn");
      const list=dropdown.querySelector(".easy-font-color-list");
      if(btn instanceof HTMLButtonElement&&list instanceof HTMLElement){
        btn.addEventListener("click",()=>{
          const willOpen=list.classList.contains("easy-font-color-hidden");
          closeColorDropdowns(willOpen?list:null);
          list.classList.toggle("easy-font-color-hidden",!willOpen);
        });
      }
      dlg.color.classList.add("easy-font-native-hidden");
    }

    const sync=()=>{
      const style=currentStyle(dlg.state.styleId);
      dlg.family.value=String(dlg.state.family||"");
      dlg.style.value=style.id;
      dlg.size.value=String(dlg.state.size||"");
      if(document.activeElement!==dlg.familyInput)dlg.familyInput.value=String(dlg.state.family||"");
      dlg.styleInput.value=style.label;
      if(document.activeElement!==dlg.sizeInput)dlg.sizeInput.value=String(dlg.state.size||"");
      dlg.preview.textContent=dlg.sampleText||"AaBbYyZz";
      dlg.preview.style.fontFamily=String(dlg.state.family||defaultValue().family);
      dlg.preview.style.fontSize=`${Number(dlg.state.size||defaultValue().size)}px`;
      dlg.preview.style.fontWeight=style.weight;
      dlg.preview.style.fontStyle=style.italic?"italic":"normal";
      dlg.preview.style.color=String(dlg.state.color||"#000000");
      dlg.preview.style.textDecoration=`${dlg.state.underline?"underline ":""}${dlg.state.strike?"line-through":""}`.trim()||"none";
      dlg.strike.checked=!!dlg.state.strike;
      dlg.underline.checked=!!dlg.state.underline;
      dlg.color.value=String(dlg.state.color||"#000000").toLowerCase();
      dlg.script.value=String(dlg.state.script||"Ocidental");
      syncColorHeader();
      renderColorList();
    };
    dlg.sync=sync;

    dlg.family.addEventListener("change",()=>{dlg.state.family=String(dlg.family.value||defaultValue().family);sync()});
    dlg.style.addEventListener("change",()=>{dlg.state.styleId=normalizeStyleId(dlg.style.value);sync()});
    dlg.size.addEventListener("change",()=>{dlg.state.size=Number(dlg.size.value||defaultValue().size)||defaultValue().size;sync()});
    const normalizeSize=(value)=>{
      const num=Number(String(value||"").replace(",","."));
      if(!Number.isFinite(num))return null;
      let n=Math.round(num/2)*2;
      n=Math.max(8,Math.min(72,n));
      return n;
    };
    dlg.familyInput.addEventListener("input",()=>{
      const raw=String(dlg.familyInput.value||"");
      const lista=filterFamilies(raw);
      renderFamilyOptions(lista);
      const filtro=raw.trim().toLowerCase();
      const match=lista.find(name=>String(name).toLowerCase().startsWith(filtro))||lista[0];
      if(match){dlg.state.family=match;dlg.family.value=match;}
      sync();
    });
    const applySizeInput=()=>{
      const normal=normalizeSize(dlg.sizeInput.value);
      if(normal==null)return;
      dlg.state.size=normal;
      dlg.size.value=String(normal);
      sync();
    };
    dlg.sizeInput.addEventListener("change",applySizeInput);
    dlg.sizeInput.addEventListener("keydown",ev=>{if(ev.key==="Enter"){ev.preventDefault();applySizeInput()}});
    dlg.color.addEventListener("change",()=>{dlg.state.color=String(dlg.color.value||"#000000").toLowerCase();sync()});
    dlg.strike.addEventListener("change",()=>{dlg.state.strike=!!dlg.strike.checked;sync()});
    dlg.underline.addEventListener("change",()=>{dlg.state.underline=!!dlg.underline.checked;sync()});
    dlg.script.addEventListener("change",()=>{dlg.state.script=String(dlg.script.value||"Ocidental");sync()});

    function fechar(){dlg.backdrop.classList.add("hidden");closeColorDropdowns()}
    function confirmar(){
      const result={
        family:String(dlg.state.family||defaultValue().family),
        styleId:normalizeStyleId(dlg.state.styleId),
        size:Number(dlg.state.size||defaultValue().size)||defaultValue().size,
        color:String(dlg.state.color||"#000000").toLowerCase(),
        strike:!!dlg.state.strike,
        underline:!!dlg.state.underline,
        script:String(dlg.state.script||"Ocidental"),
      };
      const onSave=dlg.onSave;
      fechar();
      if(typeof onSave==="function")onSave(result);
    }

    dlg.cancel.addEventListener("click",fechar);
    dlg.cancelTop.addEventListener("click",fechar);
    dlg.ok.addEventListener("click",confirmar);
    dlg.okTop.addEventListener("click",confirmar);
    backdrop.addEventListener("click",ev=>{if(ev.target===backdrop)fechar()});
    document.addEventListener("click",ev=>{
      const target=ev.target;
      if(!(target instanceof Element))return;
      if(!target.closest("#easy-font-backdrop .easy-font-color-dropdown"))closeColorDropdowns();
    });

    sync();
    refreshFamilies();
  }

  function openDialog(opts={}){
    ensureUI();
    const initial=opts&&typeof opts.initialValue==="object"&&opts.initialValue?opts.initialValue:{};
    dlg.onSave=typeof opts.onSave==="function"?opts.onSave:null;
    dlg.sampleText=String(opts.previewText||"AaBbYyZz");
    dlg.state={
      family:String(initial.family||defaultValue().family),
      styleId:normalizeStyleId(initial.styleId),
      size:Number(initial.size||defaultValue().size)||defaultValue().size,
      color:String(initial.color||defaultValue().color).toLowerCase(),
      strike:!!initial.strike,
      underline:!!initial.underline,
      script:String(initial.script||defaultValue().script),
    };
    dlg.sync&&dlg.sync();
    dlg.backdrop.classList.remove("hidden");
    refreshFamilies();
  }

  window.easyFontNormalizeStyleId=normalizeStyleId;
  window.easyFontPadrao=defaultValue;
  window.easyFontAbrir=openDialog;
})();
