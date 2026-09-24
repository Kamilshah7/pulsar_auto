var walletSettings;

const WT_MSG = {
	INIT_DATA : "wallet-init-data",
	SET_SETTINGS : "wallet-set-settings",
	TOOLTIP_TEXTS : "wallet-tooltip-texts"
};

const SKIPPED_PAGES = [
	"chrome://",
	"about:"
];

function CanInjectScript(e) {
	if (e && e.url) {
		for (const page of SKIPPED_PAGES) {
			if (e.url.startsWith(page)) { return false; }
		}
	}
	return !!NMH.getPort();
}

compatAction.setTitle({ title: TooltipStrings.off });
compatAction.setIcon({ path : WT_ICONS.WALLET_OFF });
walletStatus.buttonEnabled = false;

function RecheckCurrentTabForLogin() {
	chrome.tabs.query({ active: true, currentWindow: true, status: "complete" }, function (tabs) {
		if (tabs.length === 0) { return; }
		var tab = tabs[0];
		var tabId = tab.id;
		if (!tabsInfo.pendingLogins[tabId] || tabsInfo.pendingLogins[tabId].asked) {
			return;
		}
		chrome.tabs.sendMessage(tab.id, {
			"verb": "get-dom-info"
		}, function (response) {
			if (chrome.runtime.lastError) {
				bdiagnostic.log(chrome.runtime.lastError.message);	
			}
			NMH.postMessage({
				method: "get-info-for-page",
				data: response || null
			});
		});
		tabsInfo.pendingLogins[tabId] = tabsInfo.pendingLogins[tabId] || {};
		tabsInfo.pendingLogins[tabId].asked = true;
		saveTabsInfo();
	});
}

function UpdateExtensionButton() {
	//Update button
	if (!walletStatus.buttonEnabled) {
		compatAction.setIcon({ path: WT_ICONS.WALLET_OFF });
		compatAction.setTitle({ title: TooltipStrings.off });
		return;
	}

	if (walletStatus.db_status === DB_STATUS.NOT_CONFIGURED) {
		compatAction.setIcon({ path: WT_ICONS.WALLET_OFF });
		compatAction.setTitle({ title: TooltipStrings.configure });
	}
	else if (walletStatus.db_status === DB_STATUS.LOCKED) {
		compatAction.setIcon({ path: WT_ICONS.WALLET_LOCKED });
		compatAction.setTitle({ title: TooltipStrings.locked });
	}
	else if (walletStatus.db_status === DB_STATUS.OPEN) {
		compatAction.setIcon({ path: WT_ICONS.WALLET });
		compatAction.setTitle({ title: TooltipStrings.on });
	}
	else {
		walletStatus.buttonEnabled = false;
		compatAction.setIcon({ path: WT_ICONS.WALLET_OFF });
		compatAction.setTitle({ title: TooltipStrings.off });
		bdiagnostic.log("Unknown dbState: " + walletStatus.db_status);
	}
}

function UpdateEnabledWithSettings(settings) {
	walletStatus.enabled = (settings.settings["enabled"] || settings.default_settings["enabled"] || "false") === "true";
	walletStatus.enabled_for_browser = (settings.settings[BROWSER_KEYS.ENABLED] || settings.default_settings[BROWSER_KEYS.ENABLED] || "false") === "true";
	walletStatus.agent_running = settings.agStatus === 2;
	walletStatus.buttonEnabled = walletStatus.enabled && walletStatus.enabled_for_browser && walletStatus.agent_running;
}

