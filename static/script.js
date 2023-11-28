document.addEventListener("DOMContentLoaded", function () {
    var closedWebsites = JSON.parse(localStorage.getItem("closedWebsites")) || [];

    window.closeWebsite = function (websiteName) {
        var item = document.querySelector('.website-item[data-website="' + websiteName + '"]');
        if (item) {
            item.style.display = 'none';

            closedWebsites = closedWebsites.filter(function (closed) {
                return closed !== websiteName;
            });

            localStorage.setItem("closedWebsites", JSON.stringify(closedWebsites));
        }
    };

    closedWebsites.forEach(function (websiteName) {
        var item = document.querySelector('.website-item[data-website="' + websiteName + '"]');
        if (item) {
            item.style.display = 'none';
        }
    });
});

setInterval(function() {
    location.reload();
}, 60000);
