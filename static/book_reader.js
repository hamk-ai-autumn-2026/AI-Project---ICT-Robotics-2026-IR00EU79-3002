(function () {
  function initializeBookReader(reader, pages) {
    if (!reader || !Array.isArray(pages) || pages.length === 0) return;
    const image = reader.querySelector("[data-reader-image]");
    const placeholder = reader.querySelector("[data-reader-placeholder]");
    const counter = reader.querySelector("[data-reader-counter]");
    const text = reader.querySelector("[data-reader-text]");
    const previous = reader.querySelector("[data-reader-previous]");
    const next = reader.querySelector("[data-reader-next]");
    let pageIndex = Math.min(Number(reader.dataset.pageIndex || 0), pages.length - 1);
    if (reader.bookReaderCleanup) reader.bookReaderCleanup();

    function showPage() {
      const page = pages[pageIndex];
      reader.dataset.pageIndex = String(pageIndex);
      const imageUrl = page.asset && page.asset.url;
      image.hidden = !imageUrl;
      placeholder.hidden = Boolean(imageUrl);
      image.alt = imageUrl ? `Illustration for page ${page.pageNumber}` : "Illustration unavailable";
      image.onerror = function () {
        image.hidden = true;
        placeholder.hidden = false;
      };
      if (imageUrl) image.src = imageUrl;
      counter.textContent = `Page ${pageIndex + 1} of ${pages.length}`;
      text.textContent = page.text || page.summary;
      previous.disabled = pageIndex === 0;
      next.disabled = pageIndex === pages.length - 1;
      reader.dispatchEvent(new CustomEvent("bookpagechange", {
        detail: { page: pageIndex + 1, total: pages.length },
      }));
    }

    const goToPreviousPage = function () {
      if (pageIndex > 0) pageIndex -= 1;
      showPage();
    };
    const goToNextPage = function () {
      if (pageIndex < pages.length - 1) pageIndex += 1;
      showPage();
    };
    const handleReaderKey = function (event) {
      if (event.key === "ArrowLeft" && pageIndex > 0) pageIndex -= 1;
      else if (event.key === "ArrowRight" && pageIndex < pages.length - 1) pageIndex += 1;
      else return;
      showPage();
    };
    previous.addEventListener("click", goToPreviousPage);
    next.addEventListener("click", goToNextPage);
    reader.tabIndex = 0;
    reader.addEventListener("keydown", handleReaderKey);
    reader.bookReaderCleanup = function () {
      previous.removeEventListener("click", goToPreviousPage);
      next.removeEventListener("click", goToNextPage);
      reader.removeEventListener("keydown", handleReaderKey);
    };
    showPage();
  }

  window.initializeBookReader = initializeBookReader;

  document.querySelectorAll(".public-book-reader[data-book-data-id]").forEach(function (reader) {
    const data = document.getElementById(reader.dataset.bookDataId);
    if (data) initializeBookReader(reader, JSON.parse(data.textContent));
  });
})();