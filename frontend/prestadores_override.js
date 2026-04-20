function prestSelecionado(){return prestadoresCache.find(item=>Number(item.id||0)===Number(prestadorSelId))||null}
function prestStatusHtml(ativo){const color=ativo?'#2fbf2f':'#d14b4b';return `<span style="color:${color};font-size:14px;line-height:1;">&#9679;</span>`}
function prestFmtCodigo(valor,idx=0){const n=Number(valor||0);if(Number.isFinite(n)&&n>0)return String(n).padStart(3,"0");return String(idx+1).padStart(3,"0")}
function prestHojeBr(){return new Date().toLocaleDateString("pt-BR")}
function prestCpfSomenteDigitos(valor){return String(valor||"").replace(/\D+/g,"")}
function prestCpfValido(valor){const cpf=prestCpfSomenteDigitos(valor);if(cpf.length!==11)return false;if(/^(\d)\1{10}$/.test(cpf))return false;let soma=0;for(let i=0;i<9;i++)soma+=Number(cpf[i])*(10-i);let resto=(soma*10)%11;if(resto===10)resto=0;if(resto!==Number(cpf[9]))return false;soma=0;for(let i=0;i<10;i++)soma+=Number(cpf[i])*(11-i);resto=(soma*10)%11;if(resto===10)resto=0;return resto===Number(cpf[10])}
function prestCpfFormatado(valor){const cpf=prestCpfSomenteDigitos(valor);if(cpf.length!==11)return cpf;return `${cpf.slice(0,3)}.${cpf.slice(3,6)}.${cpf.slice(6,9)}-${cpf.slice(9)}`}
function prestNormalizarCpfCampo(input){if(!(input instanceof HTMLInputElement))return;const bruto=prestCpfSomenteDigitos(input.value);if(!bruto){input.value="";return}input.value=prestCpfValido(bruto)?prestCpfFormatado(bruto):bruto}
function prestDataBrFromAny(valor){
const txt=String(valor??"").trim();
if(!txt)return"";
const toBr=(d,m,a)=>{const dia=Number(d),mes=Number(m),ano=Number(a);if(!(dia>=1&&dia<=31&&mes>=1&&mes<=12&&ano>=1900&&ano<=2100))return"";const dt=new Date(ano,mes-1,dia);if(dt.getFullYear()!==ano||dt.getMonth()!==mes-1||dt.getDate()!==dia)return"";return`${String(dia).padStart(2,"0")}/${String(mes).padStart(2,"0")}/${String(ano).padStart(4,"0")}`};
let m=txt.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
if(m)return toBr(m[1],m[2],m[3]);
m=txt.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T\s].*)?$/);
if(m)return toBr(m[3],m[2],m[1]);
const digits=txt.replace(/\D+/g,"");
if(digits.length===8){
if(/^(19|20)\d{6}$/.test(digits))return toBr(digits.slice(6,8),digits.slice(4,6),digits.slice(0,4));
return toBr(digits.slice(0,2),digits.slice(2,4),digits.slice(4,8));
}
return"";
}
function prestEspecialidadesTexto(item){const lista=Array.isArray(item?.especialidades_exec)?item.especialidades_exec.filter(Boolean):[];if(lista.length)return lista.join(", ");return String(item?.especialidade||"").trim()}
function prestTelefonePrincipal(item,chave){return String(item?.[chave]||"").trim()}
const PREST_UFS_BR=["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"];
const PREST_AGENDA_VISUALIZACAO_PADRAO=["Número do paciente","Nome do paciente","Fone 1","Fone 2","Sala"];
function prestFiltrarLista(){const esp=String(prestCfg?.cboEspecialidade?.value||"").trim();const nome=(prestCfg?.txtNome?.value||"").trim().toLowerCase();return prestadoresCache.filter(item=>{const especialidades=prestEspecialidadesTexto(item);const okEsp=!esp||esp==="__todas__"||especialidades.split(",").map(v=>v.trim()).includes(esp);const alvo=`${String(item.nome||"")} ${String(item.apelido||"")} ${prestTelefonePrincipal(item,"fone1")} ${prestTelefonePrincipal(item,"fone2")}`.toLowerCase();return okEsp&&(!nome||alvo.includes(nome))})}
function prestRender(){if(!prestCfg)return;const lista=prestFiltrarLista();prestCfg.tbody.innerHTML=lista.map((item,idx)=>`<tr data-id="${item.id}" class="${Number(item.id||0)===Number(prestadorSelId)?"selected":""}"><td>${esc(prestFmtCodigo(item.codigo,idx))}</td><td>${esc(item.nome||"")}</td><td>${esc(prestTelefonePrincipal(item,"fone1"))}</td><td>${esc(prestTelefonePrincipal(item,"fone2"))}</td><td>${prestStatusHtml(item.ativo!==false)}</td></tr>`).join("")||'<tr><td colspan="5">Nenhum prestador encontrado.</td></tr>';prestCfg.total.textContent=`${lista.length} prestadores`}
function prestSelecionarLinha(tr){prestadorSelId=Number(tr?.dataset.id||0)||null;prestRender()}
function prestNovoCodigo(){const max=prestadoresCache.reduce((acc,item)=>Math.max(acc,Number(item.codigo||0)||0),0);return String(max+1).padStart(3,"0")}
let prestTiposPrestadorCache=[];
let prestEspecialidadesAtivasCache=[];
let prestAuxCombosCache={};
function prestTiposPrestadorPadrao(){return[{codigo:"01",descricao:"Cirurgião dentista"},{codigo:"02",descricao:"Clínica odontológica"},{codigo:"03",descricao:"Clínica ortodôntica"},{codigo:"04",descricao:"Clínica radiológica"},{codigo:"05",descricao:"Perito"}]}
function prestSexosPadrao(){return["Masculino","Feminino"]}
function prestCbosPadrao(){return["Cir.Dentista em Geral","Cir.Dentista (saúde pública)","Cir.Dentista (traumatologia buco maxilo facial)","Cir.Dentista (endodontia)","Cir.Dentista (ortodontia)","Cir.Dentista (patologia bucal)","Cir.Dentista (pediatria)","Cir.Dentista (prótese)","Cir.Dentista (radiologia)","Cir.Dentista (periodontia)"]}
function prestUfCroPadrao(){return PREST_UFS_BR.slice()}
function prestNovoItemBase(){return{id:Date.now(),codigo:prestNovoCodigo(),nome:"",apelido:"",tipo_prestador:"Cirurgião dentista",inicio:prestHojeBr(),termino:"",ativo:true,executa_procedimento:true,cro:"",uf_cro:"",cpf:"",rg:"",inss:"",ccm:"",contrato:"",cnes:"",cbos:"Cir.Dentista em Geral",nascimento:"",sexo:"",estado_civil:"",prefixo:"",inclusao:prestHojeBr(),alteracao:prestHojeBr(),id_interno:String(Date.now()).slice(-6),fone1:"",fone1_tipo:"Residencial",fone2:"",fone2_tipo:"Comercial",email:"",homepage:"",logradouro_tipo:"",endereco:"",numero:"",complemento:"",bairro:"",cidade:"São José do Rio Preto",cep:"",uf:"SP",banco:"",agencia:"",conta:"",nome_conta:"",modo_pagamento:"",faculdade:"",formatura:"",alerta_agendamentos:"",especialidades_exec:[],observacoes:"",especialidade:""}}
async function prestCarregarTiposPrestador(){try{const{res,data}=await requestJson("GET","/cadastros/prestadores/tipos",undefined,true);if(res.ok&&Array.isArray(data)&&data.length){prestTiposPrestadorCache=data.map(item=>({codigo:String(item?.codigo||""),descricao:String(item?.descricao||"").trim()})).filter(item=>item.descricao);return prestTiposPrestadorCache}}catch{}prestTiposPrestadorCache=prestTiposPrestadorPadrao();return prestTiposPrestadorCache}
function prestEspecialidadesPadrao(){return["Cirurgia","Dentística","Diagnóstico","Endodontia","Estética","Gerais","Harmonização Facial","Implantodontia","Odontopediatria","Ortodontia","Periodontia","Prevenção","Prótese","Radiologia"]}
async function prestCarregarEspecialidadesAtivas(){try{const{res,data}=await requestJson("GET","/cadastros/auxiliares/especialidades-ativas",undefined,true);if(res.ok&&Array.isArray(data)&&data.length){prestEspecialidadesAtivasCache=data.map(item=>String(item?.nome||item?.descricao||"").trim()).filter(Boolean);return prestEspecialidadesAtivasCache}}catch{}prestEspecialidadesAtivasCache=prestEspecialidadesPadrao();return prestEspecialidadesAtivasCache}
function prestAuxPadrao(tipo){switch(String(tipo||"").trim()){case"Tipos de contato":return["Comercial 1","Comercial 2","Comercial 3","Residencial","Fax","Celular","Recado"];case"Bancos":return["Banco do Brasil","Caixa Econômica Federal","Bradesco","Itaú","Santander"];case"Estado civil":return["Solteiro(a)","Casado(a)","Divorciado(a)","Viúvo(a)"];case"Prefixo pessoais":return["Dr.","Dra.","Sr.","Sra."];case"Tipos de pagamento":return["Depósito","PIX","Transferência","Cheque"];case"Cidade":return["São José do Rio Preto","Mirassol","Cedral","Bálsamo"];case"Tipos de logradouro":return["Rua","Avenida","Alameda","Travessa"];default:return[]}}
async function prestCarregarAuxTipoLista(tipo){const chave=String(tipo||"").trim();if(!chave)return[];if(Array.isArray(prestAuxCombosCache[chave])&&prestAuxCombosCache[chave].length)return prestAuxCombosCache[chave];try{if(typeof materiaisCarregarAuxTipo==="function"){const itens=await materiaisCarregarAuxTipo(chave);if(Array.isArray(itens)&&itens.length){prestAuxCombosCache[chave]=itens.map(v=>String(v||"").trim()).filter(Boolean);return prestAuxCombosCache[chave]}}}catch{}prestAuxCombosCache[chave]=prestAuxPadrao(chave);return prestAuxCombosCache[chave]}
function prestPreencherComboLista(select,itens,valorAtual="",blank=true){if(!(select instanceof HTMLSelectElement))return;const atual=String(valorAtual||"").trim();const lista=[...(blank?[""]:[]),...(Array.isArray(itens)?itens:[]).map(v=>String(v||"").trim()).filter(Boolean)];if(atual&&!lista.includes(atual))lista.push(atual);const unicos=[...new Set(lista)];select.innerHTML=unicos.map(item=>`<option value="${esc(item)}">${esc(item)}</option>`).join("");select.value=atual&&unicos.includes(atual)?atual:(blank?"":String(unicos[0]||""))}
function prestNormalizarContatoModal(){
const modal=document.querySelector("#prest-modal-backdrop .prest-modal");
if(!modal)return;
const contatoPane=modal.querySelector('[data-tab="contato"]');
if(!contatoPane)return;
contatoPane.querySelectorAll("label").forEach(lbl=>{
const txt=String(lbl.textContent||"").trim();
if(/Endere.o residencial:/i.test(txt))lbl.textContent="Endereço residencial:";
if(/^N.{0,2}:$/.test(txt))lbl.textContent="Nº:";
});
const bairroAtual=modal.querySelector("#prest-modal-bairro");
if(bairroAtual&&bairroAtual.tagName==="INPUT"){
const select=document.createElement("select");
select.id="prest-modal-bairro";
select.innerHTML='<option value=""></option>';
select.value=String(bairroAtual.value||"");
bairroAtual.replaceWith(select)
}
const cidade=modal.querySelector("#prest-modal-cidade");
if(cidade instanceof HTMLSelectElement){
const canonicalCidade=['<option value=""></option>','<option>São José do Rio Preto</option>','<option>Mirassol</option>','<option>Cedral</option>','<option>Bálsamo</option>'].join("");
const temQuebra=[...cidade.options].some(opt=>/[?ï¿½]/.test(String(opt.textContent||"")));
if(temQuebra)cidade.innerHTML=canonicalCidade;
}
const uf=modal.querySelector("#prest-modal-uf");
if(uf instanceof HTMLSelectElement&&uf.options.length<10){
uf.innerHTML='<option value=""></option><option>SP</option>'
}
}
async function prestCarregarCombosAuxiliares(base){if(!prestCfg?.modal)return;const m=prestCfg.modal;const tiposTelefonePrestador=["Residencial","Comercial","Celular","Recado"];const [bancos,estados,prefixos,pagamentos,cidades,bairros,logradouros]=await Promise.all([prestCarregarAuxTipoLista("Bancos"),prestCarregarAuxTipoLista("Estado civil"),prestCarregarAuxTipoLista("Prefixo pessoais"),prestCarregarAuxTipoLista("Tipos de pagamento"),prestCarregarAuxTipoLista("Cidade"),prestCarregarAuxTipoLista("Bairro"),prestCarregarAuxTipoLista("Tipos de logradouro")]);prestPreencherComboLista(m.foneTipo1,tiposTelefonePrestador,base.fone1_tipo||"Residencial",false);prestPreencherComboLista(m.foneTipo2,tiposTelefonePrestador,base.fone2_tipo||"Comercial",false);prestPreencherComboLista(m.estadoCivil,estados,base.estado_civil||"",true);prestPreencherComboLista(m.prefixo,prefixos,base.prefixo||"",true);prestPreencherComboLista(m.banco,bancos,base.banco||"",true);prestPreencherComboLista(m.modoPagamento,pagamentos,base.modo_pagamento||"",true);prestPreencherComboLista(m.cidade,cidades,base.cidade||"São José do Rio Preto",true);prestPreencherComboLista(m.bairro,bairros,base.bairro||"",true);prestPreencherComboLista(m.logradouroTipo,logradouros,base.logradouro_tipo||"",true);prestPreencherComboLista(m.uf,PREST_UFS_BR,base.uf||"SP",true)}
function prestNormalizarContatoModalV2(){const modal=document.querySelector("#prest-modal-backdrop .prest-modal");if(!modal)return;const contatoPane=modal.querySelector('[data-tab="contato"]');if(!contatoPane)return;const logradouro=modal.querySelector("#prest-modal-logradouro-tipo");if(logradouro){const wrap=logradouro.closest("div");const lbl=wrap?wrap.querySelector("label"):null;if(lbl)lbl.textContent="Endere\u00E7o residencial:"}const numero=modal.querySelector("#prest-modal-numero");if(numero){const wrap=numero.closest("div");const lbl=wrap?wrap.querySelector("label"):null;if(lbl)lbl.textContent="N\u00BA:"}const cidade=modal.querySelector("#prest-modal-cidade");if(cidade instanceof HTMLSelectElement){const hasBroken=[...cidade.options].some(opt=>/[ï¿½?]/.test(String(opt.textContent||"")));if(hasBroken)cidade.innerHTML='<option value=""></option><option>S\u00E3o Jos\u00E9 do Rio Preto</option><option>Mirassol</option><option>Cedral</option><option>B\u00E1lsamo</option>';}}
function prestNormalizarPrincipalModalV2(){
const setLabel=(id,texto)=>{
const el=document.getElementById(id);
const lbl=el?.closest("div")?.querySelector("label");
if(lbl)lbl.textContent=texto;
};
setLabel("prest-modal-inicio","In\u00EDcio:");
setLabel("prest-modal-termino","T\u00E9rmino:");
setLabel("prest-modal-inss","N\u00BA INSS:");
setLabel("prest-modal-ccm","N\u00BA CCM:");
setLabel("prest-modal-contrato","N\u00BA contrato:");
setLabel("prest-modal-cnes","N\u00BA CNES:");
setLabel("prest-modal-inclusao","Inclus\u00E3o:");
setLabel("prest-modal-alteracao","Altera\u00E7\u00E3o:");
}
async function prestCarregarCombosPrincipal(base){if(!prestCfg?.modal)return;const m=prestCfg.modal;const [sexosAux,cbosAux]=await Promise.all([prestCarregarAuxTipoLista("Sexo"),prestCarregarAuxTipoLista("CBO-S")]);const sexos=Array.isArray(sexosAux)&&sexosAux.length?sexosAux:prestSexosPadrao();const cbos=Array.isArray(cbosAux)&&cbosAux.length?cbosAux:prestCbosPadrao();prestPreencherComboLista(m.ufCro,prestUfCroPadrao(),base.uf_cro||"",true);prestPreencherComboLista(m.cbos,cbos,base.cbos||"Cir.Dentista em Geral",true);prestPreencherComboLista(m.sexo,sexos,base.sexo||"",true)}
function prestPreencherComboTiposPrestador(select,valorAtual){if(!(select instanceof HTMLSelectElement))return;const itens=(Array.isArray(prestTiposPrestadorCache)&&prestTiposPrestadorCache.length?prestTiposPrestadorCache:prestTiposPrestadorPadrao()).filter(item=>String(item?.descricao||"").trim());const atual=String(valorAtual||"").trim();const extras=atual&&!itens.some(item=>String(item.descricao||"").trim()===atual)?[{codigo:"",descricao:atual}]:[];select.innerHTML=[...itens,...extras].map(item=>`<option value="${esc(String(item.descricao||""))}">${esc(String(item.descricao||""))}</option>`).join("");select.value=atual||String((itens[0]&&itens[0].descricao)||"")}
function prestListaEspecialidadesComExtras(extras=[]){const ativos=(Array.isArray(prestEspecialidadesAtivasCache)&&prestEspecialidadesAtivasCache.length?prestEspecialidadesAtivasCache:prestEspecialidadesPadrao()).map(item=>String(item||"").trim()).filter(Boolean);const adicionais=[...extras,...prestadoresCache.flatMap(item=>prestEspecialidadesTexto(item).split(",").map(v=>v.trim()).filter(Boolean))];return [...new Set([...ativos,...adicionais].filter(Boolean))]}
function prestRenderEspecialidadesChecklist(selecionadas=[]){const wrap=document.querySelector("#prest-modal-backdrop .prest-checklist");if(!wrap)return;const lista=prestListaEspecialidadesComExtras(selecionadas);wrap.innerHTML=lista.map(item=>`<label><input type="checkbox" value="${esc(item)}">${esc(item)}</label>`).join("");if(prestCfg?.modal)prestCfg.modal.especialidades=[...wrap.querySelectorAll("input[type='checkbox']")];(prestCfg?.modal?.especialidades||[]).forEach(chk=>chk.checked=selecionadas.includes(chk.value))}
function prestAtualizarFiltroEspecialidades(){if(!prestCfg?.cboEspecialidade)return;const especialidades=prestListaEspecialidadesComExtras();prestCfg.cboEspecialidade.innerHTML=['<option value="__todas__">&lt;&lt;Todas&gt;&gt;</option>',...especialidades.map(item=>`<option value="${esc(item)}">${esc(item)}</option>`)].join("")}
async function prestCarregar(){await prestCarregarTiposPrestador();try{const{res,data}=await requestJson("GET","/cadastros/prestadores",undefined,true);if(!res.ok)throw new Error("prestadores");const itens=Array.isArray(data?.itens)?data.itens:[];prestadoresCache=itens.map(item=>({...prestNovoItemBase(),...item,especialidades_exec:Array.isArray(item?.especialidades_exec)?item.especialidades_exec:[],agenda_config:item?.agenda_config&&typeof item.agenda_config==="object"?item.agenda_config:{}}))}catch{const itens=[{...prestNovoItemBase(),id:-1,codigo:"001",nome:"Clínica",tipo_prestador:"Clínica odontológica",executa_procedimento:false,id_interno:"1"}];if(sessaoAtual)itens.push({...prestNovoItemBase(),id:Number(sessaoAtual.user_id||1)||1,codigo:"002",nome:String(sessaoAtual.nome||sessaoAtual.email||"Usuário"),ativo:true,email:String(sessaoAtual.email||""),id_interno:String(sessaoAtual.user_id||1||1)});prestadoresCache=itens}const seen=new Set();prestadoresCache=prestadoresCache.filter(item=>{const key=String(item.id);if(seen.has(key))return false;seen.add(key);return true});prestAtualizarFiltroEspecialidades();if(!prestadoresCache.some(item=>Number(item.id||0)===Number(prestadorSelId)))prestadorSelId=prestadoresCache[0]?.id||null;prestRender()}
function prestAcoesPlaceholder(rotulo){const item=prestSelecionado();const alvo=item?` '${item.nome}'`:"";footerMsg.textContent=`Prestadores > ${rotulo}${alvo}: próxima etapa da migração.`}
function prestApplyFineLayout(){if(document.getElementById("prest-fine-style"))return;const style=document.createElement("style");style.id="prest-fine-style";style.textContent=`
#prestadores-panel{width:min(680px,100%)}
#prestadores-panel .prest-toolbar{gap:5px;flex-wrap:nowrap}
#prestadores-panel .prest-toolbar .materiais-btn{min-width:0;padding:0 10px;height:29px;font:600 12px Tahoma,sans-serif}
#prestadores-panel .prest-toolbar .sep{margin:0 1px}
  #prest-modal-backdrop .prest-modal{width:min(492px,95vw)}
#prest-modal-backdrop .prest-modal-body{padding:6px 8px 8px}
#prest-modal-backdrop .prest-tabs{gap:2px;margin-bottom:6px}
#prest-modal-backdrop .prest-tab{height:22px;padding:0 9px;border:1px solid #bcc6d2;border-bottom:none;background:#efefef;font:12px Tahoma,sans-serif}
#prest-modal-backdrop .prest-tab.active{background:#fff;font-weight:400}
#prest-modal-backdrop .prest-pane{padding:6px;min-height:328px;overflow:hidden}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid{grid-template-columns:82px 50px 104px 1fr 88px 86px;gap:4px 6px}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(1){grid-column:1}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(2){grid-column:2 / 6}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(3){grid-column:6}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(4){grid-column:1 / 5}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(5){grid-column:5}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(6){grid-column:6}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(7){grid-column:1 / -1;padding-top:1px;border-bottom:1px solid #cfcfcf;padding-bottom:5px;margin-bottom:2px}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(8){grid-column:1}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(9){grid-column:2}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(10){grid-column:3 / 5}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(11){grid-column:5 / 7}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(12){grid-column:1 / 3}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(13){grid-column:3 / 5}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(14){grid-column:5 / 7}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(15){grid-column:1 / 3}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(16){grid-column:3 / 7}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(17){grid-column:1 / 3}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(18){grid-column:3 / 4}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(19){grid-column:4 / 6}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid > div:nth-child(20){grid-column:6 / 7}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid label{margin-bottom:1px}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid input,
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid select{min-width:0}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid input,
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-form-grid select{height:22px;padding:0 4px}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-checkline{gap:18px;white-space:nowrap;align-items:center}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-checkline label{gap:4px;white-space:nowrap}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-checkline input{transform:scale(.9);margin:0}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-info-grid{grid-template-columns:166px 166px 50px;column-gap:3px;row-gap:6px;margin-top:6px;justify-content:start}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-info-grid label{margin-bottom:1px;font:11px Tahoma,sans-serif}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-info-grid input{min-width:0}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-info-grid input{height:23px;padding:0 4px;background:#27e7ef!important;border:1px solid #7d8e97;color:#000;font:11px Tahoma,sans-serif}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-info-grid > div:nth-child(3) label{white-space:nowrap}
#prest-modal-backdrop .prest-pane[data-tab="principal"] .prest-info-grid > div:nth-child(3) input{height:20px}
#prest-modal-backdrop .prest-pane[data-tab="contato"]{padding:6px 8px;min-height:312px}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid{grid-template-columns:58px 86px 52px 52px 34px 64px 42px;gap:5px 5px;align-items:end}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid label{margin-bottom:1px;font:11px Tahoma,sans-serif;white-space:nowrap}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid input,
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid select{height:21px;padding:0 4px;font:11px Tahoma,sans-serif}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-phone-row{grid-template-columns:86px minmax(0,1fr) 86px minmax(0,1fr);gap:6px}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-phone-row > div{min-width:0}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-phone-row select,
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-phone-row input{width:100%}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid > div:nth-child(4){grid-column:1;grid-row:4}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid > div:nth-child(5){grid-column:2 / 5;grid-row:4}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid > div:nth-child(6){grid-column:5 / 6;grid-row:4}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid > div:nth-child(7){grid-column:6 / 8;grid-row:4}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid > div:nth-child(8){grid-column:1 / 3;grid-row:5}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid > div:nth-child(9){grid-column:3 / 6;grid-row:5}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid > div:nth-child(10){grid-column:6 / 7;grid-row:5}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid > div:nth-child(11){grid-column:7 / 8;grid-row:5}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .prest-contact-grid > div:nth-child(3){border-bottom:1px solid #d3d3d3;padding-bottom:6px;margin-bottom:2px}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .span-endereco{grid-column:2 / 5}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .span-bairro{grid-column:1 / 3}
#prest-modal-backdrop .prest-pane[data-tab="contato"] .span-cidade{grid-column:3 / 6}
#prest-modal-backdrop .prest-pane[data-tab="detalhes"]{padding:6px 8px;min-height:308px}
#prest-modal-backdrop .prest-pane[data-tab="detalhes"] .prest-detalhes-grid{grid-template-columns:minmax(0,1fr) 78px 150px;gap:5px 7px}
#prest-modal-backdrop .prest-pane[data-tab="detalhes"] .prest-detalhes-grid label{margin-bottom:1px;white-space:nowrap}
#prest-modal-backdrop .prest-pane[data-tab="detalhes"] .prest-detalhes-grid input,
#prest-modal-backdrop .prest-pane[data-tab="detalhes"] .prest-detalhes-grid select{height:21px;padding:0 4px}
#prest-modal-backdrop .prest-pane[data-tab="detalhes"] .prest-checklist{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:2px 24px;padding:3px 10px 4px 10px;min-height:102px;align-items:start}
#prest-modal-backdrop .prest-pane[data-tab="detalhes"] .prest-checklist label{display:grid;grid-template-columns:13px 1fr;align-items:center;gap:5px;font:11px Tahoma,sans-serif;line-height:1.05;justify-self:start}
#prest-modal-backdrop .prest-pane[data-tab="detalhes"] .prest-checklist input{transform:none;width:13px;height:13px;margin:0}
#prest-modal-backdrop .prest-modal-actions{gap:8px;padding-top:10px;justify-content:flex-end}
#prest-modal-backdrop .prest-modal-actions .materiais-btn{min-width:74px;height:28px;padding:0 10px;border-radius:4px;background:#f8f8f8;border:1px solid #c9c9c9;color:#222;font:400 11px Tahoma,sans-serif;box-shadow:none}
  #prest-modal-backdrop .prest-modal-actions .materiais-btn img{display:none}
  `;document.head.appendChild(style)}
