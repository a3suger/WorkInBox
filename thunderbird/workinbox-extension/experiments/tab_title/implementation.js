var tabTitle = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
    const titleObservers = new Map();

    context.callOnClose({
      close() {
        for (const observer of titleObservers.values()) {
          observer.disconnect();
        }
        titleObservers.clear();
      },
    });

    function resolveTabInfo(tabId) {
      const wrapper = context.extension.tabManager.get(tabId);
      if (!wrapper) {
        throw new Error(`Thunderbird tab not found: ${tabId}`);
      }

      const nativeTab = wrapper.nativeTab;
      const browser = wrapper.browser || nativeTab?.chromeBrowser || nativeTab?.browser;
      const win =
        browser?.ownerGlobal ||
        nativeTab?.tabNode?.ownerDocument?.defaultView ||
        nativeTab?.ownerGlobal;
      const tabmail = win?.document?.getElementById("tabmail");
      if (!tabmail) {
        throw new Error(`tabmail not found for Thunderbird tab: ${tabId}`);
      }

      const tabInfo = tabmail.tabInfo.find(
        (candidate) =>
          candidate === nativeTab ||
          candidate.chromeBrowser === browser ||
          candidate.browser === browser,
      );
      if (!tabInfo) {
        throw new Error(`tabInfo not found for Thunderbird tab: ${tabId}`);
      }

      const index = tabmail.tabInfo.indexOf(tabInfo);
      const tabNode = tabInfo.tabNode || tabmail.tabContainer?.allTabs?.[index];
      if (!tabNode) {
        throw new Error(`tab node not found for Thunderbird tab: ${tabId}`);
      }

      return { tabInfo, tabNode, win };
    }

    function applyTitle(tabInfo, tabNode, title) {
      tabInfo.title = title;
      tabNode.label = title;
      tabNode.setAttribute("label", title);
    }

    return {
      tabTitle: {
        async setTitle(tabId, title) {
          const requestedTitle = String(title || "").trim();
          if (!requestedTitle) {
            throw new Error("Tab title must not be empty.");
          }

          const { tabInfo, tabNode, win } = resolveTabInfo(tabId);
          titleObservers.get(tabId)?.disconnect();
          applyTitle(tabInfo, tabNode, requestedTitle);

          const observer = new win.MutationObserver(() => {
            const currentTitle = tabNode.label || tabNode.getAttribute("label") || "";
            if (currentTitle !== requestedTitle) {
              applyTitle(tabInfo, tabNode, requestedTitle);
            }
          });
          observer.observe(tabNode, {
            attributes: true,
            attributeFilter: ["label"],
          });
          titleObservers.set(tabId, observer);

          const appliedTitle = tabNode.label || tabNode.getAttribute("label") || "";
          return {
            requestedTitle,
            appliedTitle,
            applied: appliedTitle === requestedTitle,
          };
        },
      },
    };
  }
};
