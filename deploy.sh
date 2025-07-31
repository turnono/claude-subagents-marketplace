#!/bin/bash

echo "🚀 Deploying Claude Subagents Marketplace..."

# Deploy frontend to Firebase
echo "📦 Deploying frontend to Firebase Hosting..."
firebase deploy --only hosting

# Instructions for backend deployment
echo ""
echo "✅ Frontend deployed successfully!"
echo ""
echo "🌐 Your frontend is now live at:"
echo "   https://taajirah.web.app"
echo ""
echo "📋 Next steps for backend deployment:"
echo "1. Deploy backend to Railway:"
echo "   - Go to https://railway.app"
echo "   - Connect your GitHub repository"
echo "   - Deploy the backend"
echo ""
echo "2. Update the API_BASE_URL in public/index.html with your Railway URL"
echo ""
echo "3. Re-deploy the frontend:"
echo "   firebase deploy --only hosting"
echo ""
echo "🎉 Your marketplace will be fully functional!" 