function prestDadosTab(tab){if(!prestCfg?.modal)return;prestCfg.modal.tabs.forEach(btn=>btn.classList.toggle("active",btn.dataset.tab===tab));prestCfg.modal.panes.forEach(pane=>pane.classList.toggle("hidden",pane.dataset.tab!==tab));prestCfg.modal.tabAtual=tab;if(tab==="contato")prestNormalizarContatoModalV2()}
async function prestAbrirModal(modo){
const item=modo==="editar"?prestSelecionado():null;
if(modo==="editar"&&!item){window.alert("Selecione um prestador.");return}
prestEnsureUI();
prestApplyFineLayout();
prestNormalizarContatoModal();
prestNormalizarContatoModalV2();
if(prestCfg?.modal){
prestCfg.modal.bairro=document.getElementById("prest-modal-bairro");
prestCfg.modal.cidade=document.getElementById("prest-modal-cidade");
prestCfg.modal.uf=document.getElementById("prest-modal-uf")
}
const base=item?JSON.parse(JSON.stringify(item)):prestNovoItemBase();
const m=prestCfg.modal;
m.modo=modo;
m.editId=item?Number(item.id||0):null;
m.title.textContent=modo==="editar"?"Altera prestador":"Novo prestador";
m.codigo.value=String(base.codigo||"");
m.nome.value=String(base.nome||"");
m.apelido.value=String(base.apelido||"");
prestPreencherComboTiposPrestador(m.tipo,base.tipo_prestador||"Cirurgião dentista");
await prestCarregarCombosAuxiliares(base);
await prestCarregarCombosPrincipal(base);
m.inicio.value=prestDataBrFromAny(base.inicio)||prestHojeBr();
m.termino.value=prestDataBrFromAny(base.termino);
m.inativo.checked=base.ativo===false;
m.executa.checked=base.executa_procedimento!==false;
m.cro.value=String(base.cro||"");
m.ufCro.value=String(base.uf_cro||"");
m.cpf.value=String(base.cpf||"");
m.rg.value=String(base.rg||"");
m.inss.value=String(base.inss||"");
m.ccm.value=String(base.ccm||"");
m.contrato.value=String(base.contrato||"");
m.cnes.value=String(base.cnes||"");
m.cbos.value=String(base.cbos||"Cir.Dentista em Geral");
m.nascimento.value=prestDataBrFromAny(base.nascimento);
m.sexo.value=String(base.sexo||"");
m.inclusao.value=prestDataBrFromAny(base.inclusao)||prestHojeBr();
m.alteracao.value=prestDataBrFromAny(base.alteracao)||prestHojeBr();
m.idInterno.value=String(base.id_interno||"");
m.fone1.value=String(base.fone1||"");
m.fone2.value=String(base.fone2||"");
m.email.value=String(base.email||"");
m.homepage.value=String(base.homepage||"");
m.endereco.value=String(base.endereco||"");
m.numero.value=String(base.numero||"");
m.complemento.value=String(base.complemento||"");
m.bairro.value=String(base.bairro||"");
m.cep.value=String(base.cep||"");
m.uf.value=String(base.uf||"SP");
m.agencia.value=String(base.agencia||"");
m.conta.value=String(base.conta||"");
m.nomeConta.value=String(base.nome_conta||"");
m.faculdade.value=String(base.faculdade||"");
m.formatura.value=String(base.formatura||"");
m.alerta.value=String(base.alerta_agendamentos||"");
m.observacoes.value=String(base.observacoes||"");
prestRenderEspecialidadesChecklist(Array.isArray(base.especialidades_exec)?base.especialidades_exec:[]);
prestNormalizarPrincipalModalV2();
prestDadosTab("principal");
m.backdrop.classList.remove("hidden")
}
function prestFecharModal(){if(prestCfg?.modal?.backdrop)prestCfg.modal.backdrop.classList.add("hidden")}
async function prestSalvarModal(){
if(!prestCfg?.modal)return;
const m=prestCfg.modal;
const nome=String(m.nome.value||"").trim();
if(!nome){
window.alert("Informe o nome do prestador.");
m.nome.focus();
return;
}
prestNormalizarCpfCampo(m.cpf);
const inicioRaw=String(m.inicio.value||"").trim();
const terminoRaw=String(m.termino.value||"").trim();
const nascimentoRaw=String(m.nascimento.value||"").trim();
const inclusaoRaw=String(m.inclusao.value||"").trim();
const inicioNorm=prestDataBrFromAny(inicioRaw)||inicioRaw;
const terminoNorm=prestDataBrFromAny(terminoRaw)||terminoRaw;
const nascimentoNorm=prestDataBrFromAny(nascimentoRaw)||nascimentoRaw;
const inclusaoNorm=prestDataBrFromAny(inclusaoRaw)||inclusaoRaw||prestHojeBr();
const especialidadesExec=m.especialidades.filter(chk=>chk.checked).map(chk=>chk.value);
const payload={
codigo:String(m.codigo.value||prestNovoCodigo()).trim()||prestNovoCodigo(),
nome,
apelido:String(m.apelido.value||"").trim(),
tipo_prestador:String(m.tipo.value||""),
inicio:inicioNorm,
termino:terminoNorm,
ativo:!m.inativo.checked,
executa_procedimento:m.executa.checked,
cro:String(m.cro.value||"").trim(),
uf_cro:String(m.ufCro.value||"").trim(),
cpf:String(m.cpf.value||"").trim(),
rg:String(m.rg.value||"").trim(),
inss:String(m.inss.value||"").trim(),
ccm:String(m.ccm.value||"").trim(),
contrato:String(m.contrato.value||"").trim(),
cnes:String(m.cnes.value||"").trim(),
cbos:String(m.cbos.value||"").trim(),
nascimento:nascimentoNorm,
sexo:String(m.sexo.value||""),
estado_civil:String(m.estadoCivil.value||""),
prefixo:String(m.prefixo.value||""),
inclusao:inclusaoNorm,
alteracao:prestHojeBr(),
id_interno:String(m.idInterno.value||Date.now()).trim(),
fone1_tipo:String(m.foneTipo1.value||""),
fone1:String(m.fone1.value||"").trim(),
fone2_tipo:String(m.foneTipo2.value||""),
fone2:String(m.fone2.value||"").trim(),
email:String(m.email.value||"").trim(),
homepage:String(m.homepage.value||"").trim(),
logradouro_tipo:String(m.logradouroTipo.value||""),
endereco:String(m.endereco.value||"").trim(),
numero:String(m.numero.value||"").trim(),
complemento:String(m.complemento.value||"").trim(),
bairro:String(m.bairro.value||"").trim(),
cidade:String(m.cidade.value||"").trim(),
cep:String(m.cep.value||"").trim(),
uf:String(m.uf.value||"").trim(),
banco:String(m.banco.value||"").trim(),
agencia:String(m.agencia.value||"").trim(),
conta:String(m.conta.value||"").trim(),
nome_conta:String(m.nomeConta.value||"").trim(),
modo_pagamento:String(m.modoPagamento.value||""),
faculdade:String(m.faculdade.value||"").trim(),
formatura:String(m.formatura.value||"").trim(),
alerta_agendamentos:String(m.alerta.value||"").trim(),
especialidades_exec:especialidadesExec,
especialidade:especialidadesExec[0]||"",
agenda_config:(m.modo==="editar"?(prestSelecionado()?.agenda_config||{}):{}),
observacoes:String(m.observacoes.value||"").trim()
};
try{
const editId=Number(m.editId||0);
if(m.modo==="editar"&&editId<=0){
window.alert("A conta Clínica não pode ser alterada por aqui.");
return;
}
const endpoint=m.modo==="editar"?`/cadastros/prestadores/${editId}`:"/cadastros/prestadores";
const method=m.modo==="editar"?"PUT":"POST";
const{res,data}=await requestJson(method,endpoint,payload,true);
if(!res.ok)throw new Error(String(data?.detail||"Falha ao gravar prestador."));
const item={
...prestNovoItemBase(),
...(data||{}),
especialidades_exec:Array.isArray(data?.especialidades_exec)?data.especialidades_exec:[],
agenda_config:data?.agenda_config&&typeof data.agenda_config==="object"?data.agenda_config:{}
};
const idx=prestadoresCache.findIndex(x=>Number(x.id||0)===Number(item.id||0));
if(idx>=0)prestadoresCache[idx]=item;else prestadoresCache.push(item);
prestadorSelId=item.id;
prestAtualizarFiltroEspecialidades();
prestRender();
prestFecharModal();
footerMsg.textContent=`Prestadores > ${m.modo==="editar"?"Altera":"Novo prestador"} '${item.nome}' salvo.`;
}catch(err){
window.alert(err?.message||"Não foi possível salvar o prestador.");
}
}
async function prestExcluirSelecionado(){const item=prestSelecionado();if(!item){window.alert("Selecione um prestador.");return}if(Number(item.id||0)<=0){window.alert("A conta Clínica não pode ser eliminada.");return}if(!window.confirm(`Deseja eliminar o prestador ${item.nome}?`))return;try{const{res,data}=await requestJson("DELETE",`/cadastros/prestadores/${Number(item.id||0)}`,undefined,true);if(!res.ok)throw new Error(String(data?.detail||"Falha ao eliminar prestador."));prestadoresCache=prestadoresCache.filter(x=>Number(x.id||0)!==Number(item.id||0));prestadorSelId=prestadoresCache[0]?.id||null;prestAtualizarFiltroEspecialidades();prestRender();footerMsg.textContent=`Prestadores > Elimina '${item.nome}' concluído.`}catch(err){window.alert(err?.message||"Não foi possível eliminar o prestador.")}}
function prestEnsureUI(){if(prestCfg)return;const style=document.createElement("style");style.textContent=".prest-panel{width:min(650px,100%);min-height:0;height:fit-content;align-self:start;padding:8px 8px 6px;background:#fff;border:1px solid #cfd8e3;box-sizing:border-box;font:12px Tahoma,sans-serif}.prest-toolbar{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:4px 0 6px}.prest-toolbar .sep{width:1px;height:22px;background:#cfd8e3;margin:0 2px}.prest-filtros{display:grid;grid-template-columns:200px 1fr;gap:8px;align-items:end;margin-bottom:6px}.prest-filtros label{display:block;margin-bottom:2px}.prest-filtros input,.prest-filtros select{width:100%;height:22px;border:1px solid #bfc9d6;padding:0 5px;box-sizing:border-box;background:#fff}.prest-grid{border:1px solid #cfd8e3;min-height:330px;background:#fff}.prest-grid table{width:100%;border-collapse:collapse;table-layout:fixed}.prest-grid th,.prest-grid td{border-bottom:1px solid #edf1f6;padding:2px 5px;height:20px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.prest-grid th{background:#f2f6fb;font:700 12px Tahoma,sans-serif;text-align:left}.prest-grid th:nth-child(1),.prest-grid td:nth-child(1),.prest-grid th:nth-child(5),.prest-grid td:nth-child(5){text-align:center}.prest-grid tr.selected{background:#d9e8fb}.prest-total{margin-top:4px;color:#5b6b7e}.prest-modal{width:min(490px,96vw);background:#f5f5f3;border:1px solid #c8ced8;box-sizing:border-box;font:12px Tahoma,sans-serif}.prest-modal-body{padding:8px 10px 10px}.prest-tabs{display:flex;gap:4px;margin-bottom:8px}.prest-tab{height:25px;padding:0 10px;border:1px solid #bfc9d6;border-bottom:none;background:#ececec;font:12px Tahoma,sans-serif;cursor:pointer}.prest-tab.active{background:#fff;font-weight:700}.prest-pane{border:1px solid #bfc9d6;background:#fff;padding:8px;min-height:338px}.prest-pane.hidden{display:none}.prest-form-grid{display:grid;grid-template-columns:82px 1fr 92px;gap:6px 8px;align-items:end}.prest-form-grid .span-2{grid-column:span 2}.prest-form-grid .span-3{grid-column:1 / -1}.prest-info-grid{display:grid;grid-template-columns:1fr 1fr 72px;gap:8px;margin-top:8px}.prest-contact-grid{display:grid;grid-template-columns:64px 1fr 42px 64px 1fr;gap:6px 8px;align-items:end}.prest-detalhes-grid{display:grid;grid-template-columns:1fr 84px 118px;gap:6px 8px;align-items:end}.prest-detalhes-grid .span-3{grid-column:1 / -1}.prest-detalhes-grid .span-2{grid-column:span 2}.prest-form-grid label,.prest-contact-grid label,.prest-detalhes-grid label{display:block;margin-bottom:2px}.prest-form-grid input,.prest-form-grid select,.prest-contact-grid input,.prest-contact-grid select,.prest-detalhes-grid input,.prest-detalhes-grid select,.prest-observacoes textarea{width:100%;height:22px;border:1px solid #bfc9d6;padding:0 5px;box-sizing:border-box;background:#fff}.prest-checkline{display:flex;align-items:center;gap:14px;padding-top:2px}.prest-checkline label{display:flex;align-items:center;gap:5px;margin:0}.prest-checklist{display:grid;grid-template-columns:1fr 1fr;gap:1px 14px;border:1px solid #cfd8e3;background:#fff;padding:4px 6px;min-height:108px}.prest-checklist label{display:flex;align-items:center;gap:4px;margin:0;font:12px Tahoma,sans-serif}.prest-checklist input{transform:scale(.92)}.prest-observacoes{padding:6px}.prest-observacoes textarea{height:320px;padding:4px;resize:none}.prest-modal-actions{display:flex;justify-content:flex-end;gap:8px;padding:8px 0 0}.prest-modal-actions .materiais-btn{min-width:74px;justify-content:center}.prest-ro{background:#dffcff!important}.prest-phone-row{display:grid;grid-template-columns:86px 1fr;gap:8px}.prest-contact-grid .span-all,.prest-detalhes-grid .span-all{grid-column:1 / -1}.prest-contact-grid .span-endereco{grid-column:2 / 6}.prest-contact-grid .span-bairro{grid-column:1 / 3}.prest-contact-grid .span-cidade{grid-column:3 / 5}";document.head.appendChild(style);workspaceEmpty.insertAdjacentHTML("afterend",`<section id="prestadores-panel" class="prest-panel hidden"><div class="panel-title">Cadastro de prestadores</div><div class="prest-toolbar"><button id="prest-btn-novo" class="materiais-btn" type="button"><img src="/desktop-assets/novo.png" alt="">Novo prestador...</button><button id="prest-btn-editar" class="materiais-btn" type="button"><img src="/desktop-assets/editar.png" alt="">Altera...</button><button id="prest-btn-excluir" class="materiais-btn" type="button"><img src="/desktop-assets/eliminar.png" alt="">Elimina</button><span class="sep"></span><button id="prest-btn-agenda" class="materiais-btn" type="button"><img src="/desktop-assets/editar.png" alt="">Agenda...</button><button id="prest-btn-convenios" class="materiais-btn" type="button"><img src="/desktop-assets/imprimir.png" alt="">Convênios...</button><button id="prest-btn-comissoes" class="materiais-btn" type="button"><img src="/desktop-assets/imprimir.png" alt="">Comissões...</button><span class="sep"></span><button id="prest-btn-fechar" class="materiais-btn" type="button"><img src="/desktop-assets/cancela.png" alt="">Fecha</button></div><div class="prest-filtros"><div><label for="prest-cbo-especialidade">Especialidade:</label><select id="prest-cbo-especialidade"></select></div><div><label for="prest-txt-nome">Nome do prestador:</label><input id="prest-txt-nome" type="text"></div></div><div class="prest-grid"><table><colgroup><col style="width:72px"><col><col style="width:140px"><col style="width:140px"><col style="width:54px"></colgroup><thead><tr><th>Código</th><th>Nome</th><th>Fone 1</th><th>Fone 2</th><th>Status</th></tr></thead><tbody id="prest-tbody"></tbody></table></div><div id="prest-total" class="prest-total">0 prestadores</div></section><div id="prest-modal-backdrop" class="modal-backdrop hidden"><div class="modal prest-modal"><div class="modal-header"><div id="prest-modal-title" class="modal-title">Novo prestador</div></div><div class="prest-modal-body"><div class="prest-tabs"><button data-tab="principal" class="prest-tab active" type="button">Principal</button><button data-tab="contato" class="prest-tab" type="button">Contato</button><button data-tab="detalhes" class="prest-tab" type="button">Detalhes</button><button data-tab="observacoes" class="prest-tab" type="button">Observações</button></div><section data-tab="principal" class="prest-pane"><div class="prest-form-grid"><div><label>Código:</label><input id="prest-modal-codigo" type="text"></div><div><label>Nome do prestador:</label><input id="prest-modal-nome" type="text"></div><div><label>Apelido:</label><input id="prest-modal-apelido" type="text"></div><div class="span-2"><label>Tipo do prestador:</label><select id="prest-modal-tipo"><option>Cirurgião dentista</option><option>Clínica</option><option>Protético</option><option>Outros</option></select></div><div><label>Início:</label><input id="prest-modal-inicio" type="text"></div><div><label>Término:</label><input id="prest-modal-termino" type="text"></div><div class="span-3 prest-checkline"><label><input id="prest-modal-inativo" type="checkbox">Inativar prestador</label><label><input id="prest-modal-executa" type="checkbox">Prestador executa procedimento</label></div><div><label>CRO:</label><input id="prest-modal-cro" type="text"></div><div><label>UF CRO:</label><select id="prest-modal-uf-cro"><option value=""></option><option>SP</option><option>RJ</option><option>MG</option><option>PR</option><option>SC</option><option>RS</option></select></div><div><label>CPF:</label><input id="prest-modal-cpf" type="text"></div><div><label>RG:</label><input id="prest-modal-rg" type="text"></div><div><label>Nº INSS:</label><input id="prest-modal-inss" type="text"></div><div><label>Nº CCM:</label><input id="prest-modal-ccm" type="text"></div><div><label>Nº contrato:</label><input id="prest-modal-contrato" type="text"></div><div><label>Nº CNES:</label><input id="prest-modal-cnes" type="text"></div><div class="span-2"><label>CBO-S:</label><select id="prest-modal-cbos"><option>Cir.Dentista em Geral</option><option>Clínico geral</option><option>Protético</option><option>Prestador administrativo</option></select></div><div><label>Nascimento:</label><input id="prest-modal-nascimento" type="text"></div><div><label>Sexo:</label><select id="prest-modal-sexo"><option value=""></option><option>Masculino</option><option>Feminino</option><option>Não informado</option></select></div><div><label>Estado civil:</label><select id="prest-modal-estado-civil"><option value=""></option><option>Solteiro(a)</option><option>Casado(a)</option><option>Divorciado(a)</option><option>Viúvo(a)</option></select></div><div><label>Prefixo:</label><select id="prest-modal-prefixo"><option value=""></option><option>Dr.</option><option>Dra.</option><option>Sr.</option><option>Sra.</option></select></div></div><div class="prest-info-grid"><div><label>Inclusão:</label><input id="prest-modal-inclusao" class="prest-ro" type="text" readonly></div><div><label>Alteração:</label><input id="prest-modal-alteracao" class="prest-ro" type="text" readonly></div><div><label>ID interno:</label><input id="prest-modal-id-interno" class="prest-ro" type="text" readonly></div></div></section><section data-tab="contato" class="prest-pane hidden"><div class="prest-contact-grid"><div class="prest-phone-row span-all"><div><label>Telefones:</label><select id="prest-modal-fone-tipo-1"><option>Comercial 1</option><option>Residencial</option><option>Comercial 2</option><option>Fax</option><option>Celular</option></select></div><div><label>&nbsp;</label><input id="prest-modal-fone-1" type="text"></div><div><label>&nbsp;</label><select id="prest-modal-fone-tipo-2"><option>Comercial 2</option><option>Residencial</option><option>Comercial 1</option><option>Fax</option><option>Celular</option></select></div><div><label>&nbsp;</label><input id="prest-modal-fone-2" type="text"></div></div><div class="span-all"><label>E-mail principal:</label><input id="prest-modal-email" type="text"></div><div class="span-all"><label>Home-page:</label><input id="prest-modal-homepage" type="text"></div><div><label>Endereço residencial:</label><select id="prest-modal-logradouro-tipo"><option value=""></option><option>Rua</option><option>Avenida</option><option>Alameda</option><option>Travessa</option></select></div><div class="span-endereco"><label>&nbsp;</label><input id="prest-modal-endereco" type="text"></div><div><label>Nº:</label><input id="prest-modal-numero" type="text"></div><div class="span-all"><label>Complemento:</label><input id="prest-modal-complemento" type="text"></div><div class="span-bairro"><label>Bairro:</label><input id="prest-modal-bairro" type="text"></div><div class="span-cidade"><label>Cidade:</label><select id="prest-modal-cidade"><option>São José do Rio Preto</option><option>Mirassol</option><option>Cedral</option><option>Bálsamo</option></select></div><div><label>CEP:</label><input id="prest-modal-cep" type="text"></div><div><label>UF:</label><select id="prest-modal-uf"><option>SP</option><option>RJ</option><option>MG</option><option>PR</option><option>SC</option><option>RS</option></select></div></div></section><section data-tab="detalhes" class="prest-pane hidden"><div class="prest-detalhes-grid"><div><label>Banco:</label><select id="prest-modal-banco"><option value=""></option><option>Banco do Brasil</option><option>Caixa Econômica Federal</option><option>Bradesco</option><option>Itaú</option><option>Santander</option></select></div><div><label>Agência:</label><input id="prest-modal-agencia" type="text"></div><div><label>Nº Conta:</label><input id="prest-modal-conta" type="text"></div><div class="span-2"><label>Nome da conta:</label><input id="prest-modal-nome-conta" type="text"></div><div><label>Modo de pagamento:</label><select id="prest-modal-modo-pagamento"><option value=""></option><option>Depósito</option><option>PIX</option><option>Transferência</option><option>Cheque</option></select></div><div class="span-2"><label>Faculdade:</label><input id="prest-modal-faculdade" type="text"></div><div><label>Formatura:</label><input id="prest-modal-formatura" type="text"></div><div class="span-3"><label>Alerta para agendamentos:</label><input id="prest-modal-alerta" type="text"></div><div class="span-3"><label>Especialidades que executa:</label><div class="prest-checklist" style="padding-top:2px"><label><input type="checkbox" value="Cirurgia">Cirurgia</label><label><input type="checkbox" value="Odontopediatria">Odontopediatria</label><label><input type="checkbox" value="Dentística">Dentística</label><label><input type="checkbox" value="Ortodontia">Ortodontia</label><label><input type="checkbox" value="Diagnóstico">Diagnóstico</label><label><input type="checkbox" value="Periodontia">Periodontia</label><label><input type="checkbox" value="Endodontia">Endodontia</label><label><input type="checkbox" value="Prevenção">Prevenção</label><label><input type="checkbox" value="Estética">Estética</label><label><input type="checkbox" value="Prótese">Prótese</label><label><input type="checkbox" value="Gerais">Gerais</label><label><input type="checkbox" value="Radiologia">Radiologia</label><label><input type="checkbox" value="Harmonização Facial">Harmonização Facial</label><label><input type="checkbox" value="Implantodontia">Implantodontia</label></div></div></div></section><section data-tab="observacoes" class="prest-pane prest-observacoes hidden"><textarea id="prest-modal-observacoes"></textarea></section><div class="prest-modal-actions"><button id="prest-modal-ok" class="materiais-btn" type="button"><img src="/desktop-assets/gravar.png" alt="">Ok</button><button id="prest-modal-cancelar" class="materiais-btn" type="button"><img src="/desktop-assets/cancela.png" alt="">Cancela</button></div></div></div></div>`);prestCfg={panel:document.getElementById("prestadores-panel"),cboEspecialidade:document.getElementById("prest-cbo-especialidade"),txtNome:document.getElementById("prest-txt-nome"),tbody:document.getElementById("prest-tbody"),total:document.getElementById("prest-total"),btnNovo:document.getElementById("prest-btn-novo"),btnEditar:document.getElementById("prest-btn-editar"),btnExcluir:document.getElementById("prest-btn-excluir"),btnAgenda:document.getElementById("prest-btn-agenda"),btnConvenios:document.getElementById("prest-btn-convenios"),btnComissoes:document.getElementById("prest-btn-comissoes"),btnFechar:document.getElementById("prest-btn-fechar"),modal:{backdrop:document.getElementById("prest-modal-backdrop"),modal:document.querySelector("#prest-modal-backdrop .prest-modal"),title:document.getElementById("prest-modal-title"),tabs:[...document.querySelectorAll("#prest-modal-backdrop .prest-tab")],panes:[...document.querySelectorAll("#prest-modal-backdrop .prest-pane")],codigo:document.getElementById("prest-modal-codigo"),nome:document.getElementById("prest-modal-nome"),apelido:document.getElementById("prest-modal-apelido"),tipo:document.getElementById("prest-modal-tipo"),inicio:document.getElementById("prest-modal-inicio"),termino:document.getElementById("prest-modal-termino"),inativo:document.getElementById("prest-modal-inativo"),executa:document.getElementById("prest-modal-executa"),cro:document.getElementById("prest-modal-cro"),ufCro:document.getElementById("prest-modal-uf-cro"),cpf:document.getElementById("prest-modal-cpf"),rg:document.getElementById("prest-modal-rg"),inss:document.getElementById("prest-modal-inss"),ccm:document.getElementById("prest-modal-ccm"),contrato:document.getElementById("prest-modal-contrato"),cnes:document.getElementById("prest-modal-cnes"),cbos:document.getElementById("prest-modal-cbos"),nascimento:document.getElementById("prest-modal-nascimento"),sexo:document.getElementById("prest-modal-sexo"),estadoCivil:document.getElementById("prest-modal-estado-civil"),prefixo:document.getElementById("prest-modal-prefixo"),inclusao:document.getElementById("prest-modal-inclusao"),alteracao:document.getElementById("prest-modal-alteracao"),idInterno:document.getElementById("prest-modal-id-interno"),foneTipo1:document.getElementById("prest-modal-fone-tipo-1"),fone1:document.getElementById("prest-modal-fone-1"),foneTipo2:document.getElementById("prest-modal-fone-tipo-2"),fone2:document.getElementById("prest-modal-fone-2"),email:document.getElementById("prest-modal-email"),homepage:document.getElementById("prest-modal-homepage"),logradouroTipo:document.getElementById("prest-modal-logradouro-tipo"),endereco:document.getElementById("prest-modal-endereco"),numero:document.getElementById("prest-modal-numero"),complemento:document.getElementById("prest-modal-complemento"),bairro:document.getElementById("prest-modal-bairro"),cidade:document.getElementById("prest-modal-cidade"),cep:document.getElementById("prest-modal-cep"),uf:document.getElementById("prest-modal-uf"),banco:document.getElementById("prest-modal-banco"),agencia:document.getElementById("prest-modal-agencia"),conta:document.getElementById("prest-modal-conta"),nomeConta:document.getElementById("prest-modal-nome-conta"),modoPagamento:document.getElementById("prest-modal-modo-pagamento"),faculdade:document.getElementById("prest-modal-faculdade"),formatura:document.getElementById("prest-modal-formatura"),alerta:document.getElementById("prest-modal-alerta"),observacoes:document.getElementById("prest-modal-observacoes"),especialidades:[...document.querySelectorAll("#prest-modal-backdrop .prest-checklist input[type='checkbox']")],ok:document.getElementById("prest-modal-ok"),cancelar:document.getElementById("prest-modal-cancelar"),modo:"novo",editId:null,tabAtual:"principal"}};ensurePanelChrome(prestCfg.panel);ensureModalChrome(prestCfg.modal.modal);if(prestCfg.tbody&&prestCfg.tbody.dataset.prestGridBound!=="true"){prestCfg.tbody.dataset.prestGridBound="true";let lastId=0;let lastTs=0;prestCfg.tbody.addEventListener("click",ev=>{const tr=ev.target.closest("tr[data-id]");if(!tr)return;const id=Number(tr.dataset.id||0)||0;const now=Date.now();const isDouble=id>0&&id===lastId&&(now-lastTs)<=450;lastId=id;lastTs=now;prestSelecionarLinha(tr);if(isDouble){lastId=0;lastTs=0;prestAbrirModal("editar")}})}prestCfg.cboEspecialidade.addEventListener("change",prestRender);prestCfg.txtNome.addEventListener("input",prestRender);prestCfg.btnNovo.addEventListener("click",()=>prestAbrirModal("novo"));prestCfg.btnEditar.addEventListener("click",()=>prestAbrirModal("editar"));prestCfg.btnExcluir.addEventListener("click",prestExcluirSelecionado);prestCfg.btnAgenda.addEventListener("click",()=>prestAcoesPlaceholder("Agenda"));prestCfg.btnConvenios.addEventListener("click",()=>prestAcoesPlaceholder("Convênios"));prestCfg.btnComissoes.addEventListener("click",()=>prestAcoesPlaceholder("Comissões"));prestCfg.btnFechar.addEventListener("click",()=>{prestCfg.panel.classList.add("hidden");workspaceEmpty.classList.remove("hidden");footerMsg.textContent="Cadastro > Prestadores fechado."});prestCfg.modal.tabs.forEach(btn=>btn.addEventListener("click",()=>prestDadosTab(btn.dataset.tab||"principal")));prestCfg.modal.ok.addEventListener("click",prestSalvarModal);prestCfg.modal.cancelar.addEventListener("click",prestFecharModal);prestCfg.modal.cpf.addEventListener("blur",()=>prestNormalizarCpfCampo(prestCfg.modal.cpf));prestCfg.modal.cpf.addEventListener("keydown",ev=>{if(ev.key==="Enter"||ev.key==="Tab")prestNormalizarCpfCampo(prestCfg.modal.cpf)});prestCfg.modal.backdrop.addEventListener("click",ev=>{if(ev.target===prestCfg.modal.backdrop)prestFecharModal()})}
function prestAgendaNovoEstado(item){return{manha_inicio:String(item?.agenda_config?.manha_inicio||"07:00"),manha_fim:String(item?.agenda_config?.manha_fim||"13:00"),tarde_inicio:String(item?.agenda_config?.tarde_inicio||"13:00"),tarde_fim:String(item?.agenda_config?.tarde_fim||"20:00"),duracao:String(item?.agenda_config?.duracao||"5"),semana_horarios:String(item?.agenda_config?.semana_horarios||"12"),dia_horarios:String(item?.agenda_config?.dia_horarios||"12"),bloqueios_obs:String(item?.agenda_config?.bloqueios_obs||""),apresentacao_obs:String(item?.agenda_config?.apresentacao_obs||""),apresentacao_particular_cor:String(item?.agenda_config?.apresentacao_particular_cor||"#ffff00"),apresentacao_convenio_cor:String(item?.agenda_config?.apresentacao_convenio_cor||"#0000ff"),apresentacao_compromisso_cor:String(item?.agenda_config?.apresentacao_compromisso_cor||"#00e5ef"),apresentacao_fonte:item?.agenda_config?.apresentacao_fonte?{family:String(item.agenda_config.apresentacao_fonte.family||"MS Sans Serif"),size:Number(item.agenda_config.apresentacao_fonte.size||8),bold:!!item.agenda_config.apresentacao_fonte.bold,italic:!!item.agenda_config.apresentacao_fonte.italic,underline:!!item.agenda_config.apresentacao_fonte.underline,strike:!!item.agenda_config.apresentacao_fonte.strike,color:String(item.agenda_config.apresentacao_fonte.color||"#000000"),script:String(item.agenda_config.apresentacao_fonte.script||"Ocidental")}:{family:"MS Sans Serif",size:8,bold:false,italic:false,underline:false,strike:false,color:"#000000",script:"Ocidental"},visualizacao_obs:String(item?.agenda_config?.visualizacao_obs||""),visualizacao_campos:Array.isArray(item?.agenda_config?.visualizacao_campos)?item.agenda_config.visualizacao_campos:PREST_AGENDA_VISUALIZACAO_PADRAO.slice()}}
const PREST_AGENDA_DIAS=[{codigo:1,label:"Segunda"},{codigo:2,label:"Terça"},{codigo:3,label:"Quarta"},{codigo:4,label:"Quinta"},{codigo:5,label:"Sexta"},{codigo:6,label:"Sábado"},{codigo:7,label:"Domingo"}];
let prestAgendaUnidadesCache=[];
function prestAgendaDiaCodigo(valor){const txt=String(valor??"").trim().toLowerCase();if(!txt)return null;const n=Number(txt);if(Number.isFinite(n)&&n>=1&&n<=7)return n;const item=PREST_AGENDA_DIAS.find(d=>d.label.toLowerCase()===txt);return item?item.codigo:null}
function prestAgendaDiaLabel(valor){const txt=String(valor??"").trim();if(!txt)return "";const n=Number(txt);if(Number.isFinite(n)){const item=PREST_AGENDA_DIAS.find(d=>d.codigo===n);if(item)return item.label}const item=PREST_AGENDA_DIAS.find(d=>d.label.toLowerCase()===txt.toLowerCase());return item?item.label:txt}
function prestAgendaDiaCodigoSelect(select){if(!(select instanceof HTMLSelectElement))return null;const byValue=prestAgendaDiaCodigo(select.value);if(byValue)return byValue;const idx=Number(select.selectedIndex);if(Number.isFinite(idx)&&idx>=0&&idx<PREST_AGENDA_DIAS.length)return idx+1;return null}
function prestAgendaDiaSetSelect(select,valor){if(!(select instanceof HTMLSelectElement))return;const codigo=prestAgendaDiaCodigo(valor)||1;const idx=Math.max(0,Math.min(PREST_AGENDA_DIAS.length-1,codigo-1));if(select.options[idx]){select.selectedIndex=idx;return}select.value=prestAgendaDiaLabel(codigo)}
function prestAgendaNormalizarData(valor){const txt=String(valor||"").trim();if(!txt)return"";const m=txt.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);if(!m)return null;const d=Number(m[1]),mes=Number(m[2]),a=Number(m[3]);if(!(d>=1&&d<=31&&mes>=1&&mes<=12&&a>=1900&&a<=2100))return null;const dt=new Date(a,mes-1,d);if(dt.getFullYear()!==a||dt.getMonth()!==mes-1||dt.getDate()!==d)return null;return`${String(d).padStart(2,"0")}/${String(mes).padStart(2,"0")}/${String(a).padStart(4,"0")}`}
function prestAgendaDataNumero(valor){const normal=prestAgendaNormalizarData(valor);if(!normal)return null;const [d,m,a]=normal.split("/").map(Number);return a*10000+m*100+d}
function prestAgendaNormalizarHora(valor){const txt=String(valor||"").trim();if(!txt)return"";const m=txt.match(/^([01]?\d|2[0-3]):([0-5]\d)$/);if(!m)return null;const h=Number(m[1]),min=Number(m[2]);return`${String(h).padStart(2,"0")}:${String(min).padStart(2,"0")}`}
function prestAgendaHoraMs(valor){const normal=prestAgendaNormalizarHora(valor);if(!normal)return null;const [h,m]=normal.split(":").map(Number);return((h*60)+m)*60000}
function prestAgendaHoraFromAny(valor){const bruto=String(valor??"").trim();if(!bruto)return"";const normal=prestAgendaNormalizarHora(bruto);if(normal)return normal;const digits=bruto.replace(/\D+/g,"");if(!digits)return"";if(digits.length===3||digits.length===4){const pad=digits.padStart(4,"0");return prestAgendaNormalizarHora(`${pad.slice(0,2)}:${pad.slice(2,4)}`)||""}if(digits.length>=6){const hh=digits.slice(0,2);const mm=digits.slice(2,4);const hhmm=prestAgendaNormalizarHora(`${hh}:${mm}`);if(hhmm)return hhmm}const num=Number(digits);if(Number.isFinite(num)&&num>2359&&num<=86400000){const totalMin=Math.floor(num/60000);const h=Math.floor(totalMin/60)%24;const m=totalMin%60;return`${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`}if(Number.isFinite(num)&&num>=0&&num<=2359){const pad=String(num).padStart(4,"0");return prestAgendaNormalizarHora(`${pad.slice(0,2)}:${pad.slice(2,4)}`)||""}return""}
function prestAgendaNormalizarHoraEscala(valor){const txt=String(valor??"").trim();if(!txt)return"";if(/^\d{1,2}$/.test(txt)){const h=Number(txt);if(Number.isFinite(h)&&h>=0&&h<=23)return`${String(h).padStart(2,"0")}:00`;return""}return prestAgendaNormalizarHora(txt)||""}
function prestAgendaDataFromAny(valor){const bruto=String(valor??"").trim();if(!bruto)return"";const normal=prestAgendaNormalizarData(bruto);if(normal)return normal;const digits=bruto.replace(/\D+/g,"");if(digits.length===8){const candidato=`${digits.slice(0,2)}/${digits.slice(2,4)}/${digits.slice(4,8)}`;return prestAgendaNormalizarData(candidato)||""}return""}
function prestAgendaMascaraDataCampo(campo){if(!(campo instanceof HTMLInputElement))return;let digits=campo.value.replace(/\D+/g,"").slice(0,8);if(digits.length>=5)campo.value=`${digits.slice(0,2)}/${digits.slice(2,4)}/${digits.slice(4)}`;else if(digits.length>=3)campo.value=`${digits.slice(0,2)}/${digits.slice(2)}`;else campo.value=digits}
function prestAgendaMascaraHoraCampo(campo){if(!(campo instanceof HTMLInputElement))return;let digits=campo.value.replace(/\D+/g,"").slice(0,4);if(digits.length>=3)campo.value=`${digits.slice(0,2)}:${digits.slice(2)}`;else campo.value=digits}
function prestAgendaConfigurarCamposBloqueioModal(m){if(!m||m._maskBound)return;m._maskBound=true;[m.vigenciaInicio,m.vigenciaFim].forEach(input=>{if(!(input instanceof HTMLInputElement))return;input.placeholder="";input.inputMode="numeric";input.maxLength=10;input.style.minWidth="88px";input.addEventListener("input",()=>prestAgendaMascaraDataCampo(input));input.addEventListener("blur",()=>{prestAgendaMascaraDataCampo(input);const v=prestAgendaDataFromAny(input.value);input.value=v||String(input.value||"").trim()})});[m.inicio,m.final].forEach(input=>{if(!(input instanceof HTMLInputElement))return;input.placeholder="";input.inputMode="numeric";input.maxLength=5;input.style.minWidth="64px";input.addEventListener("input",()=>prestAgendaMascaraHoraCampo(input));input.addEventListener("blur",()=>{prestAgendaMascaraHoraCampo(input);const v=prestAgendaHoraFromAny(input.value);input.value=v||String(input.value||"").trim()})})}
async function prestAgendaCarregarUnidadesAtendimento(){try{const{res,data}=await requestJson("GET","/cadastros/unidades-atendimento/combos",undefined,true);if(res.ok){const itens=Array.isArray(data?.itens)?data.itens:[];prestAgendaUnidadesCache=itens.map(item=>({row_id:Number(item?.row_id||item?.id||0)||null,source_id:Number(item?.source_id||item?.id_legacy||0)||null,nome:String(item?.nome||item?.descricao||"").trim()})).filter(item=>item.nome);if(prestAgendaUnidadesCache.length)return prestAgendaUnidadesCache}}catch{}if(!prestAgendaUnidadesCache.length)prestAgendaUnidadesCache=[{row_id:null,source_id:null,nome:"Instituto Brana - Odontologia"}];return prestAgendaUnidadesCache}
function prestAgendaPreencherComboUnidades(select,atualNome="",atualSource=null,atualRow=null){if(!(select instanceof HTMLSelectElement))return;const lista=[...prestAgendaUnidadesCache];const nomeAtual=String(atualNome||"").trim();if(nomeAtual&&!lista.some(item=>String(item.nome||"").toLowerCase()===nomeAtual.toLowerCase()))lista.push({row_id:Number(atualRow||0)||null,source_id:Number(atualSource||0)||null,nome:nomeAtual});const unicos=[];const seen=new Set();for(const item of lista){const key=`${String(item.row_id||"")}|${String(item.source_id||"")}|${String(item.nome||"").toLowerCase()}`;if(seen.has(key))continue;seen.add(key);unicos.push(item)}select.innerHTML=unicos.map(item=>`<option value="${esc(String(item.row_id??""))}" data-row-id="${esc(String(item.row_id??""))}" data-source-id="${esc(String(item.source_id??""))}" data-nome="${esc(String(item.nome||""))}">${esc(String(item.nome||""))}</option>`).join("");const alvoRow=String(Number(atualRow||0)||"");if(alvoRow&&[...select.options].some(opt=>String(opt.value||"")===alvoRow)){select.value=alvoRow;return}const alvoNome=nomeAtual.toLowerCase();const byNome=[...select.options].find(opt=>String(opt.dataset.nome||opt.textContent||"").trim().toLowerCase()===alvoNome);if(byNome){select.value=byNome.value;return}if(select.options.length>0)select.selectedIndex=0}
function prestAgendaTab(tab){if(!prestCfg?.agenda)return;prestCfg.agenda.tabs.forEach(btn=>btn.classList.toggle("active",btn.dataset.tab===tab));prestCfg.agenda.panes.forEach(pane=>pane.classList.toggle("hidden",pane.dataset.tab!==tab));prestCfg.agenda.tabAtual=tab}
function prestAgendaFechar(){if(prestCfg?.agenda?.backdrop)prestCfg.agenda.backdrop.classList.add("hidden")}
function prestBuildPayloadFromItem(item,agendaConfigOverride=null,alertaOverride=null){const src=item||{};const especialidadesExec=Array.isArray(src?.especialidades_exec)?src.especialidades_exec:[];return{codigo:String(src.codigo||prestNovoCodigo()).trim()||prestNovoCodigo(),nome:String(src.nome||"").trim(),apelido:String(src.apelido||"").trim(),tipo_prestador:String(src.tipo_prestador||""),inicio:String(src.inicio||"").trim(),termino:String(src.termino||"").trim(),ativo:src.ativo!==false,executa_procedimento:!!src.executa_procedimento,cro:String(src.cro||"").trim(),uf_cro:String(src.uf_cro||"").trim(),cpf:String(src.cpf||"").trim(),rg:String(src.rg||"").trim(),inss:String(src.inss||"").trim(),ccm:String(src.ccm||"").trim(),contrato:String(src.contrato||"").trim(),cnes:String(src.cnes||"").trim(),cbos:String(src.cbos||"").trim(),nascimento:String(src.nascimento||"").trim(),sexo:String(src.sexo||""),estado_civil:String(src.estado_civil||""),prefixo:String(src.prefixo||""),inclusao:String(src.inclusao||prestHojeBr()),alteracao:prestHojeBr(),id_interno:String(src.id_interno||Date.now()).trim(),fone1_tipo:String(src.fone1_tipo||""),fone1:String(src.fone1||"").trim(),fone2_tipo:String(src.fone2_tipo||""),fone2:String(src.fone2||"").trim(),email:String(src.email||"").trim(),homepage:String(src.homepage||"").trim(),logradouro_tipo:String(src.logradouro_tipo||""),endereco:String(src.endereco||"").trim(),numero:String(src.numero||"").trim(),complemento:String(src.complemento||"").trim(),bairro:String(src.bairro||"").trim(),cidade:String(src.cidade||"").trim(),cep:String(src.cep||"").trim(),uf:String(src.uf||"").trim(),banco:String(src.banco||"").trim(),agencia:String(src.agencia||"").trim(),conta:String(src.conta||"").trim(),nome_conta:String(src.nome_conta||"").trim(),modo_pagamento:String(src.modo_pagamento||""),faculdade:String(src.faculdade||"").trim(),formatura:String(src.formatura||"").trim(),alerta_agendamentos:String(alertaOverride!=null?alertaOverride:(src.alerta_agendamentos||"")).trim(),especialidades_exec:especialidadesExec,especialidade:String(src.especialidade||especialidadesExec[0]||""),agenda_config:agendaConfigOverride&&typeof agendaConfigOverride==="object"?agendaConfigOverride:(src.agenda_config&&typeof src.agenda_config==="object"?src.agenda_config:{}),observacoes:String(src.observacoes||"").trim()}}
async function prestAgendaSalvar(){
if(!prestCfg?.agenda)return;
const item=prestSelecionado();
if(!item){prestAgendaFechar();return}
const manhaInicio=prestAgendaNormalizarHoraEscala(prestCfg.agenda.manhaInicio.value||"");
if(!manhaInicio){window.alert("Horário inicial da manhã inválido. Use HH:MM (ex.: 06:00).");prestCfg.agenda.manhaInicio.focus();return}
const manhaFim=prestAgendaNormalizarHoraEscala(prestCfg.agenda.manhaFim.value||"");
if(!manhaFim){window.alert("Horário final da manhã inválido. Use HH:MM (ex.: 13:00).");prestCfg.agenda.manhaFim.focus();return}
const tardeInicio=prestAgendaNormalizarHoraEscala(prestCfg.agenda.tardeInicio.value||"");
if(!tardeInicio){window.alert("Horário inicial da tarde inválido. Use HH:MM (ex.: 13:00).");prestCfg.agenda.tardeInicio.focus();return}
const tardeFim=prestAgendaNormalizarHoraEscala(prestCfg.agenda.tardeFim.value||"");
if(!tardeFim){window.alert("Horário final da tarde inválido. Use HH:MM (ex.: 20:00).");prestCfg.agenda.tardeFim.focus();return}
prestCfg.agenda.manhaInicio.value=manhaInicio;
prestCfg.agenda.manhaFim.value=manhaFim;
prestCfg.agenda.tardeInicio.value=tardeInicio;
prestCfg.agenda.tardeFim.value=tardeFim;
const bloqueiosItens=Array.isArray(item?.agenda_config?.bloqueios_itens)?item.agenda_config.bloqueios_itens:[];
const visualizacaoCampos=Array.isArray(prestCfg.agenda.visualizacaoChecks)?prestCfg.agenda.visualizacaoChecks.filter(chk=>chk.checked).map(chk=>chk.value):PREST_AGENDA_VISUALIZACAO_PADRAO.slice();
const agendaConfig={manha_inicio:manhaInicio,manha_fim:manhaFim,tarde_inicio:tardeInicio,tarde_fim:tardeFim,duracao:String(prestCfg.agenda.duracao.value||"5").trim(),semana_horarios:String(prestCfg.agenda.semana.value||"12").trim(),dia_horarios:String(prestCfg.agenda.dia.value||"12").trim(),bloqueios_obs:prestCfg.agenda.bloqueios?String(prestCfg.agenda.bloqueios.value||"").trim():"",bloqueios_itens:bloqueiosItens,apresentacao_obs:prestCfg.agenda.apresentacao?String(prestCfg.agenda.apresentacao.value||"").trim():"",apresentacao_particular_cor:String(prestCfg.agenda.apresParticular?.value||"#ffff00"),apresentacao_convenio_cor:String(prestCfg.agenda.apresConvenio?.value||"#0000ff"),apresentacao_compromisso_cor:String(prestCfg.agenda.apresCompromisso?.value||"#00e5ef"),apresentacao_fonte:prestCfg.agenda.apresFonteState?{...prestCfg.agenda.apresFonteState}:{family:"MS Sans Serif",size:8,bold:false,italic:false,underline:false,strike:false,color:"#000000",script:"Ocidental"},visualizacao_obs:String(prestCfg.agenda.visualizacao.value||"").trim(),visualizacao_campos:visualizacaoCampos};
const alertaAgenda=`Escala ${agendaConfig.manha_inicio}-${agendaConfig.manha_fim} / ${agendaConfig.tarde_inicio}-${agendaConfig.tarde_fim}`;
item.agenda_config=agendaConfig;
item.alerta_agendamentos=alertaAgenda;
const idx=prestadoresCache.findIndex(x=>Number(x.id||0)===Number(item.id||0));
if(idx>=0)prestadoresCache[idx]={...item};
let syncPrestadorId=Number(item.id||0)||0;
let syncAgendaConfig=item.agenda_config&&typeof item.agenda_config==="object"?item.agenda_config:agendaConfig;
const editId=Number(item.id||0);
if(editId>0){
try{
const payload=prestBuildPayloadFromItem(item,agendaConfig,alertaAgenda);
const{res,data}=await requestJson("PUT",`/cadastros/prestadores/${editId}`,payload,true);
if(!res.ok)throw new Error(String(data?.detail||"Falha ao salvar agenda do prestador."));
const salvo={...prestNovoItemBase(),...(data||{}),especialidades_exec:Array.isArray(data?.especialidades_exec)?data.especialidades_exec:[],agenda_config:data?.agenda_config&&typeof data.agenda_config==="object"?data.agenda_config:{}};
const idxSalvo=prestadoresCache.findIndex(x=>Number(x.id||0)===Number(salvo.id||0));
if(idxSalvo>=0)prestadoresCache[idxSalvo]=salvo;else prestadoresCache.push(salvo);
prestadorSelId=salvo.id;
syncPrestadorId=Number(salvo.id||syncPrestadorId)||syncPrestadorId;
syncAgendaConfig=salvo.agenda_config&&typeof salvo.agenda_config==="object"?salvo.agenda_config:syncAgendaConfig;
}catch(err){window.alert(err?.message||"Não foi possível salvar a configuração da agenda.");return}}
if(typeof agendaSemanaAplicarConfigPrestador==="function"){
try{await agendaSemanaAplicarConfigPrestador(syncPrestadorId,syncAgendaConfig)}catch(err){console.error(err)}
}
prestRender();
prestAgendaFechar();
footerMsg.textContent=`Prestadores > Agenda '${item.nome}' salva.`
}
function prestAgendaBloqueiosLista(){const item=prestSelecionado();if(!item)return[];item.agenda_config=item.agenda_config||prestAgendaNovoEstado(item);if(!Array.isArray(item.agenda_config.bloqueios_itens))item.agenda_config.bloqueios_itens=[];return item.agenda_config.bloqueios_itens}
function prestAgendaBloqueiosSelecionar(tr){if(!prestCfg?.agenda)return;prestCfg.agenda.bloqueioSelId=Number(tr?.dataset.id||0)||null;prestAgendaBloqueiosRender()}
function prestAgendaBloqueiosRender(){if(!prestCfg?.agenda?.bloqueiosTbody)return;const lista=prestAgendaBloqueiosLista();const vigenciaTexto=item=>{const ini=String(item?.data_ini||item?.vigencia_inicio||item?.vigencia||"").trim();const fim=String(item?.data_fin||item?.vigencia_fim||"").trim();if(ini&&fim)return `${ini} a ${fim}`;return ini||fim||""};prestCfg.agenda.bloqueiosTbody.innerHTML=lista.map(item=>`<tr data-id="${item.id}" class="${Number(item.id||0)===Number(prestCfg.agenda.bloqueioSelId||0)?"selected":""}"><td>${esc(String(item.unidade||""))}</td><td>${esc(prestAgendaDiaLabel(item?.dia||item?.dia_sem||""))}</td><td>${esc(vigenciaTexto(item))}</td><td>${esc(String(item.hora_ini||item.inicio||""))}</td><td>${esc(String(item.hora_fin||item.final||""))}</td></tr>`).join("")||'<tr><td colspan="5"></td></tr>'}
function prestAgendaBloqueioAtual(){return prestAgendaBloqueiosLista().find(item=>Number(item.id||0)===Number(prestCfg?.agenda?.bloqueioSelId||0))||null}
function prestAgendaBloqueioFecharModal(){if(prestCfg?.agendaBloqueioModal?.backdrop)prestCfg.agendaBloqueioModal.backdrop.classList.add("hidden")}
function prestAgendaBloqueioSalvar(){const m=prestCfg?.agendaBloqueioModal;if(!m)return;prestAgendaConfigurarCamposBloqueioModal(m);const unidadeOpt=m.unidade?.selectedOptions?.[0]||null;const unidadeNome=String(unidadeOpt?.dataset?.nome||unidadeOpt?.textContent||m.unidade.value||"").trim();const unidadeRowId=Number(unidadeOpt?.dataset?.rowId||m.unidade.value||0)||null;const unidadeId=Number(unidadeOpt?.dataset?.sourceId||0)||null;const diaSem=prestAgendaDiaCodigoSelect(m.dia)||1;const diaLabel=prestAgendaDiaLabel(diaSem);const dataIni=prestAgendaDataFromAny(m.vigenciaInicio.value||"");const dataFim=prestAgendaDataFromAny(m.vigenciaFim.value||"");if(String(m.vigenciaInicio.value||"").trim()&&!dataIni){window.alert("Período de vigência (início) inválido. Use dd/mm/aaaa.");m.vigenciaInicio.focus();return}if(String(m.vigenciaFim.value||"").trim()&&!dataFim){window.alert("Período de vigência (fim) inválido. Use dd/mm/aaaa.");m.vigenciaFim.focus();return}m.vigenciaInicio.value=dataIni||"";m.vigenciaFim.value=dataFim||"";if(dataIni&&dataFim){const iniNum=prestAgendaDataNumero(dataIni);const fimNum=prestAgendaDataNumero(dataFim);if(iniNum!==null&&fimNum!==null&&fimNum<iniNum){window.alert("A vigência final deve ser maior ou igual à vigência inicial.");m.vigenciaFim.focus();return}}const horaIni=prestAgendaHoraFromAny(m.inicio.value||"");const horaFim=prestAgendaHoraFromAny(m.final.value||"");if(String(m.inicio.value||"").trim()&&!horaIni){window.alert("Intervalo de horário (início) inválido. Use hh:mm.");m.inicio.focus();return}if(String(m.final.value||"").trim()&&!horaFim){window.alert("Intervalo de horário (fim) inválido. Use hh:mm.");m.final.focus();return}m.inicio.value=horaIni||"";m.final.value=horaFim||"";if((horaIni&&!horaFim)||(!horaIni&&horaFim)){window.alert("Preencha o intervalo completo de horário (início e fim).");if(!horaIni)m.inicio.focus();else m.final.focus();return}if(horaIni&&horaFim){const iniMs=prestAgendaHoraMs(horaIni);const fimMs=prestAgendaHoraMs(horaFim);if(iniMs!==null&&fimMs!==null&&fimMs<=iniMs){window.alert("O horário final deve ser maior que o horário inicial.");m.final.focus();return}}const mensagem=String(m.mensagem.value||"").trim();const payload={id:m.editId||Date.now(),unidade:unidadeNome||"Instituto Brana - Odontologia",unidade_id:unidadeId,unidade_row_id:unidadeRowId,dia:diaLabel,dia_sem:diaSem,vigencia_inicio:dataIni||"",vigencia_fim:dataFim||"",data_ini:dataIni||"",data_fin:dataFim||"",inicio:horaIni||"",final:horaFim||"",hora_ini:horaIni||"",hora_fin:horaFim||"",hora_ini_ms:prestAgendaHoraMs(horaIni),hora_fin_ms:prestAgendaHoraMs(horaFim),mensagem,msg_agenda:mensagem};const lista=prestAgendaBloqueiosLista();const idx=lista.findIndex(item=>Number(item.id||0)===Number(payload.id||0));if(idx>=0)lista[idx]=payload;else lista.push(payload);prestCfg.agenda.bloqueioSelId=payload.id;prestAgendaBloqueiosRender();prestAgendaBloqueioFecharModal()}
async function prestAgendaBloqueioAbrirModal(modo){prestAgendaEnhanceBloqueios();const atual=modo==="editar"?prestAgendaBloqueioAtual():null;if(modo==="editar"&&!atual){window.alert("Selecione um bloqueio.");return}await prestAgendaCarregarUnidadesAtendimento();const m=prestCfg.agendaBloqueioModal;prestAgendaConfigurarCamposBloqueioModal(m);m.editId=atual?Number(atual.id||0):null;m.title.textContent=modo==="editar"?"Altera bloqueio":"Novo bloqueio";m.unidade.innerHTML="";prestAgendaPreencherComboUnidades(m.unidade,String(atual?.unidade||""),Number(atual?.unidade_id||0)||null,Number(atual?.unidade_row_id||0)||null);prestAgendaDiaSetSelect(m.dia,atual?.dia_sem||atual?.dia||"Segunda");m.vigenciaInicio.value=prestAgendaDataFromAny(atual?.data_ini||atual?.vigencia_inicio||atual?.vigencia||prestHojeBr())||"";m.vigenciaFim.value=prestAgendaDataFromAny(atual?.data_fin||atual?.vigencia_fim||"")||"";m.inicio.value=prestAgendaHoraFromAny(atual?.hora_ini||atual?.inicio||"")||"";m.final.value=prestAgendaHoraFromAny(atual?.hora_fin||atual?.final||"")||"";m.mensagem.value=String(atual?.msg_agenda||atual?.mensagem||"");m.backdrop.classList.remove("hidden")}
function prestAgendaBloqueioExcluir(){const atual=prestAgendaBloqueioAtual();if(!atual){window.alert("Selecione um bloqueio.");return}if(!window.confirm("Deseja eliminar este bloqueio?"))return;const lista=prestAgendaBloqueiosLista();const idx=lista.findIndex(item=>Number(item.id||0)===Number(atual.id||0));if(idx>=0)lista.splice(idx,1);prestCfg.agenda.bloqueioSelId=null;prestAgendaBloqueiosRender()}
function prestAgendaApresCorOptions(){return[{value:"#ffff00",label:"Amarelo"},{value:"#0000ff",label:"Azul"},{value:"#00e5ef",label:"Azul água"},{value:"#000080",label:"Azul marinho"},{value:"#ffffff",label:"Branco"},{value:"#808080",label:"Cinza"},{value:"#d9d9d9",label:"Cinza claro"},{value:"#666666",label:"Cinza escuro"},{value:"#c61ad9",label:"Lilás"},{value:"#8b4513",label:"Marrom"},{value:"#c0c0c0",label:"Prata"},{value:"#000000",label:"Preto"},{value:"#800080",label:"Roxo"},{value:"#008000",label:"Verde"},{value:"#006400",label:"Verde escuro"},{value:"#00ff00",label:"Verde limão"},{value:"#808000",label:"Verde oliva"},{value:"#ff0000",label:"Vermelho"}]}
function prestAgendaApresPreviewSync(){if(!prestCfg?.agenda)return;const f=prestCfg.agenda.apresFonteState||{family:"MS Sans Serif",size:8,bold:false,italic:false,underline:false,strike:false,color:"#000000"};const apply=(el,color,texto)=>{if(!el)return;el.style.background=color;el.style.fontFamily=f.family;el.style.fontSize=`${f.size}px`;el.style.fontWeight=f.bold?"700":"400";el.style.fontStyle=f.italic?"italic":"normal";el.style.textDecoration=[f.underline?"underline":"",f.strike?"line-through":""].filter(Boolean).join(" ")||"none";el.style.color=f.color;el.textContent=texto};apply(prestCfg.agenda.previewParticular,prestCfg.agenda.apresParticular?.value||"#ffff00","Particular");apply(prestCfg.agenda.previewConvenio,prestCfg.agenda.apresConvenio?.value||"#0000ff","Convênio");apply(prestCfg.agenda.previewCompromisso,prestCfg.agenda.apresCompromisso?.value||"#00e5ef","Compromisso")}
function prestAgendaFonteFechar(){if(prestCfg?.agendaFonteModal?.backdrop)prestCfg.agendaFonteModal.backdrop.classList.add("hidden")}
function prestAgendaFontePreviewSync(){if(!prestCfg?.agendaFonteModal)return;const m=prestCfg.agendaFonteModal;const styleValue=String(m.style.value||"Regular");const isBold=styleValue==="Negrito"||styleValue==="Oblíquo e negrito";const isItalic=styleValue==="Oblíquo"||styleValue==="Oblíquo e negrito";m.sample.style.fontFamily=String(m.family.value||"MS Sans Serif");m.sample.style.fontSize=`${Number(m.size.value||8)}px`;m.sample.style.fontWeight=isBold?"700":"400";m.sample.style.fontStyle=isItalic?"italic":"normal";m.sample.style.textDecoration=[m.underline.checked?"underline":"",m.strike.checked?"line-through":""].filter(Boolean).join(" ")||"none";m.sample.style.color=String(m.color.value||"#000000");m.colorSwatch.style.background=String(m.color.value||"#000000");m.familyInput.value=m.family.value;m.styleInput.value=m.style.value;m.sizeInput.value=m.size.value}
function prestAgendaFonteAbrir(){prestAgendaEnhanceApresentacao();const s=prestCfg.agenda.apresFonteState||{family:"MS Sans Serif",size:8,bold:false,italic:false,underline:false,strike:false,color:"#000000",script:"Ocidental"};const m=prestCfg.agendaFonteModal;m.family.value=s.family;m.style.value=s.bold&&s.italic?"Oblíquo e negrito":s.bold?"Negrito":s.italic?"Oblíquo":"Regular";m.size.value=String(s.size);m.strike.checked=!!s.strike;m.underline.checked=!!s.underline;m.color.value=s.color;m.script.value=s.script||"Ocidental";prestAgendaFontePreviewSync();m.backdrop.classList.remove("hidden")}
function prestAgendaFonteSalvar(){if(!prestCfg?.agendaFonteModal)return;const styleValue=String(prestCfg.agendaFonteModal.style.value||"Regular");prestCfg.agenda.apresFonteState={family:String(prestCfg.agendaFonteModal.family.value||"MS Sans Serif"),size:Number(prestCfg.agendaFonteModal.size.value||8),bold:styleValue==="Negrito"||styleValue==="Oblíquo e negrito",italic:styleValue==="Oblíquo"||styleValue==="Oblíquo e negrito",underline:!!prestCfg.agendaFonteModal.underline.checked,strike:!!prestCfg.agendaFonteModal.strike.checked,color:String(prestCfg.agendaFonteModal.color.value||"#000000"),script:String(prestCfg.agendaFonteModal.script.value||"Ocidental")};prestAgendaApresPreviewSync();prestAgendaFonteFechar()}
function prestAgendaVisualizacaoCampos(){return["Número do paciente","Número do prontuário","Nome do paciente","Matrícula","Convênio","Tabela","Fone 1","Fone 2","Fone 3","Sala"]}
function prestAgendaVisualizacaoHtml(){const campos=prestAgendaVisualizacaoCampos();return `<div class="prest-agenda-vis-wrap"><label class="prest-agenda-vis-title" for="prest-agenda-vis-list">Dados a serem visualizados no agendamento:</label><div id="prest-agenda-vis-list" class="prest-agenda-vis-list">${campos.map((campo,idx)=>`<label class="prest-agenda-vis-item" for="prest-agenda-vis-chk-${idx}"><input id="prest-agenda-vis-chk-${idx}" type="checkbox" value="${campo}"><span>${campo}</span></label>`).join("")}</div></div><textarea id="prest-agenda-visualizacao" class="prest-agenda-vis-hidden" style="display:none!important;visibility:hidden!important;position:absolute!important;left:-9999px!important;top:-9999px!important;width:1px!important;height:1px!important;pointer-events:none!important;"></textarea>`}
function prestAgendaEnhanceApresentacao(){
if(!prestCfg?.agenda)return;
const pane=prestCfg.agenda.panes.find(item=>item.dataset.tab==="apresentacao");
if(!pane)return;
if(!document.getElementById("prest-agenda-apres-style")){
const style=document.createElement("style");
style.id="prest-agenda-apres-style";
style.textContent=".prest-agenda-apres-wrap{display:grid;grid-template-columns:1fr 142px;gap:12px;align-items:start}.prest-agenda-apres-box{border:1px solid #bfc9d6;background:#fff;padding:8px;box-sizing:border-box}.prest-agenda-apres-box h4{margin:0 0 8px;font:700 12px Tahoma,sans-serif}.prest-agenda-apres-field{display:grid;grid-template-columns:max-content 24px 1fr;gap:6px;align-items:center;margin:0 0 7px}.prest-agenda-apres-field label{margin:0;white-space:nowrap;font:12px Tahoma,sans-serif}.prest-agenda-apres-swatch{width:18px;height:12px;border:1px solid #222;display:inline-block;box-sizing:border-box}.prest-agenda-apres-field select{height:22px;border:1px solid #8fa7c0;padding:0 4px;background:#fff;font:12px Tahoma,sans-serif;box-sizing:border-box}.prest-agenda-apres-font-top{display:flex;justify-content:center;margin-bottom:8px}.prest-agenda-apres-preview{height:28px;border:1px solid #222;display:flex;align-items:center;justify-content:center;margin:0 0 8px;font:12px Tahoma,sans-serif;box-sizing:border-box}.prest-agenda-apres-hidden{display:none!important}.prest-agenda-font-modal{width:min(560px,94vw);background:#f5f5f3;border:1px solid #c8ced8;box-sizing:border-box}.prest-agenda-font-body{padding:8px 10px 8px;display:grid;gap:8px}.prest-agenda-font-top{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.75fr) 56px 74px;gap:6px;align-items:start}.prest-agenda-font-col{display:flex;flex-direction:column;gap:3px;min-width:0}.prest-agenda-font-col label{margin:0;font:12px Tahoma,sans-serif}.prest-agenda-font-col input{height:22px;border:1px solid #bfc9d6;padding:0 5px;min-width:0;font:12px Tahoma,sans-serif;box-sizing:border-box}.prest-agenda-font-col select{height:138px;border:1px solid #bfc9d6;padding:1px 3px;font:12px Tahoma,sans-serif;box-sizing:border-box}.prest-agenda-font-actions{display:flex;flex-direction:column;gap:6px;padding-top:20px}.prest-agenda-font-actions .btn,.prest-agenda-font-actions .btn-primary{min-width:66px;height:24px;padding:0 8px;border-radius:3px;font:12px Tahoma,sans-serif}.prest-agenda-font-bottom{display:grid;grid-template-columns:170px 1fr;gap:10px;align-items:start}.prest-agenda-font-box{border:1px solid #bfc9d6;background:#fff;padding:8px;box-sizing:border-box}.prest-agenda-font-box h5{margin:0 0 6px;font:12px Tahoma,sans-serif}.prest-agenda-font-effect{display:flex;align-items:center;gap:6px;margin:5px 0}.prest-agenda-font-effect input{margin:0}.prest-agenda-font-color{display:flex;align-items:center;gap:6px;margin-top:6px}.prest-agenda-font-color select,.prest-agenda-font-script select{height:24px;border:1px solid #bfc9d6;padding:0 6px;font:12px Tahoma,sans-serif;box-sizing:border-box}.prest-agenda-font-script{display:flex;flex-direction:column;gap:4px;margin-top:8px}.prest-agenda-font-sample{height:84px;border:1px solid #d8d8d8;background:#fff;display:flex;align-items:center;justify-content:center;font:12px Tahoma,sans-serif}";
document.head.appendChild(style)}
if(!pane.dataset.apresentacaoEnhanced){
const oldTextarea=pane.querySelector("#prest-agenda-apresentacao");
const hiddenTextarea=document.createElement("textarea");
hiddenTextarea.id="prest-agenda-apresentacao";
hiddenTextarea.className="prest-agenda-apres-hidden";
hiddenTextarea.value=oldTextarea?String(oldTextarea.value||""):"";
const colorOptions=prestAgendaApresCorOptions().map(item=>`<option value="${esc(item.value)}">${esc(item.label)}</option>`).join("");
pane.innerHTML=`<div class="prest-agenda-apres-wrap"><div class="prest-agenda-apres-box"><h4>Cor de fundo</h4><div class="prest-agenda-apres-field"><label for="prest-agenda-apres-particular">Pacientes particulares:</label><span class="prest-agenda-apres-swatch" id="prest-agenda-swatch-particular"></span><div><select id="prest-agenda-apres-particular">${colorOptions}</select></div></div><div class="prest-agenda-apres-field"><label for="prest-agenda-apres-convenio">Pacientes de convênio:</label><span class="prest-agenda-apres-swatch" id="prest-agenda-swatch-convenio"></span><div><select id="prest-agenda-apres-convenio">${colorOptions}</select></div></div><div class="prest-agenda-apres-field" style="margin-bottom:0"><label for="prest-agenda-apres-compromisso">Compromissos:</label><span class="prest-agenda-apres-swatch" id="prest-agenda-swatch-compromisso"></span><div><select id="prest-agenda-apres-compromisso">${colorOptions}</select></div></div></div><div class="prest-agenda-apres-box"><h4>Tipo de letra (fonte)</h4><div class="prest-agenda-apres-font-top"><button id="prest-agenda-apres-fonte" class="materiais-btn" type="button"><img src="/desktop-assets/editar.png" alt="">Altera letra...</button></div><div id="prest-agenda-preview-particular" class="prest-agenda-apres-preview">Particular</div><div id="prest-agenda-preview-convenio" class="prest-agenda-apres-preview">Convênio</div><div id="prest-agenda-preview-compromisso" class="prest-agenda-apres-preview" style="margin-bottom:0">Compromisso</div></div></div>`;
pane.appendChild(hiddenTextarea);
pane.dataset.apresentacaoEnhanced="1";
pane.dataset.enhanced="1";
}
prestCfg.agenda.apresentacao=pane.querySelector("#prest-agenda-apresentacao");
prestCfg.agenda.apresParticular=pane.querySelector("#prest-agenda-apres-particular");
prestCfg.agenda.apresConvenio=pane.querySelector("#prest-agenda-apres-convenio");
prestCfg.agenda.apresCompromisso=pane.querySelector("#prest-agenda-apres-compromisso");
prestCfg.agenda.swatchParticular=pane.querySelector("#prest-agenda-swatch-particular");
prestCfg.agenda.swatchConvenio=pane.querySelector("#prest-agenda-swatch-convenio");
prestCfg.agenda.swatchCompromisso=pane.querySelector("#prest-agenda-swatch-compromisso");
prestCfg.agenda.previewParticular=pane.querySelector("#prest-agenda-preview-particular");
prestCfg.agenda.previewConvenio=pane.querySelector("#prest-agenda-preview-convenio");
prestCfg.agenda.previewCompromisso=pane.querySelector("#prest-agenda-preview-compromisso");
const btnFonte=pane.querySelector("#prest-agenda-apres-fonte");
if(btnFonte&&!btnFonte.dataset.boundFonte){btnFonte.dataset.boundFonte="1";btnFonte.addEventListener("click",prestAgendaFonteAbrir)}
const syncSwatch=(select,swatch)=>{if(!(select instanceof HTMLSelectElement)||!(swatch instanceof HTMLElement))return;swatch.style.background=String(select.value||"#ffffff")};
[["apresParticular","swatchParticular"],["apresConvenio","swatchConvenio"],["apresCompromisso","swatchCompromisso"]].forEach(([selectKey,swatchKey])=>{const select=prestCfg.agenda[selectKey];const swatch=prestCfg.agenda[swatchKey];if(select instanceof HTMLSelectElement){if(!select.dataset.boundApres){select.dataset.boundApres="1";select.addEventListener("change",()=>{syncSwatch(select,swatch);prestAgendaApresPreviewSync()})}syncSwatch(select,swatch)}});
if(!document.getElementById("prest-agenda-fonte-backdrop")){
document.body.insertAdjacentHTML("beforeend",`<div id="prest-agenda-fonte-backdrop" class="modal-backdrop hidden"><div class="modal prest-agenda-font-modal"><div class="modal-header"><div class="modal-title">Fonte</div></div><div class="prest-agenda-font-body modal-body"><div class="prest-agenda-font-top"><div class="prest-agenda-font-col"><label for="prest-agenda-fonte-family-input">Fonte:</label><input id="prest-agenda-fonte-family-input" type="text"><select id="prest-agenda-fonte-family" size="8"><option>MS Sans Serif</option><option>MS Serif</option><option>Arial</option><option>Tahoma</option><option>Verdana</option><option>Times New Roman</option><option>Courier New</option><option>Segoe UI</option></select></div><div class="prest-agenda-font-col"><label for="prest-agenda-fonte-style-input">Estilo da fonte:</label><input id="prest-agenda-fonte-style-input" type="text"><select id="prest-agenda-fonte-style" size="8"><option>Regular</option><option>Oblíquo</option><option>Negrito</option><option>Oblíquo e negrito</option></select></div><div class="prest-agenda-font-col"><label for="prest-agenda-fonte-size-input">Tamanho:</label><input id="prest-agenda-fonte-size-input" type="text"><select id="prest-agenda-fonte-size" size="8"><option>8</option><option>10</option><option>12</option><option>14</option><option>15</option><option>17</option><option>18</option></select></div><div class="prest-agenda-font-actions"><button id="prest-agenda-fonte-ok-top" class="btn-primary" type="button">OK</button><button id="prest-agenda-fonte-cancelar-top" class="btn" type="button">Cancelar</button></div></div><div class="prest-agenda-font-bottom"><div class="prest-agenda-font-box"><h5>Efeitos</h5><label class="prest-agenda-font-effect"><input id="prest-agenda-fonte-strike" type="checkbox"><span>Riscado</span></label><label class="prest-agenda-font-effect"><input id="prest-agenda-fonte-underline" type="checkbox"><span>Sublinhado</span></label><div class="prest-agenda-font-color"><label for="prest-agenda-fonte-color">Cor:</label><span id="prest-agenda-fonte-color-swatch" class="prest-agenda-apres-swatch"></span><select id="prest-agenda-fonte-color"><option value="#000000">Preto</option><option value="#800000">Bordô</option><option value="#008000">Verde</option><option value="#808000">Verde-oliva</option><option value="#000080">Azul-marinho</option><option value="#800080">Roxo</option><option value="#008080">Azul-petróleo</option><option value="#808080">Cinza</option><option value="#c0c0c0">Prateado</option><option value="#ff0000">Vermelho</option><option value="#00ff00">Verde-limão</option><option value="#ffff00">Amarelo</option><option value="#0000ff">Azul</option><option value="#ff00ff">Fúcsia</option><option value="#00ffff">Azul-piscina</option><option value="#ffffff">Branco</option></select></div></div><div><div class="prest-agenda-font-box"><h5>Exemplo</h5><div id="prest-agenda-fonte-sample" class="prest-agenda-font-sample">AaBbYyZz</div></div><div class="prest-agenda-font-script"><label for="prest-agenda-fonte-script">Script:</label><select id="prest-agenda-fonte-script"><option>Ocidental</option></select></div></div></div><div class="modal-actions"><button id="prest-agenda-fonte-ok" class="btn-primary" type="button">Ok</button><button id="prest-agenda-fonte-cancelar" class="btn" type="button">Cancelar</button></div></div></div></div>`)
}
if(!prestCfg.agendaFonteModal){
prestCfg.agendaFonteModal={backdrop:document.getElementById("prest-agenda-fonte-backdrop"),familyInput:document.getElementById("prest-agenda-fonte-family-input"),family:document.getElementById("prest-agenda-fonte-family"),styleInput:document.getElementById("prest-agenda-fonte-style-input"),style:document.getElementById("prest-agenda-fonte-style"),sizeInput:document.getElementById("prest-agenda-fonte-size-input"),size:document.getElementById("prest-agenda-fonte-size"),strike:document.getElementById("prest-agenda-fonte-strike"),underline:document.getElementById("prest-agenda-fonte-underline"),colorSwatch:document.getElementById("prest-agenda-fonte-color-swatch"),color:document.getElementById("prest-agenda-fonte-color"),sample:document.getElementById("prest-agenda-fonte-sample"),script:document.getElementById("prest-agenda-fonte-script"),ok:document.getElementById("prest-agenda-fonte-ok"),cancelar:document.getElementById("prest-agenda-fonte-cancelar"),okTop:document.getElementById("prest-agenda-fonte-ok-top"),cancelarTop:document.getElementById("prest-agenda-fonte-cancelar-top")};
const modalEl=prestCfg.agendaFonteModal.backdrop.querySelector(".prest-agenda-font-modal");
if(modalEl)ensureModalChrome(modalEl);
const m=prestCfg.agendaFonteModal;
if(m.family&&!m.family.dataset.boundSync){m.family.dataset.boundSync="1";m.family.addEventListener("change",prestAgendaFontePreviewSync)}
if(m.style&&!m.style.dataset.boundSync){m.style.dataset.boundSync="1";m.style.addEventListener("change",prestAgendaFontePreviewSync)}
if(m.size&&!m.size.dataset.boundSync){m.size.dataset.boundSync="1";m.size.addEventListener("change",prestAgendaFontePreviewSync)}
if(m.strike&&!m.strike.dataset.boundSync){m.strike.dataset.boundSync="1";m.strike.addEventListener("change",prestAgendaFontePreviewSync)}
if(m.underline&&!m.underline.dataset.boundSync){m.underline.dataset.boundSync="1";m.underline.addEventListener("change",prestAgendaFontePreviewSync)}
if(m.color&&!m.color.dataset.boundSync){m.color.dataset.boundSync="1";m.color.addEventListener("change",prestAgendaFontePreviewSync)}
if(m.script&&!m.script.dataset.boundSync){m.script.dataset.boundSync="1";m.script.addEventListener("change",prestAgendaFontePreviewSync)}
if(m.ok&&!m.ok.dataset.boundSave){m.ok.dataset.boundSave="1";m.ok.addEventListener("click",prestAgendaFonteSalvar)}
if(m.okTop&&!m.okTop.dataset.boundSave){m.okTop.dataset.boundSave="1";m.okTop.addEventListener("click",prestAgendaFonteSalvar)}
if(m.cancelar&&!m.cancelar.dataset.boundClose){m.cancelar.dataset.boundClose="1";m.cancelar.addEventListener("click",prestAgendaFonteFechar)}
if(m.cancelarTop&&!m.cancelarTop.dataset.boundClose){m.cancelarTop.dataset.boundClose="1";m.cancelarTop.addEventListener("click",prestAgendaFonteFechar)}
if(m.backdrop&&!m.backdrop.dataset.boundClose){m.backdrop.dataset.boundClose="1";m.backdrop.addEventListener("click",ev=>{if(ev.target===m.backdrop)prestAgendaFonteFechar()})}
}
prestCfg.agenda.apresFonteState=prestCfg.agenda.apresFonteState||{family:"MS Sans Serif",size:8,bold:false,italic:false,underline:false,strike:false,color:"#000000",script:"Ocidental"};
prestAgendaApresPreviewSync()
}
function prestAgendaEnhanceVisualizacao(){if(!prestCfg?.agenda)return;const pane=prestCfg.agenda.panes.find(item=>item.dataset.tab==="visualizacao");if(!pane)return;if(!document.getElementById("prest-agenda-vis-style")){const style=document.createElement("style");style.id="prest-agenda-vis-style";style.textContent=".prest-agenda-vis-wrap{border:1px solid #bfc9d6;background:#fff;min-height:170px;padding:8px 10px;box-sizing:border-box}.prest-agenda-vis-title{display:block;margin:0 0 4px;font:12px Tahoma,sans-serif}.prest-agenda-vis-list{display:grid;grid-template-columns:1fr;gap:1px;align-content:start}.prest-agenda-vis-item{display:flex;align-items:center;gap:5px;margin:0;font:12px Tahoma,sans-serif;line-height:1.05}.prest-agenda-vis-item input{width:13px;height:13px;margin:0}.prest-agenda-vis-hidden{display:none!important}";document.head.appendChild(style)}if(!pane.dataset.visualizacaoEnhanced){const oldTextarea=pane.querySelector("#prest-agenda-visualizacao");const oldValue=oldTextarea?String(oldTextarea.value||""):"";const hasChecklist=!!pane.querySelector("#prest-agenda-vis-list");if(!hasChecklist){pane.innerHTML=prestAgendaVisualizacaoHtml();const hiddenTextarea=pane.querySelector("#prest-agenda-visualizacao");if(hiddenTextarea)hiddenTextarea.value=oldValue}pane.dataset.visualizacaoEnhanced="1";pane.dataset.enhanced="1"}prestCfg.agenda.visualizacao=pane.querySelector("#prest-agenda-visualizacao");prestCfg.agenda.visualizacaoChecks=[...pane.querySelectorAll('.prest-agenda-vis-item input[type=\"checkbox\"]')]}
function prestAgendaEnhanceBloqueios(){
if(!prestCfg?.agenda)return;
const pane=prestCfg.agenda.panes.find(item=>item.dataset.tab==="bloqueios");
if(!pane||pane.dataset.enhanced==="1")return;
const style=document.createElement("style");
style.textContent=".prest-agenda-block-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px}.prest-agenda-block-grid{border:1px solid #cfd8e3;background:#fff;min-height:210px}.prest-agenda-block-grid table{width:100%;border-collapse:collapse;table-layout:fixed}.prest-agenda-block-grid th,.prest-agenda-block-grid td{border-bottom:1px solid #edf1f6;padding:3px 6px;height:22px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.prest-agenda-block-grid th{background:#f2f6fb;font:700 12px Tahoma,sans-serif;text-align:left}.prest-agenda-block-grid tr.selected{background:#d9e8fb}.prest-agenda-block-modal .modal-body{display:flex;flex-direction:column;gap:10px}.prest-agenda-block-row{display:flex;gap:10px;align-items:end}.prest-agenda-block-field{display:flex;flex-direction:column;gap:2px;flex:1}.prest-agenda-block-field input,.prest-agenda-block-field select,.prest-agenda-block-field textarea{border:1px solid #bfc9d6;padding:0 6px;font:12px Tahoma,sans-serif}.prest-agenda-block-field input,.prest-agenda-block-field select{height:24px}.prest-agenda-block-field textarea{height:90px;padding:6px;resize:none}";
document.head.appendChild(style);
pane.innerHTML=`<div class="prest-agenda-block-toolbar"><button id="prest-agenda-bloq-novo" class="materiais-btn" type="button"><img src="/desktop-assets/novo.png" alt="">Novo bloqueio...</button><button id="prest-agenda-bloq-editar" class="materiais-btn" type="button"><img src="/desktop-assets/editar.png" alt="">Altera...</button><button id="prest-agenda-bloq-excluir" class="materiais-btn" type="button"><img src="/desktop-assets/eliminar.png" alt="">Elimina</button></div><div class="prest-agenda-block-grid"><table><colgroup><col><col style="width:90px"><col style="width:160px"><col style="width:90px"><col style="width:90px"></colgroup><thead><tr><th>Unidade</th><th>Dia</th><th>Vigência</th><th>Início</th><th>Final</th></tr></thead><tbody id="prest-agenda-bloq-tbody"></tbody></table></div>`;
const oldBackdrop=document.getElementById("prest-agenda-bloqueio-backdrop");
if(oldBackdrop)oldBackdrop.remove();
document.body.insertAdjacentHTML("beforeend",`<div id="prest-agenda-bloqueio-backdrop" class="modal-backdrop hidden"><div class="modal prest-agenda-block-modal" style="width:560px;max-width:calc(100vw - 24px)"><div class="modal-header"><div id="prest-agenda-bloqueio-title" class="modal-title">Novo bloqueio</div></div><div class="modal-body"><div class="prest-agenda-block-field"><label>Unidade de atendimento:</label><select id="prest-agenda-bloqueio-unidade"><option>Instituto Brana - Odontologia</option><option>Clínica</option><option>Consultório 1</option><option>Consultório 2</option></select></div><div class="prest-agenda-block-row" style="gap:8px"><div class="prest-agenda-block-field" style="flex:0 0 116px"><label>Dia da semana:</label><select id="prest-agenda-bloqueio-dia"><option>Segunda</option><option>Terça</option><option>Quarta</option><option>Quinta</option><option>Sexta</option><option>Sábado</option><option>Domingo</option></select></div><div class="prest-agenda-block-field" style="flex:0 0 198px"><label>Período de vigência:</label><div style="display:grid;grid-template-columns:84px 12px 84px;gap:4px;align-items:center"><input id="prest-agenda-bloqueio-vigencia-inicio" type="text"><span style="text-align:center">a</span><input id="prest-agenda-bloqueio-vigencia-fim" type="text"></div></div><div class="prest-agenda-block-field" style="flex:0 0 154px;margin-left:auto"><label>Intervalo de horário:</label><div style="display:grid;grid-template-columns:68px 12px 68px;gap:4px;align-items:center"><input id="prest-agenda-bloqueio-inicio" type="text"><span style="text-align:center">às</span><input id="prest-agenda-bloqueio-final" type="text"></div></div></div><div class="prest-agenda-block-field"><label>Mensagem de alerta:</label><textarea id="prest-agenda-bloqueio-mensagem"></textarea></div></div><div class="modal-actions"><button id="prest-agenda-bloqueio-ok" class="btn-primary" type="button">Ok</button><button id="prest-agenda-bloqueio-cancelar" class="btn" type="button">Cancela</button></div></div></div>`);
prestCfg.agenda.bloqueiosTbody=document.getElementById("prest-agenda-bloq-tbody");
prestCfg.agenda.bloqueioSelId=null;
prestCfg.agendaBloqueioModal={backdrop:document.getElementById("prest-agenda-bloqueio-backdrop"),title:document.getElementById("prest-agenda-bloqueio-title"),unidade:document.getElementById("prest-agenda-bloqueio-unidade"),dia:document.getElementById("prest-agenda-bloqueio-dia"),vigenciaInicio:document.getElementById("prest-agenda-bloqueio-vigencia-inicio"),vigenciaFim:document.getElementById("prest-agenda-bloqueio-vigencia-fim"),inicio:document.getElementById("prest-agenda-bloqueio-inicio"),final:document.getElementById("prest-agenda-bloqueio-final"),mensagem:document.getElementById("prest-agenda-bloqueio-mensagem"),ok:document.getElementById("prest-agenda-bloqueio-ok"),cancelar:document.getElementById("prest-agenda-bloqueio-cancelar"),editId:null};
const bloqModalEl=prestCfg.agendaBloqueioModal.backdrop.querySelector(".prest-agenda-block-modal");
if(bloqModalEl)ensureModalChrome(bloqModalEl);
bindStandardGridActivation(prestCfg.agenda.bloqueiosTbody,tr=>prestAgendaBloqueiosSelecionar(tr),()=>prestAgendaBloqueioAbrirModal("editar"));
document.getElementById("prest-agenda-bloq-novo").addEventListener("click",()=>prestAgendaBloqueioAbrirModal("novo"));
document.getElementById("prest-agenda-bloq-editar").addEventListener("click",()=>prestAgendaBloqueioAbrirModal("editar"));
document.getElementById("prest-agenda-bloq-excluir").addEventListener("click",prestAgendaBloqueioExcluir);
prestCfg.agendaBloqueioModal.ok.addEventListener("click",prestAgendaBloqueioSalvar);
prestCfg.agendaBloqueioModal.cancelar.addEventListener("click",prestAgendaBloqueioFecharModal);
prestCfg.agendaBloqueioModal.backdrop.addEventListener("click",ev=>{if(ev.target===prestCfg.agendaBloqueioModal.backdrop)prestAgendaBloqueioFecharModal()});
pane.dataset.enhanced="1"}
function prestAgendaEnsureUI(){
if(prestCfg?.agenda)return;
const style=document.createElement("style");
style.textContent=".prest-agenda-modal{width:min(520px,96vw);background:#f5f5f3;border:1px solid #c8ced8;box-sizing:border-box;font:12px Tahoma,sans-serif}.prest-agenda-body{padding:10px 12px 12px}.prest-agenda-tabs{display:flex;gap:4px;margin-bottom:10px}.prest-agenda-tab{height:28px;padding:0 12px;border:1px solid #bfc9d6;border-bottom:none;background:#ececec;font:12px Tahoma,sans-serif;cursor:pointer}.prest-agenda-tab.active{background:#fff;font-weight:700}.prest-agenda-pane{border:1px solid #bfc9d6;background:#fff;padding:10px;min-height:268px}.prest-agenda-pane.hidden{display:none}.prest-agenda-layout{display:grid;grid-template-columns:1fr 1fr;gap:14px}.prest-agenda-group{border:1px solid #bfc9d6;padding:10px;background:#fafafa}.prest-agenda-group h4{margin:0 0 8px;font:700 12px Tahoma,sans-serif}.prest-agenda-fields{display:grid;grid-template-columns:1fr auto;gap:8px 10px;align-items:center}.prest-agenda-fields label{white-space:nowrap}.prest-agenda-fields input,.prest-agenda-fields select,.prest-agenda-pane textarea{height:24px;border:1px solid #bfc9d6;padding:0 6px;box-sizing:border-box;background:#fff;font:12px Tahoma,sans-serif}.prest-agenda-pane textarea{width:100%;height:208px;padding:6px;resize:none}.prest-agenda-mini{display:grid;grid-template-columns:1fr auto auto;gap:8px 8px;align-items:center}.prest-agenda-mini input{width:56px;text-align:center}.prest-agenda-actions{display:flex;justify-content:flex-end;gap:8px;padding-top:10px}.prest-agenda-actions .materiais-btn{min-width:86px;justify-content:center}";
document.head.appendChild(style);
document.body.insertAdjacentHTML("beforeend",`<div id="prest-agenda-backdrop" class="modal-backdrop hidden"><div class="modal prest-agenda-modal"><div class="modal-header"><div id="prest-agenda-title" class="modal-title">Configura horários de agendamento</div></div><div class="prest-agenda-body"><div class="prest-agenda-tabs"><button data-tab="escala" class="prest-agenda-tab active" type="button">Escala</button><button data-tab="bloqueios" class="prest-agenda-tab" type="button">Bloqueios</button><button data-tab="apresentacao" class="prest-agenda-tab" type="button">Apresentação</button><button data-tab="visualizacao" class="prest-agenda-tab" type="button">Visualização</button></div><section data-tab="escala" class="prest-agenda-pane"><div class="prest-agenda-layout"><div><div class="prest-agenda-group" style="margin-bottom:12px"><h4>Manhã</h4><div class="prest-agenda-fields"><label for="prest-agenda-manha-inicio">Horário inicial..........</label><input id="prest-agenda-manha-inicio" type="text"><label for="prest-agenda-manha-fim">Horário final............</label><input id="prest-agenda-manha-fim" type="text"></div></div><div class="prest-agenda-group"><h4>Tarde</h4><div class="prest-agenda-fields"><label for="prest-agenda-tarde-inicio">Horário inicial..........</label><input id="prest-agenda-tarde-inicio" type="text"><label for="prest-agenda-tarde-fim">Horário final............</label><input id="prest-agenda-tarde-fim" type="text"></div></div></div><div><div class="prest-agenda-group" style="margin-bottom:12px"><h4>Duração do horário</h4><div class="prest-agenda-mini"><span></span><input id="prest-agenda-duracao" type="number" min="5" step="5"><span>minutos</span></div></div><div class="prest-agenda-group"><h4>Visualizar horários</h4><div class="prest-agenda-mini" style="margin-bottom:8px"><label for="prest-agenda-semana">Agenda da semana:</label><input id="prest-agenda-semana" type="number" min="1" step="1"><span>horários</span></div><div class="prest-agenda-mini"><label for="prest-agenda-dia">Agenda do dia:</label><input id="prest-agenda-dia" type="number" min="1" step="1"><span>horários</span></div></div></div></div></section><section data-tab="bloqueios" class="prest-agenda-pane hidden"><textarea id="prest-agenda-bloqueios" placeholder="Observações e regras de bloqueio deste prestador."></textarea></section><section data-tab="apresentacao" class="prest-agenda-pane hidden"><textarea id="prest-agenda-apresentacao" placeholder="Preferências de apresentação da agenda."></textarea></section><section data-tab="visualizacao" class="prest-agenda-pane hidden">${prestAgendaVisualizacaoHtml()}</section><div class="prest-agenda-actions"><button id="prest-agenda-ok" class="materiais-btn" type="button"><img src="/desktop-assets/gravar.png" alt="">Ok</button><button id="prest-agenda-cancelar" class="materiais-btn" type="button"><img src="/desktop-assets/cancela.png" alt="">Cancela</button></div></div></div></div>`);
prestCfg.agenda={backdrop:document.getElementById("prest-agenda-backdrop"),modal:document.querySelector("#prest-agenda-backdrop .prest-agenda-modal"),title:document.getElementById("prest-agenda-title"),tabs:[...document.querySelectorAll("#prest-agenda-backdrop .prest-agenda-tab")],panes:[...document.querySelectorAll("#prest-agenda-backdrop .prest-agenda-pane")],manhaInicio:document.getElementById("prest-agenda-manha-inicio"),manhaFim:document.getElementById("prest-agenda-manha-fim"),tardeInicio:document.getElementById("prest-agenda-tarde-inicio"),tardeFim:document.getElementById("prest-agenda-tarde-fim"),duracao:document.getElementById("prest-agenda-duracao"),semana:document.getElementById("prest-agenda-semana"),dia:document.getElementById("prest-agenda-dia"),bloqueios:document.getElementById("prest-agenda-bloqueios"),apresentacao:document.getElementById("prest-agenda-apresentacao"),visualizacao:document.getElementById("prest-agenda-visualizacao"),visualizacaoChecks:[...document.querySelectorAll('#prest-agenda-backdrop [data-tab="visualizacao"] .prest-agenda-vis-item input[type="checkbox"]')],ok:document.getElementById("prest-agenda-ok"),cancelar:document.getElementById("prest-agenda-cancelar"),editId:null,tabAtual:"escala"};
const visPane=prestCfg.agenda.panes.find(pane=>pane.dataset.tab==="visualizacao");
if(visPane){visPane.dataset.visualizacaoEnhanced="1";visPane.dataset.enhanced="1"}
ensureModalChrome(prestCfg.agenda.modal);
const bindEscalaHora=input=>{
if(!(input instanceof HTMLInputElement)||input.dataset.boundEscalaHora==="1")return;
input.dataset.boundEscalaHora="1";
input.inputMode="numeric";
input.maxLength=5;
const aplicarMascara=()=>{
const digits=String(input.value||"").replace(/\D+/g,"").slice(0,4);
if(digits.length>=3){input.value=`${digits.slice(0,2)}:${digits.slice(2)}`;return}
input.value=digits;
};
input.addEventListener("beforeinput",ev=>{
if(ev.inputType!=="insertText")return;
const txt=String(ev.data||"");
if(!txt)return;
if(/[^0-9]/.test(txt))ev.preventDefault();
});
input.addEventListener("input",aplicarMascara);
input.addEventListener("blur",()=>{
aplicarMascara();
const raw=String(input.value||"").trim();
if(!raw)return;
const normal=prestAgendaNormalizarHoraEscala(raw);
if(normal)input.value=normal;
});
};
[prestCfg.agenda.manhaInicio,prestCfg.agenda.manhaFim,prestCfg.agenda.tardeInicio,prestCfg.agenda.tardeFim].forEach(bindEscalaHora);
prestCfg.agenda.tabs.forEach(btn=>btn.addEventListener("click",()=>prestAgendaTab(btn.dataset.tab||"escala")));
prestCfg.agenda.ok.addEventListener("click",prestAgendaSalvar);
prestCfg.agenda.cancelar.addEventListener("click",prestAgendaFechar);
prestCfg.agenda.backdrop.addEventListener("click",ev=>{if(ev.target===prestCfg.agenda.backdrop)prestAgendaFechar()})
}
let prestAgendaElegiveisCache=[];
let prestAgendaElegiveisCacheTs=0;
async function prestAgendaCarregarElegiveis(force=false){const now=Date.now();if(!force&&Array.isArray(prestAgendaElegiveisCache)&&prestAgendaElegiveisCache.length&&(now-prestAgendaElegiveisCacheTs)<30000)return prestAgendaElegiveisCache;try{const{res,data}=await requestJson("GET","/agenda-legado/prestadores",undefined,true);if(res?.ok&&Array.isArray(data)){prestAgendaElegiveisCache=data;prestAgendaElegiveisCacheTs=now;return prestAgendaElegiveisCache}}catch{}prestAgendaElegiveisCache=[];prestAgendaElegiveisCacheTs=now;return prestAgendaElegiveisCache}
function prestPrestadorTemUsuarioAssociado(item,elegiveis=null){const id=Number(item?.id||0)||0;if(!id)return false;const lista=Array.isArray(elegiveis)?elegiveis:[];if(lista.length)return lista.some(x=>Number(x?.id||0)===id);const usuarioId=Number(item?.usuario_id??item?.user_id??item?.id_usuario??0)||0;return usuarioId>0}
async function prestAgendaAbrir(){let item=prestSelecionado();if(!item){const lista=Array.isArray(prestadoresCache)?prestadoresCache:[];const sessaoPrestId=Number(sessaoAtual?.prestador_id||0)||0;const sessaoUserId=Number(sessaoAtual?.user_id||sessaoAtual?.id||0)||0;let alvo=null;if(sessaoPrestId)alvo=lista.find(x=>Number(x?.id||0)===sessaoPrestId)||null;if(!alvo&&sessaoUserId)alvo=lista.find(x=>Number(x?.usuario_id||0)===sessaoUserId)||null;if(!alvo&&sessaoUserId)alvo=lista.find(x=>Number(x?.source_id||0)===sessaoUserId)||null;if(alvo){prestadorSelId=Number(alvo.id||0)||null;if(typeof prestRender==="function")prestRender();item=prestSelecionado()}}if(!item){window.alert("Selecione um prestador.");return}const elegiveis=await prestAgendaCarregarElegiveis();if(!prestPrestadorTemUsuarioAssociado(item,elegiveis)){window.alert("Não existe usuário associado ao prestador.");return}prestEnsureUI();prestAgendaEnsureUI();prestAgendaEnhanceBloqueios();prestAgendaEnhanceApresentacao();prestAgendaEnhanceVisualizacao();const a=prestCfg.agenda;const estado=prestAgendaNovoEstado(item);a.editId=Number(item.id||0)||null;a.title.textContent=`Configura horários de agendamento (${item.nome||"Prestador"})`;a.manhaInicio.value=estado.manha_inicio;a.manhaFim.value=estado.manha_fim;a.tardeInicio.value=estado.tarde_inicio;a.tardeFim.value=estado.tarde_fim;a.duracao.value=estado.duracao;a.semana.value=estado.semana_horarios;a.dia.value=estado.dia_horarios;if(a.bloqueios)a.bloqueios.value=estado.bloqueios_obs;if(a.apresentacao)a.apresentacao.value=estado.apresentacao_obs;a.visualizacao.value=estado.visualizacao_obs;a.bloqueioSelId=null;if(a.apresParticular)a.apresParticular.value=estado.apresentacao_particular_cor;if(a.apresConvenio)a.apresConvenio.value=estado.apresentacao_convenio_cor;if(a.apresCompromisso)a.apresCompromisso.value=estado.apresentacao_compromisso_cor;a.apresFonteState={...estado.apresentacao_fonte};if(Array.isArray(a.visualizacaoChecks))a.visualizacaoChecks.forEach(chk=>chk.checked=estado.visualizacao_campos.includes(chk.value));prestAgendaBloqueiosRender();prestAgendaApresPreviewSync();if(a.swatchParticular)a.swatchParticular.style.background=a.apresParticular.value;if(a.swatchConvenio)a.swatchConvenio.style.background=a.apresConvenio.value;if(a.swatchCompromisso)a.swatchCompromisso.style.background=a.apresCompromisso.value;prestAgendaTab("escala");a.backdrop.classList.remove("hidden")}
async function prestCredCarregarConvenios(){try{const{res,data}=await requestJson("GET","/cadastros/convenios-planos/combos",undefined,true);if(res.ok)return Array.isArray(data?.convenios)?data.convenios:[]}catch{}return[]}
async function prestCredCarregarItens(){try{const{res,data}=await requestJson("GET","/cadastros/prestadores/credenciamentos",undefined,true);if(res.ok&&Array.isArray(data?.itens))return data.itens}catch{}return[]}
function prestCredConvenioAtual(){return String(prestCredCfg?.cboConvenio?.value||"").trim()}
function prestCredPrestadorAtual(){return String(prestCredCfg?.cboPrestador?.value||"").trim()}
function prestCredFiltrar(){const convenio=prestCredConvenioAtual();const prestador=prestCredPrestadorAtual();return prestCredItens.filter(item=>(!convenio||convenio==="__todos__"||String(item.convenio_row_id||"")===convenio)&&(!prestador||prestador==="__todos__"||String(item.prestador_id||"")===prestador))}
function prestCredRender(){if(!prestCredCfg)return;const lista=prestCredFiltrar();prestCredCfg.tbody.innerHTML=lista.map(item=>`<tr data-id="${item.id}" class="${Number(item.id||0)===Number(prestCredSelId)?"selected":""}"><td>${esc(String(item.codigo||""))}</td><td>${esc(String(item.prestador_nome||""))}</td><td>${esc(String(item.convenio_nome||""))}</td><td>${esc(String(item.inicio||""))}</td><td>${esc(String(item.fim||""))}</td><td style="text-align:right">${esc(String(item.valor_us||""))}</td></tr>`).join("")||'<tr><td colspan="6">Nenhum credenciamento encontrado.</td></tr>';prestCredCfg.total.textContent=`${lista.length} credenciamentos   Duplo-clique para alterar o credenciamento desejado`}
function prestCredSelecionarLinha(tr){prestCredSelId=Number(tr?.dataset.id||0)||null;prestCredRender()}
function prestCredAtualizarCombos(prestadorId){if(!prestCredCfg)return;prestCredCfg.cboConvenio.innerHTML=['<option value="__todos__">&lt;&lt;Todos&gt;&gt;</option>',...prestCredConvenios.map(item=>`<option value="${esc(String(item.row_id||item.id||""))}">${esc(String(item.nome||""))}</option>`)].join("");prestCredCfg.cboPrestador.innerHTML=['<option value="__todos__">&lt;&lt;Todos&gt;&gt;</option>',...prestadoresCache.map(item=>`<option value="${esc(String(item.id||""))}">${esc(String(item.nome||""))}</option>`)].join("");prestCredCfg.cboConvenio.value="__todos__";prestCredCfg.cboPrestador.value=prestadorId?String(prestadorId):"__todos__"}
function prestCredApplyFineLayout(){if(document.getElementById("prest-cred-fine-style"))return;const style=document.createElement("style");style.id="prest-cred-fine-style";style.textContent=`
#prest-cred-modal-backdrop .prest-cred-modal{width:min(500px,95vw)}
#prest-cred-modal-backdrop .prest-cred-modal-body{padding:8px 10px 10px}
#prest-cred-modal-backdrop .prest-cred-tabs{gap:3px;margin-bottom:8px}
#prest-cred-modal-backdrop .prest-cred-tab{height:24px;padding:0 10px}
#prest-cred-modal-backdrop .prest-cred-pane{padding:8px;min-height:196px;overflow:hidden}
#prest-cred-modal-backdrop .prest-cred-modal-grid{grid-template-columns:150px minmax(0,1fr);gap:6px 10px}
#prest-cred-modal-backdrop .prest-cred-modal-grid>div{min-width:0}
#prest-cred-modal-backdrop .prest-cred-modal-grid .span-2{grid-column:1 / -1}
#prest-cred-modal-backdrop .prest-cred-modal-grid input,
#prest-cred-modal-backdrop .prest-cred-modal-grid select{height:22px;padding:0 5px;width:100%;max-width:100%;min-width:0;box-sizing:border-box}
#prest-cred-modal-backdrop .prest-cred-modal-row{grid-template-columns:90px 14px 90px minmax(90px,1fr);gap:6px;align-items:end;min-width:0}
#prest-cred-modal-backdrop .prest-cred-modal-row input{height:22px;width:100%;max-width:100%;min-width:0;box-sizing:border-box}
#prest-cred-modal-backdrop .prest-cred-modal-info{gap:8px;margin-top:8px}
#prest-cred-modal-backdrop .prest-cred-modal-info input{height:22px}
#prest-cred-modal-backdrop .prest-cred-modal-actions{padding-top:8px;gap:8px}
#prest-cred-modal-backdrop .prest-cred-modal-actions .materiais-btn{min-width:80px;height:28px}
`;document.head.appendChild(style)}
async function prestCredAbrir(){prestEnsureUI();prestCredEnsureUI();prestCredApplyFineLayout();prestCredNormalizarTextos();prestCredNormalizarTextosV2();hideAllPanels();prestCredCfg.panel.classList.remove("hidden");workspaceEmpty.classList.add("hidden");ensurePanelChrome(prestCredCfg.panel);prestCredConvenios=await prestCredCarregarConvenios();prestCredItens=await prestCredCarregarItens();const prestador=prestSelecionado();prestCredAtualizarCombos(prestador?.id||null);prestCredRender();footerMsg.textContent="Cadastro > Credenciamentos aberto."}
function prestCredAtual(){return prestCredItens.find(item=>Number(item.id||0)===Number(prestCredSelId))||null}
function prestCredNovoCodigo(){const max=prestCredItens.reduce((acc,item)=>Math.max(acc,Number(item.codigo||0)||0),0);return String(max+1).padStart(4,"0")}
function prestCredFecharModal(){if(prestCredCfg?.modal?.backdrop)prestCredCfg.modal.backdrop.classList.add("hidden")}
function prestCredTabs(tab){if(!prestCredCfg?.modal)return;prestCredCfg.modal.tabs.forEach(btn=>btn.classList.toggle("active",btn.dataset.tab===tab));prestCredCfg.modal.panes.forEach(pane=>pane.classList.toggle("hidden",pane.dataset.tab!==tab));prestCredCfg.modal.tabAtual=tab;prestCredNormalizarTextos();prestCredNormalizarTextosV2()}
function prestCredNormalizarTextos(){
if(!prestCredCfg)return;
const fix=(txt)=>{
let t=String(txt||"");
t=t
.replaceAll("Convênio","Convênio")
.replaceAll("Código","Código")
.replaceAll("Início","Início")
.replaceAll("Vigência","Vigência")
.replaceAll("Inclusão","Inclusão")
.replaceAll("Alteração","Alteração")
.replaceAll("Observações","Observações")
.replaceAll("ConvÃƒªnio","Convênio")
.replaceAll("Código","Código")
.replaceAll("Início","Início")
.replaceAll("VigÃƒªncia","Vigência")
.replaceAll("Inclusão","Inclusão")
.replaceAll("Alteração","Alteração")
.replaceAll("Observações","Observações");
return t;
};
const p=prestCredCfg.panel;
if(p){
p.querySelectorAll("label,th,.panel-title,button").forEach(el=>{
const n=fix(el.textContent);
if(n!==el.textContent)el.textContent=n;
});
}
const m=prestCredCfg.modal?.modal;
if(m){
m.querySelectorAll("label,button,.modal-title").forEach(el=>{
const n=fix(el.textContent);
if(n!==el.textContent)el.textContent=n;
});
}
}
function prestCredParseObsComAlerta(texto){const bruto=String(texto||"");const m=bruto.match(/^\[ALERTA\]\s*\n([\s\S]*?)\n\[OBS\]\s*\n([\s\S]*)$/);if(!m)return{alerta:"",obs:bruto};return{alerta:String(m[1]||"").trim(),obs:String(m[2]||"").trim()}}
function prestCredMontarObsComAlerta(alerta,obs){const a=String(alerta||"").trim();const o=String(obs||"").trim();if(!a)return o;return`[ALERTA]\n${a}\n[OBS]\n${o}`}
function prestCredGarantirCamposDetalhes(){if(!prestCredCfg?.modal)return;const pane=prestCredCfg.modal.panes.find(p=>p.dataset.tab==="detalhes");if(!pane)return;const alertaAtual=String((pane.querySelector("#prest-cred-modal-alerta")||{}).value||"");const obsAtual=String((pane.querySelector("#prest-cred-modal-obs")||{}).value||"");pane.innerHTML='<label id="prest-cred-modal-alerta-label">Alerta para atendimentos:</label><textarea id="prest-cred-modal-alerta"></textarea><label id="prest-cred-modal-obs-label">Observações:</label><textarea id="prest-cred-modal-obs"></textarea>';const alerta=pane.querySelector("#prest-cred-modal-alerta");const obs=pane.querySelector("#prest-cred-modal-obs");if(alerta)alerta.value=alertaAtual;if(obs)obs.value=obsAtual;prestCredCfg.modal.alerta=alerta;prestCredCfg.modal.obs=obs}
function prestCredNormalizarTextosV2(){if(!prestCredCfg)return;prestCredGarantirCamposDetalhes();const pane=prestCredCfg.modal?.panes?.find(p=>p.dataset.tab==="detalhes");if(pane&&!document.getElementById("prest-cred-detalhes-fine-style")){const style=document.createElement("style");style.id="prest-cred-detalhes-fine-style";style.textContent='#prest-cred-modal-backdrop .prest-cred-modal-detalhes{display:grid;grid-template-rows:auto 74px auto 74px;gap:6px}#prest-cred-modal-backdrop .prest-cred-modal-detalhes textarea{height:74px!important;padding:6px;resize:none}';document.head.appendChild(style)}}
async function prestCredExcluirSelecionado(){const item=prestCredAtual();if(!item){window.alert("Selecione um credenciamento.");return}if(!window.confirm(`Deseja eliminar o credenciamento ${item.codigo} ?`))return;try{const{res,data}=await requestJson("DELETE",`/cadastros/prestadores/credenciamentos/${Number(item.id||0)}`,undefined,true);if(!res.ok)throw new Error(String(data?.detail||"Falha ao eliminar credenciamento."));prestCredItens=prestCredItens.filter(row=>Number(row.id||0)!==Number(item.id||0));prestCredSelId=null;prestCredRender();footerMsg.textContent=`Credenciamento '${item.codigo}' eliminado.`}catch(err){window.alert(err?.message||"Não foi possível eliminar o credenciamento.")}}
function prestCredAbrirModal(modo){const item=modo==="editar"?prestCredAtual():null;if(modo==="editar"&&!item){window.alert("Selecione um credenciamento.");return}prestCredEnsureUI();prestCredApplyFineLayout();prestCredNormalizarTextos();prestCredNormalizarTextosV2();const m=prestCredCfg.modal;const base=item?JSON.parse(JSON.stringify(item)):{id:Date.now(),codigo:prestCredNovoCodigo(),convenio_row_id:prestCredConvenioAtual()==="__todos__"?"":prestCredConvenioAtual(),prestador_id:prestCredPrestadorAtual()==="__todos__"?String(prestSelecionado()?.id||"-1"):prestCredPrestadorAtual(),inicio:prestHojeBr(),fim:"",valor_us:"1,0000",inclusao:prestHojeBr(),alteracao:prestHojeBr(),obs:""};m.modo=modo;m.editId=item?Number(item.id||0):null;m.title.textContent=modo==="editar"?"Altera credenciamento":"Novo credenciamento";m.cboConvenio.innerHTML=prestCredConvenios.map(row=>`<option value="${esc(String(row.row_id||row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");m.cboPrestador.innerHTML=prestadoresCache.map(row=>`<option value="${esc(String(row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");m.codigo.value=String(base.codigo||"");m.cboConvenio.value=String(base.convenio_row_id||"");m.cboPrestador.value=String(base.prestador_id||"");m.inicio.value=prestDataBrFromAny(base.inicio)||prestHojeBr();m.fim.value=String(base.fim||"");m.valorUs.value=String(base.valor_us||"1,0000");m.inclusao.value=String(base.inclusao||prestHojeBr());m.alteracao.value=String(base.alteracao||prestHojeBr());const _obs=prestCredParseObsComAlerta(String(base.obs||base.observacoes||""));if(m.alerta)m.alerta.value=_obs.alerta;if(m.obs)m.obs.value=_obs.obs;prestCredTabs("principal");m.backdrop.classList.remove("hidden");prestCredNormalizarTextos();prestCredNormalizarTextosV2()}
async function prestCredSalvarModal(){if(!prestCredCfg?.modal)return;const m=prestCredCfg.modal;const convenioId=String(m.cboConvenio.value||"").trim();const prestadorId=String(m.cboPrestador.value||"").trim();if(!convenioId||!prestadorId){window.alert("Preencha conv?nio e prestador credenciado.");return}const _obs=prestCredMontarObsComAlerta(String(m.alerta?.value||""),String(m.obs.value||""));const payload={codigo:String(m.codigo.value||prestCredNovoCodigo()).trim()||prestCredNovoCodigo(),convenio_row_id:Number(convenioId||0),prestador_row_id:Number(prestadorId||0)>0?Number(prestadorId||0):null,inicio:String(m.inicio.value||"").trim(),fim:String(m.fim.value||"").trim(),valor_us:String(m.valorUs.value||"1,0000").trim()||"1,0000",observacoes:String(_obs||"").trim()};try{const editId=Number(m.editId||0);const endpoint=m.modo==="editar"?`/cadastros/prestadores/credenciamentos/${editId}`:"/cadastros/prestadores/credenciamentos";const method=m.modo==="editar"?"PUT":"POST";const{res,data}=await requestJson(method,endpoint,payload,true);if(!res.ok)throw new Error(String(data?.detail||"Falha ao gravar credenciamento."));const item=data||{};const idx=prestCredItens.findIndex(row=>Number(row.id||0)===Number(item.id||0));if(idx>=0)prestCredItens[idx]=item;else prestCredItens.push(item);prestCredSelId=Number(item.id||0)||null;prestCredRender();prestCredFecharModal();footerMsg.textContent=`Credenciamento '${item.codigo||""}' gravado.`}catch(err){window.alert(err?.message||"Não foi possível gravar o credenciamento.")}}

