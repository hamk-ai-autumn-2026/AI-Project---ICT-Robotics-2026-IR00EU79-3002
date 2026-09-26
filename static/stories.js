(function () {
  const form = document.querySelector("#story-form");
  const button = document.querySelector("#submit-button");
  const errorBox = document.querySelector("#form-error");
  const success = document.querySelector("#success");
  const reset = document.querySelector("#reset-button");
  const newBook = document.querySelector("#new-book-button");
  const generating = document.querySelector("#generating");
  const storybook = document.querySelector("#storybook");
  const pagesContainer = document.querySelector("#storybook-pages");
  const reader = document.querySelector("#book-reader");
  const publishConsent = document.querySelector("#publish-consent");
  const publishButton = document.querySelector("#publish-button");
  const publishStatus = document.querySelector("#publish-status");
  const publicBookLink = document.querySelector("#public-book-link");
  const downloadStatus = document.querySelector("#download-status");
  const publishConsentLabel = document.querySelector("#publish-consent-label");
  const readerGenerationStatus = document.querySelector("#reader-generation-status");
  let currentStory = null;
  let publishToken = "";
  let isPublic = false;
  let activeGenerationRequest = 0;
  let renderedSnapshot = "";
  let renderedStoryId = null;

  function csrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
  }

  function clearErrors() {
    errorBox.hidden = true;
    errorBox.textContent = "";
    document.querySelectorAll(".field-error").forEach((node) => (node.textContent = ""));
  }

  function renderStorybook(story) {
    const pages = story.pages || [];
    const isNewStory = renderedStoryId !== story.id;
    const snapshot = `${story.status}|${pages.map((page) => `${page.id}:${page.asset ? page.asset.url : ""}`).join("|")}`;
    currentStory = story;
    document.querySelector("#storybook-title").textContent = story.title || `${story.childName}'s story`;
    document.querySelector("#reader-byline").textContent = `A story made especially for ${story.childName}`;
    if (story.status === "FAILED") {
      readerGenerationStatus.textContent = story.errorMessage || "Story generation stopped. You can still read any pages that were completed.";
      readerGenerationStatus.hidden = false;
    } else if (story.status === "COMPLETE") {
      readerGenerationStatus.textContent = "Your storybook is ready.";
      readerGenerationStatus.hidden = true;
    } else {
      const illustrationsReady = pages.filter((page) => page.asset && page.asset.url).length;
      readerGenerationStatus.textContent = pages.length
        ? `Your story is ready. Painting illustrations: ${illustrationsReady} of ${pages.length} pages.`
        : "Writing your story. Pages will appear here as soon as the story is ready.";
      readerGenerationStatus.hidden = false;
    }

    if (pages.length === 0) {
      storybook.hidden = true;
      return;
    }

    const downloadLink = document.querySelector("#download-link");
    downloadLink.href = "#";
    downloadLink.hidden = story.status !== "COMPLETE";
    downloadStatus.textContent = "";
    if (snapshot !== renderedSnapshot) {
      pagesContainer.innerHTML = "";
      pages.forEach((page) => {
        const pageEl = document.createElement("article");
        pageEl.className = "storybook-page";
        const img = document.createElement("img");
        img.alt = `Illustration for page ${page.pageNumber}`;
        img.loading = "lazy";
        if (page.asset && page.asset.url) {
          img.src = page.asset.url;
        } else {
          img.classList.add("placeholder");
        }
        const badge = document.createElement("span");
        badge.className = "page-badge";
        badge.textContent = `Page ${page.pageNumber}`;
        const text = document.createElement("p");
        text.textContent = page.text || page.summary;
        pageEl.appendChild(img);
        pageEl.appendChild(badge);
        pageEl.appendChild(text);
        pagesContainer.appendChild(pageEl);
      });
      if (reader.updateProgressHandler) {
        reader.removeEventListener("bookpagechange", reader.updateProgressHandler);
      }
      reader.updateProgressHandler = updateReaderProgress;
      reader.addEventListener("bookpagechange", reader.updateProgressHandler);
      window.initializeBookReader(reader, pages);
      renderedSnapshot = snapshot;
    }
    updateReaderProgress();
    if (isNewStory) {
      pagesContainer.hidden = true;
      const pagesToggle = document.querySelector("#toggle-pages");
      pagesToggle.setAttribute("aria-expanded", "false");
      pagesToggle.textContent = "View all pages";
      publishConsent.checked = false;
      publishStatus.textContent = "";
      publicBookLink.hidden = true;
      downloadStatus.textContent = "";
      renderedSnapshot = snapshot;
      isPublic = Boolean(story.isPublic);
    }
    publishConsent.disabled = story.status !== "COMPLETE";
    publishConsentLabel.hidden = isPublic;
    publishButton.textContent = isPublic ? "Remove from community library" : "Add to community library";
    publishButton.disabled = story.status !== "COMPLETE" || (!isPublic && !publishConsent.checked);
    publicBookLink.href = `/library/${story.id}/`;
    publicBookLink.hidden = !isPublic;
    success.hidden = true;
    storybook.hidden = false;
    if (isNewStory) {
      renderedStoryId = story.id;
      storybook.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function updateReaderProgress() {
    if (!currentStory) return;
    const counter = reader.querySelector("[data-reader-counter]").textContent;
    document.querySelector("#reader-progress").textContent = `${counter} (${currentStory.pages.length} total)`;
  }

  async function updateLibraryVisibility() {
    if (!currentStory || !publishToken) return;
    const nextVisibility = !isPublic;
    publishButton.disabled = true;
    publishStatus.textContent = nextVisibility ? "Adding your book..." : "Removing your book...";
    try {
      const response = await fetch(`/api/stories/${currentStory.id}/publish/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          "X-Story-Token": publishToken,
        },
        body: JSON.stringify({ isPublic: nextVisibility }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Could not update library visibility");
      isPublic = body.story.isPublic;
      publishStatus.textContent = isPublic
        ? "Your book is now in the community library."
        : "Your book has been removed from the community library.";
      publishButton.textContent = isPublic ? "Remove from community library" : "Add to community library";
      publishConsentLabel.hidden = isPublic;
      publishConsent.checked = false;
      publishButton.disabled = !isPublic;
      publicBookLink.href = `/library/${currentStory.id}/`;
      publicBookLink.hidden = !isPublic;
    } catch (error) {
      publishStatus.textContent = error instanceof Error ? error.message : "Could not update library visibility";
      publishButton.disabled = isPublic ? false : !publishConsent.checked;
    }
  }

  async function pollForStoryUpdates(storyId, generationRequest) {
    while (generationRequest === activeGenerationRequest) {
      const response = await fetch(`/api/stories/${storyId}/`, {
        headers: { "X-Story-Token": publishToken },
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Could not check story progress");
      const story = body.story;
      renderStorybook(story);
      if (story.status === "COMPLETE") return;
      if (story.status === "FAILED") {
        if (!story.pages.length) {
          document.querySelector("#success-title").textContent = "Story generation stopped";
          document.querySelector("#success-copy").textContent = story.errorMessage || "Please try creating the story again.";
          success.hidden = false;
        }
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
  }

  async function generateStory(storyId, generationRequest) {
    generating.hidden = false;
    try {
      const response = await fetch(`/api/stories/${storyId}/generate/`, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-Story-Token": publishToken },
      });
      const body = await response.json();
      if (!response.ok) {
        errorBox.textContent =
          (body.story && body.story.errorMessage) || body.detail || "Could not generate the storybook";
        errorBox.hidden = false;
        return;
      }
      renderStorybook(body.story);
      if (body.story.status !== "COMPLETE" && body.story.status !== "FAILED") {
        await pollForStoryUpdates(storyId, generationRequest);
      }
    } catch (error) {
      errorBox.textContent = error instanceof Error
        ? error.message
        : "The server could not be reached while generating the storybook.";
      errorBox.hidden = false;
    } finally {
      generating.hidden = true;
    }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    clearErrors();
    button.disabled = true;
    button.textContent = "Saving...";
    const payload = Object.fromEntries(new FormData(form).entries());
    delete payload.csrfmiddlewaretoken;
    try {
      const response = await fetch("/api/stories/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) {
        errorBox.textContent = body.error || "Could not create story";
        errorBox.hidden = false;
        Object.entries(body.fields || {}).forEach(([field, messages]) => {
          const target = document.querySelector(`[data-error="${field}"]`);
          if (target) target.textContent = messages.map((message) => message.message).join(", ");
        });
        return;
      }
      form.hidden = true;
      publishToken = body.publishToken;
      const generationRequest = ++activeGenerationRequest;
      document.querySelector("#success-copy").textContent =
        `"${body.story.childName}"'s storybook is being created...`;
      success.hidden = false;
      await generateStory(body.story.id, generationRequest);
    } catch (error) {
      errorBox.textContent = "The server could not be reached. Please try again.";
      errorBox.hidden = false;
    } finally {
      button.disabled = false;
      button.textContent = "Create storybook";
    }
  });

  reset.addEventListener("click", function () {
    activeGenerationRequest += 1;
    form.reset();
    form.hidden = false;
    success.hidden = true;
    storybook.hidden = true;
    pagesContainer.innerHTML = "";
    pagesContainer.hidden = true;
    document.querySelector("#toggle-pages").setAttribute("aria-expanded", "false");
    document.querySelector("#toggle-pages").textContent = "View all pages";
    currentStory = null;
    renderedSnapshot = "";
    renderedStoryId = null;
    publishToken = "";
    publishStatus.textContent = "";
    clearErrors();
  });

  newBook.addEventListener("click", function () {
    reset.click();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  publishConsent.addEventListener("change", function () {
    publishButton.disabled = !publishConsent.checked;
  });
  publishButton.addEventListener("click", updateLibraryVisibility);

  document.querySelector("#download-link").addEventListener("click", async function (event) {
    event.preventDefault();
    if (!currentStory || !publishToken) return;
    const link = event.currentTarget;
    link.setAttribute("aria-busy", "true");
    downloadStatus.textContent = "Preparing your book...";
    try {
      const response = await fetch(`/api/stories/${currentStory.id}/download/`, {
        headers: { "X-Story-Token": publishToken },
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.error || "Could not download the book");
      }
      const blobUrl = URL.createObjectURL(await response.blob());
      const temporaryLink = document.createElement("a");
      temporaryLink.href = blobUrl;
      temporaryLink.download = `${currentStory.childName.replace(/[^A-Za-z0-9_-]+/g, "-")}-storybook.pdf`;
      document.body.appendChild(temporaryLink);
      temporaryLink.click();
      temporaryLink.remove();
      requestAnimationFrame(() => URL.revokeObjectURL(blobUrl));
      downloadStatus.textContent = "Your book download has started.";
    } catch (error) {
      downloadStatus.textContent = error instanceof Error ? error.message : "Could not download the book";
    } finally {
      link.removeAttribute("aria-busy");
    }
  });

  document.querySelector("#toggle-pages").addEventListener("click", function (event) {
    const expanded = pagesContainer.hidden;
    pagesContainer.hidden = !expanded;
    event.currentTarget.setAttribute("aria-expanded", String(expanded));
    event.currentTarget.textContent = expanded ? "Hide all pages" : "View all pages";
  });
})();
