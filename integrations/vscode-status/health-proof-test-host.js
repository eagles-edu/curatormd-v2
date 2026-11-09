'use strict';

// The parent proof process inspects the real webview and terminates this host.
exports.run = async function run() {
  const vscode = require('vscode');
  await vscode.commands.executeCommand('curatormdV2.openDashboard');
  await new Promise((resolve) => setTimeout(resolve, 25000));
};
