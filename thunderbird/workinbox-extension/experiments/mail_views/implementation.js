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

    function unattendedViewName(lookbackDays) {
      return lookbackDays ? `${VIEW_NAME}（直近${lookbackDays}日）` : VIEW_NAME;
    }

    function createUnattendedView(mailViewList, name, lookbackDays) {
      const searchSession = Cc["@mozilla.org/messenger/searchSession;1"].createInstance(
        Ci.nsIMsgSearchSession,
      );
      const view = mailViewList.createMailView();
      view.mailViewName = name;

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
      if (lookbackDays) {
        view.appendTerm(
          createSearchTerm(
            searchSession,
            Ci.nsMsgSearchAttrib.AgeInDays,
            Ci.nsMsgSearchOp.IsLessThan,
            (value) => {
              value.age = lookbackDays;
            },
          ),
        );
      }

      mailViewList.addMailView(view);
      mailViewList.save();
      return view;
    }

    function findOrCreateUnattendedView(lookbackDays) {
      const mailViewList = Cc["@mozilla.org/messenger/mailviewlist;1"].getService(
        Ci.nsIMsgMailViewList,
      );
      const name = unattendedViewName(lookbackDays);
      for (let index = 0; index < mailViewList.mailViewCount; index += 1) {
        const view = mailViewList.getMailViewAt(index);
        if (view.mailViewName === name) {
          return { view, name, created: false };
        }
      }
      return {
        view: createUnattendedView(mailViewList, name, lookbackDays),
        name,
        created: true,
      };
    }

    function workflowViewName(label) {
      return `WIB ${label}（未処理）`;
    }

    function findOrCreateBulkArchiveView() {
      const mailViewList = Cc["@mozilla.org/messenger/mailviewlist;1"].getService(
        Ci.nsIMsgMailViewList,
      );
      const name = "WIB 整理済み・アーカイブ待ち";
      for (let index = 0; index < mailViewList.mailViewCount; index += 1) {
        const existing = mailViewList.getMailViewAt(index);
        if (existing.mailViewName === name) {
          return { name, created: false };
        }
      }

      const searchSession = Cc["@mozilla.org/messenger/searchSession;1"].createInstance(
        Ci.nsIMsgSearchSession,
      );
      const view = mailViewList.createMailView();
      view.mailViewName = name;
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
      mailViewList.addMailView(view);
      mailViewList.save();
      return { name, created: true };
    }

    function createWorkflowView(mailViewList, name, requiredTag, excludedTags) {
      const searchSession = Cc["@mozilla.org/messenger/searchSession;1"].createInstance(
        Ci.nsIMsgSearchSession,
      );
      const view = mailViewList.createMailView();
      view.mailViewName = name;

      view.appendTerm(
        createSearchTerm(
          searchSession,
          Ci.nsMsgSearchAttrib.MsgStatus,
          Ci.nsMsgSearchOp.Is,
          (value) => {
            value.status = Ci.nsMsgMessageFlags.Marked;
          },
        ),
      );
      view.appendTerm(
        createSearchTerm(
          searchSession,
          Ci.nsMsgSearchAttrib.Keywords,
          Ci.nsMsgSearchOp.Contains,
          (value) => {
            value.str = requiredTag;
          },
        ),
      );
      for (const keyword of excludedTags) {
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

    function findOrCreateWorkflowView(label, requiredTag, excludedTags) {
      const mailViewList = Cc["@mozilla.org/messenger/mailviewlist;1"].getService(
        Ci.nsIMsgMailViewList,
      );
      const name = workflowViewName(label);
      for (let index = 0; index < mailViewList.mailViewCount; index += 1) {
        const view = mailViewList.getMailViewAt(index);
        if (view.mailViewName === name) {
          return { view, name, created: false };
        }
      }
      return {
        view: createWorkflowView(mailViewList, name, requiredTag, excludedTags),
        name,
        created: true,
      };
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
        async ensureUnattendedView(tabId, lookbackDays) {
          const normalizedLookbackDays = Number.isInteger(lookbackDays) && lookbackDays > 0
            ? lookbackDays
            : null;
          const { name, created } = findOrCreateUnattendedView(normalizedLookbackDays);
          const threePaneWindow = resolveThreePaneWindow(tabId);
          // Thunderbird 153's DBViewWrapper accepts the custom mail-view name
          // as the first argument. Passing 0 selects the built-in "all mail"
          // view and ignores the custom terms.
          threePaneWindow.gViewWrapper.setMailView(name, null, true);
          const result = {
            name,
            created,
            applied: true,
          };
          if (normalizedLookbackDays) {
            result.lookbackDays = normalizedLookbackDays;
          }
          return result;
        },

        async ensureWorkflowView(tabId, label, requiredTag, excludedTags) {
          const { name, created } = findOrCreateWorkflowView(
            label,
            requiredTag,
            excludedTags,
          );
          const threePaneWindow = resolveThreePaneWindow(tabId);
          threePaneWindow.gViewWrapper.setMailView(name, null, true);
          return {
            name,
            created,
            applied: true,
          };
        },

        async ensureBulkArchiveView(tabId) {
          const { name, created } = findOrCreateBulkArchiveView();
          const threePaneWindow = resolveThreePaneWindow(tabId);
          threePaneWindow.gViewWrapper.setMailView(name, null, true);
          return { name, created, applied: true };
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
