document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-modal-open]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = btn.getAttribute('data-modal-open');
      var modal = document.getElementById(id);
      if (modal) modal.classList.add('open');
    });
  });
  document.querySelectorAll('[data-modal-close]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var modal = btn.closest('.modal-backdrop');
      if (modal) modal.classList.remove('open');
    });
  });
  document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
    backdrop.addEventListener('click', function (e) {
      if (e.target === backdrop) backdrop.classList.remove('open');
    });
  });

  document.querySelectorAll('.js-expand').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var wrap = btn.closest('.notif-body-wrap');
      var full = wrap.querySelector('.msg-full');
      var short = wrap.querySelector('.msg-short');
      if (full) full.classList.remove('hidden');
      if (short) short.classList.add('hidden');
      btn.classList.add('hidden');
      var hideBtn = wrap.querySelector('.msg-collapse');
      if (hideBtn) hideBtn.classList.remove('hidden');
    });
  });
  document.querySelectorAll('.msg-collapse').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var wrap = btn.closest('.notif-body-wrap');
      var full = wrap.querySelector('.msg-full');
      var short = wrap.querySelector('.msg-short');
      if (full) full.classList.add('hidden');
      if (short) short.classList.remove('hidden');
      btn.classList.add('hidden');
      var exp = wrap.querySelector('.js-expand');
      if (exp) exp.classList.remove('hidden');
    });
  });

  document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = btn.getAttribute('data-copy');
      copyText(text, btn);
    });
  });

  document.querySelectorAll('.js-show-info').forEach(function (el) {
    el.addEventListener('click', function () {
      var text = el.getAttribute('data-info');
      var title = el.getAttribute('data-title') || 'Комментарий';
      showInfoModal(title, text);
    });
  });

  document.querySelectorAll('.js-confirm').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      var msg = form.getAttribute('data-confirm');
      if (!confirm(msg)) e.preventDefault();
    });
  });

  auto_attendance();
  auto_schedule_rows();
  auto_bell_rows();
  auto_child_select();
});

function hidden() { return 'hidden'; }

function copyText(text, btn) {
  var done = function () {
    if (!btn) return;
    var old = btn.textContent;
    btn.textContent = 'Скопировано!';
    setTimeout(function () { btn.textContent = old; }, 1500);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
  } else { fallbackCopy(text); done(); }
}
function fallbackCopy(text) {
  var ta = document.createElement('textarea');
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); } catch (e) {}
  document.body.removeChild(ta);
}

function randomLogins() {
  var gens = document.querySelectorAll('[data-generate-login]');
  gens.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var input = btn.closest('.input-with-btn').querySelector('[data-login-target]');
      input.value = makeLogin();
    });
  });
}
function makeLogin() {
  var pref = ['user', 'student', 'teacher', 'pupil'];
  return pref[Math.floor(Math.random() * pref.length)] + '_' + Math.random().toString(36).slice(2, 7);
}

function randomPasswords() {
  var gens = document.querySelectorAll('[data-generate-password]');
  gens.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var input = btn.closest('.input-with-btn').querySelector('[data-password-target]');
      input.value = makePassword();
    });
  });
}

function makePassword(len) {
  len = len || 9;
  var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  var symbols = '!@#$%^&*';
  var out = '';
  var set = chars;
  for (var i = 0; i < len; i++) {
    if (i % 3 === 2) set = symbols;
    else set = chars;
    out += set.charAt(Math.floor(Math.random() * set.length));
  }
  return out;
}

function showInfoModal(title, text) {
  var existing = document.getElementById('info-modal');
  if (existing) existing.remove();
  var div = document.createElement('div');
  div.className = 'modal-backdrop open';
  div.id = 'info-modal';
  div.innerHTML =
    '<div class="modal">' +
    '<h3>' + escapeHtml(title) + '</h3>' +
    '<p style="white-space:pre-wrap">' + escapeHtml(text || '—') + '</p>' +
    '<div class="actions"><button class="btn ghost" data-modal-close>Закрыть</button></div>' +
    '</div>';
  document.body.appendChild(div);
  div.querySelector('[data-modal-close]').addEventListener('click', function () { div.remove(); });
  div.addEventListener('click', function (e) { if (e.target === div) div.remove(); });
}

function escapeHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function auto_attendance() {
  document.querySelectorAll('.att-grade-row').forEach(function (row) {
    var attSel = row.querySelector('.att-select');
    var gradeSel = row.querySelector('.grade-select');
    var cmt = row.querySelector('.cmt-input');
    var save = row.querySelector('.row-save');
    if (attSel) attSel.addEventListener('change', function () { if (cmt) cmt.classList.remove('hidden'); if (save) save.classList.remove('hidden'); });
    if (gradeSel) gradeSel.addEventListener('change', function () { if (cmt) cmt.classList.remove('hidden'); if (save) save.classList.remove('hidden'); });
  });
}

function auto_schedule_rows() {
  var container = document.getElementById('schedule-rows');
  if (!container) return;
  var addBtn = document.getElementById('add-lesson');
  if (!addBtn) return;
  addBtn.addEventListener('click', function () { add_schedule_row(container); });
}

function add_schedule_row(container) {
  var row = document.createElement('div');
  row.className = 'lesson-input-row';
  row.innerHTML =
    '<div class="row-num"></div>' +
    '<div style="flex:1.4"><label class="f"><span class="lbl">Название урока</span><input type="text" name="subjects" placeholder="Например: Математика"></label></div>' +
    '<div style="flex:1"><label class="f"><span class="lbl">Учитель</span>' +
    '<select name="teacher_ids"><option value="">— не выбран —</option>' + teacherOptions() + '</select></label></div>' +
    '<div style="flex:0.6"><label class="f"><span class="lbl">Кабинет</span><input type="text" name="rooms" placeholder="12"></label></div>' +
    '<button type="button" class="btn ghost sm remove-row" style="align-self:flex-end">✕</button>';
  container.appendChild(row);
  renumber(container);
  row.querySelector('.remove-row').addEventListener('click', function () { row.remove(); renumber(container); });
  var inputs = row.querySelectorAll('input');
  inputs.forEach(function (i) { i.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); add_schedule_row(container); } }); });
}

function renumber(container) {
  container.querySelectorAll('.lesson-input-row .row-num').forEach(function (el, i) {
    el.textContent = (i + 1) + '.';
  });
}

function teacherOptions() {
  return window.__teacherOptions || '<option value="">— не выбран —</option>';
}

function auto_bell_rows() {
  var container = document.getElementById('bell-rows');
  if (!container) return;
  var addBtn = document.getElementById('add-bell');
  if (!addBtn) return;
  addBtn.addEventListener('click', function () { add_bell_row(container); });
  window.__bellRowsDone = true;
  if (!container.querySelector('.bell-input-row')) add_bell_row(container);
}

function add_bell_row(container) {
  var row = document.createElement('div');
  row.className = 'bell-input-row form-row';
  row.innerHTML =
    '<label class="f" style="flex:0.5"><span class="lbl">Номер урока</span><input type="number" name="lesson_number" min="1" value="' + (container.children.length + 1) + '"></label>' +
    '<label class="f"><span class="lbl">Начало</span><input type="time" name="start_time" value="' + defaultTime(container.children.length) + '"></label>' +
    '<label class="f"><span class="lbl">Конец</span><input type="time" name="end_time" value="' + defaultTimeEnd(container.children.length) + '"></label>' +
    '<button type="button" class="btn ghost sm remove-row" style="align-self:flex-end">✕</button>';
  container.appendChild(row);
  row.querySelector('.remove-row').addEventListener('click', function () { row.remove(); });
}

function defaultTime(i) {
  var h = 8 + i;
  return (h < 10 ? '0' + h : h) + ':30';
}
function defaultTimeEnd(i) {
  var h = 9 + i;
  return (h < 10 ? '0' + h : h) + ':15';
}

function auto_child_select() {
  var childSel = document.getElementById('child-select');
  var groupInput = document.getElementById('group-input');
  if (childSel && groupInput) {
    childSel.addEventListener('change', function () {
      var opt = childSel.options[childSel.selectedIndex];
      var g = opt ? opt.getAttribute('data-group') : '';
      if (g) groupInput.value = g;
    });
  }
}

function init_lesson_presets() {
  document.querySelectorAll('.lesson-preset').forEach(function (el) {
    var btn = el.querySelector('.preset-btn');
    var suggest = el.querySelector('.preset-suggest');
    if (btn && suggest) {
      btn.addEventListener('click', function () { suggest.classList.toggle('hidden'); });
    }
  });
}

window.__teacherOptionsLoaded = function (html) { window.__teacherOptions = html; };
document.addEventListener('DOMContentLoaded', function () {
  randomLogins();
  randomPasswords();
  init_lesson_presets();
});