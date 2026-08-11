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
            host: String(server.hostName || ""),
            username: String(server.username || ""),
            port: Number(server.port || 0),
          };
        },
      },
    };
  }
};
