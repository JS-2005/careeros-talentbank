# Submission Checklist

## Build Commands
**Frontend**:
```bash
cd frontend
npm install
npm run build
```

**Backend**:
```bash
cd backend
python -m venv .venv

# On Unix / macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

pip install -r requirements.txt
python -m uvicorn main:app --reload
```

## Environment Variables required (.env)
- `GEMINI_API_KEY`
- `PINECONE_API_KEY`
- `SERPAPI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

## Demo Flow
1. **Landing Page**: Explains the value proposition for Students (Job Matcher) and Employers (Screening Layer).
2. **Student Job Matcher**: Upload resume -> Match jobs -> View readiness scores and skill gaps. (Includes fallback static demo).
3. **Employer Report Demo**: Accessible via the "View Employer Report Demo" CTA. Shows a structured mock AI evaluation report for a candidate without requiring external live API calls.

## Known Limitations
- The live AI features (Gemini, Pinecone) require valid API keys. During competition pitch, static demo fallbacks will be used to ensure presentation stability.
- WebRTC live interviews are experimental and heavily dependent on stable network environments; thus, the demo primarily showcases the generated report.

## Responsible AI Statement
All AI-generated insights (Job Matcher, Interview Report) are decision-support tools and **do not replace** human judgment.
