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
          let database;
          try {
            database = folder.msgDatabase;
          } catch (error) {
            throw new Error(`対象フォルダのローカルDBを開けませんでした: ${error.message || error}`);
          }
          const headers = [];
          try {
            const enumerator = database.EnumerateMessages();
            while (enumerator.hasMoreElements()) {
              const header = enumerator.getNext();
              const keywords = String(header.getStringProperty("keywords") || "").split(/\s+/);
              if (keywords.includes("wib-batch")) headers.push(header);
            }
          } catch (error) {
            throw new Error(`旧キーワードを読み取れませんでした: ${error.message || error}`);
          }
          if (headers.length > 0) {
            try {
              folder.addKeywordsToMessages(headers, "wib-bulk");
              folder.removeKeywordsFromMessages(headers, "wib-batch");
            } catch (error) {
              throw new Error(`IMAPキーワードを書き換えられませんでした（${headers.length}件）: ${error.message || error}`);
            }
          }
          return { found: headers.length, migrated: headers.length, folderURI: folder.URI };
        },
      },
    };
  }
};
