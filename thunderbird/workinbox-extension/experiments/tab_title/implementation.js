var tabTitle = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
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

      return { tabInfo, tabNode };
    }

    return {
      tabTitle: {
        async setTitle(tabId, title) {
          const requestedTitle = String(title || "").trim();
          if (!requestedTitle) {
            throw new Error("Tab title must not be empty.");
          }

          const { tabInfo, tabNode } = resolveTabInfo(tabId);
          tabInfo.title = requestedTitle;
          tabNode.label = requestedTitle;
          tabNode.setAttribute("label", requestedTitle);

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
