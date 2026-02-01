const columnDefinitions = [
    { data: 'id', visible: false },

    {
        data: 'name',
        title: 'Icon',
        orderable: false,
        searchable: false,
        render: (data) => {
            if (!data) return '';
            let fileName = data.toLocaleString();
            const manualReplacements = {
                "combat bracelet(4)": "Combat_bracelet",
                "combat bracelet(3)": "Combat_bracelet",
                "combat bracelet(2)": "Combat_bracelet",
                "combat bracelet(1)": "Combat_bracelet",
                "abyssal bracelet(5)": "Abyssal_bracelet",
                "abyssal bracelet(4)": "Abyssal_bracelet",
                "abyssal bracelet(3)": "Abyssal_bracelet",
                "abyssal bracelet(2)": "Abyssal_bracelet",
                "abyssal bracelet(1)": "Abyssal_bracelet",
                "amulet of glory(4)": "Amulet_of_glory",
                "amulet of glory(6)": "Amulet_of_glory",
                "games necklace(8)": "Games_necklace",
                "ring of dueling(8)": "Ring_of_dueling",
                "atlatl dart": "Atlatl_dart_5",
                "antipoison mix": "Antipoison_mix(2)",
                "battlemage potion": "Battlemage_potion(4)",
                "infernal plate": "Infernal_plate_7",
                "oathplate shards": "Oathplate_shards_20",
                "ruby harvest mix": "Ruby_harvest_mix_(2)",
                "ancient mix": "Ancient_mix(2)",
                "goading potion": "Goading_potion(4)",
                "superantipoison": "Superantipoison(4)",
                "castle wars bracelet(3)": "Castle_wars_bracelet"
            };

            const lowerData = data.toLowerCase().trim();

            if (manualReplacements[lowerData]) {
                fileName = manualReplacements[lowerData];
            } else {
                fileName = data.trim().replace(/ /g, '_');
            }
            const finalUrl = encodeURIComponent(fileName);

            return `<img
                class="item-icon-render"
                src="https://oldschool.runescape.wiki/images/${finalUrl}_detail.png"
                loading="lazy"
                alt="${data}"
                onerror="this.style.visibility='hidden';">`;
        }
    },

    {
        data: 'name',
        title: 'Name',
        className: 'fw-bold',
        render: (data, type, row) => {
            if (type !== 'display') return data.toLocaleString();
            return `<a href="/item/${row.id}" class="item-link" target="_blank" rel="noopener noreferrer">${data}</a>`;
        }
    },

    {
        data: 'buy_limit',
        visible: true,
        render: (d, type) => (type === 'display' && d ? d.toLocaleString() : d || 0)
    },

    {
        data: 'highalch',
        visible: true,
        render: (d, type) => (type === 'display' && d ? d.toLocaleString() : d || 0)
    },

    {
        data: 'lowalch',
        visible: false,
        render: (d, type) => (type === 'display' && d ? d.toLocaleString() : d || 0)
    },

    {
        data: 'nature_price',
        visible: false,
        render: (d, type) => (type === 'display' && d ? d.toLocaleString() : d || 0)
    },

    {
        data: 'insta_buy_price',
        visible: true,
        render: (d, type) => (type === 'display' && d ? d.toLocaleString() : d || 0)
    },

    {
        data: 'slow_buy_price',
        visible: false,
        render: (d, type) => (type === 'display' && d ? d.toLocaleString() : d || 0)
    },

    {
        data: 'selling_volume',
        visible: true,
        render: (d, type) => (type === 'display' && d ? d.toLocaleString() : d || 0)
    },

    {
        data: 'profit_per_high_alch_instant',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'profit_per_high_alch_slow',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'estimated_hourly_profit_high',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'realistic_hourly_profit_high',
        visible: true,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'potential_total_profit_instant',
        title: 'Total Profit High (Instant)',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'potential_total_profit_slow',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'profit_per_low_alch_instant',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'profit_per_low_alch_slow',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'estimated_hourly_profit_low',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'realistic_hourly_profit_low',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'potential_total_profit_low_instant',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'potential_total_profit_low_slow',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },

    {
        data: 'roi_high_alch_percent',
        visible: true,
        render: (d, type) => formatROI(d, type)
    },

    {
        data: 'roi_low_alch_percent',
        visible: false,
        render: (d, type) => formatROI(d, type)
    },

    {
        data: 'cost_to_buy_limit_instant',
        visible: false,
        render: (d, type) => (type === 'display' && d ? d.toLocaleString() : d || 0)
    },

    {
        data: 'cost_to_buy_limit_slow',
        visible: false,
        render: (d, type) => (type === 'display' && d ? d.toLocaleString() : d || 0)
    },

    {
        data: 'hours_to_process_limit',
        visible: false,
        render: (d, type) => {
            const val = d || 0;
            return type === 'display' ? val.toFixed(2) : val;
        }
    },

    {
        data: 'updated_at',
        visible: true,
        render: (d, type) => {
            if (!d) return type === 'display' ? '---' : 0;
            if (type === 'sort') return new Date(d).getTime();

            const utc = d.endsWith('Z') ? d : `${d}Z`;
            return new Date(utc).toLocaleTimeString();
        }
    }
];


