(function () {
  'use strict';

  var PERIODS = {
    all: [0, 24],
    morning: [0, 12],
    afternoon: [12, 17],
    evening: [17, 24],
  };

  var GAME_HOURS = 2; // a game is 2 hours in a row on the same court
  var STATS_URL = '/api/events';

  var state = { day: null, period: loadSaved('period', PERIODS, 'all'), data: null };
  var daysEl = document.getElementById('days');
  var slotsEl = document.getElementById('slots');
  var updatedEl = document.getElementById('updated');

  function isoDate(d) {
    var local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
  }

  function loadSaved(key, allowed, fallback) {
    try {
      var saved = localStorage.getItem(key);
      if (saved && allowed[saved]) return saved;
    } catch (e) {}
    return fallback;
  }

  // Anonymous usage stats: a random id per phone, no cookies, nothing from local testing
  function visitorId() {
    try {
      var id = localStorage.getItem('visitor');
      if (!id) {
        id = Math.random().toString(36).slice(2) + Date.now().toString(36);
        localStorage.setItem('visitor', id);
      }
      return id;
    } catch (e) {
      return 'anonymous';
    }
  }

  function track(type, props) {
    if (location.hostname === 'localhost' || !navigator.sendBeacon) return;
    var body = JSON.stringify({ type: type, visitor: visitorId(), props: props || {} });
    // text/plain keeps it a simple request (no CORS preflight)
    navigator.sendBeacon(STATS_URL, new Blob([body], { type: 'text/plain' }));
  }

  function weekdayOf(iso) {
    return new Intl.DateTimeFormat('fr-FR', { weekday: 'long' }).format(new Date(iso + 'T12:00:00'));
  }

  function hhmm(hour) {
    return (hour < 10 ? '0' : '') + hour + '00';
  }

  function bookingUrl(court, day, hhmm) {
    return state.data.booking_base_url + court.product_slug + '/?date=' + day + '&time=' + hhmm;
  }

  function renderDays() {
    var fmtDow = new Intl.DateTimeFormat('fr-FR', { weekday: 'short' });
    var today = isoDate(new Date());
    daysEl.innerHTML = Object.keys(state.data.days).filter(function (iso) {
      return iso >= today;
    }).map(function (iso) {
      var d = new Date(iso + 'T12:00:00');
      var label = iso === today ? 'auj.' : fmtDow.format(d).replace('.', '');
      return '<button type="button" data-day="' + iso + '"' + (iso === state.day ? ' class="active"' : '') + '>' +
        '<span class="dow">' + label + '</span><span class="num">' + d.getDate() + '</span></button>';
    }).join('');
  }

  function renderSlots() {
    var range = PERIODS[state.period];
    var dayData = state.data.days[state.day] || {};
    var now = new Date();
    var isToday = state.day === isoDate(now);
    var byHour = {};

    state.data.courts.forEach(function (court) {
      var free = dayData[court.id] || [];
      free.forEach(function (slot) {
        var hour = parseInt(slot.slice(0, 2), 10);
        if (hour < range[0] || hour >= range[1]) return;
        if (isToday && hour <= now.getHours()) return; // already started
        // Every following hour must be free on the same court too
        for (var i = 1; i < GAME_HOURS; i++) {
          if (free.indexOf(hhmm(hour + i)) === -1) return;
        }
        (byHour[hour] = byHour[hour] || []).push({ name: court.name, url: bookingUrl(court, state.day, slot) });
      });
    });

    var times = Object.keys(byHour).map(Number).sort(function (x, y) { return x - y; });
    if (!times.length) {
      slotsEl.innerHTML = '<p class="message">Aucun créneau de 2 h libre sur cette période.</p>';
      return;
    }
    slotsEl.innerHTML = times.map(function (t) {
      var courts = byHour[t];
      var label = t + 'h – ' + (t + GAME_HOURS) + 'h';
      return '<section class="hour"><div class="hour-head"><span class="hour-time">' + label + '</span>' +
        '<span class="hour-count">' + courts.length + (courts.length > 1 ? ' terrains libres' : ' terrain libre') + '</span></div>' +
        '<div class="courts">' + courts.map(function (c) {
          return '<a href="' + c.url + '" target="_blank" rel="noopener" data-slot="' + label + '" data-court="' + c.name + '">' + c.name + '</a>';
        }).join('') + '</div></section>';
    }).join('');
  }

  function renderUpdated() {
    var minutes = Math.round((Date.now() - new Date(state.data.generated_at).getTime()) / 60000);
    updatedEl.textContent = minutes < 1 ? 'Mis à jour à l’instant' :
      minutes < 60 ? 'Mis à jour il y a ' + minutes + ' min' :
      'Mis à jour il y a ' + Math.floor(minutes / 60) + ' h';
  }

  function render() {
    var days = Object.keys(state.data.days);
    var today = isoDate(new Date());
    if (!state.day || !state.data.days[state.day]) {
      state.day = days.filter(function (d) { return d >= today; })[0] || days[0];
    }
    renderDays();
    renderSlots();
    renderUpdated();
  }

  function load() {
    slotsEl.innerHTML = '<p class="message">Chargement…</p>';
    // Bypass the browser cache: the file is rebuilt every few minutes
    fetch('data.json?t=' + Date.now())
      .then(function (res) {
        if (!res.ok) throw new Error(res.status);
        return res.json();
      })
      .then(function (data) {
        state.data = data;
        render();
      })
      .catch(function () {
        slotsEl.innerHTML = '<p class="message">Impossible de charger les créneaux. Réessayez.</p>';
      });
  }

  daysEl.addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-day]');
    if (!btn || btn.dataset.day === state.day) return;
    state.day = btn.dataset.day;
    track('day', { weekday: weekdayOf(state.day) });
    renderDays();
    renderSlots();
  });

  document.getElementById('periods').addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-period]');
    if (!btn) return;
    state.period = btn.dataset.period;
    try { localStorage.setItem('period', state.period); } catch (err) {}
    track('period', { period: state.period });
    this.querySelectorAll('button').forEach(function (b) {
      b.classList.toggle('active', b === btn);
    });
    if (state.data) renderSlots();
  });

  slotsEl.addEventListener('click', function (e) {
    var link = e.target.closest('a[data-slot]');
    if (link) track('slot_click', { slot: link.dataset.slot, court: link.dataset.court, weekday: weekdayOf(state.day) });
  });

  document.getElementById('refresh').addEventListener('click', load);

  document.querySelectorAll('#periods button').forEach(function (b) {
    b.classList.toggle('active', b.dataset.period === state.period);
  });
  track('view');
  load();
})();
