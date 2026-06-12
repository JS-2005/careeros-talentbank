from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(title="Job Matcher API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://resume-matcher-eight-flax.vercel.app", "http://localhost:4200"], # For development, allow all origins. Consider restricting this in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

@app.get("/")
def health_check():
    print("Successfully executed health_check")
    return {"status": "Server is running perfectly"}
