/* BERNVAPES i18n: BE (Bärndütsch, Quelltext = Standard) · DE · EN.
   Schlüssel = BE-Originaltext (Textknoten + alt/aria-label/title). Beim Start werden alle übersetzbaren Elemente mit data-i18n markiert;
   dynamische Texte (Tier-Popup) fängt ein MutationObserver. Marken- & Sortennamen bleiben unverändert. */
(function(){
var D={
'Nöii Linie':['Neue Linie','New Line'],'Quartier':['Quartiere','Quarters'],'Bärgtier':['Bergtiere','Mountain Beasts'],'Wärkstatt':['Werkstatt','Workshop'],'Über üs':['Über uns','About'],'Händler':['Händler','Dealers'],
'Neue Dampf us dr Houptstadt.':['Neuer Dampf aus der Hauptstadt.','Fresh vapour from the capital.'],
'Lemon Pie · Lemur':['Lemon Pie · Lemur','Lemon Pie · Lemur'],'Mango Lassi · Elefant':['Mango Lassi · Elefant','Mango Lassi · Elephant'],
'Mandarine Nuss · Chipmunk':['Mandarine Nuss · Chipmunk','Mandarine Nuss · Chipmunk'],'Öpfuchueche · Roter Panda':['Apfelkuchen · Roter Panda','Apple Pie · Red Panda'],
'Scrolle':['Scrollen','Scroll'],
'60 ml · Schwarzi Chubby-Gorilla-Fläsche':['60 ml · Schwarze Chubby-Gorilla-Flasche','60 ml · Black chubby gorilla bottle'],
'Di nöii Linie uf dr Fläsche':['Die neue Linie auf der Flasche','The new line, bottled'],
'Vorbestellen':['Vorbestellen','Pre-order'],'Erhältlich ab 1. Dez.':['Erhältlich ab 1. Dez.','Available from 1 Dec.'],
'0 mg/ml Nikotin':['0 mg/ml Nikotin','0 mg/ml nicotine'],'60 ml Shortfill':['60 ml Shortfill','60 ml shortfill'],'Gmischt z Bärn':['Gemischt in Bern','Mixed in Bern'],
'Wyter i d Quartier':['Weiter in die Quartiere','On to the quarters'],
'D Klassiker':['Die Klassiker','The Classics'],'Bärner Quartier':['Berner Quartiere','Bern Quarters'],
'Sibe Sorte, benannt nach Bärner Quartier. Vier dervo gits o on the rocks — schalt uf Winter. U nid hüle, wes chaut wird.':['Sieben Sorten, benannt nach Berner Quartieren. Vier davon gibt es auch on the rocks — schalte auf Winter. Und nicht heulen, wenn es kalt wird.','Seven flavours, named after Bern’s quarters. Four also come on the rocks — switch to winter. And no whining when it gets cold.'],
'Zartbitter · Orange · garantiert kalorieefrei':['Zartbitter · Orange · garantiert kalorienfrei','Dark chocolate · Orange · guaranteed calorie-free'],
'Öpfu · Pistache':['Apfel · Pistazie','Apple · Pistachio'],'Ingwer · Mandarine · Party':['Ingwer · Mandarine · Party','Ginger · Mandarin · Party'],
'Suuri Mango · Holunder':['Saure Mango · Holunder','Sour mango · Elderflower'],'Jasmin · Schwarztee · hate it or love it':['Jasmin · Schwarztee · hate it or love it','Jasmine · Black tea · hate it or love it'],
'Kaffi · Amaretto · fürs Morge drnah':['Kaffee · Amaretto · für den Morgen danach','Coffee · Amaretto · for the morning after'],
'Tubak · Fyge · für langi Nächt':['Tabak · Feige · für lange Nächte','Tobacco · Fig · for long nights'],
'Breitsch Hirsch · uf Ys':['Breitsch Hirsch · auf Eis','Breitsch Hirsch · on ice'],'Matte Eule · uf Ys':['Matte Eule · auf Eis','Matte Eule · on ice'],
'Länggass Dachs · uf Ys':['Länggass Dachs · auf Eis','Länggass Dachs · on ice'],'Wyler Falke · uf Ys':['Wyler Falke · auf Eis','Wyler Falke · on ice'],
'Gipfel Adler · uf Ys':['Gipfel Adler · auf Eis','Gipfel Adler · on ice'],'Nebel Wolf · uf Ys':['Nebel Wolf · auf Eis','Nebel Wolf · on ice'],'Steinschlag Bock · uf Ys':['Steinschlag Bock · auf Eis','Steinschlag Bock · on ice'],
'Öpfu · Pistache · Koolada':['Apfel · Pistazie · Koolada','Apple · Pistachio · Koolada'],'Ingwer · Mandarine · Koolada':['Ingwer · Mandarine · Koolada','Ginger · Mandarin · Koolada'],
'Suuri Mango · Holunder · Koolada':['Saure Mango · Holunder · Koolada','Sour mango · Elderflower · Koolada'],'Jasmin · Schwarztee · Koolada':['Jasmin · Schwarztee · Koolada','Jasmine · Black tea · Koolada'],
'Summer':['Sommer','Summer'],'On the rocks':['On the rocks','On the rocks'],
'Us de Aupe':['Aus den Alpen','From the Alps'],
'100 ml, Schwyzer Zuetate, nün Tier am Bärg. Je höcher, desto wiuder. Drü dervo chaut wie dr Gipfu säuber — schalt uf Winter.':['100 ml, Schweizer Zutaten, neun Tiere am Berg. Je höher, desto wilder. Drei davon kalt wie der Gipfel selbst — schalte auf Winter.','100 ml, Swiss ingredients, nine beasts on the mountain. The higher, the wilder. Three of them as cold as the summit itself — switch to winter.'],
'Zitronegras · Gingerale · Koolada':['Zitronengras · Ginger Ale · Koolada','Lemongrass · Ginger ale · Koolada'],'Öpfumues · Truube · Koolada':['Apfelmus · Traube · Koolada','Apple sauce · Grape · Koolada'],
'Aprikosetee · Citrusblüete · Koolada':['Aprikosentee · Zitrusblüte · Koolada','Apricot tea · Citrus blossom · Koolada'],
'Gingerale · Zitronegras':['Ginger Ale · Zitronengras','Ginger ale · Lemongrass'],'Öpfumues · Truube · Edelwyss':['Apfelmus · Traube · Edelweiss','Apple sauce · Grape · Edelweiss'],
'Aprikosetee · Citrusblüete':['Aprikosentee · Zitrusblüte','Apricot tea · Citrus blossom'],'Honig · Melisse':['Honig · Melisse','Honey · Lemon balm'],
'Caramelchöpfli — wie bi dr Grosi':['Caramelköpfli — wie bei Oma','Caramel custard — just like grandma’s'],'Aupechrütertee':['Alpenkräutertee','Alpine herbal tea'],
'Ananas · Hibiskus · Zitrone':['Ananas · Hibiskus · Zitrone','Pineapple · Hibiscus · Lemon'],'Himbeeri · Mascarpone':['Himbeere · Mascarpone','Raspberry · Mascarpone'],
'Erdbeer-Cheesecake':['Erdbeer-Cheesecake','Strawberry cheesecake'],
'Was z Bärn grad entsteit.':['Was in Bern gerade entsteht.','What’s brewing in Bern right now.'],
'Konzeptstudie, wo no nid im Sortimänt si: d Afrika-Tier ufem Kristallsee — Büffu, Impala, Kudu, Flamingo, Mandrill u Gepard. Luege lohnt sech. Choufe cha me se no nid, o we me no so bettlet.':['Konzeptstudien, die noch nicht im Sortiment sind: die Afrika-Tiere auf dem Kristallsee — Büffel, Impala, Kudu, Flamingo, Mandrill und Gepard. Anschauen lohnt sich. Kaufen kann man sie noch nicht, auch wenn man noch so bettelt.','Concept studies not yet in the range: the African beasts on the crystal lake — buffalo, impala, kudu, flamingo, mandrill and cheetah. Worth a look. You can’t buy them yet, no matter how much you beg.'],
'I d Wärkstatt':['In die Werkstatt','Into the workshop'],'Konzeptstudie · Yswäut':['Konzeptstudie · Eiswelt','Concept study · Ice world'],
'Über BERNVAPES':['Über BERNVAPES','About BERNVAPES'],'Vo Hand gmischt z Bärn.':['Von Hand gemischt in Bern.','Hand-mixed in Bern.'],
'BERNVAPES si nikotinfreii Arome vo dr Kontrast Kompositions GmbH a dr Fährstrass z Bärn. Jedi Sorte überchunnt ihres eigete Tier — vom Bärner Quartier bis uf e Gipfu — u wird i chlyne Charge gmischt, abgfüllt u etikettiert. Kes Masseprodukt: es Atelier, viu Geduld u e Schwächi für Art Déco u Papier. Däni häut aus zäme, Domi risst a.':['BERNVAPES sind nikotinfreie Aromen der Kontrast Kompositions GmbH an der Fährstrasse in Bern. Jede Sorte bekommt ihr eigenes Tier — vom Berner Quartier bis auf den Gipfel — und wird in kleinen Chargen gemischt, abgefüllt und etikettiert. Kein Massenprodukt: ein Atelier, viel Geduld und eine Schwäche für Art déco und Papier. Däni hält alles zusammen, Domi reisst an.','BERNVAPES are nicotine-free flavours by Kontrast Kompositions GmbH on Fährstrasse in Bern. Every flavour gets its own beast — from the Bern quarters up to the summit — and is mixed, bottled and labelled in small batches. No mass product: a studio, lots of patience and a soft spot for Art Deco and paper. Däni keeps it all together, Domi gets things going.'],
'Säg hallo':['Sag hallo','Say hello'],'Nikotin pro ml':['Nikotin pro ml','Nicotine per ml'],'Sorte':['Sorten','Flavours'],
'Bärn · Fährstrass 29':['Bern · Fährstrasse 29','Bern · Fährstrasse 29'],'Papier':['Papier','Paper'],'Es Tier pro Sorte':['Ein Tier pro Sorte','One beast per flavour'],
'Liquids us Bärn · Null Nikotin · Vou Charakter':['Liquids aus Bern · Null Nikotin · Voller Charakter','Liquids from Bern · Zero nicotine · Full of character'],
'Härsteller':['Hersteller','Manufacturer'],'Wäute':['Welten','Worlds'],
'Liquids für die E-Zigarette. Nur für Erwachsene. Von Kindern fernhalten. Dieses Produkt kann Ihre Gesundheit schädigen.':['Liquids für die E-Zigarette. Nur für Erwachsene. Von Kindern fernhalten. Dieses Produkt kann Ihre Gesundheit schädigen.','Liquids for e-cigarettes. For adults only (18+). Keep out of reach of children. This product can damage your health.'],
'Liquids für die E-Zigarette. Nur für Erwachsene. Dieses Produkt kann Ihre Gesundheit schädigen.':['Liquids für die E-Zigarette. Nur für Erwachsene. Dieses Produkt kann Ihre Gesundheit schädigen.','Liquids for e-cigarettes. For adults only (18+). This product can damage your health.'],
'Schliesse ✕':['Schliessen ✕','Close ✕'],'Schliesse':['Schliessen','Close'],'Sorten':['Sorten','Flavours'],
'Lemur – Lemon Pie – Fläsche aaluege':['Lemur – Lemon Pie – Flasche ansehen','Lemur – Lemon Pie – view bottle'],'Elefant – Mango Lassi – Fläsche aaluege':['Elefant – Mango Lassi – Flasche ansehen','Elephant – Mango Lassi – view bottle'],
'Chipmunk – Mandarine Nuss – Fläsche aaluege':['Chipmunk – Mandarine Nuss – Flasche ansehen','Chipmunk – Mandarine Nuss – view bottle'],'Roter Panda – Apple Pie – Fläsche aaluege':['Roter Panda – Apple Pie – Flasche ansehen','Red Panda – Apple Pie – view bottle'],
'Lemon Pie vorbestellen':['Lemon Pie vorbestellen','Pre-order Lemon Pie'],'Mango Lassi vorbestellen':['Mango Lassi vorbestellen','Pre-order Mango Lassi'],'Mandarine Nuss vorbestellen':['Mandarine Nuss vorbestellen','Pre-order Mandarine Nuss'],'Apple Pie vorbestellen':['Apple Pie vorbestellen','Pre-order Apple Pie'],
'Werkstatt — Eiswelt':['Werkstatt — Eiswelt','Workshop — Ice world'],
/* Tier-Popup (index.html, T-Objekt) */
'Knuspriger Mürbeteig, spritzige Zitronencreme und e Wolke Baiser obendruf – so frisch, dass dr Lemur vor Fröid grad no höcher hüpft.':['Knuspriger Mürbeteig, spritzige Zitronencreme und eine Wolke Baiser obendrauf – so frisch, dass der Lemur vor Freude gleich noch höher hüpft.','Crisp shortcrust, zingy lemon cream and a cloud of meringue on top – so fresh the lemur jumps even higher for joy.'],
'Eine reife Mango, schmeckt supergeil mit der cremigen Milch und ergibt so ein fantastisches Mango-Lassi-Erlebnis.':['Eine reife Mango, die mit cremiger Milch supergut schmeckt und ein fantastisches Mango-Lassi-Erlebnis ergibt.','A ripe mango that tastes amazing with creamy milk – a fantastic mango lassi experience.'],
'Saftigi Mandarine trifft uf gröschteti Nüss – Chippy hamschteret das Aroma scho dr ganz Herbscht i sini Backe.':['Saftige Mandarine trifft auf geröstete Nüsse – Chippy hamstert dieses Aroma schon den ganzen Herbst in seine Backen.','Juicy mandarin meets roasted nuts – Chippy has been stuffing this flavour into his cheeks all autumn.'],
'Warmi Öpfu, e Hauch Zimt und buttrige Chueche-Teig – wie früsch us Grosis Ofe, nume flauschiger.':['Warme Äpfel, ein Hauch Zimt und buttriger Kuchenteig – wie frisch aus Omas Ofen, nur flauschiger.','Warm apples, a hint of cinnamon and buttery pastry – like fresh from grandma’s oven, only fluffier.'],
/* werkstatt.html */
'BERNVAPES — Wärkstatt · Konzeptstudie':['BERNVAPES — Werkstatt · Konzeptstudie','BERNVAPES — Workshop · Concept study'],'BERNVAPES — Liquids us Bärn':['BERNVAPES — Liquids aus Bern','BERNVAPES — Liquids from Bern'],
'← Zrügg zu BERNVAPES':['← Zurück zu BERNVAPES','← Back to BERNVAPES'],'Wärkstatt · Konzeptstudie':['Werkstatt · Konzeptstudie','Workshop · Concept study'],
'Afrika ufem Kristallsee':['Afrika auf dem Kristallsee','Africa on the crystal lake'],
'Sächs Idee, no nid im Sortimänt. Mir zeige se trotzdäm — wüu si üs gfaue. Choufe geit no nid, gluschte scho.':['Sechs Ideen, noch nicht im Sortiment. Wir zeigen sie trotzdem — weil sie uns gefallen. Kaufen geht noch nicht, gluschten schon.','Six ideas, not yet in the range. We’re showing them anyway — because we like them. You can’t buy them yet, but you can crave them.'],
'Kaffernbüffu · Konzept':['Kaffernbüffel · Konzept','Cape buffalo · Concept'],'Impala · Konzept':['Impala · Konzept','Impala · Concept'],'Kudu · Konzept':['Kudu · Konzept','Kudu · Concept'],
'Flamingo · Konzept':['Flamingo · Konzept','Flamingo · Concept'],'Mandrill · Konzept':['Mandrill · Konzept','Mandrill · Concept'],'Gepard · Konzept':['Gepard · Konzept','Cheetah · Concept'],
'Us em Skizzebuech':['Aus dem Skizzenbuch','From the sketchbook'],'Alternative, wo s nid worde si':['Alternativen, die es nicht geworden sind','Alternatives that didn’t make it'],
'Für jedi nöii Sorte hei mir mehreri Tier probiert. Die hie hei mir gärn übercho — aber nume eis pro Sorte darf uf d Fläsche.':['Für jede neue Sorte haben wir mehrere Tiere ausprobiert. Diese hier mögen wir sehr — aber nur eines pro Sorte darf auf die Flasche.','For every new flavour we tried several beasts. We grew fond of these — but only one per flavour gets onto the bottle.'],
'Mango Lassi · Fuutier':['Mango Lassi · Faultier','Mango Lassi · Sloth'],'Mango Lassi · Faultier':['Mango Lassi · Faultier','Mango Lassi · Sloth'],'Mango Lassi · Tiger':['Mango Lassi · Tiger','Mango Lassi · Tiger'],
'Mandarine Nuss · Eichhörnli':['Mandarine Nuss · Eichhörnchen','Mandarine Nuss · Squirrel'],'Mandarine Nuss · Eichhörnchen':['Mandarine Nuss · Eichhörnchen','Mandarine Nuss · Squirrel'],'Mandarine Nuss · Siebenschläfer':['Mandarine Nuss · Siebenschläfer','Mandarine Nuss · Dormouse'],
'Zrügg zur nöie Linie':['Zurück zur neuen Linie','Back to the new line'],'Kaffernbüffel':['Kaffernbüffel','Cape buffalo'],'Gepard':['Gepard','Cheetah']
};
var LS='bv-lang',ATTR=['alt','aria-label','title','content'],ORIG=new WeakMap(),lang='be';
try{lang=localStorage.getItem(LS)||'be';}catch(e){}
function tr(be){var t=be.trim(),e=D[t];if(!e||lang==='be')return be;var v=e[lang==='de'?0:1];return be.replace(t,v);}
function doText(n){if(!ORIG.has(n)){if(!D[n.nodeValue.trim()])return;ORIG.set(n,n.nodeValue);if(n.parentElement&&!n.parentElement.hasAttribute('data-i18n'))n.parentElement.setAttribute('data-i18n',n.nodeValue.trim().slice(0,40));}
 var v=tr(ORIG.get(n));if(n.nodeValue!==v)n.nodeValue=v;}
function doEl(el){ATTR.forEach(function(a){if(a==='content'&&el.getAttribute('name')!=='description')return;var k='data-i18n-'+a,o=el.getAttribute(k);
 if(o==null){var c=el.getAttribute(a);if(c==null||!D[c.trim()])return;el.setAttribute(k,c);o=c;}var v=tr(o);if(el.getAttribute(a)!==v)el.setAttribute(a,v);});}
function walk(root){if(root.nodeType===3){doText(root);return;}if(root.nodeType!==1)return;
 var w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:function(n){var p=n.parentNode&&n.parentNode.nodeName;return p==='SCRIPT'||p==='STYLE'?2:1;}}),n;while((n=w.nextNode()))doText(n);
 doEl(root);root.querySelectorAll('[alt],[aria-label],[title],meta[name=description]').forEach(doEl);}
