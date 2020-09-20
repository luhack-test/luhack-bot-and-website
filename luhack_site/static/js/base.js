document.addEventListener("DOMContentLoaded", () => {
    const confirmElements = document.querySelectorAll("[data-confirm]");

    confirmElements.forEach(e => {
        e.addEventListener("click", evt => {
            if (!confirm(e.dataset.confirm)) {
                evt.preventDefault();
            }

            return true;
        });
    });
});
