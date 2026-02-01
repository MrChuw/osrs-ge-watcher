const columnDefinitions = [
    {
        data: 'item_id',
        visible: false
    },
    {
        data: 'name',
        title: 'Icon',
        visible: true,
        orderable: false,
        render: (data) => {
            if (!data) return '';
            const fileName = data.trim().replace(/ /g, '_');
            const finalUrl = encodeURIComponent(fileName);
            return `<img class="item-icon-render" src="https://oldschool.runescape.wiki/images/${finalUrl}_detail.png" loading="lazy" onerror="this.style.visibility='hidden';">`;
        },
        className: 'cell-sticky-icon',
        width: '45px'
    },
    {
        data: 'name',
        title: 'Name',
        visible: true,
        className: 'fw-bold cell-sticky-name',
        render: (data, type, row) => {
            if (type !== 'display') return data.toLocaleString();
            return `<a href="/item/${row.item_id}" class="item-link" target="_blank">${data}</a>`;
        }
    },
    {
        data: 'buy_limit',
        title: 'Limit',
        visible: true,
        render: (d, type) => (type === 'display' ? (d ? d.toLocaleString() : '0') : d)
    },
    {
        data: 'current_buy_price',
        title: 'Buy Price',
        visible: true,
        render: (d, type) => formatProfit(d, type)
    },
    {
        data: 'current_sell_price',
        title: 'Sell Price',
        visible: true,
        render: (d, type) => formatProfit(d, type)
    },
    {
        data: 'ge_tax',
        title: 'Tax',
        visible: false, // Pode deixar oculto por padrão
        render: (d, type) => (type === 'display' ? (d ? d.toLocaleString() : '0') : d)
    },
    {
        data: 'margin',
        title: 'Margin',
        visible: true,
        render: (d, type) => formatProfit(d, type)
    },
    {
        data: 'potential_profit',
        title: 'Potential Profit',
        visible: true,
        render: (d, type) => formatProfit(d, type)
    },
    {
        data: 'roi_margin_pct',
        title: 'ROI (Flip)',
        visible: true,
        render: (d, type) => formatROI(d, type)
    },
    {
        data: 'sell_volume',
        title: 'Sell Vol',
        visible: false,
        render: (d, type) => (type === 'display' ? (d ? d.toLocaleString() : '0') : d)
    },
    {
        data: 'buy_volume',
        title: 'Buy Vol',
        visible: false,
        render: (d, type) => (type === 'display' ? (d ? d.toLocaleString() : '0') : d)
    },
    {
        data: 'total_volume',
        title: 'Total Vol',
        visible: true,
        render: (d, type) => (type === 'display' ? (d ? d.toLocaleString() : '0') : d)
    },
    {
        data: 'alch_profit',
        title: 'Alch Profit',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },
    {
        data: 'roi_alch_pct',
        title: 'ROI (Alch)',
        visible: false,
        render: (d, type) => formatROI(d, type)
    },
    {
        data: 'change_pct',
        title: '24h Change',
        visible: false,
        render: (d, type) => formatROI(d, type)
    },
    {
        data: 'avg_high_24h',
        title: '24h Avg High',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },
    {
        data: 'highalch',
        title: 'High Alch',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },
    {
        data: 'lowalch',
        title: 'Low Alch',
        visible: false,
        render: (d, type) => formatProfit(d, type)
    },
    {
        data: 'max_buy_cost_instant',
        title: 'Cost (Instant)',
        visible: false,
        render: (d, type) => (type === 'display' ? `<span class="text-muted">${(d || 0).toLocaleString()}</span>` : d)
    },
    {
        data: 'max_buy_cost_slow',
        title: 'Cost (Slow)',
        visible: false,
        render: (d, type) => (type === 'display' ? `<span class="text-muted">${(d || 0).toLocaleString()}</span>` : d)
    },
    {
        data: 'value',
        title: 'Store Value',
        visible: false,
        render: (d, type) => (type === 'display' ? (d ? d.toLocaleString() : '0') : d)
    },
    {
        data: 'updated_at',
        title: 'Last Update',
        visible: true,
        render: (d, type) => {
            if (!d) return '---';
            const date = new Date(d);
            return type === 'display' ? date.toLocaleTimeString() : date.getTime();
        }
    }
];

function formatROI(value, type) {
    const v = value || 0;
    if (type !== 'display') return v;
    const color = v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--text-muted)';
    return `<span style="color:${color}; font-weight:500;">${v.toFixed(2)}%</span>`;
}

function formatProfit(value, type) {
    const v = value || 0;
    if (type !== 'display') return v;
    const color = v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--text-muted)';
    return `<span style="color:${color}; font-weight:600;">${v.toLocaleString()}</span>`;
}

DataTable.feature.register('membersSelect', function (settings, opts) {
    const savedValue = localStorage.getItem('alerts_members_filter') || "";
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
    if (settings.nTable.id !== 'alertsTable') return true;

    const rowData = settings.oInstance.api().row(dataIndex).data();
    if (!rowData) return true;

    if (rowData.item_id === 26247) return false;

    const val = localStorage.getItem('alerts_members_filter') || "";
    if (val === "") return true;

    const isMembers = rowData.members;
    if (val === "true") return isMembers === true || isMembers === 1;
    if (val === "false") return isMembers === false || isMembers === 0;

    return true;
});

$(document).ready(() => {
    const table = $('#alertsTable').DataTable({
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
                targets: '_all',
                type: 'num',
                orderable: true
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
        localStorage.setItem('alerts_members_filter', val);
        table.draw();
    });

    setupWebSocket(table);
});

function setupWebSocket(tableInstance) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/price_table`;
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
                const row = tableInstance.row((idx, data) => data && data.item_id == id);

                if (row.any()) {
                    const oldData = row.data();
                    const updateData = msg.data || msg;

                    const changed =
                        oldData.current_buy_price !== updateData.current_buy_price ||
                        oldData.current_sell_price !== updateData.current_sell_price;


                    if (changed) {
                        const newData = { ...oldData, ...updateData };

                        row.data(newData);

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
            const cleanData = (Array.isArray(message.data) ? message.data : [message.data])
                .filter(item => item.item_id != 26247);
            tableInstance.clear().rows.add(cleanData).draw();
            }
            else if (message.type === 'price_update' || message.item_id) {
                const update = message.data || message;
                if (update.item_id == 26247) return;
                updateQueue.set(update.item_id, update);
                scheduleFlush();
            }
        } catch (err) {
            console.error("WS Error:", err);
        }
    };

    socket.onclose = () => setTimeout(() => setupWebSocket(tableInstance), 2000);
}
