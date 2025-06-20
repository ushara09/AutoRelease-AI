# 🚀 AI-Powered Release Note Generator

An intelligent web application that automatically generates comprehensive release notes by analyzing JIRA tickets and GitHub repository commits using OpenAI's GPT-4. This tool streamlines the release documentation process by combining project management context with actual code changes.

## ✨ Features

### 🎯 **Core Functionality**
- **JIRA Integration**: Fetches ticket details including summary, description, status, and metadata
- **GitHub Repository Analysis**: Automatically discovers and analyzes commits linked to JIRA tickets
- **AI-Powered Generation**: Uses OpenAI GPT-4 to create comprehensive, professional release notes
- **Smart Pattern Matching**: Identifies commits using `[TICKET-ID]` prefix convention

### 🎨 **Modern Web Interface**
- **Beautiful UI**: Clean, responsive design with gradient themes and smooth animations
- **Repository Dropdown**: Auto-populated dropdown with user's GitHub repositories
- **Visual Indicators**: Programming language emojis, privacy status, and repository descriptions
- **Real-time Feedback**: Loading states, progress indicators, and error handling
- **Mobile Responsive**: Optimized for desktop and mobile devices

### 🔧 **Technical Features**
- **RESTful API**: FastAPI backend with comprehensive error handling
- **CORS Support**: Proper cross-origin configuration for development
- **Token Management**: Secure handling of API tokens and authentication
- **Pagination Handling**: Efficient processing of large repository and commit lists
- **Content Optimization**: Smart truncation and formatting for AI token limits

## 🏗️ Architecture

```
project/
├── backend/                 # FastAPI backend server
│   ├── main.py             # Main application with API endpoints
│   ├── prompt.txt          # AI prompt template for release note generation
│   ├── requirements.txt    # Python dependencies
│   └── .env               # Environment variables (not tracked)
├── frontend/               # Web interface
│   ├── index.html         # Main web application
│   ├── serve.py          # Development server with CORS support
│   └── README.md         # Frontend-specific documentation
├── requirements.txt        # Root project dependencies
├── .gitignore            # Git ignore rules
└── README.md            # This file
```

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Git
- GitHub account with API access
- JIRA account with API access
- OpenAI API account

### 1. Clone the Repository
```bash
git clone <repository-url>
cd AI-Workshop/project
```

### 2. Backend Setup

#### Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

#### Environment Configuration
Create a `.env` file in the `backend` directory:
```env
# JIRA Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_TOKEN=your-jira-api-token

# GitHub Configuration
GITHUB_TOKEN=your-github-personal-access-token
GITHUB_OWNER=your-github-username-or-org

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Email Configuration (for sending release emails)
EMAIL_PASSWORD=your-app-password-for-email
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
```

#### Start Backend Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Backend will be available at `http://localhost:8000`

### 3. Frontend Setup

#### Start Frontend Server
```bash
cd frontend
python serve.py
```
Frontend will be available at `http://localhost:3000`

**Alternative serving options:**
```bash
# Using Python's built-in server
python -m http.server 3000

# Or open index.html directly in browser (may have CORS issues)
```

## 🔑 API Token Setup

### JIRA API Token
1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Copy the generated token to your `.env` file

### GitHub Personal Access Token
1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select scopes: `repo` (for private repos) or `public_repo` (for public repos only)
4. Copy the token to your `.env` file

### OpenAI API Key
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Click "Create new secret key"
3. Copy the key to your `.env` file

## 📖 Usage

### 1. Access the Web Interface
Open your browser and navigate to `http://localhost:3000`

### 2. Generate Release Notes
1. **Select Repository**: Choose from the auto-populated dropdown of your GitHub repositories
2. **Enter JIRA Tickets**: Input one or more ticket IDs (one per line)
   ```
   PROJ-123
   PROJ-124
   PROJ-125
   ```
3. **Generate**: Click the "Generate Release Note" button
4. **Review**: The AI will analyze all tickets and commits to create a comprehensive release note

