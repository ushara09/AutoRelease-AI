# Release Note Generator Web UI

A simple web interface for generating release notes using JIRA tickets and GitHub repository data.

## Setup

1. **Start the Backend Server**
   ```bash
   cd backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
   The backend should be running on `http://localhost:8000`

2. **Start the Frontend Server**
   ```bash
   cd frontend
   python serve.py
   ```
   Then visit `http://localhost:3000`
   
   **Alternative methods:**
   - Using Python's built-in server: `python -m http.server 3000`
   - Or simply open `index.html` directly in your browser (may have CORS issues)

## Usage

1. Enter the **Repository Name** (e.g., "my-project")
2. Enter the **JIRA Ticket** (e.g., "PROJ-123")
3. Click **Generate Release Note**
4. Wait for the AI to analyze the JIRA ticket and GitHub commits
5. Review the generated release note

## Features

- Clean, modern responsive design
- Real-time loading indicators
- Error handling and user feedback
- Automatic scrolling to results
- Mobile-friendly interface

## Requirements

- Backend server running on port 8000
- Modern web browser with JavaScript enabled
- Internet connection for API calls

## Troubleshooting

- **"Network error"**: Make sure the backend server is running on `http://localhost:8000`
- **CORS errors**: The backend is configured to allow requests from `http://localhost:3000`
- **API errors**: Check the backend logs for detailed error information 