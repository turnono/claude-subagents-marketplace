# Claude Subagents Marketplace

A modern web platform for discovering, sharing, and managing Claude-compatible subagents. Built with FastAPI, Firebase, and a beautiful responsive frontend.

## 🚀 Features

- **Agent Discovery**: Browse and search through available subagents
- **Agent Submission**: Submit new subagents with authentication
- **GitHub Integration**: Auto-import agents from GitHub repositories
- **Community Features**: Like, rate, and comment on subagents
- **Modern UI**: Responsive design with TailwindCSS
- **API Access**: Full REST API for programmatic access

## 📁 Project Structure

```
claude-subagents-marketplace/
├── main.py                 # FastAPI backend server
├── public/
│   ├── index.html         # Main listing page
│   └── detail.html        # Subagent detail page
├── agents/                # User-submitted subagents
├── community_agents/      # Imported from GitHub
├── subagents/            # Additional subagent storage
├── firebase-admin-key.json # Firebase credentials (replace with your own)
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## 🛠️ Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Firebase Setup

1. Create a Firebase project at [Firebase Console](https://console.firebase.google.com/)
2. Enable Firestore Database
3. Enable Authentication (Email/Password)
4. Generate a service account key:
   - Go to Project Settings > Service Accounts
   - Click "Generate new private key"
   - Download the JSON file
   - Replace `firebase-admin-key.json` with your downloaded file

### 3. Environment Variables (Optional)

Create a `.env` file for custom configuration:

```env
FIREBASE_CREDENTIALS=firebase-admin-key.json
```

### 4. Run the Development Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at `http://localhost:8000`

## 📋 API Endpoints

| Method | Endpoint        | Description                   |
| ------ | --------------- | ----------------------------- |
| GET    | `/`             | Serve homepage                |
| GET    | `/agents`       | List/search agents            |
| GET    | `/meta`         | Get Firebase metadata         |
| POST   | `/agents`       | Add new agent (auth required) |
| POST   | `/like/{agent}` | Like an agent                 |
| POST   | `/import`       | Import from GitHub            |
| GET    | `/docs.html`    | API documentation             |

## 🎨 Frontend Features

- **Responsive Design**: Works on desktop and mobile
- **Search Functionality**: Real-time search across agents
- **Detail Pages**: Comprehensive agent information
- **Rating System**: Community-driven ratings and reviews
- **Modern UI**: Dark theme with TailwindCSS

## 🔧 Development

### Adding New Subagents

1. Create a `.md` file in the `agents/` directory
2. Include YAML frontmatter with:
   ```yaml
   ---
   name: Your Agent Name
   description: Brief description
   tools: [Tool1, Tool2, Tool3]
   ---
   ```
3. Add your agent content below the frontmatter

### Customizing the UI

- Edit `public/index.html` for the main listing page
- Edit `public/detail.html` for individual agent pages
- Styles are handled by TailwindCSS CDN

## 🚀 Deployment

### Firebase Hosting

1. Install Firebase CLI:

   ```bash
   npm install -g firebase-tools
   ```

2. Initialize Firebase:

   ```bash
   firebase init hosting
   ```

3. Deploy:
   ```bash
   firebase deploy
   ```

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🆘 Support

For issues and questions:

- Create an issue on GitHub
- Check the API documentation at `/docs.html`
- Review the Firebase setup guide

## 🎯 Roadmap

- [ ] User authentication system
- [ ] Advanced search filters
- [ ] Agent categories and tags
- [ ] Download analytics
- [ ] Social sharing features
- [ ] Mobile app
- [ ] API rate limiting
- [ ] Caching layer
