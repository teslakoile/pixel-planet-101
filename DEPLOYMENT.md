# 🚀 Deployment Guide

This guide covers deploying the Pixel Planet Weather Agent API to Google Cloud Run.

## 📋 Prerequisites

1. **Google Cloud Account**: With billing enabled
2. **gcloud CLI**: [Install gcloud](https://cloud.google.com/sdk/docs/install)
3. **Docker** (for local testing): [Install Docker](https://docs.docker.com/get-docker/)
4. **Project Setup**: BigQuery dataset with forecast data already loaded

## 🔑 Authentication Setup

1. **Login to Google Cloud**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Set your project**:
   ```bash
   export GCP_PROJECT_ID="pixel-planet-101"  # Your project ID
   gcloud config set project $GCP_PROJECT_ID
   ```

## 🧪 Test Locally First

Before deploying to Cloud Run, test the API locally:

1. **Install API dependencies**:
   ```bash
   pip install fastapi uvicorn pydantic
   ```

2. **Run the API locally**:
   ```bash
   python api_service.py
   ```

3. **Test in another terminal**:
   ```bash
   # Health check
   curl http://localhost:8080/health
   
   # View API docs
   open http://localhost:8080/docs
   
   # Test activity assessment
   curl -X POST http://localhost:8080/api/v1/assess-activity \
     -H "Content-Type: application/json" \
     -d '{
       "location_name": "Mt. Apo",
       "latitude": 6.987,
       "longitude": 125.273,
       "start_time": "2025-10-04T05:00:00",
       "end_time": "2025-10-05T21:00:00",
       "activity_type": "hiking"
     }'
   ```

## ☁️ Deploy to Google Cloud Run

### Option 1: Automated Deployment (Recommended)

Run the deployment script:

```bash
./deploy.sh
```

This script will:
- ✅ Enable required Google Cloud APIs
- ✅ Build the Docker image using Cloud Build
- ✅ Deploy to Cloud Run
- ✅ Configure autoscaling and resource limits
- ✅ Output the service URL

### Option 2: Manual Deployment

1. **Enable required APIs**:
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com
   gcloud services enable cloudbuild.googleapis.com
   ```

2. **Build and push Docker image**:
   ```bash
   PROJECT_ID="pixel-planet-101"
   IMAGE_NAME="gcr.io/${PROJECT_ID}/pixel-planet-api"
   
   gcloud builds submit --tag ${IMAGE_NAME}
   ```

3. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy pixel-planet-api \
     --image ${IMAGE_NAME} \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 2Gi \
     --cpu 2 \
     --timeout 300 \
     --max-instances 10 \
     --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=us-central1"
   ```

4. **Get the service URL**:
   ```bash
   gcloud run services describe pixel-planet-api \
     --platform managed \
     --region us-central1 \
     --format 'value(status.url)'
   ```

## 🧪 Test the Deployed API

1. **Using the test script**:
   ```bash
   ./test_api.sh
   ```

2. **Manual testing**:
   ```bash
   SERVICE_URL="https://pixel-planet-api-xxxxx.run.app"  # Your actual URL
   
   # Health check
   curl ${SERVICE_URL}/health
   
   # Interactive API docs
   open ${SERVICE_URL}/docs
   
   # Activity assessment
   curl -X POST ${SERVICE_URL}/api/v1/assess-activity \
     -H "Content-Type: application/json" \
     -d '{
       "location_name": "Mt. Apo",
       "latitude": 6.987,
       "longitude": 125.273,
       "start_time": "2025-10-04T05:00:00",
       "end_time": "2025-10-05T21:00:00",
       "activity_type": "hiking"
     }'
   ```

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Health check |
| `/docs` | GET | Interactive API documentation (Swagger UI) |
| `/redoc` | GET | Alternative API documentation (ReDoc) |
| `/api/v1/assess-activity` | POST | Activity safety assessment with AI |
| `/api/v1/forecast-data` | POST | Raw forecast data (no AI analysis) |
| `/api/v1/locations/suggest` | GET | Location suggestions |

## 💰 Cost Estimates

### Cloud Run Pricing (us-central1)
- **First 2 million requests/month**: FREE
- **CPU**: $0.00002400 per vCPU-second
- **Memory**: $0.00000250 per GiB-second
- **Requests**: $0.40 per million requests

### Estimated Monthly Cost (Low Traffic)
- **< 10,000 requests/month**: FREE (within free tier)
- **100,000 requests/month**: ~$5-10
- **1,000,000 requests/month**: ~$40-50

### Cost Optimization Tips
1. Set `--min-instances 0` (default) for scale-to-zero
2. Use `--memory 2Gi` instead of higher values
3. Set appropriate `--timeout` (300s = 5 min)
4. Monitor usage in Cloud Console

## 🔒 Security Best Practices

### For Production Deployment:

1. **Enable authentication**:
   ```bash
   # Remove --allow-unauthenticated flag
   gcloud run deploy pixel-planet-api \
     --no-allow-unauthenticated \
     ...other-flags...
   ```

2. **Add API keys** (in `api_service.py`):
   ```python
   from fastapi.security import APIKeyHeader
   
   API_KEY = os.getenv("API_KEY")
   api_key_header = APIKeyHeader(name="X-API-Key")
   
   async def verify_api_key(api_key: str = Depends(api_key_header)):
       if api_key != API_KEY:
           raise HTTPException(status_code=403, detail="Invalid API key")
   ```

3. **Restrict CORS origins**:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-streamlit-app.com"],  # Specific domain
       ...
   )
   ```

4. **Use Secret Manager for credentials**:
   ```bash
   # Store secrets
   echo -n "your-api-key" | gcloud secrets create api-key --data-file=-
   
   # Grant access to Cloud Run
   gcloud secrets add-iam-policy-binding api-key \
     --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   
   # Deploy with secrets
   gcloud run deploy pixel-planet-api \
     --update-secrets=API_KEY=api-key:latest \
     ...other-flags...
   ```

## 📈 Monitoring & Logs

1. **View logs**:
   ```bash
   gcloud run services logs read pixel-planet-api \
     --region us-central1 \
     --limit 50
   ```

2. **Monitor metrics** in Cloud Console:
   - Navigate to: Cloud Run → pixel-planet-api → Metrics
   - View: Request count, latency, CPU/memory usage, errors

3. **Set up alerts**:
   - Cloud Console → Monitoring → Alerting
   - Create alerts for: Error rate > 5%, Latency > 10s, etc.

## 🔄 Update/Redeploy

To update the API after code changes:

```bash
# Option 1: Use deploy script
./deploy.sh

# Option 2: Manual
gcloud builds submit --tag gcr.io/pixel-planet-101/pixel-planet-api
gcloud run deploy pixel-planet-api \
  --image gcr.io/pixel-planet-101/pixel-planet-api \
  --region us-central1
```

## 🐛 Troubleshooting

### Issue: "Service not found"
```bash
# List all Cloud Run services
gcloud run services list --platform managed

# Check specific region
gcloud run services list --region us-central1
```

### Issue: "Permission denied"
```bash
# Check IAM permissions
gcloud projects get-iam-policy pixel-planet-101

# Add required roles
gcloud projects add-iam-policy-binding pixel-planet-101 \
  --member="user:your-email@example.com" \
  --role="roles/run.admin"
```

### Issue: "Container failed to start"
```bash
# Check logs for startup errors
gcloud run services logs read pixel-planet-api --limit 100

# Test Docker image locally
docker build -t test-api .
docker run -p 8080:8080 --env-file .env test-api
```

### Issue: "Agent not initialized"
- Verify BigQuery dataset exists and has data
- Check service account permissions for BigQuery and Vertex AI
- Review environment variables in Cloud Run console

## 🎯 Next Steps

After successful deployment:

1. ✅ **Test all API endpoints** using the test script
2. ✅ **Create a Streamlit app** that consumes this API
3. ✅ **Deploy the Streamlit app** to Streamlit Cloud or Cloud Run
4. ✅ **Set up monitoring and alerts**
5. ✅ **Enable authentication** for production use

## 📚 Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Best Practices for Cloud Run](https://cloud.google.com/run/docs/best-practices)

