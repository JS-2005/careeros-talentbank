from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api.routes import router

app = FastAPI(title="Job Matcher API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:4200",
        "http://localhost:5173",
        "https://careeros-talentbank.vercel.app",
    ],
    allow_origin_regex=r"https://careeros-talentbank.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler so unhandled errors still return a proper JSON response
    with CORS headers attached by the middleware (prevents browser CORS errors on 500s)."""
    print(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )

app.include_router(router, prefix="/api/v1")

@app.get("/")
def health_check():
    print("Successfully executed health_check")
    return {"status": "Server is running perfectly"}

