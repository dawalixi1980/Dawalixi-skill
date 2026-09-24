import {
  normalizeThemeSettings
} from "cadgen-js/lib/themeSettings.js";
import {
  normalizeDisplaySettings
} from "cadgen-js/lib/displaySettings.js";

export function normalizeViewerRenderState({
  themeSettings = {},
  displaySettings = null
} = {}) {
  const normalizedThemeSettings = normalizeThemeSettings(themeSettings);
  const normalizedDisplaySettings = normalizeDisplaySettings(displaySettings);
  return {
    themeSettings: normalizedThemeSettings,
    displaySettings: normalizedDisplaySettings,
    displayMode: normalizedDisplaySettings.mode,
    clipSettings: normalizedDisplaySettings.clip
  };
}
