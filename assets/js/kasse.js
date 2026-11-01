/* Zur Kasse: Vorschau, dann Redirect auf die PostFinance Payment Page. */
(function () {
  var API = '/b2b-api/customer';

  function t(s) { return (window.bvI18n && window.bvI18n.t) ? window.bvI18n.t(s) : s; }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }
  function cart() {
    try {
      var v = JSON.parse(localStorage.getItem('bv-cart'));
      return Array.isArray(v) ? v : [];
    } catch (e) { return []; }
  }
  function refOk(ref) { return /^bv-\d{1,18}$/.test(ref || ''); }
  function money(n) {
    if (window.BV_SHIPPING && window.BV_SHIPPING.money) return window.BV_SHIPPING.money(n);
    var v = Number(n);
    if (!isFinite(v)) return '';
    return 'CHF ' + v.toFixed(2);
  }
  function errText(code) {
    var map = {
      login_required: 'Bitte zuerst anmelden.',
      empty_cart: 'Der Warenkorb ist leer.',
      unknown_item: 'Eine Position ist unbekannt.',
      invalid_qty: 'Die Menge stimmt nicht.',
      postfinance_not_configured: 'PostFinance ist noch nicht konfiguriert.',
      postfinance_failed: 'PostFinance hat die Zahlung nicht gestartet.',
      underage: 'Du musst mindestens 18 Jahre alt sein.',
      birthdate_invalid: 'Bitte Geburtsdatum als TT.MM.JJJJ angeben.',
      age_confirm_required: 'Bitte bestätige, dass du 18 Jahre oder älter bist.',
      csrf: 'Seite neu laden und noch einmal versuchen.',
      crm_unreachable: 'CRM nicht erreichbar.'
    };
    return t(map[code] || 'Das hat nicht geklappt.');
  }
  function api(path, opts) {
    opts = opts || {};
    var headers = { 'Accept': 'application/json' };
    if (opts.body) headers['Content-Type'] = 'application/json';
    if (opts.csrf && opts.method && opts.method !== 'GET') headers['X-CSRF-Token'] = opts.csrf;
    return fetch(API + path, {
      method: opts.method || 'GET',
      headers: headers,
      credentials: 'same-origin',
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        return { status: r.status, data: data };
      });
    }).catch(function () { return { status: 0, data: { error: 'crm_unreachable' } }; });
  }
  function itemsPayload() {
    return cart().map(function (it) {
      return { id: it.id, name: it.name, qty: it.qty || 1, preorder: !!it.preorder };
    });
  }
  var NOTICE_ALL = 'Vor dem Versand wird die Altersverifikation durchgeführt.';
  var NOTICE_NEW = 'Bei Neukunden melden wir uns persönlich, um die Altersverifizierung durchzuführen. Du schickst uns dazu ein Selfie mit deinem Ausweis.';
  function linesHtml(items) {
    return '<ul class="kasse-lines">' + items.map(function (it) {
      var mark = it.preorder ? ' <i class="premark">' + esc(t('Vorbestellung')) + '</i>' : '';
      return '<li><span>' + esc(it.name) + ' ×' + esc(it.qty) + mark + '</span><span>' + esc(money(it.line_chf)) + '</span></li>';
    }).join('') + '</ul>';
  }
  function hintText(data) {
    var free = !!(data && (data.free_shipping || Number(data.shipping_chf) <= 0));
    var rest = data && data.remaining_to_free_chf != null ? data.remaining_to_free_chf : 0;
    if (window.BV_SHIPPING && window.BV_SHIPPING.hint) return window.BV_SHIPPING.hint(free, rest);
    return free ? t('Du hast Gratisversand') : ('Noch ' + money(rest) + ' bis zum Gratisversand');
  }
  function noticesOf(data) {
    var list = (data && data.notices && data.notices.length) ? data.notices.slice() : [NOTICE_ALL];
    if (data && data.age_check_status === 'Altersprüfung offen' && list.indexOf(NOTICE_NEW) < 0) list.push(NOTICE_NEW);
    if (data && data.needs_age_check && list.indexOf(NOTICE_NEW) < 0) list.push(NOTICE_NEW);
    return list.map(function (n) { return '<p class="agenote">' + esc(t(n)) + '</p>'; }).join('');
  }
  function summaryHtml(data) {
    var ship = Number(data.shipping_chf) || 0;
    var sub = data.subtotal_chf != null ? data.subtotal_chf : data.total_chf;
    var thr = Number(data.free_shipping_threshold_chf) || (window.BV_SHIPPING && BV_SHIPPING.FREE_SHIPPING_THRESHOLD_CHF) || 50;
    var pct = Math.max(0, Math.min(100, (Number(sub) || 0) / thr * 100));
    return '<div class="kasse-sum">'
      + '<p><span>' + esc(t('Zwischensumme')) + '</span><span>' + esc(money(sub)) + '</span></p>'
      + '<p><span>' + esc(t('Versand')) + '</span><span>' + esc(ship <= 0 ? t('Gratis') : money(ship)) + '</span></p>'
      + '<p class="kasse-total"><b>' + esc(t('Total')) + '</b> <b>' + esc(money(data.total_chf)) + '</b></p>'
      + '</div>'
      + '<p class="shiphint" aria-live="polite">' + esc(hintText(data)) + '</p>'
      + '<div class="shipbar" aria-hidden="true"><i style="width:' + pct.toFixed(1) + '%"></i></div>'
      + noticesOf(data);
  }
  function ageFields() {
    return '<label class="fld" for="birthdate">' + esc(t('Geburtsdatum')) + '</label>'
      + '<input id="birthdate" name="birthdate" inputmode="numeric" autocomplete="bday" placeholder="TT.MM.JJJJ" required>'
      + '<label class="agebox"><input id="age18" type="checkbox" required> <span>'
      + esc(t('Ich bestätige, dass ich 18 Jahre oder älter bin')) + '</span></label>';
  }

  function renderKasse(root, me) {
    var items = itemsPayload();
    if (!me) {
      root.innerHTML = '<p>' + esc(t('Bitte zuerst anmelden.')) + '</p><p><a class="btn" href="konto.html?next=kasse.html">' + esc(t('Anmelden')) + '</a></p>';
      return;
    }
    if (!items.length) {
      root.innerHTML = '<p>' + esc(t('Der Warenkorb ist leer.')) + '</p><p><a href="index.html">' + esc(t('Zurück zum Shop')) + '</a></p>';
      return;
    }
    root.innerHTML = '<p class="muted">…</p>';
    api('/checkout', { method: 'POST', csrf: me.csrf_token, body: { items: items, preview: true } }).then(function (r) {
      if (r.status === 401) return renderKasse(root, null);
      if (r.status !== 200 || !r.data.ok) {
        root.innerHTML = '<p class="err">' + esc(errText(r.data && r.data.error)) + '</p>';
        return;
      }
      root.innerHTML = linesHtml(r.data.items)
        + summaryHtml(r.data)
        + ageFields()
        + '<p class="muted">' + esc(t('Testzahlung über PostFinance.')) + '</p>'
        + '<p><button class="btn" type="button" id="pay">' + esc(t('Jetzt bezahlen')) + '</button></p>'
        + '<p id="kasse-err" class="err" hidden></p>';
      root.querySelector('#pay').onclick = function () {
        var btn = root.querySelector('#pay');
        var box = root.querySelector('#kasse-err');
        var birth = (root.querySelector('#birthdate').value || '').trim();
        var confirmed = !!root.querySelector('#age18').checked;
        box.hidden = true;
        if (!/^\d{2}\.\d{2}\.\d{4}$/.test(birth)) {
          box.hidden = false;
          box.textContent = t('Bitte Geburtsdatum als TT.MM.JJJJ angeben.');
          return;
        }
        if (!confirmed) {
          box.hidden = false;
          box.textContent = t('Bitte bestätige, dass du 18 Jahre oder älter bist.');
          return;
        }
        btn.disabled = true;
        api('/checkout', { method: 'POST', csrf: me.csrf_token, body: {
          items: itemsPayload(), preview: false, birthdate: birth, age_confirmed: true
        } }).then(function (pay) {
          btn.disabled = false;
          if (pay.status === 200 && pay.data.integrationMode === 'PaymentPage' && pay.data.paymentUrl) {
            location.href = pay.data.paymentUrl;
            return;
          }
          box.hidden = false;
          box.textContent = (pay.data && pay.data.message) || errText(pay.data && pay.data.error);
        });
      };
    });
  }

  function renderReturn(root, ok) {
    var ref = new URLSearchParams(location.search).get('ref') || '';
    if (!refOk(ref)) {
      root.innerHTML = '<p>' + esc(ok ? t('Zahlung wird bestätigt') : t('Die Zahlung ist nicht durchgegangen.')) + '</p><p><a href="index.html">' + esc(t('Zurück zum Shop')) + '</a></p>';
      return;
    }
    function paint(data) {
      var status = data && data.payment_status;
      var text = ok
        ? (status === 'bezahlt' || status === 'paid' ? 'Bezahlt. Die Bestellung ist deinem Konto zugeordnet.' : 'Warten auf die Bestätigung von PostFinance.')
        : 'Die Zahlung ist nicht durchgegangen.';
      var list = (data && data.items) ? data.items.map(function (it) {
        return '<li><span>' + esc(it.name) + (it.preorder ? ' · ' + esc(t('Vorbestellung')) : '') + ' ×' + esc(it.qty) + '</span></li>';
      }).join('') : '';
      var shipBit = '';
      if (data && data.shipping_chf != null) shipBit = ' · ' + (Number(data.shipping_chf) > 0 ? esc(t('Versand')) + ' ' + esc(money(data.shipping_chf)) : esc(t('Versand')) + ' ' + esc(t('Gratis')));
      root.innerHTML = '<p>' + esc(t(text)) + '</p>'
        + (list ? '<ul class="kasse-lines">' + list + '</ul>' : '')
        + '<p class="muted">' + esc(ref) + (data && data.total_chf != null ? ' · ' + esc(money(data.total_chf)) : '') + shipBit + '</p>'
        + noticesOf(data)
        + '<p><a href="konto.html">' + esc(t('Mein Konto')) + '</a> · <a href="kasse.html">' + esc(t('Zur Kasse')) + '</a> · <a href="index.html">' + esc(t('Zurück zum Shop')) + '</a></p>';
    }
    api('/me').then(function (me) {
      if (me.status !== 200) {
        root.innerHTML = '<p>' + esc(t(ok ? 'Zahlung wird bestätigt' : 'Die Zahlung ist nicht durchgegangen.')) + '</p><p><a class="btn" href="konto.html?next=' + (ok ? 'kasse-ok.html' : 'kasse-fail.html') + '">' + esc(t('Anmelden')) + '</a></p>';
        return;
      }
      var n = 0;
      function poll() {
        api('/order?ref=' + encodeURIComponent(ref)).then(function (r) {
          paint(r.status === 200 ? r.data : null);
          n += 1;
          if (ok && r.status === 200 && r.data.payment_status !== 'bezahlt' && r.data.payment_status !== 'paid' && n < 15) {
            setTimeout(poll, 2000);
          }
        });
      }
      poll();
    });
  }

  function boot() {
    var kasse = document.getElementById('kasse');
    var ok = document.getElementById('kasse-ok');
    var fail = document.getElementById('kasse-fail');
    if (!kasse && !ok && !fail) return;
    api('/me').then(function (r) {
      var me = (r.status === 200 && r.data && r.data.ok) ? r.data : null;
      if (kasse) renderKasse(kasse, me);
      if (ok) renderReturn(ok, true);
      if (fail) renderReturn(fail, false);
    });
  }
  document.addEventListener('bv-lang', boot);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
