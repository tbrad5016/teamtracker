$(document).ready(function () {

    const USE_MOCK_PROFILE_DATA = false;
    const SAMPLE_PLAYER_ID = 'lunarraven#7777';
    const GOOD_KDA_MIN = 3.5;
    const AVERAGE_KDA_MIN = 2.5;
    const KDA_BAR_MAX = 5;
    const MISSING_VALUE = '—';

    const ROLE_LABELS = {
        TOP: 'Top',
        JUNGLE: 'Jungle',
        MIDDLE: 'Middle',
        BOTTOM: 'Bottom',
        UTILITY: 'Support',
        SUPPORT: 'Support'
    };

    const QUEUE_LABELS = {
        RANKED_SOLO_5X5: 'Ranked Solo/Duo',
        RANKED_FLEX_SR: 'Ranked Flex'
    };

    const PROFILE_MESSAGES = {
        emptySearch: 'Type a Riot ID into the search box above to look up a profile!',
        notFound: 'Oops, we couldn\'t find that profile! Try searching for a different Riot ID!',
        loginNeeded: 'Please log in to view your profile.',
        failed: 'Something went wrong loading this profile. Please try again in a moment.'
    };

    const MOCK_RANKS = [
        { queue: 'RANKED_SOLO_5x5', rank: 'Diamond II', lp: 0, wins: 47, losses: 45 },
        { queue: 'RANKED_FLEX_SR', rank: 'Platinum III', lp: 47, wins: 48, losses: 53 }
    ];

    const MOCK_FILTERED_DATA = {
        any: {
            games: 21,
            wins: 8,
            roles: [
                { role: 'TOP', games: 11, avgKills: 4.5, avgDeaths: 4.7, avgAssists: 5.9, kda: 2.21 },
                { role: 'JUNGLE', games: 12, avgKills: 5.6, avgDeaths: 4.8, avgAssists: 8.4, kda: 2.9 },
                { role: 'MIDDLE', games: 16, avgKills: 6.4, avgDeaths: 4.6, avgAssists: 7.4, kda: 3.04 },
                { role: 'BOTTOM', games: 12, avgKills: 7.3, avgDeaths: 3.7, avgAssists: 6.2, kda: 3.66 },
                { role: 'UTILITY', games: 13, avgKills: 1.3, avgDeaths: 5.2, avgAssists: 10.3, kda: 2.22 }
            ]
        },
        solo: {
            games: 13,
            wins: 6,
            roles: [
                { role: 'TOP', games: 7, avgKills: 5.1, avgDeaths: 4.2, avgAssists: 4.6, kda: 2.31 },
                { role: 'JUNGLE', games: 8, avgKills: 6.0, avgDeaths: 4.4, avgAssists: 9.1, kda: 3.43 },
                { role: 'MIDDLE', games: 10, avgKills: 6.8, avgDeaths: 4.0, avgAssists: 7.9, kda: 3.68 },
                { role: 'BOTTOM', games: 8, avgKills: 7.9, avgDeaths: 3.5, avgAssists: 6.4, kda: 4.09 },
                { role: 'UTILITY', games: 9, avgKills: 1.5, avgDeaths: 4.8, avgAssists: 11.2, kda: 2.65 }
            ]
        },
        flex: {
            games: 8,
            wins: 2,
            roles: [
                { role: 'TOP', games: 4, avgKills: 3.8, avgDeaths: 5.6, avgAssists: 4.3, kda: 1.45 },
                { role: 'JUNGLE', games: 4, avgKills: 4.9, avgDeaths: 5.5, avgAssists: 7.2, kda: 2.2 },
                { role: 'MIDDLE', games: 6, avgKills: 5.7, avgDeaths: 5.1, avgAssists: 6.5, kda: 2.39 },
                { role: 'BOTTOM', games: 4, avgKills: 6.4, avgDeaths: 4.4, avgAssists: 5.5, kda: 2.7 },
                { role: 'UTILITY', games: 5, avgKills: 1.1, avgDeaths: 5.9, avgAssists: 9.4, kda: 1.78 }
            ]
        }
    };

    const MOCK_PERIOD_SCALE = { '1': 0.15, '3': 0.5, '6': 1, '12': 1.8 };

    function buildMockProfile(riotId, queue, period) {
        const dataset = MOCK_FILTERED_DATA[queue] || MOCK_FILTERED_DATA.any;
        const scale = MOCK_PERIOD_SCALE[period] || 1;
        return {
            riotId: riotId,
            ranks: MOCK_RANKS,
            summary: {
                games: Math.round(dataset.games * scale),
                wins: Math.round(dataset.wins * scale)
            },
            roles: dataset.roles.map(function (role) {
                return $.extend({}, role, { games: Math.max(1, Math.round(role.games * scale)) });
            })
        };
    }

    function requestMockProfile(params) {
        const deferred = $.Deferred();
        const isSearch = params.riotId !== undefined;
        setTimeout(function () {
            if (isSearch && params.riotId.toLowerCase() !== SAMPLE_PLAYER_ID) {
                deferred.reject({ status: 404 });
                return;
            }
            deferred.resolve(buildMockProfile(isSearch ? 'LunarRaven#7777' : 'My Profile Username', params.queue, params.period));
        }, 300);
        return deferred.promise();
    }

    function requestProfile(endpoint, params) {
        if (USE_MOCK_PROFILE_DATA) {
            return requestMockProfile(params);
        }
        return $.ajax({ url: endpoint, data: params, dataType: 'json' });
    }

    function toNumber(value) {
        return value === null || value === undefined || value === '' ? NaN : Number(value);
    }

    function formatNumber(value, maxDecimals) {
        const number = toNumber(value);
        return Number.isFinite(number) ? String(Number(number.toFixed(maxDecimals))) : MISSING_VALUE;
    }

    function formatPercent(part, total) {
        const partNumber = toNumber(part);
        const totalNumber = toNumber(total);
        if (!Number.isFinite(partNumber) || !Number.isFinite(totalNumber) || totalNumber <= 0) {
            return MISSING_VALUE;
        }
        return (partNumber / totalNumber * 100).toFixed(1) + '%';
    }

    function formatText(value) {
        return value === null || value === undefined || value === '' ? MISSING_VALUE : String(value);
    }

    function labelFor(labels, value) {
        return labels[String(value).toUpperCase()] || formatText(value);
    }

    function ratingFor(kda) {
        if (!Number.isFinite(kda)) {
            return null;
        }
        if (kda >= GOOD_KDA_MIN) {
            return { className: 'rating-good', label: 'Good' };
        }
        if (kda >= AVERAGE_KDA_MIN) {
            return { className: 'rating-average', label: 'Average' };
        }
        return { className: 'rating-bad', label: 'Bad' };
    }

    function messageRow(columnCount, text) {
        return $('<tr></tr>').append($('<td class="empty-row"></td>').attr('colspan', columnCount).text(text));
    }

    function renderRanks(ranks) {
        const $body = $('#rank-rows').empty();
        if (!ranks || ranks.length === 0) {
            $body.append(messageRow(6, 'No ranked results yet.'));
            return;
        }
        ranks.forEach(function (entry) {
            $body.append($('<tr></tr>').append(
                $('<td></td>').text(labelFor(QUEUE_LABELS, entry.queue)),
                $('<td></td>').text(formatText(entry.rank)),
                $('<td></td>').text(formatText(entry.lp)),
                $('<td></td>').text(formatText(entry.wins)),
                $('<td></td>').text(formatText(entry.losses)),
                $('<td></td>').text(formatPercent(entry.wins, toNumber(entry.wins) + toNumber(entry.losses)))
            ));
        });
    }

    function renderSummary(summary) {
        const games = summary ? summary.games : null;
        const wins = summary ? summary.wins : null;
        $('#summary-games').text(formatNumber(games, 0));
        $('#summary-wins').text(formatNumber(wins, 0));
        $('#summary-winrate').text(formatPercent(wins, games));
    }

    function renderRoles(roles) {
        $('#role-note').text('Teammates are shown only as role averages, never by name. KDA = (kills + assists) / deaths. Good: ' + GOOD_KDA_MIN + ' or more. Average: ' + AVERAGE_KDA_MIN + ' to ' + GOOD_KDA_MIN + '. Bad: below ' + AVERAGE_KDA_MIN + '.');
        const $body = $('#role-rows').empty();
        if (!roles || roles.length === 0) {
            $body.append(messageRow(7, 'No games found for this filter.'));
            return;
        }
        roles.forEach(function (entry) {
            const kda = toNumber(entry.kda);
            const rating = ratingFor(kda);
            const $kdaCell = $('<td class="kda-cell"></td>');
            const $ratingCell = $('<td></td>');
            if (rating) {
                const width = Math.min(100, Math.max(0, kda / KDA_BAR_MAX * 100));
                $kdaCell.append(
                    $('<div class="kda-bar" aria-hidden="true"></div>').append(
                        $('<span class="kda-fill"></span>').addClass(rating.className).css('width', width + '%')
                    )
                );
                $ratingCell.append($('<span class="rating"></span>').addClass(rating.className).text(rating.label));
            }
            $kdaCell.append(document.createTextNode(formatNumber(kda, 2)));
            $body.append($('<tr></tr>').append(
                $('<td></td>').text(labelFor(ROLE_LABELS, entry.role)),
                $('<td></td>').text(formatNumber(entry.games, 0)),
                $('<td></td>').text(formatNumber(entry.avgKills, 1)),
                $('<td></td>').text(formatNumber(entry.avgDeaths, 1)),
                $('<td></td>').text(formatNumber(entry.avgAssists, 1)),
                $kdaCell,
                $ratingCell
            ));
        });
    }

    function renderProfile(data) {
        $('#profile-username').text(formatText(data.riotId));
        if (data.avatarUrl) {
            $('#profile-picture').attr('src', data.avatarUrl);
        }
        renderRanks(data.ranks);
        renderSummary(data.summary);
        renderRoles(data.roles);
    }

    const $profileView = $('#player-profile');

    if ($profileView.length) {
        const endpoint = $profileView.data('endpoint');
        const requiresSearch = $profileView.data('requiresSearch') === true;
        const $message = $('#profile-message');
        const $filterForm = $('.profile-filters');
        const $queue = $('#queue');
        const $period = $('#period');
        const $applyButton = $filterForm.find('button');
        const queryParams = new URLSearchParams(window.location.search);
        const searchedId = queryParams.get('search');
        let latestRequest = 0;

        const applyFilterFromUrl = function ($select, name) {
            const requested = queryParams.get(name);
            const isOption = requested !== null && $select.find('option').filter(function () {
                return this.value === requested;
            }).length > 0;
            if (isOption) {
                $select.val(requested);
            }
        };

        const showMessage = function (text) {
            $profileView.prop('hidden', true);
            $message.text(text).prop('hidden', false);
        };

        const showProfile = function (data) {
            renderProfile(data);
            $message.prop('hidden', true);
            $profileView.prop('hidden', false);
        };

        const syncUrl = function () {
            const params = new URLSearchParams(window.location.search);
            params.set('queue', $queue.val());
            params.set('period', $period.val());
            try {
                window.history.replaceState(null, '', window.location.pathname + '?' + params.toString());
            } catch (error) {
                return;
            }
        };

        const loadProfile = function () {
            const requestNumber = ++latestRequest;
            const params = { queue: $queue.val(), period: $period.val() };
            if (requiresSearch) {
                params.riotId = searchedId.trim();
            }
            $profileView.addClass('is-loading').attr('aria-busy', 'true');
            $applyButton.prop('disabled', true);

            requestProfile(endpoint, params)
                .done(function (data) {
                    if (requestNumber !== latestRequest) {
                        return;
                    }
                    if (data && data.found === false) {
                        showMessage(PROFILE_MESSAGES.notFound);
                        return;
                    }
                    try {
                        showProfile(data);
                    } catch (error) {
                        showMessage(PROFILE_MESSAGES.failed);
                    }
                })
                .fail(function (xhr) {
                    if (requestNumber !== latestRequest) {
                        return;
                    }
                    if (xhr.status === 404) {
                        showMessage(PROFILE_MESSAGES.notFound);
                    } else if (xhr.status === 401) {
                        showMessage(PROFILE_MESSAGES.loginNeeded);
                    } else {
                        showMessage(PROFILE_MESSAGES.failed);
                    }
                })
                .always(function () {
                    if (requestNumber !== latestRequest) {
                        return;
                    }
                    $profileView.removeClass('is-loading').removeAttr('aria-busy');
                    $applyButton.prop('disabled', false);
                });
        };

        applyFilterFromUrl($queue, 'queue');
        applyFilterFromUrl($period, 'period');

        $filterForm.on('submit', function (event) {
            event.preventDefault();
            syncUrl();
            loadProfile();
        });

        if (requiresSearch) {
            if (searchedId !== null) {
                $('#search-input').val(searchedId);
            }
            if (searchedId === null || searchedId.trim() === '') {
                showMessage(PROFILE_MESSAGES.emptySearch);
            } else {
                loadProfile();
            }
        } else {
            loadProfile();
        }
    }


    /*interaction 1: the My Builds vs Saved Builds tab sorting function on the Profile Page
    * clicking on one of the tab sorts the builds to onyl show a saved build vs a build the user created*/

    const $profileTabs = $('#profile-tabs');

    if ($profileTabs.length) {

        const switchToTab = function ($tab) {
            const targetSelector = $tab.attr('href'); // "#my-builds" or "#saved-builds"
            const $targetSection = $(targetSelector);

            $('#profile-tabs a').removeClass('selected'); //tab underline for chosen tab
            $tab.addClass('selected');

            $('#my-builds, #saved-builds').hide(); //shows the selected tab
            $targetSection.show();

            const buildCount = $targetSection.find('.build').length;
            let $summary = $targetSection.find('.tab-summary');

            if ($summary.length === 0) {
                $summary = $('<p class="tab-summary"></p>');
                $targetSection.find('> h2').after($summary);
            }
            $summary.text('Showing ' + buildCount + (buildCount === 1 ? ' build.' : ' builds.'));
        };

        $profileTabs.on('click', 'a', function (event) {
            event.preventDefault();
            switchToTab($(this));
        });

        switchToTab($profileTabs.find('a.selected'));
    }


    /* interaction 2: createItem attribute points go up and down when using the slider*/

    const TOTAL_POINTS = 30; //total points a new build gets to spend across all 4 stats, will be changed later to associate with level input
    const $attributeSliders = $('#attributes input[type="range"]');

    if ($attributeSliders.length) {

        $attributeSliders.on('input', function () {
            const $row = $(this).prev('.stat-row');
            $row.find('.stat-value').text($(this).val()); //modify the stat number

            //recalculate the total every time a slider moves.
            let pointsUsed = 0;
            $attributeSliders.each(function () {
                pointsUsed += parseInt($(this).val(), 10) || 0;
            });

            const pointsRemaining = TOTAL_POINTS - pointsUsed;
            $('#points-value').text(pointsRemaining); //modify points remaining

            const $pointsRemaining = $('#points-remaining');
            const $warning = $('#points-warning');

            if (pointsRemaining < 0) {
                $pointsRemaining.addClass('over-budget'); //warning for negative points remaining

                if ($warning.length === 0) {
                    $('<p id="points-warning" class="points-warning">You\'ve allocated more points than you have! Lower a stat to continue.</p>')
                        .insertAfter($(this).closest('#attributes'));
                }
            } else {
                $pointsRemaining.removeClass('over-budget');
                $warning.remove(); //removes warning
            }
        });
        $attributeSliders.trigger('input');
    }


    // Suggestions come from the database: GET /api/search?q=... (backend/server.py)

    $('#search-box, #home-search').each(function () {
        const $form = $(this);
        const $input = $form.find('input[type="search"]');
        const $list = $('<ul class="search-suggestions" role="listbox" hidden></ul>').appendTo($form);
        let activeIndex = -1;

        $input.attr({ autocomplete: 'off', 'aria-autocomplete': 'list' });

        const closeList = function () {
            $list.prop('hidden', true).empty();
            $input.attr('aria-expanded', 'false');
            activeIndex = -1;
        };

        const setActive = function (index) {
            const $options = $list.find('li.option');
            if ($options.length === 0) {
                return;
            }
            if (index < 0) {
                index = $options.length - 1;
            } else if (index >= $options.length) {
                index = 0;
            }
            $options.removeClass('active').attr('aria-selected', 'false');
            const $active = $options.eq(index).addClass('active').attr('aria-selected', 'true');
            $active[0].scrollIntoView({ block: 'nearest' });
            activeIndex = index;
        };

        const renderList = function () {
            const term = $input.val().trim();
            $list.empty();
            activeIndex = -1;

            if (term === '') {
                closeList();
                return;
            }

            $.getJSON('/api/search', { q: term }).done(function (data) {
                if ($input.val().trim() !== term) {
                    return; // the visitor kept typing, so this answer is out of date
                }
                const matches = (data && data.results) || [];
                $list.empty();
                activeIndex = -1;

                if (matches.length === 0) {
                    $list.append('<li class="no-match">No matching players</li>');
                } else {
                    matches.forEach(function (title) {
                        const start = title.toLowerCase().indexOf(term.toLowerCase());
                        const $option = $('<li class="option" role="option" aria-selected="false"></li>').data('title', title);
                        $option.append(
                            document.createTextNode(title.slice(0, start)),
                            $('<strong></strong>').text(title.slice(start, start + term.length)),
                            document.createTextNode(title.slice(start + term.length))
                        );
                        $list.append($option);
                    });
                }

                $list.prop('hidden', false);
                $input.attr('aria-expanded', 'true');
            });
        };

        const chooseOption = function (title) {
            $input.val(title);
            closeList();
            HTMLFormElement.prototype.submit.call($form[0]);
        };

        $input.on('input', renderList);

        $input.on('keydown', function (event) {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                if ($list.prop('hidden')) {
                    renderList();
                }
                setActive(activeIndex + 1);
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                setActive(activeIndex - 1);
            } else if (event.key === 'Enter' && activeIndex >= 0) {
                event.preventDefault();
                chooseOption($list.find('li.option').eq(activeIndex).data('title'));
            } else if (event.key === 'Escape') {
                closeList();
            }
        });

        $list.on('mousedown', 'li.option', function (event) {
            event.preventDefault();
            chooseOption($(this).data('title'));
        });

        $(document).on('click', function (event) {
            if (!$form.is(event.target) && $form.has(event.target).length === 0) {
                closeList();
            }
        });
    });

});
