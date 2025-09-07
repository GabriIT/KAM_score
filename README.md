# KAM Rewards (v4)
- Scoring aligned with revised Remarks
- Real promotions in PP decrease, SOP-delay penalty, inactivity penalty
- Dataset & Inputs tables with KAM/Month filters and CSV exports
- EMS logo on the dashboard
- Regions: China Consumer, China Industry, JP, TW

## Local run
```bash
docker compose up --build -d
curl -X POST http://localhost:8000/seed -H "Content-Type: application/json" -d '{}'
# open http://localhost:5173
```

## CSV
- /scores_csv, /scores_cumulative_csv
- /dataset_csv, /inputs_csv

## Dokku DB persistence
```bash
# install postgres plugin
sudo dokku plugin:install https://github.com/dokku/dokku-postgres.git

# create db and link to backend app (api-reward)
dokku postgres:create kam-rewards-db
dokku postgres:link kam-rewards-db api-reward  # sets DATABASE_URL

# (optional) for SQLite persistence instead
dokku storage:mount api-reward /var/lib/dokku/data/storage/api-reward:/app/data
dokku config:set api-reward DB_URL=sqlite:////app/data/kam.db
```

In production prefer Postgres (DATABASE_URL is auto-read by the backend).
