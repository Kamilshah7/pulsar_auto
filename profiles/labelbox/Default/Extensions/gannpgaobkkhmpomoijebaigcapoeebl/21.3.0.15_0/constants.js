var BROWSER_KEYS = {
	ENABLED : "Unknown_enabled"
};

var BROWSER_VERSION = chrome.runtime.getManifest().version;

var BROWSER_VALUES = {
	SOURCE : "unknown",
	ENVIRONMENT : "background",
	RELEASE : "wallet@" + BROWSER_VERSION
};

var WTX_VALUES = {
	VERB: "wtx-verb",
	CONTEXT: "wtx-context",
	FORM_CONTEXT: "wtx-form-context",
	CLICK_CONTEXT: "wtx-click-context",
	NEW_FORMS: "wtx-new-forms",
	NEW_ELEMENTS: "wtx-new-elements",
	TYPE: "wtx-type",
	VALUE: "wtx-value",
	DEF_VALUE: "wtx-defvalue",
	INPUT: "wtx-input",
	SELECT: "wtx-select",
	ITEM_ID: "wtx-item-id",
	RULE_V3: "wtx-rule-v3",
	RULE_CHECKED_V3: "wtx-rule-checked-v3",
	RULE_TEXT_V3: "wtx-rule-text-v3",
	HAS_PWD_GEN: "wtx-has-pwdgenerator",
	SOURCE: "wtx-source",
	BEFORE_URL: "wtx-before-url",
	PARENT_URL: "wtx-parent-url",
	PARENT_URL_ERR:  "wtx-parent-url-error",
	TITLE: "wtx-title",
	TITLE_ERROR: "wtx-title-error"
};

var DB_STATUS = {
	UNKNOWN: "unknown",
	NOT_CONFIGURED : "not configured",
	LOCKED: "locked",
	OPEN: "open"
};

var SUBSCR_STATUS = {
	UNKNOWN: "unknown",
	VALID : "valid",
	INVALID : "invalid"
};

var WT_ICONS = {
	WALLET : "images/ico_wallet.png",
	WALLET_OFF : "images/ico_wallet_off.png",
	WALLET_LOCKED : "images/ico_wallet_locked.png"
};
