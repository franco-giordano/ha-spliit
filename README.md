# Spliit (Home Assistant)

Tiny custom integration exposing one service to create expenses in [Spliit](https://github.com/guysoft/SpliitApi).  
Supports **self-hosted base URLs** via a config flow.

## Install (HACS)

1. In HACS → Integrations → ⋮ → *Custom repositories*
2. Add this repo’s URL, category **Integration**
3. Install **Spliit**
4. Restart Home Assistant
5. Settings → Devices & services → *Add Integration* → **Spliit**  
   Enter:
   - **Group ID**
   - **Base URL** (e.g. `https://spliit.example.com`)

> You can create multiple entries (different groups / servers). You can later change the base URL in the integration’s *Options*.

## Service

`service: spliit.create_expense`

```yaml
data:
  # optional if you have multiple config entries
  # config_entry_id: "<entry id from UI>"

  group_id: "grp_1234abcd"
  title: "Dinner"
  amount: 1200            # cents
  paid_by: "Alice"        # name or user id
  # omit paid_for to split evenly among participants
  paid_for:               # explicit shares
    - "Alice:600"
    - "Bob:600"
  category_path: "Food & Drinks/Restaurants"
  note: "Friday night"
