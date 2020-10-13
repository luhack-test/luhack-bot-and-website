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

    const selectOtherElements = document.querySelectorAll("[data-select-other-content]");

    selectOtherElements.forEach(e => {
        console.log(e);

        e.addEventListener("click", _evt => {
            window.getSelection().selectAllChildren(document.getElementById(e.dataset.selectOtherContent));
        })
    })
});
