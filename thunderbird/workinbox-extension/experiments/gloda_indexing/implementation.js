var glodaIndexing = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
    const { GlodaDatastore } = ChromeUtils.importESModule(
      "resource:///modules/gloda/GlodaDatastore.sys.mjs",
    );
    const { GlodaMsgIndexer } = ChromeUtils.importESModule(
      "resource:///modules/gloda/IndexMsg.sys.mjs",
    );

    function getNativeFolder(accountId, path) {
      const folder = context.extension.folderManager.get(accountId, path);
      if (!folder) {
        throw new Error(`Thunderbird folder not found: ${accountId}:${path}`);
      }
      return folder;
    }

    function getStatus(folder) {
      const glodaFolder = GlodaDatastore._mapFolder(folder);
      return {
        enabled: glodaFolder.indexingPriority !== glodaFolder.kIndexingNeverPriority,
        priority: glodaFolder.indexingPriority,
      };
    }

    return {
      glodaIndexing: {
        async getStatus(accountId, path) {
          return getStatus(getNativeFolder(accountId, path));
        },

        async setEnabled(accountId, path, enabled) {
          const folder = getNativeFolder(accountId, path);
          const glodaFolder = GlodaDatastore._mapFolder(folder);

          if (enabled) {
            GlodaMsgIndexer.resetFolderIndexingPriority(folder, true);
          } else {
            GlodaMsgIndexer.setFolderIndexingPriority(
              folder,
              glodaFolder.kIndexingNeverPriority,
            );
          }

          return getStatus(folder);
        },
      },
    };
  }
};
