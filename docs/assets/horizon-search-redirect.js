// The header search box is Material's built-in (lunr), whose index
// deliberately excludes the digest pages — so it finds nothing the reader
// actually wants. Enter therefore goes to the Elasticsearch search page;
// the lunr dropdown is hidden by CSS.
document.addEventListener("DOMContentLoaded", function () {
  var input = document.querySelector(".md-search__input");
  if (!input) return;
  input.setAttribute("placeholder", "Поиск по архиву");
  input.addEventListener("keydown", function (event) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    var q = input.value.trim();
    if (q) window.location.href = "/search/?q=" + encodeURIComponent(q);
  });
});
