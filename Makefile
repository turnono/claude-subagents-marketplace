# Claude Subagents Marketplace Deployment Makefile
# 
# IMPORTANT: When deploying with gcloud, you will be prompted:
# "Allow unauthenticated invocations to [your-service-name] (y/N)?"
# Answer: Y (or press Enter) to allow public access for the marketplace
# This enables the frontend to make requests to the API endpoints
#
# CORS FIX: The main.py includes CORS middleware to allow frontend requests
# This allows the frontend at subagents.web.app to make requests to the API

# ⚠️ WARNING: All deployments must be performed via GitHub Actions workflows ONLY.
# Manual deployments using 'make deploy', 'make deploy-gcloud', or 'make deploy-production' are STRICTLY PROHIBITED.
# Any manual deployment will be considered a violation of project policy.

# Environment variables (set these in your .env file)
GOOGLE_CLOUD_PROJECT ?= taajirah
GOOGLE_CLOUD_LOCATION ?= us-central1
ENV ?= production

install:
	@echo "[Install] Installing Python dependencies..."
	pip install -r requirements.txt

deploy:
	@echo "[Deploy] Deploying Claude Subagents Marketplace to Cloud Run..."
	@echo "✅ Includes CORS fix for frontend compatibility"
	@if [ -z "${GOOGLE_CLOUD_PROJECT}" ]; then \
		echo "❌ Error: GOOGLE_CLOUD_PROJECT environment variable is not set."; \
		echo "Set it in your .env file or export it: export GOOGLE_CLOUD_PROJECT=taajirah"; \
		exit 1; \
	fi
	gcloud run deploy claude-subagents-api \
		--source . \
		--region ${GOOGLE_CLOUD_LOCATION} \
		--allow-unauthenticated \
		--service-account ${GOOGLE_CLOUD_PROJECT}@appspot.gserviceaccount.com \
		--set-env-vars="GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},\
GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION},\
ENV=${ENV},\
FIREBASE_PROJECT_ID=${GOOGLE_CLOUD_PROJECT}"

deploy-staging:
	@echo "[Deploy Staging] Deploying staging service (OPEN ACCESS for testing)..."
	@if [ -z "${GOOGLE_CLOUD_PROJECT}" ]; then \
		echo "❌ Error: GOOGLE_CLOUD_PROJECT environment variable is not set."; \
		echo "Set it in your .env file or export it: export GOOGLE_CLOUD_PROJECT=taajirah"; \
		exit 1; \
	fi
	gcloud run deploy claude-subagents-staging \
		--source . \
		--region ${GOOGLE_CLOUD_LOCATION} \
		--allow-unauthenticated \
		--port 8000 \
		--service-account ${GOOGLE_CLOUD_PROJECT}@appspot.gserviceaccount.com \
		--set-env-vars="GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},\
GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION},\
ENV=staging,\
FIREBASE_PROJECT_ID=${GOOGLE_CLOUD_PROJECT}"

deploy-production:
	@echo "[Deploy Production] Deploying production service..."
	@echo "✅ Includes CORS fix for frontend compatibility"
	@if [ -z "${GOOGLE_CLOUD_PROJECT}" ]; then \
		echo "❌ Error: GOOGLE_CLOUD_PROJECT environment variable is not set."; \
		echo "Set it in your .env file or export it: export GOOGLE_CLOUD_PROJECT=taajirah"; \
		exit 1; \
	fi
	gcloud run deploy claude-subagents-api \
		--source . \
		--region ${GOOGLE_CLOUD_LOCATION} \
		--allow-unauthenticated \
		--service-account ${GOOGLE_CLOUD_PROJECT}@appspot.gserviceaccount.com \
		--set-env-vars="GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},\
GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION},\
ENV=${ENV},\
FIREBASE_PROJECT_ID=${GOOGLE_CLOUD_PROJECT}"

