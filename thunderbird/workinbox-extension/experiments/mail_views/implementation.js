var mailViews = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
    const VIEW_NAME = "WIB 未着眼";

    function createSearchTerm(searchSession, attrib, op, configureValue) {
      const term = searchSession.createTerm();
      term.booleanAnd = true;
      term.attrib = attrib;
      term.op = op;
      const value = term.value;
      value.attrib = attrib;
      configureValue(value);
      term.value = value;
      return term;
    }

    function createUnattendedView(mailViewList) {
      const searchSession = Cc["@mozilla.org/messenger/searchSession;1"].createInstance(
        Ci.nsIMsgSearchSession,
      );
      const view = mailViewList.createMailView();
      view.mailViewName = VIEW_NAME;

      view.appendTerm(
        createSearchTerm(
          searchSession,
          Ci.nsMsgSearchAttrib.MsgStatus,
          Ci.nsMsgSearchOp.Isnt,
          (value) => {
            value.status = Ci.nsMsgMessageFlags.Marked;
          },
        ),
      );
      for (const keyword of ["wib-bulk", "wib-batch"]) {
        view.appendTerm(
          createSearchTerm(
            searchSession,
            Ci.nsMsgSearchAttrib.Keywords,
            Ci.nsMsgSearchOp.DoesntContain,
            (value) => {
              value.str = keyword;
            },
          ),
        );
      }

      mailViewList.addMailView(view);
      mailViewList.save();
      return view;
    }

    function findOrCreateUnattendedView() {
      const mailViewList = Cc["@mozilla.org/messenger/mailviewlist;1"].getService(
        Ci.nsIMsgMailViewList,
      );
      for (let index = 0; index < mailViewList.mailViewCount; index += 1) {
        const view = mailViewList.getMailViewAt(index);
        if (view.mailViewName === VIEW_NAME) {
          return { view, created: false };
        }
      }
      return { view: createUnattendedView(mailViewList), created: true };
    }

    function resolveThreePaneWindow(tabId) {
      const wrapper = context.extension.tabManager.get(tabId);
      if (!wrapper) {
        throw new Error(`Thunderbird tab not found: ${tabId}`);
      }
      const nativeTab = wrapper.nativeTab;
      const browser = wrapper.browser || nativeTab?.chromeBrowser || nativeTab?.browser;
      const contentWindow = browser?.contentWindow;
      if (!contentWindow?.gViewWrapper) {
        throw new Error(`Thunderbird three-pane view not found for tab: ${tabId}`);
      }
      return contentWindow;
    }

    return {
      mailViews: {
        async ensureUnattendedView(tabId) {
          const { created } = findOrCreateUnattendedView();
          const threePaneWindow = resolveThreePaneWindow(tabId);
          // Thunderbird 153's DBViewWrapper accepts the custom mail-view name
          // as the first argument. Passing 0 selects the built-in "all mail"
          // view and ignores the custom terms.
          threePaneWindow.gViewWrapper.setMailView(VIEW_NAME, null, true);
          return {
            name: VIEW_NAME,
            created,
            applied: true,
          };
        },

        async resetView(tabId) {
          const threePaneWindow = resolveThreePaneWindow(tabId);
          // 0 is Thunderbird's built-in "all mail" view. -1 has no view
          // definition and fails when Thunderbird tries to build its terms.
          threePaneWindow.gViewWrapper.setMailView(0, null, true);
        },
      },
    };
  }
};
