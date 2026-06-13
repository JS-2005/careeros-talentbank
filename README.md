# TalentBank Sandbox

TalentBank Sandbox is an AI-powered Job Matcher application that processes candidate profiles, searches for active job matches using **SerpAPI**, evaluates and ranks them using **Google Gemini**, and integrates with **Supabase** and **Pinecone** for data persistence and vector searches.

The project is structured as a monorepo containing:
*   **Frontend**: Built with **Angular** (`/frontend`)
*   **Backend**: Built with **FastAPI** (`/backend`)

---

## Project Architecture & Configuration

This project is configured to run as a single Vercel deployment using **Vercel Services** (configured via the root [vercel.json](file:///c:/Users/khorj/Desktop/talentbank-sandbox/vercel.json)):

*   **Frontend Service**: Routes all traffic from `/` to the Angular app.
*   **Backend Service**: Routes all traffic from `/_/backend` to the FastAPI backend.

This routing setup ensures both apps are served under the same domain, preventing CORS issues in production and making API communication simple and secure.

---

## Local Development Setup

To run this project locally, you will need to start both the backend and frontend servers.

### 1. Backend Setup (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the `backend` directory (using the variables from `.env.example` or your sandbox values):
   ```env
   GEMINI_API_KEY="your-gemini-key"
   PINECONE_API_KEY="your-pinecone-key"
   SERPAPI_API_KEY="your-serpapi-key"
   SUPABASE_URL="your-supabase-url"
   SUPABASE_KEY="your-supabase-key"
   ```
5. Run the FastAPI development server:
   ```bash
   fastapi dev main.py
   ```
   The backend will be running at `http://localhost:8000`. You can check the OpenAPI documentation at `http://localhost:8000/docs`.

### 2. Frontend Setup (Angular)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Start the Angular dev server:
   ```bash
   npm run start
   ```
   The application will be accessible at `http://localhost:4200`. The development build automatically uses the configuration in `environment.development.ts`, pointing to the local backend at `http://localhost:8000`.

---

## How to Deploy to Vercel

Since you have already uploaded the project to GitHub, deploying the entire project (both Frontend and Backend) to Vercel takes only a few steps.

### Step 1: Connect your GitHub Repo to Vercel

1. Log in to the [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** and select **Project**.
3. Locate your GitHub repository (e.g., `talentbank-sandbox`) and click **Import**.

### Step 2: Automatic Vercel Services Detection

> [!NOTE]
> Vercel automatically detects the root [vercel.json](file:///c:/Users/khorj/Desktop/talentbank-sandbox/vercel.json) file which contains the `experimentalServices` configuration. It will automatically provision and build two separate services (the Angular frontend and the FastAPI backend) under the same deployment URL.

### Step 3: Configure Environment Variables

Before clicking deploy, you must add the backend environment variables so the FastAPI service can connect to the AI models and databases.

1. In the Vercel project configuration page, expand the **Environment Variables** section.
2. Add the following environment variables (values can be retrieved from your local `.env` file):

| Variable Name | Description |
| :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API key for job compatibility analysis |
| `PINECONE_API_KEY` | Pinecone API key for vector storage / matching |
| `SERPAPI_API_KEY` | SerpAPI key for Google Jobs searches |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your Supabase public/service API key |

### Step 4: Click Deploy!

1. Click **Deploy**.
2. Vercel will build the frontend (`frontend` directory) and the backend serverless functions (`backend` directory) in parallel.
3. Once completed, your application will be live at `https://your-project-name.vercel.app`.

---

## Verifying the Deployment

1. **Verify Backend Health**: 
   Open `https://your-project-name.vercel.app/_/backend/` in your browser. It should return:
   ```json
   {
     "status": "Server is running perfectly"
     }
   ```
2. **Verify Frontend**:
   Open `https://your-project-name.vercel.app/`. You should see the Angular job-matching interface loading correctly and interacting with the backend APIs via `/_/backend/api/v1/...`.
