(function () {
  const csrfToken = document.querySelector("#books-csrf-form [name=csrfmiddlewaretoken]").value;
  document.querySelectorAll("[data-delete-story]").forEach((button) => {
    button.addEventListener("click", async function () {
      if (!window.confirm("Delete this story and its private reference photo? This cannot be undone.")) return;
      button.disabled = true;
      const card = button.closest("[data-my-story]");
      const status = card.querySelector("[data-delete-status]");
      try {
        const response = await fetch(`/api/stories/${button.dataset.deleteStory}/delete/`, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken },
        });
        if (!response.ok) throw new Error("Could not delete this story.");
        card.remove();
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : "Could not delete this story.";
        button.disabled = false;
      }
    });
  });
})();
