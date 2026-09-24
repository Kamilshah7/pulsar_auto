function getDefaultTabsInfo() {
	var pendingLogins = {};
	var documentInfos = [];
	var topInfos = {};
	
	return {
		pendingLogins : pendingLogins,
		documentInfos : documentInfos,
		topInfos : topInfos
	};
}

var tabsInfo = getDefaultTabsInfo();

chrome.runtime.onStartup.addListener(function() { 
    chrome.storage.local.set({"tabsInfo": null});
	tabsInfo = getDefaultTabsInfo();
});

chrome.runtime.onInstalled.addListener(function() { 
    chrome.storage.local.set({"tabsInfo": null});
	tabsInfo = getDefaultTabsInfo();
});

chrome.storage.local.get(["tabsInfo"], (result) => {
	if (result) {
		var defTabsInfo = getDefaultTabsInfo();

		tabsInfo.pendingLogins = result.pendingLogins || defTabsInfo.pendingLogins;
		tabsInfo.documentInfos = result.documentInfos || defTabsInfo.documentInfos;
		tabsInfo.topInfos = result.topInfos || defTabsInfo.topInfos;

		bdiagnostic.log('tabsInfo', tabsInfo);
	}
});

function saveTabsInfo() {
	chrome.storage.local.set({"tabsInfo": tabsInfo});
}

chrome.tabs.onRemoved.addListener(function (tabId, removeInfo) {
	delete tabsInfo.pendingLogins[tabId];
	delete tabsInfo.topInfos[tabId];

	for (var i = tabsInfo.documentInfos.length - 1; i >= 0; i--) {
		if (tabsInfo.documentInfos[i].tabId === tabId) {
			tabsInfo.documentInfos.splice(i,1);
		}
	}
	saveTabsInfo();
});

chrome.tabs.onActivated.addListener(function (activeInfo) {
    NMH.postMessage({
        method: "tab-change",
        data: null
    });
});