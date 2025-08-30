# Spliit (Home Assistant)

Tiny custom integration exposing one service to create expenses in [Spliit](https://github.com/spliit-app/spliit).  
Uses the Python client package **[`spliit-api-client`](https://pypi.org/project/spliit-api-client/)** and supports **self-hosted base URLs** via a config flow.

> Official Spliit project: https://github.com/spliit-app/spliit  
> Python client used here (fork of SpliitApi): https://pypi.org/project/spliit-api-client/

## Install (HACS)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add this repo’s URL, category **Integration**
3. Install **Spliit**
4. Restart Home Assistant
5. Settings → Devices & services → **Add Integration** → **Spliit**  
   Enter:
   - **Group ID** (default group for this entry)
   - **Base URL** (e.g. `https://spliit.example.com` or `https://spliit.app`)

You can create multiple entries (different groups and/or different hosts). You can later change the base URL in the integration **Options**.

## Service

`service: spliit.create_expense`

```yaml
data:
  # Optional if you have multiple config entries:
  # config_entry_id: "<entry id from UI>"

  group_id: "grp_1234abcd"
  title: "Dinner"
  amount: 1200            # cents
  paid_by: "Alice"        # display name OR user id

  # Omit paid_for and split_mode to split evenly across all participants in the group,
  # or provide explicit splits + a split_mode:
  # split_mode: EVENLY | BY_PERCENTAGE | BY_AMOUNT | BY_SHARES
  # paid_for expects a list of "name_or_id:value"
  #   - BY_PERCENTAGE -> value is a percent (integers that sum to 100)
  #   - BY_AMOUNT -> value is an amount in cents; must sum to `amount`
  #   - BY_SHARES -> value is share units (any positive ints); client will scale
  paid_for:
    - "Alice:600"
    - "Bob:600"
  split_mode: BY_AMOUNT

  note: "Friday night"
