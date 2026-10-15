(function () {
  'use strict';

  var DAYS_SHOWN = 14;
  var PERIODS = {
    all: [0, 24],
    morning: [0, 12],
    afternoon: [12, 17],
    evening: [17, 24],
  };

  var state = { day: isoDate(new Date()), period: loadPeriod(), data: null };
  var daysEl = document.getElementById('days');
  var slotsEl = document.getElementById('slots');

  function isoDate(d) {
    var local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
  }

  function loadPeriod() {
    try {
      var saved = localStorage.getItem('period');
      if (saved && PERIODS[saved]) return saved;
    } catch (e) {}
    return 'all';
  }

  function renderDays() {
    var fmtDow = new Intl.DateTimeFormat('fr-FR', { weekday: 'short' });
    var html = '';
    for (var i = 0; i < DAYS_SHOWN; i++) {
      var d = new Date();
      d.setDate(d.getDate() + i);
      var iso = isoDate(d);
      var label = i === 0 ? 'auj.' : fmtDow.format(d).replace('.', '');
      html += '<button type="button" data-day="' + iso + '"' + (iso === state.day ? ' class="active"' : '') + '>' +
        '<span class="dow">' + label + '</span><span class="num">' + d.getDate() + '</span></button>';
    }
    daysEl.innerHTML = html;
  }

  function renderSlots() {
    if (!state.data) return;
    var range = PERIODS[state.period];
    var byHour = {};
    state.data.courts.forEach(function (court) {
      court.slots.forEach(function (slot) {
        var hour = parseInt(slot.time, 10);
        if (hour < range[0] || hour >= range[1]) return;
        (byHour[slot.time] = byHour[slot.time] || []).push({ name: court.name, url: slot.booking_url });
      });
    });

    var times = Object.keys(byHour).sort();
    if (!times.length) {
      slotsEl.innerHTML = '<p class="message">Aucun créneau libre sur cette période.</p>';
      return;
    }
    slotsEl.innerHTML = times.map(function (t) {
      var courts = byHour[t];
      return '<section class="hour"><div class="hour-head"><span class="hour-time">' + t + '</span>' +
        '<span class="hour-count">' + courts.length + (courts.length > 1 ? ' terrains libres' : ' terrain libre') + '</span></div>' +
        '<div class="courts">' + courts.map(function (c) {
          return '<a href="' + c.url + '" target="_blank" rel="noopener">' + c.name + '</a>';
        }).join('') + '</div></section>';
    }).join('');
  }

  function load() {
    var day = state.day;
    state.data = null;
    slotsEl.innerHTML = '<p class="message">Chargement…</p>';
    fetch('/api/availability?date=' + day)
      .then(function (res) {
        if (!res.ok) throw new Error(res.status);
        return res.json();
      })
      .then(function (data) {
        if (day !== state.day) return; // a newer day was picked meanwhile
        state.data = data;
        renderSlots();
      })
      .catch(function () {
        if (day !== state.day) return;
        slotsEl.innerHTML = '<p class="message">Impossible de joindre le site du club. Réessayez.</p>';
      });
  }

  daysEl.addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-day]');
    if (!btn || btn.dataset.day === state.day) return;
    state.day = btn.dataset.day;
    renderDays();
    load();
  });

  document.getElementById('periods').addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-period]');
    if (!btn) return;
    state.period = btn.dataset.period;
    try { localStorage.setItem('period', state.period); } catch (err) {}
    this.querySelectorAll('button').forEach(function (b) {
      b.classList.toggle('active', b === btn);
    });
    renderSlots();
  });

  document.getElementById('refresh').addEventListener('click', load);

  document.querySelectorAll('#periods button').forEach(function (b) {
    b.classList.toggle('active', b.dataset.period === state.period);
  });
  renderDays();
  load();
})();
