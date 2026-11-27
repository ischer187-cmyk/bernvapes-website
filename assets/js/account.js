/* Kunden-Login im Header (oben rechts) und die Seite konto.html.
   Spricht mit dem lokalen CRM über /b2b-api/customer. */
(function () {
  var API = '/b2b-api/customer';
  var me = null;
  var csrf = null;

  function L(s) {
    var de = {
      'Aamälde': 'Anmelden',
      'Mis Konto': 'Mein Konto',
      'Registriere': 'Registrieren',
      'Abmälden': 'Abmelden',
      'Passwort vergässe': 'Passwort vergessen',
      'Adrässe': 'Adresse',
      'I bi 18 oder elter. Kei Usweis, nume die Bestätigung.': 'Ich bin 18 oder älter. Kein Ausweis, nur diese Bestätigung.',
      'Konto aalege': 'Konto anlegen',
      'Neus Passwort': 'Neues Passwort',
      'Passwort setze': 'Passwort setzen',
      'Zrügg zum Aamälde': 'Zurück zum Anmelden',
      'Die Aamäldig het nid klappet.': 'Die Anmeldung hat nicht geklappt.',
      'Die E-Mail git’s scho.': 'Diese E-Mail gibt es schon.',
      'Bitte 18+ bestätige.': 'Bitte 18+ bestätigen.',
      'Z vil Versüech. Churz warte.': 'Zu viele Versuche. Kurz warten.',
      'CRM nid erreichbar.': 'CRM nicht erreichbar.',
      'Letschti Aamäldig': 'Letzte Anmeldung',
      'Link isch im Mail-Log. Es wird nüt verschickt.': 'Der Link steht im Mail-Log. Es wird nichts verschickt.',
      'Wen es für die E-Mail es Konto git, chunnt e Link zum Zruggsetze.': 'Wenn es für diese E-Mail ein Konto gibt, kommt ein Link zum Zurücksetzen.',
      'Passwort (mind. 10 Zeiche)': 'Passwort (mind. 10 Zeichen)',
      'Konto aagleit. Willkomme bi Bernvapes!': 'Konto erstellt. Willkommen bei Bernvapes!',
      'Die E-Mail isch scho registriert. Bitte aamälde.': 'Diese E-Mail ist bereits registriert. Bitte melde dich an.',
      'Bitte warte …': 'Bitte warten …'
    };
    var german = de[s] || s;
    var lang = (window.bvI18n && window.bvI18n.lang) || 'de';
    if ((lang === 'fr' || lang === 'en') && window.bvI18n && window.bvI18n.t) {
      var via = window.bvI18n.t(german);
      if (via && via !== german) return via;
    }
    return german;
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }
  function api(path, opts) {
    opts = opts || {};
    var headers = { 'Accept': 'application/json' };
    if (opts.body) headers['Content-Type'] = 'application/json';
    if (csrf && opts.method && opts.method !== 'GET') headers['X-CSRF-Token'] = csrf;
    return fetch(API + path, {
      method: opts.method || 'GET',
      headers: headers,
      credentials: 'same-origin',
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (data && data.csrf_token) csrf = data.csrf_token;
        return { status: res.status, data: data };
      });
    }).catch(function () {
      return { status: 0, data: { error: 'crm_unreachable' } };
    });
  }
  function errText(code) {
    if (code === 'login_failed') return L('Die Aamäldig het nid klappet.');
    if (code === 'email_taken') return L('Die E-Mail isch scho registriert. Bitte aamälde.');
    if (code === 'dealer_email') return window.BV_B2B_ENABLED ? L('Für Lädeli geit’s ins Händler-Portal.') : L('Die E-Mail git’s scho.');
    if (code === 'age_required') return L('Bitte 18+ bestätige.');
    if (code === 'rate_limited') return L('Z vil Versüech. Churz warte.');
    if (code === 'crm_unreachable') return L('CRM nid erreichbar.');
    if (code === 'reset_invalid') return L('Die Aamäldig het nid klappet.');
    return L('Die Aamäldig het nid klappet.');
  }
  function field(id, label, type, extra) {
    return '<div class="fld"><label for="' + id + '">' + esc(L(label)) + '</label><input id="' + id + '" name="' + id + '" type="' + type + '" ' + (extra || '') + '></div>';
  }
  function label() {
    return me ? L('Mis Konto') : L('Aamälde');
  }
  function paintHeader() {
    var text = label();
    var a = document.getElementById('navlogin');
    if (a) { a.textContent = text; a.href = 'konto.html'; }
    var nodes = document.querySelectorAll('.menu-login-link');
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].textContent = text;
      nodes[i].href = 'konto.html';
    }
    var menu = document.getElementById('navmenu');
    if (menu) menu.textContent = L('Menü');
  }
  function mountHeader() {
    var bar = document.querySelector('.shopbar');
    if (!bar) {
      bar = document.createElement('div');
      bar.className = 'shopbar';
      document.body.appendChild(bar);
    }
    var a = document.getElementById('navlogin');
    if (!a) {
      a = document.createElement('a');
      a.className = 'navlogin';
      a.id = 'navlogin';
      a.href = 'konto.html';
      a.textContent = L('Aamälde');
    }
    if (a.parentElement !== bar) bar.insertBefore(a, bar.firstChild);
    var cart = document.querySelector('.navcart');
    if (cart && cart.parentElement !== bar) bar.appendChild(cart);
    var sw = document.querySelector('.langsw');
    if (sw && sw.parentElement !== bar) bar.appendChild(sw);
    var lists = document.querySelectorAll('.nav ul');
    for (var i = 0; i < lists.length; i++) {
      if (lists[i].querySelector('.menu-login')) continue;
      var li = document.createElement('li');
      li.className = 'menu-login';
      var link = document.createElement('a');
      link.className = 'menu-login-link';
      link.href = 'konto.html';
      link.textContent = L('Aamälde');
      li.appendChild(link);
      lists[i].appendChild(li);
    }
    if (!document.getElementById('navmenu') && document.querySelector('.nav')) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.id = 'navmenu';
      btn.className = 'navmenubtn';
      btn.setAttribute('aria-expanded', 'false');
      btn.textContent = L('Menü');
      btn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        var nav = document.querySelector('.nav');
        if (!nav) return;
        var open = nav.classList.toggle('menu-open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      document.addEventListener('click', function (ev) {
        var nav = document.querySelector('.nav');
        if (!nav || !nav.classList.contains('menu-open')) return;
        if (ev.target.closest && ev.target.closest('.nav a')) {
          nav.classList.remove('menu-open');
          btn.setAttribute('aria-expanded', 'false');
        }
      });
      document.body.appendChild(btn);
    }
    paintHeader();
    fitNav();
  }
  function fitNav(){
    var nav=document.querySelector('.nav');
    var bar=document.querySelector('.shopbar');
    if(!nav) return;
    if(!bar||innerWidth<=760){ nav.style.paddingRight=''; return; }
    var gap=Math.ceil(innerWidth-bar.getBoundingClientRect().left)+16;
    nav.style.paddingRight=gap+'px';
  }
  addEventListener('resize',function(){ fitNav(); });

  function shell(html) {
    var root = document.getElementById('konto');
    if (!root) return null;
    root.innerHTML = html;
    return root;
  }
  function nextPage() {
    var n = new URLSearchParams(location.search).get('next') || '';
    if (/^(kasse|kasse-ok|kasse-fail)\.html$/.test(n)) return n;
    return '';
  }
  /* Login, Registrieren und Passwort-vergessen behalten ?next=, sonst landet
     jemand, der von der Kasse kam, nach dem Konto-Anlegen nur auf «Abmelden». */
  function keepNext(href) {
    var n = nextPage();
    if (!n) return href;
    return href + (href.indexOf('?') >= 0 ? '&' : '?') + 'next=' + encodeURIComponent(n);
  }
  function cartCount() {
    try {
      var v = JSON.parse(localStorage.getItem('bv-cart'));
      if (!Array.isArray(v)) return 0;
      return v.reduce(function (n, it) { return n + (Number(it.qty) || 1); }, 0);
    } catch (e) { return 0; }
  }
  function mode() {
    var q = new URLSearchParams(location.search);
    if (q.get('token')) return 'reset';
    if (q.get('neu')) return 'register';
    if (q.get('vergessen') || q.get('vergässe')) return 'forgot';
    return 'login';
  }
  /* Sperrt das Formular, bis die Antwort da ist. Gibt false zurück, wenn schon gesendet wird. */
  function lock(form) {
    if (!form || form.dataset.busy === '1') return false;
    form.dataset.busy = '1';
    var b = form.querySelector('button[type="submit"]');
    if (b) { b.disabled = true; b.setAttribute('aria-busy', 'true'); b.dataset.label = b.textContent; b.textContent = L('Bitte warte …'); }
    return true;
  }
  function scrollToMsg(root) {
    var m = root && root.querySelector('.ok, .err');
    if (!m) return;
    try {
      var r = m.getBoundingClientRect();
      if (r.top < 70 || r.bottom > innerHeight) scrollTo({ top: scrollY + r.top - 90, behavior: 'smooth' });
    } catch (e) {}
  }
  function renderAccount(notice) {
    var root = shell(
      (notice ? '<div class="ok" role="status">' + esc(notice) + '</div>' : '')
      + '<h2>' + esc(L('Mis Konto')) + '</h2>'
      + '<p>' + esc(me.name) + '<br>' + esc(me.email) + '</p>'
      + '<p class="muted">' + esc(me.address || '') + (me.zip || me.city ? '<br>' + esc((me.zip || '') + ' ' + (me.city || '')) : '') + '</p>'
      + '<p class="muted">' + esc(L('Registriert')) + ': ' + esc((me.created_at || '').slice(0, 16))
      + '<br>' + esc(L('Letschti Aamäldig')) + ': ' + esc((me.last_login_at || '').slice(0, 16)) + '</p>'
      + '<p class="muted">18+ · Checkbox. Kei e-ID, kei Usweis.</p>'
      + '<p><a class="btn" id="zur-kasse" href="kasse.html">' + esc(L('Zur Kasse')) + '</a></p>'
      + '<p class="muted" id="cart-hint"></p>'
      + '<p><a href="index.html">' + esc(L('Zum Shop')) + '</a></p>'
      + '<p><button class="btn ghost" type="button" id="out">' + esc(L('Abmälden')) + '</button></p>'
      + (window.BV_B2B_ENABLED ? '<p><a href="haendler.html">' + esc(L('Händler-Portal')) + '</a></p>' : '')
    );
    if (!root) return;
    var hint = root.querySelector('#cart-hint');
    if (hint) {
      var nItems = cartCount();
      hint.textContent = nItems
        ? (nItems + ' im Warenkorb. Die Alters- und AGB-Bestätigung steht an der Kasse.')
        : 'Der Warenkorb ist leer. Die Kasse bleibt erreichbar.';
    }
    root.querySelector('#out').onclick = function () {
      api('/logout', { method: 'POST', body: {} }).then(function () {
        me = null; csrf = null;
        paintHeader();
        location.href = 'konto.html';
      });
    };
  }
  function renderLogin(error, email) {
    var root = shell(
      (error ? '<div class="err" role="alert">' + esc(error) + '</div>' : '')
      + '<h2>' + esc(L('Aamälde')) + '</h2><form id="f">'
      + field('email', 'E-Mail', 'email', 'required autocomplete="username"')
      + field('password', 'Passwort', 'password', 'required autocomplete="current-password"')
      + '<p style="margin-top:16px"><button class="btn" type="submit">' + esc(L('Aamälde')) + '</button></p></form>'
      + '<p><a href="' + esc(keepNext('konto.html?neu=1')) + '">' + esc(L('Registriere')) + '</a> · <a href="' + esc(keepNext('konto.html?vergessen=1')) + '">' + esc(L('Passwort vergässe')) + '</a></p>'
      + (window.BV_B2B_ENABLED ? '<p class="muted"><a href="haendler.html">' + esc(L('Händler-Portal')) + '</a></p>' : '')
    );
    if (!root) return;
    if (email) {
      var em = root.querySelector('#email');
      if (em) em.value = email;
      var pw = root.querySelector('#password');
      if (pw) pw.focus();
    }
    if (error) scrollToMsg(root);
    root.querySelector('#f').onsubmit = function (ev) {
      ev.preventDefault();
      var fd = new FormData(ev.target);
      if (!lock(ev.target)) return;
      api('/login', { method: 'POST', body: { email: fd.get('email'), password: fd.get('password') } }).then(function (r) {
        if (r.status === 200 && r.data.ok) {
          me = r.data; paintHeader();
          var n = nextPage();
          if (n) { location.href = n; return; }
          renderAccount();
          return;
        }
        renderLogin(errText(r.data && r.data.error), fd.get('email'));
      });
    };
  }
  function renderRegister(error, values) {
    var root = shell(
      (error ? '<div class="err" role="alert">' + esc(error) + '</div>' : '')
      + '<h2>' + esc(L('Registriere')) + '</h2><form id="f"><div class="row2">'
      + field('name', 'Name', 'text', 'required autocomplete="name"')
      + field('email', 'E-Mail', 'email', 'required autocomplete="username"')
      + field('address', 'Adrässe', 'text', 'required autocomplete="street-address"')
      + field('zip', 'PLZ', 'text', 'required autocomplete="postal-code" style="max-width:140px"')
      + field('city', 'Ort', 'text', 'required autocomplete="address-level2"')
      + field('password', 'Passwort (mind. 10 Zeiche)', 'password', 'required minlength="10" autocomplete="new-password"')
      + '</div><label class="agebox"><input type="checkbox" name="age_18" id="age_18"> '
      + esc(L('I bi 18 oder elter. Kei Usweis, nume die Bestätigung.')) + '</label>'
      + '<p style="margin-top:16px"><button class="btn" type="submit">' + esc(L('Konto aalege')) + '</button></p></form>'
      + '<p><a href="' + esc(keepNext('konto.html')) + '">' + esc(L('Zrügg zum Aamälde')) + '</a></p>'
    );
    if (!root) return;
    if (values) {
      ['name', 'email', 'address', 'zip', 'city'].forEach(function (k) {
        var el = root.querySelector('#' + k);
        if (el && values[k] != null) el.value = values[k];
      });
      var ab = root.querySelector('#age_18');
      if (ab) ab.checked = !!values.age_18;
    }
    if (error) scrollToMsg(root);
    root.querySelector('#f').onsubmit = function (ev) {
      ev.preventDefault();
      var fd = new FormData(ev.target);
      /* Nur ein Request pro Absenden. Ein Doppelklick schickte sonst ein zweites /register,
         das mit 409 zurückkam und das frisch angelegte Konto wieder mit einer Fehlermeldung überdeckte. */
      if (!lock(ev.target)) return;
      var values = {
        name: fd.get('name'), email: fd.get('email'), address: fd.get('address'),
        zip: fd.get('zip'), city: fd.get('city'), age_18: fd.get('age_18') === 'on'
      };
      api('/register', { method: 'POST', body: {
        name: fd.get('name'), email: fd.get('email'), address: fd.get('address'),
        zip: fd.get('zip'), city: fd.get('city'), password: fd.get('password'),
        age_18: fd.get('age_18') === 'on'
      }}).then(function (r) {
        if ((r.status === 201 || r.status === 200) && r.data.ok) {
          me = r.data; paintHeader();
          var okMsg = L('Konto aagleit. Willkomme bi Bernvapes!');
          var n = nextPage();
          if (n) {
            try { sessionStorage.setItem('bv-konto-neu', '1'); } catch (e) {}
            location.href = n; return;
          }
          renderAccount(okMsg);
          scrollToMsg(document.getElementById('konto'));
          return;
        }
        var code = r.data && r.data.error;
        if (code === 'email_taken') {
          /* Bestehende E-Mail: direkt zum Anmelden, E-Mail schon eingetragen. */
          if (history.replaceState) history.replaceState(null, '', keepNext('konto.html'));
          renderLogin(errText(code), values.email);
          return;
        }
        renderRegister(errText(code), values);
      });
    };
  }
  function renderForgot(notice, error) {
    var root = shell(
      (error ? '<div class="err">' + esc(error) + '</div>' : '')
      + (notice ? '<div class="ok">' + esc(notice) + '</div>' : '')
      + '<h2>' + esc(L('Passwort vergässe')) + '</h2><form id="f">'
      + field('email', 'E-Mail', 'email', 'required')
      + '<p style="margin-top:16px"><button class="btn" type="submit">' + esc(L('Passwort vergässe')) + '</button></p></form>'
      + '<p class="muted">' + esc(L('Wen es für die E-Mail es Konto git, chunnt e Link zum Zruggsetze.')) + '</p>'
      + '<p><a href="' + esc(keepNext('konto.html')) + '">' + esc(L('Zrügg zum Aamälde')) + '</a></p>'
    );
    if (!root) return;
    root.querySelector('#f').onsubmit = function (ev) {
      ev.preventDefault();
      api('/forgot', { method: 'POST', body: { email: new FormData(ev.target).get('email') } }).then(function (r) {
        if (r.status === 200) renderForgot(L('Wen es für die E-Mail es Konto git, chunnt e Link zum Zruggsetze.'), '');
        else renderForgot('', errText(r.data && r.data.error));
      });
    };
  }
  function renderReset(error) {
    var token = new URLSearchParams(location.search).get('token');
    var root = shell(
      (error ? '<div class="err">' + esc(error) + '</div>' : '')
      + '<h2>' + esc(L('Neus Passwort')) + '</h2><form id="f">'
      + field('password', 'Passwort (mind. 10 Zeiche)', 'password', 'required minlength="10" autocomplete="new-password"')
      + '<p style="margin-top:16px"><button class="btn" type="submit">' + esc(L('Passwort setze')) + '</button></p></form>'
    );
    if (!root) return;
    root.querySelector('#f').onsubmit = function (ev) {
      ev.preventDefault();
      api('/reset', { method: 'POST', body: { token: token, password: new FormData(ev.target).get('password') } }).then(function (r) {
        if (r.status === 200 && r.data.ok) { me = r.data; paintHeader(); history.replaceState(null, '', 'konto.html'); renderAccount(); return; }
        renderReset(errText(r.data && r.data.error));
      });
    };
  }
  function renderPage() {
    if (!document.getElementById('konto')) return;
    if (me) return renderAccount();
    var m = mode();
    if (m === 'register') return renderRegister();
    if (m === 'forgot') return renderForgot();
    if (m === 'reset') return renderReset();
    return renderLogin();
  }
  /* Wer sich auf dem Weg zur Kasse registriert, landet direkt dort. Die Erfolgsmeldung
     kommt dann als kurze Einblendung auf der Zielseite. */
  function welcomeAfterRedirect() {
    var flag = null;
    try { flag = sessionStorage.getItem('bv-konto-neu'); sessionStorage.removeItem('bv-konto-neu'); } catch (e) {}
    if (!flag) return;
    var t = document.createElement('div');
    t.className = 'carttoast';
    t.setAttribute('role', 'status');
    t.setAttribute('aria-live', 'polite');
    t.textContent = L('Konto aagleit. Willkomme bi Bernvapes!');
    document.body.appendChild(t);
    setTimeout(function () { t.hidden = true; }, 5000);
  }
  function boot() {
    welcomeAfterRedirect();
    mountHeader();
    setTimeout(mountHeader, 0);
    api('/me').then(function (r) {
      me = (r.status === 200 && r.data && r.data.ok) ? r.data : null;
      paintHeader();
      var n = nextPage();
      if (me && n && document.getElementById('konto')) { location.href = n; return; }
      renderPage();
    });
  }
  document.addEventListener('bv-lang', function () { paintHeader(); renderPage(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