// Override da integração da aba Detalhes com separação nativa Easy: AVISO x OBSERV
function prestCredGarantirCamposDetalhes(){if(!prestCredCfg?.modal)return;const pane=prestCredCfg.modal.panes.find(p=>p.dataset.tab==="detalhes");if(!pane)return;const alertaAtual=String((pane.querySelector("#prest-cred-modal-alerta")||{}).value||"");const obsAtual=String((pane.querySelector("#prest-cred-modal-obs")||{}).value||"");pane.innerHTML='<label id="prest-cred-modal-alerta-label">Alerta para atendimentos:</label><textarea id="prest-cred-modal-alerta"></textarea><label id="prest-cred-modal-obs-label">Observações:</label><textarea id="prest-cred-modal-obs"></textarea>';const alerta=pane.querySelector("#prest-cred-modal-alerta");const obs=pane.querySelector("#prest-cred-modal-obs");if(alerta)alerta.value=alertaAtual;if(obs)obs.value=obsAtual;prestCredCfg.modal.alerta=alerta;prestCredCfg.modal.obs=obs}
function prestCredAbrirModal(modo){const item=modo==="editar"?prestCredAtual():null;if(modo==="editar"&&!item){window.alert("Selecione um credenciamento.");return}prestCredEnsureUI();prestCredApplyFineLayout();prestCredNormalizarTextos();prestCredNormalizarTextosV2();const m=prestCredCfg.modal;const base=item?JSON.parse(JSON.stringify(item)):{id:Date.now(),codigo:prestCredNovoCodigo(),convenio_row_id:prestCredConvenioAtual()==="__todos__"?"":prestCredConvenioAtual(),prestador_id:prestCredPrestadorAtual()==="__todos__"?String(prestSelecionado()?.id||"-1"):prestCredPrestadorAtual(),inicio:prestHojeBr(),fim:"",valor_us:"1,0000",inclusao:prestHojeBr(),alteracao:prestHojeBr(),obs:"",aviso:""};m.modo=modo;m.editId=item?Number(item.id||0):null;m.title.textContent=modo==="editar"?"Altera credenciamento":"Novo credenciamento";m.cboConvenio.innerHTML=prestCredConvenios.map(row=>`<option value="${esc(String(row.row_id||row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");m.cboPrestador.innerHTML=prestadoresCache.map(row=>`<option value="${esc(String(row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");m.codigo.value=String(base.codigo||"");m.cboConvenio.value=String(base.convenio_row_id||"");m.cboPrestador.value=String(base.prestador_id||"");m.inicio.value=prestDataBrFromAny(base.inicio)||prestHojeBr();m.fim.value=String(base.fim||"");m.valorUs.value=String(base.valor_us||"1,0000");m.inclusao.value=String(base.inclusao||prestHojeBr());m.alteracao.value=String(base.alteracao||prestHojeBr());const avisoDireto=String(base.aviso||base.alerta||"").trim();const _obs=avisoDireto?{alerta:avisoDireto,obs:String(base.obs||base.observacoes||"")} : prestCredParseObsComAlerta(String(base.obs||base.observacoes||""));if(m.alerta)m.alerta.value=_obs.alerta;if(m.obs)m.obs.value=_obs.obs;prestCredTabs("principal");m.backdrop.classList.remove("hidden");prestCredNormalizarTextos();prestCredNormalizarTextosV2()}
async function prestCredSalvarModal(){if(!prestCredCfg?.modal)return;const m=prestCredCfg.modal;const convenioId=String(m.cboConvenio.value||"").trim();const prestadorId=String(m.cboPrestador.value||"").trim();if(!convenioId||!prestadorId){window.alert("Preencha conv?nio e prestador credenciado.");return}const payload={codigo:String(m.codigo.value||prestCredNovoCodigo()).trim()||prestCredNovoCodigo(),convenio_row_id:Number(convenioId||0),prestador_row_id:Number(prestadorId||0)>0?Number(prestadorId||0):null,inicio:String(m.inicio.value||"").trim(),fim:String(m.fim.value||"").trim(),valor_us:String(m.valorUs.value||"1,0000").trim()||"1,0000",aviso:String(m.alerta?.value||"").trim(),observacoes:String(m.obs.value||"").trim()};try{const editId=Number(m.editId||0);const endpoint=m.modo==="editar"?`/cadastros/prestadores/credenciamentos/${editId}`:"/cadastros/prestadores/credenciamentos";const method=m.modo==="editar"?"PUT":"POST";const{res,data}=await requestJson(method,endpoint,payload,true);if(!res.ok)throw new Error(String(data?.detail||"Falha ao gravar credenciamento."));const item=data||{};const idx=prestCredItens.findIndex(row=>Number(row.id||0)===Number(item.id||0));if(idx>=0)prestCredItens[idx]=item;else prestCredItens.push(item);prestCredSelId=Number(item.id||0)||null;prestCredRender();prestCredFecharModal();footerMsg.textContent=`Credenciamento '${item.codigo||""}' gravado.`}catch(err){window.alert(err?.message||"Não foi possível gravar o credenciamento.")}}
function prestCredEnsureUI(){if(prestCredCfg)return;const style=document.createElement("style");style.textContent=".prest-cred-panel{width:min(760px,100%);min-height:0;height:fit-content;align-self:start;padding:10px 10px 8px;background:#fff;border:1px solid #cfd8e3;box-sizing:border-box;font:12px Tahoma,sans-serif}.prest-cred-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0 8px}.prest-cred-toolbar .sep{width:1px;height:24px;background:#cfd8e3;margin:0 2px}.prest-cred-filtros{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:end;margin-bottom:8px}.prest-cred-filtros label{display:block;margin-bottom:2px}.prest-cred-filtros select,.prest-cred-modal-grid input,.prest-cred-modal-grid select,.prest-cred-modal-info input,.prest-cred-modal-detalhes textarea{width:100%;height:24px;border:1px solid #bfc9d6;padding:0 6px;box-sizing:border-box;background:#fff}.prest-cred-grid{border:1px solid #cfd8e3;background:#fff;min-height:420px}.prest-cred-grid table{width:100%;border-collapse:collapse;table-layout:fixed}.prest-cred-grid th,.prest-cred-grid td{border-bottom:1px solid #edf1f6;padding:3px 6px;height:22px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.prest-cred-grid th{background:#f2f6fb;font:700 12px Tahoma,sans-serif;text-align:left}.prest-cred-grid tr.selected{background:#d9e8fb}.prest-cred-total{margin-top:5px;color:#5b6b7e}.prest-cred-modal{width:min(500px,96vw);background:#f5f5f3;border:1px solid #c8ced8;box-sizing:border-box;font:12px Tahoma,sans-serif}.prest-cred-modal-body{padding:10px 12px 12px}.prest-cred-tabs{display:flex;gap:4px;margin-bottom:10px}.prest-cred-tab{height:28px;padding:0 12px;border:1px solid #bfc9d6;border-bottom:none;background:#ececec;font:12px Tahoma,sans-serif;cursor:pointer}.prest-cred-tab.active{background:#fff;font-weight:700}.prest-cred-pane{border:1px solid #bfc9d6;background:#fff;padding:10px;min-height:210px}.prest-cred-pane.hidden{display:none}.prest-cred-modal-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 10px;align-items:end}.prest-cred-modal-grid .span-2{grid-column:1 / -1}.prest-cred-modal-row{display:grid;grid-template-columns:1fr 20px 1fr 120px;gap:8px;align-items:end}.prest-cred-modal-info{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.prest-cred-modal-info input{background:#dffcff}.prest-cred-modal-detalhes textarea{height:150px;padding:6px;resize:none}.prest-cred-modal-actions{display:flex;justify-content:flex-end;gap:8px;padding:10px 0 0}.prest-cred-modal-actions .materiais-btn{min-width:86px;justify-content:center}";document.head.appendChild(style);workspaceEmpty.insertAdjacentHTML("afterend",`<section id="prest-cred-panel" class="prest-cred-panel hidden"><div class="panel-title">Cadastro de credenciamentos</div><div class="prest-cred-toolbar"><button id="prest-cred-btn-novo" class="materiais-btn" type="button"><img src="/desktop-assets/novo.png" alt="">Novo credenciamento...</button><button id="prest-cred-btn-editar" class="materiais-btn" type="button"><img src="/desktop-assets/editar.png" alt="">Altera...</button><button id="prest-cred-btn-excluir" class="materiais-btn" type="button"><img src="/desktop-assets/eliminar.png" alt="">Elimina</button><span class="sep"></span><button id="prest-cred-btn-fechar" class="materiais-btn" type="button"><img src="/desktop-assets/cancela.png" alt="">Fecha</button></div><div class="prest-cred-filtros"><div><label for="prest-cred-convenio">Convênio:</label><select id="prest-cred-convenio"></select></div><div><label for="prest-cred-prestador">Prestador:</label><select id="prest-cred-prestador"></select></div></div><div class="prest-cred-grid"><table><colgroup><col style="width:80px"><col><col><col style="width:100px"><col style="width:100px"><col style="width:90px"></colgroup><thead><tr><th>Código</th><th>Prestador</th><th>Convênio</th><th>Início</th><th>Fim</th><th>Valor US</th></tr></thead><tbody id="prest-cred-tbody"></tbody></table></div><div id="prest-cred-total" class="prest-cred-total">0 credenciamentos</div></section><div id="prest-cred-modal-backdrop" class="modal-backdrop hidden"><div class="modal prest-cred-modal"><div class="modal-header"><div id="prest-cred-modal-title" class="modal-title">Novo credenciamento</div></div><div class="prest-cred-modal-body"><div class="prest-cred-tabs"><button data-tab="principal" class="prest-cred-tab active" type="button">Principal</button><button data-tab="detalhes" class="prest-cred-tab" type="button">Detalhes</button></div><section data-tab="principal" class="prest-cred-pane"><div class="prest-cred-modal-grid"><div class="span-2"><label>Convênio:</label><select id="prest-cred-modal-convenio"></select></div><div class="span-2"><label>Prestador credenciado:</label><select id="prest-cred-modal-prestador"></select></div><div><label>Código:</label><input id="prest-cred-modal-codigo" type="text"></div><div class="prest-cred-modal-row"><div><label>Vigência:</label><input id="prest-cred-modal-inicio" type="text"></div><div style="align-self:end;text-align:center">a</div><div><label>&nbsp;</label><input id="prest-cred-modal-fim" type="text"></div><div><label>Valor US:</label><input id="prest-cred-modal-valor-us" type="text"></div></div></div><div class="prest-cred-modal-info"><div><label>Inclusão:</label><input id="prest-cred-modal-inclusao" type="text" readonly></div><div><label>Alteração:</label><input id="prest-cred-modal-alteracao" type="text" readonly></div></div></section><section data-tab="detalhes" class="prest-cred-pane prest-cred-modal-detalhes hidden"><label>Observações:</label><textarea id="prest-cred-modal-obs"></textarea></section><div class="prest-cred-modal-actions"><button id="prest-cred-modal-ok" class="materiais-btn" type="button"><img src="/desktop-assets/gravar.png" alt="">Ok</button><button id="prest-cred-modal-cancelar" class="materiais-btn" type="button"><img src="/desktop-assets/cancela.png" alt="">Cancela</button></div></div></div></div>`);prestCredCfg={panel:document.getElementById("prest-cred-panel"),cboConvenio:document.getElementById("prest-cred-convenio"),cboPrestador:document.getElementById("prest-cred-prestador"),tbody:document.getElementById("prest-cred-tbody"),total:document.getElementById("prest-cred-total"),btnNovo:document.getElementById("prest-cred-btn-novo"),btnEditar:document.getElementById("prest-cred-btn-editar"),btnExcluir:document.getElementById("prest-cred-btn-excluir"),btnFechar:document.getElementById("prest-cred-btn-fechar"),modal:{backdrop:document.getElementById("prest-cred-modal-backdrop"),modal:document.querySelector("#prest-cred-modal-backdrop .prest-cred-modal"),title:document.getElementById("prest-cred-modal-title"),tabs:[...document.querySelectorAll("#prest-cred-modal-backdrop .prest-cred-tab")],panes:[...document.querySelectorAll("#prest-cred-modal-backdrop .prest-cred-pane")],cboConvenio:document.getElementById("prest-cred-modal-convenio"),cboPrestador:document.getElementById("prest-cred-modal-prestador"),codigo:document.getElementById("prest-cred-modal-codigo"),inicio:document.getElementById("prest-cred-modal-inicio"),fim:document.getElementById("prest-cred-modal-fim"),valorUs:document.getElementById("prest-cred-modal-valor-us"),inclusao:document.getElementById("prest-cred-modal-inclusao"),alteracao:document.getElementById("prest-cred-modal-alteracao"),obs:document.getElementById("prest-cred-modal-obs"),ok:document.getElementById("prest-cred-modal-ok"),cancelar:document.getElementById("prest-cred-modal-cancelar"),modo:"novo",editId:null,tabAtual:"principal"}};ensurePanelChrome(prestCredCfg.panel);ensureModalChrome(prestCredCfg.modal.modal);bindStandardGridActivation(prestCredCfg.tbody,tr=>prestCredSelecionarLinha(tr),()=>prestCredAbrirModal("editar"));prestCredCfg.cboConvenio.addEventListener("change",prestCredRender);prestCredCfg.cboPrestador.addEventListener("change",prestCredRender);prestCredCfg.btnNovo.addEventListener("click",()=>prestCredAbrirModal("novo"));prestCredCfg.btnEditar.addEventListener("click",()=>prestCredAbrirModal("editar"));prestCredCfg.btnExcluir.addEventListener("click",prestCredExcluirSelecionado);prestCredCfg.btnFechar.addEventListener("click",()=>{prestCredCfg.panel.classList.add("hidden");workspaceEmpty.classList.remove("hidden");footerMsg.textContent="Cadastro > Credenciamentos fechado."});prestCredCfg.modal.tabs.forEach(btn=>btn.addEventListener("click",()=>prestCredTabs(btn.dataset.tab||"principal")));prestCredCfg.modal.ok.addEventListener("click",prestCredSalvarModal);prestCredCfg.modal.cancelar.addEventListener("click",prestCredFecharModal);prestCredCfg.modal.backdrop.addEventListener("click",ev=>{if(ev.target===prestCredCfg.modal.backdrop)prestCredFecharModal()})}
function prestComConvenioAtual(){return String(prestComCfg?.cboConvenio?.value||"").trim()}
function prestComPrestadorAtual(){return String(prestComCfg?.cboPrestador?.value||"").trim()}
function prestComFiltrar(){const convenio=prestComConvenioAtual();const prestador=prestComPrestadorAtual();return prestComItens.filter(item=>(!convenio||convenio==="__todos__"||String(item.convenio_row_id||"")===convenio)&&(!prestador||prestador==="__todos__"||String(item.prestador_id||"")===prestador))}
function prestComRender(){if(!prestComCfg)return;const lista=prestComFiltrar();prestComCfg.tbody.innerHTML=lista.map(item=>`<tr data-id="${item.id}" class="${Number(item.id||0)===Number(prestComSelId)?"selected":""}"><td>${esc(String(item.vigencia||""))}</td><td>${esc(String(item.prestador_nome||""))}</td><td>${esc(String(item.convenio_nome||""))}</td><td>${esc(String(item.especialidade||""))}</td><td style="text-align:right">${esc(String(item.repasse||""))}</td></tr>`).join("")||'<tr><td colspan="5">Nenhum fator encontrado.</td></tr>';prestComCfg.total.textContent=`${lista.length} fatores   Duplo-clique para alterar o item desejado`}
function prestComSelecionarLinha(tr){prestComSelId=Number(tr?.dataset.id||0)||null;prestComRender()}
function prestComAtual(){return prestComItens.find(item=>Number(item.id||0)===Number(prestComSelId))||null}
function prestComFecharModal(){if(prestComCfg?.modal?.backdrop)prestComCfg.modal.backdrop.classList.add("hidden")}
function prestComEspecialidadesLista(extras=[]){const lista=prestListaEspecialidadesComExtras(extras);return lista.length?lista:["Gerais"]}
async function prestComCarregarGenericos(){try{const {res,data}=await requestJson("GET","/cadastros/procedimentos-genericos?q=",undefined,true);if(res.ok&&Array.isArray(data))return data}catch{}return []}
async function prestComCarregarItens(){try{const{res,data}=await requestJson("GET","/cadastros/prestadores/comissoes",undefined,true);if(res.ok&&Array.isArray(data?.itens))return data.itens}catch{}return[]}
async function prestComAbrirModal(modo){const item=modo==="editar"?prestComAtual():null;if(modo==="editar"&&!item){window.alert("Selecione um fator de comissão.");return}prestComEnsureUI();const genericos=await prestComCarregarGenericos();const m=prestComCfg.modal;const base=item?JSON.parse(JSON.stringify(item)):{id:Date.now(),vigencia:prestHojeBr(),prestador_id:prestComPrestadorAtual()==="__todos__"?String(prestSelecionado()?.id||"-1"):prestComPrestadorAtual(),convenio_row_id:prestComConvenioAtual()==="__todos__"?"":prestComConvenioAtual(),especialidade:prestEspecialidadesTexto(prestSelecionado())||"Gerais",procedimento_generico_id:"",tipo_repasse:"% sobre valor",repasse:"0,00",inclusao:prestHojeBr(),alteracao:prestHojeBr()};m.modo=modo;m.editId=item?Number(item.id||0):null;m.title.textContent=modo==="editar"?"Altera fator de comissão":"Novo fator de comissão";m.cboConvenio.innerHTML=prestCredConvenios.map(row=>`<option value="${esc(String(row.row_id||row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");m.cboPrestador.innerHTML=prestadoresCache.map(row=>`<option value="${esc(String(row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");m.cboEspecialidade.innerHTML=prestComEspecialidadesLista([String(base.especialidade||"").trim()]).map(row=>`<option value="${esc(String(row))}">${esc(String(row))}</option>`).join("");m.cboProcedimento.innerHTML=['<option value=""></option>',...genericos.map(row=>`<option value="${esc(String(row.id||""))}">${esc(String(row.descricao||row.nome||row.codigo||""))}</option>`)].join("");m.cboTipoRepasse.innerHTML=['<option>% sobre valor</option>','<option>Valor fixo</option>'].join("");m.cboPrestador.value=String(base.prestador_id||"");m.cboConvenio.value=String(base.convenio_row_id||"");m.cboEspecialidade.value=String(base.especialidade||"");m.cboProcedimento.value=String(base.procedimento_generico_id||"");m.vigencia.value=String(base.vigencia||prestHojeBr());m.cboTipoRepasse.value=String(base.tipo_repasse||"% sobre valor");m.repasse.value=String(base.repasse||"0,00");m.inclusao.value=String(base.inclusao||prestHojeBr());m.alteracao.value=String(base.alteracao||prestHojeBr());m.backdrop.classList.remove("hidden")}
async function prestComSalvarModal(){if(!prestComCfg?.modal)return;const m=prestComCfg.modal;const convenioId=String(m.cboConvenio.value||"").trim();const prestadorId=String(m.cboPrestador.value||"").trim();if(!convenioId||!prestadorId){window.alert("Preencha conv?nio e prestador.");return}const payload={vigencia:String(m.vigencia.value||prestHojeBr()).trim(),prestador_row_id:Number(prestadorId||0)>0?Number(prestadorId||0):null,convenio_row_id:Number(convenioId||0),especialidade:String(m.cboEspecialidade.value||"").trim(),procedimento_generico_id:Number(m.cboProcedimento.value||0)||null,tipo_repasse:String(m.cboTipoRepasse.value||"% sobre valor"),repasse:String(m.repasse.value||"0,00").trim()||"0,00"};try{const editId=Number(m.editId||0);const endpoint=m.modo==="editar"?`/cadastros/prestadores/comissoes/${editId}`:"/cadastros/prestadores/comissoes";const method=m.modo==="editar"?"PUT":"POST";const{res,data}=await requestJson(method,endpoint,payload,true);if(!res.ok)throw new Error(String(data?.detail||"Falha ao gravar fator de comissão."));const item=data||{};const idx=prestComItens.findIndex(row=>Number(row.id||0)===Number(item.id||0));if(idx>=0)prestComItens[idx]=item;else prestComItens.push(item);prestComSelId=Number(item.id||0)||null;prestComRender();prestComFecharModal();footerMsg.textContent=`Fator de comissão de '${item.prestador_nome||""}' gravado.`}catch(err){window.alert(err?.message||"Não foi possível gravar o fator de comissão.")}}
async function prestComExcluirSelecionado(){const item=prestComAtual();if(!item){window.alert("Selecione um fator de comissão.");return}if(!window.confirm(`Deseja eliminar o fator de comissão de ${item.prestador_nome} ?`))return;try{const{res,data}=await requestJson("DELETE",`/cadastros/prestadores/comissoes/${Number(item.id||0)}`,undefined,true);if(!res.ok)throw new Error(String(data?.detail||"Falha ao eliminar fator de comissão."));prestComItens=prestComItens.filter(row=>Number(row.id||0)!==Number(item.id||0));prestComSelId=null;prestComRender();footerMsg.textContent=`Fator de comissão de '${item.prestador_nome}' eliminado.`}catch(err){window.alert(err?.message||"Não foi possível eliminar o fator de comissão.")}}
function prestComAtualizarCombos(prestadorId){if(!prestComCfg)return;prestComCfg.cboConvenio.innerHTML=['<option value="__todos__">&lt;&lt;Todos&gt;&gt;</option>',...prestCredConvenios.map(item=>`<option value="${esc(String(item.row_id||item.id||""))}">${esc(String(item.nome||""))}</option>`)].join("");prestComCfg.cboPrestador.innerHTML=['<option value="__todos__">&lt;&lt;Todos&gt;&gt;</option>',...prestadoresCache.map(item=>`<option value="${esc(String(item.id||""))}">${esc(String(item.nome||""))}</option>`)].join("");prestComCfg.cboConvenio.value="__todos__";prestComCfg.cboPrestador.value=prestadorId?String(prestadorId):"__todos__"}
async function prestComAbrir(){prestEnsureUI();prestComEnsureUI();hideAllPanels();prestComCfg.panel.classList.remove("hidden");workspaceEmpty.classList.add("hidden");ensurePanelChrome(prestComCfg.panel);prestCredConvenios=await prestCredCarregarConvenios();prestComItens=await prestComCarregarItens();const prestador=prestSelecionado();prestComAtualizarCombos(prestador?.id||null);prestComRender();footerMsg.textContent="Cadastro > Comissões aberto."}
function prestComEnsureUI(){if(prestComCfg)return;const style=document.createElement("style");style.textContent=".prest-com-panel{width:min(760px,100%);min-height:0;height:fit-content;align-self:start;padding:10px 10px 8px;background:#fff;border:1px solid #cfd8e3;box-sizing:border-box;font:12px Tahoma,sans-serif}.prest-com-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0 8px}.prest-com-toolbar .sep{width:1px;height:24px;background:#cfd8e3;margin:0 2px}.prest-com-filtros{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:end;margin-bottom:8px}.prest-com-filtros label{display:block;margin-bottom:2px}.prest-com-filtros select,.prest-com-modal-grid input,.prest-com-modal-grid select{width:100%;height:24px;border:1px solid #bfc9d6;padding:0 6px;box-sizing:border-box;background:#fff}.prest-com-grid{border:1px solid #cfd8e3;background:#fff;min-height:420px}.prest-com-grid table{width:100%;border-collapse:collapse;table-layout:fixed}.prest-com-grid th,.prest-com-grid td{border-bottom:1px solid #edf1f6;padding:3px 6px;height:22px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.prest-com-grid th{background:#f2f6fb;font:700 12px Tahoma,sans-serif;text-align:left}.prest-com-grid tr.selected{background:#d9e8fb}.prest-com-total{margin-top:5px;color:#5b6b7e}.prest-com-modal{width:min(520px,96vw);background:#f5f5f3;border:1px solid #c8ced8;box-sizing:border-box;font:12px Tahoma,sans-serif}.prest-com-modal-body{padding:10px 12px 12px}.prest-com-modal-grid{display:grid;grid-template-columns:1fr 1fr 140px;gap:8px 10px;align-items:end}.prest-com-modal-grid .span-2{grid-column:span 2}.prest-com-modal-grid .span-3{grid-column:1 / -1}.prest-com-modal-info{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.prest-com-modal-info input{background:#dffcff}.prest-com-modal-actions{display:flex;justify-content:flex-end;gap:8px;padding:10px 0 0}.prest-com-modal-actions .materiais-btn{min-width:86px;justify-content:center}";document.head.appendChild(style);workspaceEmpty.insertAdjacentHTML("afterend",`<section id="prest-com-panel" class="prest-com-panel hidden"><div class="panel-title">Configura fatores de comissão</div><div class="prest-com-toolbar"><button id="prest-com-btn-novo" class="materiais-btn" type="button"><img src="/desktop-assets/novo.png" alt="">Novo fator de comissão...</button><button id="prest-com-btn-editar" class="materiais-btn" type="button"><img src="/desktop-assets/editar.png" alt="">Altera...</button><button id="prest-com-btn-excluir" class="materiais-btn" type="button"><img src="/desktop-assets/eliminar.png" alt="">Elimina</button><span class="sep"></span><button id="prest-com-btn-fechar" class="materiais-btn" type="button"><img src="/desktop-assets/cancela.png" alt="">Fecha</button></div><div class="prest-com-filtros"><div><label for="prest-com-convenio">Convênio:</label><select id="prest-com-convenio"></select></div><div><label for="prest-com-prestador">Prestador:</label><select id="prest-com-prestador"></select></div></div><div class="prest-com-grid"><table><colgroup><col style="width:100px"><col><col><col style="width:180px"><col style="width:90px"></colgroup><thead><tr><th>Vigência</th><th>Prestador</th><th>Convênio</th><th>Especialidade</th><th>Repasse</th></tr></thead><tbody id="prest-com-tbody"></tbody></table></div><div id="prest-com-total" class="prest-com-total">0 fatores</div></section><div id="prest-com-modal-backdrop" class="modal-backdrop hidden"><div class="modal prest-com-modal"><div class="modal-header"><div id="prest-com-modal-title" class="modal-title">Novo fator de comissão</div></div><div class="prest-com-modal-body"><div class="prest-com-modal-grid"><div class="span-3"><label>Convênio:</label><select id="prest-com-modal-convenio"></select></div><div class="span-3"><label>Prestador:</label><select id="prest-com-modal-prestador"></select></div><div class="span-3"><label>Especialidade:</label><select id="prest-com-modal-especialidade"></select></div><div class="span-3"><label>Procedimento genérico:</label><select id="prest-com-modal-procedimento"></select></div><div><label>Início da vigência:</label><input id="prest-com-modal-vigencia" type="text"></div><div><label>Tipo de repasse:</label><select id="prest-com-modal-tipo-repasse"></select></div><div><label>Valor de repasse:</label><input id="prest-com-modal-repasse" type="text"></div></div><div class="prest-com-modal-info"><div><label>Inclusão:</label><input id="prest-com-modal-inclusao" type="text" readonly></div><div><label>Alteração:</label><input id="prest-com-modal-alteracao" type="text" readonly></div></div><div class="prest-com-modal-actions"><button id="prest-com-modal-ok" class="materiais-btn" type="button"><img src="/desktop-assets/gravar.png" alt="">Ok</button><button id="prest-com-modal-cancelar" class="materiais-btn" type="button"><img src="/desktop-assets/cancela.png" alt="">Cancela</button></div></div></div></div>`);prestComCfg={panel:document.getElementById("prest-com-panel"),cboConvenio:document.getElementById("prest-com-convenio"),cboPrestador:document.getElementById("prest-com-prestador"),tbody:document.getElementById("prest-com-tbody"),total:document.getElementById("prest-com-total"),btnNovo:document.getElementById("prest-com-btn-novo"),btnEditar:document.getElementById("prest-com-btn-editar"),btnExcluir:document.getElementById("prest-com-btn-excluir"),btnFechar:document.getElementById("prest-com-btn-fechar"),modal:{backdrop:document.getElementById("prest-com-modal-backdrop"),modal:document.querySelector("#prest-com-modal-backdrop .prest-com-modal"),title:document.getElementById("prest-com-modal-title"),cboConvenio:document.getElementById("prest-com-modal-convenio"),cboPrestador:document.getElementById("prest-com-modal-prestador"),cboEspecialidade:document.getElementById("prest-com-modal-especialidade"),cboProcedimento:document.getElementById("prest-com-modal-procedimento"),vigencia:document.getElementById("prest-com-modal-vigencia"),cboTipoRepasse:document.getElementById("prest-com-modal-tipo-repasse"),repasse:document.getElementById("prest-com-modal-repasse"),inclusao:document.getElementById("prest-com-modal-inclusao"),alteracao:document.getElementById("prest-com-modal-alteracao"),ok:document.getElementById("prest-com-modal-ok"),cancelar:document.getElementById("prest-com-modal-cancelar"),modo:"novo",editId:null}};ensurePanelChrome(prestComCfg.panel);ensureModalChrome(prestComCfg.modal.modal);bindStandardGridActivation(prestComCfg.tbody,tr=>prestComSelecionarLinha(tr),()=>prestComAbrirModal("editar"));prestComCfg.cboConvenio.addEventListener("change",prestComRender);prestComCfg.cboPrestador.addEventListener("change",prestComRender);prestComCfg.btnNovo.addEventListener("click",()=>prestComAbrirModal("novo"));prestComCfg.btnEditar.addEventListener("click",()=>prestComAbrirModal("editar"));prestComCfg.btnExcluir.addEventListener("click",prestComExcluirSelecionado);prestComCfg.btnFechar.addEventListener("click",()=>{prestComCfg.panel.classList.add("hidden");workspaceEmpty.classList.remove("hidden");footerMsg.textContent="Cadastro > Comissões fechado."});prestComCfg.modal.ok.addEventListener("click",prestComSalvarModal);prestComCfg.modal.cancelar.addEventListener("click",prestComFecharModal);prestComCfg.modal.backdrop.addEventListener("click",ev=>{if(ev.target===prestComCfg.modal.backdrop)prestComFecharModal()})}
function prestBindAgendaButton(){if(!prestCfg?.btnAgenda||prestCfg.btnAgenda.dataset.agendaBound==="1")return;const novo=prestCfg.btnAgenda.cloneNode(true);prestCfg.btnAgenda.replaceWith(novo);prestCfg.btnAgenda=novo;prestCfg.btnAgenda.dataset.agendaBound="1";prestCfg.btnAgenda.addEventListener("click",prestAgendaAbrir)}
function prestGarantirAgendaVinculo(){const btn=document.getElementById("prest-btn-agenda");if(!btn)return;btn.onclick=ev=>{ev.preventDefault();prestAgendaAbrir()};if(prestCfg)prestCfg.btnAgenda=btn;btn.dataset.agendaBound="1"}
function prestBindConveniosButton(){if(!prestCfg?.btnConvenios||prestCfg.btnConvenios.dataset.convBound==="1")return;const novo=prestCfg.btnConvenios.cloneNode(true);prestCfg.btnConvenios.replaceWith(novo);prestCfg.btnConvenios=novo;prestCfg.btnConvenios.dataset.convBound="1";prestCfg.btnConvenios.addEventListener("click",prestCredAbrir)}
function prestBindComissoesButton(){if(!prestCfg?.btnComissoes||prestCfg.btnComissoes.dataset.comBound==="1")return;const novo=prestCfg.btnComissoes.cloneNode(true);prestCfg.btnComissoes.replaceWith(novo);prestCfg.btnComissoes=novo;prestCfg.btnComissoes.dataset.comBound="1";prestCfg.btnComissoes.addEventListener("click",prestComAbrir)}
let prestComEspecialidadesCache=[];
async function prestComCarregarEspecialidades(){try{const{res,data}=await requestJson("GET","/cadastros/auxiliares/especialidades-ativas",undefined,true);if(res.ok&&Array.isArray(data)){prestComEspecialidadesCache=data.map(item=>({id:Number(item?.id||0)||0,nome:String(item?.nome||item?.descricao||"").trim()})).filter(item=>item.id>0&&item.nome);return prestComEspecialidadesCache}}catch{}prestComEspecialidadesCache=[];return prestComEspecialidadesCache}
function prestComNormalizarTextos(){if(!prestComCfg)return;const panel=prestComCfg.panel;const title=panel?.querySelector(".panel-title");if(title)title.textContent="Configura fatores de comissão";const l1=panel?.querySelector('label[for="prest-com-convenio"]');if(l1)l1.textContent="Convênio:";const l2=panel?.querySelector('label[for="prest-com-prestador"]');if(l2)l2.textContent="Prestador:";const heads=panel?.querySelectorAll("thead th");if(heads&&heads.length>=5){heads[0].textContent="Vigência";heads[1].textContent="Prestador";heads[2].textContent="Convênio";heads[3].textContent="Especialidade";heads[4].textContent="Repasse"}if(prestComCfg.btnNovo)prestComCfg.btnNovo.lastChild.textContent="Novo fator de comissão...";if(prestComCfg.btnEditar)prestComCfg.btnEditar.lastChild.textContent="Altera...";if(prestComCfg.btnExcluir)prestComCfg.btnExcluir.lastChild.textContent="Elimina";if(prestComCfg.btnFechar)prestComCfg.btnFechar.lastChild.textContent="Fecha"}
function prestComEspecialidadesLista(extras=[]){const base=(Array.isArray(prestComEspecialidadesCache)?prestComEspecialidadesCache:[]).map(item=>String(item?.nome||"").trim()).filter(Boolean);const add=(Array.isArray(extras)?extras:[]).map(v=>String(v||"").trim()).filter(Boolean);const lista=[...new Set([...base,...add])];return lista.length?lista:["Gerais"]}
async function prestComAbrirModal(modo){const item=modo==="editar"?prestComAtual():null;if(modo==="editar"&&!item){window.alert("Selecione um fator de comissão.");return}prestComEnsureUI();prestComNormalizarTextos();const[genericos,especialidades]=await Promise.all([prestComCarregarGenericos(),prestComCarregarEspecialidades()]);const m=prestComCfg.modal;const base=item?JSON.parse(JSON.stringify(item)):{id:Date.now(),vigencia:prestHojeBr(),prestador_id:prestComPrestadorAtual()==="__todos__"?String(prestSelecionado()?.id||"-1"):prestComPrestadorAtual(),convenio_row_id:prestComConvenioAtual()==="__todos__"?"":prestComConvenioAtual(),especialidade_row_id:null,especialidade:prestEspecialidadesTexto(prestSelecionado())||"Gerais",procedimento_generico_id:"",tipo_repasse_codigo:1,tipo_repasse:"% sobre valor",repasse:"0,00",inclusao:prestHojeBr(),alteracao:prestHojeBr()};m.modo=modo;m.editId=item?Number(item.id||0):null;m.title.textContent=modo==="editar"?"Altera fator de comissão":"Novo fator de comissão";m.cboConvenio.innerHTML=prestCredConvenios.map(row=>`<option value="${esc(String(row.row_id||row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");m.cboPrestador.innerHTML=prestadoresCache.map(row=>`<option value="${esc(String(row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");const espOpts=(Array.isArray(especialidades)&&especialidades.length?especialidades:[]).map(row=>({id:Number(row.id||0)||0,nome:String(row.nome||"").trim()})).filter(row=>row.id>0&&row.nome);let espAtualId=Number(base.especialidade_row_id||0)||0;let espAtualNome=String(base.especialidade||"").trim();if(!espAtualId&&espAtualNome){const achado=espOpts.find(row=>row.nome.toLowerCase()===espAtualNome.toLowerCase());if(achado)espAtualId=achado.id}const espHtml=['<option value=""></option>',...espOpts.map(row=>`<option value="${row.id}">${esc(row.nome)}</option>` )];if(espAtualNome&&!espAtualId&&!espOpts.some(row=>row.nome.toLowerCase()===espAtualNome.toLowerCase()))espHtml.push(`<option value="__legacy__" selected>${esc(espAtualNome)}</option>`);m.cboEspecialidade.innerHTML=espHtml.join("");m.cboProcedimento.innerHTML=['<option value=""></option>',...genericos.map(row=>`<option value="${esc(String(row.id||""))}">${esc(String(row.descricao||row.nome||row.codigo||""))}</option>`)].join("");m.cboTipoRepasse.innerHTML='<option value="1">% sobre valor</option><option value="2">Valor fixo</option>';m.cboPrestador.value=String(base.prestador_id||"");m.cboConvenio.value=String(base.convenio_row_id||"");if(espAtualId)m.cboEspecialidade.value=String(espAtualId);m.cboProcedimento.value=String(base.procedimento_generico_id||"");m.vigencia.value=String(base.vigencia||prestHojeBr());m.cboTipoRepasse.value=String(Number(base.tipo_repasse_codigo||0)||((String(base.tipo_repasse||"").includes("%"))?1:2));m.repasse.value=String(base.repasse||"0,00");m.inclusao.value=String(base.inclusao||prestHojeBr());m.alteracao.value=String(base.alteracao||prestHojeBr());m.backdrop.classList.remove("hidden")}
async function prestComSalvarModal(){if(!prestComCfg?.modal)return;const m=prestComCfg.modal;const convenioId=String(m.cboConvenio.value||"").trim();const prestadorId=String(m.cboPrestador.value||"").trim();if(!convenioId||!prestadorId){window.alert("Preencha convênio e prestador.");return}const espSel=m.cboEspecialidade?.selectedOptions?.[0];const espRaw=String(m.cboEspecialidade?.value||"").trim();const espRowId=Number(espRaw||0);const espNome=String(espSel?.textContent||"").trim();const tipoCodigo=Number(m.cboTipoRepasse.value||1)||1;const tipoNome=String(m.cboTipoRepasse.selectedOptions?.[0]?.textContent||"").trim()||"% sobre valor";const payload={vigencia:String(m.vigencia.value||prestHojeBr()).trim(),prestador_row_id:Number(prestadorId||0)>0?Number(prestadorId||0):null,convenio_row_id:Number(convenioId||0),especialidade_row_id:espRowId>0?espRowId:null,especialidade:espNome||null,procedimento_generico_id:Number(m.cboProcedimento.value||0)||null,tipo_repasse_codigo:tipoCodigo,tipo_repasse:tipoNome,repasse:String(m.repasse.value||"0,00").trim()||"0,00"};try{const editId=Number(m.editId||0);const endpoint=m.modo==="editar"?`/cadastros/prestadores/comissoes/${editId}`:"/cadastros/prestadores/comissoes";const method=m.modo==="editar"?"PUT":"POST";const{res,data}=await requestJson(method,endpoint,payload,true);if(!res.ok)throw new Error(String(data?.detail||"Falha ao gravar fator de comissão."));const item=data||{};const idx=prestComItens.findIndex(row=>Number(row.id||0)===Number(item.id||0));if(idx>=0)prestComItens[idx]=item;else prestComItens.push(item);prestComSelId=Number(item.id||0)||null;prestComRender();prestComFecharModal();footerMsg.textContent=`Fator de comissão de '${item.prestador_nome||""}' gravado.`}catch(err){window.alert(err?.message||"Não foi possível gravar o fator de comissão.")}}
async function prestComAbrir(){prestEnsureUI();prestComEnsureUI();prestComNormalizarTextos();hideAllPanels();prestComCfg.panel.classList.remove("hidden");workspaceEmpty.classList.add("hidden");ensurePanelChrome(prestComCfg.panel);const [convenios,itens]=await Promise.all([prestCredCarregarConvenios(),prestComCarregarItens()]);prestCredConvenios=convenios;prestComItens=itens;await prestComCarregarEspecialidades();const prestador=prestSelecionado();prestComAtualizarCombos(prestador?.id||null);prestComRender();footerMsg.textContent="Cadastro > Comissões aberto."}
async function prestAbrir(){prestEnsureUI();prestApplyFineLayout();prestBindAgendaButton();prestBindConveniosButton();prestBindComissoesButton();prestGarantirAgendaVinculo();hideAllPanels();prestCfg.panel.classList.remove("hidden");workspaceEmpty.classList.add("hidden");ensurePanelChrome(prestCfg.panel);await prestCarregarEspecialidadesAtivas();await prestCarregar();footerMsg.textContent="Cadastro > Prestadores aberto."}

