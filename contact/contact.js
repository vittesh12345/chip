/* Briefing form behavior.
 *
 * The page's default markup state is the one that works with no scripting and
 * no form provider: the direct-address block is visible and the form is
 * hidden. This file only ever upgrades that state, and it drops back to it
 * whenever a submission cannot go through.
 */
(function () {
  'use strict';

  var form      = document.getElementById('briefing-form');
  var fallback  = document.getElementById('fallback');
  var success   = document.getElementById('form-success');
  var errorBox  = document.getElementById('form-error');
  var status    = document.getElementById('form-status');
  var submitBtn = document.getElementById('submit-btn');
  var copyBtn   = document.getElementById('copy-address');
  var copyState = document.getElementById('copy-status');
  var address   = document.getElementById('contact-address');
  var mailto    = document.getElementById('mailto-link');
  var note      = document.getElementById('mission-note');

  var MISSIONS = {
    defense:   'Defense & intelligence',
    operators: 'Satellite operators',
    orbital:   'Orbital compute & AI infrastructure',
    other:     'Other'
  };

  /* --- Per-context intent -------------------------------------------------
     Carries what the old per-CTA mail subjects used to carry: the mission area
     the visitor arrived from. Preselects the form field, and when the form is
     unavailable, moves the same context into the mail subject and a visible
     note so nothing is lost.                                                 */
  var mission = new URLSearchParams(location.search).get('mission');
  if (mission && Object.prototype.hasOwnProperty.call(MISSIONS, mission)) {
    var label = MISSIONS[mission];
    var select = document.getElementById('mission');
    if (select) select.value = mission;
    if (mailto) {
      mailto.href = 'mailto:contact@vantage.industries?subject=' +
        encodeURIComponent('Briefing request: ' + label);
    }
    if (note) {
      note.textContent = 'Mission area: ' + label;
      note.hidden = false;
    }
  }

  /* --- Copy to clipboard --------------------------------------------------
     Revealed only once we know the API is there, so the button is never a
     control that does nothing.                                               */
  if (copyBtn && address && navigator.clipboard && navigator.clipboard.writeText) {
    copyBtn.hidden = false;
    copyBtn.addEventListener('click', function () {
      navigator.clipboard.writeText(address.textContent.trim()).then(function () {
        copyState.textContent = 'Copied';
        setTimeout(function () { copyState.textContent = ''; }, 2600);
      }, function () {
        copyState.textContent = 'Copy failed, select the address above';
      });
    });
  }

  /* --- Endpoint gate ------------------------------------------------------
     With no endpoint configured there is nowhere to POST, so the form stays
     hidden and the direct-address block remains the contact path.            */
  if (!form) return;
  var endpoint = (form.getAttribute('data-endpoint') || '').trim();
  if (!endpoint) return;

  form.action = endpoint;
  form.hidden = false;
  fallback.hidden = true;

  /* --- Validation ---------------------------------------------------------
     State is carried by aria-invalid and a described-by message, not by the
     border color on its own.                                                 */
  var EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function setFieldError(input, message) {
    var msg = document.getElementById(input.getAttribute('aria-describedby'));
    if (message) {
      input.setAttribute('aria-invalid', 'true');
      if (msg) { msg.textContent = message; msg.classList.add('show'); }
    } else {
      input.removeAttribute('aria-invalid');
      if (msg) { msg.textContent = ''; msg.classList.remove('show'); }
    }
  }

  function validate() {
    var email = document.getElementById('email');
    var value = email.value.trim();
    if (!value) { setFieldError(email, 'Enter a work email so we can reply.'); return email; }
    if (!EMAIL.test(value)) { setFieldError(email, 'That does not look like an email address.'); return email; }
    setFieldError(email, '');
    return null;
  }

  document.getElementById('email').addEventListener('input', function () {
    if (this.getAttribute('aria-invalid') === 'true') validate();
  });

  /* --- Submit -------------------------------------------------------------- */
  /* The alert region is always in the DOM and collapses while empty (see the
     :empty rule in the stylesheet), so a message is announced as content
     arriving in an established live region rather than as a region appearing. */
  function showFailure(message) {
    var lede = document.getElementById('fallback-lede');
    // The default wording explains an unconfigured form. Here the form exists
    // and the send failed, so say that instead.
    if (lede) lede.textContent = 'Email the team directly and we will come back to you with times.';
    fallback.hidden = false;
    errorBox.innerHTML = '<b>' + message + '</b> Your request was not sent. ' +
      'Use the address below and it will reach the same place.';
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();

    // Honeypot: a real visitor cannot reach this field. A filled one is a bot.
    if (form.elements.company_website.value !== '') {
      showFailure('This submission was rejected.');
      return;
    }

    var invalid = validate();
    if (invalid) { invalid.focus(); return; }

    errorBox.innerHTML = '';
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending…';
    status.textContent = 'Sending your request.';

    var data = new FormData(form);
    data.delete('company_website');

    fetch(endpoint, {
      method: 'POST',
      body: data,
      headers: { 'Accept': 'application/json' }
    }).then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      status.textContent = '';
      form.hidden = true;
      fallback.hidden = true;
      success.hidden = false;
      success.focus();
    }).catch(function () {
      status.textContent = '';
      submitBtn.disabled = false;
      submitBtn.textContent = 'Request a briefing →';
      showFailure('We could not reach the form service.');
    });
  });
})();
