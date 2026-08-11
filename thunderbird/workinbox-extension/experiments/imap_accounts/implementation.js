var imapAccounts = class extends ExtensionCommon.ExtensionAPI {
  getAPI(_context) {
    const { MailServices } = ChromeUtils.importESModule(
      "resource:///modules/MailServices.sys.mjs",
    );

    function normalizeHost(value) {
      return String(value || "").trim().toLowerCase().replace(/\.$/, "");
    }

    function normalizeUsername(value) {
      return String(value || "").trim();
    }

    return {
      imapAccounts: {
        async resolveAccount(host, username, port) {
          const expectedHost = normalizeHost(host);
          const expectedUsername = normalizeUsername(username);
          const expectedPort = Number(port);

          if (!expectedHost || !expectedUsername || !Number.isInteger(expectedPort)) {
            throw new Error("Invalid WorkInBox IMAP target settings.");
          }

          const matches = [];
          for (const account of MailServices.accounts.accounts) {
            const server = account.incomingServer;
            if (!server || server.type !== "imap") {
              continue;
            }
            if (normalizeHost(server.hostName) !== expectedHost) {
              continue;
            }
            if (normalizeUsername(server.username) !== expectedUsername) {
              continue;
            }
            if (Number(server.port) !== expectedPort) {
              continue;
            }
            matches.push({ account, server });
          }

          if (matches.length === 0) {
            throw new Error(
              `Thunderbird に WIB 設定と一致する IMAP アカウントがありません: ${expectedUsername}@${expectedHost}:${expectedPort}`,
            );
          }
          if (matches.length > 1) {
            throw new Error(
              `Thunderbird に WIB 設定と一致する IMAP アカウントが複数あります: ${expectedUsername}@${expectedHost}:${expectedPort}`,
            );
          }

          const { account, server } = matches[0];
          return {
            accountId: account.key,
            host: server.hostName,
            username: server.username,
            port: server.port,
          };
        },
      },
    };
  }
};