deploy-frontend:
	@echo "[Deploy Frontend] Deploying frontend to Firebase Hosting..."
	firebase deploy --only hosting:subagents --project=${GOOGLE_CLOUD_PROJECT}

# Development and testing commands
test-local:
	@echo "[Test Local] Starting local development server..."
	ENV=staging uvicorn main:app --reload --host 0.0.0.0 --port 8000

test-api:
	@echo "[Test API] Testing API endpoints..."
	curl -X GET "https://claude-subagents-api-${GOOGLE_CLOUD_PROJECT}.${GOOGLE_CLOUD_LOCATION}.run.app/agents" \
		-H "Content-Type: application/json"

test-frontend:
	@echo "[Test Frontend] Testing frontend deployment..."
	curl -s "https://subagents.web.app" | grep -o "Claude Subagents Marketplace" || echo "Frontend not accessible"

check-deployment:
	@echo "[Check Deployment] Testing deployment status..."
	@echo "Frontend: https://subagents.web.app"
	@echo "API: https://claude-subagents-api-${GOOGLE_CLOUD_PROJECT}.${GOOGLE_CLOUD_LOCATION}.run.app"
	@curl -s "https://claude-subagents-api-${GOOGLE_CLOUD_PROJECT}.${GOOGLE_CLOUD_LOCATION}.run.app/agents" | head -5

logs:
	@echo "[View Logs] Viewing recent Cloud Run logs..."
	gcloud run services logs read claude-subagents-api --region=${GOOGLE_CLOUD_LOCATION} --project=${GOOGLE_CLOUD_PROJECT} --limit=20

logs-staging:
	@echo "[View Staging Logs] Viewing recent staging Cloud Run logs..."
	gcloud run services logs read claude-subagents-staging --region=${GOOGLE_CLOUD_LOCATION} --project=${GOOGLE_CLOUD_PROJECT} --limit=20

update-frontend-api-url:
	@echo "[Update Frontend API URL] Updating frontend to point to deployed API..."
	@API_URL="https://claude-subagents-api-855515190257.us-central1.run.app"; \
	sed -i '' "s|const API_BASE_URL = '.*';|const API_BASE_URL = '$$API_URL';|" public/index.html; \
	echo "Updated API URL to: $$API_URL"

deploy-full:
	@echo "[Deploy Full] Deploying both backend and frontend..."
	make deploy
	make update-frontend-api-url
	make deploy-frontend
	@echo "✅ Full deployment complete!"
	@echo "Frontend: https://subagents.web.app"
	@echo "API: https://claude-subagents-api-${GOOGLE_CLOUD_PROJECT}.${GOOGLE_CLOUD_LOCATION}.run.app"

help:
	@echo "Claude Subagents Marketplace Deployment Commands:"
	@echo ""
	@echo "  make install                     - Install Python dependencies"
	@echo "  make deploy                      - Deploy API to Cloud Run"
	@echo "  make deploy-staging              - Deploy staging service (open access)"
	@echo "  make deploy-production           - Deploy production service"
	@echo "  make deploy-frontend             - Deploy frontend to Firebase Hosting"
	@echo "  make deploy-full                 - Deploy both backend and frontend"
	@echo "  make test-local                  - Run local development server"
	@echo "  make test-api                    - Test deployed API endpoints"
	@echo "  make test-frontend               - Test frontend deployment"
	@echo "  make check-deployment            - Check deployment status"
	@echo "  make update-frontend-api-url     - Update frontend API URL"
	@echo "  make logs                        - View recent Cloud Run logs"
	@echo "  make logs-staging                - View staging logs"
	@echo ""
	@echo "DEPLOYMENT NOTE:"
	@echo "When deploying, answer 'Y' to 'Allow unauthenticated invocations?' for public API access"
	@echo ""
	@echo "CORS FIX:"
	@echo "The main.py includes CORS middleware to allow frontend requests"
	@echo "This allows the frontend at subagents.web.app to make requests to the API" 