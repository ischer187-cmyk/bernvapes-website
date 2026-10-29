/* Händlerportal. Spricht mit dem lokalen CRM über /b2b-api (Proxy des Dev-Servers). */
(function () {
  var API = window.BV_B2B_API || '/b2b-api';
  var root = document.getElementById('app');
  var state = { me: null, csrf: null, catalog: null, cart: {}, notice: '', error: '', totpSecret: '', otpauth: '' };
  var params = new URLSearchParams(location.search);

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }
  function money(n) { return 'CHF ' + Number(n).toFixed(2); }

  function api(path, opts) {
    opts = opts || {};
    var headers = { 'Accept': 'application/json' };
    if (opts.body) headers['Content-Type'] = 'application/json';
    if (state.csrf && opts.method && opts.method !== 'GET') headers['X-CSRF-Token'] = state.csrf;
    return fetch(API + path, {
      method: opts.method || 'GET',
      headers: headers,
      credentials: 'same-origin',
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (data && data.csrf_token) state.csrf = data.csrf_token;
        return { status: res.status, data: data };
      });
    }).catch(function () {
      return { status: 0, data: { error: 'crm_unreachable' } };
    });
  }

  function field(name, label, type, value, extra) {
    return '<div class="fld"><label for="' + name + '">' + esc(label) + '</label><input id="' + name + '" name="' + name + '" type="' + (type || 'text') + '" value="' + esc(value || '') + '" ' + (extra || '') + '></div>';
  }
  function showError(msg) {
    state.error = msg;
    var box = root.querySelector('.err');
    if (!box) {
      box = document.createElement('div');
      box.className = 'err';
      root.insertBefore(box, root.firstChild);
    }
    box.textContent = msg;
  }

  function shell(inner) {
    var msg = '';
    if (state.error) msg += '<div class="err">' + esc(state.error) + '</div>';
    if (state.notice) msg += '<div class="ok">' + esc(state.notice) + '</div>';
    root.innerHTML = msg + inner;
  }

  function authTabs(which) {
    return '<div class="tabs"><button type="button" class="btn' + (which === 'login' ? '' : ' ghost') + '" data-go="login">Anmelden</button>'
      + '<button type="button" class="btn' + (which === 'register' ? '' : ' ghost') + '" data-go="register">Registrieren</button></div>';
  }

  function renderLogin() {
    shell(authTabs('login') + '<form id="f">'
      + field('email', 'E-Mail', 'email', '', 'required autocomplete="username"')
      + field('password', 'Passwort', 'password', '', 'required autocomplete="current-password"')
      + field('totp', 'Authenticator-Code (falls schon aktiv)', 'text', '', 'inputmode="numeric" autocomplete="one-time-code"')
      + '<p style="margin-top:16px"><button class="btn" type="submit">Anmelden</button></p></form>'
      + '<p class="muted">Eingeladene Shops öffnen den einmaligen Link aus der Steuerzentrale. Selbstregistrierung bleibt pending, bis Bernvapes freigibt.</p>');
    root.querySelector('#f').onsubmit = function (ev) {
      ev.preventDefault();
      var fd = new FormData(ev.target);
      api('/login', { method: 'POST', body: { email: fd.get('email'), password: fd.get('password'), totp: fd.get('totp') } }).then(afterAuth);
    };
  }

  function renderRegister() {
    shell(authTabs('register') + '<form id="f"><div class="row2">'
      + field('company_name', 'Firma', 'text', '', 'required')
      + field('uid', 'UID (CHE-123.456.789)', 'text', '', 'required placeholder="CHE-123.456.789"')
      + field('email', 'E-Mail', 'email', '', 'required')
      + field('contact_person', 'Ansprechperson', 'text', '')
      + field('city', 'Ort', 'text', '')
      + field('language', 'Sprache', 'text', 'de', 'placeholder="de / fr / it / en"')
      + '</div>' + field('password', 'Passwort (mind. 10 Zeichen)', 'password', '', 'required minlength="10" autocomplete="new-password"')
      + '<p style="margin-top:16px"><button class="btn" type="submit">Konto anlegen</button></p></form>'
      + '<p class="muted">Das Konto bleibt gesperrt, bis es in der Steuerzentrale freigegeben ist. Format der UID wird geprüft, keine Ausweisdaten.</p>');
    root.querySelector('#f').onsubmit = function (ev) {
      ev.preventDefault();
      var fd = new FormData(ev.target);
      var body = {};
      fd.forEach(function (v, k) { body[k] = v; });
      api('/register', { method: 'POST', body: body }).then(afterAuth);
    };
  }

  function renderInvite() {
    shell('<h2>Einladung annehmen</h2><p class="muted">Einmaliger Link. Danach Passwort und Zwei-Faktor.</p><form id="f">'
      + field('password', 'Passwort (mind. 10 Zeichen)', 'password', '', 'required minlength="10" autocomplete="new-password"')
      + '<p style="margin-top:16px"><button class="btn" type="submit">Weiter</button></p></form>');
    root.querySelector('#f').onsubmit = function (ev) {
      ev.preventDefault();
      api('/invite/accept', { method: 'POST', body: { token: params.get('token'), password: new FormData(ev.target).get('password') } }).then(afterAuth);
    };
  }

  function renderTotp() {
    shell('<h2>Zwei-Faktor</h2><p class="muted">In der Authenticator-App ein Konto anlegen. Schlüssel von Hand eintragen oder den Link öffnen. Danach den 6-stelligen Code.</p>'
      + '<p><b>Schlüssel</b><br><code>' + esc(state.totpSecret) + '</code></p>'
      + (state.otpauth ? '<p><a href="' + esc(state.otpauth) + '">otpauth-Link</a></p>' : '')
      + '<form id="f">' + field('code', 'Code', 'text', '', 'required inputmode="numeric" autocomplete="one-time-code"')
      + '<p style="margin-top:16px"><button class="btn" type="submit">Bestätigen</button></p></form>');
    root.querySelector('#f').onsubmit = function (ev) {
      ev.preventDefault();
      api('/totp/confirm', { method: 'POST', body: { code: new FormData(ev.target).get('code') } }).then(afterAuth);
    };
  }

  function renderPending() {
    shell('<h2>' + esc(state.me.company_name || 'Konto') + '</h2><p>Die Firma ist erfasst'
      + (state.me.uid ? ' (' + esc(state.me.uid) + ')' : '')
      + '. Bernvapes gibt das Konto frei, danach erscheinen die Preise. Bis dahin keine Bestellung.</p>'
      + '<p class="muted">Status: ' + esc(state.me.status) + '. Firmenprüfung statt Altersprüfung pro Person.</p>'
      + '<p><button class="btn ghost" type="button" id="out">Abmelden</button></p>');
    root.querySelector('#out').onclick = logout;
  }

  function renderCatalog() {
    var rows = (state.catalog.products || []).map(function (p) {
      var qty = state.cart[p.sku] || 0;
      var price = state.catalog.prices_visible ? money(p.unit_chf) + (p.override ? ' · Sonderpreis' : '') : '—';
      return '<tr><td>' + esc(p.name) + '<br><span class="muted">' + esc(p.bottle_ml) + ' ml' + (p.sample_price ? ' · Beispielpreis' : '') + '</span></td>'
        + '<td class="num">' + esc(price) + '</td>'
        + '<td class="num"><input class="qty" data-sku="' + esc(p.sku) + '" type="number" min="0" max="999" value="' + qty + '"></td></tr>';
    }).join('');
    var total = 0;
    (state.catalog.products || []).forEach(function (p) {
      if (state.catalog.prices_visible) total += (state.cart[p.sku] || 0) * p.unit_chf;
    });
    shell('<h2>' + esc(state.me.company_name || '') + '</h2><p class="muted">Stufe ' + esc(state.catalog.tier_label || '')
      + '. Zahlungsart Rechnung. Die Firma ist geprüft, eine Altersprüfung pro Person entfällt. '
      + ((state.catalog.products || []).some(function (p) { return p.sample_price; }) ? 'Einige Preise sind noch Beispielpreise aus dem lokalen Test.' : '')
      + '</p><table><tr><th>Sorte</th><th class="num">Preis</th><th class="num">Menge</th></tr>' + rows + '</table>'
      + '<div class="tot"><div><b>' + (state.catalog.prices_visible ? money(total) : '') + '</b><br><span class="muted">Rechnung</span></div>'
      + '<div><button class="btn" type="button" id="buy">Auf Rechnung bestellen</button> <button class="btn ghost" type="button" id="out">Abmelden</button></div></div>');
    root.querySelectorAll('.qty').forEach(function (input) {
      input.onchange = function () {
        var n = parseInt(input.value, 10) || 0;
        if (n > 0) state.cart[input.dataset.sku] = n; else delete state.cart[input.dataset.sku];
        renderCatalog();
      };
    });
    root.querySelector('#out').onclick = logout;
    root.querySelector('#buy').onclick = function () {
      var items = Object.keys(state.cart).map(function (sku) { return { sku: sku, qty: state.cart[sku] }; });
      if (!items.length) { state.error = 'Keine Menge gewählt.'; renderCatalog(); return; }
      api('/orders', { method: 'POST', body: { items: items } }).then(function (r) {
        if (r.status === 202) {
          state.cart = {};
          state.notice = 'Bestellung #' + r.data.order_id + ' ist auf Rechnung erfasst.';
          state.error = '';
          loadCatalog();
        } else {
          state.error = (r.data && (r.data.error || r.data.detail)) || 'Bestellung abgelehnt';
          renderCatalog();
        }
      });
    };
  }

  function logout() {
    api('/logout', { method: 'POST', body: {} }).then(function () {
      state.me = null; state.csrf = null; state.catalog = null; state.notice = '';
      params.delete('token');
      history.replaceState(null, '', 'haendler.html');
      renderLogin();
    });
  }

  function afterAuth(r) {
    state.error = '';
    if (r.status === 0) { state.error = 'CRM nicht erreichbar. Läuft die Steuerzentrale auf 127.0.0.1:18734?'; return renderLogin(); }
    if (r.status === 429) { state.error = 'Zu viele Versuche. Kurz warten.'; return params.get('token') ? renderInvite() : renderLogin(); }
    if (r.status === 422 && r.data.error === 'invalid_uid') {
      showError('UID muss so aussehen: CHE-123.456.789');
      if (!root.querySelector('#uid')) renderRegister();
      return;
    }
    if (r.status === 409) {
      showError('Diese E-Mail gibt es schon.');
      if (!root.querySelector('#email')) renderRegister();
      return;
    }
    if (r.status === 401 || r.status === 422) {
      state.error = r.data.error === 'invite_invalid' ? 'Einladung ungültig oder abgelaufen.' : 'Anmeldung fehlgeschlagen.';
      return params.get('token') && !state.me ? renderInvite() : renderLogin();
    }
    if (!r.data || !r.data.ok) { state.error = (r.data && r.data.error) || 'Fehler'; return renderLogin(); }
    if (r.data.scope === 'totp_setup') {
      state.totpSecret = r.data.totp_secret || state.totpSecret;
      state.otpauth = r.data.otpauth_uri || '';
      state.me = r.data;
      params.delete('token');
      return renderTotp();
    }
    state.me = r.data;
    state.totpSecret = '';
    boot();
  }

  function loadCatalog() {
    return api('/catalog').then(function (r) {
      if (r.status === 401) { state.me = null; return renderLogin(); }
      state.catalog = r.data;
      if (!r.data.prices_visible) return renderPending();
      renderCatalog();
    });
  }

  function boot() {
    api('/me').then(function (r) {
      if (r.status === 0) { state.error = 'CRM nicht erreichbar. Zuerst die Steuerzentrale starten (127.0.0.1:18734), dann diese Seite über den lokalen Webserver öffnen.'; return renderLogin(); }
      if (r.status !== 200) {
        if (params.get('token')) return renderInvite();
        return renderLogin();
      }
      state.me = r.data;
      if (r.data.scope === 'totp_setup') return renderTotp();
      if (r.data.status !== 'approved' || !r.data.company_verified) return renderPending();
      loadCatalog();
    });
  }

  root.addEventListener('click', function (ev) {
    var go = ev.target && ev.target.getAttribute && ev.target.getAttribute('data-go');
    if (go === 'login') { state.error = ''; renderLogin(); }
    if (go === 'register') { state.error = ''; renderRegister(); }
  });

  boot();
})();