function UpdateDbStatusWithSettings(settings) {
	if (settings.dbStatus === 1) {
		walletStatus.db_status = DB_STATUS.NOT_CONFIGURED;
	}
	else if (settings.dbStatus === 3) {
		walletStatus.db_status = DB_STATUS.OPEN;
		RecheckCurrentTabForLogin();
	}
	else if (settings.dbStatus === 4 || settings.dbStatus === 2) {
		walletStatus.db_status = DB_STATUS.LOCKED;
	}
	else {
		walletStatus.db_status = DB_STATUS.UNKNOWN;
	}

	if (settings.subscriptionStatus === 1) {
		walletStatus.subscriptionStatus = SUBSCR_STATUS.VALID;
	}
	else if (settings.subscriptionStatus === 2) {
		walletStatus.subscriptionStatus = SUBSCR_STATUS.INVALID;
	}
	else {
		walletStatus.subscriptionStatus = SUBSCR_STATUS.UNKNOWN;
	}

	if (walletStatus.db_status === DB_STATUS.NOT_CONFIGURED
		&& walletStatus.subscriptionStatus !== SUBSCR_STATUS.VALID) {
		walletStatus.buttonEnabled = false;
	}
}

function CheckAgentJustStarted(agentRunningBefore) {
	if (walletStatus.agent_running && !agentRunningBefore && (walletStatus.openWalletTimestamp !== 0)) {

		//agent just started
		if (((!walletStatus.enabled || !walletStatus.enabled_for_browser) && (walletStatus.subscriptionStatus === SUBSCR_STATUS.INVALID)) &&
			(Date.now() < walletStatus.openWalletTimestamp + 3000)) {

			NMH.postMessage({
				method: "open-wallet",
				data: null
			});
		}

		walletStatus.openWalletTimestamp = 0;
	}
}

function UpdateContentButtons() {
	chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
		if (tabs.length === 0) { return; }
		var tabId = tabs[0].id;
		var msg = (walletStatus.subscriptionStatus === SUBSCR_STATUS.VALID
			&& walletStatus.buttonEnabled
			&& walletStatus.db_status === DB_STATUS.OPEN) ? "show-wallet-controls" : "hide-wallet-controls";
		chrome.tabs.sendMessage(tabId, {
			"verb": msg
		}, _ => {
			if (chrome.runtime.lastError) {
				bdiagnostic.log(chrome.runtime.lastError.message);	
			}
		});
	});
}

function UpdateWithSettings(settings) {
	var agentRunningBefore = walletStatus.agent_running;

	UpdateEnabledWithSettings(settings);
	UpdateDbStatusWithSettings(settings);
	CheckAgentJustStarted(agentRunningBefore);
	UpdateContentButtons();
	UpdateExtensionButton();
}

NMH.addListener(function (msg) {
	try {
		if (typeof msg[WT_MSG.INIT_DATA] !== "undefined") {
			var walletData = msg[WT_MSG.INIT_DATA];
			bdiagnostic.log("wallet-init-data received");
			bdiagnostic.log(msg);
			var flags = walletData.flags;
			if (flags === -1) { //All new data
				walletSettings = walletData;
			}
			if (flags & 8) { //dbStatus change
				walletSettings.dbStatus = walletData.dbStatus;
			}

			UpdateWithSettings(walletSettings);
		}
		if (typeof msg[WT_MSG.SET_SETTINGS] !== "undefined") {
			var newSettings = msg[WT_MSG.SET_SETTINGS];
			bdiagnostic.log("wallet-set-settings received");
			bdiagnostic.log(msg);
			walletSettings.settings = newSettings;

			UpdateWithSettings(walletSettings);
		}

		if (typeof msg[WT_MSG.TOOLTIP_TEXTS] !== "undefined") {
			var newTexts = msg[WT_MSG.TOOLTIP_TEXTS];
			bdiagnostic.log("wallet-tooltip-texts received");
			bdiagnostic.log(msg);

			TooltipStrings.locked = newTexts.locked || TooltipStrings.locked;
			TooltipStrings.on = newTexts.on || TooltipStrings.on;
			TooltipStrings.off = newTexts.off || TooltipStrings.off;
			TooltipStrings.configure = newTexts.configure || TooltipStrings.configure;
			TooltipStrings.restart = newTexts.restart || TooltipStrings.restart;
			TooltipStrings.update = newTexts.update || TooltipStrings.update;

			UpdateExtensionButton();
		}

	} catch (e) {
		bdiagnostic.exception(e);
	}
});