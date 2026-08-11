var imapAccounts = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
    return {
      imapAccounts: {
        async getServerInfo(accountId) {
          const account = context.extension.accountManager.getAccount(accountId);
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
