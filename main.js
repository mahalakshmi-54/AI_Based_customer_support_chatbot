// Global static/js/main.js for general-purpose utility scripts

console.log("SupportAI main.js loaded successfully.");

// Double-confirmation utilities or styling handlers
document.addEventListener("DOMContentLoaded", () => {
    // Enable tooltip utility of Bootstrap if active
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (typeof bootstrap !== 'undefined') {
        const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }
});
