from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv

# Using the spliit-api-client package
from spliit.client import Spliit
from spliit.utils import SplitMode

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
        vol.Optional("paid_for"): vol.All(list, [cv.string]),    # ["Alice:600","Bob:600"]
        vol.Optional("split_mode", default="EVENLY"): vol.In({"EVENLY","BY_PERCENTAGE","BY_AMOUNT","BY_SHARES"}),
        vol.Optional("note"): cv.string,
    }
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True

def _build_client(group_id: str, base_url: str) -> Spliit:
    """Instantiate the Spliit client, being tolerant to keyword naming."""
    base_url = base_url.rstrip("/")
    try:
        return Spliit(group_id=group_id, base_url=base_url)
    except TypeError:
        # Some forks used `api_url`
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
        async def _find_user_id_by_name(client: Spliit, name_or_id: string) -> str:
            """Resolve a display name to a participant id by scanning the group list.
            If not found, assume the caller already passed an id."""
            name = str(name_or_id).strip()
            try:
                participants = client.get_participants()
                for p in participants:
                    # p example is expected to have at least id + name
                    pid = p.get("id") or p.get("_id") or p.get("userId")
                    pname = (p.get("name") or p.get("username") or "").strip()
                    if pname.lower() == name.lower():
                        return pid
            except Exception as err:
                _LOGGER.debug("Could not fetch participants to resolve name '%s': %s", name, err)
            return name  # fallback (likely already an id)

        def _parse_paid_for(items: List[str]) -> List[Tuple[str, int]]:
            """Parse ['Alice:600','Bob:600'] -> [(id_or_name, 600), ...] (value kept as int)."""
            result: List[Tuple[str, int]] = []
            for item in items:
                name_or_id, val = item.split(":", 1)
                result.append((name_or_id.strip(), int(val.strip())))
            return result

        async def _create_expense(call: ServiceCall) -> None:
            data = call.data
            store = hass.data[DOMAIN]

            # choose entry
            sel_entry_id = data.get("config_entry_id")
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
            split_mode_in: str = data.get("split_mode", "EVENLY")
            note: str | None = data.get("note")

            # Map to SplitMode enum
            split_mode = {
                "EVENLY": SplitMode.EVENLY,
                "BY_PERCENTAGE": SplitMode.BY_PERCENTAGE,
                "BY_AMOUNT": SplitMode.BY_AMOUNT,
                "BY_SHARES": SplitMode.BY_SHARES,
            }[split_mode_in]

            # Resolve payer id
            paid_by = await _find_user_id_by_name(client, paid_by_in)

            # Build paid_for list depending on mode
            if paid_for_in:
                raw_pairs = _parse_paid_for(paid_for_in)
                paid_for: List[Tuple[str, int]] = []
                for name_or_id, value in raw_pairs:
                    uid = await _find_user_id_by_name(client, name_or_id)
                    paid_for.append((uid, value))
            else:
                # EVENLY across all participants when nothing provided
                participants = client.get_participants()
                if not participants:
                    raise vol.Invalid("No participants found in the group to split evenly.")
                paid_for = []
                for p in participants:
                    uid = p.get("id") or p.get("_id") or p.get("userId")
                    # For EVENLY mode, share values are ignored; pass 1 for each
                    paid_for.append((uid, 1))
                split_mode = SplitMode.EVENLY

            # Create the expense
            try:
                # Prefer passing group_id if client supports it; otherwise rely on client.group_id
                client.add_expense(
                    title=title,
                    paid_by=paid_by,
                    paid_for=paid_for,
                    amount=amount,
                    split_mode=split_mode,
                    notes=note,
                    group_id=group_id
                )
            except TypeError:
                client.add_expense(
                    title=title,
                    paid_by=paid_by,
                    paid_for=paid_for,
                    amount=amount,
                    split_mode=split_mode,
                    notes=note,
                )

            _LOGGER.info(
                "Spliit: created expense '%s' amount=%s split=%s group=%s",
                title, amount, split_mode_in, group_id
            )

        hass.services.async_register(DOMAIN, SERVICE_CREATE_EXPENSE, _create_expense, schema=SERVICE_SCHEMA)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN] and DOMAIN in hass.services.async_services():
        hass.services.async_remove(DOMAIN, SERVICE_CREATE_EXPENSE)
    return True
