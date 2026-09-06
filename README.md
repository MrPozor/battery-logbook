# Battery Logbook

A small self-hosted LAN-only battery logbook for individually numbered rechargeable cells.

## Start
```bash
docker compose up -d --build
```
Then open http://SERVER-IP:8000

The SQLite database is stored in `./data/batteries.db`.

## Notes
- Each physical battery gets an automatically assigned numeric ID. Write the displayed zero-padded ID on the cell.
- Log actions such as Charge, Break-in, Refresh,Storage and Put into use.
- Capacity measurements are optional. They allow to display the health of each battery.
- `location` is the current device/location; movements can also be recorded as events.
- For LAN-only exposure, do not publish port 8000 on your router/firewall. On a Docker host, the published port is reachable on the host's network interfaces.
