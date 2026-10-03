/*
 * Aura live demo — a scripted receptionist that runs fully in the browser,
 * so prospects can try it without a backend. Personalise with
 *   ?biz=dental&name=Smile%20Life%20Dental%20Clinic
 */
(function(){
  var P = {
    clinic:{label:"Clinic",name:"Demo Family Clinic",color:"#0f766e",
      hours:"Mon–Sat 8:00am–10:00pm, Sun 8:00am–4:00pm",
      services:[["GP consultation","RM 45"],["Health screening","from RM 150"],["Vaccination (flu)","RM 85"],["Medical check-up for work","RM 60"]],
      extra:{panel:"Yes, we're a panel clinic for most major insurers and company panels. Please bring your panel card or GL.",walkin:"Walk-ins are welcome! Average waiting time right now is about 15 minutes, or I can book you a slot so you skip the queue."}},
    dental:{label:"Dental",name:"Demo Dental Clinic",color:"#0e7490",
      hours:"Mon–Sat 9:00am–7:00pm, closed Sunday",
      services:[["Scaling & polishing","RM 120"],["Tooth filling","from RM 100"],["Teeth whitening","RM 900"],["Braces / Invisalign consultation","Free"]],
      extra:{pain:"Sorry to hear that! For toothache we keep emergency slots every day. Shall I book the earliest one for you?",panel:"We accept most company panels and insurance. Please bring your panel card."}},
    beauty:{label:"Salon / Beauty",name:"Demo Beauty Studio",color:"#be185d",
      hours:"Tue–Sun 10:00am–8:00pm, closed Monday",
      services:[["Women's cut & blow","RM 68"],["Hair colour","from RM 180"],["Gel manicure","RM 75"],["Eyelash extension","RM 128"],["Facial (60 min)","RM 150"]],
      extra:{stylist:"Of course! Tell me your preferred stylist and I'll check their slots.",promo:"This month: first-time customers get 20% off any facial 💆‍♀️"}},
    fitness:{label:"Gym / Studio",name:"Demo Fitness Studio",color:"#c2410c",
      hours:"Daily 6:30am–10:00pm",
      services:[["Trial class","Free"],["Monthly membership","RM 199"],["10-class pass","RM 280"],["Personal training (1 hr)","RM 120"]],
      extra:{trial:"Your first class is free! Shall I book you a trial class this week?",beginner:"Absolutely, most of our members started as beginners. Our coaches adjust every class to your level."}},
    tuition:{label:"Tuition / Preschool",name:"Demo Learning Centre",color:"#4338ca",
      hours:"Mon–Fri 2:00pm–9:00pm, Sat–Sun 9:00am–5:00pm",
      services:[["Primary (per subject)","RM 120/month"],["Secondary / SPM (per subject)","RM 160/month"],["IGCSE (per subject)","RM 220/month"],["Free trial class","Free"]],
      extra:{trial:"Every new student gets a free trial class. Which subject and level is it for?",teacher:"All our teachers are degree holders with 5+ years' experience, and class sizes are kept small (max 8)."}},
    pets:{label:"Vet / Pets",name:"Demo Animal Clinic",color:"#15803d",
      hours:"Mon–Sat 10:00am–8:00pm, Sun 10:00am–2:00pm",
      services:[["Consultation","RM 50"],["Vaccination (dog/cat)","from RM 80"],["Grooming (small dog)","RM 70"],["Spay / neuter","from RM 250"]],
      extra:{emergency:"If this is an emergency, please call us right away. I'll pass your details to the vet on duty too.",boarding:"Yes, we have boarding. It's RM 40/night for cats and from RM 50/night for dogs."}},
    physio:{label:"Physio / Wellness",name:"Demo Physio Centre",color:"#0369a1",
      hours:"Mon–Sat 9:00am–8:00pm, closed Sunday",
      services:[["Initial assessment & treatment","RM 150"],["Follow-up session","RM 120"],["Sports massage (60 min)","RM 140"],["Clinical pilates (private)","RM 160"]],
      extra:{pain:"Sorry you're in pain. Our physio will assess it in your first session. Shall I book the earliest assessment slot?",panel:"We accept selected insurance and company panels. Please bring your card and we'll check for you."}},
    optical:{label:"Optical",name:"Demo Optometry",color:"#7c3aed",
      hours:"Daily 10:00am–9:00pm",
      services:[["Comprehensive eye test","Free with purchase / RM 30"],["Single-vision lenses","from RM 180"],["Progressive / multifocal lenses","from RM 650"],["Contact lens fitting","RM 50"]],
      extra:{kid:"Yes, we do children's eye exams and myopia control. Shall I book a slot?",ready:"Most glasses are ready in 3–5 working days."}},
    general:{label:"Local Services",name:"Demo Services Co.",color:"#b45309",
      hours:"Mon–Sat 9:00am–6:00pm, closed Sunday",
      services:[["Free consultation & quote","Free"],["Site visit / meeting","Free within Subang Jaya"],["Standard package","from RM 500"],["Premium package","from RM 1,500"]],
      extra:{quote:"Happy to prepare a quote! Can I have your name, WhatsApp number and a short description of what you need?",urgent:"For urgent requests I'll pass your details to our team on WhatsApp right away."}},
    services:{label:"Professional",name:"Demo Services Firm",color:"#1d4ed8",
      hours:"Mon–Fri 9:00am–6:00pm, closed Saturday & Sunday",
      services:[["Free first consultation (30 min)","Free"],["Company incorporation","from RM 1,500"],["Monthly bookkeeping","from RM 300"],["Tax filing (individual)","from RM 250"]],
      extra:{quote:"Happy to prepare a quote! Can I have your name, WhatsApp number and a short description of what you need?"}}
  };
  var catMap = {gp:"clinic",clinic:"clinic",medical:"clinic",physio:"physio",chiro:"physio",pain:"physio",optometrist:"optical",
    dental:"dental",dentist:"dental",
    aesthetic:"beauty",skin:"beauty",salon:"beauty",barber:"beauty",beauty:"beauty",spa:"beauty",nail:"beauty",lash:"beauty",massage:"beauty",reflexology:"beauty",
    gym:"fitness",fitness:"fitness",yoga:"fitness",pilates:"fitness",dance:"fitness",
    tuition:"tuition",preschool:"tuition",kindergarten:"tuition",music:"tuition",school:"tuition",driving:"tuition",
    vet:"pets",veterinary:"pets",pet:"pets",grooming:"pets"};

  var qs = new URLSearchParams(location.search);
  var key = (qs.get("biz")||"clinic").toLowerCase();
  key = P[key] ? key : (catMap[key] || "general");
  var personalName = (qs.get("name")||"").slice(0,60);
  var cur, state = {}, homeKey = key;

  var $ = function(id){return document.getElementById(id)};
  var log = $("log"), input = $("msg");

  function esc(t){return t.replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  function fmt(t){return esc(t).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>")}
  function add(t,who){var d=document.createElement("div");d.className="m "+(who==="me"?"me":"bot");d.innerHTML=fmt(t);log.appendChild(d);log.scrollTop=log.scrollHeight;return d}
  function botSay(t){var d=add("…","bot");d.classList.add("typing");setTimeout(function(){d.classList.remove("typing");d.innerHTML=fmt(t);log.scrollTop=log.scrollHeight},600+Math.min(900,t.length*6))}

  function slots(){
    var d=new Date();d.setDate(d.getDate()+1);
    if(d.getDay()===0 && /closed sunday|closed saturday & sunday/i.test(cur.hours)) d.setDate(d.getDate()+1);
    var day=d.toLocaleDateString("en-MY",{weekday:"long",day:"numeric",month:"short"});
    return {day:day,times:["10:30am","2:00pm","4:30pm"]};
  }
  function menu(){return cur.services.map(function(s){return "• "+s[0]+": "+s[1]}).join("\n")}

  function lang(t){
    if(/[一-鿿]/.test(t)) return "zh";
    if(/\b(berapa|harga|boleh|nak|saya|esok|buka|tutup|pukul|janji|temu|terima|kasih|ada|tak|bila|mana|alamat)\b/i.test(t)) return "ms";
    return "en";
  }
  function slots(){
    var d=new Date();d.setDate(d.getDate()+1);
    if(d.getDay()===0 && /closed sunday/i.test(cur.hours)) d.setDate(d.getDate()+1); // skip closed Sundays
    var day=d.toLocaleDateString("en-MY",{weekday:"long",day:"numeric",month:"short"});
    return {day:day,times:["10:30am","2:00pm","4:30pm"]};
  }
  function menu(){return cur.services.map(function(s){return "• "+s[0]+": "+s[1]}).join("\n")}

  function reply(t){
    var l=lang(t), x=t.toLowerCase();
    // booking flow continuation
    if(state.step==="pick"){
      var m=x.match(/(10[:.]?30|2[:.]?00|4[:.]?30|\b2\s?pm|\b4|\b10)/);
      if(m||/first|pertama|第一|ok|yes|ya|boleh|好/.test(x)){
        var pick = m ? (/10/.test(m[0])?"10:30am":/4/.test(m[0])?"4:30pm":"2:00pm") : state.s.times[0];
        state.time=pick;state.step="name";
        return l==="ms"?"Baik! "+state.s.day+", "+pick+" ✅ Boleh saya dapatkan nama dan nombor telefon anda untuk pengesahan?":
               l==="zh"?"好的！已为您保留 "+state.s.day+" "+pick+" ✅ 请提供您的姓名和电话号码以确认预约。":
               "Great choice! I've held "+state.s.day+" at "+pick+" for you ✅ May I have your name and phone number to confirm?";
      }
    }
    if(state.step==="name" && (/\d{6,}/.test(x.replace(/[\s-]/g,""))||x.split(" ").length<=4)){
      state.step=null;
      var ref="BK-"+Math.random().toString(36).slice(2,8).toUpperCase();
      return l==="ms"?"Tempahan disahkan! 🎉 Rujukan: **"+ref+"**. Kami akan hantar peringatan WhatsApp sehari sebelum. Jumpa nanti!":
             l==="zh"?"预约成功！🎉 编号：**"+ref+"**。我们会在前一天通过 WhatsApp 提醒您。到时见！":
             "You're booked! 🎉 Reference **"+ref+"**. We'll send a WhatsApp reminder the day before. See you then!\n\n(Behind the scenes: added to the calendar, saved to the customer list, and the no-show risk was checked.)";
    }
    if(/book|appointment|slot|available|tomorrow|janji|temu|tempah|esok|预约|预定|明天|trial|reserve/.test(x)){
      state.s=slots();state.step="pick";
      return l==="ms"?"Boleh! Slot kosong terdekat ("+state.s.day+"): "+state.s.times.join(", ")+". Yang mana sesuai?":
             l==="zh"?"可以！最近可预约的日子（"+state.s.day+"）还有这些时段："+state.s.times.join("、")+"。您想选哪个？":
             "Sure! Here's the next available day ("+state.s.day+"): "+state.s.times.join(", ")+". Which works for you?";
    }
    if(/price|cost|how much|rate|fee|harga|berapa|caj|多少钱|价格|收费|package|menu|service|perkhidmatan|服务/.test(x)){
      return (l==="ms"?"Ini senarai harga kami:\n":l==="zh"?"这是我们的价格：\n":"Here are our prices:\n")+menu()+
        (l==="ms"?"\n\nNak saya tempahkan slot?":l==="zh"?"\n\n需要我帮您预约吗？":"\n\nWould you like me to book a slot?");
    }
    if(/hour|open|close|buka|tutup|营业|几点|时间|sunday|ahad|weekend/.test(x)){
      return l==="ms"?"Waktu operasi kami: "+cur.hours+".":l==="zh"?"我们的营业时间："+cur.hours+"。":"We're open "+cur.hours+".";
    }
    if(/where|address|location|park|alamat|mana|parking|地址|在哪|停车/.test(x)){
      return l==="ms"?"Kami di Subang Jaya, 5 minit dari LRT SS15. Parking tepi jalan & di SS15 Courtyard.":
             l==="zh"?"我们位于梳邦再也，离 SS15 轻快铁站步行 5 分钟。附近有路边停车位和 SS15 Courtyard 停车场。":
             "We're in Subang Jaya, about 5 minutes' walk from SS15 LRT. There's street parking and covered parking at SS15 Courtyard nearby.";
    }
    if(/human|staff|person|talk|whatsapp|call|manusia|staf|人工|客服|complain|aduan/.test(x)){
      return l==="ms"?"Tiada masalah. Saya sambungkan anda ke staf kami di WhatsApp dengan ringkasan perbualan ini. 📲":
             l==="zh"?"没问题，我会把对话摘要一起转给我们的同事，请在 WhatsApp 继续联系。📲":
             "No problem! I'll connect you to our team on WhatsApp and pass on a summary of this chat, so you won't have to repeat yourself. 📲";
    }
    for(var k in cur.extra){ if(x.indexOf(k)>-1) return cur.extra[k]; }
    if(/pay|card|cash|duitnow|tng|ewallet|bayar|付款/.test(x)) return "We accept cash, cards, DuitNow QR, Touch 'n Go eWallet and GrabPay.";
    if(/hi|hello|hai|helo|salam|你好|hey/.test(x)) return l==="ms"?"Hai! Apa yang boleh saya bantu hari ini?":l==="zh"?"您好！今天有什么可以帮您？":"Hi there! How can I help you today?";
    if(/thank|terima kasih|谢谢|tq/.test(x)) return l==="ms"?"Sama-sama! 😊":l==="zh"?"不客气！😊":"You're welcome! 😊";
    return l==="ms"?"Soalan yang bagus! Saya boleh bantu dengan harga, waktu operasi, lokasi atau tempahan. Untuk perkara lain, saya akan sambungkan anda ke staf kami di WhatsApp.":
           l==="zh"?"好问题！我可以帮您查询价格、营业时间、地址或预约。其他问题我会转给我们的同事。":
           "Good question! I can help with prices, opening hours, location and bookings. For anything else, I'll pass you to our team on WhatsApp so a person can answer.";
  }

  // Hero copy follows the demo: personalised only while the visitor's own
  // business is showing; any other tab switches back to the general copy.
  var hero = { pill: $("pill"), head: $("headline") };
  var defaults = { pill: hero.pill.textContent, head: hero.head.textContent };
  function setHero(personal){
    if(personal){
      hero.pill.textContent = "Demo prepared for " + personalName;
      hero.head.textContent = personalName + ", open all night.";
    } else {
      hero.pill.textContent = defaults.pill;
      hero.head.textContent = defaults.head;
    }
  }

  var CHIPS = ["How much?","Book tomorrow","Buka hari Ahad?","几点关门？","Talk to a person"];
  function chips(){
    var box=$("chips"); box.innerHTML="";
    CHIPS.forEach(function(t){var b=document.createElement("button");b.className="chip";b.type="button";b.textContent=t;b.onclick=function(){send(t)};box.appendChild(b)});
  }
  function load(k, personal){
    key=k; cur=P[k]; state={};
    var name = personal ? personalName : cur.name;
    $("biz-name").textContent = name;
    $("av").textContent = name.charAt(0).toUpperCase();
    log.innerHTML="";
    add("Hi! Welcome to "+name+". I can share prices, answer questions and book appointments in English, BM or 中文. How can I help?","bot");
    [].forEach.call(document.querySelectorAll("#switch button"),function(b){
      var on = b.dataset.k===k;
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    setHero(personal);
  }
  function send(t){add(t,"me");botSay(reply(t))}

  Object.keys(P).forEach(function(k){
    var b=document.createElement("button");
    b.type="button"; b.textContent=P[k].label; b.dataset.k=k;
    b.onclick=function(){ load(k, !!personalName && k===homeKey); };
    $("switch").appendChild(b);
  });
  $("form").onsubmit=function(e){e.preventDefault();var t=input.value.trim();if(!t)return;input.value="";send(t)};
  chips();
  load(key, !!personalName);
})();
