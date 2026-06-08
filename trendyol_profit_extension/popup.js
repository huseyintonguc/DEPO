// popup.js
document.addEventListener('DOMContentLoaded', () => {
    const inputs = document.querySelectorAll('input');

    function calculateProfit() {
        const price = parseFloat(document.getElementById('price').value) || 0;
        const cost = parseFloat(document.getElementById('cost').value) || 0;
        const commissionRate = parseFloat(document.getElementById('commission-rate').value) || 0;
        const taxRate = parseFloat(document.getElementById('tax-rate').value) || 0;
        const shipping = parseFloat(document.getElementById('shipping').value) || 0;

        const commissionCost = price * (commissionRate / 100);
        const taxCost = price - (price / (1 + (taxRate / 100)));
        const totalExpenses = cost + commissionCost + shipping + taxCost;

        const netProfit = price - totalExpenses;
        const profitMargin = price > 0 ? (netProfit / price) * 100 : 0;

        document.getElementById('commission-cost').innerText = commissionCost.toFixed(2) + ' ₺';
        document.getElementById('tax-cost').innerText = taxCost.toFixed(2) + ' ₺';

        const netElement = document.getElementById('profit-net');
        netElement.innerText = netProfit.toFixed(2) + ' ₺';

        if (netProfit < 0) {
            netElement.className = 'negative';
        } else {
            netElement.className = 'positive';
        }

        document.getElementById('profit-margin').innerText = 'Marj: %' + profitMargin.toFixed(2);
    }

    inputs.forEach(input => {
        input.addEventListener('input', calculateProfit);
    });
});