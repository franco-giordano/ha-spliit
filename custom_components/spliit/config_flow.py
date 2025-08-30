from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

DOMAIN = "spliit"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("group_id"): str,
        vol.Required("base_url", default="https://spliit.app"): str,
    }
)

async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    if not data["group_id"].strip():
        raise vol.Invalid("Empty group_id")
    if not data["base_url"].startswith(("http://", "https://")):
        raise vol.Invalid("base_url must start with http or https")
    return {"title": f"Spliit ({data['group_id']})"}

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input["group_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
            except vol.Invalid:
                errors["base"] = "invalid_input"
        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        # Optional YAML import support if ever needed
        return await self.async_step_user(user_input)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or {}
        schema = vol.Schema(
            {
                vol.Required(
                    "base_url",
                    default=current.get("base_url") or self.config_entry.data.get("base_url", "")
                ): str
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

async def async_get_options_flow(config_entry: config_entries.ConfigEntry):
    return OptionsFlowHandler(config_entry)
