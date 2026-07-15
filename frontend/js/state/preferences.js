const KEY = "texas-poker-ui";
const DEFAULTS = Object.freeze({ soundEnabled: false, logCollapsed: false });

export function loadPreferences(storage = window.localStorage) {
    try {
        return { ...DEFAULTS, ...JSON.parse(storage.getItem(KEY) || "{}") };
    } catch {
        return { ...DEFAULTS };
    }
}

export function savePreferences(storage = window.localStorage, preferences) {
    storage.setItem(KEY, JSON.stringify({
        soundEnabled: Boolean(preferences.soundEnabled),
        logCollapsed: Boolean(preferences.logCollapsed),
    }));
}
