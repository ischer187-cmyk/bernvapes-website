/* Kunden-Login, vorerst nur Platzhalter.
   Kein Passwort in localStorage, kein Fetch, kein Versand.

   Später an das Händlerportal / CRM aus bony/b2b-portal (PR #3) hängen,
   ohne dieses Formular umzubauen:

     window.BV_AUTH = {
       mode: 'b2b',
       api: '/b2b-api',
       // Retail-Session, sobald das CRM eine hat. Nicht /login der Händler:
       // POST /b2b-api/login ist {email, password, totp} für dealer_accounts.
       customerLogin: '/customer/login'
     };

   Händler bleiben auf haendler.html. Dort spricht assets/js/b2b.js mit
   POST /b2b-api/login (crm/portal.py). Im Platzhalter führt der Hinweis
   nicht weg und schickt nichts. Mit mode 'b2b' öffnet der Link haendler.html.
*/
(function () {
  var AUTH = window.BV_AUTH || (window.BV_AUTH = {
    mode: 'placeholder',
    api: '/b2b-api',
    customerLogin: '/customer/login',
    dealerPage: 'haendler.html'
  });

  var link, scrim, card, noticeEl, panels;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }
  function field(id, label, type, auto, name) {
    var wrap = el('div', 'fld');
    var lab = el('label', '', label);
    lab.htmlFor = id;
    var input = document.createElement('input');
    input.id = id;
    input.name = name || id;
    input.type = type;
    input.required = true;
    input.autocomplete = auto;
    if (type === 'email') input.inputMode = 'email';
    wrap.appendChild(lab);
    wrap.appendChild(input);
    return wrap;
  }
  function showPanel(name) {
    Object.keys(panels).forEach(function (k) { panels[k].hidden = k !== name; });
    if (noticeEl) noticeEl.hidden = true;
    var form = panels[name].querySelector('form');
    if (form) form.querySelectorAll('input[type="password"]').forEach(function (i) { i.value = ''; });
    var focus = panels[name].querySelector('input, button');
    if (focus) focus.focus();
  }
  function showNotice(be) {
    noticeEl.hidden = false;
    noticeEl.textContent = be;
  }
  /* Absenden gegen das CRM. Wird im Platzhalter nicht aufgerufen. */
  function postCustomer(email, password) {
    var root = String(AUTH.api || '/b2b-api').replace(/\/$/, '');
    var path = AUTH.customerLogin || '/customer/login';
    return fetch(root + path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, password: password })
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        return { status: res.status, data: data };
      });
    });
  }
  function finishPlaceholder(input, message) {
    if (input) input.value = '';
    showNotice(message);
  }
  function onLogin(ev) {
    ev.preventDefault();
    var form = ev.target;
    if (!form.reportValidity()) return;
    var email = form.email.value.trim();
    var password = form.password.value;
    form.password.value = '';
    if (AUTH.mode === 'b2b' && AUTH.customerLogin) {
      postCustomer(email, password).then(function (res) {
        password = '';
        if (res && res.data && res.data.ok) close();
        else showNotice('D Aamäldig isch no nid aktiv. Mir speichere kes Passwort u schicke nüt ewäg.');
      }).catch(function () {
        password = '';
        showNotice('D Aamäldig isch no nid aktiv. Mir speichere kes Passwort u schicke nüt ewäg.');
      });
      return;
    }
    password = '';
    finishPlaceholder(null, 'D Aamäldig isch no nid aktiv. Mir speichere kes Passwort u schicke nüt ewäg.');
  }
  function onForgot(ev) {
    ev.preventDefault();
    var form = ev.target;
    if (!form.reportValidity()) return;
    form.email.value = form.email.value;
    finishPlaceholder(null, 'Mir schicke no kei Mail. S Zruggsetze chunnt spöter.');
  }
  function onRegister(ev) {
    ev.preventDefault();
    var form = ev.target;
    if (!form.reportValidity()) return;
    var pw = form.querySelector('input[type="password"]');
    if (pw) pw.value = '';
    finishPlaceholder(null, 'Registriere chunnt spöter. Es wird no kes Konto aagleit.');
  }

  function buildDialog() {
    scrim = el('div', 'loginscrim');
    scrim.hidden = true;
    scrim.addEventListener('click', function (ev) { if (ev.target === scrim) close(); });
    card = el('div', 'logincard');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');
    card.setAttribute('aria-labelledby', 'login-title');
    var head = el('div', 'loginhead');
    var h = el('h2', '', 'Aamälde');
    h.id = 'login-title';
    var x = el('button', 'loginx', '✕');
    x.type = 'button';
    x.setAttribute('aria-label', 'Schliesse');
    x.addEventListener('click', close);
    head.appendChild(h);
    head.appendChild(x);
    card.appendChild(head);

    noticeEl = el('p', 'loginnotice');
    noticeEl.setAttribute('role', 'status');
    noticeEl.hidden = true;
    card.appendChild(noticeEl);

    var login = el('div', 'loginpanel');
    var f1 = document.createElement('form');
    f1.noValidate = false;
    f1.setAttribute('method', 'post');
    f1.setAttribute('action', '#login');
    f1.appendChild(field('login-email', 'E-Mail', 'email', 'username', 'email'));
    f1.appendChild(field('login-password', 'Passwort', 'password', 'current-password', 'password'));
    var go = el('button', 'btn', 'Aamälde');
    go.type = 'submit';
    var row = el('p', 'loginrow');
    row.appendChild(go);
    f1.appendChild(row);
    f1.addEventListener('submit', onLogin);
    login.appendChild(f1);
    var links = el('p', 'loginlinks');
    var forgot = el('button', 'loginlink', 'Passwort vergässe?');
    forgot.type = 'button';
    forgot.addEventListener('click', function () { showPanel('forgot'); });
    var reg = el('button', 'loginlink', 'Noch kes Konto? Registriere');
    reg.type = 'button';
    reg.addEventListener('click', function () { showPanel('register'); });
    links.appendChild(forgot);
    links.appendChild(reg);
    login.appendChild(links);
    var hint = el('p', 'loginhint', 'Händler mälde sech spöter im Portal a.');
    var dealer = document.createElement('a');
    dealer.href = AUTH.dealerPage || 'haendler.html';
    dealer.className = 'loginlink';
    dealer.textContent = 'Zum Händlerportal';
    dealer.addEventListener('click', function (ev) {
      if (AUTH.mode === 'b2b') return;
      ev.preventDefault();
      showNotice('Ds Händlerportal isch no nid verbunde.');
    });
    hint.appendChild(document.createTextNode(' '));
    hint.appendChild(dealer);
    login.appendChild(hint);

    var forgotP = el('div', 'loginpanel');
    var f2 = document.createElement('form');
    f2.setAttribute('method', 'post');
    f2.setAttribute('action', '#login');
    f2.appendChild(field('forgot-email', 'E-Mail', 'email', 'username', 'email'));
    var send = el('button', 'btn', 'Passwort zruggsetze');
    send.type = 'submit';
    var row2 = el('p', 'loginrow');
    row2.appendChild(send);
    f2.appendChild(row2);
    f2.addEventListener('submit', onForgot);
    forgotP.appendChild(f2);
    var back1 = el('button', 'loginlink', 'Zrügg zum Login');
    back1.type = 'button';
    back1.addEventListener('click', function () { showPanel('login'); });
    var p1 = el('p', 'loginlinks');
    p1.appendChild(back1);
    forgotP.appendChild(p1);

    var regP = el('div', 'loginpanel');
    var f3 = document.createElement('form');
    f3.setAttribute('method', 'post');
    f3.setAttribute('action', '#login');
    var name = field('reg-name', 'Name', 'text', 'name', 'name');
    name.querySelector('input').required = false;
    f3.appendChild(name);
    f3.appendChild(field('reg-email', 'E-Mail', 'email', 'email', 'email'));
    f3.appendChild(field('reg-password', 'Passwort', 'password', 'new-password', 'password'));
    var create = el('button', 'btn', 'Konto alege');
    create.type = 'submit';
    var row3 = el('p', 'loginrow');
    row3.appendChild(create);
    f3.appendChild(row3);
    f3.addEventListener('submit', onRegister);
    regP.appendChild(f3);
    var back2 = el('button', 'loginlink', 'Zrügg zum Login');
    back2.type = 'button';
    back2.addEventListener('click', function () { showPanel('login'); });
    var p2 = el('p', 'loginlinks');
    p2.appendChild(back2);
    regP.appendChild(p2);

    card.appendChild(login);
    card.appendChild(forgotP);
    card.appendChild(regP);
    scrim.appendChild(card);
    document.body.appendChild(scrim);
    panels = { login: login, forgot: forgotP, register: regP };
    forgotP.hidden = true;
    regP.hidden = true;
  }

  function open() {
    if (!scrim) return;
    scrim.hidden = false;
    link.setAttribute('aria-expanded', 'true');
    showPanel('login');
    var email = document.getElementById('login-email');
    if (email) email.focus();
  }
  function close() {
    if (!scrim || scrim.hidden) return;
    scrim.hidden = true;
    link.setAttribute('aria-expanded', 'false');
    card.querySelectorAll('input[type="password"]').forEach(function (i) { i.value = ''; });
    if (link) link.focus();
  }

  function mount() {
    var sw = document.querySelector('.langsw');
    if (!sw) return false;
    link = document.createElement('a');
    link.href = '#login';
    link.className = 'navlogin';
    link.setAttribute('aria-haspopup', 'dialog');
    link.setAttribute('aria-expanded', 'false');
    link.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5.5 19.2c1.4-3 3.6-4.4 6.5-4.4s5.1 1.4 6.5 4.4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg><span>Login</span>';
    link.addEventListener('click', function (ev) {
      ev.preventDefault();
      if (scrim && !scrim.hidden) close();
      else open();
    });
    var cluster = sw.closest('.navcluster');
    if (!cluster) {
      cluster = document.createElement('div');
      cluster.className = 'navcluster';
      if (sw.classList.contains('fixed')) {
        cluster.classList.add('fixed');
        sw.classList.remove('fixed');
      }
      sw.parentElement.insertBefore(cluster, sw);
      cluster.appendChild(sw);
    }
    var cart = document.querySelector('.navcart');
    if (cart && cart.parentElement !== cluster) {
      cart.classList.remove('fixed');
      cluster.insertBefore(cart, cluster.firstChild);
    }
    cluster.insertBefore(link, cluster.firstChild);
    buildDialog();
    addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && scrim && !scrim.hidden) close();
    });
    if (location.hash === '#login') open();
    return true;
  }

  function boot() {
    if (mount()) return;
    setTimeout(function () { mount(); }, 0);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
