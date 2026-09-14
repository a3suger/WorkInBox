var imapAccounts = class extends ExtensionCommon.ExtensionAPI {
  getAPI(_context) {
    const { MailServices } = ChromeUtils.importESModule(
      "resource:///modules/MailServices.sys.mjs",
    );

    return {
      imapAccounts: {
        async getServerInfo(accountId) {
          const account = MailServices.accounts.getAccount(accountId);
          if (!account) {
            throw new Error(`Thunderbird account not found: ${accountId}`);
          }

          const server = account.incomingServer;
          if (!server) {
            throw new Error(`Thunderbird incoming server not found: ${accountId}`);
          }

          return {
            accountId,
            type: String(server.type || ""),
            host: String(server.hostname || ""),
            username: String(server.username || ""),
            port: Number(server.port || 0),
          };
        },

        async migrateLegacyBulk(accountId, path) {
          const folder = context.extension.folderManager.get(accountId, path);
          if (!folder) throw new Error(`Thunderbird folder not found: ${accountId}:${path}`);
          const database = folder.msgDatabase;
          const headers = [];
          const enumerator = database.EnumerateMessages();
          while (enumerator.hasMoreElements()) {
            const header = enumerator.getNext().QueryInterface(Ci.nsIMsgDBHdr);
            const keywords = String(header.getStringProperty("keywords") || "").split(/\s+/);
            if (keywords.includes("wib-batch")) headers.push(header);
          }
          if (headers.length > 0) {
            folder.addKeywordsToMessages(headers, "wib-bulk");
            folder.removeKeywordsFromMessages(headers, "wib-batch");
          }
          return { found: headers.length, migrated: headers.length, folderURI: folder.URI };
        },
      },
    };
  }
};
