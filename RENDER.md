# Deploy King Soon Bot on Render

1. Push this project to GitHub.
2. In Render, create a new Blueprint and select the repository.
3. Render reads `render.yaml`, creates a Background Worker, and asks for `TOKEN`.
4. Paste the Discord bot token into `TOKEN`, then deploy.

The bot uses `SETTINGS_DIR` for saved ticket and contact-panel settings. Render services have temporary storage by default, so create a Persistent Disk if you want these settings to survive a redeploy:

1. Open the Background Worker in Render.
2. Open **Disks** and add a Persistent Disk.
3. Set its mount path to `/opt/render/project/src/data`.

Persistent Disks require a paid Render worker plan. Without one, the bot still works, but saved category and panel settings can be lost when Render redeploys the service.
