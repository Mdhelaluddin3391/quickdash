// static/assets/js/utils/formatters.js

const Formatters = {
    /**
     * Format Number to INR Currency (e.g., ₹1,200.00)
     */
    toCurrency: (amount) => {
        if (amount === null || amount === undefined) return '₹0.00';
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        }).format(amount);
    },

    /**
     * Format Date (e.g., "12 Oct, 2025")
     */
    toDate: (dateString) => {
        if (!dateString) return '';
        const options = { year: 'numeric', month: 'short', day: 'numeric' };
        return new Date(dateString).toLocaleDateString('en-IN', options);
    },

    /**
     * Format Time (e.g., "10:30 AM")
     */
    toTime: (dateString) => {
        if (!dateString) return '';
        const options = { hour: '2-digit', minute: '2-digit', hour12: true };
        return new Date(dateString).toLocaleTimeString('en-IN', options);
    },

    /**
     * Format DateTime (e.g., "12 Oct, 10:30 AM")
     */
    toDateTime: (dateString) => {
        if (!dateString) return '';
        return `${Formatters.toDate(dateString)}, ${Formatters.toTime(dateString)}`;
    },

    /**
     * Truncate Text (e.g., "Product Name..." if too long)
     */
    truncate: (str, length = 20) => {
        if (!str) return '';
        if (str.length <= length) return str;
        return str.substring(0, length) + '...';
    }
};