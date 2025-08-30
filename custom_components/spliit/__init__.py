from __future__ import annotations

import logging
from typing import Any, List, Tuple

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv

# Spliit client lib
from spliit import Spliit, CATEGORIES

_LOGGER = logging.getLogger(__name__)

DOMAIN = "spliit"
SERVICE_CREATE_EXPENSE = "create_expense"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
        vol.Required("group_id"): cv.string,
        vol.Required("title"): cv.string,
        vol.Required("amount"): vol.All(int, vol.Range(min=1)),  # cents
        vol.Required("paid_by"): cv.string,
        vol.Optional("paid_for"): vol.All(list, [cv.string]),
        vol.Optional("category_path"): cv.string,
        vol.Optional("note"): cv.string,
    }
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True

def _build_client(group_id: str, base_url: str) -> Spliit:
    base_url = base_url.rstrip("/")
    try:
        return Spliit(group_id=group_id, base_url=base_url)
    except TypeError:
        # Fallback for forks that use `api_url`
        return Spliit(group_id=group_id, api_url=base_url)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = {**entry.data, **(entry.options or {})}
    group_id: str = data["group_id"]
    base_url: str = data.get("base_url", "https://spliit.app")
    client = _build_client(group_id, base_url)

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "group_id": group_id,
        "base_url": base_url,
    }

    if f"{DOMAIN}.{SERVICE_CREATE_EXPENSE}" not in hass.services.async_services().get(DOMAIN, {}):
        async def _resolve_user_id(client: Spliit, identifier: str) -> str:
            try:
                uid = client.get_username_id(identifier)
                if uid:
                    return uid
            except Exception as err:
                _LOGGER.debug("Name lookup failed for %s: %s (falling back to raw)", identifier, err)
            return identifier

        async def _create_expense(call: ServiceCall) -> None:
            data = call.data
            sel_entry_id = data.get("config_entry_id")
            store = hass.data[DOMAIN]

            if sel_entry_id:
                entry_store = store.get(sel_entry_id)
                if not entry_store:
                    raise vol.Invalid(f"config_entry_id {sel_entry_id} not found")
            else:
                entry_store = next(iter(store.values()))

            client: Spliit = entry_store["client"]

            group_id: str = data["group_id"]
            title: str = data["title"]
            amount: int = data["amount"]
            paid_by_in: str = data["paid_by"]
            paid_for_in: List[str] | None = data.get("paid_for")
            category_path: str | None = data.get("category_path")
            note: str | None = data.get("note")

            paid_by = await _resolve_user_id(client, paid_by_in)

            if paid_for_in:
                paid_for: List[Tuple[str, int]] = []
                for item in paid_for_in:
                    try:
                        name_or_id, amt_str = item.split(":", 1)
                        uid = await _resolve_user_id(client, name_or_id.strip())
                        paid_for.append((uid, int(amt_str.strip())))
                    except Exception as err:
                        raise vol.Invalid(f"Invalid paid_for item '{item}': {err}") from err
            else:
                participants = client.get_participants()
                if not participants:
                    raise vol.Invalid("No participants found in the group to split evenly.")
                share = amount // len(participants)
                remainder = amount % len(participants)
                paid_for = []
                for idx, p in enumerate(participants):
                    uid = p.get("id") or await _resolve_user_id(client, p.get("name", ""))
                    paid_for.append((uid, share + (1 if idx < remainder else 0)))

            category_value = None
            if category_path:
                try:
                    parts = [x.strip() for x in category_path.split("/") if x.strip()]
                    node: Any = CATEGORIES
                    for part in parts[:-1]:
                        node = node[part]
                    category_value = node[parts[-1]]
                except Exception as err:
                    _LOGGER.warning(
                        "Category path '%s' not found: %s; continuing without category.",
                        category_path, err
                    )

            try:
                client.add_expense(
                    title=title,
                    paid_by=paid_by,
                    paid_for=paid_for,
                    amount=amount,
                    category=category_value,
                    note=note,
                    group_id=group_id
                )
            except TypeError:
                # Older signatures without group_id kwarg
                client.add_expense(
                    title=title,
                    paid_by=paid_by,
                    paid_for=paid_for,
                    amount=amount,
                    category=category_value,
                    note=note,
                )

            _LOGGER.info("Spliit: created expense '%s' amount=%s in group %s", title, amount, group_id)

        hass.services.async_register(DOMAIN, SERVICE_CREATE_EXPENSE, _create_expense, schema=SERVICE_SCHEMA)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN] and DOMAIN in hass.services.async_services():
        hass.services.async_remove(DOMAIN, SERVICE_CREATE_EXPENSE)
    return True
