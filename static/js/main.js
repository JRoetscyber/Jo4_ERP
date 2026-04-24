// static/js/main.js

// Helper function for Chart.js styling - LIGHT THEME
const getChartOptions = (yLabel) => ({
    responsive: true,
    maintainAspectRatio: false,
    scales: {
        x: {
            ticks: { color: '#3a435b' },
            grid: { color: 'rgba(58, 67, 91, 0.1)' }
        },
        y: {
            ticks: { color: '#3a435b' },
            grid: { color: 'rgba(58, 67, 91, 0.1)' },
            title: {
                display: true,
                text: yLabel,
                color: '#0d134f',
                font: { weight: 'bold' }
            }
        }
    },
    plugins: {
        legend: {
            labels: { color: '#3a435b' }
        }
    }
});

const getCsrfToken = () => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
};


document.addEventListener('DOMContentLoaded', () => {

    // --- KPI Fetching ---
    fetch('/api/dashboard_kpis')
        .then(response => response.json())
        .then(data => {
            if (data.error) return;
            
            // Dashboard & Analytics shared KPIs
            const updateText = (id, val) => {
                const el = document.getElementById(id);
                if (el) el.textContent = val;
            };

            updateText('kpi-total-revenue', data.total_revenue);
            updateText('kpi-total-items-sold', data.total_items_sold);
            updateText('kpi-best-seller', data.best_selling_product);
            updateText('kpi-avg-ticket', data.avg_ticket_value);
            updateText('kpi-margin', data.profit_margin);
            updateText('kpi-profit', data.gross_profit);
            updateText('kpi-gross-profit', data.gross_profit); // For dashboard if present
            updateText('kpi-profit-margin', data.profit_margin); // For dashboard if present
            
            const lowStockDiv = document.getElementById('kpi-low-stock');
            if (lowStockDiv) {
                if (data.low_stock_ingredients && data.low_stock_ingredients.length > 0) {
                    let html = '';
                    data.low_stock_ingredients.forEach(item => {
                        html += `<p><strong>${item.name}:</strong> ${item.stock} ${item.unit}</p>`;
                    });
                    lowStockDiv.innerHTML = html;
                } else {
                    lowStockDiv.innerHTML = '<p>All stock healthy.</p>';
                }
            }
        });

    // --- Chart: Revenue vs Cost Trend ---
    const salesTrendChartEl = document.getElementById('salesTrendChart');
    if (salesTrendChartEl) {
        fetch('/api/sales_trend')
            .then(response => response.json())
            .then(data => {
                new Chart(salesTrendChartEl, {
                    type: 'line',
                    data: {
                        labels: data.labels,
                        datasets: [
                            {
                                label: 'Revenue',
                                data: data.revenue,
                                borderColor: '#ff562a',
                                backgroundColor: 'rgba(255, 86, 42, 0.1)',
                                fill: true,
                                tension: 0.2
                            },
                            {
                                label: 'Cost of Goods',
                                data: data.cost,
                                borderColor: '#0d134f',
                                backgroundColor: 'rgba(13, 19, 79, 0.1)',
                                fill: true,
                                tension: 0.2
                            }
                        ]
                    },
                    options: getChartOptions('Value')
                });
            });
    }

    // --- Chart: Product Profitability ---
    const productProfitChartEl = document.getElementById('productProfitChart');
    if (productProfitChartEl) {
        fetch('/api/product_profitability')
            .then(response => response.json())
            .then(data => {
                new Chart(productProfitChartEl, {
                    type: 'bar',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            label: 'Total Profit',
                            data: data.values,
                            backgroundColor: '#2dfa7e'
                        }]
                    },
                    options: getChartOptions('Profit')
                });
            });
    }

    // --- Chart: Advanced Analytics (Peak Hours & Weekdays) ---
    const peakHoursChartEl = document.getElementById('peakHoursChart');
    if (peakHoursChartEl) {
        fetch('/api/advanced_analytics')
            .then(r => r.json())
            .then(data => {
                new Chart(peakHoursChartEl, {
                    type: 'line',
                    data: {
                        labels: data.peak_hours.labels,
                        datasets: [{
                            label: 'Items Sold',
                            data: data.peak_hours.values,
                            borderColor: '#0d134f',
                            backgroundColor: 'rgba(13, 19, 79, 0.1)',
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: getChartOptions('Items')
                });

                const weekdayChartEl = document.getElementById('weekdayChart');
                if (weekdayChartEl) {
                    new Chart(weekdayChartEl, {
                        type: 'bar',
                        data: {
                            labels: data.weekdays.labels,
                            datasets: [{
                                label: 'Items Sold',
                                data: data.weekdays.values,
                                backgroundColor: '#ff562a'
                            }]
                        },
                        options: getChartOptions('Items')
                    });
                }
            });
    }
    
    // --- Chart: Production Capacity ---
    const prodCapacityChartEl = document.getElementById('productionCapacityChart');
    if(prodCapacityChartEl) {
        fetch('/api/production_capacity')
            .then(response => response.json())
            .then(data => {
                new Chart(prodCapacityChartEl, {
                    type: 'bar',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            label: 'Maximum Units',
                            data: data.values,
                            backgroundColor: ['#ff562a', '#2dfa7e', '#0d134f', '#3a435b', '#d5d5d8'],
                        }]
                    },
                    options: getChartOptions('Units')
                });
            });
    }

    // --- AI Predictions ---
    const predictionsDiv = document.getElementById('predictions');
    let predictionData = null;

    window.renderPredictions = function(timeframe) {
        if (!predictionData) return;
        const btnWeek = document.getElementById('btn-week');
        const btnMonth = document.getElementById('btn-month');
        if (btnWeek && btnMonth) {
            btnWeek.style.background = timeframe === 'week' ? '#ff562a' : '#d5d5d8';
            btnWeek.style.color = timeframe === 'week' ? 'white' : '#3a435b';
            btnMonth.style.background = timeframe === 'month' ? '#ff562a' : '#d5d5d8';
            btnMonth.style.color = timeframe === 'month' ? 'white' : '#3a435b';
        }

        const data = predictionData[timeframe];
        let html = '<div class="prediction-panels">';
        html += '<div class="prediction-panel"><h5>Products to Prepare</h5>';
        let productsFound = false;
        for (const [product, qty] of Object.entries(data.product_predictions)) {
            if (qty > 0) {
                html += `<p class="prediction-item"><strong>${product}:</strong> ${qty} units</p>`;
                productsFound = true;
            }
        }
        if (!productsFound) html += '<p>Not enough data yet.</p>';
        html += '</div><div class="prediction-panel"><h5>Ingredients Required</h5>';
        let ingredientsFound = false;
        for (const [ingredient, details] of Object.entries(data.ingredient_requirements)) {
            html += `<p class="prediction-item"><strong>${ingredient}:</strong> ${details.quantity} ${details.unit}</p>`;
            ingredientsFound = true;
        }
        if (!ingredientsFound) html += '<p>Set up recipes to see ingredient needs.</p>';
        html += '</div></div>';
        predictionsDiv.innerHTML = html;
    };

    if (predictionsDiv) {
        fetch('/api/predict')
            .then(r => r.json())
            .then(data => {
                if (data.error) { predictionsDiv.innerHTML = `<p>${data.error}</p>`; }
                else { predictionData = data; window.renderPredictions('week'); }
            });
    }

    // --- Mobile Menu Toggle ---
    window.toggleSidebar = function() {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        if (!sidebar) return;

        const shouldOpen = arguments.length === 0 ? !sidebar.classList.contains('active') : Boolean(arguments[0]);
        sidebar.classList.toggle('active', shouldOpen);
        if (overlay) overlay.classList.toggle('active', shouldOpen);
    };

    document.querySelectorAll('.sidebar a').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 992) {
                window.toggleSidebar(false);
            }
        });
    });
});
