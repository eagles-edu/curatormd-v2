'use strict';

const vscode = require('vscode');

const STATUS_LABEL = 'CuratorMD V2';
const STATUS_DETAILS =
  'CuratorMD V2 label only. Service health, capture, persistence, and identity are not checked.';

function activate(context) {
  const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 20);
  item.name = 'CuratorMD V2';
  item.text = STATUS_LABEL;
  item.tooltip = STATUS_DETAILS;
  item.command = 'curatormdV2.showStatusInfo';
  item.show();

  const showStatusInfo = vscode.commands.registerCommand(
    'curatormdV2.showStatusInfo',
    () => vscode.window.showInformationMessage(STATUS_DETAILS),
  );

  context.subscriptions.push(item, showStatusInfo);
}

function deactivate() {}

module.exports = { activate, deactivate };
