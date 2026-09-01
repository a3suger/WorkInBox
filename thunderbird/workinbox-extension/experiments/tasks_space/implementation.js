var tasksSpace = class extends ExtensionCommon.ExtensionAPI {
  getAPI() {
    return {
      tasksSpace: {
        async open() {
          const win = Services.wm.getMostRecentWindow("mail:3pane");
          if (!win) {
            throw new Error("Thunderbirdのメインウィンドウが見つかりません。");
          }
          const button = win.document.getElementById("tasksButton");
          if (!button) {
            throw new Error("ThunderbirdのToDoボタンが見つかりません。");
          }
          button.click();
          win.focus();
          return { opened: true };
        },
      },
    };
  }
};
