(() => {
  const draftId = new URLSearchParams(window.location.search).get("draft_id");
  if (!draftId) return;

  const notify = (host, message, error = false) => {
    let note = host.querySelector(".ai-field-note");
    if (!note) {
      note = document.createElement("small");
      note.className = "ai-field-note";
      host.append(note);
    }
    note.textContent = message;
    note.style.color = error ? "#b42318" : "#027a48";
  };

  const setReactValue = (element, value) => {
    const descriptor = Object.getOwnPropertyDescriptor(
      element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,
      "value",
    );
    descriptor?.set?.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  };

  const categoryId = async () => {
    const response = await fetch(`/api/drafts/${draftId}/cbt-listing-config?optional=true`);
    if (!response.ok) throw new Error("无法读取当前商品的 CBT 分类");
    const config = await response.json();
    if (!config?.category_id) throw new Error("当前商品还没有可用的 CBT 分类，先使用系统的自动分类即可");
    return config.category_id;
  };

  const generate = async (field, input, host, button) => {
    button.disabled = true;
    button.textContent = "生成中…";
    notify(host, "正在生成…");
    try {
      const category_id = await categoryId();
      const response = await fetch(`/api/drafts/${draftId}/generate-content`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_id, language: "en", fields: [field] }),
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setReactValue(input, field === "title" ? data.title : data.description);
      notify(host, field === "title" ? "AI 标题已生成并回填。" : "AI 描述已生成并回填。");
    } catch (error) {
      notify(host, error instanceof Error ? error.message : "AI 生成失败，请稍后重试。", true);
    } finally {
      button.disabled = false;
      button.textContent = "AI";
    }
  };

  const addButton = (host, input, field) => {
    if (host.querySelector(`[data-ai-field="${field}"]`)) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-button ai-field-button";
    button.dataset.aiField = field;
    button.textContent = "AI";
    button.title = field === "title" ? "只生成英文标题，不改描述" : "只生成英文描述，不改标题";
    button.addEventListener("click", () => void generate(field, input, host, button));
    if (field === "title") {
      host.append(button);
    } else {
      const header = document.createElement("div");
      header.className = "ai-description-action";
      header.append(button);
      host.insertBefore(header, input);
    }
  };

  const mount = () => {
    const titleBox = document.querySelector(".wf-section#basic .wf-title-input");
    const titleInput = titleBox?.querySelector("input");
    if (titleBox && titleInput) addButton(titleBox, titleInput, "title");

    const description = document.querySelector(".wf-section#description textarea");
    const descriptionHost = description?.closest("label") || description?.parentElement;
    if (description && descriptionHost) addButton(descriptionHost, description, "description");
  };

  const observer = new MutationObserver(mount);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  mount();
})();