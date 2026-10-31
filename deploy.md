# Deploying Hoshiyar on Fly.io

One machine in Mumbai, always on, the data files on a 1 GB volume. Run everything from the repo root.
`flyctl` is installed and logged in (`fly auth whoami` to check).

## First deploy

```sh
# 1. Create the app. If fly says the name is taken, create it with another name (say hoshiyar-fleet)
#    and change the app = "..." line in fly.toml to match; the URL below changes with it.
fly apps create hoshiyar

# 2. The volume for data/ (roster, records, schedule, trials). Same region as the machine.
fly volumes create hoshiyar_data --region bom --size 1 --yes

# 3. Secrets, straight from .env (comments and blank lines dropped). .env never leaves this laptop otherwise.
grep -Ev '^\s*(#|$)' .env | fly secrets import

# 4. The public URL Vobiz must call back on. Use the app name fly chose in step 1.
fly secrets set LOCAL_SERVER_URL=https://hoshiyar.fly.dev

# 5. Build and deploy. The first build takes several minutes (Pipecat is large); later ones are quicker.
fly deploy

# 6. Put the roster on the volume. The machine starts with an empty /data.
fly ssh sftp shell
#   inside the sftp shell:   put data/drivers.json /data/drivers.json      then  exit
```

Then open `https://hoshiyar.fly.dev/fleet`, book a trial, and check the logs while the phone rings:

```sh
fly logs
```

## Day to day

```sh
fly deploy                 # after a git commit you want live
fly logs                   # the same output the laptop terminal showed
fly status                 # machine state, region, health check
fly ssh console            # a shell on the machine, if ever needed
fly machine stop <id>      # pause between the judging week and the finale; billing stops too
fly machine start <id>
```

Edit the roster on the volume with `fly ssh sftp shell` (`get` / `put`), or `fly ssh console` and `vi /data/drivers.json`.
The rota re-reads it every 20 s; no restart needed.

## Custom domain (optional, any time)

In Cloudflare, zone bharatghumio.com: add a CNAME `hoshiyar` -> `hoshiyar.fly.dev`, proxy **off**. Then:

```sh
fly certs add hoshiyar.bharatghumio.com
fly secrets set LOCAL_SERVER_URL=https://hoshiyar.bharatghumio.com
```

`fly certs check hoshiyar.bharatghumio.com` shows when the certificate is issued (a minute or two).
The fly.dev name keeps working alongside.

## What to know

- One process only. The scheduler's calls and the alert queue are in memory; never scale to two machines.
- `TZ=Asia/Kolkata` is set in the image and in fly.toml. The roster's check-in times are local time.
- Memory: 512 MB plus 512 MB swap. The app idles near 250 MB; a call adds about 100 MB. If `fly status`
  ever shows OOM restarts, `fly scale memory 1024` is the fix (about double the price).
- Secrets changed with `fly secrets set` restart the machine automatically.
- Cost: about $3.50 a month for the machine while it runs, billed hourly, plus a few cents for the volume.