var busy=false;
function apply(){busy=true;document.documentElement.lang=lang==='be'?'de-CH':(lang==='de'?'de':'en');walk(document.head);walk(document.body);
 document.querySelectorAll('.langsw button').forEach(function(b){var on=b.dataset.lang===lang;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on);});busy=false;}
function set(l){lang=l;try{localStorage.setItem(LS,l);}catch(e){}apply();}
function pill(){var nav=document.querySelector('.nav, nav');if(document.querySelector('.langsw'))return;var d=document.createElement('div');d.className='langsw';d.setAttribute('role','group');d.setAttribute('aria-label','Sprache / Language');
 [['be','BE','Bärndütsch'],['de','DE','Deutsch'],['en','EN','English']].forEach(function(x){var b=document.createElement('button');b.type='button';b.dataset.lang=x[0];b.textContent=x[1];b.title=x[2];b.addEventListener('click',function(){set(x[0]);});d.appendChild(b);});
 if(nav)nav.appendChild(d);else{d.classList.add('fixed');document.body.appendChild(d);}}
function init(){pill();apply();new MutationObserver(function(ms){if(busy)return;busy=true;ms.forEach(function(m){if(m.type==='characterData'){if(ORIG.has(m.target)&&D[m.target.nodeValue.trim()])ORIG.delete(m.target);doText(m.target);}else m.addedNodes.forEach(function(n){if(n.nodeType===3&&ORIG.has(n))ORIG.delete(n);walk(n);});});busy=false;})
 .observe(document.body,{childList:true,subtree:true,characterData:true});}
window.bvI18n={set:set,get lang(){return lang;}};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