function formatROI(value, type) {
    const v = value || 0;
    if (type !== 'display') {
        return v;
    }
    const color = v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--text-muted)';
    return `<span style="color:${color}; font-weight:500;">${v.toFixed(2)}%</span>`;
}

function formatProfit(value, type) {
    const v = value || 0;
    if (type !== 'display') {
        return v;
    }
    const color = v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--text-muted)';
    return `<span style="color:${color}; font-weight:500;">${v.toLocaleString()}</span>`;
}


DataTable.feature.register('membersSelect', function (settings, opts) {
    const savedValue = localStorage.getItem('alchemy_members_filter') || "";
    const $container = $('<div class="members-filter-wrapper"></div>');
    const $select = $(`
        <select id="membersFilter" class="form-select form-select-sm members-dropdown">
            <option value="" ${savedValue === "" ? 'selected' : ''}>All Types (P2P/F2P)</option>
            <option value="true" ${savedValue === "true" ? 'selected' : ''}>Members Only</option>
            <option value="false" ${savedValue === "false" ? 'selected' : ''}>Free-to-play Only</option>
        </select>
    `);

    return $container.append($select)[0];
});


$.fn.dataTable.ext.search.push(function(settings, data, dataIndex) {
    if (settings.nTable.id !== 'alchemyTable') return true;

    const val = localStorage.getItem('alchemy_members_filter') || "";
    if (val === "") return true;

    const rowData = settings.oInstance.api().row(dataIndex).data();
    if (!rowData) return true;

    const isMembers = rowData.members;

    if (val === "true") return isMembers === true || isMembers === 1;
    if (val === "false") return isMembers === false || isMembers === 0;

    return true;
});

$(document).ready(() => {
    const table = $('#alchemyTable').DataTable({
        responsive: true,
        pageLength: 20,
        deferRender: true,
        // scroller: true,
        processing: true,
        columns: columnDefinitions,
        stateSave: true,
        columnControl: [
            {
                target: '_all',
                content: [
                    'searchDropdown',
                    [
                        'orderAsc',
                        'orderDesc',
                        'orderRemove',
                        'orderClear',
                        'orderAddAsc',
                        'orderAddDesc',
                        'spacer',
                        'colVisDropdown'
                    ],
                ]
            }
        ],
        columnDefs: [
            {
                targets: '_all',
                type: 'num',
                orderable: true
            },
            {
                targets: 1,
                orderable: false,
                searchable: false,
                className: 'cell-sticky-icon',
                width: '45px'
            },
            {
                targets: [2],
                type: 'string',
                className: 'fw-bold cell-sticky-name'
            },
            {
                target: -1,
                type: 'date'
            }
        ],

        language: {
            lengthMenu: "Show: _MENU_",
            search: "Search:",
            info: "Showing _START_ to _END_ of _TOTAL_ items",
            paginate: {
                first: "«",
                last: "»",
                next: "›",
                previous: "‹"
            }
        },

        layout: {
            topStart: [
                'search',
                'membersSelect'
            ],
            topEnd: {
                pageLength: {
                    menu: [ 5, 10, 25, 50, 100 ]
                }
            },
            bottomStart: 'info',
            bottomEnd: 'paging'
        },

        buttons: [
            {
            dom: {
                button: {
                    className: 'dt-button'
                }
            }
        },
        ],

    });

    $(document).on('change', '#membersFilter', function() {
        const val = $(this).val();
        localStorage.setItem('alchemy_members_filter', val);
        table.draw();
    });

    setupWebSocket(table);
});

function setupWebSocket(tableInstance) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/alchemy`;
    const socket = new WebSocket(wsUrl);
    const updateQueue = new Map();
    let flushScheduled = false;
    function scheduleFlush() {
        if (flushScheduled) return;
        flushScheduled = true;
        requestAnimationFrame(() => {
            flushScheduled = false;
            if (updateQueue.size === 0) return;
            updateQueue.forEach((msg, id) => {
                const row = tableInstance.row((idx, data) => data && data.id === id);
                if (row.any()) {
                    const oldData = row.data();

                    const changed =
                        oldData.insta_buy_price !== msg.insta_buy_price ||
                        oldData.slow_buy_price !== msg.slow_buy_price;

                    row.data(msg);

                    if (changed) {
                        const node = row.node();
                        if (node) {
                            node.classList.remove('row-updated');
                            void node.offsetWidth;
                            node.classList.add('row-updated');
                        }
                    }
                }

            });
            updateQueue.clear();
            tableInstance.rows().invalidate().draw(false);
        });

    }

    socket.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);

            if (message.type === 'snapshot') {
                const data = Array.isArray(message.data) ? message.data : [];
                const MAX = 10000;
                if (data.length > MAX) {
                    tableInstance.clear().rows.add(data.slice(0, MAX)).draw(false);
                } else {
                    tableInstance.clear().rows.add(data).draw(false);
                }
            } else if (message.type === 'alchemy_update') {
                if (!message.id) return;
                updateQueue.set(message.id, message);
                scheduleFlush();
            }
        } catch (err) {
            console.error("WS parse/error:", err);
        }
    };

    socket.onclose = () => {
        setTimeout(() => setupWebSocket(tableInstance), 2000);
    };

    socket.onerror = (e) => {
        console.error('WS erro:', e);
        socket.close();
    };
}
