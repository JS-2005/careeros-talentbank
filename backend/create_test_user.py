import asyncio
from supabase import create_client
from core.config import settings

async def main():
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    email = "testuser@example.com"
    password = "Password123!"
    
    print(f"URL: {settings.SUPABASE_URL}")
    print(f"Trying to sign up/in user: {email}")
    
    try:
        # Try signing up
        res = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        print("Sign up successful!")
        user = res.user
        session = res.session
    except Exception as e:
        print(f"Sign up failed or user already exists, trying sign in: {e}")
        try:
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            print("Sign in successful!")
            user = res.user
            session = res.session
        except Exception as e2:
            print(f"Sign in failed too: {e2}")
            return

    if session:
        print("\n--- AUTH SUCCESS ---")
        print(f"User ID: {user.id}")
        print(f"Access Token:\n{session.access_token}")
        print("--------------------")
    else:
        print("No session returned.")

if __name__ == "__main__":
    asyncio.run(main())
