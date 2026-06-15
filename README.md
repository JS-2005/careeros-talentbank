# CareerOS TalentBank 🚀

CareerOS TalentBank is an intelligent, AI-powered career platform designed to streamline the job search process. It leverages advanced LLMs and semantic search to analyze resumes, find highly relevant job postings, and conduct AI-driven mock interviews.

## 🌟 Key Features

- **AI-Powered Job Matching**: Upload a resume, and the platform uses Google Gemma (via LangChain) to extract skills, experience, and target roles.
- **Smart Job Search**: Automatically fetches live job postings from SerpApi based on the extracted resume profile.
- **Semantic Ranking**: Uses Pinecone Vector Database and RRF (Reciprocal Rank Fusion) to semantically match and score jobs against the user's profile.
- **AI Mock Interviews**: Dedicated meeting rooms for AI-driven technical and behavioral interviews, complete with a lobby and post-interview reports.
- **User Dashboard**: A unified internal dashboard with a marketplace, profile management, and a job matching hub.
- **Authentication**: Seamless user authentication and session management using Supabase.

## 🛠️ Tech Stack

### Frontend
- **Framework**: Angular (v21)
- **Language**: TypeScript
- **Styling**: Vanilla CSS / Tailwind (integrated via Angular)
- **UI Components**: `@mysten/sui`
- **Backend as a Service (BaaS)**: Supabase JS Client

### Backend
- **Framework**: FastAPI (Python 3)
- **AI & LLMs**: LangChain, Google GenAI (Gemma)
- **Vector Database**: Pinecone
- **External APIs**: SerpApi (Job Search)
- **Database**: Supabase (PostgreSQL)

---

## 🏗️ Project Structure

This is a monorepo consisting of both frontend and backend code, configured for unified deployment on Vercel.

```text
careeros-talentbank-main/
├── backend/                  # FastAPI Application
│   ├── api/                  # Route handlers and endpoints
│   ├── core/                 # App configurations and constants
│   ├── schemas/              # Pydantic models for validation
│   ├── services/             # Business logic (Pinecone, SerpApi, AI Extraction)
│   ├── tests/                # Unit and integration tests
│   ├── main.py               # FastAPI entry point
│   └── requirements.txt      # Python dependencies
├── frontend/                 # Angular Application
│   ├── src/
│   │   ├── app/
│   │   │   ├── auth/         # Authentication modules
│   │   │   ├── internal/     # Main dashboard (Marketplace, Job Matching, Profile)
│   │   │   ├── meeting-room/ # AI Interview Room UI
│   │   │   └── ...           # Additional Angular components
│   ├── package.json          # Node dependencies
│   └── angular.json          # Angular workspace configuration
└── vercel.json               # Monorepo deployment configuration for Vercel
```

---

## 🚀 Getting Started

### Prerequisites
- Node.js (v18 or higher)
- Angular CLI (`npm install -g @angular/cli`)
- Python 3.9+
- API Keys for: Supabase, Pinecone, Google Gemini, and SerpApi.

### 1. Backend Setup

Navigate to the backend directory and set up the Python environment:

```bash
cd backend
python -m venv venv
# On Windows: venv\Scripts\activate
# On Mac/Linux: source venv/bin/activate

pip install -r requirements.txt
```

**Environment Variables:**
Create a `.env` file in the `backend` directory (or export them) with your API keys:
```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
PINECONE_API_KEY=your_pinecone_api_key
GOOGLE_API_KEY=your_google_api_key
SERPAPI_API_KEY=your_serpapi_api_key
```

**Run the Backend Server:**
```bash
fastapi dev main.py
# or using uvicorn: uvicorn main:app --reload
```
The backend API will be available at `http://localhost:8000`.

### 2. Frontend Setup

Navigate to the frontend directory and install dependencies:

```bash
cd frontend
npm install
```

**Run the Frontend Server:**
```bash
npm start
# or: ng serve
```
The frontend application will be available at `http://localhost:4200`.

---

## 🧪 Testing

### Backend
The backend uses `pytest` for testing integrations.
```bash
cd backend
pytest
```

### Frontend
The frontend uses `vitest` for unit testing.
```bash
cd frontend
npm run test
```

---

## 🌐 Deployment

This project is pre-configured for deployment on **Vercel**. 
The `vercel.json` at the root of the project routes traffic appropriately:
- `/` routes to the Angular frontend.
- `/_/backend/*` routes to the FastAPI backend.

To deploy:
1. Import the repository into Vercel.
2. Ensure you add all required environment variables in the Vercel dashboard.
3. Vercel will automatically build the Angular app and deploy the FastAPI serverless functions.
