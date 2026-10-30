/* auth.js : login glue between the pages and the backend (written by the backend side).
 *
 * Add it to every page, AFTER jQuery and script.js:
 *     <script src="auth.js"></script>
 *
 * What it does (no HTML changes needed):
 *   1. Asks the server who is logged in (GET /api/session) and gets the CSRF token.
 *   2. Adds the token to every POST/PUT/DELETE request, as the X-CSRF-Token header.
 *   3. #login-box   : sends the username and password to /api/login (the form's own
 *                     field ids stay #username and #pw), shows an error message if it
 *                     fails, and reloads the page when it works.
 *   4. When logged in, replaces #login-box with the same #account-box markup that
 *      list.html uses (picture, username, "Log Out"). "Log Out" calls /api/logout.
 *   5. If somebody opens a "logged in" page (list.html) while logged out, the
 *      #account-box says "Not logged in" with a link back to the home page.
 *
 *   6. Points the "Register" link at register.html, adds Account (and Admin, for admins)
 *      links to the logged-in box, and adds a "Follow this player" button to profiles.
 * The Register, Account and Admin pages themselves are in account.js.
 */
$(document).ready(function () {

    var csrfToken = null;
    var AVATAR = 'img/profilePicImg.PNG';

    // Every request that changes data carries the token.
    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (csrfToken && !/^(GET|HEAD|OPTIONS)$/i.test(settings.type)) {
                xhr.setRequestHeader('X-CSRF-Token', csrfToken);
            }
        }
    });

    function accountBox(user) {
        var $box = $('<div id="account-box"></div>');
        $box.append(
            $('<img>').attr({ src: AVATAR, alt: user.username + "'s profile picture" }),
            $('<span></span>').text(user.username),
            $('<a href="account.html">Account</a>')
        );
        if (user.role === 'admin') {
            $box.append($('<a href="admin.html">Admin</a>'));
        }
        $box.append($('<a href="home.html" id="logout-link">Log Out</a>'));
        return $box;
    }

    function showLoggedIn(user) {
        var $login = $('#login-box');
        var $existing = $('#account-box');
        if ($login.length) {
            $login.replaceWith(accountBox(user));
        } else if ($existing.length) {
            $existing.replaceWith(accountBox(user));
        }
    }

    function showLoggedOut() {
        var $existing = $('#account-box');   // pages such as list.html have no login form
        if ($existing.length) {
            $existing.empty().append(
                $('<span>Not logged in</span>'),
                $('<a href="home.html">Log in</a>')
            );
        }
    }

    function wireLoginForm() {
        var $form = $('#login-box');
        if (!$form.length) {
            return;
        }
        $form.find('a').attr('href', 'register.html');
        var $error = $('<span class="login-error" role="alert"></span>')
            .css({ color: '#ffb4b4', fontSize: '0.8rem' }).hide();
        $form.append($error);

        $form.on('submit', function (event) {
            event.preventDefault();
            $error.hide();
            $.ajax({
                url: '/api/login',
                method: 'POST',
                contentType: 'application/json',
                dataType: 'json',
                data: JSON.stringify({ username: $('#username').val(), password: $('#pw').val() })
            }).done(function () {
                window.location.reload();
            }).fail(function (xhr) {
                var message = (xhr.responseJSON && xhr.responseJSON.error) || 'Login failed. Please try again.';
                $error.text(message).show();
            });
        });
    }

    $(document).on('click', '#logout-link', function (event) {
        event.preventDefault();
        $.ajax({ url: '/api/logout', method: 'POST', dataType: 'json' }).always(function () {
            window.location.href = 'home.html';
        });
    });

    /* ---- "Follow this player" on the profile page (saves a search) ---- */
    var currentSession = null;
    var shownRiotId = null;
    var QUEUE_TO_SAVED = { any: 'any', solo: 'ranked', flex: 'ranked' };   // saved searches store any / ranked / casual

    function renderFollow() {
        var $info = $('#profile-info .profile-details');
        if (!$info.length || !currentSession || !shownRiotId) {
            return;
        }
        $info.find('.follow-box').remove();
        var $box = $('<div class="follow-box"></div>');
        var $status = $('<span class="follow-status"></span>');
        if (currentSession.loggedIn) {
            var $button = $('<button type="button" class="btn btn-gold">Follow this player</button>');
            $button.on('click', function () {
                var queue = QUEUE_TO_SAVED[$('#queue').val()] || 'any';
                var period = Math.min(6, Number($('#period').val()) || 6);
                $button.prop('disabled', true);
                $.ajax({
                    url: '/api/me/searches', method: 'POST', contentType: 'application/json', dataType: 'json',
                    data: JSON.stringify({ riotId: shownRiotId, queue: queue, period: period })
                }).done(function () {
                    $status.removeClass('error').addClass('success').empty()
                        .append(document.createTextNode('Saved! See it on your '), $('<a href="account.html">Account page</a>'), document.createTextNode('.'));
                }).fail(function (xhr) {
                    var message = (xhr.responseJSON && xhr.responseJSON.error) || 'Could not save.';
                    $status.removeClass('success').addClass('error').text(message);
                }).always(function () {
                    $button.prop('disabled', false);
                });
            });
            $box.append($button);
        } else {
            $status.text('Log in to follow this player and save this search.');
        }
        $box.append($status);
        $info.append($box);
    }

    $(document).ajaxSuccess(function (event, xhr, settings, data) {
        if (settings.url.indexOf('/api/profile') === 0 && data && data.riotId) {
            shownRiotId = data.riotId;
            renderFollow();
        }
    });

    $.getJSON('/api/session').done(function (session) {
        csrfToken = session.csrfToken;
        currentSession = session;
        if (session.loggedIn) {
            showLoggedIn(session);
        } else {
            showLoggedOut();
            wireLoginForm();
        }
        renderFollow();
    });
});