function prestComNormalizarTextos(){if(!prestComCfg)return;const panel=prestComCfg.panel;const title=panel?.querySelector(".panel-title");if(title)title.textContent="Configura fatores de comissão";const l1=panel?.querySelector('label[for="prest-com-convenio"]');if(l1)l1.textContent="Convênio:";const l2=panel?.querySelector('label[for="prest-com-prestador"]');if(l2)l2.textContent="Prestador:";const heads=panel?.querySelectorAll("thead th");if(heads&&heads.length>=5){heads[0].textContent="Vigência";heads[1].textContent="Prestador";heads[2].textContent="Convênio";heads[3].textContent="Especialidade";heads[4].textContent="Repasse"}if(prestComCfg.btnNovo)prestComCfg.btnNovo.lastChild.textContent="Novo fator de comissão...";if(prestComCfg.btnEditar)prestComCfg.btnEditar.lastChild.textContent="Altera...";if(prestComCfg.btnExcluir)prestComCfg.btnExcluir.lastChild.textContent="Elimina";if(prestComCfg.btnFechar)prestComCfg.btnFechar.lastChild.textContent="Fecha";const m=prestComCfg.modal;if(!m)return;const setLbl=(id,txt)=>{const el=document.getElementById(id);const lbl=el?.closest("div")?.querySelector("label");if(lbl)lbl.textContent=txt};setLbl("prest-com-modal-convenio","Convênio:");setLbl("prest-com-modal-prestador","Prestador:");setLbl("prest-com-modal-especialidade","Especialidade:");setLbl("prest-com-modal-procedimento","Procedimento genérico:");setLbl("prest-com-modal-vigencia","Início da vigência:");setLbl("prest-com-modal-tipo-repasse","Tipo de repasse:");setLbl("prest-com-modal-repasse","Valor de repasse:");setLbl("prest-com-modal-inclusao","Inclusão:");setLbl("prest-com-modal-alteracao","Alteração:")}
function prestComApplyFineLayout(){if(document.getElementById("prest-com-fine-style"))return;const style=document.createElement("style");style.id="prest-com-fine-style";style.textContent=`#prest-com-panel{width:min(736px,100%);padding:8px 8px 6px}#prest-com-panel .prest-com-toolbar{gap:6px;margin:4px 0 6px;flex-wrap:nowrap}#prest-com-panel .prest-com-toolbar .materiais-btn{height:28px;padding:0 9px;font:600 12px Tahoma,sans-serif}#prest-com-panel .prest-com-filtros{gap:8px;margin-bottom:6px}#prest-com-panel .prest-com-filtros select{height:22px;padding:0 5px}#prest-com-panel .prest-com-grid{min-height:390px}#prest-com-panel .prest-com-grid th,#prest-com-panel .prest-com-grid td{height:20px;padding:2px 5px}#prest-com-modal-backdrop .prest-com-modal{width:min(458px,94vw)}#prest-com-modal-backdrop .prest-com-modal-body{padding:8px 9px 8px}#prest-com-modal-backdrop .prest-com-modal-grid{grid-template-columns:1fr 1fr 120px;gap:4px 7px}#prest-com-modal-backdrop .prest-com-modal-grid label{margin-bottom:1px;font:12px Tahoma,sans-serif}#prest-com-modal-backdrop .prest-com-modal-grid input,#prest-com-modal-backdrop .prest-com-modal-grid select{height:22px;padding:0 4px;font:12px Tahoma,sans-serif}#prest-com-modal-backdrop .prest-com-modal-info{gap:8px;margin-top:6px;align-items:start}#prest-com-modal-backdrop .prest-com-modal-info>div{display:block}#prest-com-modal-backdrop .prest-com-modal-info label{display:block;margin-bottom:1px}#prest-com-modal-backdrop .prest-com-modal-info input{display:block;width:100%;height:22px}#prest-com-modal-backdrop .prest-com-modal-actions{gap:8px;padding:7px 0 0}#prest-com-modal-backdrop .prest-com-modal-actions .materiais-btn{min-width:74px;height:28px;padding:0 10px;justify-content:center;border-radius:4px;font:12px Tahoma,sans-serif}#prest-com-modal-backdrop .prest-com-modal-actions .materiais-btn img{display:none}`;document.head.appendChild(style)}
async function prestComAbrirModal(modo){const item=modo==="editar"?prestComAtual():null;if(modo==="editar"&&!item){window.alert("Selecione um fator de comissão.");return}prestComEnsureUI();prestComApplyFineLayout();prestComNormalizarTextos();const[genericos,especialidades]=await Promise.all([prestComCarregarGenericos(),prestComCarregarEspecialidades()]);const m=prestComCfg.modal;const base=item?JSON.parse(JSON.stringify(item)):{id:Date.now(),vigencia:prestHojeBr(),prestador_id:prestComPrestadorAtual()==="__todos__"?String(prestSelecionado()?.id||"-1"):prestComPrestadorAtual(),convenio_row_id:prestComConvenioAtual()==="__todos__"?"":prestComConvenioAtual(),especialidade_row_id:null,especialidade:prestEspecialidadesTexto(prestSelecionado())||"Gerais",procedimento_generico_id:"",tipo_repasse_codigo:1,tipo_repasse:"% sobre valor",repasse:"0,00",inclusao:prestHojeBr(),alteracao:prestHojeBr()};m.modo=modo;m.editId=item?Number(item.id||0):null;m.title.textContent=modo==="editar"?"Altera fator de comissão":"Novo fator de comissão";m.cboConvenio.innerHTML=prestCredConvenios.map(row=>`<option value="${esc(String(row.row_id||row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");m.cboPrestador.innerHTML=prestadoresCache.map(row=>`<option value="${esc(String(row.id||""))}">${esc(String(row.nome||""))}</option>`).join("");const espOpts=(Array.isArray(especialidades)&&especialidades.length?especialidades:[]).map(row=>({id:Number(row.id||0)||0,nome:String(row.nome||"").trim()})).filter(row=>row.id>0&&row.nome);let espAtualId=Number(base.especialidade_row_id||0)||0;let espAtualNome=String(base.especialidade||"").trim();if(!espAtualId&&espAtualNome){const achado=espOpts.find(row=>row.nome.toLowerCase()===espAtualNome.toLowerCase());if(achado)espAtualId=achado.id}const espHtml=['<option value=""></option>',...espOpts.map(row=>`<option value="${row.id}">${esc(row.nome)}</option>` )];if(espAtualNome&&!espAtualId&&!espOpts.some(row=>row.nome.toLowerCase()===espAtualNome.toLowerCase()))espHtml.push(`<option value="__legacy__" selected>${esc(espAtualNome)}</option>`);m.cboEspecialidade.innerHTML=espHtml.join("");m.cboProcedimento.innerHTML=['<option value=""></option>',...genericos.map(row=>`<option value="${esc(String(row.id||""))}">${esc(String(row.descricao||row.nome||row.codigo||""))}</option>`)].join("");m.cboTipoRepasse.innerHTML='<option value="1">% sobre valor</option><option value="2">Valor fixo</option>';m.cboPrestador.value=String(base.prestador_id||"");m.cboConvenio.value=String(base.convenio_row_id||"");if(espAtualId)m.cboEspecialidade.value=String(espAtualId);m.cboProcedimento.value=String(base.procedimento_generico_id||"");m.vigencia.value=String(base.vigencia||prestHojeBr());m.cboTipoRepasse.value=String(Number(base.tipo_repasse_codigo||0)||((String(base.tipo_repasse||"").includes("%"))?1:2));m.repasse.value=String(base.repasse||"0,00");m.inclusao.value=String(base.inclusao||prestHojeBr());m.alteracao.value=String(base.alteracao||prestHojeBr());prestComNormalizarTextos();m.backdrop.classList.remove("hidden")}
async function prestComAbrir(){prestEnsureUI();prestComEnsureUI();prestComApplyFineLayout();prestComNormalizarTextos();hideAllPanels();prestComCfg.panel.classList.remove("hidden");workspaceEmpty.classList.add("hidden");ensurePanelChrome(prestComCfg.panel);const [convenios,itens]=await Promise.all([prestCredCarregarConvenios(),prestComCarregarItens()]);prestCredConvenios=convenios;prestComItens=itens;await prestComCarregarEspecialidades();const prestador=prestSelecionado();prestComAtualizarCombos(prestador?.id||null);prestComRender();footerMsg.textContent="Cadastro > Comissões aberto."}

// PATCH Agenda da semana: habilita seleção/edição de agendamento existente
// sem alterar a estrutura-base do módulo legado.
if(typeof agendaSemanaRenderEventos==="function"){
  const _agendaSemanaRenderEventosOrig=agendaSemanaRenderEventos;
  const _agendaSemanaRenderEstruturaOrig=typeof agendaSemanaRenderEstrutura==="function"?agendaSemanaRenderEstrutura:null;
  const _agendaLegadoExcluirOrig=typeof agendaLegadoExcluir==="function"?agendaLegadoExcluir:null;
  let agendaSemanaCtxMenu=null;
  let agendaSemanaDeleteDialog=null;
  let agendaSemanaDragState=null;
  let agendaSemanaPesquisa=null;
  let agendaSemanaHorariosLivres=null;
  let agendaSemanaAviso=null;
  let agendaSemanaPublicar=null;

  const agendaSemanaGetEventoById=(id)=>{
    const n=Number(id||0)||0;
    if(!n)return null;
    return (Array.isArray(agendaSemanaCache)?agendaSemanaCache:[]).find(item=>Number(item?.id||0)===n)||null;
  };
  const agendaSemanaPassoMs=()=>{
    const step=Math.max(1,Number(agendaSemanaState?.step||5)||5);
    return step*60*1000;
  };
  const agendaSemanaEventoDataIso=(item)=>{
    const raw=String(item?.data||"").trim();
    if(!raw)return"";
    if(/^\d{4}-\d{2}-\d{2}$/.test(raw))return raw;
    const d=new Date(raw);
    if(Number.isNaN(d.getTime()))return"";
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  };
  const agendaSemanaBuscarOcupanteIntervalo=(dataIso,inicioMs,fimMs,ignoreEventId=0)=>{
    const iniLim=Math.max(0,Number(inicioMs||0)||0);
    const fimRaw=Number(fimMs||0);
    const fimLim=(Number.isFinite(fimRaw)&&fimRaw>iniLim)?fimRaw:(iniLim+1);
    const passoMs=agendaSemanaPassoMs();
    const ignoreId=Math.max(0,Number(ignoreEventId||0)||0);
    const candidatos=(Array.isArray(agendaSemanaCache)?agendaSemanaCache:[])
      .filter(item=>agendaSemanaEventoDataIso(item)===String(dataIso||""))
      .filter(item=>{
        const idEv=Math.max(0,Number(item?.id||0)||0);
        if(ignoreId>0&&idEv===ignoreId)return false;
        const iniEv=Math.max(0,Number(item?.hora_inicio||0)||0);
        let fimEv=Math.max(0,Number(item?.hora_fim||0)||0);
        if(!fimEv||fimEv<=iniEv)fimEv=iniEv+passoMs;
        return iniEv<fimLim&&fimEv>iniLim;
      })
      .sort((a,b)=>{
        const aIni=Math.max(0,Number(a?.hora_inicio||0)||0);
        const bIni=Math.max(0,Number(b?.hora_inicio||0)||0);
        if(aIni!==bIni)return aIni-bIni;
        const aId=Math.max(0,Number(a?.id||0)||0);
        const bId=Math.max(0,Number(b?.id||0)||0);
        return aId-bId;
      });
    return candidatos[0]||null;
  };
  const agendaSemanaIntervaloCliqueMs=(slot,slotHeight,clientY,rectTop)=>{
    const slotIniMs=Math.max(0,Number(slot?.min||0)||0)*60*1000;
    const passoMs=agendaSemanaPassoMs();
    const h=Math.max(1,Number(slotHeight||1)||1);
    const dy=Math.max(0,Math.min(h-1,(Number(clientY||0)-Number(rectTop||0))));
    const fracao=dy/h;
    const pontoMs=slotIniMs+Math.floor(fracao*passoMs);
    const iniMs=Math.max(slotIniMs,Math.min(slotIniMs+passoMs-1,pontoMs));
    return {iniMs,fimMs:iniMs+1};
  };
  const agendaSemanaIntervaloEventoMs=(item)=>{
    const iniMs=Math.max(0,Number(item?.hora_inicio||0)||0);
    let fimMs=Math.max(0,Number(item?.hora_fim||0)||0);
    if(!fimMs||fimMs<=iniMs)fimMs=iniMs+agendaSemanaPassoMs();
    const durMs=Math.max(1,fimMs-iniMs);
    return {iniMs,fimMs,durMs};
  };
  const agendaSemanaResolverDestinoDrop=(target,clientY)=>{
    const col=target?.closest?.(".agenda-semana-day[data-day]");
    if(!col)return null;
    const slots=Array.isArray(agendaSemanaSlots)?agendaSemanaSlots:[];
    if(!slots.length)return null;
    const slotHeight=Math.max(1,Number(agendaSemanaState?.slotHeight||AGENDA_SEMANA_SLOT_HEIGHT)||AGENDA_SEMANA_SLOT_HEIGHT);
    const dayIdx=Math.max(0,Math.min(5,Number(col.dataset.day||0)));
    const dayDate=Array.isArray(agendaSemanaState?.weekDates)?agendaSemanaState.weekDates[dayIdx]:null;
    if(!dayDate)return null;
    const rect=col.getBoundingClientRect();
    const slotIdx=Math.max(0,Math.min(slots.length-1,Math.floor((Number(clientY||0)-rect.top)/slotHeight)));
    const slot=slots[slotIdx];
    if(!slot)return null;
    const dataIso=agendaSemanaToIsoDate(dayDate);
    if(!dataIso)return null;
    const {iniMs}=agendaSemanaIntervaloCliqueMs(slot,slotHeight,clientY,rect.top);
    return {col,dataIso,inicioMs:iniMs};
  };
  const agendaSemanaLimparDropClasses=()=>{
    if(!agendaSemana?.daysWrap)return;
    agendaSemana.daysWrap.querySelectorAll(".agenda-semana-day.agenda-semana-drop-valid,.agenda-semana-day.agenda-semana-drop-invalid")
      .forEach(el=>el.classList.remove("agenda-semana-drop-valid","agenda-semana-drop-invalid"));
  };
  const agendaSemanaMarcarDropClasse=(col,ok)=>{
    agendaSemanaLimparDropClasses();
    if(!col)return;
    col.classList.add(ok?"agenda-semana-drop-valid":"agenda-semana-drop-invalid");
  };
  const agendaSemanaAvaliarDrop=(target,clientY)=>{
    if(!agendaSemanaDragState)return null;
    const destino=agendaSemanaResolverDestinoDrop(target,clientY);
    if(!destino)return null;
    const item=agendaSemanaGetEventoById(agendaSemanaDragState.eventId)||agendaSemanaDragState.item||null;
    if(!item)return null;
    const intervalo=agendaSemanaIntervaloEventoMs(item);
    const limiteIniMs=Math.max(0,Number(agendaSemanaState?.startMin||0)||0)*60*1000;
    if(destino.inicioMs<limiteIniMs){
      return {...destino,fimMs:destino.inicioMs+intervalo.durMs,valido:false,motivo:"antes-do-inicio"};
    }
    const fimMs=destino.inicioMs+intervalo.durMs;
    const limiteFimMs=Math.max(0,Number(agendaSemanaState?.endMin||0)||0)*60*1000;
    if(!limiteFimMs||fimMs>limiteFimMs){
      return {...destino,fimMs,valido:false,motivo:"sem-espaco-final"};
    }
    const conflito=agendaSemanaBuscarOcupanteIntervalo(destino.dataIso,destino.inicioMs,fimMs,agendaSemanaDragState.eventId);
    return {...destino,fimMs,valido:!conflito,conflito,motivo:conflito?"conflito":""};
  };
  const agendaSemanaNumOrNull=(value)=>{
    if(value===null||value===undefined)return null;
    const txt=String(value).trim();
    if(!txt)return null;
    const n=Number(txt);
    return Number.isFinite(n)?n:null;
  };
  const agendaSemanaPayloadMover=(item,dataIso,horaInicioMs,horaFimMs)=>({
    data:String(dataIso||""),
    hora_inicio:Math.max(0,Number(horaInicioMs||0)||0),
    hora_fim:Math.max(0,Number(horaFimMs||0)||0),
    sala:agendaSemanaNumOrNull(item?.sala),
    tipo:agendaSemanaNumOrNull(item?.tipo),
    nro_pac:agendaSemanaNumOrNull(item?.nro_pac),
    nome:String(item?.nome||"").trim(),
    motivo:String(item?.motivo||"").trim(),
    status:agendaSemanaNumOrNull(item?.status),
    observ:String(item?.observ||"").trim(),
    tip_fone1:agendaSemanaNumOrNull(item?.tip_fone1),
    fone1:String(item?.fone1||"").trim(),
    tip_fone2:agendaSemanaNumOrNull(item?.tip_fone2),
    fone2:String(item?.fone2||"").trim(),
    tip_fone3:agendaSemanaNumOrNull(item?.tip_fone3),
    fone3:String(item?.fone3||"").trim(),
    id_prestador:Math.max(0,Number(item?.id_prestador||agendaSemana?.selectPrestador?.value||sessaoAtual?.prestador_id||0)||0)||null,
    id_unidade:Math.max(0,Number(item?.id_unidade||agendaSemana?.selectUnidade?.value||sessaoAtual?.unidade_atendimento_id||0)||0)||null,
  });
  const agendaSemanaMoverEventoDrop=async(item,destino)=>{
    const id=Math.max(0,Number(item?.id||0)||0);
    if(!id)return false;
    const payload=agendaSemanaPayloadMover(item,destino.dataIso,destino.inicioMs,destino.fimMs);
    if(!payload.data||!payload.hora_inicio)return false;
    const {res,data}=await requestJson("PUT",`/agenda-legado/${id}`,payload,true);
    if(!res.ok){
      window.alert(data?.detail||"Não foi possível mover o agendamento.");
      return false;
    }
    agendaSemanaState.selectedEventId=id;
    await agendaSemanaCarregarEventos();
    return true;
  };
  const agendaSemanaFinalizarDrag=(manterClasse=false)=>{
    const prev=agendaSemanaDragState;
    agendaSemanaDragState=null;
    agendaSemanaLimparDropClasses();
    if(!manterClasse&&prev?.eventEl){
      prev.eventEl.classList.remove("agenda-semana-event-dragging");
    }
  };
  const agendaSemanaOnDragOver=(ev)=>{
    if(!agendaSemanaDragState)return;
    const avaliacao=agendaSemanaAvaliarDrop(ev.target,ev.clientY);
    if(!avaliacao){
      agendaSemanaLimparDropClasses();
      return;
    }
    ev.preventDefault();
    agendaSemanaDragState.destino=avaliacao;
    agendaSemanaMarcarDropClasse(avaliacao.col,!!avaliacao.valido);
    try{
      if(ev.dataTransfer)ev.dataTransfer.dropEffect=avaliacao.valido?"move":"none";
    }catch{}
  };
  const agendaSemanaOnDragLeave=(ev)=>{
    if(!agendaSemanaDragState)return;
    const rel=ev.relatedTarget;
    if(rel&&agendaSemana?.daysWrap?.contains(rel))return;
    agendaSemanaLimparDropClasses();
  };
  const agendaSemanaOnDrop=async(ev)=>{
    if(!agendaSemanaDragState)return;
    ev.preventDefault();
    const drag=agendaSemanaDragState;
    const destino=drag.destino||agendaSemanaAvaliarDrop(ev.target,ev.clientY);
    const item=agendaSemanaGetEventoById(drag.eventId)||drag.item||null;
    const mesmaPosicao=!!(destino&&destino.dataIso===drag.origemDataIso&&destino.inicioMs===drag.origemIniMs);
    agendaSemanaFinalizarDrag();
    if(!item)return;
    if(!destino||!destino.valido){
      footerMsg.textContent="Destino inválido: espaço livre menor que a duração do agendamento.";
      return;
    }
    if(mesmaPosicao)return;
    const ok=await agendaSemanaMoverEventoDrop(item,destino);
    if(ok){
      footerMsg.textContent="Agendamento movido com sucesso.";
    }
  };
  const agendaSemanaOcultarContexto=()=>{
    if(!agendaSemanaCtxMenu?.menu)return;
    agendaSemanaCtxMenu.menu.classList.add("hidden");
  };
  const agendaSemanaIndiceDiaVigente=()=>{
    const dias=Array.isArray(agendaSemanaState?.weekDates)?agendaSemanaState.weekDates:[];
    if(!dias.length)return-1;
    const hojeIso=agendaSemanaToIsoDate(new Date());
    return dias.findIndex(d=>agendaSemanaToIsoDate(d)===hojeIso);
  };
  const agendaSemanaAplicarDestaqueCabecalhoDia=()=>{
    if(!agendaSemana?.headDays)return;
    const heads=[...agendaSemana.headDays.children];
    if(!heads.length)return;
    const modo=String(agendaSemanaState?.mode||"semana").toLowerCase();
    if(modo==="clinica"){
      heads.forEach(el=>el.classList.remove("agenda-semana-day-head-active"));
      return;
    }
    const idxAtivo=agendaSemanaIndiceDiaVigente();
    heads.forEach((el,idx)=>el.classList.toggle("agenda-semana-day-head-active",idx===idxAtivo));
  };
  const agendaSemanaGarantirDialogoExclusao=()=>{
    if(agendaSemanaDeleteDialog?.backdrop)return agendaSemanaDeleteDialog;
    if(!document.getElementById("agenda-semana-delete-style")){
      const style=document.createElement("style");
      style.id="agenda-semana-delete-style";
      style.textContent=`
        .agenda-semana-delete-backdrop{
          position:fixed;inset:0;z-index:2600;background:transparent;
          display:grid;place-items:center
        }
        .agenda-semana-delete-backdrop.hidden{display:none}
        .agenda-semana-delete-modal{
          width:min(620px,96vw);
          border:1px solid #b9b9b9;
          background:#ececec;
          box-shadow:2px 2px 10px rgba(0,0,0,.3);
          box-sizing:border-box;
          font:12px Tahoma,sans-serif
        }
        .agenda-semana-delete-header{
          height:36px;
          border-bottom:1px solid #c9c9c9;
          display:flex;
          align-items:center;
          justify-content:center;
          background:#f2f2f2
        }
        .agenda-semana-delete-title{
          font:400 34px/1 "Segoe UI Symbol","Arial Unicode MS",Tahoma,sans-serif;
          margin:0;
          color:#2d2d2d;
          letter-spacing:0;
          transform:translateY(-1px) scaleX(0.72);
          transform-origin:center;
        }
        .agenda-semana-delete-body{padding:14px 16px 12px}
        .agenda-semana-delete-content{
          display:grid;
          grid-template-columns:88px 1fr;
          align-items:center;
          column-gap:16px;
          min-height:86px;
        }
        .agenda-semana-delete-icon{
          width:58px;height:58px;border-radius:50%;
          border:3px solid #5db1e9;
          background:radial-gradient(circle at 30% 28%,#c7edff 0,#9edbff 42%,#67b8ef 100%);
          color:#fff;
          font:700 42px/52px Tahoma,sans-serif;
          text-align:center;
          box-shadow:inset 0 0 0 1px rgba(255,255,255,.7);
          user-select:none;
        }
        .agenda-semana-delete-msg{
          line-height:1.35;
          font:400 31px/1 "Segoe UI Symbol","Arial Unicode MS",Tahoma,sans-serif;
          color:#1f1f1f;
          letter-spacing:0;
          transform:translateY(-1px) scaleX(0.72);
          transform-origin:left center;
        }
        .agenda-semana-delete-sep{
          height:1px;
          background:#bfc4cb;
          margin:10px 0 10px;
        }
        .agenda-semana-delete-actions{
          display:flex;
          justify-content:flex-end;
          gap:8px;
        }
        .agenda-semana-delete-actions button{
          min-width:94px;height:30px;border:1px solid #9ea7b4;background:#ececec;
          font:12px Tahoma,sans-serif;cursor:pointer
        }
      `;
      document.head.appendChild(style);
    }
    const backdrop=document.createElement("div");
    backdrop.id="agenda-semana-delete-backdrop";
    backdrop.className="agenda-semana-delete-backdrop hidden";
    backdrop.innerHTML=`
      <div class="agenda-semana-delete-modal" role="dialog" aria-modal="true" aria-labelledby="agenda-semana-delete-title">
        <div class="agenda-semana-delete-header">
          <div id="agenda-semana-delete-title" class="agenda-semana-delete-title">Agenda</div>
        </div>
        <div class="agenda-semana-delete-body">
          <div class="agenda-semana-delete-content">
            <div class="agenda-semana-delete-icon" aria-hidden="true">?</div>
            <div id="agenda-semana-delete-msg" class="agenda-semana-delete-msg"></div>
          </div>
          <div class="agenda-semana-delete-sep"></div>
          <div class="agenda-semana-delete-actions">
            <button id="agenda-semana-delete-excluir" type="button">Sim</button>
            <button id="agenda-semana-delete-cancelar" type="button">Não</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    const msg=backdrop.querySelector("#agenda-semana-delete-msg");
    const btnCancelar=backdrop.querySelector("#agenda-semana-delete-cancelar");
    const btnExcluir=backdrop.querySelector("#agenda-semana-delete-excluir");
    const dlg={backdrop,msg,btnCancelar,btnExcluir,resolve:null};
    const fechar=(ok)=>{
      if(dlg.backdrop.classList.contains("hidden"))return;
      dlg.backdrop.classList.add("hidden");
      const done=dlg.resolve;
      dlg.resolve=null;
      if(typeof done==="function")done(!!ok);
    };
    btnCancelar.addEventListener("click",()=>fechar(false));
    btnExcluir.addEventListener("click",()=>fechar(true));
    backdrop.addEventListener("click",ev=>{if(ev.target===backdrop)fechar(false)});
    document.addEventListener("keydown",ev=>{
      if(ev.key!=="Escape")return;
      if(dlg.backdrop.classList.contains("hidden"))return;
      ev.preventDefault();
      fechar(false);
    });
    agendaSemanaDeleteDialog=dlg;
    return dlg;
  };
  const agendaSemanaConfirmarExclusao=async(item)=>{
    const dlg=agendaSemanaGarantirDialogoExclusao();
    if(!dlg)return false;
    if(typeof dlg.resolve==="function"){
      const pendente=dlg.resolve;
      dlg.resolve=null;
      pendente(false);
    }
    const nome=String(item?.nome||"Sem nome").trim()||"Sem nome";
    dlg.msg.textContent=`Deseja eliminar o agendamento de '${nome}'?`;
    dlg.backdrop.classList.remove("hidden");
    requestAnimationFrame(()=>{try{dlg.btnExcluir.focus()}catch{}});
    return await new Promise(resolve=>{dlg.resolve=resolve});
  };
  const agendaSemanaPlaceholderContexto=(titulo)=>{
    footerMsg.textContent=`${titulo}: em planejamento.`;
  };
  const agendaSemanaGarantirContexto=()=>{
    if(agendaSemanaCtxMenu?.menu)return agendaSemanaCtxMenu;
    if(!document.getElementById("agenda-semana-context-style")){
      const style=document.createElement("style");
      style.id="agenda-semana-context-style";
      style.textContent=`
        .agenda-semana-context-menu{
          position:fixed;z-index:2500;min-width:220px;background:#f4f4f4;
          border:1px solid #8fa3ba;box-shadow:2px 2px 8px rgba(0,0,0,.28);
          font:12px Tahoma,sans-serif;padding:2px 0
        }
        .agenda-semana-context-menu.hidden{display:none}
        .agenda-semana-context-item{
          display:block;width:100%;height:24px;padding:0 10px;text-align:left;
          border:0;background:transparent;cursor:pointer;font:12px Tahoma,sans-serif;color:#000
        }
        .agenda-semana-context-item:hover{background:#cfe6ff}
        .agenda-semana-context-item.placeholder{color:#4b5a6a}
        .agenda-semana-context-sep{height:1px;background:#b9c4d1;margin:2px 0}
      `;
      document.head.appendChild(style);
    }
    const menu=document.createElement("div");
    menu.id="agenda-semana-context-menu";
    menu.className="agenda-semana-context-menu hidden";
    menu.dataset.mode="";
    document.body.appendChild(menu);
    agendaSemanaCtxMenu={menu,payload:null};
    menu.addEventListener("click",async(ev)=>{
      const btn=ev.target.closest("button[data-action]");
      if(!btn)return;
      ev.preventDefault();
      const action=String(btn.dataset.action||"");
      const payload=agendaSemanaCtxMenu?.payload||{};
      agendaSemanaOcultarContexto();
      if(action==="novo"){
        if(payload?.dataIso&&payload?.hora){
          agendaSemanaAbrirModalNovo(payload.dataIso,payload.hora);
        }
        return;
      }
      const item=payload?.item||null;
      if(action==="editar"){
        if(item)agendaSemanaAbrirModalEditar(item);
        return;
      }
      if(action==="excluir"){
        if(!item)return;
        agendaSemanaState.selectedEventId=Number(item.id||0)||null;
        if(typeof agendaLegadoEnsureUI==="function")agendaLegadoEnsureUI();
        if(agendaLegado?.modalBackdrop){
          agendaLegado.modalBackdrop.dataset.origem="agenda-semana";
          agendaLegado.modalBackdrop.dataset.prestadorId=String(Number(item?.id_prestador||agendaSemana?.selectPrestador?.value||sessaoAtual?.prestador_id||0)||0);
          agendaLegado.modalBackdrop.dataset.unidadeId=String(Number(item?.id_unidade||agendaSemana?.selectUnidade?.value||sessaoAtual?.unidade_atendimento_id||0)||0);
        }
        agendaLegadoSelId=Number(item.id||0)||null;
        if(typeof agendaLegadoExcluir==="function")await agendaLegadoExcluir();
        return;
      }
      if(action==="repetir"){agendaSemanaPlaceholderContexto("Repetir agendamento");return}
      if(action==="odontograma"){agendaSemanaPlaceholderContexto("Abrir odontograma");return}
      if(action==="ficha"){agendaSemanaPlaceholderContexto("Abrir ficha pessoal");return}
      if(action==="iguais"){agendaSemanaPlaceholderContexto("Pesquisar iguais");return}
    });
    document.addEventListener("mousedown",(ev)=>{
      if(!agendaSemanaCtxMenu?.menu||agendaSemanaCtxMenu.menu.classList.contains("hidden"))return;
      if(agendaSemanaCtxMenu.menu.contains(ev.target))return;
      agendaSemanaOcultarContexto();
    });
    document.addEventListener("keydown",(ev)=>{
      if(ev.key==="Escape")agendaSemanaOcultarContexto();
    });
    window.addEventListener("blur",agendaSemanaOcultarContexto);
    window.addEventListener("resize",agendaSemanaOcultarContexto);
    return agendaSemanaCtxMenu;
  };
  const agendaSemanaMostrarContexto=(payload,mouseEvent)=>{
    if(!mouseEvent)return;
    mouseEvent.preventDefault();
    const ctx=agendaSemanaGarantirContexto();
    if(!ctx?.menu)return;
    const modo=String(payload?.mode||"");
    if(modo==="ocupado"){
      ctx.menu.innerHTML=`
        <button class="agenda-semana-context-item" data-action="editar" type="button">Editar agendamento...</button>
        <button class="agenda-semana-context-item" data-action="excluir" type="button">Excluir agendamento</button>
        <div class="agenda-semana-context-sep"></div>
        <button class="agenda-semana-context-item placeholder" data-action="repetir" type="button">Repetir agendamento...</button>
        <button class="agenda-semana-context-item placeholder" data-action="odontograma" type="button">Abrir odontograma...</button>
        <button class="agenda-semana-context-item placeholder" data-action="ficha" type="button">Abrir ficha pessoal...</button>
        <button class="agenda-semana-context-item placeholder" data-action="iguais" type="button">Pesquisar iguais...</button>
      `;
    }else{
      ctx.menu.innerHTML=`<button class="agenda-semana-context-item" data-action="novo" type="button">Novo agendamento...</button>`;
    }
    ctx.payload=payload||null;
    ctx.menu.dataset.mode=modo;
    ctx.menu.classList.remove("hidden");
    ctx.menu.style.left="0px";
    ctx.menu.style.top="0px";
    const margin=8;
    const mw=ctx.menu.offsetWidth||220;
    const mh=ctx.menu.offsetHeight||30;
    let left=Number(mouseEvent.clientX||0);
    let top=Number(mouseEvent.clientY||0);
    const maxLeft=Math.max(margin,(window.innerWidth||left+mw)-mw-margin);
    const maxTop=Math.max(margin,(window.innerHeight||top+mh)-mh-margin);
    left=Math.min(Math.max(margin,left),maxLeft);
    top=Math.min(Math.max(margin,top),maxTop);
    ctx.menu.style.left=`${left}px`;
    ctx.menu.style.top=`${top}px`;
  };

  const agendaSemanaSyncSelecaoUI=()=>{
    const selId=Number(agendaSemanaState?.selectedEventId||0)||0;
    document.querySelectorAll(".agenda-semana-event[data-id]").forEach(el=>{
      const id=Number(el.getAttribute("data-id")||0)||0;
      el.classList.toggle("selected",!!selId&&id===selId);
    });
  };

  const agendaSemanaAbrirModalEditar=async(item)=>{
    if(!item)return;
    agendaLegadoEnsureUI();
    agendaLegadoVincularEventos();
    if(typeof agendaLegadoCarregarCombos==="function"){
      try{await agendaLegadoCarregarCombos()}catch{}
    }
    if(typeof agendaLegadoGarantirContatosCarregados==="function"){
      try{await agendaLegadoGarantirContatosCarregados()}catch{}
    }
    if(typeof agendaLegadoRecarregarStatus==="function"){
      try{await agendaLegadoRecarregarStatus()}catch{}
    }
    agendaLegadoSelId=Number(item.id||0)||null;
    agendaLegado.modalTitle.textContent="Editar agendamento";
    agendaLegadoModalPreencher(item);
    if(agendaLegado?.modalBackdrop){
      agendaLegado.modalBackdrop.dataset.origem="agenda-semana";
      delete agendaLegado.modalBackdrop.dataset.forceNovo;
      agendaLegado.modalBackdrop.dataset.prestadorId=String(Number(item?.id_prestador||agendaSemana?.selectPrestador?.value||sessaoAtual?.prestador_id||0)||0);
      agendaLegado.modalBackdrop.dataset.unidadeId=String(Number(item?.id_unidade||agendaSemana?.selectUnidade?.value||sessaoAtual?.unidade_atendimento_id||0)||0);
      agendaLegado.modalBackdrop.classList.remove("hidden");
    }
    if(typeof agendaLegadoAplicarFocoPorTipo==="function")agendaLegadoAplicarFocoPorTipo();
  };
  const agendaSemanaPesquisaIsCompromisso=(item)=>{
    const tipo=Number(item?.tipo);
    if(Number.isFinite(tipo)){
      if(tipo===2)return true;
      if(tipo===1)return false;
    }
    return !(Number(item?.nro_pac||0)||0);
  };
  const agendaSemanaPesquisaTextoLinha=(item)=>{
    const nome=String(item?.nome||"").trim();
    const motivo=String(item?.motivo||"").trim();
    return agendaSemanaPesquisaIsCompromisso(item)?(motivo||nome):(nome||motivo);
  };
  const agendaSemanaPesquisaDataBr=(valor)=>{
    const d=agendaSemanaParseDataCivil(String(valor||"").trim());
    if(!d)return String(valor||"").trim();
    return `${String(d.getDate()).padStart(2,"0")}/${String(d.getMonth()+1).padStart(2,"0")}/${d.getFullYear()}`;
  };
  const agendaSemanaPesquisaHora=(horaMs)=>{
    const ms=Math.max(0,Number(horaMs||0)||0);
    const totalMin=Math.floor(ms/60000);
    const h=Math.max(0,Math.floor(totalMin/60));
    const m=Math.max(0,totalMin%60);
    return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`;
  };
  const agendaSemanaPesquisaCirurgiaoNome=(idPrestador)=>{
    const id=Math.max(0,Number(idPrestador||0)||0);
    if(!id)return"";
    const item=(Array.isArray(agendaSemanaState?.prestadores)?agendaSemanaState.prestadores:[])
      .find(row=>Number(row?.id||0)===id);
    return String(item?.nome||"").trim();
  };
  const agendaSemanaPesquisaDataHoraMs=(item)=>{
    const d=agendaSemanaParseDataCivil(String(item?.data||"").trim());
    if(!d)return NaN;
    const ms=Math.max(0,Number(item?.hora_inicio||0)||0);
    const min=Math.floor(ms/60000);
    d.setHours(Math.floor(min/60),min%60,0,0);
    return d.getTime();
  };
  const agendaSemanaPesquisaFechar=()=>{
    if(!agendaSemanaPesquisa?.backdrop)return;
    agendaSemanaPesquisa.backdrop.classList.add("hidden");
  };
  const agendaSemanaPesquisaAtualizarBotoes=()=>{
    const cfg=agendaSemanaPesquisa;
    if(!cfg)return;
    const temTermo=String(cfg.input?.value||"").trim().length>0;
    if(cfg.btnPesquisar)cfg.btnPesquisar.disabled=!temTermo;
    const idx=Math.max(-1,Number(cfg.selectedIdx??-1));
    if(cfg.btnEditar)cfg.btnEditar.disabled=idx<0||idx>=cfg.results.length;
  };
  const agendaSemanaPesquisaSelecionarIndice=(idx,scroll=false)=>{
    const cfg=agendaSemanaPesquisa;
    if(!cfg)return;
    const total=cfg.results.length;
    if(!total){
      cfg.selectedIdx=-1;
      agendaSemanaPesquisaAtualizarBotoes();
      return;
    }
    const alvo=Math.max(0,Math.min(total-1,Number(idx||0)));
    cfg.selectedIdx=alvo;
    cfg.tbody.querySelectorAll("tr[data-idx]").forEach(row=>{
      const rowIdx=Number(row.dataset.idx||-1);
      row.classList.toggle("selected",rowIdx===alvo);
      if(rowIdx===alvo&&scroll)row.scrollIntoView({block:"nearest"});
    });
    agendaSemanaPesquisaAtualizarBotoes();
  };
  const agendaSemanaPesquisaRenderResultados=(rows)=>{
    const cfg=agendaSemanaPesquisa;
    if(!cfg)return;
    cfg.results=Array.isArray(rows)?rows:[];
    if(!cfg.results.length){
      cfg.selectedIdx=-1;
      cfg.tbody.innerHTML='<tr class="agenda-semana-pesquisa-empty"><td colspan="4"></td></tr>';
      agendaSemanaPesquisaAtualizarBotoes();
      return;
    }
    cfg.tbody.innerHTML=cfg.results.map((item,idx)=>{
      const dataTxt=agendaSemanaPesquisaDataBr(item?.data);
      const horaTxt=agendaSemanaPesquisaHora(item?.hora_inicio);
      const principalTxt=agendaSemanaPesquisaTextoLinha(item);
      const cirurgiaoTxt=agendaSemanaPesquisaCirurgiaoNome(item?.id_prestador);
      return `<tr data-idx="${idx}"><td>${esc(dataTxt)}</td><td>${esc(horaTxt)}</td><td>${esc(principalTxt)}</td><td>${esc(cirurgiaoTxt)}</td></tr>`;
    }).join("");
    agendaSemanaPesquisaSelecionarIndice(0,false);
  };
  const agendaSemanaPesquisaAbrirEdicaoSelecionada=()=>{
    const cfg=agendaSemanaPesquisa;
    if(!cfg)return;
    const idx=Math.max(0,Number(cfg.selectedIdx||0)||0);
    const item=cfg.results[idx]||null;
    if(!item)return;
    agendaSemanaPesquisaFechar();
    agendaSemanaState.selectedEventId=Number(item?.id||0)||null;
    agendaSemanaAbrirModalEditar(item);
  };
  const agendaSemanaPesquisaPesquisar=async()=>{
    const cfg=agendaSemanaPesquisa;
    if(!cfg)return;
    const termo=String(cfg.input?.value||"").trim();
    if(!termo){
      agendaSemanaPesquisaAtualizarBotoes();
      return;
    }
    const incluirFuturos=!!cfg.chkFuturos?.checked;
    const incluirPassados=!!cfg.chkPassados?.checked;
    if(!incluirFuturos&&!incluirPassados){
      return;
    }
    const hojeIso=agendaSemanaToIsoDate(new Date());
    const params=new URLSearchParams();
    if(incluirFuturos&&incluirPassados){
      params.set("start","1900-01-01");
      params.set("end","2100-12-31");
    }else if(incluirFuturos){
      params.set("start",hojeIso);
      params.set("end","2100-12-31");
    }else{
      params.set("start","1900-01-01");
      params.set("end",hojeIso);
    }
    const prestador=String(agendaSemana?.selectPrestador?.value||"").trim();
    const unidade=String(agendaSemana?.selectUnidade?.value||"").trim();
    if(prestador)params.set("prestador_id",prestador);
    if(unidade)params.set("unidade_id",unidade);
    params.set("nome",termo);
    params.set("limit","10000");
    if(cfg.btnPesquisar)cfg.btnPesquisar.disabled=true;
    const {res,data}=await requestJson("GET",`/agenda-legado?${params.toString()}`,undefined,true);
    agendaSemanaPesquisaAtualizarBotoes();
    if(!res.ok){
      footerMsg.textContent=data?.detail||"Falha ao pesquisar agendamentos.";
      return;
    }
    const permitirPacientes=!!cfg.chkPacientes?.checked;
    const permitirCompromissos=!!cfg.chkCompromissos?.checked;
    const nowMs=Date.now();
    const rows=(Array.isArray(data)?data:[]).filter(item=>{
      const compromisso=agendaSemanaPesquisaIsCompromisso(item);
      if(compromisso&&!permitirCompromissos)return false;
      if(!compromisso&&!permitirPacientes)return false;
      if(incluirFuturos!==incluirPassados){
        const dataHoraMs=agendaSemanaPesquisaDataHoraMs(item);
        if(Number.isFinite(dataHoraMs)){
          if(incluirFuturos&&dataHoraMs<nowMs)return false;
          if(incluirPassados&&dataHoraMs>=nowMs)return false;
        }
      }
      return true;
    });
    agendaSemanaPesquisaRenderResultados(rows);
  };
  const agendaSemanaPesquisaVincularEventos=()=>{
    const cfg=agendaSemanaPesquisa;
    if(!cfg||cfg.bound)return;
    cfg.bound=true;
    cfg.input.addEventListener("input",()=>agendaSemanaPesquisaAtualizarBotoes());
    cfg.input.addEventListener("keydown",ev=>{
      if(ev.key==="Enter"){
        ev.preventDefault();
        agendaSemanaPesquisaPesquisar();
      }
    });
    cfg.btnPesquisar.addEventListener("click",agendaSemanaPesquisaPesquisar);
    [cfg.chkFuturos,cfg.chkPassados,cfg.chkPacientes,cfg.chkCompromissos].forEach(el=>{
      if(el)el.addEventListener("change",()=>agendaSemanaPesquisaAtualizarBotoes());
    });
    cfg.btnEditar.addEventListener("click",agendaSemanaPesquisaAbrirEdicaoSelecionada);
    cfg.btnFechar.addEventListener("click",agendaSemanaPesquisaFechar);
    cfg.backdrop.addEventListener("click",ev=>{
      if(ev.target===cfg.backdrop)agendaSemanaPesquisaFechar();
    });
    cfg.tbody.addEventListener("click",ev=>{
      const tr=ev.target.closest("tr[data-idx]");
      if(!tr)return;
      agendaSemanaPesquisaSelecionarIndice(Number(tr.dataset.idx||0),false);
    });
    cfg.tbody.addEventListener("dblclick",ev=>{
      const tr=ev.target.closest("tr[data-idx]");
      if(!tr)return;
      agendaSemanaPesquisaSelecionarIndice(Number(tr.dataset.idx||0),false);
      agendaSemanaPesquisaAbrirEdicaoSelecionada();
    });
    cfg.modal.addEventListener("keydown",ev=>{
      if(ev.key==="Escape"){
        ev.preventDefault();
        agendaSemanaPesquisaFechar();
        return;
      }
      if(ev.key==="ArrowDown"||ev.key==="ArrowUp"){
        if(!cfg.results.length)return;
        ev.preventDefault();
        const delta=ev.key==="ArrowDown"?1:-1;
        const atual=Math.max(-1,Number(cfg.selectedIdx??-1));
        agendaSemanaPesquisaSelecionarIndice((atual<0?0:atual)+delta,true);
        return;
      }
      if(ev.key==="Enter"&&ev.target!==cfg.input&&cfg.selectedIdx>=0){
        ev.preventDefault();
        agendaSemanaPesquisaAbrirEdicaoSelecionada();
      }
    });
  };
  const agendaSemanaPesquisaEnsureUI=()=>{
    if(agendaSemanaPesquisa?.backdrop)return agendaSemanaPesquisa;
    if(!document.getElementById("agenda-semana-pesquisa-style")){
      const style=document.createElement("style");
      style.id="agenda-semana-pesquisa-style";
      style.textContent=`
        .agenda-semana-pesquisa-backdrop{position:fixed;inset:0;z-index:2700;background:rgba(0,0,0,.18);display:grid;place-items:center}
        .agenda-semana-pesquisa-backdrop.hidden{display:none}
        .agenda-semana-pesquisa-modal{width:min(560px,96vw);background:#efefef;border:1px solid #b9b9b9;box-shadow:2px 2px 10px rgba(0,0,0,.25);padding:8px;box-sizing:border-box;font:12px Tahoma,sans-serif}
        .agenda-semana-pesquisa-title{font:400 33px/1 "Segoe UI Symbol","Arial Unicode MS",Tahoma,sans-serif;text-align:center;letter-spacing:0;transform:translateY(-1px) scaleX(.72);transform-origin:center;margin:2px 0 8px;color:#2d2d2d}
        .agenda-semana-pesquisa-box{border:1px solid #c3c3c3;padding:8px;background:#efefef}
        .agenda-semana-pesquisa-row{display:flex;align-items:center;gap:8px;margin-top:4px}
        .agenda-semana-pesquisa-row input[type="text"]{flex:1;height:24px;border:1px solid #bfc9d6;padding:0 6px;box-sizing:border-box;background:#fff}
        .agenda-semana-pesquisa-row .materiais-btn{height:24px;min-width:92px;justify-content:center}
        .agenda-semana-pesquisa-subtitle{margin-top:10px;margin-bottom:2px}
        .agenda-semana-pesquisa-checks{display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;margin-bottom:8px}
        .agenda-semana-pesquisa-checks label{display:flex;align-items:center;gap:5px}
        .agenda-semana-pesquisa-grid{border:1px solid #c0c9d6;background:#fff;height:192px;overflow:auto}
        .agenda-semana-pesquisa-grid table{width:100%;border-collapse:collapse;table-layout:fixed}
        .agenda-semana-pesquisa-grid th,.agenda-semana-pesquisa-grid td{height:22px;padding:2px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-bottom:1px solid #edf1f6}
        .agenda-semana-pesquisa-grid th{background:#f2f6fb;font:700 12px Tahoma,sans-serif;text-align:left}
        .agenda-semana-pesquisa-grid tr.selected{background:#1f66c2;color:#fff}
        .agenda-semana-pesquisa-grid tr.agenda-semana-pesquisa-empty td{height:168px;border-bottom:none}
        .agenda-semana-pesquisa-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:8px}
        .agenda-semana-pesquisa-actions .materiais-btn{min-width:92px;justify-content:center}
      `;
      document.head.appendChild(style);
    }
    const backdrop=document.createElement("div");
    backdrop.className="agenda-semana-pesquisa-backdrop hidden";
    backdrop.innerHTML=`
      <div class="agenda-semana-pesquisa-modal" role="dialog" aria-modal="true" tabindex="0">
        <div class="agenda-semana-pesquisa-title">Pesquisa agendamentos</div>
        <div class="agenda-semana-pesquisa-box">
          <label for="agenda-semana-pesquisa-termo">Texto a ser pesquisado (nome ou assunto):</label>
          <div class="agenda-semana-pesquisa-row">
            <input id="agenda-semana-pesquisa-termo" type="text" autocomplete="off">
            <button id="agenda-semana-pesquisa-btn" class="materiais-btn" type="button" disabled>Pesquisa</button>
          </div>
          <div class="agenda-semana-pesquisa-subtitle">Opcoes de pesquisa:</div>
          <div class="agenda-semana-pesquisa-checks">
            <label><input id="agenda-semana-pesquisa-futuros" type="checkbox" checked> Agendamentos futuros</label>
            <label><input id="agenda-semana-pesquisa-pacientes" type="checkbox" checked> Pesquisar pacientes</label>
            <label><input id="agenda-semana-pesquisa-passados" type="checkbox" checked> Agendamentos passados</label>
            <label><input id="agenda-semana-pesquisa-compromissos" type="checkbox" checked> Pesquisar compromissos</label>
          </div>
          <div class="agenda-semana-pesquisa-grid">
            <table>
              <colgroup>
                <col style="width:100px">
                <col style="width:68px">
                <col>
                <col style="width:120px">
              </colgroup>
              <thead><tr><th>Data</th><th>Hora</th><th>Paciente / compromisso</th><th>Cirurgiao</th></tr></thead>
              <tbody id="agenda-semana-pesquisa-tbody"></tbody>
            </table>
          </div>
        </div>
        <div class="agenda-semana-pesquisa-actions">
          <button id="agenda-semana-pesquisa-edita" class="materiais-btn" type="button" disabled>Edita...</button>
          <button id="agenda-semana-pesquisa-fecha" class="materiais-btn" type="button">Fecha</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    agendaSemanaPesquisa={
      backdrop,
      modal:backdrop.querySelector(".agenda-semana-pesquisa-modal"),
      input:backdrop.querySelector("#agenda-semana-pesquisa-termo"),
      btnPesquisar:backdrop.querySelector("#agenda-semana-pesquisa-btn"),
      chkFuturos:backdrop.querySelector("#agenda-semana-pesquisa-futuros"),
      chkPassados:backdrop.querySelector("#agenda-semana-pesquisa-passados"),
      chkPacientes:backdrop.querySelector("#agenda-semana-pesquisa-pacientes"),
      chkCompromissos:backdrop.querySelector("#agenda-semana-pesquisa-compromissos"),
      tbody:backdrop.querySelector("#agenda-semana-pesquisa-tbody"),
      btnEditar:backdrop.querySelector("#agenda-semana-pesquisa-edita"),
      btnFechar:backdrop.querySelector("#agenda-semana-pesquisa-fecha"),
      results:[],
      selectedIdx:-1,
      bound:false,
    };
    agendaSemanaPesquisaVincularEventos();
    agendaSemanaPesquisaRenderResultados([]);
    return agendaSemanaPesquisa;
  };
  const agendaSemanaPesquisaAbrir=()=>{
    const cfg=agendaSemanaPesquisaEnsureUI();
    cfg.input.value="";
    cfg.chkFuturos.checked=true;
    cfg.chkPassados.checked=true;
    cfg.chkPacientes.checked=true;
    cfg.chkCompromissos.checked=true;
    agendaSemanaPesquisaRenderResultados([]);
    agendaSemanaPesquisaAtualizarBotoes();
    cfg.backdrop.classList.remove("hidden");
    requestAnimationFrame(()=>{
      cfg.input.focus();
      cfg.input.select();
    });
  };

  const agendaSemanaHorariosToDataBr=(iso)=>{
    const d=agendaSemanaParseDataCivil(String(iso||"").trim());
    if(!d)return String(iso||"").trim();
    return `${String(d.getDate()).padStart(2,"0")}/${String(d.getMonth()+1).padStart(2,"0")}/${d.getFullYear()}`;
  };
  const agendaSemanaHorariosNormalizarHora=(value)=>{
    const bruto=String(value||"").trim();
    if(!bruto)return"";
    const m=/^(\d{1,2}):(\d{2})$/.exec(bruto);
    if(m){
      const h=Number(m[1]);
      const min=Number(m[2]);
      if(Number.isFinite(h)&&Number.isFinite(min)&&h>=0&&h<=23&&min>=0&&min<=59){
        return `${String(h).padStart(2,"0")}:${String(min).padStart(2,"0")}`;
      }
    }
    const dig=bruto.replace(/\D+/g,"");
    if(dig.length===3||dig.length===4){
      const pad=dig.padStart(4,"0");
      const h=Number(pad.slice(0,2));
      const min=Number(pad.slice(2,4));
      if(Number.isFinite(h)&&Number.isFinite(min)&&h>=0&&h<=23&&min>=0&&min<=59){
        return `${String(h).padStart(2,"0")}:${String(min).padStart(2,"0")}`;
      }
    }
    return"";
  };
  const agendaSemanaHorariosMs=(hhmm)=>{
    const txt=agendaSemanaHorariosNormalizarHora(hhmm);
    if(!txt)return NaN;
    const[h,m]=txt.split(":").map(v=>Number(v)||0);
    return(h*60+m)*60000;
  };
  const agendaSemanaHorariosCirurgiaoNome=(id)=>{
    const n=Number(id||0)||0;
    if(!n)return"";
    const item=(Array.isArray(agendaSemanaState?.prestadores)?agendaSemanaState.prestadores:[])
      .find(row=>Number(row?.id||0)===n);
    return String(item?.nome||"").trim();
  };
  const agendaSemanaHorariosFechar=()=>{
    if(!agendaSemanaHorariosLivres?.backdrop)return;
    agendaSemanaHorariosLivres.backdrop.classList.add("hidden");
  };
  const agendaSemanaHorariosSelecionarIndice=(idx,scroll=false)=>{
    const cfg=agendaSemanaHorariosLivres;
    if(!cfg)return;
    const total=cfg.results.length;
    if(!total){
      cfg.selectedIdx=-1;
      return;
    }
    const alvo=Math.max(0,Math.min(total-1,Number(idx||0)));
    cfg.selectedIdx=alvo;
    cfg.tbody.querySelectorAll("tr[data-idx]").forEach(row=>{
      const rowIdx=Number(row.dataset.idx||-1);
      row.classList.toggle("selected",rowIdx===alvo);
      if(rowIdx===alvo&&scroll)row.scrollIntoView({block:"nearest"});
    });
  };
  const agendaSemanaHorariosAtualizarBotoes=()=>{
    const cfg=agendaSemanaHorariosLivres;
    if(!cfg)return;
    const temDia=cfg.chkDias.some(chk=>!!chk?.checked);
    const horaIni=agendaSemanaHorariosNormalizarHora(cfg.horaIni?.value||"");
    const horaFim=agendaSemanaHorariosNormalizarHora(cfg.horaFim?.value||"");
    const msIni=agendaSemanaHorariosMs(horaIni);
    const msFim=agendaSemanaHorariosMs(horaFim);
    const periodoLigado=!!cfg.chkPeriodo?.checked;
    if(cfg.dataIni)cfg.dataIni.disabled=!periodoLigado;
    if(cfg.dataFim)cfg.dataFim.disabled=!periodoLigado;
    const periodoOk=!periodoLigado||(
      String(cfg.dataIni?.value||"").trim().length>0&&
      String(cfg.dataFim?.value||"").trim().length>0&&
      String(cfg.dataFim?.value||"").trim()>=String(cfg.dataIni?.value||"").trim()
    );
    const horasOk=Number.isFinite(msIni)&&Number.isFinite(msFim)&&msFim>msIni;
    if(cfg.btnPesquisar)cfg.btnPesquisar.disabled=!(temDia&&horasOk&&periodoOk);
    if(cfg.btnEditar)cfg.btnEditar.disabled=cfg.selectedIdx<0||cfg.selectedIdx>=cfg.results.length;
  };
  const agendaSemanaHorariosRenderResultados=(rows)=>{
    const cfg=agendaSemanaHorariosLivres;
    if(!cfg)return;
    cfg.results=Array.isArray(rows)?rows:[];
    cfg.selectedIdx=-1;
    if(!cfg.results.length){
      cfg.tbody.innerHTML='<tr class="agenda-semana-horarios-empty"><td colspan="5"></td></tr>';
      agendaSemanaHorariosAtualizarBotoes();
      return;
    }
    cfg.tbody.innerHTML=cfg.results.map((item,idx)=>{
      const dataTxt=agendaSemanaHorariosToDataBr(item?.data);
      const diaTxt=String(item?.dia||"").trim();
      const horaTxt=agendaSemanaHorariosNormalizarHora(item?.hora||"");
      const durPadrao=Math.max(5,parseInt(agendaSemanaState?.step||5,10)||5);
      const durTxt=String(durPadrao);
      const cirTxt=String(item?.cirurgiao||agendaSemanaHorariosCirurgiaoNome(item?.id_prestador)||"").trim();
      return `<tr data-idx="${idx}"><td>${esc(dataTxt)}</td><td>${esc(diaTxt)}</td><td>${esc(horaTxt)}</td><td>${esc(durTxt)}</td><td>${esc(cirTxt)}</td></tr>`;
    }).join("");
    agendaSemanaHorariosSelecionarIndice(0,false);
    agendaSemanaHorariosAtualizarBotoes();
  };
  const agendaSemanaHorariosAbrirNovoSelecionado=()=>{
    const cfg=agendaSemanaHorariosLivres;
    if(!cfg)return;
    const idx=Math.max(0,Number(cfg.selectedIdx||0)||0);
    const row=cfg.results[idx]||null;
    if(!row)return;
    const prestadorId=String(Number(row?.id_prestador||0)||"");
    const unidadeId=String(Number(row?.id_unidade||0)||"");
    if(prestadorId&&agendaSemana?.selectPrestador&&[...agendaSemana.selectPrestador.options].some(opt=>opt.value===prestadorId)){
      agendaSemana.selectPrestador.value=prestadorId;
      if(typeof agendaSemanaSaveFiltro==="function")agendaSemanaSaveFiltro("prestador_id",prestadorId);
    }
    if(unidadeId&&agendaSemana?.selectUnidade&&[...agendaSemana.selectUnidade.options].some(opt=>opt.value===unidadeId)){
      agendaSemana.selectUnidade.value=unidadeId;
      if(typeof agendaSemanaSaveFiltro==="function")agendaSemanaSaveFiltro("unidade_id",unidadeId);
    }
    agendaSemanaHorariosFechar();
    agendaSemanaAbrirModalNovo(String(row?.data||""),String(row?.hora||""));
  };
  const agendaSemanaHorariosPesquisar=async()=>{
    const cfg=agendaSemanaHorariosLivres;
    if(!cfg)return;
    const dias=cfg.chkDias.filter(chk=>chk.checked).map(chk=>String(chk.value||"").trim()).filter(Boolean);
    if(!dias.length){
      agendaSemanaHorariosRenderResultados([]);
      return;
    }
    const horaIni=agendaSemanaHorariosNormalizarHora(cfg.horaIni?.value||"");
    const horaFim=agendaSemanaHorariosNormalizarHora(cfg.horaFim?.value||"");
    if(!horaIni||!horaFim||agendaSemanaHorariosMs(horaFim)<=agendaSemanaHorariosMs(horaIni)){
      agendaSemanaHorariosAtualizarBotoes();
      return;
    }
    cfg.horaIni.value=horaIni;
    cfg.horaFim.value=horaFim;
    const params=new URLSearchParams();
    params.set("dias_semana",dias.join(","));
    params.set("hora_inicio",horaIni);
    params.set("hora_fim",horaFim);
    const prestador=String(cfg.prestador?.value||agendaSemana?.selectPrestador?.value||"").trim();
    const unidade=String(cfg.unidade?.value||agendaSemana?.selectUnidade?.value||"").trim();
    if(prestador)params.set("prestador_id",prestador);
    if(unidade)params.set("unidade_id",unidade);
    if(cfg.chkPeriodo?.checked){
      const ini=String(cfg.dataIni?.value||"").trim();
      const fim=String(cfg.dataFim?.value||"").trim();
      if(ini)params.set("data_ini",ini);
      if(fim)params.set("data_fim",fim);
    }
    params.set("limit","5000");
    if(cfg.btnPesquisar)cfg.btnPesquisar.disabled=true;
    const {res,data}=await requestJson("GET",`/agenda-legado/horarios-livres?${params.toString()}`,undefined,true);
    agendaSemanaHorariosAtualizarBotoes();
    if(!res.ok){
      footerMsg.textContent=data?.detail||"Falha ao pesquisar horarios livres.";
      return;
    }
    agendaSemanaHorariosRenderResultados(Array.isArray(data)?data:[]);
  };
  const agendaSemanaHorariosVincularEventos=()=>{
    const cfg=agendaSemanaHorariosLivres;
    if(!cfg||cfg.bound)return;
    cfg.bound=true;
    cfg.chkDias.forEach(chk=>chk.addEventListener("change",agendaSemanaHorariosAtualizarBotoes));
    cfg.chkPeriodo.addEventListener("change",agendaSemanaHorariosAtualizarBotoes);
    [cfg.horaIni,cfg.horaFim,cfg.dataIni,cfg.dataFim,cfg.prestador,cfg.unidade].forEach(el=>{
      if(el)el.addEventListener("change",agendaSemanaHorariosAtualizarBotoes);
    });
    [cfg.horaIni,cfg.horaFim].forEach(el=>{
      if(!el)return;
      el.addEventListener("blur",()=>{
        const normal=agendaSemanaHorariosNormalizarHora(el.value);
        if(normal)el.value=normal;
        agendaSemanaHorariosAtualizarBotoes();
      });
    });
    cfg.btnPesquisar.addEventListener("click",agendaSemanaHorariosPesquisar);
    cfg.btnEditar.addEventListener("click",agendaSemanaHorariosAbrirNovoSelecionado);
    cfg.btnFechar.addEventListener("click",agendaSemanaHorariosFechar);
    cfg.backdrop.addEventListener("click",ev=>{
      if(ev.target===cfg.backdrop)agendaSemanaHorariosFechar();
    });
    cfg.tbody.addEventListener("click",ev=>{
      const tr=ev.target.closest("tr[data-idx]");
      if(!tr)return;
      agendaSemanaHorariosSelecionarIndice(Number(tr.dataset.idx||0),false);
      agendaSemanaHorariosAtualizarBotoes();
    });
    cfg.tbody.addEventListener("dblclick",ev=>{
      const tr=ev.target.closest("tr[data-idx]");
      if(!tr)return;
      agendaSemanaHorariosSelecionarIndice(Number(tr.dataset.idx||0),false);
      agendaSemanaHorariosAbrirNovoSelecionado();
    });
    cfg.modal.addEventListener("keydown",ev=>{
      if(ev.key==="Escape"){
        ev.preventDefault();
        agendaSemanaHorariosFechar();
        return;
      }
      if(ev.key==="ArrowDown"||ev.key==="ArrowUp"){
        if(!cfg.results.length)return;
        ev.preventDefault();
        const delta=ev.key==="ArrowDown"?1:-1;
        const atual=Math.max(-1,Number(cfg.selectedIdx??-1));
        agendaSemanaHorariosSelecionarIndice((atual<0?0:atual)+delta,true);
        agendaSemanaHorariosAtualizarBotoes();
        return;
      }
      if(ev.key==="Enter"&&ev.target!==cfg.horaIni&&ev.target!==cfg.horaFim&&cfg.selectedIdx>=0){
        ev.preventDefault();
        agendaSemanaHorariosAbrirNovoSelecionado();
      }
    });
  };
  const agendaSemanaHorariosPreencherCombos=()=>{
    const cfg=agendaSemanaHorariosLivres;
    if(!cfg)return;
    const prestadores=Array.isArray(agendaSemanaState?.prestadores)?agendaSemanaState.prestadores:[];
    const unidades=Array.isArray(agendaSemanaState?.unidades)?agendaSemanaState.unidades:[];
    const prestadorAtual=String(agendaSemana?.selectPrestador?.value||sessaoAtual?.prestador_id||"").trim();
    const unidadeAtual=String(agendaSemana?.selectUnidade?.value||sessaoAtual?.unidade_atendimento_id||"").trim();
    cfg.prestador.innerHTML=prestadores.map(item=>`<option value="${esc(String(item?.id||""))}">${esc(String(item?.nome||"").trim())}</option>`).join("");
    cfg.unidade.innerHTML=unidades.map(item=>`<option value="${esc(String(item?.id||""))}">${esc(String(item?.nome||"").trim())}</option>`).join("");
    if(prestadorAtual&&[...cfg.prestador.options].some(opt=>opt.value===prestadorAtual))cfg.prestador.value=prestadorAtual;
    else if(cfg.prestador.options.length)cfg.prestador.selectedIndex=0;
    if(unidadeAtual&&[...cfg.unidade.options].some(opt=>opt.value===unidadeAtual))cfg.unidade.value=unidadeAtual;
    else if(cfg.unidade.options.length)cfg.unidade.selectedIndex=0;
  };
  const agendaSemanaHorariosEnsureUI=()=>{
    if(agendaSemanaHorariosLivres?.backdrop)return agendaSemanaHorariosLivres;
    if(!document.getElementById("agenda-semana-horarios-style")){
      const style=document.createElement("style");
      style.id="agenda-semana-horarios-style";
      style.textContent=`
        .agenda-semana-horarios-backdrop{position:fixed;inset:0;z-index:2700;background:rgba(0,0,0,.18);display:grid;place-items:center}
        .agenda-semana-horarios-backdrop.hidden{display:none}
        .agenda-semana-horarios-modal{width:min(640px,96vw);background:#efefef;border:1px solid #b9b9b9;box-shadow:2px 2px 10px rgba(0,0,0,.25);padding:8px;box-sizing:border-box;font:12px Tahoma,sans-serif}
        .agenda-semana-horarios-title{font:400 33px/1 "Segoe UI Symbol","Arial Unicode MS",Tahoma,sans-serif;text-align:center;transform:translateY(-1px) scaleX(.72);transform-origin:center;margin:2px 0 8px;color:#2d2d2d}
        .agenda-semana-horarios-box{border:1px solid #c3c3c3;padding:8px;background:#efefef}
        .agenda-semana-horarios-top{display:grid;grid-template-columns:140px 1fr;gap:8px}
        .agenda-semana-horarios-dias{border:1px solid #c6c6c6;padding:6px;background:#efefef}
        .agenda-semana-horarios-dias-title{margin-bottom:4px;font-weight:700}
        .agenda-semana-horarios-dias label{display:flex;align-items:center;gap:5px;line-height:19px}
        .agenda-semana-horarios-filtros{display:grid;grid-template-columns:auto 1fr;gap:6px 8px;align-items:center}
        .agenda-semana-horarios-filtros label{white-space:nowrap}
        .agenda-semana-horarios-filtros select,.agenda-semana-horarios-filtros input[type="text"],.agenda-semana-horarios-filtros input[type="date"]{height:24px;border:1px solid #bfc9d6;padding:0 6px;box-sizing:border-box;background:#fff;font:12px Tahoma,sans-serif}
        .agenda-semana-horarios-linha-hora{display:flex;align-items:center;gap:6px}
        .agenda-semana-horarios-linha-hora input{width:64px}
        .agenda-semana-horarios-linha-periodo{display:flex;align-items:center;gap:6px}
        .agenda-semana-horarios-linha-periodo input[type="date"]{width:136px}
        .agenda-semana-horarios-btn-wrap{display:flex;justify-content:flex-end}
        .agenda-semana-horarios-btn-wrap .materiais-btn{height:24px;min-width:92px;justify-content:center}
        .agenda-semana-horarios-grid{border:1px solid #c0c9d6;background:#fff;height:214px;overflow:auto;margin-top:8px}
        .agenda-semana-horarios-grid table{width:100%;border-collapse:collapse;table-layout:fixed}
        .agenda-semana-horarios-grid th,.agenda-semana-horarios-grid td{height:22px;padding:2px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-bottom:1px solid #edf1f6}
        .agenda-semana-horarios-grid th{background:#f2f6fb;font:700 12px Tahoma,sans-serif;text-align:left}
        .agenda-semana-horarios-grid tr.selected{background:#1f66c2;color:#fff}
        .agenda-semana-horarios-grid tr.agenda-semana-horarios-empty td{height:190px;border-bottom:none}
        .agenda-semana-horarios-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:8px}
        .agenda-semana-horarios-actions .materiais-btn{min-width:92px;justify-content:center}
      `;
      document.head.appendChild(style);
    }
    const backdrop=document.createElement("div");
    backdrop.className="agenda-semana-horarios-backdrop hidden";
    backdrop.innerHTML=`
      <div class="agenda-semana-horarios-modal" role="dialog" aria-modal="true" tabindex="0">
        <div class="agenda-semana-horarios-title">Pesquisa horarios livres</div>
        <div class="agenda-semana-horarios-box">
          <div class="agenda-semana-horarios-top">
            <div class="agenda-semana-horarios-dias">
              <div class="agenda-semana-horarios-dias-title">Dias da semana:</div>
              <label><input id="agenda-semana-hl-dia-1" type="checkbox" value="1" checked> Segunda</label>
              <label><input id="agenda-semana-hl-dia-2" type="checkbox" value="2" checked> Terca</label>
              <label><input id="agenda-semana-hl-dia-3" type="checkbox" value="3" checked> Quarta</label>
              <label><input id="agenda-semana-hl-dia-4" type="checkbox" value="4" checked> Quinta</label>
              <label><input id="agenda-semana-hl-dia-5" type="checkbox" value="5" checked> Sexta</label>
              <label><input id="agenda-semana-hl-dia-6" type="checkbox" value="6" checked> Sabado</label>
            </div>
            <div class="agenda-semana-horarios-filtros">
              <label for="agenda-semana-hl-prestador">Cirurgiao:</label>
              <select id="agenda-semana-hl-prestador"></select>
              <label for="agenda-semana-hl-unidade">Unidade:</label>
              <select id="agenda-semana-hl-unidade"></select>
              <label for="agenda-semana-hl-hora-ini">Horario entre:</label>
              <div class="agenda-semana-horarios-linha-hora">
                <input id="agenda-semana-hl-hora-ini" type="text" maxlength="5" value="07:00">
                <span>e</span>
                <input id="agenda-semana-hl-hora-fim" type="text" maxlength="5" value="20:00">
              </div>
              <label for="agenda-semana-hl-data-ini"><input id="agenda-semana-hl-periodo" type="checkbox"> Periodo entre:</label>
              <div class="agenda-semana-horarios-linha-periodo">
                <input id="agenda-semana-hl-data-ini" type="date" disabled>
                <span>e</span>
                <input id="agenda-semana-hl-data-fim" type="date" disabled>
              </div>
              <div></div>
              <div class="agenda-semana-horarios-btn-wrap">
                <button id="agenda-semana-hl-pesquisar" class="materiais-btn" type="button">Pesquisa</button>
              </div>
            </div>
          </div>
          <div class="agenda-semana-horarios-grid">
            <table>
              <colgroup>
                <col style="width:98px">
                <col style="width:84px">
                <col style="width:78px">
                <col style="width:82px">
                <col>
              </colgroup>
              <thead><tr><th>Data</th><th>Dia</th><th>Hora</th><th>Duração</th><th>Cirurgião</th></tr></thead>
              <tbody id="agenda-semana-hl-tbody"></tbody>
            </table>
          </div>
        </div>
        <div class="agenda-semana-horarios-actions">
          <button id="agenda-semana-hl-editar" class="materiais-btn" type="button" disabled>Edita...</button>
          <button id="agenda-semana-hl-fechar" class="materiais-btn" type="button">Fecha</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    agendaSemanaHorariosLivres={
      backdrop,
      modal:backdrop.querySelector(".agenda-semana-horarios-modal"),
      chkDias:[1,2,3,4,5,6].map(n=>backdrop.querySelector(`#agenda-semana-hl-dia-${n}`)).filter(Boolean),
      prestador:backdrop.querySelector("#agenda-semana-hl-prestador"),
      unidade:backdrop.querySelector("#agenda-semana-hl-unidade"),
      horaIni:backdrop.querySelector("#agenda-semana-hl-hora-ini"),
      horaFim:backdrop.querySelector("#agenda-semana-hl-hora-fim"),
      chkPeriodo:backdrop.querySelector("#agenda-semana-hl-periodo"),
      dataIni:backdrop.querySelector("#agenda-semana-hl-data-ini"),
      dataFim:backdrop.querySelector("#agenda-semana-hl-data-fim"),
      btnPesquisar:backdrop.querySelector("#agenda-semana-hl-pesquisar"),
      tbody:backdrop.querySelector("#agenda-semana-hl-tbody"),
      btnEditar:backdrop.querySelector("#agenda-semana-hl-editar"),
      btnFechar:backdrop.querySelector("#agenda-semana-hl-fechar"),
      results:[],
      selectedIdx:-1,
      bound:false,
    };
    agendaSemanaHorariosVincularEventos();
    agendaSemanaHorariosRenderResultados([]);
    return agendaSemanaHorariosLivres;
  };
  const agendaSemanaHorariosAbrir=()=>{
    const cfg=agendaSemanaHorariosEnsureUI();
    agendaSemanaHorariosPreencherCombos();
    cfg.chkDias.forEach(chk=>{chk.checked=true});
    cfg.chkPeriodo.checked=false;
    cfg.dataIni.value="";
    cfg.dataFim.value="";
    const prestSel=(Array.isArray(agendaSemanaState?.prestadores)?agendaSemanaState.prestadores:[])
      .find(item=>Number(item?.id||0)===Number(cfg.prestador?.value||0));
    const agendaCfg=agendaSemanaNormalizaConfig(prestSel?.agenda_config||{});
    const horaIni=agendaSemanaHorariosNormalizarHora(agendaCfg?.manha_inicio||"07:00")||"07:00";
    const horaFim=agendaSemanaHorariosNormalizarHora(agendaCfg?.tarde_fim||"20:00")||"20:00";
    cfg.horaIni.value=horaIni;
    cfg.horaFim.value=horaFim;
    agendaSemanaHorariosRenderResultados([]);
    agendaSemanaHorariosAtualizarBotoes();
    cfg.backdrop.classList.remove("hidden");
    requestAnimationFrame(()=>{try{cfg.horaIni.focus();cfg.horaIni.select()}catch{}});
  };
  const agendaSemanaAvisoDataBr=(iso)=>{
    const d=agendaSemanaParseDataCivil(String(iso||"").trim());
    if(!d)return String(iso||"").trim();
    return `${String(d.getDate()).padStart(2,"0")}/${String(d.getMonth()+1).padStart(2,"0")}/${d.getFullYear()}`;
  };
  const agendaSemanaAvisoTipoAtual=()=>String(agendaSemanaAviso?.tipo?.value||"email").trim().toLowerCase()==="whatsapp"?"whatsapp":"email";
  const agendaSemanaAvisoFechar=()=>{
    if(!agendaSemanaAviso?.backdrop)return;
    agendaSemanaAviso.backdrop.classList.add("hidden");
  };
  const agendaSemanaAvisoAtualizarColunaContato=()=>{
    if(!agendaSemanaAviso)return;
    if(agendaSemanaAviso.thContato)agendaSemanaAviso.thContato.textContent=agendaSemanaAvisoTipoAtual()==="whatsapp"?"WhatsApp":"E-mail";
  };
  const agendaSemanaAvisoAtualizarBotoes=()=>{
    if(!agendaSemanaAviso)return;
    const ini=String(agendaSemanaAviso.dataIni?.value||"").trim();
    const fim=String(agendaSemanaAviso.dataFim?.value||"").trim();
    const podePesquisar=!!ini&&!!fim&&fim>=ini&&String(agendaSemanaAviso.modelo?.value||"").trim().length>0;
    if(agendaSemanaAviso.btnPesquisar)agendaSemanaAviso.btnPesquisar.disabled=!podePesquisar;
    const marcados=(Array.isArray(agendaSemanaAviso.rows)?agendaSemanaAviso.rows:[]).some(row=>!!row?.ok);
    if(agendaSemanaAviso.btnOk)agendaSemanaAviso.btnOk.disabled=!marcados;
  };
  const agendaSemanaAvisoRenderRows=(rows)=>{
    if(!agendaSemanaAviso)return;
    agendaSemanaAviso.rows=(Array.isArray(rows)?rows:[]).map(row=>({...row,ok:row?.ok!==false}));
    agendaSemanaAviso.selectedIdx=agendaSemanaAviso.rows.length?0:-1;
    agendaSemanaAviso.tbody.innerHTML=agendaSemanaAviso.rows.map((row,idx)=>{
      const selected=idx===agendaSemanaAviso.selectedIdx?" selected":"";
      const okMark=row?.ok?"✔":"";
      return `<tr data-idx="${idx}" class="${selected}"><td>${esc(agendaSemanaAvisoDataBr(row?.data))}</td><td>${esc(String(row?.hora||""))}</td><td>${esc(String(row?.paciente||""))}</td><td>${esc(String(row?.contato||""))}</td><td class="agenda-semana-aviso-ok-cell">${esc(okMark)}</td></tr>`;
    }).join("")||'<tr class="agenda-semana-aviso-empty"><td colspan="5"></td></tr>';
    agendaSemanaAvisoAtualizarColunaContato();
    agendaSemanaAvisoAtualizarBotoes();
  };
  const agendaSemanaAvisoRecarregarModelos=()=>{
    if(!agendaSemanaAviso)return;
    const tipo=agendaSemanaAvisoTipoAtual();
    const modelos=(agendaSemanaAviso.opcoes?.modelos?.[tipo]||[]);
    const atual=String(agendaSemanaAviso.modelo.value||"").trim();
    agendaSemanaAviso.modelo.innerHTML=modelos.map(item=>`<option value="${esc(String(item?.id||""))}">${esc(String(item?.nome||""))}</option>`).join("");
    if(atual&&[...agendaSemanaAviso.modelo.options].some(opt=>opt.value===atual)){
      agendaSemanaAviso.modelo.value=atual;
    }else{
      const defaults=agendaSemanaAviso.opcoes?.defaults||{};
      const def=String(tipo==="whatsapp"?defaults?.whatsapp_modelo_id||"":defaults?.email_modelo_id||"");
      if(def&&[...agendaSemanaAviso.modelo.options].some(opt=>opt.value===def))agendaSemanaAviso.modelo.value=def;
      else if(agendaSemanaAviso.modelo.options.length)agendaSemanaAviso.modelo.selectedIndex=0;
    }
    agendaSemanaAvisoAtualizarColunaContato();
    agendaSemanaAvisoAtualizarBotoes();
  };
  const agendaSemanaAvisoCarregarOpcoes=async()=>{
    if(!agendaSemanaAviso)return false;
    const {res,data}=await requestJson("GET","/agenda-legado/avisos-agendamento/opcoes",undefined,true);
    if(!res.ok){
      window.alert(data?.detail||"Falha ao carregar opções de aviso.");
      return false;
    }
    agendaSemanaAviso.opcoes=data||{};
    const tipos=Array.isArray(data?.tipos_envio)?data.tipos_envio:[];
    agendaSemanaAviso.tipo.innerHTML=tipos.map(item=>`<option value="${esc(String(item?.id||""))}">${esc(String(item?.label||item?.id||""))}</option>`).join("");
    if(!agendaSemanaAviso.tipo.value&&agendaSemanaAviso.tipo.options.length)agendaSemanaAviso.tipo.selectedIndex=0;
    agendaSemanaAvisoRecarregarModelos();
    const defaults=data?.defaults||{};
    if(defaults?.periodo_ini)agendaSemanaAviso.dataIni.value=String(defaults.periodo_ini||"");
    if(defaults?.periodo_fim)agendaSemanaAviso.dataFim.value=String(defaults.periodo_fim||"");
    agendaSemanaAviso.chkTodos.checked=true;
    agendaSemanaAvisoRenderRows([]);
    return true;
  };
  const agendaSemanaAvisoPesquisar=async()=>{
    if(!agendaSemanaAviso)return;
    const params=new URLSearchParams();
    params.set("data_ini",String(agendaSemanaAviso.dataIni.value||"").trim());
    params.set("data_fim",String(agendaSemanaAviso.dataFim.value||"").trim());
    params.set("tipo_envio",agendaSemanaAvisoTipoAtual());
    params.set("todos_cirurgioes",agendaSemanaAviso.chkTodos.checked?"1":"0");
    if(!agendaSemanaAviso.chkTodos.checked){
      const prestador=String(agendaSemana?.selectPrestador?.value||"").trim();
      if(prestador)params.set("id_prestador",prestador);
    }
    params.set("limit","5000");
    if(agendaSemanaAviso.btnPesquisar)agendaSemanaAviso.btnPesquisar.disabled=true;
    const {res,data}=await requestJson("GET",`/agenda-legado/avisos-agendamento?${params.toString()}`,undefined,true);
    if(!res.ok){
      window.alert(data?.detail||"Falha ao pesquisar avisos.");
      agendaSemanaAvisoAtualizarBotoes();
      return;
    }
    agendaSemanaAvisoRenderRows(Array.isArray(data)?data:[]);
  };
  const agendaSemanaAvisoEnviar=async()=>{
    if(!agendaSemanaAviso)return;
    const rows=Array.isArray(agendaSemanaAviso.rows)?agendaSemanaAviso.rows:[];
    const itens=rows.map(row=>({agenda_id:Number(row?.id||0)||0,ok:!!row?.ok})).filter(row=>row.agenda_id>0);
    if(!itens.some(item=>item.ok)){
      agendaSemanaAvisoAtualizarBotoes();
      return;
    }
    const payload={
      tipo_envio:agendaSemanaAvisoTipoAtual(),
      modelo_id:Number(agendaSemanaAviso.modelo?.value||0)||null,
      itens,
    };
    const {res,data}=await requestJson("POST","/agenda-legado/avisos-agendamento/enviar",payload,true);
    if(!res.ok){
      window.alert(data?.detail||"Falha ao enviar avisos.");
      return;
    }
    const enviados=Number(data?.enviados||0)||0;
    const pendentes=Number(data?.pendentes||0)||0;
    const total=Number(data?.total_selecionados||0)||0;
    if(payload.tipo_envio==="whatsapp"){
      const links=Array.isArray(data?.links_whatsapp)?data.links_whatsapp:[];
      links.forEach(item=>{
        const url=String(item?.url||"").trim();
        if(url)window.open(url,"_blank","noopener");
      });
    }
    const falhas=Array.isArray(data?.falhas)?data.falhas:[];
    if(falhas.length)window.alert(`Processado ${total} aviso(s). Enviados: ${enviados}. Pendentes: ${pendentes}. Falhas: ${falhas.length}.`);
    else window.alert(`Processado ${total} aviso(s). Enviados: ${enviados}. Pendentes: ${pendentes}.`);
    agendaSemanaAvisoFechar();
  };
  const agendaSemanaAvisoVincularEventos=()=>{
    if(!agendaSemanaAviso||agendaSemanaAviso.bound)return;
    agendaSemanaAviso.bound=true;
    [agendaSemanaAviso.dataIni,agendaSemanaAviso.dataFim,agendaSemanaAviso.modelo].forEach(el=>{
      if(el)el.addEventListener("change",agendaSemanaAvisoAtualizarBotoes);
    });
    agendaSemanaAviso.tipo.addEventListener("change",()=>{
      agendaSemanaAvisoRecarregarModelos();
      agendaSemanaAvisoRenderRows([]);
    });
    agendaSemanaAviso.chkTodos.addEventListener("change",agendaSemanaAvisoAtualizarBotoes);
    agendaSemanaAviso.btnPesquisar.addEventListener("click",agendaSemanaAvisoPesquisar);
    agendaSemanaAviso.btnOk.addEventListener("click",agendaSemanaAvisoEnviar);
    agendaSemanaAviso.btnCancela.addEventListener("click",agendaSemanaAvisoFechar);
    agendaSemanaAviso.backdrop.addEventListener("click",ev=>{
      if(ev.target===agendaSemanaAviso.backdrop)agendaSemanaAvisoFechar();
    });
    agendaSemanaAviso.tbody.addEventListener("click",ev=>{
      const tr=ev.target.closest("tr[data-idx]");
      if(!tr)return;
      const idx=Math.max(0,Number(tr.dataset.idx||0)||0);
      agendaSemanaAviso.selectedIdx=idx;
      if(ev.target.closest(".agenda-semana-aviso-ok-cell")){
        const row=agendaSemanaAviso.rows[idx];
        if(row)row.ok=!row.ok;
      }
      agendaSemanaAvisoRenderRows(agendaSemanaAviso.rows);
    });
    agendaSemanaAviso.modal.addEventListener("keydown",ev=>{
      if(ev.key==="Escape"){
        ev.preventDefault();
        agendaSemanaAvisoFechar();
        return;
      }
      if(ev.key==="Enter"){
        ev.preventDefault();
        agendaSemanaAvisoPesquisar();
      }
    });
  };
  const agendaSemanaAvisoEnsureUI=()=>{
    if(agendaSemanaAviso?.backdrop)return agendaSemanaAviso;
    if(!document.getElementById("agenda-semana-aviso-style")){
      const style=document.createElement("style");
      style.id="agenda-semana-aviso-style";
      style.textContent=`
        .agenda-semana-aviso-backdrop{position:fixed;inset:0;z-index:2700;background:rgba(0,0,0,.12);display:grid;place-items:center}
        .agenda-semana-aviso-backdrop.hidden{display:none}
        .agenda-semana-aviso-modal{width:min(700px,96vw);background:#efefef;border:1px solid #9ea9b5;box-shadow:2px 2px 8px rgba(0,0,0,.18);padding:8px;box-sizing:border-box;font:12px Tahoma,sans-serif;color:#111}
        .agenda-semana-aviso-modal *{font-family:Tahoma,sans-serif}
        .agenda-semana-aviso-title{font:400 33px/1 "Segoe UI Symbol","Arial Unicode MS",Tahoma,sans-serif;text-align:center;transform:translateY(-1px) scaleX(.72);transform-origin:center;margin:0 0 8px;color:#2a2a2a}
        .agenda-semana-aviso-box{border:1px solid #bfc6ce;padding:8px;background:#efefef}
        .agenda-semana-aviso-top{display:grid;grid-template-columns:190px 120px minmax(140px,1fr) 86px;column-gap:8px;row-gap:0;align-items:end}
        .agenda-semana-aviso-top label{display:block;margin:0 0 1px}
        .agenda-semana-aviso-top input,.agenda-semana-aviso-top select{height:24px;border:1px solid #aeb9c6;padding:0 6px;box-sizing:border-box;background:#fff;font:12px Tahoma,sans-serif;border-radius:0}
        .agenda-semana-aviso-periodo{display:flex;align-items:center;gap:5px}
        #agenda-semana-aviso-data-ini,#agenda-semana-aviso-data-fim{width:86px;min-width:86px}
        #agenda-semana-aviso-tipo{width:118px;min-width:118px}
        #agenda-semana-aviso-modelo{width:100%;min-width:0}
        #agenda-semana-aviso-pesquisar{width:86px;min-width:86px;padding:0}
        .agenda-semana-aviso-todos{margin:8px 0 6px;display:flex;align-items:center;gap:6px}
        .agenda-semana-aviso-todos input{margin:0}
        .agenda-semana-aviso-grid{border:1px solid #bfc6ce;background:#fff;height:318px;overflow:auto}
        .agenda-semana-aviso-grid table{width:100%;border-collapse:collapse;table-layout:fixed}
        .agenda-semana-aviso-grid th,.agenda-semana-aviso-grid td{height:22px;padding:2px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-bottom:1px solid #e7ebf0}
        .agenda-semana-aviso-grid th{background:#eceff3;font:700 12px Tahoma,sans-serif;text-align:left;border-bottom:1px solid #c8d0da}
        .agenda-semana-aviso-grid tr.selected{background:#2a72c9;color:#fff}
        .agenda-semana-aviso-grid tr.agenda-semana-aviso-empty td{height:286px;border-bottom:none}
        .agenda-semana-aviso-grid .agenda-semana-aviso-ok-cell{text-align:center;font-weight:700;cursor:pointer}
        .agenda-semana-aviso-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:8px}
        .agenda-semana-aviso-modal .materiais-btn{height:30px;min-width:90px;padding:0 12px;border:1px solid #9ba9b9;border-radius:2px;background:#efefef;color:#111;box-shadow:none;font:700 12px Tahoma,sans-serif}
        .agenda-semana-aviso-modal .materiais-btn:disabled{color:#8f8f8f;background:#ececec;opacity:1}
        .agenda-semana-aviso-modal .materiais-btn:not(:disabled):hover{background:#e7ebf1}
      `;
      document.head.appendChild(style);
    }
    const backdrop=document.createElement("div");
    backdrop.className="agenda-semana-aviso-backdrop hidden";
    backdrop.innerHTML=`
      <div class="agenda-semana-aviso-modal" role="dialog" aria-modal="true" tabindex="0">
        <div class="agenda-semana-aviso-title">Enviar avisos de agendamento</div>
        <div class="agenda-semana-aviso-box">
          <div class="agenda-semana-aviso-top">
            <div>
              <label for="agenda-semana-aviso-data-ini">Período:</label>
              <div class="agenda-semana-aviso-periodo">
                <input id="agenda-semana-aviso-data-ini" type="date">
                <span>a</span>
                <input id="agenda-semana-aviso-data-fim" type="date">
              </div>
            </div>
            <div>
              <label for="agenda-semana-aviso-tipo">Tipo de envio:</label>
              <select id="agenda-semana-aviso-tipo"></select>
            </div>
            <div>
              <label for="agenda-semana-aviso-modelo">Arquivo:</label>
              <select id="agenda-semana-aviso-modelo"></select>
            </div>
            <button id="agenda-semana-aviso-pesquisar" class="materiais-btn" type="button">Pesquisa</button>
          </div>
          <label class="agenda-semana-aviso-todos"><input id="agenda-semana-aviso-todos" type="checkbox" checked> Todos os cirurgiões</label>
          <div class="agenda-semana-aviso-grid">
            <table>
              <colgroup>
                <col style="width:102px">
                <col style="width:66px">
                <col>
                <col style="width:170px">
                <col style="width:46px">
              </colgroup>
              <thead><tr><th>Data</th><th>Hora</th><th>Paciente</th><th id="agenda-semana-aviso-th-contato">E-mail</th><th>Ok</th></tr></thead>
              <tbody id="agenda-semana-aviso-tbody"></tbody>
            </table>
          </div>
        </div>
        <div class="agenda-semana-aviso-actions">
          <button id="agenda-semana-aviso-ok" class="materiais-btn" type="button">Ok</button>
          <button id="agenda-semana-aviso-cancela" class="materiais-btn" type="button">Cancela</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    agendaSemanaAviso={
      backdrop,
      modal:backdrop.querySelector(".agenda-semana-aviso-modal"),
      dataIni:backdrop.querySelector("#agenda-semana-aviso-data-ini"),
      dataFim:backdrop.querySelector("#agenda-semana-aviso-data-fim"),
      tipo:backdrop.querySelector("#agenda-semana-aviso-tipo"),
      modelo:backdrop.querySelector("#agenda-semana-aviso-modelo"),
      btnPesquisar:backdrop.querySelector("#agenda-semana-aviso-pesquisar"),
      chkTodos:backdrop.querySelector("#agenda-semana-aviso-todos"),
      thContato:backdrop.querySelector("#agenda-semana-aviso-th-contato"),
      tbody:backdrop.querySelector("#agenda-semana-aviso-tbody"),
      btnOk:backdrop.querySelector("#agenda-semana-aviso-ok"),
      btnCancela:backdrop.querySelector("#agenda-semana-aviso-cancela"),
      rows:[],
      selectedIdx:-1,
      opcoes:null,
      bound:false,
    };
    agendaSemanaAvisoVincularEventos();
    agendaSemanaAvisoRenderRows([]);
    return agendaSemanaAviso;
  };
  const agendaSemanaAvisoAbrir=async()=>{
    const cfg=agendaSemanaAvisoEnsureUI();
    const ok=await agendaSemanaAvisoCarregarOpcoes();
    if(!ok)return;
    cfg.backdrop.classList.remove("hidden");
    requestAnimationFrame(()=>{try{cfg.dataIni.focus();cfg.dataIni.select()}catch{}});
  };

  const agendaSemanaPublicarDataPadrao=()=>{
    const foco=agendaSemanaState?.focusDate instanceof Date?agendaSemanaState.focusDate:new Date();
    const d=new Date(foco.getFullYear(),foco.getMonth(),foco.getDate());
    const ini=new Date(d);
    const fim=new Date(d);
    fim.setDate(fim.getDate()+5);
    return {ini:agendaSemanaToIsoDate(ini),fim:agendaSemanaToIsoDate(fim)};
  };
  const agendaSemanaPublicarFechar=()=>{
    if(!agendaSemanaPublicar?.backdrop)return;
    agendaSemanaPublicar.backdrop.classList.add("hidden");
  };
  const agendaSemanaPublicarAtualizarBotoes=()=>{
    if(!agendaSemanaPublicar)return;
    const ini=String(agendaSemanaPublicar.dataIni?.value||"").trim();
    const fim=String(agendaSemanaPublicar.dataFim?.value||"").trim();
    const periodoOk=!!ini&&!!fim&&fim>=ini;
    if(agendaSemanaPublicar.btnVisualizar)agendaSemanaPublicar.btnVisualizar.disabled=!periodoOk;
    const temRows=(Array.isArray(agendaSemanaPublicar.rows)?agendaSemanaPublicar.rows:[]).length>0;
    const conectado=!!agendaSemanaPublicar.connected;
    if(agendaSemanaPublicar.btnExportar)agendaSemanaPublicar.btnExportar.disabled=!(periodoOk&&temRows&&conectado);
  };
  const agendaSemanaPublicarRenderRows=(rows)=>{
    if(!agendaSemanaPublicar)return;
    agendaSemanaPublicar.rows=Array.isArray(rows)?rows:[];
    agendaSemanaPublicar.tbody.innerHTML=agendaSemanaPublicar.rows.map((row,idx)=>{
      const selected=idx===0?" selected":"";
      return `<tr class="${selected}"><td>${esc(agendaSemanaAvisoDataBr(row?.data))}</td><td>${esc(String(row?.hora||""))}</td><td>${esc(String(row?.titulo||""))}</td></tr>`;
    }).join("")||'<tr class="agenda-semana-publicar-empty"><td colspan="3"></td></tr>';
    agendaSemanaPublicarAtualizarBotoes();
  };
  const agendaSemanaPublicarAtualizarStatus=async()=>{
    if(!agendaSemanaPublicar)return false;
    const {res,data}=await requestJson("GET","/agenda-legado/google-agenda/status",undefined,true);
    if(!res.ok){
      agendaSemanaPublicar.connected=false;
      agendaSemanaPublicar.login.value="";
      agendaSemanaPublicar.status.textContent="Falha ao consultar conexão Google.";
      agendaSemanaPublicarAtualizarBotoes();
      return false;
    }
    const connected=!!data?.connected;
    agendaSemanaPublicar.connected=connected;
    agendaSemanaPublicar.login.value=String(data?.email||"").trim();
    agendaSemanaPublicar.status.textContent=connected
      ? `Conectado em: ${String(data?.calendar_summary||"Agenda principal")}`
      : "Google Agenda não conectado.";
    agendaSemanaPublicarAtualizarBotoes();
    return true;
  };
  const agendaSemanaPublicarConectar=async()=>{
    if(!agendaSemanaPublicar)return;
    const {res,data}=await requestJson("GET","/agenda-legado/google-agenda/oauth/start",undefined,true);
    if(!res.ok){
      window.alert(data?.detail||"Falha ao iniciar conexão com Google Agenda.");
      return;
    }
    const authUrl=String(data?.auth_url||"").trim();
    if(!authUrl){
      window.alert("URL de autorização Google não disponível.");
      return;
    }
    const popup=window.open(authUrl,"brana_google_calendar_oauth","width=580,height=700,resizable=yes,scrollbars=yes");
    if(!popup){
      window.alert("Não foi possível abrir a janela de autorização Google.");
      return;
    }
    agendaSemanaPublicar.status.textContent="Aguardando autorização Google...";
  };
  const agendaSemanaPublicarVisualizar=async()=>{
    if(!agendaSemanaPublicar)return;
    const ini=String(agendaSemanaPublicar.dataIni.value||"").trim();
    const fim=String(agendaSemanaPublicar.dataFim.value||"").trim();
    const params=new URLSearchParams();
    params.set("data_ini",ini);
    params.set("data_fim",fim);
    const prestador=Number(agendaSemana?.selectPrestador?.value||0)||0;
    const unidade=Number(agendaSemana?.selectUnidade?.value||0)||0;
    if(prestador>0)params.set("id_prestador",String(prestador));
    if(unidade>0)params.set("id_unidade",String(unidade));
    params.set("limit","10000");
    if(agendaSemanaPublicar.btnVisualizar)agendaSemanaPublicar.btnVisualizar.disabled=true;
    const {res,data}=await requestJson("GET",`/agenda-legado/google-agenda/preview?${params.toString()}`,undefined,true);
    if(!res.ok){
      window.alert(data?.detail||"Falha ao visualizar agenda para exportação.");
      agendaSemanaPublicarAtualizarBotoes();
      return;
    }
    agendaSemanaPublicarRenderRows(Array.isArray(data)?data:[]);
  };
  const agendaSemanaPublicarExportar=async()=>{
    if(!agendaSemanaPublicar)return;
    const ini=String(agendaSemanaPublicar.dataIni.value||"").trim();
    const fim=String(agendaSemanaPublicar.dataFim.value||"").trim();
    const prestador=Number(agendaSemana?.selectPrestador?.value||0)||0;
    const unidade=Number(agendaSemana?.selectUnidade?.value||0)||0;
    const itensIds=(Array.isArray(agendaSemanaPublicar.rows)?agendaSemanaPublicar.rows:[])
      .map(item=>Number(item?.id||0)||0)
      .filter(n=>n>0);
    if(!itensIds.length){
      agendaSemanaPublicarAtualizarBotoes();
      return;
    }
    const payload={
      data_ini:ini,
      data_fim:fim,
      id_prestador:prestador>0?prestador:null,
      id_unidade:unidade>0?unidade:null,
      itens_ids:itensIds,
    };
    const {res,data}=await requestJson("POST","/agenda-legado/google-agenda/exportar",payload,true);
    if(!res.ok){
      window.alert(data?.detail||"Falha ao exportar para Google Agenda.");
      return;
    }
    const total=Number(data?.total||0)||0;
    const publicados=Number(data?.publicados||0)||0;
    const falhas=Array.isArray(data?.falhas)?data.falhas:[];
    if(falhas.length){
      window.alert(`Exportação concluída. Total: ${total}. Publicados: ${publicados}. Falhas: ${falhas.length}.`);
    }else{
      window.alert(`Exportação concluída. Total: ${total}. Publicados: ${publicados}.`);
    }
    agendaSemanaPublicarFechar();
  };
  const agendaSemanaPublicarVincularEventos=()=>{
    if(!agendaSemanaPublicar||agendaSemanaPublicar.bound)return;
    agendaSemanaPublicar.bound=true;
    [agendaSemanaPublicar.dataIni,agendaSemanaPublicar.dataFim].forEach(el=>{
      if(el)el.addEventListener("change",agendaSemanaPublicarAtualizarBotoes);
    });
    agendaSemanaPublicar.btnConectar.addEventListener("click",agendaSemanaPublicarConectar);
    agendaSemanaPublicar.btnVisualizar.addEventListener("click",agendaSemanaPublicarVisualizar);
    agendaSemanaPublicar.btnExportar.addEventListener("click",agendaSemanaPublicarExportar);
    agendaSemanaPublicar.btnFechar.addEventListener("click",agendaSemanaPublicarFechar);
    agendaSemanaPublicar.backdrop.addEventListener("click",ev=>{
      if(ev.target===agendaSemanaPublicar.backdrop)agendaSemanaPublicarFechar();
    });
    window.addEventListener("message",async(ev)=>{
      const payload=ev?.data;
      if(!payload||payload.type!=="google_calendar_auth")return;
      if(String(payload.status||"")!=="ok"){
        window.alert(String(payload.message||"Falha na autorização Google Agenda."));
      }
      await agendaSemanaPublicarAtualizarStatus();
    });
  };
  const agendaSemanaPublicarEnsureUI=()=>{
    if(agendaSemanaPublicar?.backdrop)return agendaSemanaPublicar;
    if(!document.getElementById("agenda-semana-publicar-style")){
      const style=document.createElement("style");
      style.id="agenda-semana-publicar-style";
      style.textContent=`
        .agenda-semana-publicar-backdrop{position:fixed;inset:0;z-index:2700;background:rgba(0,0,0,.12);display:grid;place-items:center}
        .agenda-semana-publicar-backdrop.hidden{display:none}
        .agenda-semana-publicar-modal{width:min(720px,96vw);background:#efefef;border:1px solid #9ea9b5;box-shadow:2px 2px 8px rgba(0,0,0,.18);padding:8px;box-sizing:border-box;font:12px Tahoma,sans-serif;color:#111}
        .agenda-semana-publicar-modal *{font-family:Tahoma,sans-serif}
        .agenda-semana-publicar-title{font:400 33px/1 "Segoe UI Symbol","Arial Unicode MS",Tahoma,sans-serif;text-align:center;transform:translateY(-1px) scaleX(.72);transform-origin:center;margin:0 0 8px;color:#2a2a2a}
        .agenda-semana-publicar-box{border:1px solid #bfc6ce;padding:8px;background:#efefef}
        .agenda-semana-publicar-top{display:grid;grid-template-columns:1fr 1fr 96px;column-gap:8px;row-gap:6px;align-items:end}
        .agenda-semana-publicar-top label{display:block;margin:0 0 1px}
        .agenda-semana-publicar-top input{height:24px;border:1px solid #aeb9c6;padding:0 6px;box-sizing:border-box;background:#fff;font:12px Tahoma,sans-serif;border-radius:0}
        .agenda-semana-publicar-periodo{display:flex;align-items:center;gap:5px}
        #agenda-semana-publicar-data-ini,#agenda-semana-publicar-data-fim{width:100px;min-width:100px}
        .agenda-semana-publicar-status{grid-column:1 / span 3;color:#3d4b5b;min-height:16px}
        .agenda-semana-publicar-grid{margin-top:6px;border:1px solid #bfc6ce;background:#fff;height:312px;overflow:auto}
        .agenda-semana-publicar-grid table{width:100%;border-collapse:collapse;table-layout:fixed}
        .agenda-semana-publicar-grid th,.agenda-semana-publicar-grid td{height:22px;padding:2px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-bottom:1px solid #e7ebf0}
        .agenda-semana-publicar-grid th{background:#eceff3;font:700 12px Tahoma,sans-serif;text-align:left;border-bottom:1px solid #c8d0da}
        .agenda-semana-publicar-grid tr.selected{background:#2a72c9;color:#fff}
        .agenda-semana-publicar-grid tr.agenda-semana-publicar-empty td{height:286px;border-bottom:none}
        .agenda-semana-publicar-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:8px}
        .agenda-semana-publicar-modal .materiais-btn{height:30px;min-width:90px;padding:0 12px;border:1px solid #9ba9b9;border-radius:2px;background:#efefef;color:#111;box-shadow:none;font:700 12px Tahoma,sans-serif}
        .agenda-semana-publicar-modal .materiais-btn:disabled{color:#8f8f8f;background:#ececec;opacity:1}
        .agenda-semana-publicar-modal .materiais-btn:not(:disabled):hover{background:#e7ebf1}
      `;
      document.head.appendChild(style);
    }
    const backdrop=document.createElement("div");
    backdrop.className="agenda-semana-publicar-backdrop hidden";
    backdrop.innerHTML=`
      <div class="agenda-semana-publicar-modal" role="dialog" aria-modal="true" tabindex="0">
        <div class="agenda-semana-publicar-title">Publicar agenda no Google</div>
        <div class="agenda-semana-publicar-box">
          <div class="agenda-semana-publicar-top">
            <div>
              <label for="agenda-semana-publicar-login">Conta Google:</label>
              <input id="agenda-semana-publicar-login" type="text" readonly>
            </div>
            <div>
              <label>Período a exportar:</label>
              <div class="agenda-semana-publicar-periodo">
                <input id="agenda-semana-publicar-data-ini" type="date">
                <span>a</span>
                <input id="agenda-semana-publicar-data-fim" type="date">
              </div>
            </div>
            <button id="agenda-semana-publicar-visualizar" class="materiais-btn" type="button">Visualiza</button>
            <div class="agenda-semana-publicar-status" id="agenda-semana-publicar-status"></div>
          </div>
          <div style="display:flex;justify-content:flex-end;margin-top:4px">
            <button id="agenda-semana-publicar-conectar" class="materiais-btn" type="button">Conectar Google</button>
          </div>
          <div class="agenda-semana-publicar-grid">
            <table>
              <colgroup>
                <col style="width:110px">
                <col style="width:80px">
                <col>
              </colgroup>
              <thead><tr><th>Data</th><th>Hora</th><th>Paciente / compromisso</th></tr></thead>
              <tbody id="agenda-semana-publicar-tbody"></tbody>
            </table>
          </div>
        </div>
        <div class="agenda-semana-publicar-actions">
          <button id="agenda-semana-publicar-exportar" class="materiais-btn" type="button">Exporta</button>
          <button id="agenda-semana-publicar-fechar" class="materiais-btn" type="button">Fecha</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    agendaSemanaPublicar={
      backdrop,
      modal:backdrop.querySelector(".agenda-semana-publicar-modal"),
      login:backdrop.querySelector("#agenda-semana-publicar-login"),
      status:backdrop.querySelector("#agenda-semana-publicar-status"),
      dataIni:backdrop.querySelector("#agenda-semana-publicar-data-ini"),
      dataFim:backdrop.querySelector("#agenda-semana-publicar-data-fim"),
      btnConectar:backdrop.querySelector("#agenda-semana-publicar-conectar"),
      btnVisualizar:backdrop.querySelector("#agenda-semana-publicar-visualizar"),
      tbody:backdrop.querySelector("#agenda-semana-publicar-tbody"),
      btnExportar:backdrop.querySelector("#agenda-semana-publicar-exportar"),
      btnFechar:backdrop.querySelector("#agenda-semana-publicar-fechar"),
      rows:[],
      connected:false,
      bound:false,
    };
    agendaSemanaPublicarVincularEventos();
    agendaSemanaPublicarRenderRows([]);
    return agendaSemanaPublicar;
  };
  const agendaSemanaPublicarAbrir=async()=>{
    const cfg=agendaSemanaPublicarEnsureUI();
    const padrao=agendaSemanaPublicarDataPadrao();
    cfg.dataIni.value=padrao.ini;
    cfg.dataFim.value=padrao.fim;
    agendaSemanaPublicarRenderRows([]);
    await agendaSemanaPublicarAtualizarStatus();
    cfg.backdrop.classList.remove("hidden");
    requestAnimationFrame(()=>{try{cfg.dataIni.focus();cfg.dataIni.select()}catch{}});
  };
  if(_agendaSemanaRenderEstruturaOrig){
    agendaSemanaRenderEstrutura=function(skipStablePass=false){
      _agendaSemanaRenderEstruturaOrig(skipStablePass);
      if(!agendaSemana?.daysWrap)return;
      const modo=String(agendaSemanaState?.mode||"semana").toLowerCase();
      if(modo!=="clinica"){
        const cols=[...agendaSemana.daysWrap.children];
        const days=Array.isArray(agendaSemanaState?.weekDates)?agendaSemanaState.weekDates:[];
        cols.forEach((col,idx)=>{
          col.ondblclick=ev=>{
            if(ev.target.closest(".agenda-semana-event"))return;
            const slots=Array.isArray(agendaSemanaSlots)?agendaSemanaSlots:[];
            if(!slots.length)return;
            const slotHeight=Math.max(1,Number(agendaSemanaState?.slotHeight||AGENDA_SEMANA_SLOT_HEIGHT)||AGENDA_SEMANA_SLOT_HEIGHT);
            const rect=col.getBoundingClientRect();
            const slotIdx=Math.max(0,Math.min(slots.length-1,Math.floor((ev.clientY-rect.top)/slotHeight)));
            const slot=slots[slotIdx];
            const dataRef=days[idx];
            if(!slot||!dataRef)return;
            const dataIso=agendaSemanaToIsoDate(dataRef);
            const hora=agendaSemanaMinToHHMM(slot.min);
            const{iniMs,fimMs}=agendaSemanaIntervaloCliqueMs(slot,slotHeight,ev.clientY,rect.top);
            const ocupante=agendaSemanaBuscarOcupanteIntervalo(dataIso,iniMs,fimMs);
            if(ocupante){
              agendaSemanaState.selectedEventId=Number(ocupante?.id||0)||null;
              agendaSemanaSyncSelecaoUI();
              agendaSemanaAbrirModalEditar(ocupante);
              return;
            }
            agendaSemanaAbrirModalNovo(dataIso,hora);
          };
        });
      }
      agendaSemanaAplicarDestaqueCabecalhoDia();
    };
  }

  if(!document.getElementById("agenda-semana-head-active-style")){
    const style=document.createElement("style");
    style.id="agenda-semana-head-active-style";
    style.textContent=`
      .agenda-semana-day-head.agenda-semana-day-head-active{
        font-weight:900;color:#0f3f7f;background:#eef4fc;
      }
    `;
    document.head.appendChild(style);
  }

  if(!document.getElementById("agenda-semana-event-select-style")){
    const style=document.createElement("style");
    style.id="agenda-semana-event-select-style";
    style.textContent=`
      .agenda-semana-event{cursor:pointer}
      .agenda-semana-event.selected{
        box-shadow:0 0 0 2px #0f3f7f inset,0 0 0 1px #ffffff;
      }
    `;
    document.head.appendChild(style);
  }

  if(!document.getElementById("agenda-semana-drag-style")){
    const style=document.createElement("style");
    style.id="agenda-semana-drag-style";
    style.textContent=`
      .agenda-semana-event[draggable="true"]{cursor:grab}
      .agenda-semana-event.agenda-semana-event-dragging{opacity:.55;cursor:grabbing}
      .agenda-semana-day.agenda-semana-drop-valid{outline:2px solid #2f8f2f;outline-offset:-2px}
      .agenda-semana-day.agenda-semana-drop-invalid{outline:2px solid #c43b3b;outline-offset:-2px}
    `;
    document.head.appendChild(style);
  }

  agendaSemanaRenderEventos=function(){
    _agendaSemanaRenderEventosOrig();
    if(!agendaSemana?.daysWrap)return;

    const itensDiaOrdenados=(dayIdx)=>{
      const dias=Array.isArray(agendaSemanaState?.weekDates)?agendaSemanaState.weekDates:[];
      const dataRef=dias[dayIdx];
      if(!dataRef)return [];
      const dataIso=agendaSemanaToIsoDate(dataRef);
      return (Array.isArray(agendaSemanaCache)?agendaSemanaCache:[])
        .filter(item=>agendaSemanaToIsoDate(item?.data)===dataIso)
        .sort((a,b)=>{
          const inicioA=Number(a?.hora_inicio||0)||0;
          const inicioB=Number(b?.hora_inicio||0)||0;
          if(inicioA!==inicioB)return inicioA-inicioB;
          const idA=Number(a?.id||0)||0;
          const idB=Number(b?.id||0)||0;
          return idA-idB;
        });
    };

    document.querySelectorAll(".agenda-semana-event").forEach(el=>{
      let idNum=Number(el.getAttribute("data-id")||0)||0;
      let item=idNum>0?agendaSemanaGetEventoById(idNum):null;
      if(!item){
        const col=el.closest(".agenda-semana-day[data-day]");
        const dayIdx=Math.max(0,Math.min(5,Number(col?.dataset?.day||0)));
        const itensDia=itensDiaOrdenados(dayIdx);
        const eventosDia=col?[...col.querySelectorAll(".agenda-semana-event")]:[];
        const idxEvento=eventosDia.indexOf(el);
        item=idxEvento>=0?itensDia[idxEvento]||null:null;
        idNum=Number(item?.id||0)||0;
        if(idNum>0)el.setAttribute("data-id",String(idNum));
      }
      if(!item||idNum<=0)return;
      el.setAttribute("draggable","true");
      el.addEventListener("click",ev=>{
        ev.stopPropagation();
        agendaSemanaState.selectedEventId=idNum;
        agendaSemanaSyncSelecaoUI();
      });
      el.addEventListener("dblclick",ev=>{
        ev.stopPropagation();
        agendaSemanaState.selectedEventId=idNum;
        agendaSemanaSyncSelecaoUI();
        agendaSemanaAbrirModalEditar(item);
      });
      el.addEventListener("contextmenu",ev=>{
        ev.preventDefault();
        ev.stopPropagation();
        agendaSemanaState.selectedEventId=idNum;
        agendaSemanaSyncSelecaoUI();
        agendaSemanaMostrarContexto({mode:"ocupado",item},ev);
      });
      el.addEventListener("dragstart",ev=>{
        const itemAtual=agendaSemanaGetEventoById(idNum)||item;
        if(!itemAtual){
          ev.preventDefault();
          return;
        }
        const intervalo=agendaSemanaIntervaloEventoMs(itemAtual);
        agendaSemanaOcultarContexto();
        agendaSemanaState.selectedEventId=idNum;
        agendaSemanaSyncSelecaoUI();
        agendaSemanaDragState={
          eventId:idNum,
          item:itemAtual,
          origemDataIso:agendaSemanaEventoDataIso(itemAtual),
          origemIniMs:intervalo.iniMs,
          durMs:intervalo.durMs,
          destino:null,
          eventEl:el,
        };
        try{
          ev.dataTransfer.effectAllowed="move";
          ev.dataTransfer.setData("text/plain",String(idNum));
        }catch{}
        requestAnimationFrame(()=>el.classList.add("agenda-semana-event-dragging"));
      });
      el.addEventListener("dragend",()=>{
        agendaSemanaFinalizarDrag();
      });
    });

    const ids=new Set((Array.isArray(agendaSemanaCache)?agendaSemanaCache:[]).map(item=>Number(item?.id||0)||0));
    if(!ids.has(Number(agendaSemanaState?.selectedEventId||0)||0))agendaSemanaState.selectedEventId=null;
    agendaSemanaSyncSelecaoUI();
  };

  if(typeof agendaSemanaVincularEventos==="function"){
    const _agendaSemanaVincularEventosOrig=agendaSemanaVincularEventos;
    agendaSemanaVincularEventos=function(){
      _agendaSemanaVincularEventosOrig();
      agendaSemanaGarantirContexto();
      if(agendaSemana?.daysWrap&&agendaSemana.daysWrap.dataset.ctxBound!=="1"){
        agendaSemana.daysWrap.dataset.ctxBound="1";
        agendaSemana.daysWrap.addEventListener("contextmenu",ev=>{
          const eventEl=ev.target.closest(".agenda-semana-event[data-id]");
          if(eventEl){
            ev.preventDefault();
            return;
          }
          const col=ev.target.closest(".agenda-semana-day[data-day]");
          if(!col)return;
          ev.preventDefault();
          const dayIdx=Math.max(0,Math.min(5,Number(col.dataset.day||0)));
          const dayDate=Array.isArray(agendaSemanaState?.weekDates)?agendaSemanaState.weekDates[dayIdx]:null;
          if(!dayDate)return;
          const slotHeight=Math.max(1,Number(agendaSemanaState?.slotHeight||AGENDA_SEMANA_SLOT_HEIGHT)||AGENDA_SEMANA_SLOT_HEIGHT);
          const slots=Array.isArray(agendaSemanaSlots)?agendaSemanaSlots:[];
        if(!slots.length)return;
        const rect=col.getBoundingClientRect();
        const slotIdx=Math.max(0,Math.min(slots.length-1,Math.floor((ev.clientY-rect.top)/slotHeight)));
        const slot=slots[slotIdx];
        if(!slot)return;
        const dataIso=agendaSemanaToIsoDate(dayDate);
        const hora=agendaSemanaMinToHHMM(slot.min);
        const{iniMs,fimMs}=agendaSemanaIntervaloCliqueMs(slot,slotHeight,ev.clientY,rect.top);
        const ocupante=agendaSemanaBuscarOcupanteIntervalo(dataIso,iniMs,fimMs);
        if(ocupante){
          agendaSemanaState.selectedEventId=Number(ocupante?.id||0)||null;
          agendaSemanaSyncSelecaoUI();
          agendaSemanaMostrarContexto({mode:"ocupado",item:ocupante,dataIso,hora},ev);
          return;
        }
        agendaSemanaMostrarContexto({mode:"livre",dataIso,hora,item:null},ev);
      });
    }
      if(agendaSemana?.daysWrap&&agendaSemana.daysWrap.dataset.dragBound!=="1"){
        agendaSemana.daysWrap.dataset.dragBound="1";
        agendaSemana.daysWrap.addEventListener("dragover",agendaSemanaOnDragOver);
        agendaSemana.daysWrap.addEventListener("drop",agendaSemanaOnDrop);
        agendaSemana.daysWrap.addEventListener("dragleave",agendaSemanaOnDragLeave);
      }
      if(agendaSemana?.btnPaciente&&agendaSemana.btnPaciente.dataset.searchPatchBound!=="1"){
        const novoBtnPaciente=agendaSemana.btnPaciente.cloneNode(true);
        agendaSemana.btnPaciente.replaceWith(novoBtnPaciente);
        agendaSemana.btnPaciente=novoBtnPaciente;
        agendaSemana.btnPaciente.dataset.searchPatchBound="1";
        agendaSemana.btnPaciente.addEventListener("click",()=>agendaSemanaPesquisaAbrir());
      }
      if(agendaSemana?.btnHorario&&agendaSemana.btnHorario.dataset.freeSearchPatchBound!=="1"){
        const novoBtn=agendaSemana.btnHorario.cloneNode(true);
        agendaSemana.btnHorario.replaceWith(novoBtn);
        agendaSemana.btnHorario=novoBtn;
        agendaSemana.btnHorario.dataset.freeSearchPatchBound="1";
        agendaSemana.btnHorario.addEventListener("click",()=>{
          agendaSemanaHorariosAbrir();
        });
      }
      if(agendaSemana?.btnAviso&&agendaSemana.btnAviso.dataset.avisoPatchBound!=="1"){
        const novoBtnAviso=agendaSemana.btnAviso.cloneNode(true);
        agendaSemana.btnAviso.replaceWith(novoBtnAviso);
        agendaSemana.btnAviso=novoBtnAviso;
        agendaSemana.btnAviso.dataset.avisoPatchBound="1";
        agendaSemana.btnAviso.addEventListener("click",()=>{
          agendaSemanaAvisoAbrir();
        });
      }
      if(agendaSemana?.btnPublicar&&agendaSemana.btnPublicar.dataset.publicarPatchBound!=="1"){
        const novoBtnPublicar=agendaSemana.btnPublicar.cloneNode(true);
        agendaSemana.btnPublicar.replaceWith(novoBtnPublicar);
        agendaSemana.btnPublicar=novoBtnPublicar;
        agendaSemana.btnPublicar.dataset.publicarPatchBound="1";
        agendaSemana.btnPublicar.addEventListener("click",()=>{
          agendaSemanaPublicarAbrir();
        });
      }
    };
  }

  if(_agendaLegadoExcluirOrig){
    agendaLegadoExcluir=async function(){
      agendaSemanaOcultarContexto();
      const origem=String(agendaLegado?.modalBackdrop?.dataset?.origem||"").trim();
      if(origem!=="agenda-semana")return _agendaLegadoExcluirOrig();
      const item=agendaSemanaGetEventoById(agendaLegadoSelId)||agendaSemanaGetEventoById(agendaSemanaState?.selectedEventId);
      if(!item){window.alert("Selecione um agendamento.");return}
      const confirmou=await agendaSemanaConfirmarExclusao(item);
      if(!confirmou)return;
      const{res,data}=await requestJson("DELETE",`/agenda-legado/${item.id}`,undefined,true);
      if(!res.ok){window.alert(data.detail||"Falha ao eliminar agendamento.");return}
      agendaLegadoSelId=null;
      agendaSemanaState.selectedEventId=null;
      agendaLegadoFecharModal();
      await agendaSemanaCarregarEventos();
    };
  }
}








