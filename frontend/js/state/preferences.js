const KEY = "texas-poker-ui";
const DEFAULTS = Object.freeze({ soundEnabled: false, logCollapsed: false });

export function loadPreferences(storage) {
    try {
        const target = storage === undefined ? window.localStorage : storage;
        return { ...DEFAULTS, ...JSON.parse(target.getItem(KEY) || "{}") };
    } catch {
        return { ...DEFAULTS };
    }
}

export function savePreferences(storage, preferences) {
    try {
        const target = storage === undefined ? window.localStorage : storage;
        target.setItem(KEY, JSON.stringify({
            soundEnabled: Boolean(preferences.soundEnabled),
            logCollapsed: Boolean(preferences.logCollapsed),
        }));
        return true;
    } catch {
        return false;
    }
}
