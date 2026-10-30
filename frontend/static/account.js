/* account.js : the Register, Account and Admin pages (written by the backend side).
 * Each page sets <body data-page="register|account|admin">. Nothing happens on other pages.
 * Talks to the JSON API in docs/API.md. auth.js (loaded first) adds the CSRF header.
 * Every piece of server data is shown with .text(), never as HTML.
 */
$(document).ready(function () {

    var page = $('body').data('page');
    if (!page) {
        return;
    }

    var QUEUE_LABELS = { any: 'Any queue', ranked: 'Ranked', casual: 'Casual' };

    function periodLabel(months) {
        return months + (Number(months) === 1 ? ' month' : ' months');
    }

    function errorText(xhr) {
        return (xhr.responseJSON && xhr.responseJSON.error) || 'Something went wrong. Please try again.';
    }

    function say($el, text, kind) {
        $el.removeClass('error success').addClass(kind).text(text).prop('hidden', false);
    }

    function clear($el) {
        $el.prop('hidden', true).text('');
    }

    function send(method, url, data) {
        return $.ajax({
            url: url,
            method: method,
            contentType: 'application/json',
            dataType: 'json',
            data: data === undefined ? undefined : JSON.stringify(data)
        });
    }

    function formData($form) {
        var data = {};
        $form.serializeArray().forEach(function (field) {
            data[field.name] = field.value;
        });
        return data;
    }

    // Shows the page only to people who may see it.
    function gate(session, needAdmin, $view) {
        var $message = $('#gate-message');
        if (!session.loggedIn) {
            $message.text('Please log in using the box at the top of the page to see this page.').prop('hidden', false);
            return false;
        }
        if (needAdmin && session.role !== 'admin') {
            $message.text('Only administrators can see this page.').prop('hidden', false);
            return false;
        }
        $view.prop('hidden', false);
        return true;
    }

    /* ------------------------------ Register ------------------------------ */
    if (page === 'register') {
        var $registerForm = $('#register-form');
        var $registerMessage = $('#form-message');

        $registerForm.on('submit', function (event) {
            event.preventDefault();
            clear($registerMessage);
            var data = formData($registerForm);
            if (data.password !== data.confirmPassword) {
                say($registerMessage, 'The two passwords do not match.', 'error');
                return;
            }
            var $button = $registerForm.find('button').prop('disabled', true);
            send('POST', '/api/register', data).done(function () {
                // Log the new user in straight away, then show their account page.
                send('POST', '/api/login', { username: data.username, password: data.password })
                    .done(function () { window.location.href = 'account.html'; })
                    .fail(function () {
                        say($registerMessage, 'Account created. Use the login box at the top to sign in.', 'success');
                        $button.prop('disabled', false);
                    });
            }).fail(function (xhr) {
                say($registerMessage, errorText(xhr), 'error');
                $button.prop('disabled', false);
            });
        });
    }

    /* ------------------------------ Account ------------------------------- */
    function renderSearches(searches) {
        var $body = $('#search-rows').empty();
        if (searches.length === 0) {
            $body.append($('<tr></tr>').append(
                $('<td class="empty-row" colspan="5"></td>').text('No saved searches yet. Open a player profile and press "Follow this player".')
            ));
            return;
        }
        searches.forEach(function (s) {
            var href = 'results.html?search=' + encodeURIComponent(s.riotId) + '&period=' + encodeURIComponent(s.period);
            var $row = $('<tr></tr>').data('search', s);
            $row.append(
                $('<td></td>').append($('<a></a>').attr('href', href).text(s.riotId)),
                $('<td class="cell-queue"></td>').text(QUEUE_LABELS[s.queue] || s.queue),
                $('<td class="cell-period"></td>').text(periodLabel(s.period)),
                $('<td></td>').text(s.savedOn),
                $('<td class="cell-actions"></td>')
            );
            showRowActions($row);
            $body.append($row);
        });
    }

    function showRowActions($row) {
        var s = $row.data('search');
        $row.find('.cell-queue').text(QUEUE_LABELS[s.queue] || s.queue);
        $row.find('.cell-period').text(periodLabel(s.period));
        $row.find('.cell-actions').empty().append(
            $('<div class="row-actions"></div>').append(
                $('<button type="button" class="btn-small btn-quiet js-edit">Edit</button>'),
                $('<button type="button" class="btn-small btn-quiet js-delete">Delete</button>')
            )
        );
    }

    function loadSearches() {
        return $.getJSON('/api/me/searches').done(function (data) {
            renderSearches(data.searches);
        }).fail(function (xhr) {
            say($('#searches-message'), errorText(xhr), 'error');
        });
    }

    if (page === 'account') {
        var $searchesMessage = $('#searches-message');

        $.getJSON('/api/session').done(function (session) {
            if (!gate(session, false, $('#account-view'))) {
                return;
            }
            $('#account-name').text(session.username);
            $('#account-role').text(session.role === 'admin' ? 'Administrator account' : 'Registered user');
            loadSearches();
        });

        // UPDATE: swap the cells for drop-downs
        $('#search-rows').on('click', '.js-edit', function () {
            var $row = $(this).closest('tr');
            var s = $row.data('search');
            var $queue = $('<select aria-label="Queue"></select>');
            Object.keys(QUEUE_LABELS).forEach(function (key) {
                $queue.append($('<option></option>').val(key).text(QUEUE_LABELS[key]));
            });
            $queue.val(s.queue);
            var $period = $('<select aria-label="Time period"></select>');
            for (var m = 1; m <= 6; m++) {
                $period.append($('<option></option>').val(m).text(periodLabel(m)));
            }
            $period.val(String(s.period));
            $row.find('.cell-queue').empty().append($queue);
            $row.find('.cell-period').empty().append($period);
            $row.find('.cell-actions').empty().append(
                $('<div class="row-actions"></div>').append(
                    $('<button type="button" class="btn-small js-save">Save</button>'),
                    $('<button type="button" class="btn-small btn-quiet js-cancel">Cancel</button>')
                )
            );
        });

        $('#search-rows').on('click', '.js-cancel', function () {
            showRowActions($(this).closest('tr'));
        });

        $('#search-rows').on('click', '.js-save', function () {
            var $row = $(this).closest('tr');
            var s = $row.data('search');
            var change = { queue: $row.find('.cell-queue select').val(), period: Number($row.find('.cell-period select').val()) };
            clear($searchesMessage);
            send('PUT', '/api/me/searches/' + s.id, change).done(function () {
                $row.data('search', $.extend({}, s, change));
                showRowActions($row);
                say($searchesMessage, 'Saved search updated.', 'success');
            }).fail(function (xhr) {
                say($searchesMessage, errorText(xhr), 'error');
            });
        });

        // DELETE: ask first, in the row itself
        $('#search-rows').on('click', '.js-delete', function () {
            $(this).closest('.cell-actions').empty().append(
                $('<div class="row-actions"></div>').append(
                    $('<span class="confirm-text">Delete this search?</span>'),
                    $('<button type="button" class="btn-small btn-danger js-confirm-delete">Yes, delete</button>'),
                    $('<button type="button" class="btn-small btn-quiet js-cancel">No</button>')
                )
            );
        });

        $('#search-rows').on('click', '.js-confirm-delete', function () {
            var $row = $(this).closest('tr');
            clear($searchesMessage);
            send('DELETE', '/api/me/searches/' + $row.data('search').id).done(function () {
                say($searchesMessage, 'Saved search deleted.', 'success');
                loadSearches();
            }).fail(function (xhr) {
                say($searchesMessage, errorText(xhr), 'error');
            });
        });

        // CREATE
        var $addForm = $('#add-search-form');
        var $addMessage = $('#add-message');
        $addForm.on('submit', function (event) {
            event.preventDefault();
            clear($addMessage);
            var data = formData($addForm);
            data.period = Number(data.period);
            send('POST', '/api/me/searches', data).done(function () {
                $addForm[0].reset();
                say($addMessage, 'Saved. It now appears in the list above.', 'success');
                loadSearches();
            }).fail(function (xhr) {
                say($addMessage, errorText(xhr), 'error');
            });
        });

        // Change password
        var $passwordForm = $('#password-form');
        var $passwordMessage = $('#password-message');
        $passwordForm.on('submit', function (event) {
            event.preventDefault();
            clear($passwordMessage);
            var data = formData($passwordForm);
            if (data.newPassword !== data.confirmPassword) {
                say($passwordMessage, 'The two new passwords do not match.', 'error');
                return;
            }
            send('POST', '/api/me/password', data).done(function () {
                $passwordForm[0].reset();
                say($passwordMessage, 'Your password was changed.', 'success');
            }).fail(function (xhr) {
                say($passwordMessage, errorText(xhr), 'error');
            });
        });
    }

    /* ------------------------------- Admin -------------------------------- */
    if (page === 'admin') {
        var $usersMessage = $('#users-message');
        var myName = null;

        var renderUsers = function (users) {
            var $body = $('#user-rows').empty();
            users.forEach(function (u) {
                var $actions = $('<td class="cell-actions"></td>');
                if (u.username === myName) {
                    $actions.append($('<span class="muted">(you)</span>').css('color', 'var(--text-muted)'));
                } else {
                    $actions.append($('<div class="row-actions"></div>').append(
                        $('<button type="button" class="btn-small btn-quiet js-delete-user">Delete</button>')
                    ));
                }
                $body.append($('<tr></tr>').data('user', u).append(
                    $('<td></td>').text(u.username),
                    $('<td></td>').text(u.email),
                    $('<td></td>').text(u.role),
                    $('<td></td>').text(u.joined),
                    $('<td></td>').text(u.savedSearches),
                    $actions
                ));
            });
        };

        var loadUsers = function () {
            $.getJSON('/api/admin/users').done(function (data) {
                renderUsers(data.users);
            }).fail(function (xhr) {
                say($usersMessage, errorText(xhr), 'error');
            });
        };

        $.getJSON('/api/session').done(function (session) {
            myName = session.username;
            if (gate(session, true, $('#admin-view'))) {
                loadUsers();
            }
        });

        $('#user-rows').on('click', '.js-delete-user', function () {
            var u = $(this).closest('tr').data('user');
            $(this).closest('.cell-actions').empty().append(
                $('<div class="row-actions"></div>').append(
                    $('<span class="confirm-text"></span>').text('Delete ' + u.username + ' and ' + u.savedSearches + ' saved search(es)?'),
                    $('<button type="button" class="btn-small btn-danger js-confirm-delete-user">Yes, delete</button>'),
                    $('<button type="button" class="btn-small btn-quiet js-cancel-delete-user">No</button>')
                )
            );
        });

        $('#user-rows').on('click', '.js-cancel-delete-user', loadUsers);

        $('#user-rows').on('click', '.js-confirm-delete-user', function () {
            var u = $(this).closest('tr').data('user');
            clear($usersMessage);
            send('DELETE', '/api/admin/users/' + u.id).done(function () {
                say($usersMessage, 'Deleted the account "' + u.username + '" and its saved searches.', 'success');
                loadUsers();
            }).fail(function (xhr) {
                say($usersMessage, errorText(xhr), 'error');
                loadUsers();
            });
        });

        var $createForm = $('#create-user-form');
        var $createMessage = $('#create-message');
        $createForm.on('submit', function (event) {
            event.preventDefault();
            clear($createMessage);
            send('POST', '/api/admin/users', formData($createForm)).done(function (result) {
                $createForm[0].reset();
                say($createMessage, 'Created the ' + result.role + ' account "' + result.username + '".', 'success');
                loadUsers();
            }).fail(function (xhr) {
                say($createMessage, errorText(xhr), 'error');
            });
        });
    }
});
