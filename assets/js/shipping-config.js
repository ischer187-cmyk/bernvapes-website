/* Zentrale Versand-Konfiguration für Shop und Kasse.
   crm/shipping.py liest genau diese Datei. Nicht ein zweites Mal pflegen. */
window.BV_SHIPPING = {
  SHIPPING_FEE_CHF: 9.00,
  FREE_SHIPPING_THRESHOLD_CHF: 50.00,
  VAT_RATE: 8.1
};

window.BV_SHIPPING.money = function (n) {
  var v = Number(n);
  if (!isFinite(v)) return '';
  var neg = v < 0;
  var parts = Math.abs(v).toFixed(2).split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, "'");
  return (neg ? '-' : '') + 'CHF ' + parts[0] + '.' + parts[1];
};

window.BV_SHIPPING.feeFor = function (subtotal) {
  var cfg = window.BV_SHIPPING;
  var sub = Math.round(Number(subtotal) * 100) / 100;
  if (!isFinite(sub)) sub = 0;
  var free = sub + 1e-9 >= Number(cfg.FREE_SHIPPING_THRESHOLD_CHF);
  var shipping = free ? 0 : Number(cfg.SHIPPING_FEE_CHF);
  var total = Math.round((sub + shipping) * 100) / 100;
  var remaining = free ? 0 : Math.round((Number(cfg.FREE_SHIPPING_THRESHOLD_CHF) - sub) * 100) / 100;
  return { subtotal: sub, shipping: shipping, total: total, free: free, remaining: remaining };
};

window.BV_SHIPPING.hint = function (free, remaining) {
  if (free) {
    var t = (window.bvI18n && window.bvI18n.t) ? window.bvI18n.t : function (s) { return s; };
    return t('Du hast Gratisversand');
  }
  var amount = window.BV_SHIPPING.money(remaining);
  var lang = (window.bvI18n && window.bvI18n.lang) || 'be';
  if (lang === 'en') return amount + ' until free shipping';
  if (lang === 'fr') return 'Encore ' + amount + ' avant la livraison gratuite';
  return 'Noch ' + amount + ' bis zum Gratisversand';
};
