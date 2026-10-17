(function () {
  const button = document.querySelector("#public-report-button");
  if (!button) return;
  button.addEventListener("click", async function () {
    const status = document.querySelector("#public-report-status");
    button.disabled = true;
    try {
      const response = await fetch(`/api/stories/${button.dataset.storyId}/report/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("#report-csrf-form [name=csrfmiddlewaretoken]").value,
        },
        body: JSON.stringify({
          reason: document.querySelector("#public-report-reason").value,
          details: document.querySelector("#public-report-details").value,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Could not send report.");
      status.textContent = body.message;
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : "Could not send report.";
      button.disabled = false;
    }
  });
})();
