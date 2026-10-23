# Deploy to Azure for Students (no credit card)

The app runs as one container on **Azure Container Apps**: FastAPI serves the API and
the React site from the same address, so login cookies work without extra setup.
The database is your free **Neon** PostgreSQL project.

Cost: Container Apps includes a free monthly allowance per subscription
(180,000 vCPU-seconds, 360,000 GiB-seconds, 2 million requests) and costs nothing while
scaled to zero. The image is built and stored for free by GitHub. Your $100 student
credit is only a safety net. Check **Cost Management** in the portal once a week.

You need: an Azure for Students subscription, this repository on GitHub, and the Neon
connection string (Neon console > your project > **Connect**).

---

## 1. Activate Azure for Students

Go to <https://azure.microsoft.com/free/students>, sign in and verify with your
university email. No credit card is asked for.

## 2. Build the image (GitHub, once)

1. Push this repository, including `.github/workflows/docker-image.yml`, to `main`.
2. On GitHub open **Actions** > **Docker image** and wait for the green tick (about 3-5 minutes).
3. Make the image public so Azure can download it without a password:
   your GitHub profile > **Packages** > `ai-interview-coach` > **Package settings** >
   **Change visibility** > **Public**. The image contains no secrets.

The image is `ghcr.io/mennatullah-essam/ai-interview-coach:latest` (all lower case).

## 3. Find a region you are allowed to use

Azure for Students only lets you deploy to a few regions, and the list differs per student.
In the portal search **Policy** > **Assignments** > **Allowed resource deployment regions** >
**Parameters**. Pick one from **Allowed locations**, preferably in Europe (closest to the
Neon database in Frankfurt), for example `germanywestcentral`, `francecentral`, `italynorth`
or `polandcentral`.

## 4. Create the app (Azure Cloud Shell)

In the Azure portal click the **Cloud Shell** icon (`>_`, top bar) and choose **Bash**.
Paste the blocks below one at a time. Replace the two values marked `<...>`.

```bash
# --- settings ------------------------------------------------------------------
LOCATION=<an allowed region, e.g. germanywestcentral>
RG=ai-interview-coach-rg
ENVNAME=ai-interview-coach-env
APP=ai-interview-coach
IMAGE=ghcr.io/mennatullah-essam/ai-interview-coach:latest

# Neon connection string: paste it between the quotes, then change the start from
# postgresql:// to postgresql+psycopg://  (use the non-pooled one, without "-pooler").
DATABASE_URL='<postgresql+psycopg://...neon.tech/ai_interview_coach?sslmode=require&channel_binding=require>'

# A new random secret for signing login tokens. It never leaves Azure.
JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n/+=')
```

```bash
# --- one-time setup --------------------------------------------------------------
az extension add --name containerapp --upgrade --only-show-errors
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait

az group create --name $RG --location $LOCATION -o table

# No log workspace: avoids log-storage charges. Logs still stream with `az containerapp logs show`.
az containerapp env create --name $ENVNAME --resource-group $RG --location $LOCATION \
  --logs-destination none -o table
```

```bash
# --- the app ---------------------------------------------------------------------
az containerapp create --name $APP --resource-group $RG --environment $ENVNAME \
  --image $IMAGE --target-port 8000 --ingress external \
  --cpu 0.5 --memory 1.0Gi --min-replicas 0 --max-replicas 1 \
  --secrets database-url="$DATABASE_URL" jwt-secret="$JWT_SECRET" \
  --env-vars APP_ENV=production DATABASE_URL=secretref:database-url JWT_SECRET=secretref:jwt-secret \
             SIMILARITY_BACKEND=lexical LLM_PROVIDER=none PASSWORD_HASH_COST=15 LOG_LEVEL=INFO \
             ALLOWED_HOSTS=localhost \
  -o table

# Allow the app's own public address (the app rejects unknown host names).
FQDN=$(az containerapp show --name $APP --resource-group $RG --query properties.configuration.ingress.fqdn -o tsv)
az containerapp update --name $APP --resource-group $RG \
  --set-env-vars ALLOWED_HOSTS="$FQDN,localhost" CORS_ORIGINS="https://$FQDN" -o table

echo "Your app: https://$FQDN"
```

The first start takes up to a minute: the container creates the database tables
(`alembic upgrade head`) and loads the question bank, then starts the server.

## 5. Check it

```bash
curl -s https://$FQDN/api/v1/health      # "status":"ok", "database":"ok"
az containerapp logs show --name $APP --resource-group $RG --follow   # Ctrl+C to stop
```

Then open `https://<FQDN>` in a browser: sign up, upload a test CV and run an interview.

## Updating the app later

Push to `main`. When the GitHub Action is green, run in Cloud Shell:

```bash
az containerapp update --name ai-interview-coach --resource-group ai-interview-coach-rg \
  --image ghcr.io/mennatullah-essam/ai-interview-coach:latest --revision-suffix v$(date +%s)
```

## Good to know

- **Cold start:** with `--min-replicas 0` the app sleeps when unused and the first visit
  takes about 20-60 seconds. Before a presentation open the site once, or keep one copy
  running with `az containerapp update ... --min-replicas 1` (small idle charge from your
  credit), and set it back to 0 afterwards.
- **Uploaded CV files are not kept** when the container restarts; the extracted profile
  and interviews are in the database. Use test CVs for a public demo.
- **Secrets** live only in Azure (`--secrets`). Never put them in the repository or in
  `ALLOWED_HOSTS`/`CORS_ORIGINS`-style plain variables.
- **Error `RequestDisallowedByAzure` / `RequestDisallowedByPolicy`:** the region is not
  allowed for your subscription. Delete the group (`az group delete -n $RG`) and repeat
  step 4 with a region from step 3.
- **Remove everything:** `az group delete --name ai-interview-coach-rg` (the Neon database
  is separate and keeps your data).
