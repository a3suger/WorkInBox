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
        neverPriority: glodaFolder.kIndexingNeverPriority,
        folderProperty: folder.getStringProperty("indexingPriority") || "",
      };
    }

    return {
      glodaIndexing: {
        async getStatus(accountId, path) {
          return getStatus(getNativeFolder(accountId, path));
        },

        async setEnabled(accountId, path, enabled) {
          const folder = getNativeFolder(accountId, path);
          const before = getStatus(folder);
          const glodaFolder = GlodaDatastore._mapFolder(folder);

          if (enabled) {
            GlodaMsgIndexer.resetFolderIndexingPriority(folder, true);
          } else {
            GlodaMsgIndexer.setFolderIndexingPriority(
              folder,
              glodaFolder.kIndexingNeverPriority,
            );
          }

          const after = getStatus(folder);
          return {
            requestedEnabled: enabled,
            beforeEnabled: before.enabled,
            beforePriority: before.priority,
            beforeFolderProperty: before.folderProperty,
            afterEnabled: after.enabled,
            afterPriority: after.priority,
            afterFolderProperty: after.folderProperty,
            neverPriority: after.neverPriority,
            applied: after.enabled === enabled,
          };
        },
      },
    };
  }
};