### 3. Send Release Emails
1. **Enter Module Name**: Input the application/module name (e.g., "Retail Webstore V1")
2. **Enter Git Tag**: Input the release version (e.g., "1.77.0-RC1")
3. **Enter Release Note Link**: Provide the wiki URL for the release note
4. **Send Email**: Click the "Send Release Email" button
5. **Confirmation**: The system will send an email to qa@applova.io and cc devs@applova.io

**Email Template:**
```
Subject: {module_name} | {git_tag}

HI QA Team,

{module_name} | {git_tag} is ready for QA testing.

Wiki - {release_note_link}

Thanks and regards
```

### 4. Commit Convention
Ensure your commits follow the pattern: `[TICKET-ID] Your commit message`

Example:
```bash
git commit -m "[PROJ-123] Add user authentication feature"
git commit -m "[PROJ-123] Fix validation bug in login form"
```

## 🔌 API Endpoints

### Repository Management
- `GET /repositories` - Fetch user's GitHub repositories
- `GET /test-jira/{ticket_key}` - Test JIRA connection with a specific ticket

### Release Note Generation
- `POST /generate-release-note/` - Generate AI-powered release notes
  ```json
  {
    "repo": "repository-name",
    "jira_tickets": ["PROJ-123", "PROJ-124", "PROJ-125"]
  }
  ```

- `POST /generate-release-note-debug/` - Debug endpoint returning raw data without AI processing

### Email Management
- `POST /send-release-email/` - Send release notification email to QA and Dev teams
  ```json
  {
    "module_name": "Retail Webstore V1",
    "git_tag": "1.77.0-RC1",
    "release_note_link": "https://projects.hsenidmobile.com/projects/retail-webstore/wiki/1770-RC1_Release_Note"
  }
  ```

## 🎨 Release Note Template

The AI generates release notes using a structured template including:

- **Prerequisites**: Setup requirements and dependencies
- **New Features and Enhancements**: User-facing improvements
- **Limitations**: Known constraints or incomplete features
- **Bug Fixes**: Issues resolved in this release
- **Areas to Test**: QA focus areas and testing recommendations
- **Impact Area**: Affected services, APIs, and components

## 🔧 Configuration

### Backend Configuration
- **Port**: Default 8000 (configurable via uvicorn)
- **CORS**: Configured for development with multiple origin support
- **Token Limits**: Automatic content truncation for AI processing
- **Pagination**: Handles large repository and commit collections

### Frontend Configuration
- **Port**: Default 3000 (configurable via serve.py)
- **API Base URL**: `http://localhost:8000`
- **Responsive Design**: Supports desktop and mobile devices

## 🐛 Troubleshooting

### Common Issues

#### "Network error: Failed to fetch"
- Ensure backend server is running on port 8000
- Check CORS configuration in backend
- Verify frontend is served from allowed origin

#### "JIRA authentication failed"
- Verify JIRA_EMAIL and JIRA_TOKEN in .env
- Ensure API token has proper permissions
- Check JIRA_BASE_URL format

#### "Failed to fetch repositories"
- Verify GITHUB_TOKEN and GITHUB_OWNER in .env
- Ensure token has repo access permissions
- Check rate limits on GitHub API

#### "OpenAI API errors"
- Verify OPENAI_API_KEY in .env
- Check OpenAI account billing and limits
- Monitor token usage and context length

### Debug Mode
Use the debug endpoint to inspect raw data:
```bash
curl -X POST http://localhost:8000/generate-release-note-debug/ \
  -H "Content-Type: application/json" \
  -d '{"repo": "your-repo", "jira_tickets": ["PROJ-123", "PROJ-124"]}'
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **OpenAI GPT-4** for intelligent release note generation
- **FastAPI** for the robust backend framework
- **JIRA API** for project management integration
- **GitHub API** for repository and commit analysis

## 📞 Support

For issues, questions, or contributions:
1. Check existing [Issues](../../issues)
2. Create a new issue with detailed description
3. Include logs and environment details for bugs

---

**Built with ❤️ using FastAPI, Vanilla JavaScript, and AI** 