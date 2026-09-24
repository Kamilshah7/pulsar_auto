function logLastError() {
	if (chrome.runtime.lastError) { 
		bdiagnostic.log(chrome.runtime.lastError.message); 
	} 
}

chrome.webNavigation['onBeforeNavigate'].addListener(function (e) {
	bdiagnostic.log("onBeforeNavigate, tabID " + e.tabId + ", frameID " + e.frameId);
	if (e.frameId === 0) {
		if (walletStatus.subscriptionStatus !== SUBSCR_STATUS.INVALID
			&& walletStatus.buttonEnabled
			&& walletStatus.db_status ===  DB_STATUS.OPEN) {
			chrome.tabs.sendMessage(e.tabId, {
				"verb": "before-navigate-event"
			}, logLastError);
		}
	}
	if (e.frameId === 0 && tabsInfo.pendingLogins[e.tabId] && tabsInfo.pendingLogins[e.tabId].asked) {
		delete tabsInfo.pendingLogins[e.tabId];
		saveTabsInfo();
	}
});

chrome.alarms.onAlarm.addListener((alarm) => {
	if (alarm.name === "generate-sentry-error") {
		testSentryErrorReporting();
	}
	else if (alarm.name === "uninstall-native-self") {
		browser.management.uninstallSelf();
	}
});

function postHtmlDocMessage(data) {
	NMH.postMessage({
		method: "on-msg-html-doc",
		data: data
	});
}

chrome.webNavigation['onDOMContentLoaded'].addListener(function (e) {
	bdiagnostic.log("onDOMContentLoaded, tabID " + e.tabId + ", frameID " + e.frameId);
	var tabId = e.tabId;
	try {
		if (CanInjectScript(e)) {
			compatExecuteScript(
				tabId,
				[e.frameId],  
				[
					"bundle.min.js",
					"constants.js",
					"constants.content.js",
					"constants.override.js",
					"content.js"
				],
				logLastError
			);
		}
	} catch (ex) { bdiagnostic.exception(ex); }
});

chrome.webNavigation['onTabReplaced'].addListener(function (e) {
	bdiagnostic.log("onTabReplaced, tabID " + e.tabId);
	var tabId = e.tabId;
	try {
		if (CanInjectScript(e)) {
			compatExecuteScript(
				tabId,
				[e.frameId],  
				[
					"content.js"
				],
				logLastError
			);
		}
	} catch (e) { bdiagnostic.exception(e); }
});

function passMessageToTab(msg, doc_context, forgetIds) {
	var tabs = tabsInfo.documentInfos;
	if (doc_context) {
		for (var i = 0, size = tabs.length; i < size; i++) {
			if (tabs[i].context === doc_context) {
				chrome.tabs.sendMessage(tabs[i].tabId, msg, logLastError);
				break;
			}
		}
	}
	else {
		chrome.tabs.query({ active: true, lastFocusedWindow: true }, function (tabs) {
			if (tabs && tabs[0]) {
				chrome.tabs.sendMessage(tabs[0].id, msg, logLastError);
			}
		});
	}
	if (forgetIds) {
		delete tabsInfo.pendingLogins[tabs[i].tabId];
		saveTabsInfo();
	}
}

function handleHtmlDocUpdate(msg) {
	bdiagnostic.log("wallet_html_doc_update received");
	bdiagnostic.log(msg);

	var msgDoc = msg["wallet_html_doc_update"];
	var verb = msgDoc[WTX_VALUES.VERB];

	var context;
	if ((verb === "doc-complete") ||                 //Update inputs with rule field
		(verb === "doc-password-generator-rsp") ||   //Fill with pwd values
		(verb === "before-navigate") ||              //Handle 2-phase login
		(verb === "handle-menu-rsp")) {              //Autofill with form values

		context = msgDoc[WTX_VALUES.CONTEXT];
		passMessageToTab(msgDoc, context);
	}
	else if (verb === "doc-autofill") {
		//Autofill with values
		context = msgDoc[WTX_VALUES.CONTEXT];
		passMessageToTab(msgDoc, context, true);
	}
	else if (verb === "open-page") {
		//Autofill with values
		chrome.tabs.create({
			"url": msgDoc["open-url"]
		}, function (tab) {
			bdiagnostic.log("new tab callback for id " + tab.id);
			tabsInfo.pendingLogins[tab.id] = { id: msgDoc[WTX_VALUES.ITEM_ID], asked: false };
			saveTabsInfo();
		});
	}
	else if (verb === "handle-menu-report") {
		//Autofill with values
		chrome.tabs.create({
			"url": msgDoc["open-url"]
		});
	}
	else if (verb === "handle-menu-debug") {
		const cmd = msgDoc["wtx-cmd-id"];
		if (cmd) {
			if (cmd === "__dbg-generate-sentry-error") {
				chrome.alarms.create("generate-sentry-error", { when: Date.now() + 1000 });
			};
		}
	}
}

NMH.addListener(function (msg) {
	try {
		if (typeof msg["wallet_html_doc_update"] !== "undefined") {
			handleHtmlDocUpdate(msg);
		}
		if (typeof msg["ping"] !== "undefined") {
			var ping = msg["ping"];
			bdiagnostic.log("ping received: " + ping);
			NMH.postMessage({ 'ping_response': ping });
		}
	} catch (e) {
		bdiagnostic.exception(e);
	}
});

function handleButtonStatusNotConfigured() {
	NMH.postMessage({
		method: "configure-wallet",
		data: null
	});
}

