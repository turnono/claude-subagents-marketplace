#!/bin/bash

echo "🚀 Deploying Claude Subagents Marketplace (Firebase-Only Version)"

# Deploy Firebase Functions
echo "📦 Deploying Firebase Functions..."
firebase deploy --only functions

# Deploy Frontend
echo "🌐 Deploying Frontend..."
firebase deploy --only hosting:subagents

echo ""
echo "✅ Deployment Complete!"
echo ""
echo "🌐 Frontend: https://subagents.web.app"
echo "🔧 API: https://us-central1-taajirah.cloudfunctions.net/api"
echo ""
echo "📋 Next Steps:"
echo "1. Add sample agents to Firestore"
echo "2. Set up Firebase Authentication"
echo "3. Configure CORS for your domain"
echo ""
echo "🎉 Your Firebase-only marketplace is ready!" 