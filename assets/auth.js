(function() {
  var AUTH_COOKIE_NAME = 'gdst_auth';
  var AUTH_PASSWORD = '7777777';
  var COOKIE_DAYS = 30;

  function getCookie(name) {
    var match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? match[2] : null;
  }

  function setCookie(name, value, days) {
    var expires = new Date();
    expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
    document.cookie = name + '=' + value + ';expires=' + expires.toUTCString() + ';path=/;SameSite=Lax';
  }

  function showAuth() {
    var overlay = document.getElementById('auth-overlay');
    if (overlay) {
      overlay.style.display = 'flex';
    }
    document.body.style.overflow = 'hidden';
  }

  function hideAuth() {
    var overlay = document.getElementById('auth-overlay');
    if (overlay) {
      overlay.style.display = 'none';
    }
    document.body.style.overflow = '';
  }

  window.checkPassword = function() {
    var input = document.getElementById('auth-password');
    if (input.value === AUTH_PASSWORD) {
      setCookie(AUTH_COOKIE_NAME, '1', COOKIE_DAYS);
      hideAuth();
      return false;
    } else {
      alert('口令错误，请重新输入');
      input.value = '';
      input.focus();
      return false;
    }
  };

  document.addEventListener('DOMContentLoaded', function() {
    if (!getCookie(AUTH_COOKIE_NAME)) {
      showAuth();
    }
  });
})();