function handleButtonStatusOpened(tab) {
	var msg = {};
	var parentTitle = "";
	var parentUrl = "";
	if (tab) {
		parentTitle = tab.title;
		parentUrl = tab.url;
		if (tabsInfo[tab.id]) {
			try {
				parentTitle = tabsInfo.topInfos[tab.id].title;
				parentUrl = tabsInfo.topInfos[tab.id].url;
			} catch (e) {
				bdiagnostic.exception(e);
			}
		}
	}
	msg[WTX_VALUES.TITLE] = parentTitle;
	msg[WTX_VALUES.PARENT_URL] = parentUrl;

	NMH.postMessage({
		method: "drop-down",
		data: msg
	});
}

function handleButtonStatusLocked() {
	NMH.postMessage({
		method: "unlock-wallet",
		data: null
	});
}

function handleButtonDisabled() {
	if (!walletStatus.agent_running && (walletStatus.subscriptionStatus !== SUBSCR_STATUS.VALID)) {
		walletStatus.openWalletTimestamp = Date.now();
		NMH.postMessage({
			method: "start-agent",
			data: null
		});
	}
}

compatAction.onClicked.addListener(function (tab) {
	bdiagnostic.log("button clicked");
	if (walletStatus.buttonEnabled) {
		if (walletStatus.db_status === DB_STATUS.NOT_CONFIGURED) {
			handleButtonStatusNotConfigured();
		} else if (walletStatus.db_status === DB_STATUS.OPEN) {
			handleButtonStatusOpened(tab);
		} else if (walletStatus.db_status === DB_STATUS.LOCKED) {
			handleButtonStatusLocked();
		}
	}
	else handleButtonDisabled();
});

function onRequestGeneratePwd(message) {
	NMH.postMessage({
		method: "request-generate-password",
		data: message.data
	});
}

function onInfoClick(message) {
	postHtmlDocMessage(message.data);
}

function onInfoSubmit(message, sender) {
	var tabId = sender.tab.id;
	var msg = message.data;

	var parentTitle = sender.tab.title;
	var parentUrl = sender.tab.url;
	
	try {
		parentTitle = tabsInfo.topInfos[tabId].title;
		parentUrl = tabsInfo.topInfos[tabId].url;
	} catch (e) {
		bdiagnostic.exception(e);
	}

	try {
		if (msg[WTX_VALUES.VERB] === "before-navigate") {
			if (msg[WTX_VALUES.TITLE_ERROR] === "true") {
				msg[WTX_VALUES.TITLE] = parentTitle;
			}
			if (msg[WTX_VALUES.PARENT_URL_ERR] === "true") {
				if (URI(msg[WTX_VALUES.BEFORE_URL]).domain() === 
					URI(parentUrl).domain()) {

					msg[WTX_VALUES.PARENT_URL] = parentUrl;
				}
				else {
					msg[WTX_VALUES.PARENT_URL] = msg[WTX_VALUES.BEFORE_URL];
				}
			}
		}
	} catch (e) {
		bdiagnostic.exception(e);
	}

	postHtmlDocMessage(msg);
}

function onInfoComplete(message, sender) {
	var tabId = sender.tab.id;
	var msg = message.data;

	tabsInfo.topInfos[tabId] = tabsInfo.topInfos[tabId] || {};
	tabsInfo.topInfos[tabId].title = sender.tab.title;
	tabsInfo.topInfos[tabId].url = sender.tab.url;

	try {
		if (msg[WTX_VALUES.TITLE_ERROR] === "true") {
				msg[WTX_VALUES.TITLE] = sender.tab.title;
			}
			if (msg[WTX_VALUES.PARENT_URL_ERR] === "true") {
				if (URI(msg[WTX_VALUES.BEFORE_URL]).domain() === 
					URI(sender.tab.url).domain()) {

					msg[WTX_VALUES.PARENT_URL] = sender.tab.url;
				}
				else {
					msg[WTX_VALUES.PARENT_URL] = msg[WTX_VALUES.BEFORE_URL];
				}
			}
	} catch (e) {
		bdiagnostic.exception(e);
	}

	bdiagnostic.log("Interogating loginId of new tab " + tabId);
	if (tabsInfo.pendingLogins[tabId] && tabsInfo.pendingLogins[tabId].id) {
		msg[WTX_VALUES.ITEM_ID] = tabsInfo.pendingLogins[tabId].id;
		tabsInfo.pendingLogins[tabId].asked = true;
	}

	tabsInfo.documentInfos.push({
		tabId: sender.tab.id,
		context: msg[WTX_VALUES.CONTEXT]
	});
	saveTabsInfo();

	postHtmlDocMessage(msg);
}

function onUpdateButtonsStats(sender) {
	var tabId = sender.tab.id;
	var msg = (walletStatus.subscriptionStatus !== SUBSCR_STATUS.INVALID
		&& walletStatus.buttonEnabled
		&& walletStatus.db_status ===  DB_STATUS.OPEN) ? "show-wallet-controls" : "hide-wallet-controls";
	chrome.tabs.sendMessage(tabId, {
		"verb": msg
	}, logLastError);
}

chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
	if (!walletStatus.buttonEnabled || walletStatus.db_status !==  DB_STATUS.OPEN) {
		return;
	}
	bdiagnostic.log("received", message);
	try {
		if (message.verb === "request-generate-password") {
			onRequestGeneratePwd(message);
		} else if (message.verb === "info-onclick") {
			onInfoClick(message);
		} else if (message.verb === "info-onsubmit") {
			onInfoSubmit(message, sender);
		} else if (message.verb === "info-oncomplete") {
			onInfoComplete(message, sender);
		} else if (message.verb === "update-buttons-status") {
			onUpdateButtonsStats(sender);
		}
	} catch (ex) { bdiagnostic.exception(ex); }
});