var compatAction = chrome.action;

function compatExecuteScript(tabId, frameIds, files, callback) {
	return chrome.scripting.executeScript(
		{
			target: { tabId: tabId, frameIds: frameIds },
			files: files
		},
		callback
	);
}
